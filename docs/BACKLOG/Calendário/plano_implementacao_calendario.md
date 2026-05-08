# IMPL PLAN: CALENDAR MODULE
**Ref**: `docs/BACKLOG/modulo_calendario.md`
**Strategy**: Phased MVP, Token-Efficient, Backend-Driven Security.

## P1: DATA LAYER (DB & Schema)
**Goal**: Foundation & Persistence.
- [ ] **Model `event_types`**: `id`, `name`, `visibility_type` (enum: public/private), `color`, `icon`, `active`.
- [ ] **Model `calendar_events`**: `id`, `owner_user_id` (FK), `created_by_user_id` (FK), `event_type_id` (FK), `start_date`, `end_date`, `notes`.
- [ ] **Schemas**: Pydantic schemas for IO.
- [ ] **Seeder**: Inject base types (🌴 Férias, 🏥 Consulta, 🛡️ Serviço).

## P2: CORE BACKEND (Aggregator & RBAC)
**Goal**: API with built-in censorship.
- [ ] **Service `calendario/service.py`**:
  - `get_events(start_date, end_date, current_user)`
  - Query `calendar_events` JOIN `users` (`trigram`) JOIN `event_types`.
- [ ] **Censorship Logic**:
  - `IS_PRIVATE = (event_type.visibility_type == 'private')`
  - `HAS_PRIVILEGE = (current_user.role IN ['ENCARREGADO', 'ADMIN'])`
  - `IS_OWNER = (current_user.id == owner_user_id)`
  - **IF** `IS_PRIVATE` AND `NOT HAS_PRIVILEGE` AND `NOT IS_OWNER`:
    - `title = "Particular"`, `icon = "🔒"`, drop `notes`.
- [ ] **Router**: `GET /api/v1/calendario/eventos` -> Returns `{id, title, start, end, backgroundColor, icon, owner_trigram}`.

## P3: FRONTEND UI (Read-Only)
**Goal**: Visual rendering of time blocks.
- [ ] **Setup Lib**: Integrate FullCalendar (or equivalent).
- [ ] **Views**: Day, Week, Month, Year.
- [ ] **Data Fetching**: Hook calendar state to `GET /api/v1/calendario/eventos`.
- [ ] **Custom Event Render**: Format as `[ {trigram} ] {icon} {title}`.

## P4: INTERACTIVE UI (Write Operations)
**Goal**: Create/Edit modals respecting RBAC.
- [ ] **Event Handlers**: Listen to `dateClick` / `eventClick`.
- [ ] **Dynamic Modal**:
  - Type Selector `[ Férias | Serviço | Particular | Eventos ]`.
  - Field `Militar` (read-only self se Mantenedor/Inspetor; select if Encarregado/Admin).
- [ ] **API Bindings**:
  - `POST/PUT /api/v1/calendario/eventos`.
  - `DELETE /api/v1/calendario/eventos/{id}` (Backend blocks if not Admin).

## P5: EXTERNAL MODULES (Aggregation)
**Goal**: Cross-domain data fusion.
- [ ] **Backend Update**: `get_events()` calls `inspecoes_service` -> maps DPE (Data Prev. Encerramento) to `{type: 'inspecao'}`.
- [ ] **Backend Update**: calls `todo_service` -> maps deadlines to `{type: 'task'}`.
- [ ] **UI Filters**: Sidebar toggles (`[x] Efetivo`, `[x] Inspeções`, `[ ] Tarefas`).
