import { renderFiscalChart } from "../charts/fiscal.js";
import { formatDate, formatRate } from "../format.js";
import { openIndicatorDetails } from "../indicator_details.js";
import { DEFAULT_RANGES } from "../config.js";
import { setRangeControlState } from "../ranges.js";
import { renderPaginatedRows } from "../table.js";

const LABELS = {
  "br.fiscal.primary_result_12m_gdp": "Primário",
  "br.fiscal.nominal_interest_12m_gdp": "Juros nominais",
  "br.fiscal.nominal_result_12m_gdp": "Nominal",
  "br.fiscal.dbgg_gdp": "DBGG",
  "br.fiscal.dlgg_gdp": "DLGG",
  "br.fiscal.dlsp_gdp": "DLSP",
};

function formatPercentOfGdp(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}% PIB`; }
function formatBillions(value) { return `R$ ${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} bi`; }
function formatYears(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} anos`; }
function formatMonths(value) { return `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} meses`; }

const FISCAL_INTERPRETATIONS = {
  "br.fiscal.primary_result_12m_gdp": "Resultado primário acumulado em 12 meses: receitas menos despesas não financeiras, segundo a convenção oficial da NFSP. No contrato usado pelo monitor, valor positivo indica necessidade de financiamento/déficit e negativo, superávit.",
  "br.fiscal.nominal_interest_12m_gdp": "Juros nominais apropriados pelo setor público em 12 meses. O valor depende de estoque e composição da dívida, indexadores, câmbio e trajetória de juros; não é efeito isolado da Selic.",
  "br.fiscal.nominal_result_12m_gdp": "Resultado nominal acumulado em 12 meses, combinando resultado primário e juros nominais pela convenção da NFSP. Não deve ser lido como medida pura de impulso fiscal corrente.",
  "br.fiscal.dbgg_gdp": "Estoque bruto de débitos do Governo Geral em relação ao PIB. É útil para observar a exposição bruta e a necessidade de financiamento, mas não desconta os ativos financeiros do Governo Geral.",
  "br.fiscal.dlgg_gdp": "Endividamento líquido do Governo Geral em relação ao PIB: balanceia débitos e créditos do Governo Federal, estados e municípios. Tem perímetro institucional próximo ao da DBGG e ajuda a separar exposição bruta de posição financeira líquida.",
  "br.fiscal.dlsp_gdp": "Posição líquida do setor público consolidado em relação ao PIB. Seu perímetro é mais amplo que o Governo Geral porque inclui o setor público não financeiro e o Banco Central; é também o conceito de dívida usado como base do resultado fiscal abaixo da linha.",
};

const STOCK_NOTES = {
  "br.fiscal.dbgg_gdp": "DBGG é bruta: não deduz os ativos financeiros usados nos conceitos de dívida líquida. Também não é sinônimo da DPF administrada pelo Tesouro.",
  "br.fiscal.dlgg_gdp": "DLGG é líquida e mantém o foco no Governo Geral. Ela não deve ser confundida com DLSP, cujo perímetro inclui Banco Central e outros componentes do setor público não financeiro.",
  "br.fiscal.dlsp_gdp": "DLSP possui perímetro institucional mais amplo que DBGG/DLGG. A comparação visual informa posições fiscais distintas, não três versões intercambiáveis do mesmo estoque.",
};

function metricCard(label, value, detail = "", indicator = null) {
  const card = document.createElement(indicator ? "button" : "article");
  if (indicator) card.type = "button";
  card.className = "metric-card fiscal-metric-card";
  const name = document.createElement("p"); name.className = "metric-label"; name.textContent = label;
  const number = document.createElement("p"); number.className = "metric-value"; number.textContent = value;
  card.append(name, number);
  if (detail) {
    const note = document.createElement("p");
    note.className = "metric-meta";
    note.textContent = indicator ? `${detail} · detalhes` : detail;
    card.append(note);
  }
  if (indicator) card.addEventListener("click", () => openIndicatorDetails(indicator));
  return card;
}

function fiscalSeriesIndicator(series, style) {
  const isFlow = series.key.includes("result_") || series.key.includes("interest_");
  return {
    ...series,
    label: LABELS[series.key] || series.title,
    definition: series.definition ?? null,
    interpretation: FISCAL_INTERPRETATIONS[series.key] ?? null,
    caveats: [isFlow
      ? "A convenção das NFSP usada neste painel registra valores positivos como necessidade de financiamento/déficit e negativos como superávit."
      : (STOCK_NOTES[series.key] ?? "Os conceitos de dívida mantêm seus perímetros institucionais originais.")],
    inputs: series.inputs ?? [],
    missing_inputs: series.missing_inputs ?? [],
    series_style: style,
  };
}

function profileIndicator(label, item, unit, interpretation) {
  if (!item) return null;
  return {
    ...item,
    label,
    title: label,
    definition: item.methodology,
    interpretation,
    status: "available",
    data_kind: item.kind ?? "observed",
    unit,
    frequency: { key: "monthly_document_release", label: "mensal, conforme a publicação do relatório" },
    transformation: { key: "published_rmd_value", label: "valor publicado no Relatório Mensal da Dívida" },
    latest: {
      value: item.value,
      date: item.reference_period ?? item.effective_from,
      available_at: item.published_at,
    },
    observations: [],
    source: {
      provider: "Tesouro Nacional",
      name: item.source_label ?? "Relatório Mensal da Dívida Pública Federal (RMD)",
      documentation_url: item.source_url,
      reference: item.source_reference,
    },
    caveats: ["Este valor ainda é um snapshot documental; as séries históricas oficiais do Tesouro ainda não foram incorporadas."],
    history_unavailable_note: "A série histórica oficial será publicada quando o RMD for migrado para observações mensais.",
  };
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
    ["Estoque DPF", m["br.dpf.stock_brl_billions"], formatBillions, "brl_billions", "Estoque da Dívida Pública Federal sob responsabilidade do Tesouro Nacional; não é sinônimo de DBGG, DLGG ou DLSP."],
    ["Vence em 12 meses", m["br.dpf.maturing_12m_share"], formatRate, "percent", "Parcela do estoque da DPF com vencimento nos doze meses seguintes à referência do relatório."],
    ["Prazo médio", m["br.dpf.average_term_years"], formatYears, "years", "Prazo médio oficial da DPF publicado pelo Tesouro. O monitor não o reconstrói a partir de vencimentos individuais."],
    ["Custo médio 12m", m["br.dpf.average_cost_12m"], formatRate, "percent_per_year", "Custo médio acumulado em doze meses da DPF conforme a metodologia oficial do Tesouro."],
    ["Reserva de liquidez", m["br.dpf.liquidity_reserve_brl_billions"], formatBillions, "brl_billions", "Recursos mantidos pelo Tesouro para gestão de caixa e cobertura de vencimentos da dívida."],
    ["Índice de liquidez", m["br.dpf.liquidity_index_months"], formatMonths, "months", "Número de meses de vencimentos da DPF que a reserva de liquidez pode cobrir segundo a métrica publicada no RMD."],
  ];
  for (const [label, item, formatter, unit, interpretation] of items) {
    const indicator = profileIndicator(label, item, unit, interpretation);
    container.append(metricCard(label, item ? formatter(item.value) : "—", item?.source_reference || "", indicator));
  }
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


function renderFiscalReconciliation(flows) {
  const container = document.querySelector("#fiscal-reconciliation");
  if (!container) return;
  const byKey = new Map(flows.map((series) => [series.key, series]));
  const primary = byKey.get("br.fiscal.primary_result_12m_gdp");
  const interest = byKey.get("br.fiscal.nominal_interest_12m_gdp");
  const nominal = byKey.get("br.fiscal.nominal_result_12m_gdp");
  if (!primary || !interest || !nominal) {
    container.textContent = "Séries necessárias indisponíveis.";
    return;
  }
  const maps = [primary, interest, nominal].map((series) => new Map((series.observations ?? []).map((item) => [item.date, Number(item.value)])));
  const dates = [...maps[0].keys()].filter((date) => maps[1].has(date) && maps[2].has(date)).sort();
  const date = dates.at(-1);
  if (!date) {
    container.textContent = "Ainda não há uma data comum às três séries.";
    return;
  }
  const primaryValue = maps[0].get(date);
  const interestValue = maps[1].get(date);
  const nominalValue = maps[2].get(date);
  const calculated = primaryValue + interestValue;
  const residual = nominalValue - calculated;
  const table = document.createElement("table");
  table.className = "fiscal-reconciliation-table";
  const caption = document.createElement("caption");
  caption.textContent = `Conferência na referência ${formatDate(date)}`;
  table.innerHTML = `<thead><tr><th scope="col">Componente</th><th scope="col">% do PIB</th></tr></thead>`;
  const tbody = document.createElement("tbody");
  const rows = [
    ["Resultado primário", primaryValue],
    ["+ Juros nominais", interestValue],
    ["= Soma dos componentes", calculated],
    ["Resultado nominal publicado", nominalValue],
    ["Diferença de conferência", residual],
  ];
  for (const [label, value] of rows) {
    const tr = document.createElement("tr");
    const name = document.createElement("th");
    name.scope = "row";
    name.textContent = label;
    const number = document.createElement("td");
    number.textContent = formatPercentOfGdp(value);
    tr.append(name, number);
    tbody.append(tr);
  }
  table.append(caption, tbody);
  const note = document.createElement("p");
  note.className = "exploration-copy";
  note.textContent = Math.abs(residual) < 0.02
    ? "A pequena diferença, quando existente, é compatível com arredondamento das séries publicadas."
    : "A diferença merece conferência metodológica; o painel não força a identidade quando as séries publicadas não coincidem.";
  container.replaceChildren(table, note);
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
  const debtPositions = payload.debt_positions ?? [];
  let mode = "flows";
  let range = DEFAULT_RANGES.fiscal;
  setRangeControlState(rangeControls, "data-fiscal-range", range);
  let handle = null;

  renderProfile(payload);
  renderFiscalReconciliation(payload.flows);
  const latestDates = [...payload.flows, ...debtPositions].map((s) => s.latest?.date).filter(Boolean).sort();
  dateLabel.textContent = latestDates.length ? `Último dado: ${formatDate(latestDates.at(-1))}` : "Sem dados SGS";

  const rerender = () => {
    const selected = mode === "flows" ? payload.flows : debtPositions;
    const chartSeries = selected.map((series) => ({
      label: LABELS[series.key] || series.title,
      observations: withinRange(series.observations || [], range),
    }));
    metrics.replaceChildren();
    selected.forEach((series, index) => {
      const latest = series.latest;
      metrics.append(metricCard(
        LABELS[series.key] || series.title,
        latest ? formatPercentOfGdp(latest.value) : "—",
        latest ? formatDate(latest.date) : "Sem observação",
        fiscalSeriesIndicator(series, `series-${index + 1}`),
      ));
    });
    legend.replaceChildren();
    selected.forEach((series, index) => {
      const item = document.createElement("span");
      item.innerHTML = `<span class="legend-line legend-series-${index + 1}" aria-hidden="true"></span>`;
      item.append(LABELS[series.key] || series.title); legend.append(item);
    });
    note.textContent = mode === "flows"
      ? payload.sign_convention.note
      : "DBGG mede exposição bruta do Governo Geral; DLGG desconta créditos no mesmo núcleo institucional; DLSP usa perímetro mais amplo, incluindo o Banco Central. DPF permanece um conceito separado do Tesouro.";
    handle?.destroy();
    handle = renderFiscalChart(chart, { series: chartSeries, valueFormatter: formatPercentOfGdp });

    const maps = chartSeries.map((series) => new Map(series.observations.map((o) => [o.date, o])));
    const dates = [...new Set(chartSeries.flatMap((s) => s.observations.map((o) => o.date)))].sort().reverse();
    const rows = [];
    for (const date of dates) {
      const tr = document.createElement("tr");
      const d = document.createElement("td"); d.textContent = formatDate(date); tr.append(d);
      for (const map of maps) { const td = document.createElement("td"); const item = map.get(date); td.textContent = item ? formatPercentOfGdp(item.value) : "—"; tr.append(td); }
      while (tr.children.length < 4) { const td = document.createElement("td"); td.textContent = "—"; tr.append(td); }
      rows.push(tr);
    }
    renderPaginatedRows(tbody, rows);
    document.querySelector("#fiscal-table-head-1").textContent = mode === "flows" ? "Primário" : "DBGG";
    document.querySelector("#fiscal-table-head-2").textContent = mode === "flows" ? "Juros" : "DLGG";
    document.querySelector("#fiscal-table-head-3").textContent = mode === "flows" ? "Nominal" : "DLSP";
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
