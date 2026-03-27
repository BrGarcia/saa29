# SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)
[![License](https://img.shields.io/badge/Uso-Interno%20FAB-yellow)]()

Sistema web para **registro e acompanhamento de panes de manutenção aeronáutica** do A-29 Super Tucano. Desenvolvido seguindo o **Método Akita** e práticas de Clean Code e TDD.

---

## Início Rápido

```bash
git clone https://github.com/BrGarcia/saa29.git
cd saa29
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # Editar com suas credenciais
docker-compose up -d db       # Sobe PostgreSQL
alembic upgrade head          # Aplica migrações
uvicorn app.main:app --reload # Inicia servidor
```

📖 **API Docs:** `http://localhost:8000/docs`

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Framework Web | FastAPI 0.115 |
| ORM | SQLAlchemy 2.x (async) |
| Banco de Dados | PostgreSQL 16 |
| Migrações | Alembic |
| Validação | Pydantic v2 |
| Autenticação | JWT (python-jose) + bcrypt |
| Testes | Pytest + httpx (async) |
| Container | Docker + Docker Compose |

---

## Funcionalidades (MVP)

| RF | Funcionalidade | Status |
|----|---------------|--------|
| RF-01/02 | Autenticação JWT | 🏗️ Estruturado |
| RF-03/04/05 | Dashboard de panes com cards e cores | 🏗️ Estruturado |
| RF-06 | Filtros (texto, status, aeronave, data) | 🏗️ Estruturado |
| RF-07/08 | Registro de nova pane (fluxo guiado) | 🏗️ Estruturado |
| RF-09 | Visualização detalhada da pane | 🏗️ Estruturado |
| RF-10/11/12 | Editar, anexar imagem, concluir pane | 🏗️ Estruturado |
| RF-14/15/16 | Cadastros: efetivo, aeronaves, equipamentos | 🏗️ Estruturado |

---

## Estrutura do Projeto

```
SAA29/
├── app/
│   ├── core/           → Enums compartilhados
│   ├── auth/           → Autenticação e efetivo
│   ├── aeronaves/      → Gestão de aeronaves
│   ├── equipamentos/   → Equipamentos, itens e vencimentos
│   └── panes/          → Panes, anexos e responsáveis
├── docs/
│   ├── architecture/   → Visão geral e ADRs
│   ├── agile/          → Definition of Done e Ready
│   ├── development/    → Guias técnicos
│   └── api/            → Referência da API
├── migrations/         → Alembic (env.py, versions/)
└── tests/              → Pytest (conftest + test_*.py)
```

---

## Documentação

### 📐 Requisitos e Especificações
| Documento | Descrição |
|-----------|-----------|
| [`00_SRS.md`](./docs/requirements/00_SRS.md) | Software Requirements Specification |
| [`01_SPECS.md`](./docs/requirements/01_SPECS.md) | Especificação de Algoritmos e Fluxos |
| [`03_MODEL_DB.md`](./docs/architecture/03_MODEL_DB.md) | Modelo de Banco de Dados |
| [`04_AKITA.MD`](./docs/methodology/04_AKITA.MD) | Metodologia de Desenvolvimento |

### 🏛️ Arquitetura
| Documento | Descrição |
|-----------|-----------|
| [`docs/architecture/overview.md`](./docs/architecture/overview.md) | Visão geral da arquitetura |
| [`docs/architecture/adr/001-stack-tecnologica.md`](./docs/architecture/adr/001-stack-tecnologica.md) | ADR-001: Stack tecnológica |
| [`docs/architecture/adr/002-autenticacao-jwt.md`](./docs/architecture/adr/002-autenticacao-jwt.md) | ADR-002: Autenticação JWT |
| [`docs/architecture/adr/003-heranca-controles-vencimento.md`](./docs/architecture/adr/003-heranca-controles-vencimento.md) | ADR-003: Herança de controles |

### ⚙️ Desenvolvimento
| Documento | Descrição |
|-----------|-----------|
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Guia para contribuidores |
| [`docs/development/guia-desenvolvimento.md`](./docs/development/guia-desenvolvimento.md) | Padrões de código e setup |
| [`docs/development/guia-testes.md`](./docs/development/guia-testes.md) | TDD, fixtures e métricas |
| [`docs/api/referencia-api.md`](./docs/api/referencia-api.md) | Referência dos endpoints |

### 🔄 Processo Ágil
| Documento | Descrição |
|-----------|-----------|
| [`ROADMAP.md`](./ROADMAP.md) | Roteiro de entregas por fase |
| [`docs/agile/definition-of-done.md`](./docs/agile/definition-of-done.md) | Critérios de conclusão |
| [`docs/agile/definition-of-ready.md`](./docs/agile/definition-of-ready.md) | Critérios de início |
| [`CHANGELOG.md`](./CHANGELOG.md) | Histórico de versões |

### 🔒 Segurança e Conduta
| Documento | Descrição |
|-----------|-----------|
| [`SECURITY.md`](./SECURITY.md) | Política de segurança |
| [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) | Código de conduta |

---

## Fase Atual

> **Método Akita – Dia 2 (Fundação) ✅ Concluído**
>
> Toda a estrutura está criada com stubs documentados. A equipe de implementação deve prosseguir para:
>
> **Dia 3:** Implementar os testes (`tests/test_*.py`)  
> **Dia 4:** Implementar a lógica (substituir `raise NotImplementedError`)

Veja o [ROADMAP.md](./ROADMAP.md) para o roteiro completo de entregas.

---

## Testes

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

---

## Contribuindo

Leia o [CONTRIBUTING.md](./CONTRIBUTING.md) antes de iniciar qualquer implementação.

---

*Uso interno – Força Aérea Brasileira.*
