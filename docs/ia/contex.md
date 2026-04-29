# ctx

meta:
- sync_date: 2026-04-29
- mode: machine
- format: kv_short
- truth: official_docs_first

project:
- name: SAA29
- type: web_monolith_modular_ddd
- domain: panes_aeronaves_inventario_a29
- status: architecture_stabilized_ddd_active
- test_status: unit_pass_after_inspecoes_tests (88 tests)
- db_state: active_db_preserve_no_schema_change_for_inspecoes

operational_constraints:
- active_database_in_use: true
- fine_tuning_phase: true
- preserve_current_database: mandatory
- preserve_existing_panes: mandatory
- before_any_db_schema_or_data_change: backup_original_database
- avoid_reset_or_reseed_on_active_database: true
- seed_execution_env: must_run_inside_docker (use `docker-compose exec -e PYTHONPATH=/app web python scripts/seed/seed.py` to target the active docker volume instead of local venv)

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
- inspecoes: isolated_backend_scaffold_not_registered (tipos_inspecao,tarefas_template,inspecoes,inspecao_tarefas)

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
- RN-I01: abrir_inspecao_instancia_tarefas_template
- RN-I02: concluir_inspecao_exige_tarefas_obrigatorias_resolvidas
- RN-I03: primeira_tarefa_resolvida_muda_status_para_EM_ANDAMENTO
- RN-I04: tarefa_CONCLUIDA_exige_executor_e_data_execucao
- RN-I05: inspecao_CONCLUIDA_ou_CANCELADA_nao_editavel
- RN-I07: bloqueia_duplicidade_ativa_por_aeronave_tipo

current_focus:
- docs_synced: true (IA updated for isolated inspections scaffold)
- security_controls_active: 100_percent (CSP hardening completed)
- inventory_module_active: true
- configuracoes_module_active: true
- matriz_vencimentos_active: true
- inspecoes_module_active: true
- inspecoes_backend_scaffold_isolated: false (integrated and tests passing)
- inspecoes_router_registered_in_bootstrap: true
- inspecoes_models_imported_in_bootstrap: true
- inspecoes_migration_created: true
- inspecoes_frontend_integrated: phase_4_completed (lista e detalhes)
- ddd_modularization_completed: true
- frontend_csp_refactoring_completed: true (removed all inline scripts)
- alembic_migrations_up_to_date: true

known_gaps_from_roadmap:
- logout_frontend_backend_alignment
- database_url_consistency
- bug_fix_inativar_anv_config (documented in docs/relatorio)
- inspecoes_requires_activation_plan: migration, bootstrap_model_import, router_registration, frontend_integration, tests
