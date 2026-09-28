const DEFAULT_DATA_URLS = Object.freeze({
  overview: "./data/overview.json",
  copom: "./data/copom-events.json",
  credit: "./data/credit-transmission.json",
  fiscal: "./data/fiscal.json",
  external: "./data/external-sector.json",
  us: "./data/us-benchmark.json",
  curve: "./data/yield-curve.json",
});

const ARCHIVE_FILENAMES = Object.freeze({
  overview: "overview.json",
  copom: "copom-events.json",
  credit: "credit-transmission.json",
  fiscal: "fiscal.json",
  external: "external-sector.json",
  us: "us-benchmark.json",
  curve: "yield-curve.json",
});

export async function loadVintageIndex(url = "./data/vintages/index.json") {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    const payload = await response.json();
    if (!payload || payload.view !== "vintage_index" || !Array.isArray(payload.entries)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function sortedEntries(index) {
  return [...(index?.entries ?? [])]
    .filter((entry) => /^\d{4}-\d{2}-\d{2}$/.test(entry?.date ?? ""))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function resolveKnowledgeSelection(index, search = window.location.search) {
  const params = new URLSearchParams(search);
  const requestedMode = params.get("knowledge");
  const requestedDate = params.get("date");
  const entries = sortedEntries(index);

  if (requestedMode !== "as_known") {
    return {
      mode: "latest_revision",
      requestedDate: null,
      effectiveDate: null,
      entry: null,
      urls: { ...DEFAULT_DATA_URLS },
      availableDates: entries.map((entry) => entry.date),
    };
  }

  const target = /^\d{4}-\d{2}-\d{2}$/.test(requestedDate ?? "")
    ? requestedDate
    : entries.at(-1)?.date ?? null;
  const eligible = target ? entries.filter((entry) => entry.date <= target) : [];
  const entry = eligible.at(-1) ?? null;
  if (!entry) {
    return {
      mode: "latest_revision",
      requestedDate: target,
      effectiveDate: null,
      entry: null,
      urls: { ...DEFAULT_DATA_URLS },
      availableDates: entries.map((item) => item.date),
      fallbackReason: "Não há registro histórico local defensável em ou antes da data solicitada.",
    };
  }

  const prefix = `./data/vintages/${entry.date}`;
  return {
    mode: "as_known",
    requestedDate: target,
    effectiveDate: entry.date,
    entry,
    urls: Object.fromEntries(
      Object.entries(ARCHIVE_FILENAMES).map(([key, filename]) => [key, `${prefix}/${filename}`]),
    ),
    availableDates: entries.map((item) => item.date),
  };
}

function navigate(mode, dateValue) {
  const url = new URL(window.location.href);
  if (mode === "as_known") {
    url.searchParams.set("knowledge", "as_known");
    url.searchParams.set("date", dateValue);
  } else {
    url.searchParams.delete("knowledge");
    url.searchParams.delete("date");
  }
  window.location.assign(url.toString());
}

export function initializeVintageControls(selection, index) {
  const mode = document.querySelector("#knowledge-select");
  const dateInput = document.querySelector("#knowledge-date");
  const apply = document.querySelector("#knowledge-apply");
  const status = document.querySelector("#vintage-status");
  if (!mode || !dateInput || !apply || !status) return;

  const entries = sortedEntries(index);
  const asKnownOption = mode.querySelector('option[value="as_known"]');
  if (!entries.length && asKnownOption) asKnownOption.disabled = true;

  mode.value = selection.mode;
  const defaultDate = selection.requestedDate ?? entries.at(-1)?.date ?? "";
  dateInput.value = defaultDate;
  dateInput.disabled = mode.value !== "as_known" || !entries.length;
  if (entries.length) {
    dateInput.min = entries[0].date;
    dateInput.max = entries.at(-1).date;
  }

  if (selection.mode === "as_known") {
    const coverage = selection.entry?.coverage;
    const shifted = selection.requestedDate && selection.requestedDate !== selection.effectiveDate;
    status.textContent = shifted
      ? `Corte solicitado ${selection.requestedDate}. Usando o último registro histórico local disponível em ${selection.effectiveDate}.`
      : `Reconstrução como conhecida em ${selection.effectiveDate}. ${coverage?.caveat ?? ""}`;
  } else if (selection.fallbackReason) {
    status.textContent = `${selection.fallbackReason} Exibindo a revisão mais recente.`;
  } else if (!entries.length) {
    status.textContent = "Registros históricos locais ainda não publicados. Execute ./scripts/publish-vintages.sh para habilitar a reconstrução histórica.";
  } else {
    status.textContent = "Informações mais recentes.";
  }

  mode.addEventListener("change", () => {
    dateInput.disabled = mode.value !== "as_known" || !entries.length;
  });
  apply.addEventListener("click", () => {
    if (mode.value === "as_known") {
      if (!dateInput.value) return;
      navigate("as_known", dateInput.value);
    } else {
      navigate("latest_revision", "");
    }
  });
}
