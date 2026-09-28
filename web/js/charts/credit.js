import { formatDate, formatRate } from "../format.js";

const NS = "http://www.w3.org/2000/svg";

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

function parseDate(value) {
  return new Date(`${value}T00:00:00Z`).getTime();
}

function nearestObservation(observations, target) {
  if (!observations.length) return null;
  let low = 0;
  let high = observations.length - 1;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (parseDate(observations[mid].date) < target) low = mid + 1;
    else high = mid;
  }
  if (low === 0) return observations[0];
  const before = observations[low - 1];
  const after = observations[low];
  return Math.abs(parseDate(before.date) - target) <= Math.abs(parseDate(after.date) - target)
    ? before
    : after;
}

function linePath(observations, x, y) {
  return observations.map((item, index) => {
    const command = index === 0 ? "M" : "L";
    return `${command}${x(parseDate(item.date)).toFixed(2)},${y(Number(item.value)).toFixed(2)}`;
  }).join(" ");
}

export function renderCreditChart(container, {
  primary = [],
  secondary = [],
  primaryLabel = "Livre",
  secondaryLabel = "Direcionado",
  valueFormatter = formatRate,
}) {
  container.replaceChildren();
  const all = [...primary, ...secondary];
  if (!all.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Nenhuma observação disponível para o período selecionado.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 330;
  const margin = { top: 18, right: 18, bottom: 36, left: 56 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const timestamps = all.map((item) => parseDate(item.date));
  const values = all.map((item) => Number(item.value));
  const xMin = Math.min(...timestamps);
  const xMaxRaw = Math.max(...timestamps);
  const xMax = xMaxRaw === xMin ? xMin + 86400000 : xMaxRaw;
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.12, 0.25);
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
  svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: "axis-line" }));
  for (let index = 0; index <= 4; index += 1) {
    const timestamp = xMin + ((xMax - xMin) * index) / 4;
    const label = svgElement("text", { x: x(timestamp), y: height - 12, "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle" });
    label.textContent = formatDate(new Date(timestamp).toISOString().slice(0, 10));
    svg.append(label);
  }

  if (primary.length) svg.append(svgElement("path", { d: linePath(primary, x, y), class: "series-line credit-primary-line" }));
  if (secondary.length) svg.append(svgElement("path", { d: linePath(secondary, x, y), class: "series-line credit-secondary-line" }));

  const hoverLine = svgElement("line", { class: "hover-line", y1: margin.top, y2: height - margin.bottom, visibility: "hidden" });
  const primaryDot = svgElement("circle", { class: "hover-dot credit-primary-dot", r: 4, visibility: "hidden" });
  const secondaryDot = svgElement("circle", { class: "hover-dot credit-secondary-dot", r: 4, visibility: "hidden" });
  const tooltipGroup = svgElement("g", { visibility: "hidden" });
  const tooltipRect = svgElement("rect", { class: "tooltip-box", rx: 6, width: 190, height: 68 });
  const tooltipDate = svgElement("text", { class: "tooltip-title" });
  const tooltipPrimary = svgElement("text");
  const tooltipSecondary = svgElement("text");
  tooltipGroup.append(tooltipRect, tooltipDate, tooltipPrimary, tooltipSecondary);
  svg.append(hoverLine, primaryDot, secondaryDot, tooltipGroup);

  const pointerHandler = (event) => {
    const rect = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * width;
    const boundedX = Math.max(margin.left, Math.min(width - margin.right, pointerX));
    const targetTime = xMin + ((boundedX - margin.left) / plotWidth) * (xMax - xMin);
    const primaryItem = nearestObservation(primary, targetTime);
    const secondaryItem = nearestObservation(secondary, targetTime);
    const anchor = primaryItem ?? secondaryItem;
    if (!anchor) return;
    const xx = x(parseDate(anchor.date));
    hoverLine.setAttribute("x1", xx);
    hoverLine.setAttribute("x2", xx);
    hoverLine.setAttribute("visibility", "visible");
    if (primaryItem) {
      primaryDot.setAttribute("cx", x(parseDate(primaryItem.date)));
      primaryDot.setAttribute("cy", y(Number(primaryItem.value)));
      primaryDot.setAttribute("visibility", "visible");
    }
    if (secondaryItem) {
      secondaryDot.setAttribute("cx", x(parseDate(secondaryItem.date)));
      secondaryDot.setAttribute("cy", y(Number(secondaryItem.value)));
      secondaryDot.setAttribute("visibility", "visible");
    }
    const tooltipX = xx > width - 210 ? xx - 198 : xx + 8;
    const tooltipY = Math.max(4, y(Number(anchor.value)) - 74);
    tooltipGroup.setAttribute("transform", `translate(${tooltipX}, ${tooltipY})`);
    tooltipGroup.setAttribute("visibility", "visible");
    tooltipDate.setAttribute("x", 9);
    tooltipDate.setAttribute("y", 18);
    tooltipDate.textContent = formatDate(anchor.date);
    tooltipPrimary.setAttribute("x", 9);
    tooltipPrimary.setAttribute("y", 39);
    tooltipPrimary.textContent = primaryItem ? `${primaryLabel}: ${valueFormatter(Number(primaryItem.value))}` : `${primaryLabel}: —`;
    tooltipSecondary.setAttribute("x", 9);
    tooltipSecondary.setAttribute("y", 58);
    tooltipSecondary.textContent = secondaryItem ? `${secondaryLabel}: ${valueFormatter(Number(secondaryItem.value))}` : `${secondaryLabel}: —`;
  };
  const leaveHandler = () => {
    hoverLine.setAttribute("visibility", "hidden");
    primaryDot.setAttribute("visibility", "hidden");
    secondaryDot.setAttribute("visibility", "hidden");
    tooltipGroup.setAttribute("visibility", "hidden");
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
