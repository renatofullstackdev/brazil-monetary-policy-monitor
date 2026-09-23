import { renderFiscalChart } from "../charts/fiscal.js";
import { formatDate, formatRate } from "../format.js";

const LABELS = {
  "br.fiscal.primary_result_12m_gdp": "Primário",
  "br.fiscal.nominal_interest_12m_gdp": "Juros nominais",
  "br.fiscal.nominal_result_12m_gdp": "Nominal",
  "br.fiscal.dbgg_gdp": "DBGG",
};

function formatPercentOfGdp(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}% PIB`; }
function formatBillions(value) { return `R$ ${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} bi`; }
function formatYears(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} anos`; }
function formatMonths(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} meses`; }

function metricCard(label, value, detail = "") {
  const article = document.createElement("article");
  article.className = "metric-card";
  const name = document.createElement("p"); name.className = "metric-label"; name.textContent = label;
  const number = document.createElement("p"); number.className = "metric-value"; number.textContent = value;
  article.append(name, number);
  if (detail) { const note = document.createElement("p"); note.className = "metric-meta"; note.textContent = detail; article.append(note); }
  return article;
}

function withinRange(observations, years) {
  if (years === "all" || !observations.length) return observations;
  const latest = new Date(`${observations.at(-1).date}T00:00:00Z`);
  const cutoff = new Date(latest); cutoff.setUTCFullYear(cutoff.getUTCFullYear() - Number(years));
  return observations.filter((item) => new Date(`${item.date}T00:00:00Z`) >= cutoff);
}

function renderProfile(payload) {
  const container = document.querySelector("#fiscal-profile-metrics");
  const composition = document.querySelector("#fiscal-composition");
  const status = document.querySelector("#fiscal-profile-date");
  container.replaceChildren(); composition.replaceChildren();
  const profile = payload.dpf_profile;
  if (!profile || profile.status !== "available") { status.textContent = "Perfil DPF indisponível"; return; }
  status.textContent = `RMD ${profile.reference_period}`;
  const m = profile.metrics;
  const items = [
    ["Estoque DPF", m["br.dpf.stock_brl_billions"], formatBillions],
    ["Vence em 12 meses", m["br.dpf.maturing_12m_share"], formatRate],
    ["Prazo médio", m["br.dpf.average_term_years"], formatYears],
    ["Custo médio 12m", m["br.dpf.average_cost_12m"], formatRate],
    ["Reserva de liquidez", m["br.dpf.liquidity_reserve_brl_billions"], formatBillions],
    ["Índice de liquidez", m["br.dpf.liquidity_index_months"], formatMonths],
  ];
  for (const [label, item, formatter] of items) container.append(metricCard(label, item ? formatter(item.value) : "—", item?.source_reference || ""));
  for (const item of profile.composition) {
    const row = document.createElement("div"); row.className = "fiscal-composition-row";
    const head = document.createElement("div"); head.className = "fiscal-composition-head";
    const label = document.createElement("span"); label.textContent = item.label;
    const value = document.createElement("strong"); value.textContent = item.value == null ? "—" : formatRate(item.value);
    head.append(label, value);
    const track = document.createElement("div"); track.className = "fiscal-composition-track";
    const fill = document.createElement("div"); fill.className = "fiscal-composition-fill"; fill.style.width = `${Math.max(0, Math.min(100, Number(item.value || 0)))}%`;
    track.append(fill); row.append(head, track); composition.append(row);
  }
}

export function renderFiscalUnavailable(message) {
  const panel = document.querySelector("#fiscal-unavailable");
  panel.hidden = false; panel.textContent = message;
  document.querySelector("#fiscal-content").hidden = true;
}

export function renderFiscal(payload) {
  document.querySelector("#fiscal-unavailable").hidden = true;
  document.querySelector("#fiscal-content").hidden = false;
  const dateLabel = document.querySelector("#fiscal-date");
  const metrics = document.querySelector("#fiscal-metrics");
  const legend = document.querySelector("#fiscal-legend");
  const note = document.querySelector("#fiscal-note");
  const chart = document.querySelector("#fiscal-chart");
  const tbody = document.querySelector("#fiscal-table-body");
  const modeControls = document.querySelector("#fiscal-mode-controls");
  const rangeControls = document.querySelector("#fiscal-range-controls");
  let mode = "flows";
  let range = "5";
  let handle = null;

  renderProfile(payload);
  const latestDates = [...payload.flows, payload.debt].map((s) => s.latest?.date).filter(Boolean).sort();
  dateLabel.textContent = latestDates.length ? `Último dado: ${formatDate(latestDates.at(-1))}` : "Sem dados SGS";

  const rerender = () => {
    const selected = mode === "flows" ? payload.flows : [payload.debt];
    const chartSeries = selected.map((series) => ({
      label: LABELS[series.key] || series.title,
      observations: withinRange(series.observations || [], range),
    }));
    metrics.replaceChildren();
    for (const series of selected) {
      const latest = series.latest;
      metrics.append(metricCard(LABELS[series.key] || series.title, latest ? formatPercentOfGdp(latest.value) : "—", latest ? formatDate(latest.date) : "Sem observação"));
    }
    legend.replaceChildren();
    selected.forEach((series, index) => {
      const item = document.createElement("span");
      item.innerHTML = `<span class="legend-line fiscal-legend-${index + 1}" aria-hidden="true"></span>`;
      item.append(LABELS[series.key] || series.title); legend.append(item);
    });
    note.textContent = mode === "flows"
      ? payload.sign_convention.note
      : "DBGG é estoque do Governo Geral em % do PIB; não deve ser confundida com a DPF do Tesouro, que tem cobertura institucional distinta.";
    handle?.destroy();
    handle = renderFiscalChart(chart, { series: chartSeries, valueFormatter: formatPercentOfGdp });

    const maps = chartSeries.map((series) => new Map(series.observations.map((o) => [o.date, o])));
    const dates = [...new Set(chartSeries.flatMap((s) => s.observations.map((o) => o.date)))].sort().slice(-12).reverse();
    tbody.replaceChildren();
    for (const date of dates) {
      const tr = document.createElement("tr");
      const d = document.createElement("td"); d.textContent = formatDate(date); tr.append(d);
      for (const map of maps) { const td = document.createElement("td"); const item = map.get(date); td.textContent = item ? formatPercentOfGdp(item.value) : "—"; tr.append(td); }
      while (tr.children.length < 4) { const td = document.createElement("td"); td.textContent = "—"; tr.append(td); }
      tbody.append(tr);
    }
    document.querySelector("#fiscal-table-head-1").textContent = mode === "flows" ? "Primário" : "DBGG";
    document.querySelector("#fiscal-table-head-2").textContent = mode === "flows" ? "Juros" : "—";
    document.querySelector("#fiscal-table-head-3").textContent = mode === "flows" ? "Nominal" : "—";
  };

  modeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-fiscal-mode]"); if (!button) return;
    mode = button.dataset.fiscalMode;
    modeControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  rangeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-fiscal-range]"); if (!button) return;
    range = button.dataset.fiscalRange;
    rangeControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  let timer = null;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(rerender, 120); });
  rerender();
}
