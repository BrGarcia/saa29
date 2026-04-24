# ctx

meta:
- sync_date: 2026-04-22
- mode: machine
- format: kv_short
- truth: official_docs_first

project:
- name: SAA29
- type: web_monolith_modular
- domain: panes_aeronaves_inventario_a29
- status: active_local_production_ready

operational_constraints:
- active_database_in_use: true
- fine_tuning_phase: true
- preserve_current_database: mandatory
- preserve_existing_panes: mandatory
- before_any_db_schema_or_data_change: backup_original_database
- avoid_reset_or_reseed_on_active_database: true

stack:
- backend: fastapi
- orm: sqlalchemy_async
- validation: pydantic_v2
- migrations: alembic
- db_default: sqlite_aiosqlite
- db_optional: postgresql_asyncpg
- frontend: jinja2_vanilla_js_css
- storage: local_or_r2

entrypoints:
- app: app/bootstrap/main.py
- run_local: scripts/run_app.py
- db_init: scripts/db/init_db.py
- db_seed: scripts/db/seed.py

domains:
- auth: usuarios, token_blacklist, token_refresh
- aeronaves: cadastro, status, toggle_status
- panes: pane, anexo, responsavel, soft_delete, restore
- equipamentos: modelo, slot, item, instalacao, vencimento, inventario
- configuracoes: admin_dashboard, gerenciamento_tabelas_apoio

auth_state:
- access_token: jwt_hs256
- refresh_token: persisted_rotated
- transport: authorization_header_or_cookie_saa29_token
- roles: ADMINISTRADOR, ENCARREGADO, MANTENEDOR

core_rules:
- RN-01: pane_requires_aeronave
- RN-02: pane_default_status_ABERTA
- RN-03: only_open_pane_can_be_edited
- RN-04: conclude_sets_data_conclusao
- RN-05: empty_desc_becomes_AGUARDANDO_EDICAO
- RN-06: admin_or_encarregado_for_admin_writes
- RN-07: mantenedor_only_self_assign
- RN-12: controle_association_propagates_to_existing_items

current_focus:
- docs_synced: true
- security_controls_active: true
- inventory_module_active: true
- preserve_existing_pane_data: mandatory
- test_suites_present: unit, security, architecture

known_gaps_from_roadmap:
- logout_frontend_backend_alignment
- database_url_consistency
- stronger_cookie_only_auth_migration
- dead_code_cleanup
