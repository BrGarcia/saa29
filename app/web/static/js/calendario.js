// @ts-check

/**
 * @typedef {Object} CalendarEvent
 * @property {string} id
 * @property {string} title
 * @property {string} start
 * @property {string} end
 * @property {string} [source]
 * @property {string} [owner_trigram]
 * @property {string} [owner_user_id]
 * @property {string} [event_type_id]
 * @property {string} [icon]
 * @property {string} [backgroundColor]
 * @property {string} [notes]
 * @property {boolean} [can_edit]
 * @property {boolean} [can_delete]
 */

/**
 * @typedef {Object} CalendarEventType
 * @property {string} id
 * @property {string} name
 * @property {string} icon
 */

/**
 * @typedef {Object} CalendarState
 * @property {Date} currentDate
 * @property {"month"|"week"|"day"|"year"} view
 * @property {CalendarEvent[]} events
 * @property {CalendarEventType[]} eventTypes
 * @property {any[]} users
 */

/** @type {CalendarState} */
const calendarState = {
    currentDate: new Date(),
    view: "month",
    events: [],
    eventTypes: [],
    users: [],
};

/**
 * @param {Date|string|number} date
 * @returns {Date}
 */
function startOfDay(date) {
    const value = new Date(date);
    value.setHours(0, 0, 0, 0);
    return value;
}

/**
 * @param {Date|string|number} date
 * @param {number} days
 * @returns {Date}
 */
function addDays(date, days) {
    const value = new Date(date);
    value.setDate(value.getDate() + days);
    return value;
}

/**
 * @param {Date|string|number} date
 * @param {number} months
 * @returns {Date}
 */
function addMonths(date, months) {
    const value = new Date(date);
    value.setMonth(value.getMonth() + months);
    return value;
}

/**
 * @param {Date} date
 * @returns {string}
 */
function formatDateKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/**
 * @param {Date|string|number} date
 * @returns {string}
 */
function toInputDateTime(date) {
    const value = new Date(date);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
}

/**
 * @param {string} value
 * @returns {string}
 */
function fromInputDateTime(value) {
    return new Date(value).toISOString();
}

/**
 * @returns {any}
 */
function currentUser() {
    try {
        return JSON.parse(localStorage.getItem("saa29_user") || "{}");
    } catch (e) {
        return {};
    }
}

/**
 * @returns {boolean}
 */
function isPrivilegedUser() {
    const role = (currentUser().funcao || "").toUpperCase();
    return role === "ADMINISTRADOR" || role === "ENCARREGADO";
}

/**
 * @returns {{start: Date, end: Date}}
 */
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

/**
 * @returns {Promise<void>}
 */
async function loadCalendarData() {
    const { start, end } = getRange();
    const params = new URLSearchParams({
        start_date: start.toISOString(),
        end_date: end.toISOString(),
    });
    // @ts-ignore (Assuming apiFetch is globally available)
    calendarState.events = await apiFetch(`/api/v1/calendario/eventos?${params.toString()}`);
    renderCalendar();
}

/**
 * @returns {Promise<void>}
 */
async function loadSupportData() {
    // @ts-ignore
    calendarState.eventTypes = await apiFetch("/api/v1/calendario/tipos");
    // @ts-ignore
    calendarState.users = await apiFetch("/auth/usuarios");
}

/**
 * @returns {Set<string>}
 */
function activeSources() {
    return new Set(
        Array.from(document.querySelectorAll(".calendar-source-filter:checked"))
            /** @param {any} input */
            .map((input) => input.value)
    );
}

/**
 * @returns {CalendarEvent[]}
 */
function visibleEvents() {
    const sources = activeSources();
    return calendarState.events.filter((event) => sources.has(event.source || "calendario"));
}

/**
 * @returns {void}
 */
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

/**
 * @returns {string}
 */
function buildTitle() {
    const date = calendarState.currentDate;
    if (calendarState.view === "year") return String(date.getFullYear());
    if (calendarState.view === "day") return date.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
    if (calendarState.view === "week") return "Semana Operacional";
    return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

/**
 * @param {HTMLElement} grid
 * @returns {void}
 */
function renderDaysGrid(grid) {
    const { start, end } = getRange();
    /** @type {Date[]} */
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

/**
 * @param {HTMLElement} grid
 * @returns {void}
 */
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

/**
 * @param {HTMLElement} grid
 * @returns {void}
 */
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
            // @ts-ignore
            setView("month");
        });
        grid.appendChild(monthBox);
    }
}

/**
 * @param {CalendarEvent[]} events
 * @param {Date} day
 * @returns {CalendarEvent[]}
 */
function eventsForDay(events, day) {
    const dayStart = startOfDay(day);
    const dayEnd = addDays(dayStart, 1);
    return events.filter((event) => new Date(event.start) < dayEnd && new Date(event.end) >= dayStart);
}

/**
 * @param {CalendarEvent[]} events
 * @param {number} month
 * @returns {CalendarEvent[]}
 */
function eventsForMonth(events, month) {
    return events.filter((event) => new Date(event.start).getMonth() === month || new Date(event.end).getMonth() === month);
}

/**
 * @param {CalendarEvent} event
 * @returns {HTMLButtonElement}
 */
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

/**
 * @param {CalendarEvent} event
 * @returns {HTMLButtonElement}
 */
function renderEventRow(event) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `calendar-event-row source-${event.source || "calendario"}`;
    row.style.borderLeftColor = event.backgroundColor || "var(--primary-color)";
    // @ts-ignore (Assuming escapeHtml is globally available)
    row.innerHTML = `
        <span>${new Date(event.start).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
        <strong>[ ${escapeHtml(event.owner_trigram || "---")} ] ${escapeHtml(event.icon || "")} ${escapeHtml(event.title)}</strong>
        <small>${escapeHtml(event.notes || "")}</small>
    `;
    row.addEventListener("click", () => openEditModal(event));
    return row;
}

/**
 * @param {"month"|"week"|"day"|"year"} view
 * @returns {void}
 */
function setView(view) {
    calendarState.view = view;
    document.querySelectorAll(".calendar-view-btn").forEach((btn) => {
        // @ts-ignore
        btn.classList.toggle("is-active", btn.dataset.view === view);
    });
    loadCalendarData();
}

/**
 * @param {number} direction
 * @returns {void}
 */
function movePeriod(direction) {
    if (calendarState.view === "day") calendarState.currentDate = addDays(calendarState.currentDate, direction);
    else if (calendarState.view === "week") calendarState.currentDate = addDays(calendarState.currentDate, direction * 7);
    else if (calendarState.view === "year") calendarState.currentDate = new Date(calendarState.currentDate.getFullYear() + direction, 0, 1);
    else calendarState.currentDate = addMonths(calendarState.currentDate, direction);
    loadCalendarData();
}

/**
 * @returns {void}
 */
function fillSelects() {
    const typeSelect = document.getElementById("calendar-event-type");
    const ownerSelect = document.getElementById("calendar-owner");
    if (!typeSelect || !ownerSelect) return;
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
    // @ts-ignore
    ownerSelect.disabled = !canSelectOwner;
}

/**
 * @param {Date|string|number} date
 * @returns {void}
 */
function openCreateModal(date) {
    fillSelects();
    const titleEl = document.getElementById("calendar-modal-title");
    const eventIdEl = document.getElementById("calendar-event-id");
    const ownerEl = document.getElementById("calendar-owner");
    const startEl = document.getElementById("calendar-start");
    const endEl = document.getElementById("calendar-end");
    const notesEl = document.getElementById("calendar-notes");
    const deleteBtnEl = document.getElementById("calendar-delete-btn");

    if (titleEl) titleEl.textContent = "Novo Evento";
    // @ts-ignore
    if (eventIdEl) eventIdEl.value = "";
    const user = currentUser();
    // @ts-ignore
    if (ownerEl) ownerEl.value = user.id || "";
    const start = new Date(date);
    start.setHours(8, 0, 0, 0);
    const end = new Date(date);
    end.setHours(17, 0, 0, 0);
    // @ts-ignore
    if (startEl) startEl.value = toInputDateTime(start);
    // @ts-ignore
    if (endEl) endEl.value = toInputDateTime(end);
    // @ts-ignore
    if (notesEl) notesEl.value = "";
    if (deleteBtnEl) deleteBtnEl.style.display = "none";
    setFormEnabled(true);
    showModal();
}

/**
 * @param {CalendarEvent} event
 * @returns {void}
 */
function openEditModal(event) {
    if ((event.source || "calendario") !== "calendario" || !event.can_edit) {
        // @ts-ignore
        showToast("Evento somente para consulta.", "info");
        return;
    }
    fillSelects();
    const titleEl = document.getElementById("calendar-modal-title");
    const eventIdEl = document.getElementById("calendar-event-id");
    const typeEl = document.getElementById("calendar-event-type");
    const ownerEl = document.getElementById("calendar-owner");
    const startEl = document.getElementById("calendar-start");
    const endEl = document.getElementById("calendar-end");
    const notesEl = document.getElementById("calendar-notes");
    const deleteBtnEl = document.getElementById("calendar-delete-btn");

    if (titleEl) titleEl.textContent = "Editar Evento";
    // @ts-ignore
    if (eventIdEl) eventIdEl.value = event.id;
    // @ts-ignore
    if (typeEl) typeEl.value = event.event_type_id || "";
    // @ts-ignore
    if (ownerEl) ownerEl.value = event.owner_user_id || "";
    // @ts-ignore
    if (startEl) startEl.value = toInputDateTime(event.start);
    // @ts-ignore
    if (endEl) endEl.value = toInputDateTime(event.end);
    // @ts-ignore
    if (notesEl) notesEl.value = event.notes || "";
    if (deleteBtnEl) deleteBtnEl.style.display = event.can_delete ? "inline-flex" : "none";
    setFormEnabled(true);
    showModal();
}

/**
 * @param {boolean} enabled
 * @returns {void}
 */
function setFormEnabled(enabled) {
    document.querySelectorAll("#calendar-event-form input, #calendar-event-form select, #calendar-event-form textarea, #calendar-save-btn").forEach((el) => {
        // @ts-ignore
        if (el.id !== "calendar-owner" || isPrivilegedUser()) el.disabled = !enabled;
    });
}

/**
 * @returns {void}
 */
function showModal() {
    const modal = document.getElementById("calendar-event-modal");
    if (modal) modal.hidden = false;
}

/**
 * @returns {void}
 */
function closeModal() {
    const modal = document.getElementById("calendar-event-modal");
    if (modal) modal.hidden = true;
    const form = document.getElementById("calendar-event-form");
    // @ts-ignore
    if (form) form.reset();
}

/**
 * @param {Event} e
 * @returns {Promise<void>}
 */
async function saveEvent(e) {
    e.preventDefault();
    const idEl = document.getElementById("calendar-event-id");
    // @ts-ignore
    const id = idEl ? idEl.value : "";
    const ownerEl = document.getElementById("calendar-owner");
    const typeEl = document.getElementById("calendar-event-type");
    const startEl = document.getElementById("calendar-start");
    const endEl = document.getElementById("calendar-end");
    const notesEl = document.getElementById("calendar-notes");

    const payload = {
        // @ts-ignore
        owner_user_id: ownerEl ? ownerEl.value : "",
        // @ts-ignore
        event_type_id: typeEl ? typeEl.value : "",
        // @ts-ignore
        start_date: fromInputDateTime(startEl ? startEl.value : ""),
        // @ts-ignore
        end_date: fromInputDateTime(endEl ? endEl.value : ""),
        // @ts-ignore
        notes: (notesEl && notesEl.value) ? notesEl.value : null,
    };
    const url = id ? `/api/v1/calendario/eventos/${id}` : "/api/v1/calendario/eventos";
    const method = id ? "PUT" : "POST";
    // @ts-ignore
    await apiFetch(url, { method, body: payload });
    // @ts-ignore
    showToast("Evento salvo.", "success");
    closeModal();
    loadCalendarData();
}

/**
 * @returns {Promise<void>}
 */
async function deleteEvent() {
    const idEl = document.getElementById("calendar-event-id");
    // @ts-ignore
    const id = idEl ? idEl.value : "";
    if (!id || !confirm("Excluir este evento?")) return;
    // @ts-ignore
    await apiFetch(`/api/v1/calendario/eventos/${id}`, { method: "DELETE" });
    // @ts-ignore
    showToast("Evento excluido.", "success");
    closeModal();
    loadCalendarData();
}

document.addEventListener("DOMContentLoaded", async () => {
    if (!document.getElementById("calendar-grid")) return;
    document.querySelectorAll(".calendar-view-btn").forEach((btn) => btn.addEventListener("click", () => {
        // @ts-ignore
        setView(btn.dataset.view)
    }));
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
