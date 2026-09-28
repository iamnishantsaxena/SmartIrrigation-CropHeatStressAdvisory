const MAX_DAYS = 30;
const fmtDate = d => new Date(d + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const addDays = (iso, n) => { const d = new Date(iso + "T00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const maxDate = (a, b) => (a > b ? a : b);
const minDate = (a, b) => (a < b ? a : b);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const $ = id => document.getElementById(id);
const charts = {};
let range;

async function getJSON(url) {
  const r = await fetch(url);
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail || r.status);
  return body;
}

// Keep the two date inputs within the available data and at most MAX_DAYS apart.
function constrainInputs() {
  const start = $("start"), end = $("end");
  start.min = end.value ? maxDate(range.min_date, addDays(end.value, 1 - MAX_DAYS)) : range.min_date;
  start.max = end.value || range.max_date;
  end.min = start.value || range.min_date;
  end.max = start.value ? minDate(range.max_date, addDays(start.value, MAX_DAYS - 1)) : range.max_date;
}

function renderToday(a) {
  const { irrigation: i, heat_stress: h, weather: w } = a;
  $("asof").textContent = `Latest day: ${fmtDate(a.date)}`;
  $("advice").textContent = i.irrigation_needed
    ? `Irrigate ${i.timing} — ${i.irrigation_amount_mm} mm. ${i.reason}.`
    : `No irrigation needed. ${i.reason}.`;
  $("m-irr").textContent = i.irrigation_needed ? `${i.irrigation_amount_mm} mm` : "None";
  $("m-heat").textContent = h.heat_level;
  $("m-heat").className = `lvl-${h.heat_level}`;
  $("m-rain").textContent = `${w.rainfall_mm} mm`;
  $("m-def").textContent = `${i.soil_deficit_mm} mm`;
}

function renderTable(days) {
  $("rows").innerHTML = days.map(({ date, irrigation: i, heat_stress: h, weather: w }) => `
    <tr>
      <td>${fmtDate(date)}</td>
      <td class="${i.irrigation_needed ? "yes" : "no"}">${i.irrigation_needed ? `${i.irrigation_amount_mm} mm` : "—"}</td>
      <td>${i.timing}</td>
      <td>${i.soil_deficit_mm} mm</td>
      <td>${w.rainfall_mm} mm</td>
      <td>${w.temp_min}–${w.temp_max}°</td>
      <td><span class="pill lvl-${h.heat_level}" title="${h.mitigation}">${h.heat_level}</span></td>
    </tr>`).join("");
}

function drawChart(id, type, labels, datasets) {
  charts[id]?.destroy();
  charts[id] = new Chart($(id), {
    type, data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
    },
  });
}

function renderCharts(summary) {
  const labels = summary.map(d => fmtDate(d.date));
  Chart.defaults.color = css("--muted");
  Chart.defaults.borderColor = css("--grid");
  drawChart("temp-chart", "line", labels, [
    { label: "Max", data: summary.map(d => d.temp_max), borderColor: css("--hot"), backgroundColor: css("--hot"), tension: .3 },
    { label: "Min", data: summary.map(d => d.temp_min), borderColor: css("--cool"), backgroundColor: css("--cool"), tension: .3 },
  ]);
  drawChart("water-chart", "bar", labels, [
    { label: "ET₀", data: summary.map(d => d.ET_mm), backgroundColor: css("--accent") },
    { label: "Rainfall", data: summary.map(d => d.rainfall_mm), backgroundColor: css("--cool") },
  ]);
}

async function load() {
  const start = $("start").value, end = $("end").value, button = document.querySelector("#range button");
  button.disabled = true;
  $("advice").textContent = "Loading…";
  try {
    const [forecast, summary] = await Promise.all([
      getJSON(`/forecast/7day?end=${end}`),
      getJSON(`/data/daily-summary?start=${start}&end=${end}`),
    ]);
    if (!forecast.length) throw new Error("no sensor data in this range");
    renderToday(forecast.at(-1));
    renderTable(forecast);
    renderCharts(summary);
  } catch (e) {
    $("advice").textContent = `Could not load data: ${e.message}`;
  } finally {
    button.disabled = false;
  }
}

(async () => {
  try {
    range = await getJSON("/data/range");
  } catch (e) {
    $("advice").textContent = `Could not reach the API (${e.message}). Is the server running?`;
    return;
  }
  const live = range.source === "conduit-api";
  $("source").textContent = live ? "Live · Conduit API" : "Offline archive";
  $("source").classList.toggle("live", live);
  // ?start=YYYY-MM-DD&end=YYYY-MM-DD for shareable views; the server rejects invalid ranges.
  const params = new URLSearchParams(location.search);
  $("end").value = params.get("end") || range.max_date;
  $("start").value = params.get("start") || maxDate(range.min_date, addDays($("end").value, 1 - MAX_DAYS));
  constrainInputs();
  $("start").addEventListener("change", constrainInputs);
  $("end").addEventListener("change", constrainInputs);
  $("range").addEventListener("submit", e => {
    e.preventDefault();
    history.replaceState(null, "", `?start=${$("start").value}&end=${$("end").value}`);
    load();
  });
  load();
})();
