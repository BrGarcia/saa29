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
