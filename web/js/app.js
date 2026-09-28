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

async function main() {
  initializeIndicatorDetails();
  const vintageIndex = await loadVintageIndex();
  const knowledge = resolveKnowledgeSelection(vintageIndex);
  initializeVintageControls(knowledge, vintageIndex);
  try {
    const datasets = {};
    const payload = await loadOverview(knowledge.urls.overview);
    datasets.overview = payload;

    let copom = null;
    try {
      copom = await loadCopomEvents(knowledge.urls.copom);
      datasets.copom = copom;
      renderCopomEvents(copom);
    } catch (copomError) {
      renderCopomUnavailable(`Eventos Copom indisponíveis. Execute ./scripts/update-copom.sh. Detalhe: ${copomError.message}`);
    }
    renderOverview(payload, copom);
    initializeSimulator(payload);

    try {
      datasets.curve = await loadYieldCurve(knowledge.urls.curve);
      renderYieldCurve(datasets.curve, payload);
    } catch (curveError) {
      renderYieldCurveUnavailable(`Curvas de mercado indisponíveis. Execute ./scripts/update-market-curves.sh. Detalhe: ${curveError.message}`);
    }
    try {
      datasets.credit = await loadCreditTransmission(knowledge.urls.credit);
      renderCreditTransmission(datasets.credit);
    } catch (creditError) {
      renderCreditUnavailable(`Crédito indisponível. Execute ./scripts/update-credit.sh. Detalhe: ${creditError.message}`);
    }
    try {
      datasets.fiscal = await loadFiscal(knowledge.urls.fiscal);
      renderFiscal(datasets.fiscal);
    } catch (fiscalError) {
      renderFiscalUnavailable(`Fiscal indisponível. Execute ./scripts/update-fiscal.sh. Detalhe: ${fiscalError.message}`);
    }
    try {
      datasets.external = await loadExternalSector(knowledge.urls.external);
      renderExternal(datasets.external);
    } catch (externalError) {
      renderExternalUnavailable(`Setor externo indisponível. Execute ./scripts/update-external.sh. Detalhe: ${externalError.message}`);
    }
    try {
      datasets.us = await loadUSBenchmark(knowledge.urls.us);
      renderUS(datasets.us);
    } catch (usError) {
      renderUSUnavailable(`EUA indisponível. Execute ./scripts/update-us.sh. Detalhe: ${usError.message}`);
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
  } catch (error) {
    const panel = document.querySelector("#load-error");
    const dot = document.querySelector("#data-status");
    dot.classList.add("error");
    document.querySelector("#generated-at").textContent = "Dados indisponíveis";
    panel.hidden = false;
    panel.textContent = window.location.protocol === "file:"
      ? "Abra a interface por HTTP. Execute ./scripts/serve-web.sh e acesse http://127.0.0.1:8000/."
      : `Não foi possível carregar o contrato de dados. Execute ./scripts/publish-overview.sh. Detalhe: ${error.message}`;
  }
}

main();
