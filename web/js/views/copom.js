import { formatDate, formatRate } from "../format.js";

const RECENT_LIMIT = 4;
const UPCOMING_LIMIT = 3;

function eventTypeLabel(type) {
  return {
    copom_decision: "Comunicado",
    copom_minutes: "Ata",
    copom_meeting: "Reunião",
    rpm_release: "RPM",
    rpm_schedule: "Agenda RPM",
  }[type] ?? type;
}

function eventCard(event) {
  const article = document.createElement("article");
  article.className = `policy-event-card policy-event-${event.type}`;
  const top = document.createElement("div");
  top.className = "policy-event-topline";
  const type = document.createElement("span");
  type.className = "policy-event-type";
  type.textContent = eventTypeLabel(event.type);
  const date = document.createElement("time");
  date.dateTime = String(event.occurred_at).slice(0, 10);
  date.textContent = formatDate(String(event.occurred_at).slice(0, 10));
  top.append(type, date);
  const title = document.createElement("h3");
  title.textContent = event.title;
  article.append(top, title);

  if (event.decision_rate_percent != null) {
    const decision = document.createElement("p");
    decision.className = "policy-event-decision";
    const direction = { cut: "Corte", hike: "Alta", hold: "Manutenção" }[event.decision_direction] ?? "Decisão";
    decision.textContent = `${direction} · Selic ${formatRate(Number(event.decision_rate_percent))}`;
    article.append(decision);
  }
  if (event.published_at && String(event.published_at).slice(0, 10) !== String(event.occurred_at).slice(0, 10)) {
    const published = document.createElement("p");
    published.className = "policy-event-meta";
    published.textContent = `Publicado em ${formatDate(String(event.published_at).slice(0, 10))}`;
    article.append(published);
  }
  if (["scheduled", "scheduled_unverified", "fulfilled"].includes(event.status)) {
    const status = document.createElement("p");
    status.className = "policy-event-status";
    status.textContent = event.status === "scheduled"
      ? "Agendado"
      : event.status === "fulfilled"
        ? "Agenda cumprida; relatório publicado"
        : "Data agendada; publicação ainda não verificada";
    article.append(status);
  }
  if (event.url) {
    const link = document.createElement("a");
    link.href = event.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Abrir fonte oficial";
    article.append(link);
  }
  return article;
}

function emptyNote(message) {
  const note = document.createElement("p");
  note.className = "inline-note";
  note.textContent = message;
  return note;
}

function renderLimitedList(container, toggle, events, limit, emptyMessage) {
  let expanded = false;
  const render = () => {
    const visible = expanded ? events : events.slice(0, limit);
    container.replaceChildren(...visible.map(eventCard));
    container.classList.toggle("policy-event-list-expanded", expanded);
    if (!events.length) container.append(emptyNote(emptyMessage));
    const hasMore = events.length > limit;
    toggle.hidden = !hasMore;
    toggle.textContent = expanded ? "Recolher" : `Ver todos (${events.length})`;
    toggle.setAttribute("aria-expanded", String(expanded));
  };
  toggle.onclick = () => {
    expanded = !expanded;
    render();
  };
  render();
}

export function renderCopomEvents(payload) {
  const section = document.querySelector("#copom-content");
  const unavailable = document.querySelector("#copom-unavailable");
  const recent = document.querySelector("#copom-recent");
  const upcoming = document.querySelector("#copom-upcoming");
  const recentToggle = document.querySelector("#copom-recent-toggle");
  const upcomingToggle = document.querySelector("#copom-upcoming-toggle");
  const date = document.querySelector("#copom-date");
  if (!section || !recent || !upcoming || !recentToggle || !upcomingToggle) return;

  unavailable.hidden = true;
  section.hidden = false;
  date.textContent = payload.knowledge_mode === "as_known"
    ? `Como era conhecido em ${formatDate(String(payload.knowledge_cutoff).slice(0, 10))}`
    : `Atualizado ${formatDate(String(payload.generated_at).slice(0, 10))}`;

  renderLimitedList(
    recent,
    recentToggle,
    payload.recent ?? [],
    RECENT_LIMIT,
    "Nenhum documento do Copom disponível neste recorte de conhecimento.",
  );
  renderLimitedList(
    upcoming,
    upcomingToggle,
    payload.upcoming ?? [],
    UPCOMING_LIMIT,
    "Nenhum evento futuro conhecido neste recorte.",
  );
}

export function renderCopomUnavailable(message) {
  const section = document.querySelector("#copom-content");
  const unavailable = document.querySelector("#copom-unavailable");
  if (section) section.hidden = true;
  if (unavailable) {
    unavailable.hidden = false;
    unavailable.textContent = message;
  }
}
