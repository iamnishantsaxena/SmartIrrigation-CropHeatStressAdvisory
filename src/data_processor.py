"""Raw Conduit AWS readings (~15 min, UTC) -> daily ET0, water deficit, heat stress."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "Data" / "weatherdata.csv"
OUT_CSV = ROOT / "Data" / "processed_weather.csv"

# JKUAT weather station, Juja, Kenya
LAT_DEG = -1.09
ELEVATION_M = 1520
TZ = "Africa/Nairobi"
READINGS_PER_DAY = 96  # one every 15 min
MIN_COVERAGE = 0.8     # drop partial days (ET from half a day's Tmin/Tmax is wrong)

# Heat stress thresholds. Crop: maize/beans pollination suffers above ~30-32 °C.
# WBGT: field-worker thresholds (ISO 7243, moderate work).
HEAT_HIGH = {"temp_max": 32.0, "wbgt_max": 26.0}
HEAT_MODERATE = {"temp_max": 28.0, "wbgt_max": 22.0}


def heat_stress_level(temp_max, wbgt_max):
    if temp_max >= HEAT_HIGH["temp_max"] or wbgt_max >= HEAT_HIGH["wbgt_max"]:
        return "HIGH"
    if temp_max >= HEAT_MODERATE["temp_max"] or wbgt_max >= HEAT_MODERATE["wbgt_max"]:
        return "MODERATE"
    return "LOW"


def load_raw(path=RAW_CSV):
    df = pd.read_csv(path, parse_dates=["ts"])
    df["ts"] = df["ts"].dt.tz_convert(TZ)
    # rg1tt is a cumulative bucket total that resets daily; rain = positive increments.
    # (rg2tt fluctuates up and down every day, so it is not accumulated rain; ignored.)
    df["rain_mm"] = df["rg1tt"].diff().clip(lower=0).fillna(0)
    return df


def fao56_et0(tmin, tmax, rh_mean, wind_ms, pressure_kpa, day_of_year):
    """FAO-56 Penman-Monteith reference ET (mm/day).

    Solar radiation is estimated from the temperature range (FAO-56 eq. 50)
    because the station's UV/solar sensor reads 0 throughout.
    """
    tmean = (tmin + tmax) / 2
    es_t = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))
    es = (es_t(tmax) + es_t(tmin)) / 2
    ea = es * rh_mean / 100
    delta = 4098 * es_t(tmean) / (tmean + 237.3) ** 2
    gamma = 0.000665 * pressure_kpa

    phi = np.radians(LAT_DEG)
    dr = 1 + 0.033 * np.cos(2 * np.pi * day_of_year / 365)
    decl = 0.409 * np.sin(2 * np.pi * day_of_year / 365 - 1.39)
    ws = np.arccos(-np.tan(phi) * np.tan(decl))
    ra = 24 * 60 / np.pi * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.sin(ws))
    rs = 0.16 * np.sqrt(tmax - tmin) * ra  # interior location, kRs = 0.16
    rso = (0.75 + 2e-5 * ELEVATION_M) * ra
    rnl = (4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
           * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * np.minimum(rs / rso, 1) - 0.35))
    rn = 0.77 * rs - rnl

    return (0.408 * delta * rn + gamma * 900 / (tmean + 273) * wind_ms * (es - ea)) / (
        delta + gamma * (1 + 0.34 * wind_ms))


def process(raw: pd.DataFrame) -> pd.DataFrame:
    daily = raw.groupby(raw["ts"].dt.date).agg(
        temp_min=("temp_sht", "min"),
        temp_max=("temp_sht", "max"),
        humidity_mean=("humidity_sht", "mean"),
        rainfall_mm=("rain_mm", "sum"),
        wind_mean=("wind_spd", "mean"),
        pressure_kpa=("press_bmx", lambda p: p.mean() / 10),
        heat_index_max=("heat_idx", "max"),
        wbgt_max=("wet_bulb_globe_temp", "max"),
        readings=("ts", "size"),
    )
    daily.index = pd.to_datetime(daily.index)
    daily.index.name = "date"
    daily["coverage"] = (daily["readings"] / READINGS_PER_DAY).clip(upper=1)
    daily = daily[daily["coverage"] >= MIN_COVERAGE].copy()

    daily["ET_mm"] = fao56_et0(daily["temp_min"], daily["temp_max"], daily["humidity_mean"],
                               daily["wind_mean"], daily["pressure_kpa"], daily.index.dayofyear)
    daily["water_deficit_mm"] = daily["ET_mm"] - daily["rainfall_mm"]
    daily["heat_stress_level"] = [heat_stress_level(t, w) for t, w in
                                  zip(daily["temp_max"], daily["wbgt_max"])]

    cols = ["ET_mm", "water_deficit_mm", "heat_stress_level", "rainfall_mm", "temp_min",
            "temp_max", "humidity_mean", "wbgt_max", "heat_index_max", "coverage"]
    out = daily[cols].reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.round(2)


def run(path=RAW_CSV, out=OUT_CSV) -> pd.DataFrame:
    df = process(load_raw(path))
    df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    print(run().to_string(index=False))
