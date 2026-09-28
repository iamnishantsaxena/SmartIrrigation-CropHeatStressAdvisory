# Shamba Water: Smart Irrigation & Crop Heat Stress Advisory

Built for **Hack The Weather @ JKUAT**. 

Turns the Conduit climate initiative's JKUAT weather station readings into daily farm advice, for example *"Irrigate 06:00–07:29 (1.5 h), 4.5 mm: water deficit 4.0 mm"*,
plus crop heat stress alerts.

## Quick start

```bash
uv venv && uv pip install -r requirements.txt   # or: python -m venv .venv && pip install -r requirements.txt
.venv/bin/uvicorn api.main:app --reload
```

Open http://localhost:8000 for the dashboard and http://localhost:8000/docs for interactive API docs.

```bash
.venv/bin/python -m src.data_processor      # writes Data/processed_weather.csv
.venv/bin/python -m src.irrigation_advisor  # prints the 7-day schedule
.venv/bin/python -m pytest                  # 24 tests
```

## How it works

```
Data/weatherdata.csv (15-min, UTC)
  → src/data_processor.py   convert to Nairobi time, aggregate to days, drop days <80% coverage,
                            FAO-56 Penman-Monteith ET₀, water deficit, heat stress level
  → src/irrigation_advisor.py  crop water need, irrigation amount/duration, heat mitigation
  → api/main.py             FastAPI; also serves frontend/
  → frontend/               dashboard (vanilla JS + Chart.js)
```

**Evapotranspiration.** Reference ET₀ uses FAO-56 Penman-Monteith with the station's temperature,
humidity, wind and pressure. The station's UV/solar sensor reads 0 throughout, so solar radiation is
estimated from the daily temperature range (FAO-56 eq. 50, kRs = 0.16).

**Rainfall.** `rg1tt` is a cumulative tipping-bucket total that resets daily, so daily rain is the sum
of its positive increments. `rg2tt` is non-zero every day and moves up and down, so it is not
accumulated rain and is ignored. The dataset's only real rain was 0.4 mm on 31 Aug 2026.

**Irrigation.** `crop ET = Kc × ET₀`, `deficit = crop ET − rain`. If the deficit is ≥ 1 mm, apply
`deficit / efficiency`, starting at 06:00 (less evaporation, and leaves dry by evening, which cuts
fungal risk). Duration = amount / application rate. Confidence is the share of the day's expected
sensor readings actually present.

**Heat stress.** HIGH if Tmax ≥ 32 °C or WBGT ≥ 26 °C; MODERATE if Tmax ≥ 28 °C or WBGT ≥ 22 °C.
Thresholds are at the top of `src/data_processor.py`.

## Configuration

Copy `.env.example` and export the variables (for example `set -a; source .env; set +a`), or pass
`--env-file .env` to uvicorn (needs `python-dotenv`).

| Variable | Default | Meaning |
|---|---|---|
| `WEATHER_CSV` | `Data/weatherdata.csv` | Raw sensor export |
| `CROP_KC` | `1.0` | Crop coefficient (maize mid-season ≈ 1.2) |
| `APPLICATION_RATE_MM_H` | `3.0` | Irrigation system output |
| `IRRIGATION_EFFICIENCY` | `0.9` | Drip ≈ 0.9, sprinkler ≈ 0.75 |

## Limitations and next steps

- **"7-day forecast" shows the latest 7 observed days.** For real look-ahead, feed a forecast
  (for example Open-Meteo) through the same `process()`/`IrrigationAdvisor`.
- Each day's deficit is independent; there is no soil-moisture carryover. The next step is an
  FAO-56 soil water balance once soil type and root depth are known.
- Solar radiation is estimated because the UV sensor is dead. A working pyranometer would improve ET₀.

See [API_DOCS.md](API_DOCS.md) for endpoint details.
