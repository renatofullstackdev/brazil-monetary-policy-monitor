import { dataKindLabel, formatDate, formatDateTime, formatPoints, formatRate, formatValue } from "../format.js";
import { openIndicatorDetails } from "../indicator_details.js";
import { filterByRange, renderHistoryChart } from "../charts/history.js";
import { DEFAULT_RANGES } from "../config.js";
import { setRangeControlState } from "../ranges.js";
import { asOfObservation, renderPaginatedRows } from "../table.js";

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


function latestNumber(series) {
  return series?.status === "available" && series.latest && Number.isFinite(Number(series.latest.value))
    ? Number(series.latest.value)
    : null;
}

function renderCurrentReading(series) {
  const target = document.querySelector("#current-reading");
  if (!target) return;
  const selic = latestNumber(series.selic);
  const taylor = latestNumber(series.taylor_prospective);
  const realRate = latestNumber(series.ex_ante_real_rate);
  const neutral = latestNumber(series.neutral_real_rate);
  const realGap = latestNumber(series.real_monetary_gap);
  const parts = [];
  if (selic !== null && taylor !== null) {
    const difference = selic - taylor;
    parts.push(`A Selic está ${formatPoints(Math.abs(difference))} ${difference >= 0 ? "acima" : "abaixo"} da Taylor de referência.`);
  } else if (selic !== null) {
    parts.push(`A Selic está em ${formatRate(selic)}, mas a Taylor de referência ainda não pode ser calculada com todos os insumos documentados.`);
  }
  if (realRate !== null && neutral !== null && realGap !== null) {
    const relation = realGap >= 0 ? "acima" : "abaixo";
    parts.push(`O juro real ex ante é ${formatRate(realRate)}, ${formatPoints(Math.abs(realGap))} ${relation} da estimativa de taxa real neutra de ${formatRate(neutral)}.`);
  }
  target.textContent = parts.length
    ? parts.join(" ")
    : "Ainda faltam insumos para sintetizar a posição da Selic em relação às referências do monitor.";
}

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

const INTERPRETATIONS = {
  selic: "Meta para a taxa básica de juros definida pelo Copom. É o principal instrumento operacional da política monetária brasileira.",
  taylor_prospective: "Regra mecânica de referência que combina inflação esperada, meta, taxa real neutra e hiato do produto. A diferença para a Selic é descritiva, não uma recomendação de política.",
  selic_minus_taylor: "Mostra quantos pontos percentuais a Selic corrente está acima ou abaixo da regra de Taylor usada como referência pelo monitor.",
  ex_ante_real_rate: "Aproxima o juro real prospectivo subtraindo da Selic a inflação esperada no horizonte relevante.",
  real_monetary_gap: "Compara o juro real ex ante com a estimativa de taxa real neutra. É uma medida de distância em relação ao parâmetro neutro, não uma classificação normativa automática.",
  expected_inflation: "Inflação prospectiva usada pela regra de referência. O monitor compõe medianas mensais Focus no horizonte relevante do Copom e identifica o resultado como cálculo derivado.",
  inflation_target: "Meta oficial usada como referência no regime de metas para a inflação.",
  neutral_real_rate: "Estimativa da taxa real compatível com equilíbrio macroeconômico no horizonte considerado; não é uma variável diretamente observável.",
  output_gap: "Estimativa da diferença entre atividade efetiva e produto potencial. Valores positivos indicam atividade acima da estimativa de potencial e negativos, abaixo.",
  ipca_12m: "Variação acumulada do IPCA em doze meses, construída a partir das variações mensais oficiais.",
  ipca_core_12m: "Acumulado em doze meses de uma medida de núcleo do IPCA, útil para observar componentes menos influenciados por movimentos extremos de preços.",
  ipca_services_12m: "Acumulado em doze meses dos preços de serviços dentro do IPCA, componente acompanhado por sua relação com demanda, salários e persistência inflacionária.",
  ibc_br_mom: "Variação mensal do IBC-Br dessazonalizado, indicador de atividade econômica do Banco Central. Não equivale ao PIB trimestral do IBGE.",
  unemployment_rate: "Taxa de desocupação da PNAD Contínua, usada como uma das leituras do grau de utilização do mercado de trabalho.",
  real_earnings: "Rendimento médio real habitual da PNAD Contínua. A série já desconta a inflação segundo a metodologia da fonte.",
};

function indicatorFor(series) {
  return {
    ...series,
    definition: series.definition ?? null,
    interpretation: INTERPRETATIONS[series.key] ?? series.interpretation ?? null,
    methodology: series.methodology ?? null,
    caveats: series.caveats ?? [],
    inputs: series.inputs ?? [],
    missing_inputs: series.missing_inputs ?? [],
    history_style: series.key === "selic" ? "step" : "line",
    series_style: series.key === "taylor_prospective" ? "series-2" : "series-1",
  };
}

function updateTable(tbody, selicObservations, taylorObservations, taylorAvailable) {
  const rows = selicObservations.slice().reverse().map((item) => {
    const row = document.createElement("tr");
    const date = document.createElement("td");
    date.textContent = formatDate(item.date);
    const selic = document.createElement("td");
    selic.textContent = formatRate(Number(item.value));
    const taylor = document.createElement("td");
    const taylorItem = asOfObservation(taylorObservations, item.date);
    taylor.textContent = taylorItem
      ? formatRate(Number(taylorItem.value))
      : taylorAvailable ? "—" : "indisponível";
    row.append(date, selic, taylor);
    return row;
  });
  renderPaginatedRows(tbody, rows);
}

export function renderOverview(payload, copom = null) {
  const series = payload.series;
  renderCards(document.querySelector("#primary-cards"), PRIMARY_KEYS, series);
  renderCards(document.querySelector("#assumption-cards"), ASSUMPTION_KEYS, series);
  renderCards(document.querySelector("#context-cards"), CONTEXT_KEYS, series);
  renderCurrentReading(series);

  document.querySelectorAll("[data-series-key]").forEach((button) => {
    button.addEventListener("click", () => openIndicatorDetails(indicatorFor(series[button.dataset.seriesKey])));
  });

  const generated = document.querySelector("#generated-at");
  generated.textContent = `Atualizado ${formatDateTime(payload.generated_at)}`;
  const dot = document.querySelector("#data-status");
  dot.classList.add(payload.availability.status === "complete" ? "ok" : "partial");
  const horizon = payload.policy_horizon;
  const knowledgeLabel = payload.knowledge_mode === "as_known"
    ? `Como era conhecido em ${formatDate((payload.knowledge_cutoff ?? "").slice(0, 10))}`
    : "Informações mais recentes";
  document.querySelector("#knowledge-mode").textContent = horizon
    ? `${knowledgeLabel} · horizonte ${formatDate(horizon.reference)}`
    : knowledgeLabel;

  const selic = series.selic;
  const taylor = series.taylor_prospective;
  const legend = document.querySelector("#taylor-legend");
  if (taylor.status !== "available") legend.classList.add("unavailable");

  const message = document.querySelector("#history-message");
  message.textContent = taylor.status !== "available"
    ? "A Taylor de referência será adicionada quando todos os seus insumos documentados estiverem disponíveis."
    : taylor.observations.length === 0
      ? "A Taylor de referência corrente já está disponível. O histórico da Taylor permanece vazio até existirem registros históricos de r* e hiato alinhados à data de conhecimento."
      : "";

  const chartContainer = document.querySelector("#history-chart");
  const tableBody = document.querySelector("#history-table-body");
  const chartSummary = document.querySelector("#chart-summary");
  const rangeControls = document.querySelector("#range-controls");
  let range = DEFAULT_RANGES.monetaryPolicy;
  setRangeControlState(rangeControls, "data-range", range);
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
      events: copom?.decision_markers ?? [],
    });
    updateTable(tableBody, selicObservations, taylorObservations, taylor.status === "available");
    if (selicObservations.length) {
      const first = selicObservations[0];
      const last = selicObservations.at(-1);
      const taylorText = taylorObservations.length
        ? ` Taylor de referência disponível com ${taylorObservations.length} observações no mesmo intervalo.`
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
