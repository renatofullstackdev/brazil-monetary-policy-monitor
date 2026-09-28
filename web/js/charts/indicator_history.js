import { formatDate } from "../format.js";

const NS = "http://www.w3.org/2000/svg";

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function parseDate(value) {
  return new Date(`${value}T00:00:00Z`).getTime();
}

function nearest(observations, target) {
  if (!observations.length) return null;
  let result = observations[0];
  let distance = Math.abs(parseDate(result.date) - target);
  for (const item of observations.slice(1)) {
    const candidate = Math.abs(parseDate(item.date) - target);
    if (candidate < distance) {
      result = item;
      distance = candidate;
    }
  }
  return result;
}

function linePath(observations, x, y, step) {
  if (!observations.length) return "";
  const first = observations[0];
  let path = `M${x(parseDate(first.date)).toFixed(2)},${y(Number(first.value)).toFixed(2)}`;
  for (const item of observations.slice(1)) {
    const xx = x(parseDate(item.date)).toFixed(2);
    const yy = y(Number(item.value)).toFixed(2);
    path += step ? ` H${xx} V${yy}` : ` L${xx},${yy}`;
  }
  return path;
}

export function renderIndicatorHistoryChart(
  container,
  { observations = [], valueFormatter, step = false, style = "series-1" },
) {
  container.replaceChildren();
  if (!observations.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Nenhuma observação disponível para o período selecionado.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 300;
  const margin = { top: 18, right: 18, bottom: 36, left: 62 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const timestamps = observations.map((item) => parseDate(item.date));
  const values = observations.map((item) => Number(item.value));
  const xMin = Math.min(...timestamps);
  const xMaxRaw = Math.max(...timestamps);
  const xMax = xMaxRaw === xMin ? xMin + 86400000 : xMaxRaw;
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.12, Math.abs(rawMax || 1) * 0.02, 0.1);
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

  for (let index = 0; index <= 4; index += 1) {
    const timestamp = xMin + ((xMax - xMin) * index) / 4;
    const label = svgElement("text", {
      x: x(timestamp),
      y: height - 12,
      "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle",
    });
    label.textContent = formatDate(new Date(timestamp).toISOString().slice(0, 10));
    svg.append(label);
  }

  svg.append(svgElement("path", {
    d: linePath(observations, x, y, step),
    class: `series-line indicator-history-line ${style}`,
  }));

  const hoverLine = svgElement("line", {
    class: "hover-line",
    y1: margin.top,
    y2: height - margin.bottom,
    visibility: "hidden",
  });
  const dot = svgElement("circle", { class: `hover-dot indicator-history-dot ${style}-dot`, r: 4, visibility: "hidden" });
  const tooltip = svgElement("g", { visibility: "hidden" });
  const box = svgElement("rect", { class: "tooltip-box", rx: 6, width: 176, height: 48 });
  const title = svgElement("text", { class: "tooltip-title", x: 9, y: 18 });
  const valueText = svgElement("text", { x: 9, y: 38 });
  tooltip.append(box, title, valueText);
  svg.append(hoverLine, dot, tooltip);

  const pointerHandler = (event) => {
    const rect = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * width;
    const bounded = Math.max(margin.left, Math.min(width - margin.right, pointerX));
    const target = xMin + ((bounded - margin.left) / plotWidth) * (xMax - xMin);
    const item = nearest(observations, target);
    if (!item) return;
    const xx = x(parseDate(item.date));
    const yy = y(Number(item.value));
    hoverLine.setAttribute("x1", xx);
    hoverLine.setAttribute("x2", xx);
    hoverLine.setAttribute("visibility", "visible");
    dot.setAttribute("cx", xx);
    dot.setAttribute("cy", yy);
    dot.setAttribute("visibility", "visible");
    tooltip.setAttribute("transform", `translate(${xx > width - 196 ? xx - 186 : xx + 8}, ${Math.max(4, yy - 56)})`);
    tooltip.setAttribute("visibility", "visible");
    title.textContent = formatDate(item.date);
    valueText.textContent = valueFormatter(Number(item.value));
  };
  const leaveHandler = () => {
    hoverLine.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    tooltip.setAttribute("visibility", "hidden");
  };
  svg.addEventListener("pointermove", pointerHandler);
  svg.addEventListener("pointerleave", leaveHandler);
  container.append(svg);

  return {
    destroy() {
      svg.removeEventListener("pointermove", pointerHandler);
      svg.removeEventListener("pointerleave", leaveHandler);
      svg.remove();
    },
  };
}
