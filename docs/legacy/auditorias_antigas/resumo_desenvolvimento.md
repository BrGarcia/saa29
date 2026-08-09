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
- **Prorrogao de Vencimento**: Implementado modelo e UI (Roxo) para estender prazos de manuten��o com justificativa e anexo.
- **Status PENDENTE**: Criado novo status para itens instalados sem data de execu��o registrada (Cor Cinza).
- **Status FALTANTE**: Identifica��o de slots obrigat�rios vazios (Tracejado Cinza).
- **Consolida��o de Status**: A aeronave agora s� fica 'Em Dia' (Verde) se N�O houver itens pendentes ou vencidos.

## 2. Gest�o de Frota
- **Renomea��o**: 'DESATIVADA' alterado para 'ESTOCADA'.
- **Novo Status**: 'INSPE��O' (Azul) para aeronaves em manuten��o pesada.
- **Interface Centralizada**: Novo modal 'Alterar Status' na p�gina de Configura��es para transi��es r�pidas entre OPERACIONAL, ESTOCADA, INATIVA e INSPE��O.

## 3. Banco de Dados e Infra
- **Reset & Seed V2**: Criado script seed.py modular para limpeza total do ambiente e carga de dados de engenharia (PNs, Regras e Frota) via Docker.
- **Ajuste de Credenciais**: Seed agora exige senhas via .env para evitar dados sensíveis no código.
- **Docker Sync**: Sincronização de comandos para garantir que o seed afete o banco de dados dentro do container.

## 4. Reestruturação Arquitetural (Phase 1 & 2)
- **Extração de Vencimentos**: Lógica de inteligência temporal (PN, controles, prorrogações e matriz) movida do módulo Equipamentos para um novo módulo `vencimentos`.
- **Módulo de Efetivo**: Criado o módulo `efetivo` com gestão de indisponibilidades (Férias, Dispensa, etc.) integrado ao usuário.
- **Consistência de Status**: Unificação e padronização do status operacional de aeronaves para `DISPONIVEL` / `INDISPONIVEL` em todo o sistema.
