# IMPL PLAN: CALENDAR MODULE
**Ref**: `docs/BACKLOG/modulo_calendario.md`
**Strategy**: Phased MVP, Token-Efficient, Backend-Driven Security.
**Development Rules**: **ISOLATED DEVELOPMENT**. Do not modify existing modules (except essential routes) until the final integration phase (P5) to prevent breaking the system. Start with tests (TDD).
**Status**: P0-P2 completed. Validation: `.\.venv\Scripts\pytest.exe tests -q` -> 158 passed.
**Commits**:
- P0: `6c276dc` `test: define calendario module contracts`
- P1: `91d587b` `feat: add calendario data layer`
- P2: `2229683` `feat: implement calendario backend api`

## P0: TDD IMPLEMENTATION (Tests First)
**Goal**: Define contracts and expected behavior before coding.
- [x] **Setup Pytest**: Created `tests/test_calendario.py`.
- [x] **Tests for Models & Schemas**: Validated `event_types` and `calendar_events` constraints.
- [x] **Tests for RBAC & Censorship**: Added assertions for `IS_PRIVATE`, `HAS_PRIVILEGE`, and `IS_OWNER` logic.
- [x] **Tests for CRUD APIs**: Covered create, update, delete, and list through isolated router tests.

## P1: DATA LAYER (DB & Schema)
**Goal**: Foundation & Persistence.
- [x] **Model `event_types`**: `id`, `name`, `visibility_type` (enum: public/private), `color`, `icon`, `active`.
- [x] **Model `calendar_events`**: `id`, `owner_user_id` (FK), `created_by_user_id` (FK), `event_type_id` (FK), `start_date`, `end_date`, `notes`.
- [x] **Schemas**: Pydantic schemas for IO.
- [x] **Seeder**: Inject base types (`Ferias`, `Consulta`, `Servico`) via `scripts/seed/seed_calendario.py`.
- [x] **Migration**: Added Alembic revision `c4d5e6f7a8b9`.
- [x] **Bootstrap metadata**: Imported `app.modules.calendario.models` in app bootstrap.

## P2: CORE BACKEND (Aggregator & RBAC)
**Goal**: API with built-in censorship.
- [x] **Service `calendario/service.py`**:
  - `get_events(start_date, end_date, current_user)`
  - Query `calendar_events` with `owner` (`trigrama`) and `event_type` eager loading.
- [x] **Censorship Logic**:
  - `IS_PRIVATE = (event_type.visibility_type == 'private')`
  - `HAS_PRIVILEGE = (current_user.funcao IN ['ENCARREGADO', 'ADMINISTRADOR', 'ADMIN'])`
  - `IS_OWNER = (current_user.id == owner_user_id)`
  - **IF** `IS_PRIVATE` AND `NOT HAS_PRIVILEGE` AND `NOT IS_OWNER`:
    - `title = "Particular"`, `icon = "L"`, drop `notes`.
- [x] **Router**: `GET /api/v1/calendario/eventos` -> Returns `{id, title, start, end, backgroundColor, icon, owner_trigram, notes}`.
- [x] **CRUD APIs**: `POST/PUT /api/v1/calendario/eventos` and `DELETE /api/v1/calendario/eventos/{id}` with backend authorization.
- [x] **App integration**: Router registered in `app/bootstrap/main.py` under `/api/v1/calendario`.

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
  - Type Selector `[ Ferias | Servico | Particular | Eventos ]`.
  - Field `Militar` (read-only self se Mantenedor/Inspetor; select if Encarregado/Admin).
- [ ] **API Bindings**:
  - `POST/PUT /api/v1/calendario/eventos`.
  - `DELETE /api/v1/calendario/eventos/{id}` (Backend blocks if not Admin).

## P5: EXTERNAL MODULES (Aggregation)
**Goal**: Cross-domain data fusion.
- [ ] **Backend Update**: `get_events()` calls `inspecoes_service` -> maps DPE (Data Prev. Encerramento) to `{type: 'inspecao'}`.
- [ ] **Backend Update**: calls `todo_service` -> maps deadlines to `{type: 'task'}`.
- [ ] **UI Filters**: Sidebar toggles (`[x] Efetivo`, `[x] Inspecoes`, `[ ] Tarefas`).
