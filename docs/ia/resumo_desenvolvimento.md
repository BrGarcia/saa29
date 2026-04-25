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
- docker_auto_build_on_requirements_change: sempre que requirements.txt mudar, executar docker-compose up -d --build

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
- 2026-04-24: Migração Alembic aplicada (213295655e96) — remoção da coluna periodicidade_meses da tabela tipos_controle e redução do campo nome para String(10).
- 2026-04-24: Implementado CRUD de Tipos de Controle na UI de Configurações — botões Cadastrar Tipo e Editar Tipo com modais dinâmicos e endpoints POST/PUT /equipamentos/tipos-controle.
- 2026-04-25: Implementada funcionalidade de Auto-Update no Docker — scripts/start.sh agora executa pip install no startup para garantir que dependências novas sejam instaladas automaticamente ao ligar o container.
- 2026-04-25: Adicionada regra mandatória de build imediato (`docker-compose up -d --build`) após qualquer alteração no requirements.txt para garantir prontidão do ambiente.
- 2026-04-25: Implementado o Gerenciamento de Catálogo (Part Numbers) na UI de Configurações, incluindo listagem, cadastro com validação de unicidade e armazenamento em caixa alta (uppercase).
- 2026-04-25: Criado módulo de Controle de Vencimentos — ícone de calendário adicionado à navbar entre Inventário e Frota, visível para Encarregado/Administrador.
- 2026-04-25: Implementada página /vencimentos com tabela matricial dinâmica (Frota × TipoEquipamento × Controle), seguindo o padrão do planilhão operacional real (EGIR/ELT/VADR/V-UHF2 como colunas).
- 2026-04-25: Backend otimizado para a visão matricial — endpoint GET /equipamentos/vencimentos/matriz monta a estrutura completa em 4 queries fixas (sem N+1). Colunas determinadas por ModeloEquipamento com EquipamentoControle cadastrados.
- 2026-04-25: Adicionados schemas Pydantic MatrizVencimentosOut, AeronaveMatrizOut, SlotMatrizOut, VencimentoCelulaOut para serialização da matriz.
- 2026-04-25: Adicionada rota de frontend /vencimentos e template vencimentos.html com tabela centralizada, código de cores por status (OK/VENCENDO/VENCIDO), sticky column de matrícula e modal de registro de execução por clique na célula.
