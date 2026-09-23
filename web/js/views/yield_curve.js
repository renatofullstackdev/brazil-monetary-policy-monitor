import { formatDate, formatPoints, formatRate } from "../format.js";
import { renderYieldCurveChart } from "../charts/yield_curve.js";

const FIELD_BY_KIND = {
  nominal: "nominal",
  real: "real",
  implicit: "implicit_inflation",
};

const LABEL_BY_KIND = {
  nominal: "Nominal",
  real: "Real",
  implicit: "Inflação implícita",
};

function pointsFor(snapshot, kind) {
  if (!snapshot) return [];
  if (kind === "implicit") {
    return snapshot.tenors
      .filter((item) => item.implicit_inflation != null)
      .map((item) => ({ tenor_years: item.tenor_years, value: Number(item.implicit_inflation) }));
  }
  return (snapshot[kind] ?? []).map((item) => ({
    tenor_years: Number(item.tenor_years),
    value: Number(item.yield_percent),
    maturity_date: item.maturity_date,
    instrument_type: item.instrument_type,
  }));
}

function tenorValue(snapshot, kind, tenor) {
  if (!snapshot) return null;
  const field = FIELD_BY_KIND[kind];
  const row = snapshot.tenors.find((item) => Number(item.tenor_years) === tenor);
  return row?.[field] == null ? null : Number(row[field]);
}

function slopeValue(snapshot, kind) {
  if (!snapshot) return null;
  const key = `${kind === "implicit" ? "implicit" : kind}_10y_minus_2y`;
  const value = snapshot.slopes?.[key];
  return value == null ? null : Number(value);
}

function curveMetric(label, value, points = false) {
  const card = document.createElement("div");
  card.className = "curve-metric";
  const title = document.createElement("span");
  title.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value == null ? "—" : points ? formatPoints(value) : formatRate(value);
  card.append(title, strong);
  return card;
}

function nearestSnapshot(snapshots, requestedDate) {
  const eligible = snapshots.filter((snapshot) => snapshot.effective_date <= requestedDate);
  return eligible.at(-1) ?? null;
}

function presetSnapshot(payload, key) {
  const preset = payload.presets?.[key];
  if (!preset) return null;
  if (key === "previous_copom") return preset.status === "available" ? preset.snapshot : null;
  return preset;
}

function updateMetrics(container, snapshot, kind) {
  container.replaceChildren(
    curveMetric(`${LABEL_BY_KIND[kind]} · 2 anos`, tenorValue(snapshot, kind, 2)),
    curveMetric(`${LABEL_BY_KIND[kind]} · 10 anos`, tenorValue(snapshot, kind, 10)),
    curveMetric("Inclinação 10a − 2a", slopeValue(snapshot, kind), true),
  );
}

function updateTable(tbody, current, comparison, kind) {
  const field = FIELD_BY_KIND[kind];
  const currentByTenor = new Map((current?.tenors ?? []).map((item) => [Number(item.tenor_years), item[field]]));
  const comparisonByTenor = new Map((comparison?.tenors ?? []).map((item) => [Number(item.tenor_years), item[field]]));
  const tenors = [2, 3, 5, 7, 10];
  tbody.replaceChildren(...tenors.map((tenor) => {
    const row = document.createElement("tr");
    const term = document.createElement("td");
    term.textContent = `${tenor} anos`;
    const currentCell = document.createElement("td");
    const comparisonCell = document.createElement("td");
    const currentValue = currentByTenor.get(tenor);
    const comparisonValue = comparisonByTenor.get(tenor);
    currentCell.textContent = currentValue == null ? "—" : formatRate(Number(currentValue));
    comparisonCell.textContent = comparisonValue == null ? "—" : formatRate(Number(comparisonValue));
    row.append(term, currentCell, comparisonCell);
    return row;
  }));
}

export function renderYieldCurveUnavailable(message) {
  const panel = document.querySelector("#yield-curve-unavailable");
  const content = document.querySelector("#yield-curve-content");
  panel.hidden = false;
  panel.textContent = message;
  content.hidden = true;
  document.querySelector("#yield-curve-date").textContent = "Dados ainda não carregados";
}

export function renderYieldCurve(payload) {
  if (!payload || payload.status !== "available" || !payload.latest) {
    renderYieldCurveUnavailable("Execute ./scripts/update-yield-curve.sh para carregar a curva do Tesouro Direto.");
    return;
  }

  const unavailable = document.querySelector("#yield-curve-unavailable");
  const content = document.querySelector("#yield-curve-content");
  unavailable.hidden = true;
  content.hidden = false;

  const kindControls = document.querySelector("#curve-kind-controls");
  const compareSelect = document.querySelector("#curve-compare");
  const customDate = document.querySelector("#curve-custom-date");
  const metricContainer = document.querySelector("#yield-curve-metrics");
  const chartContainer = document.querySelector("#yield-curve-chart");
  const legend = document.querySelector("#yield-curve-legend");
  const note = document.querySelector("#yield-curve-note");
  const tableBody = document.querySelector("#yield-curve-table-body");
  const summary = document.querySelector("#yield-curve-summary");
  const dateLabel = document.querySelector("#yield-curve-date");

  const copomOption = compareSelect.querySelector('option[value="previous_copom"]');
  if (payload.presets?.previous_copom?.status !== "available") {
    copomOption.disabled = true;
    copomOption.textContent = "Copom anterior — aguarda eventos";
  }
  if (payload.available_range) {
    customDate.min = payload.available_range.start;
    customDate.max = payload.available_range.end;
  }

  let kind = "nominal";
  let comparisonKey = "none";
  let chartHandle = null;

  const comparisonSnapshot = () => {
    if (comparisonKey === "none") return null;
    if (comparisonKey === "custom") return customDate.value ? nearestSnapshot(payload.snapshots, customDate.value) : null;
    return presetSnapshot(payload, comparisonKey);
  };

  const rerender = () => {
    const current = payload.latest;
    const comparison = comparisonSnapshot();
    const currentPoints = pointsFor(current, kind);
    const comparisonPoints = pointsFor(comparison, kind);
    updateMetrics(metricContainer, current, kind);
    updateTable(tableBody, current, comparison, kind);

    dateLabel.textContent = `Ref. ${formatDate(current.effective_date)}`;
    legend.replaceChildren();
    const currentLegend = document.createElement("span");
    currentLegend.innerHTML = '<span class="legend-line legend-selic" aria-hidden="true"></span>';
    currentLegend.append(`Atual · ${formatDate(current.effective_date)}`);
    legend.append(currentLegend);
    if (comparison) {
      const comparisonLegend = document.createElement("span");
      comparisonLegend.innerHTML = '<span class="legend-line legend-taylor" aria-hidden="true"></span>';
      comparisonLegend.append(`Comparação · ${formatDate(comparison.effective_date)}`);
      legend.append(comparisonLegend);
    }

    if (comparisonKey === "custom" && customDate.value && comparison) {
      note.textContent = comparison.effective_date === customDate.value
        ? "A data personalizada coincide com um dia disponível."
        : `A data escolhida não tinha observação; foi usado o último dia disponível: ${formatDate(comparison.effective_date)}.`;
    } else if (kind === "implicit") {
      note.textContent = "Inflação implícita é um proxy de mercado derivado por Fisher; não equivale a expectativa pura de inflação.";
    } else {
      note.textContent = "Taxas de compra dos títulos ofertados; os pontos são yields até o vencimento, não uma curva zero-cupom.";
    }

    chartHandle?.destroy();
    chartHandle = renderYieldCurveChart(chartContainer, {
      current: currentPoints,
      comparison: comparisonPoints,
      currentLabel: formatDate(current.effective_date),
      comparisonLabel: comparison ? formatDate(comparison.effective_date) : "",
    });
    summary.textContent = `${LABEL_BY_KIND[kind]} em ${formatDate(current.effective_date)}, com ${currentPoints.length} pontos${comparison ? `, comparada a ${formatDate(comparison.effective_date)}` : ""}.`;
  };

  kindControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-curve-kind]");
    if (!button) return;
    kind = button.dataset.curveKind;
    kindControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  compareSelect.addEventListener("change", () => {
    comparisonKey = compareSelect.value;
    customDate.hidden = comparisonKey !== "custom";
    rerender();
  });
  customDate.addEventListener("change", rerender);

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerender, 120);
  });
  rerender();
}
