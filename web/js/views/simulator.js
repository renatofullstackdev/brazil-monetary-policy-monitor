import { formatPoints, formatRate } from "../format.js";
import { inertialTaylor, prospectiveTaylor } from "../models/taylor.js";

const CONTROL_DEFINITIONS = [
  { key: "expected_inflation", property: "expectedInflation", label: "Inflação esperada", description: "Inflação prospectiva usada pela regra.", min: -5, max: 30, step: 0.1 },
  { key: "inflation_target", property: "inflationTarget", label: "Meta de inflação", description: "Referência para o desvio da inflação esperada.", min: 0, max: 15, step: 0.1 },
  { key: "neutral_real_rate", property: "neutralRealRate", label: "Taxa real neutra (r*)", description: "Estimativa da taxa real compatível com equilíbrio macroeconômico.", min: -10, max: 20, step: 0.1 },
  { key: "output_gap", property: "outputGap", label: "Hiato do produto", description: "Desvio estimado da atividade em relação ao potencial.", min: -20, max: 20, step: 0.1 },
];

const ADVANCED_DEFINITIONS = [
  { key: "alpha", label: "α · resposta à inflação", min: 0, max: 3, step: 0.05, value: 0.5, help: "Peso aplicado ao desvio da inflação em relação à meta." },
  { key: "beta", label: "β · resposta ao hiato", min: 0, max: 3, step: 0.05, value: 0.5, help: "Peso aplicado ao hiato do produto." },
  { key: "rho", label: "ρ · inércia", min: 0, max: 1, step: 0.05, value: 0, help: "0 = sem ajuste parcial. Acima de 0 combina iₜ₋₁ com a Taylor testada." },
  { key: "previous_policy_rate", label: "Selic anterior (iₜ₋₁)", min: 0, max: 50, step: 0.05, value: null, help: "Taxa de partida do ajuste parcial. Quando possível, o painel sugere a última meta Selic distinta anterior à atual." },
];

function publishedValue(series) {
  if (series?.status !== "available" || !series.latest) return null;
  const value = Number(series.latest.value);
  return Number.isFinite(value) ? value : null;
}

function createControl(definition, series) {
  const published = publishedValue(series);
  const wrapper = document.createElement("div");
  wrapper.className = "sim-control";
  wrapper.dataset.simKey = definition.key;
  const heading = document.createElement("div");
  heading.className = "sim-control-heading";
  const label = document.createElement("label");
  label.htmlFor = `sim-${definition.key}-number`;
  label.textContent = definition.label;
  const publishedLabel = document.createElement("span");
  publishedLabel.className = "sim-published-value";
  publishedLabel.textContent = published === null ? "Base: indisponível" : `Base: ${formatRate(published)}`;
  heading.append(label, publishedLabel);
  const description = document.createElement("p");
  description.className = "sim-control-description";
  description.textContent = definition.description;
  const controls = document.createElement("div");
  controls.className = "sim-control-inputs";
  const range = document.createElement("input");
  range.type = "range";
  range.id = `sim-${definition.key}-range`;
  range.min = String(definition.min);
  range.max = String(definition.max);
  range.step = String(definition.step);
  range.setAttribute("aria-label", `${definition.label} — controle deslizante`);
  const number = document.createElement("input");
  number.type = "number";
  number.id = `sim-${definition.key}-number`;
  number.min = String(definition.min);
  number.max = String(definition.max);
  number.step = String(definition.step);
  number.inputMode = "decimal";
  number.placeholder = "Informe";
  number.setAttribute("aria-describedby", `sim-${definition.key}-help`);
  if (published === null) {
    range.disabled = true;
    range.value = "0";
    number.value = "";
  } else {
    range.value = String(Math.min(definition.max, Math.max(definition.min, published)));
    number.value = String(published);
  }
  const suffix = document.createElement("span");
  suffix.className = "sim-input-unit";
  suffix.textContent = "%";
  controls.append(range, number, suffix);
  const help = document.createElement("p");
  help.id = `sim-${definition.key}-help`;
  help.className = "sim-control-help";
  help.textContent = `Intervalo: ${definition.min}% a ${definition.max}%.`;
  wrapper.append(heading, description, controls, help);
  return { wrapper, range, number, published };
}

function createAdvancedControls(container, defaults = {}) {
  const inputs = new Map();
  const fragment = document.createDocumentFragment();
  for (const definition of ADVANCED_DEFINITIONS) {
    const label = document.createElement("label");
    label.className = "advanced-control";
    const caption = document.createElement("span");
    caption.textContent = definition.label;
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(definition.min);
    input.max = String(definition.max);
    input.step = String(definition.step);
    const initialValue = Object.hasOwn(defaults, definition.key) ? defaults[definition.key] : definition.value;
    input.value = initialValue === null || initialValue === undefined ? "" : String(initialValue);
    input.dataset.advancedKey = definition.key;
    const help = document.createElement("small");
    help.textContent = definition.help;
    label.append(caption, input, help);
    fragment.append(label);
    inputs.set(definition.key, { definition, input });
  }
  container.replaceChildren(fragment);
  return inputs;
}

function previousDistinctPolicyRate(series) {
  if (series?.status !== "available" || !Array.isArray(series.observations)) return null;
  const current = publishedValue(series);
  if (current === null) return null;
  for (let index = series.observations.length - 2; index >= 0; index -= 1) {
    const value = Number(series.observations[index]?.value);
    if (Number.isFinite(value) && Math.abs(value - current) > 1e-12) return value;
  }
  return null;
}

function numericValue(input) {
  if (input.value.trim() === "") return null;
  const value = Number(input.value);
  return Number.isFinite(value) ? value : null;
}

function setText(selector, text) {
  const element = document.querySelector(selector);
  if (element) element.textContent = text;
}

function renderDecomposition(result) {
  const values = result ? {
    neutral: result.decomposition.neutralRealRate,
    inflation: result.decomposition.inflation,
    inflation_gap: result.decomposition.inflationGapResponse,
    output_gap: result.decomposition.outputGapResponse,
    total: result.nominalRate,
  } : {};
  document.querySelectorAll("[data-decomposition]").forEach((row) => {
    const value = values[row.dataset.decomposition];
    row.querySelector(".decomposition-value").textContent = Number.isFinite(value) ? formatPoints(value) : "—";
  });
}

function validateControl(definition, input) {
  if (input.value.trim() === "") return null;
  const value = Number(input.value);
  if (!Number.isFinite(value)) return `${definition.label}: informe um número válido.`;
  if (value < definition.min || value > definition.max) return `${definition.label}: use um valor entre ${definition.min} e ${definition.max}.`;
  return null;
}

function advancedValues(advanced) {
  const values = {};
  const errors = [];
  for (const [key, control] of advanced) {
    const error = validateControl(control.definition, control.input);
    control.input.setAttribute("aria-invalid", String(Boolean(error)));
    if (error) errors.push(error);
    values[key] = numericValue(control.input);
  }
  return { values, errors };
}

function centeredValues(value, step) {
  return [-2, -1, 0, 1, 2].map((offset) => Number((value + offset * step).toFixed(2)));
}

function renderSensitivity(container, parameters, alpha, beta) {
  if (!container || Object.values(parameters).some((value) => value === null)) {
    container?.replaceChildren();
    return;
  }
  const inflations = centeredValues(parameters.expectedInflation, 0.5);
  const gaps = centeredValues(parameters.outputGap, 1);
  const table = document.createElement("table");
  table.className = "sensitivity-table";
  const caption = document.createElement("caption");
  caption.textContent = "Taylor resultante por inflação esperada e hiato do produto";
  const thead = document.createElement("thead");
  const head = document.createElement("tr");
  const corner = document.createElement("th");
  corner.scope = "col";
  corner.textContent = "Inflação ↓ / hiato →";
  head.append(corner, ...gaps.map((gap) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = `${gap.toFixed(1)}%`;
    return th;
  }));
  thead.append(head);
  const tbody = document.createElement("tbody");
  inflations.forEach((inflation, rowIndex) => {
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = `${inflation.toFixed(1)}%`;
    row.append(th);
    gaps.forEach((gap, columnIndex) => {
      const td = document.createElement("td");
      const result = prospectiveTaylor({
        ...parameters,
        expectedInflation: inflation,
        outputGap: gap,
        inflationCoefficient: alpha,
        outputGapCoefficient: beta,
      });
      td.textContent = formatRate(result.nominalRate);
      if (rowIndex === 2 && columnIndex === 2) {
        td.className = "sensitivity-current";
        td.title = "Cenário testado";
      }
      row.append(td);
    });
    tbody.append(row);
  });
  table.append(caption, thead, tbody);
  container.replaceChildren(table);
}

export function initializeSimulator(payload) {
  const container = document.querySelector("#simulator-controls");
  const advancedContainer = document.querySelector("#simulator-advanced-controls");
  const sensitivityContainer = document.querySelector("#simulator-sensitivity");
  if (!container || !advancedContainer) return;

  const controls = new Map();
  const nodes = CONTROL_DEFINITIONS.map((definition) => {
    const control = createControl(definition, payload.series[definition.key]);
    controls.set(definition.key, { definition, ...control });
    return control.wrapper;
  });
  container.replaceChildren(...nodes);
  const previousPolicyRate = previousDistinctPolicyRate(payload.series.selic);
  const advancedDefaults = { previous_policy_rate: previousPolicyRate };
  const advanced = createAdvancedControls(advancedContainer, advancedDefaults);

  const officialTaylor = publishedValue(payload.series.taylor_prospective);
  const selic = publishedValue(payload.series.selic);
  setText("#sim-official-taylor", officialTaylor === null ? "—" : formatRate(officialTaylor));
  setText("#sim-current-selic", selic === null ? "—" : formatRate(selic));
  const status = document.querySelector("#simulator-status");
  const reset = document.querySelector("#simulator-reset");

  const update = () => {
    const errors = [];
    const parameters = {};
    for (const control of controls.values()) {
      const error = validateControl(control.definition, control.number);
      control.number.setAttribute("aria-invalid", String(Boolean(error)));
      if (error) errors.push(error);
      parameters[control.definition.property] = numericValue(control.number);
      const value = parameters[control.definition.property];
      control.range.disabled = value === null || Boolean(error);
      if (!control.range.disabled) control.range.value = String(value);
    }
    const advancedResult = advancedValues(advanced);
    errors.push(...advancedResult.errors);
    const { alpha, beta, rho, previous_policy_rate: previousRate } = advancedResult.values;
    const inertialReady = rho === 0 || previousRate !== null;
    const complete = Object.values(parameters).every((value) => value !== null)
      && [alpha, beta, rho].every((value) => value !== null)
      && inertialReady
      && errors.length === 0;
    if (!complete) {
      setText("#sim-taylor", "—");
      setText("#sim-vs-official", "—");
      setText("#sim-selic-gap", "—");
      setText("#sim-inertial-taylor", "—");
      renderDecomposition(null);
      sensitivityContainer.replaceChildren();
      status.textContent = errors.length
        ? errors[0]
        : rho > 0 && previousRate === null
          ? "Informe a Selic anterior (iₜ₋₁) para calcular o ajuste parcial."
          : "Informe os quatro parâmetros para calcular a Taylor testada.";
      status.classList.toggle("error-text", errors.length > 0);
      return;
    }

    const result = prospectiveTaylor({
      ...parameters,
      inflationCoefficient: alpha,
      outputGapCoefficient: beta,
    });
    setText("#sim-taylor", formatRate(result.nominalRate));
    setText("#sim-vs-official", officialTaylor === null ? "—" : formatPoints(result.nominalRate - officialTaylor));
    setText("#sim-selic-gap", selic === null ? "—" : formatPoints(selic - result.nominalRate));
    renderDecomposition(result);
    renderSensitivity(sensitivityContainer, parameters, alpha, beta);

    const inertialRow = document.querySelector("#sim-inertial-row");
    if (rho > 0 && previousRate !== null) {
      const inertial = inertialTaylor({ previousPolicyRate: previousRate, taylorRate: result.nominalRate, smoothing: rho });
      inertialRow.hidden = false;
      setText("#sim-inertial-taylor", formatRate(inertial.nominalRate));
    } else {
      inertialRow.hidden = true;
    }
    status.classList.remove("error-text");
    const specification = alpha === 0.5 && beta === 0.5
      ? "coeficientes canônicos 0,5/0,5"
      : `α=${alpha.toFixed(2)} e β=${beta.toFixed(2)}`;
    status.textContent = officialTaylor === null
      ? `Simulação local com ${specification}. O cenário-base continuará indisponível até existirem todos os insumos documentados.`
      : `Simulação local com ${specification}; nenhum valor foi persistido.`;
  };

  for (const control of controls.values()) {
    control.number.addEventListener("input", update);
    control.range.addEventListener("input", () => { control.number.value = control.range.value; update(); });
  }
  for (const { input } of advanced.values()) input.addEventListener("input", update);

  reset.addEventListener("click", () => {
    for (const control of controls.values()) {
      if (control.published === null) {
        control.number.value = "";
        control.range.disabled = true;
        control.range.value = "0";
      } else {
        control.number.value = String(control.published);
        control.range.disabled = false;
        control.range.value = String(control.published);
      }
      control.number.setAttribute("aria-invalid", "false");
    }
    for (const [key, { definition, input }] of advanced) {
      const resetValue = Object.hasOwn(advancedDefaults, key) ? advancedDefaults[key] : definition.value;
      input.value = resetValue === null || resetValue === undefined ? "" : String(resetValue);
    }
    update();
  });

  update();
}
