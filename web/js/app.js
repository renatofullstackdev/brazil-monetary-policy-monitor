import { loadCopomEvents, loadCreditTransmission, loadExternalSector, loadFiscal, loadOverview, loadUSBenchmark, loadYieldCurve } from "./data.js";
import { renderOverview } from "./views/overview.js";
import { initializeSimulator } from "./views/simulator.js";
import { renderYieldCurve, renderYieldCurveUnavailable } from "./views/yield_curve.js";
import { renderCreditTransmission, renderCreditUnavailable } from "./views/credit.js";
import { renderFiscal, renderFiscalUnavailable } from "./views/fiscal.js";
import { renderExternal, renderExternalUnavailable } from "./views/external.js";
import { renderUS, renderUSUnavailable } from "./views/us.js";
import { renderCopomEvents, renderCopomUnavailable } from "./views/copom.js";
import { initializeRelationshipExplorer } from "./views/explorer.js";
import { initializeIndicatorDetails } from "./indicator_details.js";
import { initializeVintageControls, loadVintageIndex, resolveKnowledgeSelection } from "./vintage.js";

function errorMessage(result) {
  return result?.status === "rejected" ? result.reason?.message ?? String(result.reason) : "erro desconhecido";
}

function renderOverviewUnavailable(result) {
  const panel = document.querySelector("#load-error");
  const dot = document.querySelector("#data-status");
  dot?.classList.add("error");
  const generated = document.querySelector("#generated-at");
  if (generated) generated.textContent = "Visão geral indisponível";
  if (!panel) return;
  panel.hidden = false;
  panel.textContent = window.location.protocol === "file:"
    ? "Abra a interface por HTTP. Execute ./scripts/serve-web.sh e acesse http://127.0.0.1:8000/."
    : `A visão geral não pôde ser carregada. Execute ./scripts/publish-overview.sh. Detalhe: ${errorMessage(result)}`;
}

async function main() {
  initializeIndicatorDetails();
  const vintageIndex = await loadVintageIndex();
  const knowledge = resolveKnowledgeSelection(vintageIndex);
  initializeVintageControls(knowledge, vintageIndex);

  const requests = {
    overview: loadOverview(knowledge.urls.overview),
    copom: loadCopomEvents(knowledge.urls.copom),
    curve: loadYieldCurve(knowledge.urls.curve),
    credit: loadCreditTransmission(knowledge.urls.credit),
    fiscal: loadFiscal(knowledge.urls.fiscal),
    external: loadExternalSector(knowledge.urls.external),
    us: loadUSBenchmark(knowledge.urls.us),
  };
  const keys = Object.keys(requests);
  const settled = await Promise.allSettled(Object.values(requests));
  const results = Object.fromEntries(keys.map((key, index) => [key, settled[index]]));
  const datasets = Object.fromEntries(
    keys
      .filter((key) => results[key].status === "fulfilled")
      .map((key) => [key, results[key].value]),
  );

  const copom = datasets.copom ?? null;
  if (copom) {
    renderCopomEvents(copom);
  } else {
    renderCopomUnavailable(`Eventos Copom indisponíveis. Execute ./scripts/update-copom.sh. Detalhe: ${errorMessage(results.copom)}`);
  }

  if (datasets.overview) {
    renderOverview(datasets.overview, copom);
    initializeSimulator(datasets.overview);
  } else {
    renderOverviewUnavailable(results.overview);
  }

  if (datasets.curve) {
    renderYieldCurve(datasets.curve, datasets.overview ?? null);
  } else {
    renderYieldCurveUnavailable(`Curvas de mercado indisponíveis. Execute ./scripts/update-market-curves.sh. Detalhe: ${errorMessage(results.curve)}`);
  }
  if (datasets.credit) {
    renderCreditTransmission(datasets.credit);
  } else {
    renderCreditUnavailable(`Crédito indisponível. Execute ./scripts/update-credit.sh. Detalhe: ${errorMessage(results.credit)}`);
  }
  if (datasets.fiscal) {
    renderFiscal(datasets.fiscal);
  } else {
    renderFiscalUnavailable(`Fiscal indisponível. Execute ./scripts/update-fiscal.sh. Detalhe: ${errorMessage(results.fiscal)}`);
  }
  if (datasets.external) {
    renderExternal(datasets.external);
  } else {
    renderExternalUnavailable(`Setor externo indisponível. Execute ./scripts/update-external.sh. Detalhe: ${errorMessage(results.external)}`);
  }
  if (datasets.us) {
    renderUS(datasets.us);
  } else {
    renderUSUnavailable(`EUA indisponível. Execute ./scripts/update-us.sh. Detalhe: ${errorMessage(results.us)}`);
  }

  try {
    initializeRelationshipExplorer(datasets);
  } catch (explorerError) {
    const unavailable = document.querySelector("#explorer-unavailable");
    const content = document.querySelector("#explorer-content");
    if (content) content.hidden = true;
    if (unavailable) {
      unavailable.hidden = false;
      unavailable.textContent = `Explorador indisponível neste recorte. Detalhe: ${explorerError.message}`;
    }
  }
}

main();
