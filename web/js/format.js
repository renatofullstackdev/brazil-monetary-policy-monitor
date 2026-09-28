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
  return formatUnitValue(Number(series.latest.value), series.unit);
}

export function unitLabel(unit) {
  return {
    percent_per_year: "% a.a.",
    percent_per_month: "% a.m.",
    percent: "%",
    percent_of_gdp: "% do PIB",
    percentage_points: "p.p.",
    percent_year_over_year_real: "% em 12 meses, real",
    brl_billions: "R$ bilhões",
    years: "anos",
    months: "meses",
    brl_real: "R$",
    index: "índice",
    brl_per_usd: "R$/US$",
    usd_millions: "US$ milhões",
    percent_change: "%",
  }[unit] ?? "—";
}

export function formatUnitValue(value, unit) {
  if (!Number.isFinite(Number(value))) return "—";
  const numeric = Number(value);
  if (unit === "percentage_points") return formatPoints(numeric);
  if (["percent_per_year", "percent_per_month", "percent", "percent_year_over_year_real", "percent_change"].includes(unit)) return formatRate(numeric);
  if (unit === "percent_of_gdp") return `${numberFormatter.format(numeric)}% do PIB`;
  if (unit === "brl_billions") return `R$ ${numberFormatter.format(numeric)} bi`;
  if (unit === "brl_per_usd") return `R$ ${numberFormatter.format(numeric)}/US$`;
  if (unit === "usd_millions") return `US$ ${numberFormatter.format(numeric)} mi`;
  if (unit === "years") return `${numberFormatter.format(numeric)} anos`;
  if (unit === "months") return `${numberFormatter.format(numeric)} meses`;
  if (unit === "brl_real") {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(numeric);
  }
  return numberFormatter.format(numeric);
}

export function dataKindLabel(kind) {
  return {
    observed: "dado observado",
    survey: "pesquisa",
    estimated: "estimativa",
    derived: "cálculo",
    simulated: "simulação",
  }[kind] ?? "não classificado";
}
