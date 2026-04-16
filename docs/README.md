# SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-blue)](https://sqlite.org)
[![License](https://img.shields.io/badge/Uso-Interno%20FAB-yellow)]()

Sistema web para **registro e acompanhamento de panes de manutenção aeronáutica** do A-29 Super Tucano. 

---

## Início Rápido (Local)

```bash
git clone https://github.com/BrGarcia/saa29.git
cd saa29
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Banco SQLite já configurado no template
alembic upgrade head          # Cria o banco local saa29_local.db
uvicorn app.main:app --reload # Inicia servidor: http://localhost:8000
```

📖 **API Docs:** `http://localhost:8000/docs`

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| **Backend** | FastAPI 0.115 (Python 3.12) |
| **Banco de Dados** | SQLite + aiosqlite (Local/Produção) |
| **ORM / Migrações** | SQLAlchemy 2.x + Alembic |
| **Frontend** | HTML5 (Jinja2) + Vanilla JS + CSS Glassmorphism |
| **Segurança** | JWT (OAuth2) + RBAC (3 níveis) |
| **Qualidade** | Pytest (Async) + GitHub Actions |

---

## Hub de Documentação

### 📐 Requisitos e Especificações
- [`00_SRS.md`](./requirements/00_SRS.md): Requisitos de Software.
- [`01_SPECS.md`](./requirements/01_SPECS.md): Especificação de Algoritmos.
- [`03_MODEL_DB.md`](./architecture/03_MODEL_DB.md): Dicionário de Dados.

### 🏛️ Arquitetura e Decisões
- [`overview.md`](./architecture/overview.md): Visão geral do sistema.
- [`ADR-001: Stack Tecnológica`](./architecture/adr/001-stack-tecnologica.md).
- [`ADR-002: Autenticação JWT`](./architecture/adr/002-autenticacao-jwt.md).

### ⚙️ Desenvolvimento e APIs
- [`Guia de Desenvolvimento`](./development/guia-desenvolvimento.md): Setup e padrões.
- [`Guia de Testes`](./development/guia-testes.md): TDD e Cobertura.
- [`Referência API`](./api/referencia-api.md): Endpoints e payloads.

### 🔄 Processo e Histórico
- [`ROADMAP.md`](./ROADMAP.md): Planejamento de fases.
- [`CHANGELOG.md`](./CHANGELOG.md): Histórico de versões.
- [`CONTRIBUTING.md`](./CONTRIBUTING.md): Guia de contribuição.

---

## Estrutura do Projeto

```
SAA29/
├── app/                → Código fonte (FastAPI)
├── docs/               → Documentação técnica completa
├── migrations/         → Versionamento de banco de dados
├── scripts/            → Utilitários de inicialização e seed
├── static/             → Ativos frontend (CSS, JS, Imagens)
├── templates/          → Interface Jinja2
└── tests/              → Suíte de testes automatizados
```

---

*Uso interno – Força Aérea Brasileira.*

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

---

## Contribuindo

Leia o [CONTRIBUTING.md](./CONTRIBUTING.md) antes de iniciar qualquer implementação.

---

*Uso interno – Força Aérea Brasileira.*
