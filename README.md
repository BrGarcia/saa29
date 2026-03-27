# SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

Sistema web para **registro e acompanhamento de panes** de manutenção aeronáutica, desenvolvido para o A-29 Super Tucano.

---

## Stack

| Componente | Tecnologia |
|-----------|-----------|
| Backend | FastAPI 0.115 + Python 3.12 |
| ORM | SQLAlchemy 2.x (async) |
| Banco | PostgreSQL 16 |
| Migrações | Alembic |
| Validação | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt |
| Testes | Pytest + httpx (async) |
| Container | Docker + Docker Compose |

---

## Estrutura de Pastas

```
SAA29/
├── app/
│   ├── core/           # Enums e shared
│   ├── auth/           # Autenticação e usuários
│   ├── aeronaves/      # Gestão de aeronaves
│   ├── equipamentos/   # Equipamentos, itens e vencimentos
│   └── panes/          # Panes, anexos e responsáveis
├── migrations/         # Alembic (env.py, versions/)
├── tests/              # Pytest (conftest, test_*.py)
├── .env.example        # Template de variáveis de ambiente
├── docker-compose.yml  # PostgreSQL + API
├── Dockerfile          # Imagem da API
├── requirements.txt    # Dependências
└── alembic.ini         # Configuração do Alembic
```

---

## Pré-requisitos

- Python 3.12+
- PostgreSQL 16 (ou Docker)
- pip

---

## Como Executar

### 1. Clone e configure o ambiente

```bash
git clone <repo>
cd SAA29

# Copiar e preencher variáveis de ambiente
cp .env.example .env

# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate      # Windows
# ou: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

### 2. Com Docker (recomendado)

```bash
# Sobe PostgreSQL + API
docker-compose up -d

# Acompanhar logs
docker-compose logs -f api
```

### 3. Sem Docker (desenvolvimento local)

```bash
# PostgreSQL deve estar rodando localmente com os dados do .env

# Executar migrações
alembic upgrade head

# Iniciar servidor de desenvolvimento
uvicorn app.main:app --reload --port 8000
```

---

## Migrações

```bash
# Gerar nova migração (após alterar models)
alembic revision --autogenerate -m "descricao_da_mudanca"

# Aplicar migrações
alembic upgrade head

# Reverter última migração
alembic downgrade -1
```

---

## Testes

```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=html
```

---

## Endpoints Principais

| Módulo | Endpoint | Método | Descrição |
|--------|---------|--------|-----------|
| Auth | `/auth/login` | POST | Login (retorna JWT) |
| Auth | `/auth/me` | GET | Dados do usuário logado |
| Aeronaves | `/aeronaves/` | GET/POST | CRUD de aeronaves |
| Equipamentos | `/equipamentos/` | GET/POST | CRUD de equipamentos |
| Equipamentos | `/equipamentos/itens` | POST | Criar item (herança automática) |
| Equipamentos | `/equipamentos/vencimentos/{id}/executar` | PATCH | Registrar execução |
| Panes | `/panes/` | GET/POST | Listar/criar panes |
| Panes | `/panes/{id}/concluir` | POST | Concluir pane |
| Panes | `/panes/{id}/anexos` | POST | Upload de imagem |

Documentação interativa disponível em: `http://localhost:8000/docs`

---

## Módulos

### `app/auth` — Autenticação e Efetivo
RF-01, RF-02, RF-14. Login via JWT, cadastro de usuários com funções (Inspetor, Encarregado, Mantenedor).

### `app/aeronaves` — Gestão de Aeronaves
RF-15. CRUD de aeronaves com controle de status operacional.

### `app/equipamentos` — Controle de Equipamentos
RF-16. Rastreabilidade por número de série, controle de vencimentos com herança automática por tipo.

### `app/panes` — Gestão de Panes
RF-03 a RF-13. Registro, acompanhamento e conclusão de panes com upload de imagens.

---

## Regras de Negócio Principais

| Código | Regra |
|--------|-------|
| RN-01 | Pane deve estar vinculada a uma aeronave |
| RN-02 | Status inicial de pane = ABERTA |
| RN-03 | Apenas panes ABERTA/EM_PESQUISA podem ser editadas |
| RN-04 | `data_conclusao` gerada automaticamente ao concluir |
| RN-05 | Descrição vazia → "AGUARDANDO EDICAO" |

---

## Licença

Uso interno – Força Aérea Brasileira.
