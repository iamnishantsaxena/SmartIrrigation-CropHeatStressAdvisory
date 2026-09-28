"""Raw Conduit AWS readings (~15 min, UTC) -> daily ET0, water deficit, heat stress."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "Data" / "weatherdata.csv"
OUT_CSV = ROOT / "Data" / "processed_weather.csv"
ARCHIVE_CSV = ROOT / "Data" / "conduit_archive.csv"  # offline copy of API history (see archive())
CONDUIT_URL = "https://conduit.jhubafrica.com/data.php"

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


def load_dotenv(path=ROOT / ".env"):
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, val = line.partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), val.strip())


def _prepare(df):
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(TZ)
    # rg1tt is a cumulative bucket total that resets daily; rain = positive increments.
    # (rg2tt fluctuates up and down every day, so it is not accumulated rain; ignored.)
    df["rain_mm"] = df["rg1tt"].diff().clip(lower=0).fillna(0)
    return df


def load_raw(path=RAW_CSV):
    return _prepare(pd.read_csv(path))


def fetch_conduit(fromdate: date, todate: date) -> pd.DataFrame:
    """Raw readings (UTC ts, as in the CSV) from the Conduit API. Dates inclusive, max ~1 month apart."""
    body = urllib.parse.urlencode({
        "apikey": os.environ["CONDUIT_API_KEY"], "email": os.environ["CONDUIT_EMAIL"],
        "fromdate": fromdate.isoformat(), "todate": todate.isoformat()}).encode()
    try:
        with urllib.request.urlopen(CONDUIT_URL, body, timeout=60) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:  # errors come back as JSON with a 4xx status
        payload = json.load(e)
    if payload.get("status") != "success":
        raise RuntimeError(f"Conduit API: {payload.get('message')}")
    df = pd.DataFrame(payload["data"], columns=payload["headers"])
    num = df.columns.drop("ts")
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    return df


def fetch_range(start: date, end: date, verbose=False) -> pd.DataFrame:
    """Raw API readings start..end of any length, one request per calendar month."""
    chunks = []
    for m in pd.date_range(start.replace(day=1), end, freq="MS").date:
        first, last = max(m, start), min((pd.Timestamp(m) + pd.offsets.MonthEnd()).date(), end)
        chunks.append(fetch_conduit(first, last))
        if verbose:
            print(f"{first} .. {last}: {len(chunks[-1])} readings")
    return pd.concat(chunks).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


# ponytail: unbounded-age cache; fine because ranges end >= 2 days ago, so data is final.
@lru_cache(maxsize=64)
def fetch_days(start: date, end: date) -> pd.DataFrame:
    """Processed local (Nairobi) days start..end from the live API. Do not mutate the result."""
    # Local day D starts at 21:00 UTC on D-1, so fetch one extra UTC day in front.
    df = process(_prepare(fetch_range(start - timedelta(days=1), end)))
    return df[df["date"].between(start.isoformat(), end.isoformat())].reset_index(drop=True)


def archive(start: date, end: date, out=ARCHIVE_CSV) -> pd.DataFrame:
    """Save raw API readings start..end to CSV for offline use."""
    df = fetch_range(start, end, verbose=True)
    df.to_csv(out, index=False)
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
    import sys
    if sys.argv[1:2] == ["--archive"]:  # python -m src.data_processor --archive 2025-06-01 2026-09-26
        load_dotenv()
        archive(date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3]))
    else:
        print(run().to_string(index=False))
