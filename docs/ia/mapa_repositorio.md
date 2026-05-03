# repo_map

root:
- app/: source_code
- data/: runtime_or_input_data
- docs/: official_docs
- migrations/: alembic_history
- scripts/: ops_bootstrap_seed_maintenance
- static/: legacy_static_root
- templates/: legacy_template_root
- tests/: automated_tests
- uploads/: runtime_uploads
- var/: runtime_storage

app:
- bootstrap/: config,database,dependencies,create_app
- modules/auth/: auth_users_jwt_refresh_blacklist
- modules/efetivo/: availability_absences_scales
- modules/aeronaves/: aircraft_crud_status
- modules/panes/: pane_flow_attachments_responsaveis
- modules/equipamentos/: catalog_slots_physical_items_inventory
- modules/vencimentos/: temporal_intelligence_maintenance_rules_extensions
- modules/inspecoes/: integrated_backend_active_with_task_catalog_decoupling
- shared/core/: enums,helpers,storage,validators,limiter,exceptions
- shared/middleware/: csrf
- shared/services/image/: image_processing_pipeline (validator,converter,resizer,optimizer,pipeline)
- bootstrap/config/: split_config_package (__init__.py=app_settings, image.py=image_pipeline_constants)
- web/pages/router.py: html_routes (panes,frota,inventario,vencimentos,configuracoes,efetivo,inspecoes)
- web/templates/: jinja_templates (base,panes,aeronaves,inventario,vencimentos,configuracoes,efetivo,inspecoes)
- web/static/js/: configuracoes.js,vencimentos.js,inventario.js,panes.js,app.js,auth_check.js,inspecoes.js,inspecao_detalhe.js
- web/static/css/: index.css (design_system_tokens_and_components)

app/modules/inspecoes:
- __init__.py: passive_package
- models.py: TipoInspecao,TarefaCatalogo,TarefaTemplate,Inspecao (with persistent audit),InspecaoTarefa
- schemas.py: local_status_enums,pydantic_contracts
- service.py: business_rules_crud_instantiation_completion_extras_audit
- router.py: api_router_fully_registered_and_bootstrapped

scripts:
- db/init_db.py: bootstrap_admin_frota
- db/seed.py: dev_seed_base
- seed_equipamentos.py: seed_inventory_structure_and_bootstrap_catalog
- seed_30_panes.py: sample_panes
- run_app.py: local_run
- maintenance/r2_manager.py: sqlite_backup_restore_r2
- maintenance/reset_admin.py: admin_password_reset

tests:
- unit/: feature_and_api_behavior
- unit/test_inspecoes.py: isolated_inspections_service_router_security_tests
- unit/shared/services/image/: image_pipeline_unit_tests (test_validator,test_converter,test_resizer,test_optimizer,test_pipeline)
- security/: csrf_refresh
- architecture/: architecture_and_perf_guards

docs:
- architecture/: source_for_architecture (Database.md, RBAC.md, overview.md, referencia-api.md)
- core/: source_of_truth_specs (SRS.md, SPECS.md)
- ia/: ai_context_layer (CTX.md, *.ctx files, glossario.md, mapa_repositorio.md, prompts_base.md)
- summaries/: condensed_human_docs (PROJECT_SUMMARY.md, SRS_SUMMARY.md, SPECS_SUMMARY.md, MODEL_DB_SUMMARY.md)
- guides/: operational_setup_docs (guia-desenvolvimento.md, guia-testes.md, cloudflare_r2.md, migracao_postgresql.md)
- backlog/: planning_and_bugs (implementacoes pendentes, resolvidos/)
- legacy/: historical_docs_and_archive
- tdd/: test_planning
- relatorio/: audit_reports
- methodology/: AKITA.md, DoD.md, DoR.md

ignore_likely:
- .venv/
- __pycache__/
- .pytest_cache/
- .mypy_cache/
- .ruff_cache/
- generated_db_files
- runtime_logs
