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
- modules/aeronaves/: aircraft_crud_status
- modules/panes/: pane_flow_attachments_responsaveis
- modules/equipamentos/: models_slots_items_installations_vencimentos_inventory
- shared/core/: enums,helpers,storage,validators,limiter,exceptions
- shared/middleware/: csrf
- web/pages/: html_routes
- web/templates/: jinja_templates
- web/static/: js_css_assets

scripts:
- db/init_db.py: bootstrap_admin_frota
- db/seed.py: dev_seed_base
- seed_equipamentos.py: seed_inventory_structure
- seed_30_panes.py: sample_panes
- run_app.py: local_run
- maintenance/r2_manager.py: sqlite_backup_restore_r2
- maintenance/reset_admin.py: admin_password_reset

tests:
- unit/: feature_and_api_behavior
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
