import { filterByRange } from "./charts/history.js";
import { renderIndicatorHistoryChart } from "./charts/indicator_history.js";
import { DEFAULT_RANGES, RANGE_OPTIONS } from "./config.js";
import { dataKindLabel, formatDate, formatDateTime, formatUnitValue, unitLabel } from "./format.js";
import { renderPaginatedRows } from "./table.js";

let currentIndicator = null;
let currentRange = DEFAULT_RANGES.indicatorDetails;
let chartHandle = null;
let initialized = false;

function dialogNodes() {
  return {
    dialog: document.querySelector("#metadata-dialog"),
    title: document.querySelector("#metadata-title"),
    body: document.querySelector("#metadata-body"),
  };
}

function publicMetadataLabel(value) {
  if (!value || typeof value !== "object") return null;
  return typeof value.label === "string" && value.label.trim() ? value.label : null;
}

function sourceLabel(source) {
  if (!source) return "—";
  return [source.provider, source.name].filter(Boolean).join(" — ") || "—";
}

function normalize(indicator) {
  const latest = indicator.latest ?? (indicator.value != null ? {
    value: indicator.value,
    date: indicator.reference_period ?? indicator.effective_from ?? null,
    reference_period: indicator.reference_period ?? null,
    as_of_date: indicator.as_of_date ?? indicator.source_observation_at ?? null,
    available_at: indicator.available_at ?? indicator.published_at ?? null,
  } : null);
  return {
    ...indicator,
    label: indicator.label ?? indicator.title ?? "Indicador",
    title: indicator.title ?? indicator.label ?? "Indicador",
    definition: indicator.definition ?? null,
    interpretation: indicator.interpretation ?? null,
    methodology: indicator.methodology ?? null,
    caveats: Array.isArray(indicator.caveats) ? indicator.caveats.filter(Boolean) : [],
    inputs: Array.isArray(indicator.inputs) ? indicator.inputs.filter(Boolean) : [],
    missing_inputs: Array.isArray(indicator.missing_inputs) ? indicator.missing_inputs.filter(Boolean) : [],
    data_kind: indicator.data_kind ?? indicator.kind ?? "observed",
    observations: Array.isArray(indicator.observations) ? indicator.observations : [],
    latest,
    source: indicator.source ?? null,
    unit: indicator.unit ?? "percent",
    status: indicator.status ?? (latest ? "available" : "unavailable"),
  };
}

function appendRow(list, term, description) {
  if (description == null || description === "") return;
  const dt = document.createElement("dt");
  dt.textContent = term;
  const dd = document.createElement("dd");
  if (description instanceof Node) dd.append(description);
  else dd.textContent = String(description);
  list.append(dt, dd);
}

function sourceLink(indicator) {
  const url = indicator.source?.documentation_url ?? indicator.source?.url ?? indicator.source_url;
  if (!url) return null;
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "Abrir fonte oficial";
  return link;
}

function historyAvailable(indicator) {
  return indicator.observations.length >= 2;
}

function section(title, content, className = "indicator-explanation") {
  const box = document.createElement("section");
  box.className = className;
  const heading = document.createElement("h3");
  heading.textContent = title;
  box.append(heading, content);
  return box;
}

function paragraphSection(title, text) {
  if (!text) return null;
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  return section(title, paragraph);
}

function referenceListSection(title, values, className) {
  if (!values?.length) return null;
  const references = new Map();
  for (const value of values) {
    if (!value || typeof value !== "object" || !value.key || !value.label) continue;
    references.set(value.key, value);
  }
  if (!references.size) return null;
  const list = document.createElement("ul");
  for (const value of references.values()) {
    const item = document.createElement("li");
    item.textContent = value.label;
    list.append(item);
  }
  return section(title, list, className);
}

function textListSection(title, values, className) {
  const texts = [...new Set((values ?? []).filter((value) => typeof value === "string" && value.trim()))];
  if (!texts.length) return null;
  const list = document.createElement("ul");
  for (const text of texts) {
    const item = document.createElement("li");
    item.textContent = text;
    list.append(item);
  }
  return section(title, list, className);
}

function detailsView(indicator) {
  const wrapper = document.createElement("div");
  wrapper.className = "indicator-details-view";

  const definition = paragraphSection("O que mede", indicator.definition);
  const interpretation = paragraphSection("Como interpretar", indicator.interpretation);
  const methodology = paragraphSection("Metodologia", indicator.methodology);
  for (const item of [definition, interpretation, methodology]) if (item) wrapper.append(item);

  const list = document.createElement("dl");
  list.className = "metadata-list";
  appendRow(list, "Natureza", dataKindLabel(indicator.data_kind));
  appendRow(list, "Estado", indicator.status === "available" ? "disponível" : "indisponível");
  if (indicator.latest) {
    appendRow(list, "Valor", formatUnitValue(Number(indicator.latest.value), indicator.unit));
    appendRow(list, "Referência", formatDate(indicator.latest.reference_period ?? indicator.latest.date));
    if (indicator.latest.as_of_date) appendRow(list, "Data da estimativa", formatDate(indicator.latest.as_of_date));
    if (indicator.latest.available_at) appendRow(list, "Disponível em", formatDateTime(indicator.latest.available_at));
    appendRow(list, "Unidade", indicator.display_unit ?? unitLabel(indicator.unit));
  }
  appendRow(list, "Frequência", publicMetadataLabel(indicator.frequency));
  appendRow(list, "Transformação", publicMetadataLabel(indicator.transformation));
  appendRow(list, "Fonte", sourceLabel(indicator.source));
  appendRow(list, "Referência da fonte", indicator.source_reference ?? indicator.source?.reference);
  const link = sourceLink(indicator);
  if (link) appendRow(list, "Documentação", link);
  wrapper.append(list);

  const inputs = referenceListSection("Insumos", indicator.inputs, "indicator-inputs");
  const missing = referenceListSection("Insumos ainda indisponíveis", indicator.missing_inputs, "indicator-missing-inputs");
  const caveats = textListSection("Ressalvas", indicator.caveats, "indicator-caveats");
  for (const item of [inputs, missing, caveats]) if (item) wrapper.append(item);

  const actions = document.createElement("div");
  actions.className = "indicator-dialog-actions";
  if (historyAvailable(indicator)) {
    const history = document.createElement("button");
    history.type = "button";
    history.className = "secondary-button";
    history.dataset.indicatorAction = "history";
    history.textContent = "Ver série histórica";
    actions.append(history);
  } else {
    const unavailable = document.createElement("p");
    unavailable.className = "history-unavailable-note";
    unavailable.textContent = indicator.history_unavailable_note ?? "Série histórica ainda não publicada para este indicador.";
    actions.append(unavailable);
  }
  wrapper.append(actions);
  return wrapper;
}

function renderHistory(indicator) {
  const { body } = dialogNodes();
  chartHandle?.destroy();
  const wrapper = document.createElement("div");
  wrapper.className = "indicator-history-view";

  const toolbar = document.createElement("div");
  toolbar.className = "indicator-history-toolbar";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "secondary-button";
  back.dataset.indicatorAction = "details";
  back.textContent = "← Voltar aos detalhes";
  const ranges = document.createElement("div");
  ranges.className = "range-controls";
  ranges.setAttribute("role", "group");
  ranges.setAttribute("aria-label", "Período da série histórica");
  for (const [value, label] of RANGE_OPTIONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.indicatorRange = value;
    button.setAttribute("aria-pressed", String(value === currentRange));
    button.textContent = label;
    ranges.append(button);
  }
  toolbar.append(back, ranges);

  const chart = document.createElement("div");
  chart.className = "chart indicator-history-chart";
  chart.setAttribute("role", "img");
  chart.setAttribute("aria-label", `Série histórica de ${indicator.label}`);

  const data = document.createElement("details");
  data.className = "indicator-history-data data-table-panel";
  const summary = document.createElement("summary");
  summary.textContent = "Ver dados do período selecionado";
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap indicator-history-table";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th scope=\"col\">Data</th><th scope=\"col\">Valor</th></tr>";
  const tbody = document.createElement("tbody");
  table.append(thead, tbody);
  tableWrap.append(table);
  data.append(summary, tableWrap);
  wrapper.append(toolbar, chart, data);
  body.replaceChildren(wrapper);

  const observations = filterByRange(indicator.observations, currentRange);
  const formatter = (value) => formatUnitValue(Number(value), indicator.unit);
  chartHandle = renderIndicatorHistoryChart(chart, {
    observations,
    valueFormatter: formatter,
    step: indicator.history_style === "step",
    style: indicator.series_style ?? "series-1",
  });
  const rows = observations.slice().reverse().map((item) => {
    const row = document.createElement("tr");
    const date = document.createElement("td");
    date.textContent = formatDate(item.date);
    const value = document.createElement("td");
    value.textContent = formatter(item.value);
    row.append(date, value);
    return row;
  });
  renderPaginatedRows(tbody, rows);
}

function renderDetails(indicator) {
  const { body } = dialogNodes();
  chartHandle?.destroy();
  chartHandle = null;
  body.replaceChildren(detailsView(indicator));
}

export function openIndicatorDetails(rawIndicator) {
  currentIndicator = normalize(rawIndicator);
  currentRange = DEFAULT_RANGES.indicatorDetails;
  const { dialog, title } = dialogNodes();
  title.textContent = currentIndicator.label;
  renderDetails(currentIndicator);
  if (!dialog.open) dialog.showModal();
}

export function initializeIndicatorDetails() {
  if (initialized) return;
  const { dialog, body } = dialogNodes();
  if (!dialog || !body) return;
  initialized = true;
  body.addEventListener("click", (event) => {
    const history = event.target.closest("button[data-indicator-action=\"history\"]");
    if (history && currentIndicator) {
      renderHistory(currentIndicator);
      return;
    }
    const details = event.target.closest("button[data-indicator-action=\"details\"]");
    if (details && currentIndicator) {
      renderDetails(currentIndicator);
      return;
    }
    const range = event.target.closest("button[data-indicator-range]");
    if (range && currentIndicator) {
      currentRange = range.dataset.indicatorRange;
      renderHistory(currentIndicator);
    }
  });
  dialog.addEventListener("close", () => {
    chartHandle?.destroy();
    chartHandle = null;
    currentIndicator = null;
  });
}
