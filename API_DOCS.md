# API Reference

Base URL: `http://localhost:8000`. Interactive docs: `/docs` (Swagger) and `/redoc`.

Data comes from the live Conduit API when a key is configured, otherwise from the bundled CSV.
All dates are local (Africa/Nairobi) days.

## `GET /health`
```json
{"status": "ok", "timestamp": "2026-09-28T10:02:39+00:00", "source": "conduit-api"}
```
`source` is `conduit-api` or `csv-archive`.

## `GET /data/range`
The dates that can be selected. Use this to set limits on a date picker.
```json
{"source": "conduit-api", "min_date": "2026-01-01", "max_date": "2026-09-26", "max_days": 30}
```
In live mode `max_date` is today − 2. In CSV mode the range is the CSV's extent.

## `GET /forecast/7day?end=YYYY-MM-DD`
Advisories for the 7 days ending on `end` (default `max_date`), as a list of **Advisory** objects (below).

## `GET /advisory/{date}`
Advisory for one day. `date` must be `YYYY-MM-DD`.

| Status | When |
|---|---|
| 200 | Advisory returned |
| 404 | No data for that date (message lists the available range) |
| 422 | Malformed date |
| 502 | Conduit API request failed |

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
    "reason": "Soil 14.4 mm below field capacity (crop ET 4.4 mm, rain 0.0 mm)",
    "soil_deficit_mm": 14.4,
    "soil_deficit_end_mm": 10.0
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
- `soil_deficit_mm`: mm the root zone is below field capacity before irrigation; `soil_deficit_end_mm` is after.
  Advisories simulate soil water from 10 days before the requested date, so a day's advice is the same
  whichever endpoint or range it comes from.
- `weather.water_deficit_mm`: that day alone, ET₀ − rain (no soil storage).
- `heat_level`: `LOW` | `MODERATE` | `HIGH`.

## `GET /data/daily-summary?start=YYYY-MM-DD&end=YYYY-MM-DD`
Processed daily weather for `start` to `end`, inclusive. With no parameters it returns the last 30 days.

| Status | When |
|---|---|
| 200 | List of days (may be empty if the sensor was offline) |
| 422 | Range is reversed, longer than 30 days, or outside `/data/range` |
| 502 | Conduit API request failed |

```json
[{"date": "2026-08-28", "ET_mm": 3.99, "water_deficit_mm": 3.99, "heat_stress_level": "LOW",
  "rainfall_mm": 0.0, "temp_min": 12.6, "temp_max": 27.3, "humidity_mean": 57.94,
  "wbgt_max": 21.1, "heat_index_max": 26.7, "coverage": 0.86}]
```
Units: mm for water, °C for temperature, % for humidity.
