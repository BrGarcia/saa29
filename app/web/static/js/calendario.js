const calendarState = {
    currentDate: new Date(),
    view: "month",
    events: [],
    eventTypes: [],
    users: [],
};

function startOfDay(date) {
    const value = new Date(date);
    value.setHours(0, 0, 0, 0);
    return value;
}

function addDays(date, days) {
    const value = new Date(date);
    value.setDate(value.getDate() + days);
    return value;
}

function addMonths(date, months) {
    const value = new Date(date);
    value.setMonth(value.getMonth() + months);
    return value;
}

function formatDateKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function toInputDateTime(date) {
    const value = new Date(date);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
}

function fromInputDateTime(value) {
    return new Date(value).toISOString();
}

function currentUser() {
    try {
        return JSON.parse(localStorage.getItem("saa29_user") || "{}");
    } catch (e) {
        return {};
    }
}

function isPrivilegedUser() {
    const role = (currentUser().funcao || "").toUpperCase();
    return role === "ADMINISTRADOR" || role === "ENCARREGADO";
}

function getRange() {
    const base = startOfDay(calendarState.currentDate);
    if (calendarState.view === "day") {
        return { start: base, end: addDays(base, 1) };
    }
    if (calendarState.view === "week") {
        const start = addDays(base, -base.getDay());
        return { start, end: addDays(start, 7) };
    }
    if (calendarState.view === "year") {
        const start = new Date(base.getFullYear(), 0, 1);
        return { start, end: new Date(base.getFullYear() + 1, 0, 1) };
    }
    const start = new Date(base.getFullYear(), base.getMonth(), 1);
    return { start, end: new Date(base.getFullYear(), base.getMonth() + 1, 1) };
}

async function loadCalendarData() {
    const { start, end } = getRange();
    const params = new URLSearchParams({
        start_date: start.toISOString(),
        end_date: end.toISOString(),
    });
    calendarState.events = await apiFetch(`/api/v1/calendario/eventos?${params.toString()}`);
    renderCalendar();
}

async function loadSupportData() {
    calendarState.eventTypes = await apiFetch("/api/v1/calendario/tipos");
    calendarState.users = await apiFetch("/auth/usuarios");
}

function activeSources() {
    return new Set(
        Array.from(document.querySelectorAll(".calendar-source-filter:checked"))
            .map((input) => input.value)
    );
}

function visibleEvents() {
    const sources = activeSources();
    return calendarState.events.filter((event) => sources.has(event.source || "calendario"));
}

function renderCalendar() {
    const grid = document.getElementById("calendar-grid");
    const title = document.getElementById("calendar-title");
    const rangeLabel = document.getElementById("calendar-range-label");
    if (!grid || !title || !rangeLabel) return;

    const { start, end } = getRange();
    rangeLabel.textContent = `${start.toLocaleDateString("pt-BR")} - ${addDays(end, -1).toLocaleDateString("pt-BR")}`;
    title.textContent = buildTitle();

    if (calendarState.view === "year") renderYear(grid);
    else if (calendarState.view === "day") renderDay(grid);
    else renderDaysGrid(grid);
}

function buildTitle() {
    const date = calendarState.currentDate;
    if (calendarState.view === "year") return String(date.getFullYear());
    if (calendarState.view === "day") return date.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
    if (calendarState.view === "week") return "Semana Operacional";
    return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

function renderDaysGrid(grid) {
    const { start, end } = getRange();
    const days = [];
    let cursor = new Date(start);
    if (calendarState.view === "month") {
        cursor = addDays(cursor, -cursor.getDay());
    }
    const last = calendarState.view === "month" ? addDays(end, 6 - addDays(end, -1).getDay()) : end;
    while (cursor < last) {
        days.push(new Date(cursor));
        cursor = addDays(cursor, 1);
    }

    grid.className = "calendar-grid calendar-grid-days";
    grid.innerHTML = "";
    ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"].forEach((label) => {
        const header = document.createElement("div");
        header.className = "calendar-day-header";
        header.textContent = label;
        grid.appendChild(header);
    });

    const events = visibleEvents();
    days.forEach((day) => {
        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = "calendar-day-cell";
        if (day.getMonth() !== calendarState.currentDate.getMonth() && calendarState.view === "month") {
            cell.classList.add("is-muted");
        }
        cell.dataset.date = day.toISOString();

        const number = document.createElement("span");
        number.className = "calendar-day-number";
        number.textContent = String(day.getDate());
        cell.appendChild(number);

        eventsForDay(events, day).slice(0, 4).forEach((event) => {
            cell.appendChild(renderEventChip(event));
        });

        cell.addEventListener("click", () => openCreateModal(day));
        grid.appendChild(cell);
    });
}

function renderDay(grid) {
    grid.className = "calendar-grid calendar-grid-list";
    grid.innerHTML = "";
    const events = eventsForDay(visibleEvents(), calendarState.currentDate);
    if (events.length === 0) {
        const empty = document.createElement("div");
        empty.className = "calendar-empty";
        empty.textContent = "Sem eventos para o dia selecionado.";
        grid.appendChild(empty);
        return;
    }
    events.forEach((event) => grid.appendChild(renderEventRow(event)));
}

function renderYear(grid) {
    grid.className = "calendar-grid calendar-grid-year";
    grid.innerHTML = "";
    const events = visibleEvents();
    for (let month = 0; month < 12; month += 1) {
        const monthBox = document.createElement("button");
        monthBox.type = "button";
        monthBox.className = "calendar-month-box";
        const date = new Date(calendarState.currentDate.getFullYear(), month, 1);
        monthBox.innerHTML = `<strong>${date.toLocaleDateString("pt-BR", { month: "short" })}</strong><span>${eventsForMonth(events, month).length} eventos</span>`;
        monthBox.addEventListener("click", () => {
            calendarState.currentDate = date;
            setView("month");
        });
        grid.appendChild(monthBox);
    }
}

function eventsForDay(events, day) {
    const dayStart = startOfDay(day);
    const dayEnd = addDays(dayStart, 1);
    return events.filter((event) => new Date(event.start) < dayEnd && new Date(event.end) >= dayStart);
}

function eventsForMonth(events, month) {
    return events.filter((event) => new Date(event.start).getMonth() === month || new Date(event.end).getMonth() === month);
}

function renderEventChip(event) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `calendar-event-chip source-${event.source || "calendario"}`;
    chip.style.borderLeftColor = event.backgroundColor || "var(--primary-color)";
    chip.textContent = `[ ${event.owner_trigram || "---"} ] ${event.icon || ""} ${event.title}`;
    chip.addEventListener("click", (e) => {
        e.stopPropagation();
        openEditModal(event);
    });
    return chip;
}

function renderEventRow(event) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `calendar-event-row source-${event.source || "calendario"}`;
    row.style.borderLeftColor = event.backgroundColor || "var(--primary-color)";
    row.innerHTML = `
        <span>${new Date(event.start).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
        <strong>[ ${escapeHtml(event.owner_trigram || "---")} ] ${escapeHtml(event.icon || "")} ${escapeHtml(event.title)}</strong>
        <small>${escapeHtml(event.notes || "")}</small>
    `;
    row.addEventListener("click", () => openEditModal(event));
    return row;
}

function setView(view) {
    calendarState.view = view;
    document.querySelectorAll(".calendar-view-btn").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.view === view);
    });
    loadCalendarData();
}

function movePeriod(direction) {
    if (calendarState.view === "day") calendarState.currentDate = addDays(calendarState.currentDate, direction);
    else if (calendarState.view === "week") calendarState.currentDate = addDays(calendarState.currentDate, direction * 7);
    else if (calendarState.view === "year") calendarState.currentDate = new Date(calendarState.currentDate.getFullYear() + direction, 0, 1);
    else calendarState.currentDate = addMonths(calendarState.currentDate, direction);
    loadCalendarData();
}

function fillSelects() {
    const typeSelect = document.getElementById("calendar-event-type");
    const ownerSelect = document.getElementById("calendar-owner");
    const user = currentUser();
    const canSelectOwner = isPrivilegedUser();

    typeSelect.innerHTML = "";
    calendarState.eventTypes.forEach((type) => {
        const option = document.createElement("option");
        option.value = type.id;
        option.textContent = `${type.icon} ${type.name}`;
        typeSelect.appendChild(option);
    });

    ownerSelect.innerHTML = "";
    calendarState.users
        .filter((item) => item.ativo && (canSelectOwner || item.id === user.id))
        .forEach((item) => {
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = `[ ${item.trigrama || "---"} ] ${item.posto} ${item.nome}`;
            ownerSelect.appendChild(option);
        });
    ownerSelect.disabled = !canSelectOwner;
}

function openCreateModal(date) {
    fillSelects();
    document.getElementById("calendar-modal-title").textContent = "Novo Evento";
    document.getElementById("calendar-event-id").value = "";
    const user = currentUser();
    document.getElementById("calendar-owner").value = user.id || "";
    const start = new Date(date);
    start.setHours(8, 0, 0, 0);
    const end = new Date(date);
    end.setHours(17, 0, 0, 0);
    document.getElementById("calendar-start").value = toInputDateTime(start);
    document.getElementById("calendar-end").value = toInputDateTime(end);
    document.getElementById("calendar-notes").value = "";
    document.getElementById("calendar-delete-btn").style.display = "none";
    setFormEnabled(true);
    showModal();
}

function openEditModal(event) {
    if ((event.source || "calendario") !== "calendario" || !event.can_edit) {
        showToast("Evento somente para consulta.", "info");
        return;
    }
    fillSelects();
    document.getElementById("calendar-modal-title").textContent = "Editar Evento";
    document.getElementById("calendar-event-id").value = event.id;
    document.getElementById("calendar-event-type").value = event.event_type_id || "";
    document.getElementById("calendar-owner").value = event.owner_user_id || "";
    document.getElementById("calendar-start").value = toInputDateTime(event.start);
    document.getElementById("calendar-end").value = toInputDateTime(event.end);
    document.getElementById("calendar-notes").value = event.notes || "";
    document.getElementById("calendar-delete-btn").style.display = event.can_delete ? "inline-flex" : "none";
    setFormEnabled(true);
    showModal();
}

function setFormEnabled(enabled) {
    document.querySelectorAll("#calendar-event-form input, #calendar-event-form select, #calendar-event-form textarea, #calendar-save-btn").forEach((el) => {
        if (el.id !== "calendar-owner" || isPrivilegedUser()) el.disabled = !enabled;
    });
}

function showModal() {
    document.getElementById("calendar-event-modal").hidden = false;
}

function closeModal() {
    document.getElementById("calendar-event-modal").hidden = true;
    document.getElementById("calendar-event-form").reset();
}

async function saveEvent(e) {
    e.preventDefault();
    const id = document.getElementById("calendar-event-id").value;
    const payload = {
        owner_user_id: document.getElementById("calendar-owner").value,
        event_type_id: document.getElementById("calendar-event-type").value,
        start_date: fromInputDateTime(document.getElementById("calendar-start").value),
        end_date: fromInputDateTime(document.getElementById("calendar-end").value),
        notes: document.getElementById("calendar-notes").value || null,
    };
    const url = id ? `/api/v1/calendario/eventos/${id}` : "/api/v1/calendario/eventos";
    const method = id ? "PUT" : "POST";
    await apiFetch(url, { method, body: payload });
    showToast("Evento salvo.", "success");
    closeModal();
    loadCalendarData();
}

async function deleteEvent() {
    const id = document.getElementById("calendar-event-id").value;
    if (!id || !confirm("Excluir este evento?")) return;
    await apiFetch(`/api/v1/calendario/eventos/${id}`, { method: "DELETE" });
    showToast("Evento excluido.", "success");
    closeModal();
    loadCalendarData();
}

document.addEventListener("DOMContentLoaded", async () => {
    if (!document.getElementById("calendar-grid")) return;
    document.querySelectorAll(".calendar-view-btn").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
    document.querySelectorAll(".calendar-source-filter").forEach((input) => input.addEventListener("change", renderCalendar));
    document.getElementById("calendar-prev-btn")?.addEventListener("click", () => movePeriod(-1));
    document.getElementById("calendar-next-btn")?.addEventListener("click", () => movePeriod(1));
    document.getElementById("calendar-today-btn")?.addEventListener("click", () => {
        calendarState.currentDate = new Date();
        loadCalendarData();
    });
    document.getElementById("calendar-new-btn")?.addEventListener("click", () => openCreateModal(calendarState.currentDate));
    document.getElementById("calendar-event-form")?.addEventListener("submit", saveEvent);
    document.getElementById("calendar-delete-btn")?.addEventListener("click", deleteEvent);
    document.getElementById("calendar-cancel-btn")?.addEventListener("click", closeModal);
    document.getElementById("calendar-modal-close")?.addEventListener("click", closeModal);
    await loadSupportData();
    await loadCalendarData();
});
