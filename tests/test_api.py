from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and "timestamp" in r.json()


def test_forecast_7day():
    days = client.get("/forecast/7day").json()
    assert len(days) == 7
    assert {"irrigation", "heat_stress", "weather"} <= days[0].keys()


def test_advisory_found():
    r = client.get("/advisory/2026-09-05")
    assert r.status_code == 200
    assert r.json()["heat_stress"]["heat_level"] == "MODERATE"


def test_advisory_missing_and_invalid():
    assert client.get("/advisory/2030-01-01").status_code == 404
    assert client.get("/advisory/not-a-date").status_code == 422


def test_daily_summary():
    rows = client.get("/data/daily-summary").json()
    assert len(rows) == 19 and rows[0]["date"] == "2026-08-28"


def test_dashboard_served():
    r = client.get("/")
    assert r.status_code == 200 and "Shamba Water" in r.text
