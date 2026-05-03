# Implementation Plan: RBAC v2 (Inspetor Role)

## Objective
Implement the new `INSPETOR` role as defined in `docs/architecture/RBAC_v2.md` and align the existing RBAC system to enforce the updated permission matrix across the application.

## Key Files & Context
- `app/shared/core/enums.py`: Contains the `TipoPapel` enum which defines the system roles.
- `app/bootstrap/dependencies.py`: Defines FastApi dependencies for role-based access control.
- `app/modules/auth/router.py`: Handles authentication and user management routes.
- `app/modules/aeronaves/router.py`: Handles aircraft routes.
- `app/modules/equipamentos/router.py`: Handles equipment routes.
- `app/modules/vencimentos/router.py`: Handles maintenance schedules/deadlines routes.
- `app/modules/inspecoes/router.py`: Handles inspections routes.
- `app/web/pages/router.py`: Handles frontend page rendering and route protection.

## Implementation Steps

### Phase 1: Core Definitions and Dependencies
1. **Update `TipoPapel` Enum:**
   - In `app/shared/core/enums.py`, add `INSPETOR = "INSPETOR"` to the `TipoPapel` enum.
   - Update the docstring to reflect the four roles (MANTENEDOR, ENCARREGADO, INSPETOR, ADMINISTRADOR).

2. **Add New Dependencies:**
   - In `app/bootstrap/dependencies.py`, add the following type aliases:
     - `InspetorRequired = Annotated[Usuario, Depends(require_role("INSPETOR"))]`
     - `InspetorOuAdmin = Annotated[Usuario, Depends(require_role("INSPETOR", "ADMINISTRADOR"))]`
     - `EncarregadoInspetorOuAdmin = Annotated[Usuario, Depends(require_role("ENCARREGADO", "INSPETOR", "ADMINISTRADOR"))]`
     - `ExecucaoPermitida = Annotated[Usuario, Depends(require_role("MANTENEDOR", "ENCARREGADO", "ADMINISTRADOR"))]` (Explicitly excludes INSPETOR from execution tasks).

### Phase 2: Route Updates (Backend API)
Review and update each router based on the `docs/architecture/RBAC_v2.md` matrix:

1. **Panes (`app/modules/panes/router.py`):**
   - Adicionar anexos, Assumir, Concluir/fechar: Update to use `ExecucaoPermitida`.
   - Atribuir responsabilidade, Editar, Excluir: Keep `EncarregadoOuAdmin`.

2. **Aeronaves (`app/modules/aeronaves/router.py`):**
   - Alternar status: Update to use `EncarregadoInspetorOuAdmin`.

3. **Equipamentos (`app/modules/equipamentos/router.py`):**
   - Instalar/Remover, Ajustar S/N: Update to use `ExecucaoPermitida`.

4. **Vencimentos (`app/modules/vencimentos/router.py`):**
   - Controlar (análise), Prorrogar: Update to use `EncarregadoInspetorOuAdmin`.

5. **Inspeções (`app/modules/inspecoes/router.py`):**
   - Executar tarefa: Update to use `ExecucaoPermitida`.
   - Abrir, Cancelar, Concluir, Validar: Update to use `EncarregadoInspetorOuAdmin`.

### Phase 3: Frontend Updates
- Review `app/web/pages/router.py` to ensure route protection matches the backend.
- Update template logic (`{% if current_user.funcao == ... %}`) to account for the `INSPETOR` role, hiding execution buttons and showing validation/coordination buttons where appropriate.

## Verification & Testing
1. Verify unit tests for the `dependencies.py` module to ensure `require_role` correctly handles the new roles and combinations.
2. Manually test or write integration tests for critical routes (e.g., trying to close a pane as an INSPETOR should return 403 Forbidden).
3. Ensure no existing `MANTENEDOR` or `ENCARREGADO` workflows are broken by the addition of the new role.