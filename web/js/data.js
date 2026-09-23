export async function loadOverview(url = "./data/overview.json") {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  }
  const payload = await response.json();
  validateOverview(payload);
  return payload;
}

export function validateOverview(payload) {
  if (!payload || typeof payload !== "object") {
    throw new TypeError("Contrato overview inválido: objeto JSON esperado.");
  }
  if (payload.schema_version !== 1 || payload.view !== "overview") {
    throw new Error("Versão do contrato overview não suportada.");
  }
  if (!payload.series || typeof payload.series !== "object") {
    throw new Error("Contrato overview sem coleção de séries.");
  }
}


export async function loadYieldCurve(url = "./data/yield-curve.json") {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || payload.schema_version !== 1 || payload.view !== "yield_curve") {
    throw new Error("Contrato yield_curve não suportado.");
  }
  return payload;
}


export async function loadCreditTransmission(url = "./data/credit-transmission.json") {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || payload.schema_version !== 1 || payload.view !== "credit_transmission") {
    throw new Error("Contrato credit_transmission não suportado.");
  }
  return payload;
}


export async function loadFiscal(url = "./data/fiscal.json") {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${url}: HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || payload.schema_version !== 1 || payload.view !== "fiscal") {
    throw new Error("Contrato fiscal não suportado.");
  }
  return payload;
}
