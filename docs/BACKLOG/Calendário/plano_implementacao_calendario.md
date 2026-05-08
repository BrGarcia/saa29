# IMPL PLAN: CALENDAR MODULE
**Ref**: `docs/BACKLOG/modulo_calendario.md`
**Strategy**: Phased MVP, Token-Efficient, Backend-Driven Security.
**Development Rules**: **ISOLATED DEVELOPMENT**. Do not modify existing modules (except essential routes) until the final integration phase (P5) to prevent breaking the system. Start with tests (TDD).
**Status**: P0-P5 completed. Validation: `.\.venv\Scripts\pytest.exe tests -q` -> 162 passed.
**Commits**:
- P0: `6c276dc` `test: define calendario module contracts`
- P1: `91d587b` `feat: add calendario data layer`
- P2: `2229683` `feat: implement calendario backend api`
- P3: `c4ffdfd` `feat: add calendario frontend view`
- P4: `57095cf` `test: cover calendario write permissions`
- P5: pending final commit

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
- [x] **Setup Lib**: Implemented equivalent vanilla JS calendar to avoid new runtime dependencies.
- [x] **Views**: Day, Week, Month, Year.
- [x] **Data Fetching**: Hook calendar state to `GET /api/v1/calendario/eventos`.
- [x] **Custom Event Render**: Format as `[ {trigram} ] {icon} {title}`.

## P4: INTERACTIVE UI (Write Operations)
**Goal**: Create/Edit modals respecting RBAC.
- [x] **Event Handlers**: Listen to calendar day clicks and event clicks.
- [x] **Dynamic Modal**:
  - Type Selector `[ Ferias | Servico | Particular | Eventos ]`.
  - Field `Militar` (read-only self se Mantenedor/Inspetor; select if Encarregado/Admin).
- [x] **API Bindings**:
  - `POST/PUT /api/v1/calendario/eventos`.
  - `DELETE /api/v1/calendario/eventos/{id}` (Backend blocks if not Admin).
- [x] **Support API**: `GET /api/v1/calendario/tipos` for type selector.
- [x] **Write permission tests**: covered third-party create block and non-admin delete block.

## P5: EXTERNAL MODULES (Aggregation)
**Goal**: Cross-domain data fusion.
- [x] **Backend Update**: `get_events()` aggregates inspection DPE as `source: 'inspecao'`.
- [x] **Backend Update**: added no-op task adapter pending a real To-Do module. See `docs/BACKLOG/Calendário/Duvidas.md`.
- [x] **UI Filters**: Sidebar toggles (`[x] Efetivo`, `[x] Inspecoes`, `[ ] Tarefas`).
