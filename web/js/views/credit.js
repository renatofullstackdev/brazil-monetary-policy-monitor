import { filterByRange } from "../charts/history.js";
import { renderCreditChart } from "../charts/credit.js";
import { formatDate, formatPoints, formatRate } from "../format.js";
import { openIndicatorDetails } from "../indicator_details.js";
import { DEFAULT_RANGES } from "../config.js";
import { setRangeControlState } from "../ranges.js";
import { renderPaginatedRows } from "../table.js";

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

function creditInterpretation(series) {
  if (series.key.includes("balance")) {
    return "Variação real em doze meses do saldo de crédito. O indicador ajuda a observar expansão ou contração do estoque após descontar a inflação, sem atribuir o movimento exclusivamente à política monetária.";
  }
  if (series.key.includes("interest_rate")) {
    return "Taxa média das novas operações de crédito. O nível observado também depende de composição, risco, prazos, garantias e condições de oferta.";
  }
  return "Parcela da carteira com atraso superior a 90 dias. É um indicador de qualidade do crédito e pode reagir com defasagem às condições financeiras e de renda.";
}

function latestMetric(series, style) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = `credit-metric ${series.status === "available" ? "" : "unavailable"}`.trim();
  const label = document.createElement("span");
  label.textContent = series.label;
  const value = document.createElement("strong");
  value.textContent = series.status === "available" ? formatRate(Number(series.latest.value)) : "—";
  const ref = document.createElement("small");
  ref.textContent = series.status === "available" ? `Ref. ${formatDate(series.latest.date)} · detalhes` : "Indisponível · detalhes";
  card.append(label, value, ref);
  card.addEventListener("click", () => openIndicatorDetails({
    ...series,
    definition: series.definition ?? null,
    interpretation: creditInterpretation(series),
    caveats: series.caveats ?? [],
    inputs: series.inputs ?? [],
    missing_inputs: series.missing_inputs ?? [],
    series_style: style,
  }));
  return card;
}

function differenceSeries(group) {
  const [free, directed] = group.series;
  const directedByDate = new Map((directed.observations ?? []).map((item) => [item.date, item]));
  const observations = (free.observations ?? []).flatMap((item) => {
    const counterpart = directedByDate.get(item.date);
    if (!counterpart) return [];
    return [{
      date: item.date,
      value: Number(item.value) - Number(counterpart.value),
      available_at: [item.available_at, counterpart.available_at].filter(Boolean).sort().at(-1) ?? null,
    }];
  });
  const latest = observations.at(-1) ?? null;
  return {
    key: `credit_difference_${group.label}`,
    label: "Livre − direcionado",
    title: `Diferença entre ${group.label.toLowerCase()} do crédito livre e direcionado`,
    definition: "Diferença descritiva entre os dois segmentos na mesma data de referência.",
    interpretation: "Valores positivos indicam que o indicador do crédito livre está acima do direcionado; valores negativos indicam o inverso. A diferença não identifica, por si só, a causa do movimento.",
    status: latest ? "available" : "unavailable",
    data_kind: "derived",
    unit: "percentage_points",
    frequency: { key: "monthly", label: "mensal" },
    transformation: {
      key: "free_minus_directed_same_reference_month",
      label: "crédito livre menos crédito direcionado na mesma referência mensal",
    },
    caveats: ["Diferença calculada apenas quando os dois segmentos têm observação na mesma data."],
    inputs: [
      { key: "credit.free", label: "Crédito livre" },
      { key: "credit.directed", label: "Crédito direcionado" },
    ],
    missing_inputs: [],
    latest,
    observations,
    source: null,
    series_style: "series-3",
  };
}

function differenceMetric(group) {
  const indicator = differenceSeries(group);
  const card = document.createElement("button");
  card.type = "button";
  card.className = `credit-metric ${indicator.status === "available" ? "" : "unavailable"}`.trim();
  const label = document.createElement("span");
  label.textContent = indicator.label;
  const value = document.createElement("strong");
  value.textContent = indicator.latest ? formatPoints(Number(indicator.latest.value)) : "—";
  const ref = document.createElement("small");
  ref.textContent = "Diferença descritiva · detalhes";
  card.append(label, value, ref);
  card.addEventListener("click", () => openIndicatorDetails(indicator));
  return card;
}

function tableRows(tbody, primary, secondary, formatter) {
  const secondaryByDate = new Map(secondary.map((item) => [item.date, item]));
  const dates = [...new Set([...primary.map((item) => item.date), ...secondary.map((item) => item.date)])].sort().reverse();
  const rows = dates.map((dateValue) => {
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
  });
  renderPaginatedRows(tbody, rows);
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
  let range = DEFAULT_RANGES.credit;
  setRangeControlState(rangeControls, "data-credit-range", range);
  let chartHandle = null;

  const rerender = () => {
    const group = payload.groups[mode];
    const [free, directed] = group.series;
    const anchor = [free.latest?.date, directed.latest?.date].filter(Boolean).sort().at(-1) ?? null;
    const freeObs = free.status === "available" ? filterByRange(free.observations, range, anchor) : [];
    const directedObs = directed.status === "available" ? filterByRange(directed.observations, range, anchor) : [];
    const formatter = formatterFor(mode);

    metricContainer.replaceChildren(
      latestMetric(free, "series-1"),
      latestMetric(directed, "series-2"),
      differenceMetric(group),
    );

    legend.replaceChildren();
    const freeLegend = document.createElement("span");
    freeLegend.innerHTML = '<span class="legend-line legend-series-1" aria-hidden="true"></span>';
    freeLegend.append("Livre");
    const directedLegend = document.createElement("span");
    directedLegend.innerHTML = '<span class="legend-line legend-series-2" aria-hidden="true"></span>';
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
