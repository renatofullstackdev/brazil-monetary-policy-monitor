import { renderExplorerScatterChart, renderExplorerTimeChart } from "../charts/explorer.js";

function monthKey(dateValue) {
  const match = /^(\d{4})-(\d{2})/.exec(String(dateValue ?? ""));
  return match ? `${match[1]}-${match[2]}` : null;
}

function addMonths(month, amount) {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return month;
  const total = Number(match[1]) * 12 + Number(match[2]) - 1 + Number(amount);
  const year = Math.floor(total / 12);
  const monthNumber = total % 12 + 1;
  return `${year}-${String(monthNumber).padStart(2, "0")}`;
}

export function monthlySeries(observations = []) {
  const byMonth = new Map();
  for (const item of observations) {
    const month = monthKey(item.date);
    const value = Number(item.value);
    if (!month || !Number.isFinite(value)) continue;
    const current = byMonth.get(month);
    if (!current || String(item.date) >= String(current.sourceDate)) byMonth.set(month, { date: month, value, sourceDate: item.date });
  }
  return [...byMonth.values()].sort((a, b) => a.date.localeCompare(b.date)).map(({ date, value }) => ({ date, value }));
}

export function transformSeries(observations, transformation) {
  const monthly = monthlySeries(observations);
  if (transformation === "level") return monthly;
  if (transformation === "index100") {
    const base = monthly.find((item) => item.value !== 0);
    if (!base) return [];
    return monthly.map((item) => ({ date: item.date, value: item.value / base.value * 100 }));
  }
  if (transformation === "change12m") {
    const byMonth = new Map(monthly.map((item) => [item.date, item.value]));
    return monthly.flatMap((item) => {
      const previous = byMonth.get(addMonths(item.date, -12));
      return previous == null ? [] : [{ date: item.date, value: item.value - previous }];
    });
  }
  return monthly;
}

export function lagSeries(observations, months) {
  return observations.map((item) => ({ ...item, date: addMonths(item.date, Number(months)) }));
}

function filterRange(seriesList, range) {
  if (range === "all") return seriesList;
  const dates = seriesList.flatMap((series) => series.map((item) => item.date)).sort();
  const anchor = dates.at(-1);
  if (!anchor) return seriesList;
  const cutoff = addMonths(anchor, -Number(range) * 12);
  return seriesList.map((series) => series.filter((item) => item.date >= cutoff));
}


export function rebaseToCommonStart(a, b) {
  const aByDate = new Map(a.map((item) => [item.date, Number(item.value)]));
  const bByDate = new Map(b.map((item) => [item.date, Number(item.value)]));
  const commonDate = [...aByDate.keys()].filter((date) => bByDate.has(date)).sort().at(0);
  if (!commonDate) return [[], []];
  const baseA = aByDate.get(commonDate);
  const baseB = bByDate.get(commonDate);
  if (!Number.isFinite(baseA) || !Number.isFinite(baseB) || baseA === 0 || baseB === 0) return [[], []];
  const convert = (series, base) => series
    .filter((item) => item.date >= commonDate)
    .map((item) => ({ date: item.date, value: Number(item.value) / base * 100 }));
  return [convert(a, baseA), convert(b, baseB)];
}

export function pairSeries(a, b) {
  const bByDate = new Map(b.map((item) => [item.date, item.value]));
  return a.flatMap((item) => bByDate.has(item.date) ? [{ date: item.date, a: item.value, b: bByDate.get(item.date) }] : []);
}

function dedupeCandidates(candidates) {
  const map = new Map();
  for (const candidate of candidates) {
    if (!candidate?.key || !Array.isArray(candidate.observations) || candidate.observations.length < 2) continue;
    if (!map.has(candidate.key)) map.set(candidate.key, candidate);
  }
  return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
}

function yieldCandidates(payload) {
  if (!payload?.snapshots?.length) return [];
  const specs = [
    ["yield.nominal.2y", "Juros Brasil ≈2 anos", "nominal_rate", 2],
    ["yield.nominal.10y", "Juros Brasil ≈10 anos", "nominal_rate", 10],
    ["yield.real.10y", "Juro real Brasil ≈10 anos", "real_rate", 10],
    ["yield.implicit.10y", "Inflação implícita Brasil ≈10 anos", "implicit_inflation", 10],
  ];
  return specs.map(([key, label, field, tenor]) => ({
    key, label, unit: "percent_per_year",
    observations: payload.snapshots.flatMap((snapshot) => {
      const point = (snapshot.tenors ?? []).find((item) => Number(item.tenor_years) === tenor);
      const value = point?.[field];
      return value == null ? [] : [{ date: snapshot.effective_date, value: Number(value) }];
    }),
  }));
}

export function collectExplorerSeries(datasets) {
  const candidates = [];
  Object.values(datasets.overview?.series ?? {}).forEach((series) => candidates.push(series));
  Object.values(datasets.credit?.groups ?? {}).forEach((group) => (group.series ?? []).forEach((series) => candidates.push(series)));
  (datasets.fiscal?.flows ?? []).forEach((series) => candidates.push(series));
  (datasets.fiscal?.debt_positions ?? []).forEach((series) => candidates.push(series));
  Object.values(datasets.external?.groups ?? {}).forEach((group) => (group.metrics ?? []).forEach((series) => candidates.push(series)));
  Object.values(datasets.us?.groups ?? {}).forEach((group) => (group.metrics ?? []).forEach((series) => candidates.push(series)));
  candidates.push(...yieldCandidates(datasets.curve));
  return dedupeCandidates(candidates).map((series) => ({
    key: series.key,
    label: series.label ?? series.title ?? series.key,
    unit: series.unit ?? "value",
    observations: series.observations,
  }));
}

function labelWithUnit(series, transformation) {
  if (transformation === "index100") return `${series.label} · índice 100`;
  if (transformation === "change12m") return `${series.label} · mudança em 12 meses`;
  return series.label;
}

function populateSelect(select, candidates) {
  select.replaceChildren(...candidates.map((candidate) => {
    const option = document.createElement("option");
    option.value = candidate.key;
    option.textContent = candidate.label;
    return option;
  }));
}

export function initializeRelationshipExplorer(datasets) {
  const content = document.querySelector("#explorer-content");
  const unavailable = document.querySelector("#explorer-unavailable");
  if (!content || !unavailable) return;
  const candidates = collectExplorerSeries(datasets);
  if (candidates.length < 2) {
    content.hidden = true;
    unavailable.hidden = false;
    unavailable.textContent = "São necessárias ao menos duas séries com histórico para usar o explorador.";
    return;
  }
  content.hidden = false;
  unavailable.hidden = true;
  const byKey = new Map(candidates.map((candidate) => [candidate.key, candidate]));
  const selectA = document.querySelector("#explorer-series-a");
  const selectB = document.querySelector("#explorer-series-b");
  const transform = document.querySelector("#explorer-transform");
  const lag = document.querySelector("#explorer-lag");
  const range = document.querySelector("#explorer-range");
  const viewControls = document.querySelector("#explorer-view-controls");
  const chart = document.querySelector("#explorer-chart");
  const legend = document.querySelector("#explorer-legend");
  const note = document.querySelector("#explorer-note");
  const summary = document.querySelector("#explorer-summary");
  populateSelect(selectA, candidates);
  populateSelect(selectB, candidates);
  const selicKey = candidates.find((item) => item.key === "selic" || item.key === "br.selic.target")?.key;
  const creditKey = candidates.find((item) => item.key === "br.credit.free.interest_rate")?.key;
  if (selicKey) selectA.value = selicKey;
  selectB.value = creditKey && creditKey !== selectA.value ? creditKey : candidates.find((item) => item.key !== selectA.value).key;
  let view = "time";
  let handle = null;

  const rerender = () => {
    if (selectA.value === selectB.value) {
      const alternative = candidates.find((item) => item.key !== selectA.value);
      if (alternative) selectB.value = alternative.key;
    }
    const seriesA = byKey.get(selectA.value);
    const seriesB = byKey.get(selectB.value);
    let a;
    let b;
    if (transform.value === "index100") {
      a = monthlySeries(seriesA.observations);
      b = lagSeries(monthlySeries(seriesB.observations), Number(lag.value));
      [a, b] = filterRange([a, b], range.value);
      [a, b] = rebaseToCommonStart(a, b);
    } else {
      a = transformSeries(seriesA.observations, transform.value);
      b = lagSeries(transformSeries(seriesB.observations, transform.value), Number(lag.value));
      [a, b] = filterRange([a, b], range.value);
    }
    const labelA = labelWithUnit(seriesA, transform.value);
    const labelB = labelWithUnit(seriesB, transform.value);
    const pairs = pairSeries(a, b);
    handle?.destroy();
    handle = view === "scatter"
      ? renderExplorerScatterChart(chart, { pairs, labelA, labelB })
      : renderExplorerTimeChart(chart, { a, b, labelA, labelB, combined: transform.value === "index100" });
    legend.replaceChildren();
    for (const [index, label] of [labelA, labelB].entries()) {
      const span = document.createElement("span");
      span.innerHTML = `<span class="legend-line legend-series-${index + 1}" aria-hidden="true"></span>`;
      span.append(label);
      legend.append(span);
    }
    const lagText = Number(lag.value) ? ` B foi deslocado ${lag.value} meses para a frente para comparar A(t) com B(t−${lag.value}m).` : "";
    note.textContent = view === "scatter"
      ? `${pairs.length} meses coincidentes no recorte.${lagText} O gráfico mostra associação, não causalidade.`
      : `${transform.value === "index100" ? "As duas séries foram rebaseadas para 100 no primeiro mês coincidente do recorte." : "Séries em painéis separados quando as unidades não são diretamente comparáveis."}${lagText}`;
    summary.textContent = `${labelA} e ${labelB}; ${pairs.length} observações mensais coincidentes no recorte.`;
  };

  [selectA, selectB, transform, lag, range].forEach((control) => control.addEventListener("change", rerender));
  viewControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-explorer-view]");
    if (!button) return;
    view = button.dataset.explorerView;
    viewControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  let timer = null;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(rerender, 120); });
  rerender();
}
