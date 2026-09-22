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
  const quarter = /^(\d{4})-Q([1-4])$/.exec(value);
  if (quarter) return `${quarter[2]}º tri ${quarter[1]}`;
  const month = /^(\d{4})-(\d{2})$/.exec(value);
  if (month) return `${month[2]}/${month[1]}`;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed);
}

export function formatDateTime(value) {
  if (!value) return "—";
  return dateTimeFormatter.format(new Date(value));
}

export function formatValue(series) {
  if (series?.status !== "available" || !series.latest) return "—";
  const value = Number(series.latest.value);
  if (series.unit === "percentage_points") return formatPoints(value);
  if (["percent_per_year", "percent_per_month", "percent"].includes(series.unit)) return formatRate(value);
  if (series.unit === "brl_real") {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(value);
  }
  if (series.unit === "index") return numberFormatter.format(value);
  return Number.isFinite(value) ? numberFormatter.format(value) : "—";
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
