import { filterByRange } from "../charts/history.js";
import { renderExternalChart } from "../charts/external.js";
import { formatDate, formatUnitValue } from "../format.js";
import { openIndicatorDetails } from "../indicator_details.js";
import { DEFAULT_RANGES } from "../config.js";
import { setRangeControlState } from "../ranges.js";
import { renderPaginatedRows } from "../table.js";

const MODE_NOTES = {
  fx_nominal: "A cotação nominal é um preço relativo. O painel descreve seu nível e variações, mas não atribui movimentos cambiais a uma única causa nem estima valor justo.",
  fx_real: "O câmbio real efetivo combina câmbio nominal, preços relativos e pesos comerciais. É um índice de competitividade/preço relativo, não uma estimativa de câmbio de equilíbrio.",
  external_balance: "Transações correntes e IDP são apresentados na mesma escala (% do PIB). A razão IDP/déficit é apenas descritiva e não constitui identidade de financiamento nem inferência causal.",
  portfolio: "O fluxo de carteira segue a convenção estatística do balanço de pagamentos e representa passivos de investimento em carteira, não todo o fluxo financeiro de estrangeiros.",
  reserves: "Reservas internacionais são estoque de ativos externos no conceito liquidez. Não devem ser interpretadas como fluxo mensal nem como meta implícita de câmbio.",
};

function metricCard(indicator, style) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = `credit-metric external-metric ${indicator.status === "available" ? "" : "unavailable"}`.trim();
  const label = document.createElement("span");
  label.textContent = indicator.label;
  const value = document.createElement("strong");
  value.textContent = indicator.latest
    ? formatUnitValue(Number(indicator.latest.value), indicator.unit)
    : "—";
  const ref = document.createElement("small");
  ref.textContent = indicator.latest
    ? `Ref. ${formatDate(indicator.latest.date)} · detalhes`
    : "Indisponível · detalhes";
  card.append(label, value, ref);
  card.addEventListener("click", () => openIndicatorDetails({ ...indicator, definition: indicator.definition ?? null, caveats: indicator.caveats ?? [], inputs: indicator.inputs ?? [], missing_inputs: indicator.missing_inputs ?? [], series_style: style }));
  return card;
}

function legendItem(series, index) {
  const item = document.createElement("span");
  const line = document.createElement("span");
  line.className = `legend-line legend-series-${Math.min(index + 1, 5)}`;
  line.setAttribute("aria-hidden", "true");
  item.append(line, series.label);
  return item;
}

function formatExternalAxisValue(value, unit) {
  if (!Number.isFinite(value)) return "—";
  if (unit === "usd_millions") {
    const absolute = Math.abs(value);
    if (absolute >= 1000) return `US$ ${(value / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} bi`;
    return `US$ ${value.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mi`;
  }
  if (unit === "percent_of_gdp") {
    return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% PIB`;
  }
  if (["percent", "percent_change"].includes(unit)) {
    return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  }
  if (unit === "brl_per_usd") {
    return value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (unit === "index") {
    return value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  }
  return formatUnitValue(value, unit);
}

function observationsFor(series, range, anchor) {
  if (series.status !== "available") return [];
  return filterByRange(series.observations ?? [], range, anchor);
}

function tableRows(tbody, headerOne, headerTwo, series, formatter) {
  const [first, second] = series;
  headerOne.textContent = first?.label ?? "Série";
  headerTwo.textContent = second?.label ?? "—";
  headerTwo.hidden = !second;

  const firstByDate = new Map((first?.observations ?? []).map((item) => [item.date, item]));
  const secondByDate = new Map((second?.observations ?? []).map((item) => [item.date, item]));
  const dates = [...new Set([...firstByDate.keys(), ...secondByDate.keys()])]
    .sort()
    .reverse();
  const rows = dates.map((dateValue) => {
    const row = document.createElement("tr");
    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(dateValue);
    const firstCell = document.createElement("td");
    const secondCell = document.createElement("td");
    const firstItem = firstByDate.get(dateValue);
    const secondItem = secondByDate.get(dateValue);
    firstCell.textContent = firstItem ? formatter(Number(firstItem.value)) : "—";
    secondCell.textContent = secondItem ? formatter(Number(secondItem.value)) : "—";
    secondCell.hidden = !second;
    row.append(dateCell, firstCell, secondCell);
    return row;
  });
  renderPaginatedRows(tbody, rows);
}

export function renderExternalUnavailable(message) {
  document.querySelector("#external-unavailable").hidden = false;
  document.querySelector("#external-unavailable").textContent = message;
  document.querySelector("#external-content").hidden = true;
  document.querySelector("#external-date").textContent = "Dados ainda não carregados";
}

export function renderExternal(payload) {
  if (!payload || payload.status !== "available") {
    renderExternalUnavailable("Execute ./scripts/update-external.sh para carregar câmbio e setor externo.");
    return;
  }

  document.querySelector("#external-unavailable").hidden = true;
  document.querySelector("#external-content").hidden = false;
  document.querySelector("#external-date").textContent = payload.latest_reference
    ? `Última referência ${formatDate(payload.latest_reference)}`
    : "Referência indisponível";

  const modeControls = document.querySelector("#external-mode-controls");
  const rangeControls = document.querySelector("#external-range-controls");
  const metrics = document.querySelector("#external-metrics");
  const legend = document.querySelector("#external-legend");
  const note = document.querySelector("#external-note");
  const chart = document.querySelector("#external-chart");
  const summary = document.querySelector("#external-summary");
  const tbody = document.querySelector("#external-table-body");
  const tableHeadOne = document.querySelector("#external-table-head-1");
  const tableHeadTwo = document.querySelector("#external-table-head-2");
  let mode = "fx_nominal";
  let range = DEFAULT_RANGES.external;
  setRangeControlState(rangeControls, "data-external-range", range);
  let chartHandle = null;

  const rerender = () => {
    const group = payload.groups[mode];
    if (!group) return;
    const anchor = group.chart_series
      .map((series) => series.latest?.date)
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;
    const displayedSeries = group.chart_series.map((series) => ({
      ...series,
      observations: observationsFor(series, range, anchor),
    }));
    const chartUnit = group.chart_series[0]?.unit ?? group.metrics[0]?.unit;
    const formatter = (value) => formatUnitValue(value, chartUnit);

    metrics.replaceChildren(...group.metrics.map((indicator, index) => metricCard(
      indicator,
      `series-${Math.min(index + 1, 5)}`,
    )));
    legend.replaceChildren(...group.chart_series.map(legendItem));
    note.textContent = MODE_NOTES[mode] ?? "";

    chartHandle?.destroy();
    chartHandle = renderExternalChart(chart, {
      series: displayedSeries,
      valueFormatter: formatter,
      axisValueFormatter: (value) => formatExternalAxisValue(value, chartUnit),
      geometry: mode === "portfolio" ? "bar" : "line",
    });
    tableRows(tbody, tableHeadOne, tableHeadTwo, displayedSeries, formatter);

    const available = group.metrics.filter((indicator) => indicator.latest);
    summary.textContent = available.length
      ? `${group.label}. ${available.map((indicator) => `${indicator.label}: ${formatUnitValue(Number(indicator.latest.value), indicator.unit)}`).join("; ")}.`
      : `${group.label} sem observações disponíveis.`;
  };

  modeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-external-mode]");
    if (!button) return;
    mode = button.dataset.externalMode;
    modeControls.querySelectorAll("button").forEach((candidate) => {
      candidate.setAttribute("aria-pressed", String(candidate === button));
    });
    rerender();
  });
  rangeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-external-range]");
    if (!button) return;
    range = button.dataset.externalRange;
    rangeControls.querySelectorAll("button").forEach((candidate) => {
      candidate.setAttribute("aria-pressed", String(candidate === button));
    });
    rerender();
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerender, 120);
  });

  rerender();
}
