import { formatDate } from "../format.js";

const NS = "http://www.w3.org/2000/svg";
const DAY_MS = 86_400_000;

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

function parseDate(value) {
  return new Date(`${value}T00:00:00Z`).getTime();
}

function linePath(observations, x, y) {
  return observations
    .map((item, index) => `${index === 0 ? "M" : "L"}${x(parseDate(item.date)).toFixed(2)},${y(Number(item.value)).toFixed(2)}`)
    .join(" ");
}

function nearest(observations, target) {
  if (!observations.length) return null;
  let answer = observations[0];
  let distance = Math.abs(parseDate(answer.date) - target);
  for (const item of observations) {
    const current = Math.abs(parseDate(item.date) - target);
    if (current < distance) {
      answer = item;
      distance = current;
    }
  }
  return answer;
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function shortSeriesLabel(label) {
  return label
    .replace(" — 12m / PIB", "")
    .replace(" — venda", "")
    .replace("Reservas internacionais — liquidez", "Reservas — liquidez")
    .replace("Carteira — passivos líquidos", "Carteira — passivos");
}

function formatAxisDate(timestamp, spanMs) {
  const current = new Date(timestamp);
  const day = String(current.getUTCDate()).padStart(2, "0");
  const month = String(current.getUTCMonth() + 1).padStart(2, "0");
  const year = current.getUTCFullYear();
  if (spanMs >= 2 * 365 * DAY_MS) return `${month}/${year}`;
  if (spanMs >= 120 * DAY_MS) return `${month}/${String(year).slice(-2)}`;
  return `${day}/${month}`;
}

function estimatedTextWidth(text) {
  return String(text).length * 6.4;
}

export function renderExternalChart(
  container,
  { series, valueFormatter, axisValueFormatter = valueFormatter, geometry = "line" },
) {
  container.replaceChildren();
  const populated = series.filter((item) => item.observations.length);
  const all = populated.flatMap((item) => item.observations);
  if (!all.length) {
    const empty = document.createElement("p");
    empty.className = "inline-note";
    empty.textContent = "Nenhuma observação disponível para o período selecionado.";
    container.append(empty);
    return { destroy() {} };
  }

  const width = Math.max(container.clientWidth, 280);
  const height = Math.max(container.clientHeight || 330, 300);
  const times = all.map((item) => parseDate(item.date));
  const values = all.map((item) => Number(item.value));
  const xMin = Math.min(...times);
  const rawXMax = Math.max(...times);
  const xMax = rawXMax === xMin ? xMin + DAY_MS : rawXMax;
  const spanMs = xMax - xMin;

  let rawMin = geometry === "bar" ? Math.min(0, ...values) : Math.min(...values);
  let rawMax = geometry === "bar" ? Math.max(0, ...values) : Math.max(...values);
  if (rawMin === rawMax) {
    const delta = Math.max(Math.abs(rawMin) * 0.05, 1);
    rawMin -= delta;
    rawMax += delta;
  }
  const includeZero = geometry === "bar" || (rawMin < 0 && rawMax > 0);
  const padding = Math.max((rawMax - rawMin) * 0.1, Math.abs(rawMax) * 0.01, 0.1);
  const yMin = rawMin - padding;
  const yMax = rawMax + padding;
  const yTicks = Array.from({ length: 5 }, (_, index) => yMin + ((yMax - yMin) * index) / 4);
  const longestYLabel = yTicks
    .map((value) => axisValueFormatter(value))
    .reduce((longest, current) => (current.length > longest.length ? current : longest), "");

  const margin = {
    top: 18,
    right: width < 440 ? 10 : 16,
    bottom: width < 440 ? 34 : 38,
    left: clamp(estimatedTextWidth(longestYLabel) + 14, 48, width < 440 ? 82 : 104),
  };
  const plotWidth = Math.max(width - margin.left - margin.right, 80);
  const plotHeight = Math.max(height - margin.top - margin.bottom, 120);
  const x = (timestamp) => margin.left + ((timestamp - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin || 1)) * plotHeight;

  const svg = svgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    "aria-hidden": "true",
    preserveAspectRatio: "xMidYMid meet",
  });

  yTicks.forEach((value) => {
    const yy = y(value);
    svg.append(svgElement("line", {
      x1: margin.left,
      x2: width - margin.right,
      y1: yy,
      y2: yy,
      class: "grid-line",
    }));
    const label = svgElement("text", {
      x: margin.left - 8,
      y: yy + 4,
      "text-anchor": "end",
      class: "external-axis-label",
    });
    label.textContent = axisValueFormatter(value);
    svg.append(label);
  });

  if (includeZero) {
    const yy = y(0);
    svg.append(svgElement("line", {
      x1: margin.left,
      x2: width - margin.right,
      y1: yy,
      y2: yy,
      class: "axis-line external-zero-line",
    }));
  }

  const xIntervals = width < 520 ? 2 : 4;
  for (let index = 0; index <= xIntervals; index += 1) {
    const timestamp = xMin + ((xMax - xMin) * index) / xIntervals;
    const label = svgElement("text", {
      x: x(timestamp),
      y: height - 12,
      "text-anchor": index === 0 ? "start" : index === xIntervals ? "end" : "middle",
      class: "external-axis-label",
    });
    label.textContent = formatAxisDate(timestamp, spanMs);
    svg.append(label);
  }

  populated.forEach((item, index) => {
    if (geometry === "bar" && populated.length === 1) {
      const zeroY = y(0);
      const barWidth = clamp((plotWidth / Math.max(item.observations.length, 1)) * 0.68, 2, 16);
      item.observations.forEach((observation) => {
        const yy = y(Number(observation.value));
        svg.append(svgElement("rect", {
          x: x(parseDate(observation.date)) - barWidth / 2,
          y: Math.min(yy, zeroY),
          width: barWidth,
          height: Math.max(Math.abs(zeroY - yy), 1),
          class: `external-bar series-${Math.min(index + 1, 5)}-fill`,
        }));
      });
      return;
    }
    svg.append(svgElement("path", {
      d: linePath(item.observations, x, y),
      class: `series-line series-${Math.min(index + 1, 5)}`,
    }));
  });

  const hoverLine = svgElement("line", {
    class: "hover-line",
    y1: margin.top,
    y2: height - margin.bottom,
    visibility: "hidden",
  });
  const tooltip = svgElement("g", { visibility: "hidden", class: "external-tooltip" });
  const tooltipWidth = clamp(width - 24, 190, 320);
  const tooltipHeight = 30 + 21 * populated.length;
  const box = svgElement("rect", {
    class: "tooltip-box",
    rx: 7,
    width: tooltipWidth,
    height: tooltipHeight,
  });
  tooltip.append(box);
  const title = svgElement("text", { class: "tooltip-title", x: 10, y: 19 });
  tooltip.append(title);

  const tooltipRows = populated.map((item, index) => {
    const yy = 40 + index * 20;
    const label = svgElement("text", { x: 10, y: yy, class: "external-tooltip-label" });
    label.textContent = shortSeriesLabel(item.label);
    const value = svgElement("text", {
      x: tooltipWidth - 10,
      y: yy,
      "text-anchor": "end",
      class: "external-tooltip-value",
    });
    const dot = svgElement("circle", {
      r: 3.5,
      class: `series-${Math.min(index + 1, 5)}-dot`,
      visibility: "hidden",
    });
    tooltip.append(label, value);
    svg.append(dot);
    return { item, value, dot };
  });
  svg.append(hoverLine, tooltip);

  const pointerHandler = (event) => {
    const rect = svg.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * width;
    const bounded = clamp(pointerX, margin.left, width - margin.right);
    const target = xMin + ((bounded - margin.left) / plotWidth) * (xMax - xMin);
    const anchor = nearest(populated[0].observations, target);
    if (!anchor) return;
    const anchorTime = parseDate(anchor.date);
    const xx = x(anchorTime);
    hoverLine.setAttribute("x1", xx);
    hoverLine.setAttribute("x2", xx);
    hoverLine.setAttribute("visibility", "visible");

    const preferredTooltipX = xx + 10;
    const tooltipX = clamp(preferredTooltipX, 8, width - tooltipWidth - 8);
    tooltip.setAttribute("transform", `translate(${tooltipX}, 8)`);
    tooltip.setAttribute("visibility", "visible");
    title.textContent = formatDate(anchor.date);

    tooltipRows.forEach(({ item, value, dot }) => {
      const observation = nearest(item.observations, anchorTime);
      value.textContent = observation ? valueFormatter(Number(observation.value)) : "—";
      if (!observation) {
        dot.setAttribute("visibility", "hidden");
        return;
      }
      dot.setAttribute("cx", x(parseDate(observation.date)));
      dot.setAttribute("cy", y(Number(observation.value)));
      dot.setAttribute("visibility", "visible");
    });
  };

  const leaveHandler = () => {
    hoverLine.setAttribute("visibility", "hidden");
    tooltip.setAttribute("visibility", "hidden");
    tooltipRows.forEach(({ dot }) => dot.setAttribute("visibility", "hidden"));
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
