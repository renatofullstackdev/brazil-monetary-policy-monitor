import { loadOverview } from "./data.js";
import { renderOverview } from "./views/overview.js";
import { initializeSimulator } from "./views/simulator.js";

async function main() {
  try {
    const payload = await loadOverview();
    renderOverview(payload);
    initializeSimulator(payload);
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
