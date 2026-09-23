import { formatDate } from "../format.js";

const NS = "http://www.w3.org/2000/svg";

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

function parseDate(value) {
  return new Date(`${value}T00:00:00Z`).getTime();
}

function linePath(observations, x, y) {
  return observations.map((item, index) => `${index === 0 ? "M" : "L"}${x(parseDate(item.date)).toFixed(2)},${y(Number(item.value)).toFixed(2)}`).join(" ");
}

function nearest(observations, target) {
  if (!observations.length) return null;
  let answer = observations[0];
  let distance = Math.abs(parseDate(answer.date) - target);
  for (const item of observations) {
    const current = Math.abs(parseDate(item.date) - target);
    if (current < distance) { answer = item; distance = current; }
  }
  return answer;
}

export function renderFiscalChart(container, { series, valueFormatter }) {
  container.replaceChildren();
  const populated = series.filter((item) => item.observations.length);
  const all = populated.flatMap((item) => item.observations);
  if (!all.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Nenhuma observação fiscal disponível para o período selecionado.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 330;
  const margin = { top: 18, right: 18, bottom: 36, left: 60 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const times = all.map((item) => parseDate(item.date));
  const values = all.map((item) => Number(item.value));
  const xMin = Math.min(...times);
  const rawXMax = Math.max(...times);
  const xMax = rawXMax === xMin ? xMin + 86400000 : rawXMax;
  const rawMin = Math.min(...values, 0);
  const rawMax = Math.max(...values, 0);
  const padding = Math.max((rawMax - rawMin) * 0.1, 0.5);
  const yMin = rawMin - padding;
  const yMax = rawMax + padding;
  const x = (timestamp) => margin.left + ((timestamp - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin || 1)) * plotHeight;

  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
  for (let index = 0; index <= 4; index += 1) {
    const value = yMin + ((yMax - yMin) * index) / 4;
    const yy = y(value);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: yy, y2: yy, class: "grid-line" }));
    const label = svgElement("text", { x: margin.left - 8, y: yy + 4, "text-anchor": "end" });
    label.textContent = valueFormatter(value);
    svg.append(label);
  }
  if (yMin < 0 && yMax > 0) {
    const yy = y(0);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: yy, y2: yy, class: "axis-line fiscal-zero-line" }));
  }
  for (let index = 0; index <= 4; index += 1) {
    const timestamp = xMin + ((xMax - xMin) * index) / 4;
    const label = svgElement("text", { x: x(timestamp), y: height - 12, "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle" });
    label.textContent = formatDate(new Date(timestamp).toISOString().slice(0, 10));
    svg.append(label);
  }

  populated.forEach((item, index) => {
    svg.append(svgElement("path", { d: linePath(item.observations, x, y), class: `series-line fiscal-series-${index + 1}` }));
  });

  const hoverLine = svgElement("line", { class: "hover-line", y1: margin.top, y2: height - margin.bottom, visibility: "hidden" });
  const tooltip = svgElement("g", { visibility: "hidden" });
  const box = svgElement("rect", { class: "tooltip-box", rx: 6, width: 245, height: 30 + 20 * populated.length });
  tooltip.append(box);
  const title = svgElement("text", { class: "tooltip-title", x: 9, y: 18 });
  tooltip.append(title);
  const valueNodes = populated.map((item, index) => {
    const node = svgElement("text", { x: 9, y: 39 + index * 19 });
    tooltip.append(node);
    return [item, node];
  });
  svg.append(hoverLine, tooltip);

  const pointerHandler = (event) => {
    const rect = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * width;
    const bounded = Math.max(margin.left, Math.min(width - margin.right, pointerX));
    const target = xMin + ((bounded - margin.left) / plotWidth) * (xMax - xMin);
    const anchor = nearest(populated[0].observations, target);
    if (!anchor) return;
    const xx = x(parseDate(anchor.date));
    hoverLine.setAttribute("x1", xx); hoverLine.setAttribute("x2", xx); hoverLine.setAttribute("visibility", "visible");
    const tooltipX = xx > width - 265 ? xx - 255 : xx + 8;
    tooltip.setAttribute("transform", `translate(${tooltipX}, 8)`);
    tooltip.setAttribute("visibility", "visible");
    title.textContent = formatDate(anchor.date);
    valueNodes.forEach(([item, node]) => {
      const observation = nearest(item.observations, parseDate(anchor.date));
      node.textContent = `${item.label}: ${observation ? valueFormatter(Number(observation.value)) : "—"}`;
    });
  };
  const leaveHandler = () => { hoverLine.setAttribute("visibility", "hidden"); tooltip.setAttribute("visibility", "hidden"); };
  svg.addEventListener("pointermove", pointerHandler);
  svg.addEventListener("pointerleave", leaveHandler);
  container.append(svg);
  return { destroy() { svg.removeEventListener("pointermove", pointerHandler); svg.removeEventListener("pointerleave", leaveHandler); svg.remove(); } };
}
