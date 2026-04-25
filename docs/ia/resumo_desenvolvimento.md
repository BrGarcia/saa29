# dev_summary

requirements:
- python: 3.12_plus
- vcs: git
- db_local: sqlite (var/db)
- db_optional: postgresql_with_asyncpg
- system_deps: python-magic-bin (for windows MIME detection)

local_setup:
- create_venv
- install_requirements: pip install -r requirements.txt
- install_windows_fix: pip install python-magic-bin
- copy_env_example_to_env
- run_migrations: python -m alembic upgrade head
- run_app: python -m scripts.run_app

testing_state:
- status: 100_percent_pass
- total_tests: 93
- run_all: python -m pytest
- run_by_domain:
    - auth: python -m pytest tests/unit/test_auth.py
    - operational: python -m pytest tests/unit/test_aeronaves.py tests/unit/test_panes.py
    - logistics: python -m pytest tests/unit/test_equipamentos.py tests/unit/test_inventario.py

key_architectural_patterns:
- modular_monolith
- repository_service_pattern
- async_sqlalchemy_2_0
- pydantic_v2_schemas
- jinja2_htmx_style_frontend

env_critical_vars:
- DATABASE_URL
- SECRET_KEY
- STORAGE_BACKEND (local | r2)
- UPLOAD_DIR
- JWT_ALGORITHM

# Recent Implementations (April 2026)

## 1. Mdulo de Vencimentos & Prorrogao
- **Prorrogao de Vencimento**: Implementado modelo e UI (Roxo) para estender prazos de manutenção com justificativa e anexo.
- **Status PENDENTE**: Criado novo status para itens instalados sem data de execução registrada (Cor Cinza).
- **Status FALTANTE**: Identificação de slots obrigatórios vazios (Tracejado Cinza).
- **Consolidação de Status**: A aeronave agora só fica 'Em Dia' (Verde) se NÃO houver itens pendentes ou vencidos.

## 2. Gestão de Frota
- **Renomeação**: 'DESATIVADA' alterado para 'ESTOCADA'.
- **Novo Status**: 'INSPEÇÃO' (Azul) para aeronaves em manutenção pesada.
- **Interface Centralizada**: Novo modal 'Alterar Status' na página de Configurações para transições rápidas entre OPERACIONAL, ESTOCADA, INATIVA e INSPEÇÃO.

## 3. Banco de Dados e Infra
- **Reset & Seed V2**: Criado script seed_v2.py para limpeza total do ambiente e carga de dados de engenharia (PNs, Regras e Frota) via Docker.
- **Ajuste de Credenciais**: Seed agora exige senhas via .env para evitar dados sensíveis no código.
- **Docker Sync**: Sincronização de comandos para garantir que o seed afete o banco de dados dentro do container.
