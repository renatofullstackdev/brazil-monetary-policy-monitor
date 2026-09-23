import { loadCreditTransmission, loadFiscal, loadOverview, loadYieldCurve } from "./data.js";
import { renderOverview } from "./views/overview.js";
import { initializeSimulator } from "./views/simulator.js";
import { renderYieldCurve, renderYieldCurveUnavailable } from "./views/yield_curve.js";
import { renderCreditTransmission, renderCreditUnavailable } from "./views/credit.js";
import { renderFiscal, renderFiscalUnavailable } from "./views/fiscal.js";

async function main() {
  try {
    const payload = await loadOverview();
    renderOverview(payload);
    initializeSimulator(payload);
    try {
      const credit = await loadCreditTransmission();
      renderCreditTransmission(credit);
    } catch (creditError) {
      renderCreditUnavailable(`Crédito indisponível. Execute ./scripts/update-credit.sh. Detalhe: ${creditError.message}`);
    }
    try {
      const fiscal = await loadFiscal();
      renderFiscal(fiscal);
    } catch (fiscalError) {
      renderFiscalUnavailable(`Fiscal indisponível. Execute ./scripts/update-fiscal.sh. Detalhe: ${fiscalError.message}`);
    }
    try {
      const curve = await loadYieldCurve();
      renderYieldCurve(curve);
    } catch (curveError) {
      renderYieldCurveUnavailable(`Curva de juros indisponível. Execute ./scripts/update-yield-curve.sh. Detalhe: ${curveError.message}`);
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
