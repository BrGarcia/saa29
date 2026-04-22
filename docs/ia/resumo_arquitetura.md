# arch_summary

style:
- pattern: layered_monolith
- flow: router_to_service_to_orm_to_db
- transport: html_pages_and_json_api

paths:
- app_entry: app/bootstrap/main.py
- config: app/bootstrap/config.py
- db: app/bootstrap/database.py
- deps: app/bootstrap/dependencies.py

layers:
- web_html: app/web/pages, app/web/templates, app/web/static
- api: app/modules/*/router.py
- service: app/modules/*/service.py
- model_schema: app/modules/*/models.py, app/modules/*/schemas.py
- shared: app/shared/core, app/shared/middleware

modules:
- auth
- aeronaves
- panes
- equipamentos

entities:
- usuarios
- token_blacklist
- token_refresh
- aeronaves
- panes
- anexos
- pane_responsaveis
- modelos_equipamento
- slots_inventario
- tipos_controle
- equipamento_controles
- itens_equipamento
- instalacoes
- controle_vencimentos

important_arch_decisions:
- ADR-001: fastapi_sqlalchemy_pydantic_sqlite_default
- ADR-002: jwt_plus_refresh_plus_blacklist
- ADR-003: controle_inheritance_in_service_layer

runtime_notes:
- startup_ensures_default_fleet
- sqlite_uses_wal_and_foreign_keys
- static_mounted_from_app/web/static
- r2_backup_can_run_event_driven_when_enabled
