import pandas as pd
import pytest

from src.irrigation_advisor import IrrigationAdvisor


def days(et, rain=None):
    rain = rain or [0.0] * len(et)
    return pd.DataFrame({"date": [f"2026-04-{d + 1:02d}" for d in range(len(et))],
                         "ET_mm": et, "water_deficit_mm": [e - r for e, r in zip(et, rain)],
                         "rainfall_mm": rain, "temp_min": 16.0, "temp_max": 28.0,
                         "humidity_mean": 65.0, "wbgt_max": 21.0, "coverage": 0.99})


def test_tops_up_to_rain_buffer():
    # Soil already 8 mm dry + 4.5 mm ET = 12.5 mm; top up 2.5 mm back to the 10 mm buffer.
    r = IrrigationAdvisor(efficiency=1.0, application_rate_mm_h=2.5, rain_buffer_mm=10) \
        .calculate_irrigation_need("d", 4.5, 0, soil_depletion_mm=8)
    assert r["irrigation_needed"] and r["irrigation_amount_mm"] == 2.5
    assert r["timing"] == "06:00-07:00 (1.0 h)"
    assert r["soil_deficit_mm"] == 12.5 and r["soil_deficit_end_mm"] == 10


def test_efficiency_increases_amount():
    r = IrrigationAdvisor(efficiency=0.9).calculate_irrigation_need("d", 4.5, 0, soil_depletion_mm=10)
    assert r["irrigation_amount_mm"] == 5.0


def test_moist_soil_skips_irrigation():
    r = IrrigationAdvisor().calculate_irrigation_need("d", 4.0, 0, soil_depletion_mm=0)
    assert not r["irrigation_needed"] and r["soil_deficit_end_mm"] == 4.0
    assert "still moist" in r["reason"]


def test_rain_refills_soil_and_excess_drains():
    r = IrrigationAdvisor().calculate_irrigation_need("d", -12.0, 16.0, soil_depletion_mm=10)
    assert not r["irrigation_needed"] and r["soil_deficit_end_mm"] == 0  # not negative
    assert "Rain" in r["reason"]


def test_crop_coefficient_scales_et_not_rain():
    # ET0 = 3 + 1 = 4; crop ET = 1.2 * 4 = 4.8; depletion = 10 + 4.8 - 1 = 13.8; top up 3.8
    r = IrrigationAdvisor(kc=1.2, efficiency=1.0).calculate_irrigation_need("d", 3.0, 1.0, soil_depletion_mm=10)
    assert r["irrigation_amount_mm"] == 3.8


def test_rain_postpones_irrigation_for_days():
    # Like 7 Apr 2026: 16 mm rain on a dry-ish soil, then 4 mm/day ET.
    plan = IrrigationAdvisor().plan(days([4] * 4 + [3] + [4] * 5, rain=[0] * 4 + [16] + [0] * 5))
    needed = [a["irrigation"]["irrigation_needed"] for a in plan]
    #          dry-down to buffer        rain   2 days of stored water, then daily top-ups
    assert needed == [False, False, True, True, False, False, False, True, True, True]


def test_state_converges_regardless_of_start():
    # Same final week whether the simulation starts 10 or 20 days earlier.
    df = days([3.5, 4, 4.2, 2, 3.8, 4.4, 4, 3.9, 4.1, 3.6, 4, 4.3, 3.2, 4.5, 4, 3.8, 4.1, 3.9, 4.2, 4, 3.7, 4.4],
              rain=[0, 0, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0, 12, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    long_run, short_run = IrrigationAdvisor().plan(df)[-7:], IrrigationAdvisor().plan(df.iloc[5:])[-7:]
    assert long_run == short_run


def test_heat_stress():
    h = IrrigationAdvisor().assess_heat_stress("d", 26.5, (18, 31))
    assert h["heat_level"] == "HIGH" and h["mitigation"]


def test_7day_forecast_uses_latest_week():
    out = IrrigationAdvisor().generate_7day_forecast(days([4.0] * 10))
    assert [a["date"] for a in out] == [f"2026-04-{d:02d}" for d in range(4, 11)]
    assert out[0]["irrigation"]["confidence"] == 0.99


@pytest.mark.parametrize("amount", [4.0, 25.0])
def test_amount_never_negative(amount):
    r = IrrigationAdvisor().calculate_irrigation_need("d", amount - 30, 30, soil_depletion_mm=5)
    assert r["irrigation_amount_mm"] >= 0
