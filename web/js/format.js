const numberFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

export function formatRate(value) {
  return Number.isFinite(value) ? `${numberFormatter.format(value)}%` : "—";
}

export function formatPoints(value) {
  if (!Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${numberFormatter.format(value)} p.p.`;
}

export function formatDate(value) {
  if (!value) return "—";
  return dateFormatter.format(new Date(`${value}T00:00:00Z`));
}

export function formatDateTime(value) {
  if (!value) return "—";
  return dateTimeFormatter.format(new Date(value));
}

export function formatValue(series) {
  if (series?.status !== "available" || !series.latest) return "—";
  if (series.unit === "percentage_points") return formatPoints(series.latest.value);
  return formatRate(series.latest.value);
}

export function dataKindLabel(kind) {
  return {
    observed: "dado observado",
    survey: "pesquisa",
    estimated: "estimativa",
    derived: "cálculo",
    simulated: "simulação",
  }[kind] ?? kind ?? "não classificado";
}
