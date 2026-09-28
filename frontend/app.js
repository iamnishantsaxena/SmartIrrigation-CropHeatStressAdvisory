const fmtDate = d => new Date(d + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function renderToday(a) {
  const { irrigation: i, heat_stress: h, weather: w } = a;
  document.getElementById("asof").textContent = `latest data ${fmtDate(a.date)}`;
  document.getElementById("advice").textContent = i.irrigation_needed
    ? `Irrigate ${i.timing} — ${i.irrigation_amount_mm} mm. ${i.reason}.`
    : `No irrigation needed. ${i.reason}.`;
  document.getElementById("m-irr").textContent = i.irrigation_needed ? `${i.irrigation_amount_mm} mm` : "None";
  const heat = document.getElementById("m-heat");
  heat.textContent = h.heat_level;
  heat.className = `lvl-${h.heat_level}`;
  document.getElementById("m-rain").textContent = `${w.rainfall_mm} mm`;
  document.getElementById("m-def").textContent = `${w.water_deficit_mm} mm`;
}

function renderTable(days) {
  document.getElementById("rows").innerHTML = days.map(({ date, irrigation: i, heat_stress: h, weather: w }) => `
    <tr>
      <td>${fmtDate(date)}</td>
      <td class="${i.irrigation_needed ? "yes" : "no"}">${i.irrigation_needed ? `${i.irrigation_amount_mm} mm` : "—"}</td>
      <td>${i.timing}</td>
      <td>${w.water_deficit_mm} mm</td>
      <td>${w.rainfall_mm} mm</td>
      <td>${w.temp_min}–${w.temp_max}°</td>
      <td><span class="pill lvl-${h.heat_level}" title="${h.mitigation}">${h.heat_level}</span></td>
    </tr>`).join("");
}

function renderCharts(summary) {
  const labels = summary.map(d => fmtDate(d.date));
  Chart.defaults.color = css("--muted");
  Chart.defaults.borderColor = css("--grid");
  const opts = { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false } };

  new Chart(document.getElementById("temp-chart"), {
    type: "line",
    data: { labels, datasets: [
      { label: "Max", data: summary.map(d => d.temp_max), borderColor: css("--hot"), backgroundColor: css("--hot"), tension: .3 },
      { label: "Min", data: summary.map(d => d.temp_min), borderColor: css("--cool"), backgroundColor: css("--cool"), tension: .3 },
    ] },
    options: opts,
  });

  new Chart(document.getElementById("water-chart"), {
    type: "bar",
    data: { labels, datasets: [
      { label: "ET₀", data: summary.map(d => d.ET_mm), backgroundColor: css("--accent") },
      { label: "Rainfall", data: summary.map(d => d.rainfall_mm), backgroundColor: css("--cool") },
    ] },
    options: opts,
  });
}

(async () => {
  try {
    const [forecast, summary] = await Promise.all([getJSON("/forecast/7day"), getJSON("/data/daily-summary")]);
    renderToday(forecast.at(-1));
    renderTable(forecast);
    renderCharts(summary);
  } catch (e) {
    document.getElementById("advice").textContent = `Could not load data (${e.message}). Is the API running?`;
  }
})();
