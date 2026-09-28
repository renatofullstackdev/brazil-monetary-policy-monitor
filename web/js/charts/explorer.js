function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function extent(values) {
  const finite = values.map(Number).filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (min === max) return [min - 1, max + 1];
  const padding = Math.max((max - min) * 0.12, Math.abs(max) * 0.02, 0.1);
  return [min - padding, max + padding];
}

function formatNumber(value) {
  const magnitude = Math.abs(value);
  const digits = magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 2;
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(value);
}

function dateLabel(value) {
  const match = /^(\d{4})-(\d{2})/.exec(value ?? "");
  return match ? `${match[2]}/${match[1].slice(2)}` : value;
}

function drawGrid(svg, x1, x2, top, bottom, ticks = 4) {
  for (let index = 0; index <= ticks; index += 1) {
    const y = top + ((bottom - top) * index) / ticks;
    svg.append(svgElement("line", { x1, x2, y1: y, y2: y, class: "grid-line" }));
  }
}

function empty(container, message) {
  container.replaceChildren();
  const note = document.createElement("p");
  note.className = "inline-note";
  note.textContent = message;
  container.append(note);
  return { destroy() {} };
}

export function renderExplorerTimeChart(container, { a = [], b = [], labelA = "A", labelB = "B", combined = false }) {
  if (!a.length && !b.length) return empty(container, "Não há observações suficientes para esta combinação.");
  container.replaceChildren();
  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 380;
  const margin = { top: 18, right: 18, bottom: 36, left: 60 };
  const plotWidth = width - margin.left - margin.right;
  const dates = [...new Set([...a.map((item) => item.date), ...b.map((item) => item.date)])].sort();
  const dateIndex = new Map(dates.map((date, index) => [date, index]));
  const x = (date) => margin.left + (dateIndex.get(date) / Math.max(dates.length - 1, 1)) * plotWidth;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });

  const panels = combined
    ? [{ top: margin.top, bottom: height - margin.bottom, series: [{ values: a, className: "series-1", label: labelA }, { values: b, className: "series-2", label: labelB }] }]
    : [
        { top: margin.top, bottom: height / 2 - 12, series: [{ values: a, className: "series-1", label: labelA }] },
        { top: height / 2 + 20, bottom: height - margin.bottom, series: [{ values: b, className: "series-2", label: labelB }] },
      ];

  for (const panel of panels) {
    const allValues = panel.series.flatMap((series) => series.values.map((item) => Number(item.value)));
    const [yMin, yMax] = extent(allValues);
    const y = (value) => panel.top + (1 - (Number(value) - yMin) / (yMax - yMin || 1)) * (panel.bottom - panel.top);
    drawGrid(svg, margin.left, width - margin.right, panel.top, panel.bottom);
    const yTop = svgElement("text", { x: margin.left - 8, y: panel.top + 4, "text-anchor": "end" });
    yTop.textContent = formatNumber(yMax);
    const yBottom = svgElement("text", { x: margin.left - 8, y: panel.bottom + 4, "text-anchor": "end" });
    yBottom.textContent = formatNumber(yMin);
    svg.append(yTop, yBottom);
    if (!combined) {
      const title = svgElement("text", { x: margin.left, y: panel.top - 5, class: "explorer-panel-label" });
      title.textContent = panel.series[0].label;
      svg.append(title);
    }
    for (const series of panel.series) {
      const path = series.values.map((item, index) => `${index ? "L" : "M"}${x(item.date).toFixed(2)},${y(item.value).toFixed(2)}`).join(" ");
      if (path) svg.append(svgElement("path", { d: path, class: `series-line ${series.className}` }));
    }
  }

  const tickIndexes = [...new Set([0, Math.floor((dates.length - 1) / 2), dates.length - 1])].filter((index) => index >= 0);
  tickIndexes.forEach((index) => {
    const date = dates[index];
    const text = svgElement("text", { x: x(date), y: height - 10, "text-anchor": index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle" });
    text.textContent = dateLabel(date);
    svg.append(text);
  });
  container.append(svg);
  return { destroy() { svg.remove(); } };
}

export function renderExplorerScatterChart(container, { pairs = [], labelA = "A", labelB = "B" }) {
  if (!pairs.length) return empty(container, "As séries não possuem meses coincidentes suficientes neste recorte.");
  container.replaceChildren();
  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 380;
  const margin = { top: 18, right: 24, bottom: 52, left: 64 };
  const [xMin, xMax] = extent(pairs.map((item) => item.a));
  const [yMin, yMax] = extent(pairs.map((item) => item.b));
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin || 1)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin || 1)) * plotHeight;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
  drawGrid(svg, margin.left, width - margin.right, margin.top, height - margin.bottom);
  for (let index = 0; index <= 4; index += 1) {
    const xv = xMin + ((xMax - xMin) * index) / 4;
    const xt = svgElement("text", { x: x(xv), y: height - 30, "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle" });
    xt.textContent = formatNumber(xv);
    svg.append(xt);
    const yv = yMin + ((yMax - yMin) * index) / 4;
    const yt = svgElement("text", { x: margin.left - 8, y: y(yv) + 4, "text-anchor": "end" });
    yt.textContent = formatNumber(yv);
    svg.append(yt);
  }
  pairs.forEach((item) => svg.append(svgElement("circle", { cx: x(item.a), cy: y(item.b), r: 3.4, class: "explorer-scatter-dot" })));
  const xTitle = svgElement("text", { x: margin.left + plotWidth / 2, y: height - 4, "text-anchor": "middle", class: "axis-title" });
  xTitle.textContent = labelA;
  const yTitle = svgElement("text", { x: 14, y: margin.top + plotHeight / 2, transform: `rotate(-90 14 ${margin.top + plotHeight / 2})`, "text-anchor": "middle", class: "axis-title" });
  yTitle.textContent = labelB;
  svg.append(xTitle, yTitle);
  container.append(svg);
  return { destroy() { svg.remove(); } };
}
