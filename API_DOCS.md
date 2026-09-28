# API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (Swagger) and `/redoc`.

## `GET /health`
```json
{"status": "ok", "timestamp": "2026-09-28T10:02:39+00:00", "days_loaded": 19}
```

## `GET /forecast/7day`
Advisories for the latest 7 days of data, as a list of **Advisory** objects (below).

## `GET /advisory/{date}`
Advisory for one day. `date` must be `YYYY-MM-DD`.

| Status | When |
|---|---|
| 200 | Advisory returned |
| 404 | No data for that date (message lists the available range) |
| 422 | Malformed date |

**Advisory**
```json
{
  "date": "2026-09-05",
  "irrigation": {
    "date": "2026-09-05",
    "irrigation_needed": true,
    "irrigation_amount_mm": 4.9,
    "timing": "06:00-07:37 (1.6 h)",
    "confidence": 0.99,
    "reason": "Water deficit 4.4 mm (crop ET 4.4 mm, rain 0.0 mm)"
  },
  "heat_stress": {
    "date": "2026-09-05",
    "heat_level": "MODERATE",
    "risk_to_crops": "Mild midday wilting; reduced growth in sensitive crops.",
    "mitigation": "Irrigate before 08:00 so plants start the day hydrated; mulch to keep soil cool.",
    "temp_min": 14.1, "temp_max": 29.8, "wbgt_max": 23.0
  },
  "weather": {
    "ET_mm": 4.4, "water_deficit_mm": 4.4, "rainfall_mm": 0.0,
    "temp_min": 14.1, "temp_max": 29.8, "humidity_mean": 61.67
  }
}
```
- `irrigation_amount_mm`: water to apply, after allowing for system efficiency.
- `confidence`: 0–1, the fraction of the day's expected 96 sensor readings that were present.
- `heat_level`: `LOW` | `MODERATE` | `HIGH`.

## `GET /data/daily-summary`
All processed days (the same data as `Data/processed_weather.csv`):
```json
[{"date": "2026-08-28", "ET_mm": 3.99, "water_deficit_mm": 3.99, "heat_stress_level": "LOW",
  "rainfall_mm": 0.0, "temp_min": 12.6, "temp_max": 27.3, "humidity_mean": 57.94,
  "wbgt_max": 21.1, "heat_index_max": 26.7, "coverage": 0.86}]
```
Units: mm for water, °C for temperature, % for humidity.
