import { formatPoints, formatRate } from "../format.js";
import { prospectiveTaylor } from "../models/taylor.js";

const CONTROL_DEFINITIONS = [
  {
    key: "expected_inflation",
    property: "expectedInflation",
    label: "Inflação esperada",
    description: "Inflação usada pela Taylor prospectiva.",
    min: -5,
    max: 30,
    step: 0.1,
  },
  {
    key: "inflation_target",
    property: "inflationTarget",
    label: "Meta de inflação",
    description: "Meta contra a qual o desvio inflacionário é calculado.",
    min: 0,
    max: 15,
    step: 0.1,
  },
  {
    key: "neutral_real_rate",
    property: "neutralRealRate",
    label: "Taxa real neutra (r*)",
    description: "Estimativa da taxa real compatível com equilíbrio macroeconômico.",
    min: -10,
    max: 20,
    step: 0.1,
  },
  {
    key: "output_gap",
    property: "outputGap",
    label: "Hiato do produto",
    description: "Desvio percentual estimado da atividade em relação ao potencial.",
    min: -20,
    max: 20,
    step: 0.1,
  },
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
  publishedLabel.textContent = published === null
    ? "Publicado: indisponível"
    : `Publicado: ${formatRate(published)}`;

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
  help.textContent = `Intervalo do controle: ${definition.min}% a ${definition.max}%.`;

  wrapper.append(heading, description, controls, help);
  return { wrapper, range, number, published };
}

function numericValue(input) {
  if (input.value.trim() === "") return null;
  const value = Number(input.value);
  return Number.isFinite(value) ? value : null;
}

function setText(selector, text) {
  document.querySelector(selector).textContent = text;
}

function renderDecomposition(result) {
  const rows = document.querySelectorAll("[data-decomposition]");
  const values = result
    ? {
        neutral: result.decomposition.neutralRealRate,
        inflation: result.decomposition.inflation,
        inflation_gap: result.decomposition.inflationGapResponse,
        output_gap: result.decomposition.outputGapResponse,
        total: result.nominalRate,
      }
    : {};

  rows.forEach((row) => {
    const key = row.dataset.decomposition;
    const value = values[key];
    row.querySelector(".decomposition-value").textContent = Number.isFinite(value)
      ? formatPoints(value)
      : "—";
  });
}

function validateControl(definition, input) {
  if (input.value.trim() === "") return null;
  const value = Number(input.value);
  if (!Number.isFinite(value)) return `${definition.label}: informe um número válido.`;
  if (value < definition.min || value > definition.max) {
    return `${definition.label}: use um valor entre ${definition.min}% e ${definition.max}%.`;
  }
  return null;
}

export function initializeSimulator(payload) {
  const container = document.querySelector("#simulator-controls");
  if (!container) return;

  const controls = new Map();
  const nodes = CONTROL_DEFINITIONS.map((definition) => {
    const control = createControl(definition, payload.series[definition.key]);
    controls.set(definition.key, { definition, ...control });
    return control.wrapper;
  });
  container.replaceChildren(...nodes);

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
      if (value === null || error) {
        control.range.disabled = true;
      } else {
        control.range.disabled = false;
        control.range.value = String(value);
      }
    }

    const complete = Object.values(parameters).every((value) => value !== null) && errors.length === 0;
    if (!complete) {
      setText("#sim-taylor", "—");
      setText("#sim-vs-official", "—");
      setText("#sim-selic-gap", "—");
      renderDecomposition(null);
      status.textContent = errors.length
        ? errors[0]
        : "Informe os quatro parâmetros para calcular a Taylor simulada.";
      status.classList.toggle("error-text", errors.length > 0);
      return;
    }

    const result = prospectiveTaylor(parameters);
    setText("#sim-taylor", formatRate(result.nominalRate));
    setText(
      "#sim-vs-official",
      officialTaylor === null ? "—" : formatPoints(result.nominalRate - officialTaylor),
    );
    setText(
      "#sim-selic-gap",
      selic === null ? "—" : formatPoints(selic - result.nominalRate),
    );
    renderDecomposition(result);
    status.classList.remove("error-text");
    status.textContent = officialTaylor === null
      ? "Simulação calculada localmente. A Taylor oficial continuará indisponível até os insumos oficiais serem publicados."
      : "Simulação calculada localmente; nenhum valor foi persistido.";
  };

  for (const control of controls.values()) {
    control.number.addEventListener("input", update);
    control.range.addEventListener("input", () => {
      control.number.value = control.range.value;
      update();
    });
  }

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
    update();
  });

  update();
}
