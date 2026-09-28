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
    """Root-zone water balance (FAO-56 ch. 8), managed to "leave room for rain".

    Each day the soil is topped up to rain_buffer_mm below field capacity rather than to
    full, so the next rain is stored instead of draining away. The buffer must stay below
    readily available water (~18 mm for shallow-rooted vegetables on loam) to avoid stress.
    """

    def __init__(self, kc=1.0, application_rate_mm_h=3.0, efficiency=0.9, min_deficit_mm=1.0,
                 rain_buffer_mm=10.0):
        self.kc = kc                                    # crop coefficient
        self.application_rate_mm_h = application_rate_mm_h
        self.efficiency = efficiency                    # drip ~0.9, sprinkler ~0.75
        self.min_deficit_mm = min_deficit_mm            # below this, not worth irrigating
        self.rain_buffer_mm = rain_buffer_mm            # room left in the soil for rain

    def calculate_irrigation_need(self, date, water_deficit, rainfall, soil_depletion_mm=0.0):
        """soil_depletion_mm: mm below field capacity at the end of the previous day."""
        crop_et = self.kc * (water_deficit + rainfall)
        depletion = max(soil_depletion_mm + crop_et - rainfall, 0.0)  # excess rain drains
        top_up = depletion - self.rain_buffer_mm
        needed = top_up >= self.min_deficit_mm
        amount = top_up / self.efficiency if needed else 0.0
        hours = amount / self.application_rate_mm_h
        weather = f"crop ET {crop_et:.1f} mm, rain {rainfall:.1f} mm"

        if needed:
            end = 6 + hours
            timing = f"06:00-{int(end):02d}:{int(end % 1 * 60):02d} ({hours:.1f} h)"
            reason = f"Soil {depletion:.1f} mm below field capacity ({weather})"
        elif rainfall > 0:
            timing, reason = "None", f"Rain refilled the soil ({weather})"
        else:
            timing, reason = "None", (f"Soil still moist: {depletion:.1f} mm below field capacity, "
                                      f"irrigate beyond {self.rain_buffer_mm:.0f} mm ({weather})")

        return {
            "date": str(date),
            "irrigation_needed": bool(needed),
            "irrigation_amount_mm": round(amount, 1),
            "timing": timing,
            "confidence": None,  # set by caller from data coverage
            "reason": reason,
            "soil_deficit_mm": round(depletion, 1),
            "soil_deficit_end_mm": round(depletion - top_up if needed else depletion, 2),
        }

    def assess_heat_stress(self, date, wbgt_max, temp_range):
        temp_min, temp_max = temp_range
        level = heat_stress_level(temp_max, wbgt_max)
        risk, mitigation = HEAT_ADVICE[level]
        return {"date": str(date), "heat_level": level, "risk_to_crops": risk,
                "mitigation": mitigation, "temp_min": temp_min, "temp_max": temp_max,
                "wbgt_max": wbgt_max}

    def advise(self, row, soil_depletion_mm=0.0) -> dict:
        irrigation = self.calculate_irrigation_need(row["date"], row["water_deficit_mm"],
                                                    row["rainfall_mm"], soil_depletion_mm)
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

    def plan(self, processed_df: pd.DataFrame) -> list[dict]:
        """Advisories for consecutive days, carrying soil water forward (starts at field capacity).

        The state is pinned between 0 and the rain buffer, so runs started >= ~10 days apart
        converge; callers pass that much warm-up history before the days they show.
        """
        depletion, out = 0.0, []
        for row in processed_df.to_dict("records"):
            out.append(self.advise(row, depletion))
            depletion = out[-1]["irrigation"]["soil_deficit_end_mm"]
        return out

    def generate_7day_forecast(self, processed_df: pd.DataFrame) -> list[dict]:
        # ponytail: "forecast" = latest 7 observed days; plug in a weather forecast API
        # (e.g. Open-Meteo) upstream of data_processor for true look-ahead.
        return self.plan(processed_df)[-7:]


if __name__ == "__main__":
    from src.data_processor import run
    for a in IrrigationAdvisor().generate_7day_forecast(run()):
        i, h = a["irrigation"], a["heat_stress"]
        print(f"{a['date']}  irrigate={i['irrigation_needed']!s:5} {i['irrigation_amount_mm']:>4} mm  "
              f"{i['timing']:<22} heat={h['heat_level']:<8} | {i['reason']}")
