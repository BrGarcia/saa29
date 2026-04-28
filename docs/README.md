# SAA29 - Sistema de Gestao de Panes, Aeronaves e Inventario A-29

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-blue)](https://sqlite.org)
[![Uso Interno](https://img.shields.io/badge/Uso-Interno%20FAB-yellow)]()

Sistema web monolitico e modular para:

- autenticar usuarios com JWT e refresh token;
- gerenciar efetivo com RBAC;
- cadastrar aeronaves;
- registrar e acompanhar panes;
- operar inventario de equipamentos e controles de vencimento;
- armazenar anexos localmente ou em Cloudflare R2.

## Aviso Operacional

- O banco de dados atual ja esta em uso e deve ser preservado.
- Os dados das panes ja cadastradas fazem parte do ativo operacional do projeto e nao podem ser perdidos.
- Qualquer alteracao de schema, migracao, ajuste manual ou script que modifique dados deve ser executado com extremo cuidado e sempre precedido por backup do banco original.
- Scripts de seed, reset ou recriacao de base so devem ser usados em banco descartavel ou copia de trabalho, nunca na base ativa.

## Inicio Rapido

```bash
git clone <repo>
cd SAA29
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

python -m alembic upgrade head
python scripts/db/init_db.py
python scripts/run_app.py
```

Observacao:

- Antes de qualquer manutencao no banco em uso, gere backup do arquivo original e valide a mudanca em uma copia quando houver risco de impactar os registros existentes.

Documentacao interativa da API:

- `http://localhost:8000/docs`

## Stack Atual

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI |
| ORM | SQLAlchemy 2.x async |
| Banco padrao | SQLite + aiosqlite |
| Migracoes | Alembic |
| Validacao | Pydantic v2 |
| Auth | JWT (HS256) + refresh token + blacklist |
| Frontend | Jinja2 + Vanilla JS + CSS |
| Seguranca | CSRF, CSP, Zero Trust (HTML Auth), RBAC, Rate Limiting, Trusted Host |
| Upload/Storage | Local ou Cloudflare R2 |

## Arquitetura

O codigo fonte esta organizado em:

- `app/bootstrap` para configuracao, database e entrada da aplicacao;
- `app/modules/auth` para autenticacao e usuarios;
- `app/modules/aeronaves` para aeronaves;
- `app/modules/panes` para panes, anexos e responsaveis;
- `app/modules/equipamentos` para inventario e vencimentos;
- `app/shared` para enums, utilitarios, storage e middleware;
- `app/web` para rotas HTML, templates e assets.

## Documentacao

### Requisitos

- [00_SRS.md](./requirements/00_SRS.md)
- [01_SPECS.md](./requirements/01_SPECS.md)

### Arquitetura

- [overview.md](./architecture/overview.md)
- [Database.md](./architecture/Database.md)
- [ADR-001 - Stack Tecnologica](./architecture/adr/001-stack-tecnologica.md)
- [ADR-002 - Autenticacao JWT](./architecture/adr/002-autenticacao-jwt.md)
- [ADR-003 - Controles de Vencimento](./architecture/adr/003-heranca-controles-vencimento.md)

### Desenvolvimento

- [Guia de Desenvolvimento](./development/guia-desenvolvimento.md)
- [Guia de Testes](./development/guia-testes.md)
- [Migracao PostgreSQL](./development/migracao_postgresql.md)
- [Cloudflare R2](./development/cloudflare_r2.md)

### API

- [Referencia da API](./api/referencia-api.md)

### Processo

- [ROADMAP.md](./ROADMAP.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)

## Estrutura do Repositorio

```text
SAA29/
├── app/
├── data/
├── docs/
├── migrations/
├── scripts/
├── static/
├── templates/
├── tests/
├── uploads/
└── var/
```

## Execucao e Testes

```bash
# Executar aplicação
python scripts/run_app.py

# Rodar testes
pytest tests -q

# Cobertura
pytest tests --cov=app --cov-report=html
```

## Variaveis de Ambiente

As principais variaveis ficam em `.env.example`:

- `DATABASE_URL`
- `APP_ENV`
- `APP_DEBUG`
- `APP_SECRET_KEY`
- `DEFAULT_ADMIN_USER`
- `DEFAULT_ADMIN_PASSWORD`
- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`
- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_MB`
- `STORAGE_BACKEND`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_BUCKET_NAME`

## Contribuicao

Leia [CONTRIBUTING.md](./CONTRIBUTING.md) antes de iniciar qualquer alteracao.
