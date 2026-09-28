"""Daily irrigation + heat stress advice from processed weather (see data_processor)."""
import pandas as pd

from src.data_processor import heat_stress_level

HEAT_ADVICE = {
    "HIGH": ("Pollination failure and wilting likely in maize/beans/vegetables.",
             "Irrigate early morning AND light evening top-up; mulch; shade nets for "
             "seedlings; avoid field work 11:00-15:00."),
    "MODERATE": ("Mild midday wilting; reduced growth in sensitive crops.",
                 "Irrigate before 08:00 so plants start the day hydrated; mulch to "
                 "keep soil cool."),
    "LOW": ("Minimal heat risk.", "No action needed."),
}


class IrrigationAdvisor:
    # ponytail: day-by-day deficit only, no soil water carryover; add a soil bucket
    # model (FAO-56 ch. 8) when soil type / root depth are known.
    def __init__(self, kc=1.0, application_rate_mm_h=3.0, efficiency=0.9, min_deficit_mm=1.0):
        self.kc = kc                                    # crop coefficient
        self.application_rate_mm_h = application_rate_mm_h
        self.efficiency = efficiency                    # drip ~0.9, sprinkler ~0.75
        self.min_deficit_mm = min_deficit_mm            # below this, not worth irrigating

    def calculate_irrigation_need(self, date, water_deficit, rainfall):
        et0 = water_deficit + rainfall
        crop_deficit = self.kc * et0 - rainfall
        needed = crop_deficit >= self.min_deficit_mm
        amount = crop_deficit / self.efficiency if needed else 0.0
        hours = amount / self.application_rate_mm_h

        if needed:
            end = 6 + hours
            timing = f"06:00-{int(end):02d}:{int(end % 1 * 60):02d} ({hours:.1f} h)"
            reason = f"Water deficit {crop_deficit:.1f} mm (crop ET {self.kc * et0:.1f} mm, rain {rainfall:.1f} mm)"
        elif rainfall > 0:
            timing, reason = "None", f"Rainfall {rainfall:.1f} mm covers crop water need"
        else:
            timing, reason = "None", f"Deficit {crop_deficit:.1f} mm is below {self.min_deficit_mm} mm threshold"

        return {
            "date": str(date),
            "irrigation_needed": bool(needed),
            "irrigation_amount_mm": round(amount, 1),
            "timing": timing,
            "confidence": None,  # set by caller from data coverage
            "reason": reason,
        }

    def assess_heat_stress(self, date, wbgt_max, temp_range):
        temp_min, temp_max = temp_range
        level = heat_stress_level(temp_max, wbgt_max)
        risk, mitigation = HEAT_ADVICE[level]
        return {"date": str(date), "heat_level": level, "risk_to_crops": risk,
                "mitigation": mitigation, "temp_min": temp_min, "temp_max": temp_max,
                "wbgt_max": wbgt_max}

    def advise(self, row) -> dict:
        irrigation = self.calculate_irrigation_need(row["date"], row["water_deficit_mm"], row["rainfall_mm"])
        # Confidence = share of the day's expected sensor readings actually present.
        irrigation["confidence"] = round(float(row.get("coverage", 1.0)), 2)
        return {
            "date": str(row["date"]),
            "irrigation": irrigation,
            "heat_stress": self.assess_heat_stress(row["date"], row["wbgt_max"],
                                                   (row["temp_min"], row["temp_max"])),
            "weather": {k: row[k] for k in ("ET_mm", "water_deficit_mm", "rainfall_mm",
                                            "temp_min", "temp_max", "humidity_mean")},
        }

    def generate_7day_forecast(self, processed_df: pd.DataFrame) -> list[dict]:
        # ponytail: "forecast" = latest 7 observed days; plug in a weather forecast API
        # (e.g. Open-Meteo) upstream of data_processor for true look-ahead.
        return [self.advise(row) for row in processed_df.tail(7).to_dict("records")]


if __name__ == "__main__":
    from src.data_processor import run
    for a in IrrigationAdvisor().generate_7day_forecast(run()):
        i, h = a["irrigation"], a["heat_stress"]
        print(f"{a['date']}  irrigate={i['irrigation_needed']!s:5} {i['irrigation_amount_mm']:>4} mm  "
              f"{i['timing']:<22} heat={h['heat_level']:<8} | {i['reason']}")
