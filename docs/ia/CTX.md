# ctx

meta:
- sync_date: 2026-08-08
- docs_structure: reorganized and cleaned (core/, guides/, backlog/, summaries/, ia/*.ctx)
- mode: machine
- format: kv_short
- truth: official_docs_first

project:
- name: SAA29
- type: web_monolith_modular_ddd
- domain: panes_aeronaves_inventario_a29_publicacoes
- status: architecture_stabilized_ddd_active
- version: 1.5.0
- test_status: all tests passing (650+ tests passed, 100% green test suite)
- db_state: active_db_preserve_no_schema_change_for_inspecoes

operational_constraints:
- active_database_in_use: true
- fine_tuning_phase: true
- preserve_current_database: mandatory
- preserve_existing_panes: mandatory
- before_any_db_schema_or_data_change: backup_original_database
- avoid_reset_or_reseed_on_active_database: true
- merge_main_policy: mandatory_follow_docs/methodology/merge_main.md
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
- export: openpyxl_csv_utf8_bom

entrypoints:
- app: app/bootstrap/main.py
- run_local: scripts/run_app.py
- db_init: scripts/db/init_db.py
- db_seed: scripts/seed/seed.py (Single Entry Point - Conditional Dev Seeds)
- indexar_acervo: scripts/publicacoes/indexar.py
- publicar_edicao: scripts/publicacoes/publicar.py

domains:
- auth: usuarios, token_blacklist, token_refresh
- efetivo: indisponividades, ferias, ausencias (Modulo Ativo)
- aeronaves: cadastro, status (DISPONIVEL, INDISPONIVEL, ESTOCADA, INATIVA, INSPEÇÃO), toggle_status
- panes: pane (FK sistema_ata_id), sistemas_ata (Lookup), anexo, responsavel, soft_delete, restore, export_csv_xlsx
- equipamentos: modelo (PN), slot, item (SN), instalacao, inventario, export_csv_xlsx
- vencimentos: tipo_controle, periodicidade_pn, matriz_vencimentos, prorrogacoes (OK, VENCENDO, VENCIDO, PRORROGADO)
- configuracoes: admin_dashboard, gerenciamento_frota, administracao_efetivo, regras_vencimento, gestao_publicacoes
- inspecoes: integrated_fully_active (tipos_inspecao,tarefas_catalogo,tarefas_template,inspecoes,inspecao_tarefas,export_csv_xlsx)
- calendario: p0_p5_active (event_types,calendar_events,rbac_censorship,frontend_ui,write_modal,inspecoes_dpe_aggregation,safe_tz_sorting)
- publicacoes: m0_m4_web_active (manuais_edicoes,manuais_documentos,manuais_fim_map,publicacoes_avulsas,publicacoes_favoritos,publicacoes_upload_jobs,fts5_search,explorador_tree,pdf_viewer_canvas)
- shared/image_pipeline: service_layer_for_image_processing (validator,converter,resizer,optimizer,pipeline)
- shared/contracts: ddd_domain_lookup_protocols (AeronaveLookupProtocol)
- shared/exporter: generic_csv_xlsx_report_generator (gerar_csv, gerar_xlsx)

auth_state:
- access_token: jwt_hs256
- refresh_token: persisted_rotated
- transport: authorization_header_or_cookie_saa29_token
- roles: ADMINISTRADOR, ENCARREGADO, INSPETOR, MANTENEDOR

core_rules:
- RN-01: pane_requires_aeronave
- RN-02: pane_default_status_ABERTA
- RN-02b: sistema_ata_id_optional_but_standardized_lookup
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
- RN-I08: tarefas_extras_manuais_via_frontend_completed
- RN-I09: auditoria_checklist_coluna_atualizacao_trigrama_completed
- RN-I10: desacoplamento_tarefas_catalogo_global_completed
- RN-I11: DPE_calculada_pela_maior_duracao_dos_tipos (DPE = inicio + max_duracao_tipos, permite override manual)
- RN-I12: captura_auditoria_trigrama_persistente_na_inspecao (aberto_por_trigrama, concluido_por_trigrama)
- RN-P01: fts5_search_isolated_by_edition_catalog (catalog.<rotulo>.db resolved by VIGENTE status)
- RN-P02: upload_job_single_flight_lock (max 1 active job in ENVIANDO or PROCESSANDO state)
- RN-P03: zip_security_validation (zip_slip_containment_check, zip_bomb_ratio_entry_limits, extension_allowlist)
- RN-P04: edition_activation_restricted_to_admin (Inspetor and Admin can upload; only Admin can activate)
- RN-D01: dashboard_tactical_override (Active Inspection status overrides persisted aircraft status)
- RN-A02: admin_password_reset_authorized (Admins can reset passwords for other users)

current_focus:
- docs_synced: true (IA updated for v1.5.0 Publicações M0-M4.Web, Calendário Bugfix, and Development branch merge)
- security_controls_active: 100_percent (CSP hardening, Zip security, and Path Traversal fixes completed)
- publicacoes_m0_m4_web_completed: true (M0-M4 + M4.Web web upload fully implemented and tested)
- publicacoes_explorador_promoted: true (Default view at /publicacoes and /publicacoes/viewer/{id})
- publicacoes_single_flight_lock_active: true (uq_publicacoes_upload_jobs_ativo_unico)
- calendario_timezone_bug_resolved: true (safe sorting of aware and naive datetimes)
- merged_to_development: true (feature/modulo-publicacoes merged into development)
- configuracoes_module_active: true
- inspecoes_module_active: true
- calendario_module_active: true
- alembic_migrations_up_to_date: true

known_gaps_from_roadmap:
- publicacoes_m0_m4_web_completed: true
- calendario_tz_sorting_bug_resolved: true
- audit_2026-05-07_resolved: true
- audit_2026-05-27_resolved: true
- ddd_decoupling_equipamentos_aeronaves_resolved: true
- data_export_csv_xlsx_v1_2_0_resolved: true
- ci_matrix_testing_workflow_resolved: true
- feature_modo_calendario_p0_p5: completed
- mobile_linha_de_voo_module_completed: true
- aircraft_status_hierarchy_sync_completed: true
- rbac_documentation_active: true
- image_pipeline_module_active: true
