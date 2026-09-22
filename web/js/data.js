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
