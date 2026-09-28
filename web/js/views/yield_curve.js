import { formatDate, formatPoints, formatRate } from "../format.js";
import { renderYieldCurveChart, renderYieldCurveDeltaChart } from "../charts/yield_curve.js";
import { openIndicatorDetails } from "../indicator_details.js";

const FIELD_BY_KIND = { nominal: "nominal", real: "real", implicit: "implicit_inflation" };
const LABEL_BY_KIND = { nominal: "Nominal", real: "Real", implicit: "Inflação implícita" };
const FAMILY_LABELS = {
  di: "Trajetória de juros · DI B3",
  ettj: "Curva zero-cupom · ANBIMA",
};

function familyContract(payload, family) {
  if (family === "ettj") {
    const curve = payload.market?.ettj;
    return curve?.status === "available" ? {
      family, latest: curve.latest, snapshots: curve.history ?? [], presets: curve.presets ?? {},
      source: curve.source, availableRange: curve.available_range, caveat: payload.market?.methodology?.caveat,
    } : null;
  }
  return null;
}

function pointsFor(snapshot, kind, family) {
  if (!snapshot) return [];
  if (kind === "implicit") {
    const direct = snapshot.implicit;
    if (direct?.length) return direct.map((item) => ({ tenor_years: Number(item.tenor_years), value: Number(item.yield_percent) }));
    return (snapshot.tenors ?? []).filter((item) => item.implicit_inflation != null)
      .map((item) => ({ tenor_years: Number(item.tenor_years), value: Number(item.implicit_inflation) }));
  }
  const direct = snapshot[kind] ?? [];
  if (direct.length) return direct.map((item) => ({
    tenor_years: Number(item.tenor_years), value: Number(item.yield_percent),
    maturity_date: item.maturity_date, instrument_type: item.instrument_type,
  }));
  const field = FIELD_BY_KIND[kind];
  return (snapshot.tenors ?? []).filter((item) => item[field] != null)
    .map((item) => ({ tenor_years: Number(item.tenor_years), value: Number(item[field]) }));
}

function tenorValue(snapshot, kind, tenor) {
  if (!snapshot) return null;
  const row = (snapshot.tenors ?? []).find((item) => Number(item.tenor_years) === tenor);
  const value = row?.[FIELD_BY_KIND[kind]];
  return value == null ? null : Number(value);
}

function slopeValue(snapshot, kind) {
  if (!snapshot) return null;
  const key = `${kind === "implicit" ? "implicit" : kind}_10y_minus_2y`;
  const value = snapshot.slopes?.[key];
  return value == null ? null : Number(value);
}

function nearestSnapshot(snapshots, requestedDate) {
  return snapshots.filter((snapshot) => snapshot.effective_date <= requestedDate).at(-1) ?? null;
}

function presetSnapshot(contract, key) {
  const preset = contract.presets?.[key];
  if (!preset) return null;
  if (key === "previous_copom") return preset.status === "available" ? preset.snapshot : null;
  return preset;
}

function curveHistory(contract, kind, tenor = null, slope = false) {
  return (contract.snapshots ?? []).flatMap((snapshot) => {
    const value = slope ? slopeValue(snapshot, kind) : tenorValue(snapshot, kind, tenor);
    return value == null ? [] : [{ date: snapshot.effective_date, value }];
  });
}

function curveInterpretation(family, kind, tenor = null, slope = false) {
  if (slope) return "Diferença entre 10 e 2 anos da mesma estrutura a termo. O sinal descreve a inclinação, mas não identifica sozinho sua causa.";
  if (kind === "implicit") return `Inflação implícita para ${tenor} anos. Contém prêmios de risco e liquidez e não equivale a expectativa pura de inflação.`;
  return `Taxa zero-cupom ${LABEL_BY_KIND[kind].toLowerCase()} para ${tenor} anos na ETTJ da ANBIMA, estimada pela metodologia de estrutura a termo publicada pela associação.`;
}

function curveMetric(contract, snapshot, kind, label, value, { points = false, tenor = null, slope = false } = {}) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "curve-metric";
  const title = document.createElement("span"); title.textContent = label;
  const strong = document.createElement("strong"); strong.textContent = value == null ? "—" : points ? formatPoints(value) : formatRate(value);
  const hint = document.createElement("small"); hint.textContent = "Detalhes e histórico";
  card.append(title, strong, hint);
  const observations = curveHistory(contract, kind, tenor, slope);
  card.addEventListener("click", () => openIndicatorDetails({
    key: `yield_curve_${contract.family}_${kind}_${slope ? "slope_10y_2y" : `${tenor}y`}`,
    label, title: label, definition: contract.caveat,
    interpretation: curveInterpretation(contract.family, kind, tenor, slope),
    status: value == null ? "unavailable" : "available", data_kind: "derived",
    unit: points ? "percentage_points" : "percent_per_year",
    frequency: { key: "daily", label: "diária" },
    transformation: slope
      ? { key: "constant_tenor_10y_minus_2y", label: "taxa de 10 anos menos taxa de 2 anos da mesma curva" }
      : { key: "anbima_ettj_zero_coupon", label: "taxa zero-cupom da ETTJ ANBIMA" },
    caveats: contract.caveat ? [contract.caveat] : [],
    inputs: [], missing_inputs: [],
    latest: value == null ? null : { value, date: snapshot.effective_date }, observations,
    source: contract.source, series_style: slope ? "series-3" : kind === "real" ? "series-4" : kind === "implicit" ? "series-2" : "series-1",
  }));
  return card;
}

function updateMetrics(container, contract, snapshot, kind) {
  container.replaceChildren(
    curveMetric(contract, snapshot, kind, `${LABEL_BY_KIND[kind]} · 2 anos`, tenorValue(snapshot, kind, 2), { tenor: 2 }),
    curveMetric(contract, snapshot, kind, `${LABEL_BY_KIND[kind]} · 10 anos`, tenorValue(snapshot, kind, 10), { tenor: 10 }),
    curveMetric(contract, snapshot, kind, "Inclinação 10a − 2a", slopeValue(snapshot, kind), { points: true, slope: true }),
  );
}

function updateTermTable(tbody, current, comparison, kind) {
  const field = FIELD_BY_KIND[kind];
  const currentByTenor = new Map((current?.tenors ?? []).map((item) => [Number(item.tenor_years), item[field]]));
  const comparisonByTenor = new Map((comparison?.tenors ?? []).map((item) => [Number(item.tenor_years), item[field]]));
  tbody.replaceChildren(...[2, 3, 5, 7, 10].map((tenor) => {
    const row = document.createElement("tr");
    const a = document.createElement("td"); a.textContent = `${tenor} anos`;
    const b = document.createElement("td"); b.textContent = currentByTenor.get(tenor) == null ? "—" : formatRate(Number(currentByTenor.get(tenor)));
    const c = document.createElement("td"); c.textContent = comparisonByTenor.get(tenor) == null ? "—" : formatRate(Number(comparisonByTenor.get(tenor)));
    row.append(a, b, c); return row;
  }));
}

function simpleMetric(label, value, detail, { points = false } = {}) {
  const card = document.createElement("div"); card.className = "curve-metric";
  const title = document.createElement("span"); title.textContent = label;
  const strong = document.createElement("strong"); strong.textContent = value == null ? "—" : points ? formatPoints(value) : formatRate(value);
  const hint = document.createElement("small"); hint.textContent = detail;
  card.append(title, strong, hint); return card;
}

function nearestPoint(points, years) {
  return points.length ? points.reduce((best, item) => Math.abs(item.tenor_years - years) < Math.abs(best.tenor_years - years) ? item : best) : null;
}

function setTableHeaders(headers, first, second, third) {
  headers[0].textContent = first;
  headers[1].textContent = second;
  headers[2].textContent = third;
}

function signedDifferenceText(value, lowerText, higherText, closeText) {
  if (value == null || !Number.isFinite(value)) return "Não há pontos suficientes para comparar.";
  const magnitude = formatPoints(Math.abs(value)).replace(/^\+/, "");
  if (value <= -0.10) return `${lowerText} ${magnitude}.`;
  if (value >= 0.10) return `${higherText} ${magnitude}.`;
  return closeText;
}

function setGuide(container, title, explanation, reading) {
  container.replaceChildren();
  const strong = document.createElement("strong"); strong.textContent = title;
  const p1 = document.createElement("p"); p1.textContent = explanation;
  const p2 = document.createElement("p"); p2.className = "curve-reading"; p2.textContent = reading;
  container.append(strong, p1, p2);
}

function setFamilyStatus(container, text, warning = false) {
  container.textContent = text;
  container.classList.toggle("is-warning", warning);
}

function lastRunDescription(contract, providerLabel) {
  const run = contract?.last_ingestion;
  if (!run) return `Ainda não há dados de ${providerLabel} no contrato publicado. Execute ./scripts/update-market-curves.sh.`;

  const received = Number(run.records_received ?? 0);
  const finished = run.finished_at ? ` em ${new Date(run.finished_at).toLocaleString("pt-BR")}` : "";

  if (received > 0) {
    if (run.status === "succeeded") return `Última coleta concluída${finished}: ${received} registros recebidos.`;
    if (run.status === "partial") return `Última coleta parcialmente concluída${finished}: ${received} registros recebidos.`;
    if (run.status === "failed") return `A última coleta falhou${finished}, após receber ${received} registros.`;
    return `Última coleta registrada${finished}: ${received} registros recebidos.`;
  }

  if (run.status === "failed") return `A última coleta falhou${finished} e não produziu registros utilizáveis.`;
  if (run.status === "partial") return `A última coleta terminou parcialmente${finished}, sem registros utilizáveis.`;
  if (run.status === "succeeded") return `A última coleta foi concluída${finished}, mas não produziu registros utilizáveis.`;
  return `A última coleta${finished} não produziu registros utilizáveis.`;
}

function renderFamilyUnavailable(payload, family, elements) {
  const providerLabel = family === "di" ? "DI1 da B3" : "ETTJ da ANBIMA";
  const sourceContract = payload.market?.[family];
  const diagnostic = lastRunDescription(sourceContract, providerLabel);
  setFamilyStatus(elements.familyStatus, `${providerLabel}: indisponível. ${diagnostic}`, true);
  setGuide(
    elements.guide,
    family === "di" ? "Pergunta: o mercado precifica queda ou alta dos juros à frente?" : "Pergunta: como a estrutura a termo muda com o prazo?",
    family === "di"
      ? "Essa leitura precisa dos contratos DI1 coletados da B3. Sem pontos DI não há taxa até o vencimento nem forwards para calcular."
      : "Essa leitura depende da curva escolhida estar presente no contrato publicado.",
    "O painel mantém a opção selecionável justamente para mostrar por que a leitura não está disponível, em vez de deixar um botão silenciosamente desabilitado.",
  );
  elements.metrics.replaceChildren();
  elements.legend.replaceChildren();
  elements.note.textContent = diagnostic;
  elements.date.textContent = "Sem dados para esta referência";
  elements.summary.textContent = `${providerLabel} indisponível.`;
  elements.table.replaceChildren();
  elements.chartHandle?.destroy();
  elements.chart.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "inline-note";
  empty.textContent = diagnostic;
  elements.chart.append(empty);
  elements.methodNote.textContent = family === "di"
    ? "DI1 B3 só é habilitado analiticamente quando a coleta contém ao menos um contrato válido; forwards exigem ao menos dois vencimentos válidos."
    : "A referência escolhida está sem observações publicadas neste recorte.";
  return { ...elements, chartHandle: { destroy() { empty.remove(); } } };
}

function renderDi(payload, mode, elements, selicLatest) {
  const latest = payload.market?.di?.latest;
  if (!latest) return renderFamilyUnavailable(payload, "di", elements);

  const rates = (latest.points ?? []).map((item) => ({
    tenor_years: Number(item.tenor_years), value: Number(item.yield_percent), label: item.instrument_key ?? "DI1",
  })).filter((item) => Number.isFinite(item.tenor_years) && Number.isFinite(item.value));
  const forwards = (latest.forwards ?? []).map((item) => ({
    tenor_years: Number(item.end_years), value: Number(item.rate_percent),
    label: `${item.start_instrument ?? "início"} → ${item.end_instrument ?? "fim"}`,
  })).filter((item) => Number.isFinite(item.tenor_years) && Number.isFinite(item.value));
  const raw = mode === "forwards" ? forwards : rates;
  const oneYear = nearestPoint(rates, 1);
  const selic = selicLatest?.value == null ? null : Number(selicLatest.value);

  if (mode === "rates") {
    const difference = oneYear && Number.isFinite(selic) ? oneYear.value - selic : null;
    elements.metrics.replaceChildren(
      simpleMetric("Selic atual", selic, selicLatest?.date ? `Meta em ${formatDate(selicLatest.date)}` : "referência do BCB"),
      simpleMetric("DI próximo de 1 ano", oneYear?.value, oneYear?.label ?? "sem contrato próximo"),
      simpleMetric("DI ~1a − Selic", difference, "diferença de nível", { points: true }),
    );
    const reading = signedDifferenceText(
      difference,
      "O DI próximo de 1 ano está abaixo da Selic atual em",
      "O DI próximo de 1 ano está acima da Selic atual em",
      "O DI próximo de 1 ano está próximo da Selic atual.",
    );
    setGuide(
      elements.guide,
      "Pergunta: qual taxa média o mercado embute de hoje até cada vencimento?",
      "Cada ponto DI1 resume a taxa anualizada negociada até aquele vencimento. Compare-a com a linha da Selic atual para enxergar se a taxa média precificada no período está abaixo ou acima da taxa de política de hoje.",
      `${reading} Isso é compatível com uma trajetória de juros mais baixa/alta ao longo do período, mas a diferença também contém prêmios de mercado.`,
    );
    setTableHeaders(elements.headers, "Contrato", "Taxa até o vencimento", "Prazo aproximado");
  } else {
    const first = raw[0] ?? null;
    const oneYearForward = nearestPoint(raw, 1);
    const last = raw.at(-1) ?? null;
    elements.metrics.replaceChildren(
      simpleMetric("Forward mais curto", first?.value, first?.label ?? "sem trecho"),
      simpleMetric("Forward próximo de 1 ano", oneYearForward?.value, oneYearForward?.label ?? "sem trecho próximo"),
      simpleMetric("Forward mais longo", last?.value, last?.label ?? "sem trecho"),
    );
    const direction = first && last
      ? signedDifferenceText(last.value - first.value, "Os forwards mais longos ficam abaixo dos mais curtos em", "Os forwards mais longos ficam acima dos mais curtos em", "Os forwards curtos e longos estão em níveis semelhantes.")
      : "Há poucos trechos para comparar a direção dos forwards.";
    setGuide(
      elements.guide,
      "Pergunta: que taxa está implícita apenas entre dois vencimentos futuros?",
      "O forward remove a média acumulada desde hoje e isola a taxa anualizada compatível com o intervalo entre dois contratos DI1 adjacentes. É a leitura mais próxima de uma trajetória por segmentos futuros.",
      `${direction} Forward também contém prêmio de risco; não deve ser lido como previsão pontual da Selic em uma reunião específica.`,
    );
    setTableHeaders(elements.headers, "Trecho", "Taxa forward", "Fim do trecho");
  }

  elements.table.replaceChildren(...raw.map((item) => {
    const row = document.createElement("tr");
    const a = document.createElement("td"); a.textContent = item.label;
    const b = document.createElement("td"); b.textContent = formatRate(item.value);
    const c = document.createElement("td"); c.textContent = `${item.tenor_years.toFixed(2)} anos`;
    row.append(a, b, c); return row;
  }));
  elements.legend.replaceChildren();
  const legendItem = document.createElement("span");
  legendItem.innerHTML = '<span class="legend-line legend-series-1" aria-hidden="true"></span>';
  legendItem.append(mode === "forwards" ? "Forward entre vencimentos DI1" : `DI1 · ${formatDate(latest.effective_date)}`);
  elements.legend.append(legendItem);
  if (Number.isFinite(selic)) {
    const benchmarkLegend = document.createElement("span");
    benchmarkLegend.innerHTML = '<span class="legend-line legend-series-3" aria-hidden="true"></span>';
    benchmarkLegend.append(`Selic atual · ${formatRate(selic)}`);
    elements.legend.append(benchmarkLegend);
  }
  elements.note.textContent = mode === "forwards"
    ? "Use forwards para observar os segmentos futuros da curva; quedas ou altas entre trechos não isolam expectativa de prêmio."
    : "Use os DI1 para comparar a taxa média até cada vencimento com a Selic vigente; o ponto não é a Selic esperada exatamente naquela data.";
  elements.date.textContent = `DI B3 · ref. ${formatDate(latest.effective_date)}`;
  elements.summary.textContent = `${raw.length} pontos de ${mode === "forwards" ? "taxas forward" : "DI futuro"} em ${formatDate(latest.effective_date)}.`;
  setFamilyStatus(elements.familyStatus, `DI B3 disponível · ${rates.length} contratos · ${forwards.length} forwards · ref. ${formatDate(latest.effective_date)}.`);
  elements.chartHandle?.destroy();
  const chartHandle = renderYieldCurveChart(elements.chart, {
    current: raw,
    comparison: [],
    currentLabel: formatDate(latest.effective_date),
    comparisonLabel: "",
    benchmark: Number.isFinite(selic) ? { value: selic, label: "Selic" } : null,
  });
  return { ...elements, chartHandle };
}

function setEttjGuide(container, snapshot, kind, family) {
  const slope = slopeValue(snapshot, kind);
  const direction = signedDifferenceText(
    slope,
    "A taxa de 10 anos está abaixo da de 2 anos em",
    "A taxa de 10 anos está acima da de 2 anos em",
    "Os vértices de 2 e 10 anos estão em níveis próximos.",
  );
  if (kind === "nominal") {
    setGuide(container,
      "Pergunta: como o custo nominal do dinheiro muda com o prazo?",
      "Compare os vértices de 2 e 10 anos e a inclinação. A curva nominal combina expectativas de juros e inflação com prêmios de prazo e risco.",
      `${direction} A inclinação descreve a forma da curva; sozinha, não identifica qual componente causou o movimento.`);
  } else if (kind === "real") {
    setGuide(container,
      "Pergunta: quanto de juro real o mercado exige em diferentes horizontes?",
      "A curva real vem dos títulos indexados ao IPCA e mostra a remuneração real zero-cupom exigida por prazo.",
      `${direction} Compare esta curva com a nominal e com a inflação implícita para separar as dimensões da precificação.`);
  } else {
    setGuide(container,
      "Pergunta: qual inflação de equilíbrio iguala títulos nominais e indexados ao IPCA?",
      "A inflação implícita é uma taxa de equilíbrio extraída das duas curvas, não uma pesquisa de expectativas.",
      `${direction} O nível contém prêmio de inflação e diferenças de liquidez, portanto não deve ser tratado como previsão pura do IPCA.`);
  }
}

export function renderYieldCurveUnavailable(message) {
  const panel = document.querySelector("#yield-curve-unavailable");
  const content = document.querySelector("#yield-curve-content");
  panel.hidden = false; panel.textContent = message; content.hidden = true;
  document.querySelector("#yield-curve-date").textContent = "Dados ainda não carregados";
}

export function renderYieldCurve(payload, overview = null) {
  const hasEttj = payload?.market?.ettj?.status === "available" && payload.market.ettj.latest;
  const hasDi = payload?.market?.di?.status === "available" && payload.market.di.latest;
  if (!payload || payload.status !== "available" || (!hasEttj && !hasDi)) {
    renderYieldCurveUnavailable("Execute ./scripts/update-market-curves.sh para carregar as curvas de mercado.");
    return;
  }

  const unavailable = document.querySelector("#yield-curve-unavailable");
  const content = document.querySelector("#yield-curve-content"); unavailable.hidden = true; content.hidden = false;
  const familyControls = document.querySelector("#curve-family-controls");
  const kindControls = document.querySelector("#curve-kind-controls");
  const diModeControls = document.querySelector("#curve-di-mode-controls");
  const compareSelect = document.querySelector("#curve-compare");
  const compareWrap = compareSelect.closest(".curve-compare-controls");
  const customDate = document.querySelector("#curve-custom-date");
  const metrics = document.querySelector("#yield-curve-metrics");
  const viewControls = document.querySelector("#curve-view-controls");
  const chart = document.querySelector("#yield-curve-chart");
  const legend = document.querySelector("#yield-curve-legend");
  const note = document.querySelector("#yield-curve-note");
  const table = document.querySelector("#yield-curve-table-body");
  const summary = document.querySelector("#yield-curve-summary");
  const dateLabel = document.querySelector("#yield-curve-date");
  const methodNote = document.querySelector("#yield-curve-method-note");
  const guide = document.querySelector("#yield-curve-guide");
  const familyStatus = document.querySelector("#yield-curve-family-status");
  const headers = [
    document.querySelector("#yield-curve-table-col-1"),
    document.querySelector("#yield-curve-table-col-2"),
    document.querySelector("#yield-curve-table-col-3"),
  ];
  const selicLatest = overview?.series?.selic?.status === "available" ? overview.series.selic.latest : null;

  const availability = { di: Boolean(hasDi), ettj: Boolean(hasEttj) };
  familyControls.querySelectorAll("button[data-curve-family]").forEach((button) => {
    const available = availability[button.dataset.curveFamily];
    button.disabled = false;
    button.setAttribute("aria-disabled", String(!available));
    button.textContent = `${FAMILY_LABELS[button.dataset.curveFamily]}${available ? "" : " · sem dados"}`;
    button.title = available ? "" : "Selecione para ver o motivo da indisponibilidade.";
  });

  let family = hasDi ? "di" : "ettj";
  let kind = "nominal", comparisonKey = "none", view = "levels", diMode = "rates", chartHandle = null;

  const selectFamilyButton = () => familyControls.querySelectorAll("button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.curveFamily === family)));

  const rerender = () => {
    selectFamilyButton();
    const isDi = family === "di";
    const familyAvailable = availability[family];
    kindControls.hidden = isDi;
    diModeControls.hidden = !isDi || !familyAvailable;
    compareWrap.hidden = isDi || !familyAvailable;
    viewControls.hidden = isDi || !familyAvailable;
    customDate.hidden = isDi || !familyAvailable || comparisonKey !== "custom";

    const elements = { metrics, table, legend, note, date: dateLabel, summary, chart, chartHandle, methodNote, guide, familyStatus, headers };
    if (!familyAvailable) {
      const result = renderFamilyUnavailable(payload, family, elements);
      chartHandle = result.chartHandle;
      return;
    }

    if (isDi) {
      const forwardButton = diModeControls.querySelector('[data-di-mode="forwards"]');
      const forwardCount = payload.market?.di?.latest?.forwards?.length ?? 0;
      forwardButton.disabled = forwardCount < 1;
      forwardButton.setAttribute("aria-disabled", String(forwardCount < 1));
      forwardButton.title = forwardCount < 1 ? "São necessários ao menos dois contratos DI1 válidos para calcular forwards." : "";
      if (diMode === "forwards" && forwardCount < 1) diMode = "rates";
      diModeControls.querySelectorAll("button[data-di-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.diMode === diMode)));
      const result = renderDi(payload, diMode, elements, selicLatest);
      chartHandle = result.chartHandle;
      methodNote.textContent = "DI1 B3: taxa de ajuste até cada vencimento. Forwards entre contratos adjacentes isolam trechos futuros em base 252 dias úteis. Ambas as leituras contêm prêmios de mercado.";
      return;
    }

    const contract = familyContract(payload, family);
    if (!contract) return;
    const current = contract.latest;
    const comparison = comparisonKey === "none" ? null
      : comparisonKey === "custom" ? (customDate.value ? nearestSnapshot(contract.snapshots, customDate.value) : null)
      : presetSnapshot(contract, comparisonKey);
    if (contract.availableRange) { customDate.min = contract.availableRange.start; customDate.max = contract.availableRange.end; }
    const copomOption = compareSelect.querySelector('option[value="previous_copom"]');
    copomOption.disabled = contract.presets?.previous_copom?.status !== "available";
    copomOption.textContent = copomOption.disabled ? "Copom anterior — sem histórico comparável" : "Copom anterior";

    const currentPoints = pointsFor(current, kind, family);
    const comparisonPoints = pointsFor(comparison, kind, family);
    updateMetrics(metrics, contract, current, kind);
    updateTermTable(table, current, comparison, kind);
    setTableHeaders(headers, "Prazo", "Atual", comparison ? `Comparação · ${formatDate(comparison.effective_date)}` : "Comparação");
    setEttjGuide(guide, current, kind, family);
    dateLabel.textContent = `ANBIMA · ref. ${formatDate(current.effective_date)}`;
    setFamilyStatus(familyStatus, `ETTJ ANBIMA disponível · ref. ${formatDate(current.effective_date)}.`);
    legend.replaceChildren();
    const currentLegend = document.createElement("span"); currentLegend.innerHTML = '<span class="legend-line legend-series-1" aria-hidden="true"></span>'; currentLegend.append(`Atual · ${formatDate(current.effective_date)}`); legend.append(currentLegend);
    if (comparison) { const item = document.createElement("span"); item.innerHTML = '<span class="legend-line legend-series-2" aria-hidden="true"></span>'; item.append(`Comparação · ${formatDate(comparison.effective_date)}`); legend.append(item); }

    if (comparisonKey === "custom" && customDate.value && comparison) note.textContent = comparison.effective_date === customDate.value ? "A data personalizada coincide com um dia disponível." : `Usado o último dia disponível: ${formatDate(comparison.effective_date)}.`;
    else if (kind === "implicit") note.textContent = "Inflação implícita da ETTJ ANBIMA; contém prêmios e não equivale a expectativa pura de inflação.";
    else note.textContent = "Estrutura a termo zero-cupom da ANBIMA. Compare o nível dos vértices e a inclinação 10a − 2a.";

    chartHandle?.destroy();
    chartHandle = view === "changes" ? renderYieldCurveDeltaChart(chart, { current: currentPoints, comparison: comparisonPoints })
      : renderYieldCurveChart(chart, { current: currentPoints, comparison: comparisonPoints, currentLabel: formatDate(current.effective_date), comparisonLabel: comparison ? formatDate(comparison.effective_date) : "" });
    if (view === "changes" && !comparison) note.textContent = "Selecione uma comparação para visualizar a reprecificação por prazo em pontos-base.";
    summary.textContent = view === "changes" ? `Mudança da ${LABEL_BY_KIND[kind].toLowerCase()} até ${formatDate(current.effective_date)}.` : `${LABEL_BY_KIND[kind]} em ${formatDate(current.effective_date)}, com ${currentPoints.length} pontos.`;
    methodNote.textContent = "ETTJ ANBIMA: curvas zero-cupom prefixada, real IPCA e inflação implícita. Comparações históricas usam vértices constantes de 2, 3, 5, 7 e 10 anos, sem extrapolação.";
  };

  familyControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-curve-family]");
    if (!button) return;
    family = button.dataset.curveFamily;
    comparisonKey = "none";
    compareSelect.value = "none";
    rerender();
  });
  kindControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-curve-kind]"); if (!button) return;
    kind = button.dataset.curveKind;
    kindControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  diModeControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-di-mode]"); if (!button || button.disabled) return;
    diMode = button.dataset.diMode;
    diModeControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  compareSelect.addEventListener("change", () => { comparisonKey = compareSelect.value; rerender(); });
  viewControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-curve-view]"); if (!button) return;
    view = button.dataset.curveView;
    viewControls.querySelectorAll("button").forEach((candidate) => candidate.setAttribute("aria-pressed", String(candidate === button)));
    rerender();
  });
  customDate.addEventListener("change", rerender);
  let resizeTimer = null; window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(rerender, 120); });
  rerender();
}
