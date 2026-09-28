async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  return response.json();
}

function requireObject(payload, key, contractName) {
  if (!payload?.[key] || typeof payload[key] !== "object" || Array.isArray(payload[key])) {
    throw new Error(`Contrato ${contractName} sem ${key} válido.`);
  }
}

function requireArray(payload, key, contractName) {
  if (!Array.isArray(payload?.[key])) {
    throw new Error(`Contrato ${contractName} sem ${key} válido.`);
  }
}

function validateView(payload, expectedView, contractName = expectedView) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new TypeError(`Contrato ${contractName} inválido: objeto JSON esperado.`);
  }
  if (payload.view !== expectedView) {
    throw new Error(`Contrato ${contractName} incompatível: view esperada ${expectedView}.`);
  }
}

export async function loadOverview(url = "./data/overview.json") {
  const payload = await fetchJson(url);
  validateOverview(payload);
  return payload;
}

export function validateOverview(payload) {
  validateView(payload, "overview", "overview");
  requireObject(payload, "series", "overview");
  requireObject(payload, "availability", "overview");
}

export async function loadYieldCurve(url = "./data/yield-curve.json") {
  const payload = await fetchJson(url);
  validateView(payload, "yield_curve", "yield_curve");
  requireObject(payload, "market", "yield_curve");
  return payload;
}

export async function loadCreditTransmission(url = "./data/credit-transmission.json") {
  const payload = await fetchJson(url);
  validateView(payload, "credit_transmission", "credit_transmission");
  requireObject(payload, "groups", "credit_transmission");
  return payload;
}

export async function loadFiscal(url = "./data/fiscal.json") {
  const payload = await fetchJson(url);
  validateView(payload, "fiscal", "fiscal");
  requireArray(payload, "flows", "fiscal");
  requireArray(payload, "debt_positions", "fiscal");
  requireObject(payload, "dpf_profile", "fiscal");
  return payload;
}

export async function loadExternalSector(url = "./data/external-sector.json") {
  const payload = await fetchJson(url);
  validateView(payload, "external_sector", "external_sector");
  requireObject(payload, "groups", "external_sector");
  return payload;
}

export async function loadUSBenchmark(url = "./data/us-benchmark.json") {
  const payload = await fetchJson(url);
  validateView(payload, "us_benchmark", "us_benchmark");
  requireObject(payload, "groups", "us_benchmark");
  return payload;
}

export async function loadCopomEvents(url = "./data/copom-events.json") {
  const payload = await fetchJson(url);
  validateView(payload, "copom_events", "copom_events");
  requireArray(payload, "events", "copom_events");
  requireArray(payload, "decision_markers", "copom_events");
  return payload;
}
