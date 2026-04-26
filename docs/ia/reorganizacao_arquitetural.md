# arch_reorg_plan
- goal: modular_decoupling_ddd
- strategy: split_physical_from_logical
- status: planned

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
