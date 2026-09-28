from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health").json()
    assert r["status"] == "ok" and "timestamp" in r and r["source"] == "csv-archive"


def test_range():
    r = client.get("/data/range").json()
    assert r == {"source": "csv-archive", "min_date": "2026-08-28", "max_date": "2026-09-15", "max_days": 30}


def test_forecast_7day():
    days = client.get("/forecast/7day").json()
    assert len(days) == 7 and days[-1]["date"] == "2026-09-15"
    assert {"irrigation", "heat_stress", "weather"} <= days[0].keys()


def test_forecast_7day_with_end():
    days = client.get("/forecast/7day?end=2026-09-05").json()
    assert [d["date"] for d in days][::6] == ["2026-08-30", "2026-09-05"]


def test_advisory_found():
    r = client.get("/advisory/2026-09-05")
    assert r.status_code == 200
    assert r.json()["heat_stress"]["heat_level"] == "MODERATE"


def test_advisory_missing_and_invalid():
    assert client.get("/advisory/2030-01-01").status_code == 404
    assert client.get("/advisory/not-a-date").status_code == 422


def test_daily_summary_default_and_range():
    assert len(client.get("/data/daily-summary").json()) == 19
    rows = client.get("/data/daily-summary?start=2026-09-01&end=2026-09-10").json()
    assert len(rows) == 10 and rows[0]["date"] == "2026-09-01"


def test_daily_summary_rejects_bad_ranges():
    for q in ["start=2026-09-10&end=2026-09-01",   # reversed
              "start=2026-08-01&end=2026-09-10",   # before data / too long
              "start=2026-09-01&end=2026-09-20"]:  # after latest day
        assert client.get(f"/data/daily-summary?{q}").status_code == 422, q


def test_dashboard_served():
    r = client.get("/")
    assert r.status_code == 200 and "Shamba Water" in r.text


def test_advisory_matches_forecast_row():
    # Soil water warm-up makes a day's advice independent of the range it was requested with.
    week = {d["date"]: d for d in client.get("/forecast/7day?end=2026-09-15").json()}
    assert client.get("/advisory/2026-09-12").json() == week["2026-09-12"]
