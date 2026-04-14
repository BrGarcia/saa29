# Visão Geral da Arquitetura – SAA29

## 1. Estilo Arquitetural

O sistema adota **Arquitetura em Camadas** (_Layered Architecture_) com separação clara de responsabilidades:

```
┌─────────────────────────────────────────────────────┐
│                   CLIENTE (Browser)                  │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP/REST (JSON)
┌───────────────────▼─────────────────────────────────┐
│              Router Layer (FastAPI)                  │
│  Valida entrada · autenticação · serialização       │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│             Service Layer (Python)                   │
│  Regras de negócio · algoritmos · orquestração      │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│            Repository Layer (SQLAlchemy)             │
│  Queries · ORM · transações · persistência          │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│       PostgreSQL 16 / SQLite (banco de dados)       │
└─────────────────────────────────────────────────────┘
```

> **Regra fundamental:** Dependências apontam sempre para baixo. O Router nunca acessa o banco diretamente. O Service nunca conhece detalhes HTTP.

---

## 2. Estrutura de Módulos

```
app/
├── core/           → Enums e tipos compartilhados entre domínios
├── auth/           → Autenticação · Efetivo (usuários)
├── aeronaves/      → Gestão de aeronaves
├── equipamentos/   → Equipamentos · Itens · Controles de vencimento
└── panes/          → Panes · Anexos · Responsáveis
```

Cada módulo segue a estrutura:
```
<modulo>/
├── __init__.py
├── models.py    → ORM (SQLAlchemy) – entidades do banco
├── schemas.py   → Pydantic – validação de entrada/saída
├── service.py   → Regras de negócio (sem HTTP, sem ORM direto)
└── router.py    → Endpoints FastAPI (sem lógica de negócio)
```

---

## 3. Fluxo de uma Requisição

```
POST /panes/
    │
    ▼
router.py::criar_pane()
    │  Valida schema (Pydantic)
    │  Extrai usuário do JWT
    │
    ▼
service.py::criar_pane(db, dados, criado_por_id)
    │  Verifica aeronave existe
    │  Aplica RN-02 (status=ABERTA)
    │  Aplica RN-05 (descricao padrão)
    │
    ▼
ORM (SQLAlchemy)
    │  INSERT INTO panes ...
    │
    ▼
PostgreSQL
    │
    ▼
PaneOut (Pydantic) → JSON response
```

---

## 4. Diagrama de Entidades (resumido)

```
 usuarios ──────────┐
    │               │ criado_por / concluido_por
    │               ▼
aeronaves ──────► panes ──────► anexos
    │               │
    │               └──────────► pane_responsaveis ◄── usuarios
    │
    ▼
instalacoes ◄── itens_equipamento ◄── equipamentos
                     │                    │
                     ▼                    ▼
           controle_vencimentos ◄── equipamento_controles
                     │
                     ▼
               tipos_controle
```

Diagrama completo: [`03_MODEL_DB.md`](./03_MODEL_DB.md)

---

## 5. Decisões de Arquitetura (ADRs)

| ADR | Decisão |
|-----|---------|
| [ADR-001](./adr/001-stack-tecnologica.md) | Stack: FastAPI + SQLAlchemy 2 + PostgreSQL/SQLite |
| [ADR-002](./adr/002-autenticacao-jwt.md) | Autenticação stateless via JWT |

---

## 6. Considerações Não Funcionais

| Requisito | Estratégia |
|-----------|-----------|
| Desempenho < 2s | Queries async, índices no banco, pool de conexões |
| Segurança | JWT + bcrypt + validação Pydantic + MIME check no upload |
| Escalabilidade | PostgreSQL relacional, UUIDs, pool configurável |
| Testabilidade | Service layer desacoplado, SQLite in-memory nos testes |
| Manutenibilidade | Tipagem estrita, stubs documentados, ADRs |
