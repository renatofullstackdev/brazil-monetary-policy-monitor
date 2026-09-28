import { TABLE_PAGE_SIZE } from "./config.js";

export function asOfObservation(observations, date) {
  if (!date || !Array.isArray(observations) || observations.length === 0) return null;
  let candidate = null;
  for (const item of observations) {
    if (!item?.date || item.date > date) continue;
    if (!candidate || item.date > candidate.date) candidate = item;
  }
  return candidate;
}

export function renderPaginatedRows(tbody, rows, { pageSize = TABLE_PAGE_SIZE } = {}) {
  const allRows = Array.from(rows ?? []);
  const panel = tbody.closest(".data-table-panel, .indicator-history-data") ?? tbody.parentElement;
  panel?.querySelector(":scope > .table-pagination")?.remove();

  let visible = Math.min(pageSize, allRows.length);
  const render = () => {
    tbody.replaceChildren(...allRows.slice(0, visible));
    if (!panel) return;
    panel.querySelector(":scope > .table-pagination")?.remove();
    if (allRows.length <= pageSize) return;

    const footer = document.createElement("div");
    footer.className = "table-pagination";
    const status = document.createElement("span");
    status.textContent = `${visible.toLocaleString("pt-BR")} de ${allRows.length.toLocaleString("pt-BR")} observações`;
    footer.append(status);
    if (visible < allRows.length) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button table-more-button";
      button.textContent = "Mostrar mais";
      button.addEventListener("click", () => {
        visible = Math.min(visible + pageSize, allRows.length);
        render();
      });
      footer.append(button);
    }
    panel.append(footer);
  };
  render();
}
