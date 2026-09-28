import pytest

from src.data_processor import fao56_et0, heat_stress_level, load_raw, process


@pytest.fixture(scope="module")
def daily():
    return process(load_raw())


def test_output_columns(daily):
    for col in ["date", "ET_mm", "water_deficit_mm", "heat_stress_level", "rainfall_mm",
                "temp_min", "temp_max", "humidity_mean", "wbgt_max"]:
        assert col in daily.columns


def test_partial_days_dropped(daily):
    assert daily["coverage"].min() >= 0.8
    assert daily["date"].iloc[-1] == "2026-09-15"  # Sep 16 local has only 3 h of data


def test_deficit_is_et_minus_rain(daily):
    assert ((daily["ET_mm"] - daily["rainfall_mm"]) - daily["water_deficit_mm"]).abs().max() < 0.02


def test_rain_from_cumulative_gauge(daily):
    # Only real rain event in the dataset: 0.4 mm on 31 Aug.
    assert daily.set_index("date")["rainfall_mm"].to_dict()["2026-08-31"] == 0.4
    assert daily["rainfall_mm"].sum() == pytest.approx(0.4)


def test_et0_plausible(daily):
    assert daily["ET_mm"].between(1, 8).all()


def test_et0_rises_with_heat_and_dryness():
    cool_humid = fao56_et0(15, 22, 85, 1.0, 85.2, 250)
    hot_dry = fao56_et0(15, 30, 40, 1.0, 85.2, 250)
    assert hot_dry > cool_humid


@pytest.mark.parametrize("tmax,wbgt,level", [(25, 18, "LOW"), (29, 20, "MODERATE"),
                                             (27, 23, "MODERATE"), (33, 20, "HIGH"), (25, 27, "HIGH")])
def test_heat_stress_level(tmax, wbgt, level):
    assert heat_stress_level(tmax, wbgt) == level
