import { filterByRange } from "../charts/history.js";
import { renderCreditChart } from "../charts/credit.js";
import { formatDate, formatPoints, formatRate } from "../format.js";

const MODE_LABELS = {
  real_growth: "Crescimento real (12m)",
  interest_rates: "Taxas médias (a.a.)",
  delinquency: "Inadimplência (>90 dias)",
};

function formatterFor(mode) {
  if (mode === "real_growth") return formatRate;
  if (mode === "interest_rates") return formatRate;
  return formatRate;
}

function latestMetric(series) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = `credit-metric ${series.status === "available" ? "" : "unavailable"}`.trim();
  card.dataset.creditSeries = series.key;
  const label = document.createElement("span");
  label.textContent = series.label;
  const value = document.createElement("strong");
  value.textContent = series.status === "available" ? formatRate(Number(series.latest.value)) : "—";
  const ref = document.createElement("small");
  ref.textContent = series.status === "available" ? `Ref. ${formatDate(series.latest.date)}` : "Indisponível";
  card.append(label, value, ref);
  return card;
}

function differenceMetric(group) {
  const card = document.createElement("div");
  card.className = "credit-metric";
  const label = document.createElement("span");
  label.textContent = "Livre − direcionado";
  const value = document.createElement("strong");
  const [free, directed] = group.series;
  if (free.status === "available" && directed.status === "available") {
    value.textContent = formatPoints(Number(free.latest.value) - Number(directed.latest.value));
  } else {
    value.textContent = "—";
    card.classList.add("unavailable");
  }
  const ref = document.createElement("small");
  ref.textContent = "Diferença descritiva";
  card.append(label, value, ref);
  return card;
}

function showSeriesNote(series, noteContainer) {
  noteContainer.textContent = series.note ?? "";
  if (series.source?.documentation_url) {
    const link = document.createElement("a");
    link.href = series.source.documentation_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = " Fonte oficial.";
    noteContainer.append(link);
  }
}

function tableRows(tbody, primary, secondary, formatter) {
  const secondaryByDate = new Map(secondary.map((item) => [item.date, item]));
  const dates = [...new Set([...primary.map((item) => item.date), ...secondary.map((item) => item.date)])].sort().slice(-12).reverse();
  tbody.replaceChildren(...dates.map((dateValue) => {
    const row = document.createElement("tr");
    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(dateValue);
    const primaryCell = document.createElement("td");
    const secondaryCell = document.createElement("td");
    const primaryItem = primary.find((item) => item.date === dateValue);
    const secondaryItem = secondaryByDate.get(dateValue);
    primaryCell.textContent = primaryItem ? formatter(Number(primaryItem.value)) : "—";
    secondaryCell.textContent = secondaryItem ? formatter(Number(secondaryItem.value)) : "—";
    row.append(dateCell, primaryCell, secondaryCell);
    return row;
  }));
}

export function renderCreditUnavailable(message) {
  document.querySelector("#credit-unavailable").hidden = false;
  document.querySelector("#credit-unavailable").textContent = message;
  document.querySelector("#credit-content").hidden = true;
  document.querySelector("#credit-date").textContent = "Dados ainda não carregados";
}

export function renderCreditTransmission(payload) {
  if (!payload || payload.status !== "available") {
    renderCreditUnavailable("Execute ./scripts/update-credit.sh para carregar os indicadores de crédito.");
    return;
  }
  document.querySelector("#credit-unavailable").hidden = true;
  document.querySelector("#credit-content").hidden = false;
  document.querySelector("#credit-date").textContent = payload.latest_reference ? `Ref. ${formatDate(payload.latest_reference)}` : "Referência indisponível";

  const modeControls = document.querySelector("#credit-mode-controls");
  const rangeControls = document.querySelector("#credit-range-controls");
  const metricContainer = document.querySelector("#credit-metrics");
  const chartContainer = document.querySelector("#credit-chart");
  const legend = document.querySelector("#credit-legend");
  const note = document.querySelector("#credit-note");
  const tbody = document.querySelector("#credit-table-body");
  const summary = document.querySelector("#credit-summary");
  let mode = "real_growth";
  let range = "5";
  let chartHandle = null;

  const rerender = () => {
    const group = payload.groups[mode];
    const [free, directed] = group.series;
    const anchor = [free.latest?.date, directed.latest?.date].filter(Boolean).sort().at(-1) ?? null;
    const freeObs = free.status === "available" ? filterByRange(free.observations, range, anchor) : [];
    const directedObs = directed.status === "available" ? filterByRange(directed.observations, range, anchor) : [];
    const formatter = formatterFor(mode);

    metricContainer.replaceChildren(latestMetric(free), latestMetric(directed), differenceMetric(group));
    metricContainer.querySelectorAll("button[data-credit-series]").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = group.series.find((item) => item.key === button.dataset.creditSeries);
        showSeriesNote(selected, note);
      });
    });

    legend.replaceChildren();
    const freeLegend = document.createElement("span");
    freeLegend.innerHTML = '<span class="legend-line legend-selic" aria-hidden="true"></span>';
    freeLegend.append("Livre");
    const directedLegend = document.createElement("span");
    directedLegend.innerHTML = '<span class="legend-line legend-taylor" aria-hidden="true"></span>';
    directedLegend.append("Direcionado");
    legend.append(freeLegend, directedLegend);

    note.textContent = mode === "real_growth"
      ? "Crescimento real em 12 meses: saldo nominal deflacionado pelo IPCA composto no mesmo intervalo."
      : mode === "interest_rates"
        ? "Taxas médias das novas operações; mudanças de composição e risco também afetam o nível observado."
        : "Inadimplência: parcela da carteira com atraso superior a 90 dias.";

    chartHandle?.destroy();
    chartHandle = renderCreditChart(chartContainer, {
      primary: freeObs,
      secondary: directedObs,
      primaryLabel: "Livre",
      secondaryLabel: "Direcionado",
      valueFormatter: formatter,
    });
    tableRows(tbody, freeObs, directedObs, formatter);
    const latestText = free.latest && directed.latest
      ? `${MODE_LABELS[mode]}: livre ${formatter(Number(free.latest.value))}; direcionado ${formatter(Number(directed.latest.value))}.`
      : `${MODE_LABELS[mode]} com disponibilidade parcial.`;
    summary.textContent = latestText;
  };

  modeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-credit-mode]");
    if (!button) return;
    mode = button.dataset.creditMode;
    modeControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  rangeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-credit-range]");
    if (!button) return;
    range = button.dataset.creditRange;
    rangeControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerender, 120);
  });
  rerender();
}
