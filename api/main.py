import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.data_processor import ARCHIVE_CSV, RAW_CSV, ROOT, TZ, fetch_days, load_dotenv, run
from src.irrigation_advisor import IrrigationAdvisor

MAX_DAYS = 30               # API returns at most ~1 month per request
LAG_DAYS = 2                # newest selectable day = today - 2, so it is always complete
LIVE_MIN_DATE = date(2025, 6, 1)  # API has no data before June 2025
WARMUP_DAYS = 10            # soil water history simulated before the shown days

load_dotenv()
CSV_DAYS = run(os.getenv("WEATHER_CSV") or (ARCHIVE_CSV if ARCHIVE_CSV.exists() else RAW_CSV))
ADVISOR = IrrigationAdvisor(
    kc=float(os.getenv("CROP_KC", 1.0)),
    application_rate_mm_h=float(os.getenv("APPLICATION_RATE_MM_H", 3.0)),
    efficiency=float(os.getenv("IRRIGATION_EFFICIENCY", 0.9)),
    rain_buffer_mm=float(os.getenv("RAIN_BUFFER_MM", 10.0)),
)


def live_max_date():
    return datetime.now(ZoneInfo(TZ)).date() - timedelta(days=LAG_DAYS)


def probe_live():
    if not os.getenv("CONDUIT_API_KEY"):
        return False
    try:
        fetch_days(live_max_date(), live_max_date())
        return True
    except Exception as e:
        logging.warning("Conduit API unavailable, using CSV archive: %s", e)
        return False


# ponytail: source picked once at startup; restart to switch after the API key expires.
LIVE = probe_live()

app = FastAPI(title="Smart Irrigation & Crop Heat Stress Advisory",
              description="Daily irrigation and heat stress advice from JKUAT Conduit AWS data.")


def bounds():
    if LIVE:
        return LIVE_MIN_DATE, live_max_date()
    return date.fromisoformat(CSV_DAYS["date"].iloc[0]), date.fromisoformat(CSV_DAYS["date"].iloc[-1])


def check_range(start: date, end: date):
    lo, hi = bounds()
    if not lo <= start <= end <= hi:
        raise HTTPException(422, f"Need {lo} <= start <= end <= {hi}, got {start} to {end}")
    if (end - start).days >= MAX_DAYS:
        raise HTTPException(422, f"Range is {(end - start).days + 1} days; max is {MAX_DAYS}")


def load(start: date, end: date):
    if not LIVE:
        return CSV_DAYS[CSV_DAYS["date"].between(start.isoformat(), end.isoformat())]
    try:
        return fetch_days(start, end)
    except Exception as e:
        raise HTTPException(502, f"Conduit API unavailable: {e}")


def get_days(start: date, end: date):
    check_range(start, end)
    return load(start, end)


def advisories(start: date, end: date):
    check_range(start, end)
    rows = load(max(start - timedelta(days=WARMUP_DAYS), bounds()[0]), end)
    return [a for a in ADVISOR.plan(rows) if a["date"] >= start.isoformat()]


def default_start(n: int, end: date):
    return max(end - timedelta(days=n - 1), bounds()[0])


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "conduit-api" if LIVE else "csv-archive"}


@app.get("/data/range")
def data_range():
    lo, hi = bounds()
    return {"source": "conduit-api" if LIVE else "csv-archive",
            "min_date": lo, "max_date": hi, "max_days": MAX_DAYS}


@app.get("/forecast/7day")
def forecast_7day(end: date | None = None):
    end = end or bounds()[1]
    return advisories(default_start(7, end), end)


@app.get("/advisory/{day}")
def advisory(day: date):
    lo, hi = bounds()
    found = advisories(day, day) if lo <= day <= hi else []
    if not found:
        raise HTTPException(404, f"No data for {day}. Available: {lo} to {hi}")
    return found[0]


@app.get("/data/daily-summary")
def daily_summary(start: date | None = None, end: date | None = None):
    end = end or bounds()[1]
    return get_days(start or default_start(MAX_DAYS, end), end).to_dict("records")


app.mount("/", StaticFiles(directory=Path(ROOT, "frontend"), html=True), name="frontend")
