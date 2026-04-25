# architecture_summary

style: modular_monolith
philosophy: surgical_updates_preserve_data

domain_layers:
- models: sqlalchemy_2_0_mapped_types
- schemas: pydantic_v2_strict
- services: async_business_logic
- routers: fastapi_rest_endpoints
- templates: jinja2_vanilla_js

core_entities:
- Auth: Usuario (RBAC)
- Operational: Aeronave, Pane, Anexo, PaneResponsavel
- Logistics: 
    - ModeloEquipamento (PN)
    - SlotInventario (Location in ACFT)
    - ItemEquipamento (Physical SN)
    - Instalacao (Link SN + Slot + ACFT)
    - TipoControle (Code only: CRI, TLV)
    - EquipamentoControle (Rules: PN + Control = Months)
    - ControleVencimento (Instance tracking)
    - ProrrogacaoVencimento (Engineering extensions)

key_relationships:
- PN_to_Control: N:N via EquipamentoControle (defines periodicity)
- Item_to_Control: 1:N via ControleVencimento (created on item creation)
- Installation: Requires slot_id + item_id + aeronave_id (strict integrity)

critical_flows:
- Item_Creation: Inherits controls from its PN (EquipamentoControle -> ControleVencimento)
- Execution_Record: Calculates next date based on PN-specific rule and deactivates active extensions.
- Inventory_Adjustment: Synchronizes physical state with digital slots.

security_posture:
- JWT_Rotation: Enabled
- CSRF_Protection: Global middleware
- Permissions: Encarregado/Admin for configuration, Mantenedor for operations.
