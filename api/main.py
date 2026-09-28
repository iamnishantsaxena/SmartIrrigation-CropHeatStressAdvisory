import os
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.data_processor import RAW_CSV, ROOT, run
from src.irrigation_advisor import IrrigationAdvisor

# ponytail: processed once at startup; re-run on a schedule when data is streamed live.
DAILY = run(os.getenv("WEATHER_CSV", RAW_CSV))
ADVISOR = IrrigationAdvisor(
    kc=float(os.getenv("CROP_KC", 1.0)),
    application_rate_mm_h=float(os.getenv("APPLICATION_RATE_MM_H", 3.0)),
    efficiency=float(os.getenv("IRRIGATION_EFFICIENCY", 0.9)),
)

app = FastAPI(title="Smart Irrigation & Crop Heat Stress Advisory",
              description="Daily irrigation and heat stress advice from JKUAT Conduit AWS data.")


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(),
            "days_loaded": len(DAILY)}


@app.get("/forecast/7day")
def forecast_7day():
    return ADVISOR.generate_7day_forecast(DAILY)


@app.get("/advisory/{day}")
def advisory(day: date):
    rows = DAILY[DAILY["date"] == day.isoformat()]
    if rows.empty:
        raise HTTPException(404, f"No data for {day}. Available: {DAILY['date'].iloc[0]} to {DAILY['date'].iloc[-1]}")
    return ADVISOR.advise(rows.iloc[0].to_dict())


@app.get("/data/daily-summary")
def daily_summary():
    return DAILY.to_dict("records")


app.mount("/", StaticFiles(directory=Path(ROOT, "frontend"), html=True), name="frontend")
