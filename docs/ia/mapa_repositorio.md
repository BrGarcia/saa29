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
- modules/inspecoes/: isolated_backend_scaffold_not_bootstrapped
- shared/core/: enums,helpers,storage,validators,limiter,exceptions
- shared/middleware/: csrf
- web/pages/router.py: html_routes (panes,frota,inventario,vencimentos,configuracoes,efetivo,inspecoes_placeholder)
- web/templates/: jinja_templates (base,panes,aeronaves,inventario,vencimentos,configuracoes,efetivo,inspecoes_placeholder)
- web/static/js/: configuracoes.js,vencimentos.js,inventario.js,panes.js,app.js,auth_check.js
- web/static/css/: index.css (design_system_tokens_and_components)

app/modules/inspecoes:
- __init__.py: passive_package_no_router_autoimport
- models.py: TipoInspecao,TarefaTemplate,Inspecao,InspecaoTarefa
- schemas.py: local_status_enums,pydantic_contracts
- service.py: isolated_business_rules_crud_instantiation_completion
- router.py: api_router_defined_not_registered
- activation_required: bootstrap_model_import,include_router,migration,frontend_binding,tests

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
- security/: csrf_refresh
- architecture/: architecture_and_perf_guards

docs:
- architecture/: source_for_architecture
- api/: source_for_endpoints
- development/: source_for_setup_tests_ops
- requirements/: source_for_srs_specs
- ia/: summarized_machine_docs

ignore_likely:
- .venv/
- __pycache__/
- .pytest_cache/
- .mypy_cache/
- .ruff_cache/
- generated_db_files
- runtime_logs
