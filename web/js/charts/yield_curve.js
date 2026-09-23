function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function formatNumber(value) {
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

export function renderYieldCurveChart(container, { current = [], comparison = [], currentLabel = "Atual", comparisonLabel = "Comparação" }) {
  container.replaceChildren();
  const all = [...current, ...comparison];
  if (!all.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Não há pontos disponíveis para esta curva.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 320);
  const height = container.clientHeight || 330;
  const margin = { top: 18, right: 18, bottom: 42, left: 56 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const xs = all.map((item) => Number(item.tenor_years));
  const ys = all.map((item) => Number(item.value));
  const xMinRaw = Math.min(...xs);
  const xMaxRaw = Math.max(...xs);
  const xPadding = Math.max((xMaxRaw - xMinRaw) * 0.05, 0.2);
  const xMin = Math.max(0, xMinRaw - xPadding);
  const xMax = xMaxRaw + xPadding;
  const yMinRaw = Math.min(...ys);
  const yMaxRaw = Math.max(...ys);
  const yPadding = Math.max((yMaxRaw - yMinRaw) * 0.15, 0.25);
  const yMin = yMinRaw - yPadding;
  const yMax = yMaxRaw + yPadding;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin || 1)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin || 1)) * plotHeight;

  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
  for (let index = 0; index <= 4; index += 1) {
    const value = yMin + ((yMax - yMin) * index) / 4;
    const yy = y(value);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: yy, y2: yy, class: "grid-line" }));
    const label = svgElement("text", { x: margin.left - 8, y: yy + 4, "text-anchor": "end" });
    label.textContent = `${formatNumber(value)}%`;
    svg.append(label);
  }
  for (let index = 0; index <= 4; index += 1) {
    const value = xMin + ((xMax - xMin) * index) / 4;
    const xx = x(value);
    const label = svgElement("text", { x: xx, y: height - 14, "text-anchor": index === 0 ? "start" : index === 4 ? "end" : "middle" });
    label.textContent = `${formatNumber(value)}a`;
    svg.append(label);
  }

  const pathFor = (points) => points.map((point, index) => `${index ? "L" : "M"}${x(Number(point.tenor_years)).toFixed(2)},${y(Number(point.value)).toFixed(2)}`).join(" ");
  if (comparison.length) {
    svg.append(svgElement("path", { d: pathFor(comparison), class: "series-line curve-comparison-line" }));
    comparison.forEach((point) => svg.append(svgElement("circle", { cx: x(Number(point.tenor_years)), cy: y(Number(point.value)), r: 3, class: "curve-comparison-dot" })));
  }
  if (current.length) {
    svg.append(svgElement("path", { d: pathFor(current), class: "series-line curve-current-line" }));
    current.forEach((point) => svg.append(svgElement("circle", { cx: x(Number(point.tenor_years)), cy: y(Number(point.value)), r: 3.5, class: "curve-current-dot" })));
  }

  const xTitle = svgElement("text", { x: margin.left + plotWidth / 2, y: height - 1, "text-anchor": "middle", class: "axis-title" });
  xTitle.textContent = "Prazo até o vencimento (anos)";
  svg.append(xTitle);
  container.append(svg);

  return {
    destroy() { svg.remove(); },
    labels: { currentLabel, comparisonLabel },
  };
}
