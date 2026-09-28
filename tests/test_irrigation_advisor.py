import pandas as pd

from src.irrigation_advisor import IrrigationAdvisor


def test_deficit_triggers_irrigation():
    r = IrrigationAdvisor(efficiency=1.0, application_rate_mm_h=3.0).calculate_irrigation_need("2026-09-05", 4.5, 0)
    assert r["irrigation_needed"] and r["irrigation_amount_mm"] == 4.5
    assert r["timing"] == "06:00-07:30 (1.5 h)"


def test_efficiency_increases_amount():
    r = IrrigationAdvisor(efficiency=0.9).calculate_irrigation_need("d", 4.5, 0)
    assert r["irrigation_amount_mm"] == 5.0


def test_rain_covers_need():
    r = IrrigationAdvisor().calculate_irrigation_need("d", -2.0, 5.0)
    assert not r["irrigation_needed"] and r["irrigation_amount_mm"] == 0
    assert "Rainfall" in r["reason"]


def test_small_deficit_skipped():
    assert not IrrigationAdvisor(min_deficit_mm=1.0).calculate_irrigation_need("d", 0.5, 0)["irrigation_needed"]


def test_crop_coefficient_scales_et_not_rain():
    # ET0 = 3 + 1 = 4; crop ET = 1.2 * 4 = 4.8; deficit = 4.8 - 1 = 3.8
    r = IrrigationAdvisor(kc=1.2, efficiency=1.0).calculate_irrigation_need("d", 3.0, 1.0)
    assert r["irrigation_amount_mm"] == 3.8


def test_heat_stress():
    h = IrrigationAdvisor().assess_heat_stress("d", 26.5, (18, 31))
    assert h["heat_level"] == "HIGH" and h["mitigation"]


def test_7day_forecast_uses_latest_week():
    df = pd.DataFrame({"date": [f"2026-09-{d:02d}" for d in range(1, 11)], "ET_mm": 4.0,
                       "water_deficit_mm": 4.0, "rainfall_mm": 0.0, "temp_min": 14.0,
                       "temp_max": 27.0, "humidity_mean": 60.0, "wbgt_max": 21.0, "coverage": 0.99})
    out = IrrigationAdvisor().generate_7day_forecast(df)
    assert [a["date"] for a in out] == [f"2026-09-{d:02d}" for d in range(4, 11)]
    assert out[0]["irrigation"]["confidence"] == 0.99
