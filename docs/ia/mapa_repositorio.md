# repo_map

root:
- app/: source_code
- data/: runtime_or_input_data
- docs/: official_docs
- migrations/: alembic_history
- scripts/: ops_bootstrap_seed_maintenance_publicacoes
- static/: legacy_static_root
- templates/: legacy_template_root
- tests/: automated_tests
- uploads/: runtime_uploads
- var/: runtime_storage

app:
- bootstrap/: config,database,dependencies,create_app,tasks,events
- modules/auth/: auth_users_jwt_refresh_blacklist
- modules/efetivo/: availability_absences_scales
- modules/aeronaves/: aircraft_crud_status
- modules/panes/: pane_flow_attachments_responsaveis_export
- modules/equipamentos/: catalog_slots_physical_items_inventory_export
- modules/vencimentos/: temporal_intelligence_maintenance_rules_extensions
- modules/inspecoes/: integrated_backend_active_with_task_catalog_decoupling_export_pdf
- modules/calendario/: calendar_events_api_and_business_logic_dpe_aggregation_safe_tz_sorting
- modules/publicacoes/: acervo_catalog_search_fts5_avulsas_favoritos_edicoes_upload_jobs_m4_web
- modules/dashboard/: consolidated_operational_metrics_and_summary
- shared/contracts.py: ddd_domain_lookup_protocols (AeronaveLookupProtocol)
- shared/exporter.py: generic_csv_and_xlsx_report_generator
- shared/core/: enums,helpers,storage,validators,limiter,exceptions
- shared/middleware/: csrf
- shared/services/image/: image_processing_pipeline (validator,converter,resizer,optimizer,pipeline)
- bootstrap/config/: split_config_package (__init__.py=app_settings, image.py=image_pipeline_constants)
- web/pages/router.py: html_routes (panes,frota,inventario,vencimentos,configuracoes,efetivo,inspecoes,publicacoes,mobile /m/)
- web/templates/: jinja_templates (base,panes,aeronaves,inventario,vencimentos,configuracoes,efetivo,inspecoes,publicacoes,mobile)
- web/static/js/: configuracoes.js,configuracoes_publicacoes.js,vencimentos.js,inventario.js,panes.js,app.js,auth_check.js,inspecoes.js,inspecao_detalhe.js,publicacoes.js,publicacoes_explorador.js,publicacoes_viewer.js,publicacoes_avulsas.js,mobile/
- web/static/css/: index.css,publicacoes.css,mobile.css

app/modules/publicacoes:
- __init__.py: passive_package
- models.py: ManualEdicao,ManualDocumento,ManualFimMap,PublicacaoAvulsa,PublicacaoFavorito,PublicacoesUploadJob,PublicacaoAcesso
- schemas.py: pydantic_contracts_for_catalog_search_avulsas_edicoes_uploads
- catalog.py: lucene_and_fim_index_parser_and_database_builder
- search.py: sqlite3_fts5_bm25_search_engine_with_snippet_sentinels
- avulsas.py: avulsas_crud_vigencia_and_snippet_building
- service.py: business_logic_edicoes_favoritos_status_caminho_indice
- router.py: api_router_fully_registered_with_upload_endpoints_and_pdf_streaming

app/modules/inspecoes:
- __init__.py: passive_package
- models.py: TipoInspecao,TarefaCatalogo,TarefaTemplate,Inspecao,InspecaoTarefa
- schemas.py: local_status_enums,pydantic_contracts
- service.py: business_rules_crud_instantiation_completion_extras_audit
- pdf_service.py: reportlab_pdf_generator_for_inspection_orders_and_checklists
- router.py: api_router_fully_registered_and_bootstrapped

app/modules/calendario:
- __init__.py: passive_package
- models.py: EventType,CalendarEvent (with UTCDateTime decorator)
- schemas.py: pydantic_contracts
- service.py: business_logic_dpe_aggregation_safe_tz_sorting
- router.py: api_router

scripts:
- db/init_db.py: bootstrap_admin_frota
- db/seed.py: dev_seed_base
- seed_equipamentos.py: seed_inventory_structure_and_bootstrap_catalog
- seed_30_panes.py: sample_panes
- publicacoes/indexar.py: index_manuals_into_fts5_catalog_db
- publicacoes/publicar.py: publication_pipeline_zip_validation_worker
- publicacoes/merge_data.py: merge_new_edition_remessa
- run_app.py: local_run
- maintenance/r2_manager.py: sqlite_backup_restore_r2

tests:
- unit/: feature_and_api_behavior (including test_publicacoes_*.py, test_zip_validator.py, test_mobile.py)
- integration/: test_publicacoes_busca.py, test_mobile_integration.py
- test_calendario.py: full_calendar_test_suite
- test_exporter.py: csv_and_xlsx_export_unit_tests

docs:
- architecture/: Database.md, RBAC.md, overview.md, referencia-api.md, adr/ (ADR-001..004)
- core/: source_of_truth_specs (SRS.md, SPECS.md)
- ia/: ai_context_layer (CTX.md, *.ctx files, glossario.md, mapa_repositorio.md, prompts_base.md, prompt_codex.md)
- summaries/: condensed_human_docs (PROJECT_SUMMARY.md, SRS_SUMMARY.md, SPECS_SUMMARY.md, MODEL_DB_SUMMARY.md)
- guides/: operational_setup_and_governance (guia-desenvolvimento.md, guia-testes.md, cloudflare_r2.md, sugestao_envio.md, operacao_publicacoes.md)
- backlog/: active_planning_and_bugs (modulo_publicacoes/, feature_controle_pedidos.md)

ignore_likely:
- .venv/
- __pycache__/
- .pytest_cache/
- .mypy_cache/
- .ruff_cache/
- generated_db_files
- runtime_logs
