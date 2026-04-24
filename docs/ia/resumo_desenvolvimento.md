# dev_summary

requirements:
- python: 3.12_plus
- vcs: git
- db_local: sqlite
- db_optional: postgresql_with_asyncpg

local_setup:
- create_venv
- install_requirements
- copy_env_example_to_env
- run: python -m alembic upgrade head
- run: python scripts/db/init_db.py
- optional: python scripts/db/seed.py
- optional: python scripts/seed_equipamentos.py
- optional: python scripts/seed_30_panes.py
- run_app: python scripts/run_app.py

dev_rules:
- keep_router_thin
- keep_business_logic_in_service
- update_docs_after_behavior_change
- review_alembic_migration_before_apply
- preserve_active_database
- backup_original_db_before_schema_or_data_change
- do_not_reset_or_reseed_active_db
- prefer_testing_db_changes_on_copy_before_apply

db_safety:
- active_db_contains_registered_panes
- current_db_must_not_be_recreated
- seed_scripts_only_on_disposable_database
- any_manual_db_change_requires_backup_of_original_file

tests:
- full: pytest tests -q
- unit: pytest tests/unit -q
- security: pytest tests/security -q
- architecture: pytest tests/architecture -q
- coverage: pytest tests --cov=app --cov-report=html

important_scripts:
- scripts/run_app.py
- scripts/db/init_db.py
- scripts/db/seed.py
- scripts/maintenance/r2_manager.py
- scripts/maintenance/reset_admin.py

env_keys_main:
- DATABASE_URL
- APP_ENV
- APP_DEBUG
- APP_SECRET_KEY
- DEFAULT_ADMIN_USER
- DEFAULT_ADMIN_PASSWORD
- JWT_ALGORITHM
- JWT_EXPIRE_MINUTES
- UPLOAD_DIR
- MAX_UPLOAD_SIZE_MB
- STORAGE_BACKEND
- R2_ACCOUNT_ID
- R2_ACCESS_KEY_ID
- R2_SECRET_ACCESS_KEY
- R2_ENDPOINT
- R2_BUCKET_NAME

recent_implementations:
- 2026-04-24: Implementado o módulo de Configurações (UI), centralizando a gestão de Frota (Cadastro, Desativação, Reativação de Aeronaves com validações pré-save) e Administração de Efetivo.
- 2026-04-24: Ícone de Efetivo removido da navbar superior e migrado para dentro de Configurações. Modal de edição de aeronaves restaurado na página de Frota.
- 2026-04-24: Redesign do modelo de controles de vencimento — periodicidade_meses migrada de tipos_controle para equipamento_controles (ADR-004), permitindo que o mesmo código de controle (ex TLV) tenha valores distintos por equipamento.

