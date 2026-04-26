# ctx

meta:
- sync_date: 2026-04-26
- mode: machine
- format: kv_short
- truth: official_docs_first

project:
- name: SAA29
- type: web_monolith_modular_ddd
- domain: panes_aeronaves_inventario_a29
- status: architecture_stabilized_ddd_active
- test_status: 100_percent_pass (93 tests)
- db_state: clean_reset_seed_standardized_active

operational_constraints:
- active_database_in_use: true
- fine_tuning_phase: true
- preserve_current_database: mandatory
- preserve_existing_panes: mandatory
- before_any_db_schema_or_data_change: backup_original_database
- avoid_reset_or_reseed_on_active_database: false (Standardized seed.py is the preferred dev path)

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
- db_seed: scripts/seed/seed.py (Single Entry Point)

domains:
- auth: usuarios, token_blacklist, token_refresh
- efetivo: indisponibilidades, ferias, ausencias (Modulo Ativo)
- aeronaves: cadastro, status (DISPONIVEL, INDISPONIVEL, ESTOCADA, INATIVA, INSPEÇÃO), toggle_status
- panes: pane, anexo, responsavel, soft_delete, restore
- equipamentos: modelo (PN), slot, item (SN), instalacao, inventario
- vencimentos: tipo_controle, periodicidade_pn, matriz_vencimentos, prorrogacoes (OK, VENCENDO, VENCIDO, PRORROGADO)
- configuracoes: admin_dashboard, gerenciamento_frota, administracao_efetivo, regras_vencimento

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
- RN-13: periodicidade_meses_defined_per_modelo_controle_pair
- RN-14: execucao_desativa_prorrogacao_ativa

current_focus:
- docs_synced: true (IA and Architecture folders aligned)
- security_controls_active: true
- inventory_module_active: true
- configuracoes_module_active: true
- matriz_vencimentos_active: true
- ddd_modularization_completed: true (Vencimentos and Efetivo extracted)
- status_standardization_completed: true (DISPONIVEL vs OPERACIONAL)
- alembic_migrations_up_to_date: true
- test_suites_passing: 100_percent (unit, security, architecture)

known_gaps_from_roadmap:
- logout_frontend_backend_alignment
- database_url_consistency
- stronger_cookie_only_auth_migration
