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

function subtractYears(timestamp, years) {
  const date = new Date(timestamp);
  date.setUTCFullYear(date.getUTCFullYear() - years);
  return date.getTime();
}

export function filterByRange(observations, range, anchorDate = null) {
  if (!observations?.length || range === "all") return observations ?? [];
  const years = Number(range);
  const anchor = anchorDate ? parseDate(anchorDate) : parseDate(observations.at(-1).date);
  const cutoff = subtractYears(anchor, years);
  return observations.filter((item) => parseDate(item.date) >= cutoff && parseDate(item.date) <= anchor);
}

function compressSteps(observations) {
  if (observations.length <= 2) return observations;
  const points = [observations[0]];
  for (let index = 1; index < observations.length; index += 1) {
    const current = observations[index];
    const previous = observations[index - 1];
    if (current.value !== previous.value) points.push(current);
  }
  const last = observations.at(-1);
  if (points.at(-1).date !== last.date) points.push(last);
  return points;
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

function stepPath(observations, x, y) {
  if (!observations.length) return "";
  const points = compressSteps(observations);
  const first = points[0];
  let d = `M${x(parseDate(first.date)).toFixed(2)},${y(Number(first.value)).toFixed(2)} `;
  for (const item of points.slice(1)) {
    d += `H${x(parseDate(item.date)).toFixed(2)} V${y(Number(item.value)).toFixed(2)} `;
  }
  return d.trim();
}

function linePath(observations, x, y) {
  return observations.map((item, index) => {
    const command = index === 0 ? "M" : "L";
    return `${command}${x(parseDate(item.date)).toFixed(2)},${y(Number(item.value)).toFixed(2)}`;
  }).join(" ");
}

export function renderHistoryChart(container, { selic = [], taylor = [] }) {
  container.replaceChildren();
  const all = [...selic, ...taylor];
  if (!all.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Nenhuma observação disponível para o período selecionado.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 330;
  const margin = { top: 18, right: 18, bottom: 36, left: 52 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;

  const timestamps = all.map((item) => parseDate(item.date));
  const values = all.map((item) => Number(item.value));
  const xMin = Math.min(...timestamps);
  const xMaxRaw = Math.max(...timestamps);
  const xMax = xMaxRaw === xMin ? xMin + 86400000 : xMaxRaw;
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.12, 0.5);
  const yMin = Math.max(0, rawMin - padding);
  const yMax = rawMax + padding;

  const x = (timestamp) => margin.left + ((timestamp - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin)) * plotHeight;

  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });

  for (let index = 0; index <= 4; index += 1) {
    const value = yMin + ((yMax - yMin) * index) / 4;
    const yy = y(value);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: yy, y2: yy, class: "grid-line" }));
    const label = svgElement("text", { x: margin.left - 8, y: yy + 4, "text-anchor": "end" });
    label.textContent = `${value.toFixed(1)}%`;
    svg.append(label);
  }

  svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: "axis-line" }));

  for (let index = 0; index <= 4; index += 1) {
    const timestamp = xMin + ((xMax - xMin) * index) / 4;
    const label = svgElement("text", { x: x(timestamp), y: height - 12, "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle" });
    label.textContent = formatDate(new Date(timestamp).toISOString().slice(0, 10));
    svg.append(label);
  }

  if (selic.length) {
    svg.append(svgElement("path", { d: stepPath(selic, x, y), class: "series-line selic-line" }));
  }
  if (taylor.length) {
    svg.append(svgElement("path", { d: linePath(taylor, x, y), class: "series-line taylor-line" }));
  }

  const hoverLine = svgElement("line", { class: "hover-line", y1: margin.top, y2: height - margin.bottom, visibility: "hidden" });
  const selicDot = svgElement("circle", { class: "hover-dot selic-dot", r: 4, visibility: "hidden" });
  const taylorDot = svgElement("circle", { class: "hover-dot taylor-dot", r: 4, visibility: "hidden" });
  const tooltipGroup = svgElement("g", { visibility: "hidden" });
  const tooltipHeight = taylor.length ? 66 : 48;
  const tooltipRect = svgElement("rect", { class: "tooltip-box", rx: 6, width: 154, height: tooltipHeight });
  const tooltipDate = svgElement("text", { class: "tooltip-title" });
  const tooltipSelic = svgElement("text");
  const tooltipTaylor = svgElement("text");
  tooltipGroup.append(tooltipRect, tooltipDate, tooltipSelic, tooltipTaylor);
  svg.append(hoverLine, selicDot, taylorDot, tooltipGroup);

  const pointerHandler = (event) => {
    const rect = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * width;
    const boundedX = Math.max(margin.left, Math.min(width - margin.right, pointerX));
    const targetTime = xMin + ((boundedX - margin.left) / plotWidth) * (xMax - xMin);
    const selicItem = nearestObservation(selic, targetTime);
    const taylorItem = nearestObservation(taylor, targetTime);
    const anchorItem = selicItem ?? taylorItem;
    const xx = x(parseDate(anchorItem.date));

    hoverLine.setAttribute("x1", xx);
    hoverLine.setAttribute("x2", xx);
    hoverLine.setAttribute("visibility", "visible");

    if (selicItem) {
      selicDot.setAttribute("cx", x(parseDate(selicItem.date)));
      selicDot.setAttribute("cy", y(Number(selicItem.value)));
      selicDot.setAttribute("visibility", "visible");
    }
    if (taylorItem) {
      taylorDot.setAttribute("cx", x(parseDate(taylorItem.date)));
      taylorDot.setAttribute("cy", y(Number(taylorItem.value)));
      taylorDot.setAttribute("visibility", "visible");
    }

    const anchorY = y(Number(anchorItem.value));
    const tooltipX = xx > width - 180 ? xx - 162 : xx + 8;
    const tooltipY = Math.max(4, anchorY - tooltipHeight - 6);
    tooltipGroup.setAttribute("transform", `translate(${tooltipX}, ${tooltipY})`);
    tooltipGroup.setAttribute("visibility", "visible");
    tooltipDate.setAttribute("x", 9);
    tooltipDate.setAttribute("y", 18);
    tooltipDate.textContent = formatDate(anchorItem.date);
    tooltipSelic.setAttribute("x", 9);
    tooltipSelic.setAttribute("y", 37);
    tooltipSelic.textContent = selicItem ? `Selic: ${formatRate(Number(selicItem.value))}` : "Selic: —";
    tooltipTaylor.setAttribute("x", 9);
    tooltipTaylor.setAttribute("y", 56);
    tooltipTaylor.textContent = taylorItem ? `Taylor: ${formatRate(Number(taylorItem.value))}` : "";
  };

  const leaveHandler = () => {
    hoverLine.setAttribute("visibility", "hidden");
    selicDot.setAttribute("visibility", "hidden");
    taylorDot.setAttribute("visibility", "hidden");
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
