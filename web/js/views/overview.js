import { dataKindLabel, formatDate, formatDateTime, formatPoints, formatRate, formatValue } from "../format.js";
import { filterByRange, renderHistoryChart } from "../charts/history.js";

const PRIMARY_KEYS = [
  "selic",
  "taylor_prospective",
  "selic_minus_taylor",
  "ex_ante_real_rate",
  "real_monetary_gap",
];

const ASSUMPTION_KEYS = [
  "expected_inflation",
  "inflation_target",
  "neutral_real_rate",
  "output_gap",
];

const CONTEXT_KEYS = [
  "ipca_12m",
  "ipca_core_12m",
  "ipca_services_12m",
  "ibc_br_mom",
  "unemployment_rate",
  "real_earnings",
];

function seriesUnitSuffix(series) {
  return series.unit === "percent_per_year" ? " a.a." : "";
}

function metricCard(series) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `metric-card ${series.status === "available" ? "" : "unavailable"}`.trim();
  button.dataset.seriesKey = series.key;
  button.setAttribute("aria-label", `Ver metadados de ${series.label}`);

  const label = document.createElement("span");
  label.className = "metric-label";
  label.textContent = series.label;

  const value = document.createElement("span");
  value.className = "metric-value";
  value.textContent = formatValue(series);
  const suffix = seriesUnitSuffix(series);
  if (series.status === "available" && suffix) {
    const unit = document.createElement("span");
    unit.className = "metric-unit";
    unit.textContent = suffix;
    value.append(unit);
  }

  const meta = document.createElement("span");
  meta.className = "metric-meta";
  meta.textContent = series.status === "available"
    ? `Ref. ${formatDate(series.latest.date)}`
    : "Ainda não publicado";

  const kind = document.createElement("span");
  kind.className = "kind-badge";
  kind.textContent = dataKindLabel(series.data_kind);

  button.append(label, value, meta, kind);
  return button;
}

function renderCards(container, keys, series) {
  container.replaceChildren(...keys.map((key) => metricCard(series[key])));
}

function metadataRows(series) {
  const rows = [
    ["Natureza", dataKindLabel(series.data_kind)],
    ["Estado", series.status === "available" ? "disponível" : "indisponível"],
  ];
  if (series.status === "available") {
    rows.push(
      ["Valor", formatValue(series)],
      ["Referência", formatDate(series.latest.date)],
      ["Disponível no monitor desde", formatDateTime(series.latest.available_at)],
      ["Frequência", series.frequency ?? "—"],
      ["Transformação", series.transformation ?? "—"],
      ...(series.latest.source_observation_at ? [["Data da estatística fonte", formatDate(series.latest.source_observation_at)]] : []),
      ["Fonte", series.source ? `${series.source.provider} — ${series.source.name}` : "—"],
    );
  } else {
    rows.push(["Motivo", series.note ?? "Sem dado disponível."]);
  }
  return rows;
}

function showMetadata(series) {
  const dialog = document.querySelector("#metadata-dialog");
  const title = document.querySelector("#metadata-title");
  const body = document.querySelector("#metadata-body");
  title.textContent = series.label;

  const list = document.createElement("dl");
  list.className = "metadata-list";
  for (const [term, description] of metadataRows(series)) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = description;
    list.append(dt, dd);
  }

  if (series.required_inputs?.length) {
    const dt = document.createElement("dt");
    dt.textContent = "Insumos necessários";
    const dd = document.createElement("dd");
    const ul = document.createElement("ul");
    series.required_inputs.forEach((input) => {
      const li = document.createElement("li");
      li.textContent = input;
      ul.append(li);
    });
    dd.append(ul);
    list.append(dt, dd);
  }

  if (series.source?.documentation_url) {
    const dt = document.createElement("dt");
    dt.textContent = "Documentação oficial";
    const dd = document.createElement("dd");
    const link = document.createElement("a");
    link.href = series.source.documentation_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Abrir fonte";
    dd.append(link);
    list.append(dt, dd);
  }

  body.replaceChildren(list);
  dialog.showModal();
}

function updateTable(tbody, selicObservations, taylorObservations, taylorAvailable) {
  const taylorByDate = new Map(taylorObservations.map((item) => [item.date, item]));
  const recent = selicObservations.slice(-12).reverse();
  tbody.replaceChildren(...recent.map((item) => {
    const row = document.createElement("tr");
    const date = document.createElement("td");
    date.textContent = formatDate(item.date);
    const selic = document.createElement("td");
    selic.textContent = formatRate(Number(item.value));
    const taylor = document.createElement("td");
    const taylorItem = taylorByDate.get(item.date);
    taylor.textContent = taylorItem
      ? formatRate(Number(taylorItem.value))
      : taylorAvailable ? "—" : "indisponível";
    row.append(date, selic, taylor);
    return row;
  }));
}

export function renderOverview(payload) {
  const series = payload.series;
  renderCards(document.querySelector("#primary-cards"), PRIMARY_KEYS, series);
  renderCards(document.querySelector("#assumption-cards"), ASSUMPTION_KEYS, series);
  renderCards(document.querySelector("#context-cards"), CONTEXT_KEYS, series);

  document.querySelectorAll("[data-series-key]").forEach((button) => {
    button.addEventListener("click", () => showMetadata(series[button.dataset.seriesKey]));
  });

  const generated = document.querySelector("#generated-at");
  generated.textContent = `Atualizado ${formatDateTime(payload.generated_at)}`;
  const dot = document.querySelector("#data-status");
  dot.classList.add(payload.availability.status === "complete" ? "ok" : "partial");
  const horizon = payload.policy_horizon;
  document.querySelector("#knowledge-mode").textContent = horizon
    ? `Revisão mais recente · horizonte ${formatDate(horizon.reference)}`
    : "Revisão mais recente conhecida";

  const selic = series.selic;
  const taylor = series.taylor_prospective;
  const legend = document.querySelector("#taylor-legend");
  if (taylor.status !== "available") legend.classList.add("unavailable");

  const message = document.querySelector("#history-message");
  message.textContent = taylor.status !== "available"
    ? "A Taylor prospectiva será adicionada quando todos os seus insumos documentados estiverem disponíveis."
    : taylor.observations.length === 0
      ? "O benchmark corrente já está disponível. O histórico da Taylor permanece vazio até existirem vintages historicamente alinhados de r* e hiato."
      : "";

  const chartContainer = document.querySelector("#history-chart");
  const tableBody = document.querySelector("#history-table-body");
  const chartSummary = document.querySelector("#chart-summary");
  const rangeControls = document.querySelector("#range-controls");
  let range = "10";
  let chartHandle = null;

  const rerenderHistory = () => {
    const availableDates = [
      ...(selic.status === "available" ? [selic.observations.at(-1)?.date] : []),
      ...(taylor.status === "available" ? [taylor.observations.at(-1)?.date] : []),
    ].filter(Boolean).sort();
    const anchorDate = availableDates.at(-1) ?? null;
    const selicObservations = selic.status === "available"
      ? filterByRange(selic.observations, range, anchorDate)
      : [];
    const taylorObservations = taylor.status === "available"
      ? filterByRange(taylor.observations, range, anchorDate)
      : [];
    chartHandle?.destroy();
    chartHandle = renderHistoryChart(chartContainer, {
      selic: selicObservations,
      taylor: taylorObservations,
    });
    updateTable(tableBody, selicObservations, taylorObservations, taylor.status === "available");
    if (selicObservations.length) {
      const first = selicObservations[0];
      const last = selicObservations.at(-1);
      const taylorText = taylorObservations.length
        ? ` Taylor prospectiva disponível com ${taylorObservations.length} observações no mesmo intervalo.`
        : "";
      chartSummary.textContent = `Selic de ${formatRate(Number(first.value))} em ${formatDate(first.date)} a ${formatRate(Number(last.value))} em ${formatDate(last.date)}.${taylorText}`;
    } else {
      chartSummary.textContent = "Sem observações no período selecionado.";
    }
  };

  rangeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-range]");
    if (!button) return;
    range = button.dataset.range;
    rangeControls.querySelectorAll("button").forEach((candidate) => {
      candidate.setAttribute("aria-pressed", String(candidate === button));
    });
    rerenderHistory();
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerenderHistory, 120);
  });

  rerenderHistory();
}
