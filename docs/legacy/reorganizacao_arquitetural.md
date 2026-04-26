# arch_reorg_plan
- goal: modular_decoupling_ddd
- strategy: split_physical_from_logical
- status: completed

## directory_structure (Template per Module)
- path: app/modules/<domain>/
- files:
  - models.py   # SQLAlchemy Entities
  - schemas.py  # Pydantic DTOs
  - service.py  # Business Rules (Use Cases)
  - router.py   # FastAPI Endpoints

## domain_map

### 1. auth (Efetivo & Segurança)
- scope: Users, Roles, Auth logic.
- models: Usuario, Posto, Especialidade.
- key_logic: session_management, role_enforcement.

### 2. aeronaves (Frota)
- scope: Aircraft lifecycle.
- models: Aeronave.
- key_logic: availability_toggle, operational_status.

### 3. equipamentos (Catálogo & Inventário)
- scope: Physical assets and positions.
- models: ModeloEquipamento (PN), SlotInventario (Slot), ItemEquipamento (SN), Instalacao.
- key_logic: installation_integrity, physical_tracking.

### 4. vencimentos (Inteligência Temporal)
- scope: Maintenance periodicities and limits.
- models: ControleVencimento, TipoControle, EquipamentoControle, ProrrogacaoVencimento.
- key_logic: date_calculation, status_propagation (Green/Yellow/Red/Grey).

### 5. panes (Corretiva)
- scope: Unplanned maintenance.
- models: Pane, Anexo, PaneResponsavel.
- key_logic: lifecycle (Open -> Resolved), attachments.

### 6. inspecoes (Programada) [BACKLOG]
- scope: Process-based maintenance.
- models: Inspecao, ChecklistItem.
- key_logic: inspections_triggers_panes_or_vencimentos.

### 7. logistica (Pedidos de Material) [BACKLOG]
- scope: Supply chain and parts requesting.
- models: PedidoMaterial, ItemPedido.
- key_logic: workflow (Requested -> Approved -> Delivered), linked to Panes/Inspecoes.

### 8. efetivo (Gestão de Pessoal) [BACKLOG]
- scope: Personnel availability and scales.
- models: Indisponibilidade (Ferias, Dispensa, Folga).
- key_logic: blocking_assignment_in_panes_if_unavailable.

## implementation_notes
- cross_module: Use IDs for relationships; avoid deep object joins between Equipamentos and Vencimentos in services.
- migration: Incremental move of models from 'equipamentos' to 'vencimentos'.

## execution_roadmap

### Phase 1: Vencimentos Extraction (Critical) [COMPLETED]
1. **Bootstrap Module**: Create `app/modules/vencimentos/` with `__init__.py`. (Done)
2. **Model Migration**: 
   - Move `TipoControle`, `EquipamentoControle`, `ControleVencimento`, `ProrrogacaoVencimento` from `equipamentos.models` to `vencimentos.models`. (Done)
   - Update `Base` metadata imports to ensure Alembic detects the move (if needed). (Done)
3. **Logic Migration**:
   - Move `calcular_vencimentos` and related date utility functions to `vencimentos.service`. (Done)
   - Ensure `vencimentos.service` can access `ItemEquipamento` via ID to avoid circular imports. (Done)
4. **API Refactor**:
   - Create `vencimentos.router`. (Done)
   - Migrate endpoints: `GET /matriz`, `POST /prorrogacao`, etc. (Done)
5. **Cross-Module Cleanup**: Update all `import app.modules.equipamentos.models` to `vencimentos.models` where applicable. (Done)

### Consistência Arquitetural e Bugs Identificados [COMPLETED]
1. **Inconsistências de Status (Enums)**: 
   - Sincronização dos status de `Aeronave` (agora: `DISPONIVEL`, `INDISPONIVEL`, `INSPEÇÃO`, `ESTOCADA`, `INATIVA`) no banco, schemas e código. (Done)
   - Sincronização dos status de `ControleVencimento` (agora: `OK`, `VENCENDO`, `VENCIDO`, `PRORROGADO`). Status ambíguos removidos e lógica de PRORROGADO implementada via junção da prorrogação com o status base. (Done)
2. **Relação de Equipamentos e Vencimentos**: Correção da hierarquia lógica em cascata (PN -> Slot -> SN -> Vencimentos -> Instalação). Lógica de "Desinstalado" implementada em nível de view/matriz quando o Slot não possui Instalação ativa. (Done)
3. **Resolução de Quebras de Importação (Seed)**: Correção de referências nas importações da base de dados de `seed_vencimentos.py` e `seed_inventario.py` que falhavam devido à extração de módulos. (Done)
4. **Ajustes Adicionais**: Comentários, remoção de acentos e alinhamento do `models.py` da base para evitar erros de validação e interpretação inconsistentes. (Done)

### Phase 2: Efetivo Foundation [COMPLETED]
1. **Bootstrap Module**: Create `app/modules/efetivo/`. (Done)
2. **New Model**: Implement `Indisponibilidade` (FK to `Usuario`). (Done)
3. **Auth Bridge**: Update `AuthService.garantir_usuarios_essenciais` to optionally initialize availability data in dev. (Done)

### Phase 3: Global Routing & Standardization [COMPLETED]
1. **Router Registration**: Update `app/main.py` to include new routers. (Done para Vencimentos e Efetivo)
2. **Seed Synchronization**: Update `scripts/seed/seed.py` e arquivos de `init_db.py` para usarem a estrutura fragmentada. (Done - adicionados modelos no init_db)
3. **Test Validation**: Run `pytest` and fix any broken import/mock. (Done - 93 testes passando)

## seed_maintenance_rules (Rigoroso)
- **Não criar novos orquestradores**: O único ponto de entrada para carga de dados deve ser o `scripts/seed/seed.py`.
- **Edição Modular**: Alterações em dados de um domínio devem ser feitas EXCLUSIVAMENTE em seu arquivo correspondente (ex: mudar frota -> editar `seed_aeronaves.py`).
- **Novos Módulos**: Somente criar um novo arquivo (ex: `seed_inspecoes.py`) se um novo domínio for implementado, e registrá-lo imediatamente no `seed.py` principal.
- **Transação Única**: O orquestrador `seed.py` deve manter a política de transação única (commit apenas no final) para garantir integridade.