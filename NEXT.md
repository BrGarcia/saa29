# NEXT.md – Guia do Desenvolvedor: Próximos Passos

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29  
**Atualizado em:** 2026-03-28  
**Branch atual:** `main`  
**Versão atual:** `0.4.1` (Estável)

---

## 📊 Onde Estamos

| Fase | Status | Dia |
|------|--------|-----|
| ✅ Fase 1 – Fundação | Concluída | Dia 2 |
| ✅ Fase 2 – Testes | Concluída | Dia 3 |
| ✅ Fase 3 – Codificação | Concluída | Dia 4 |
| ✅ Fase 3.5 – Migração e Seed | Concluída | Dia 5 |
| ✅ Fase 4 – Otimização | Concluída | Dia 5 |
| ✅ Fase 5 – Interface | Concluída | Dia 6 |
| 🔲 Fase 6 – Deploy/CI | Pendente | Dia 7 |

> **Resumo:** Backend e Frontend concluídos com sucesso (Estável 0.5.0) com UI em Glassmorphism e RBAC nativo.
> Faltam: **Módulo de Equipamentos (UI)** (Opcional) e **Deploy (CI/CD)**.

---

## 🚀 Ao Abrir o Projeto: Checklist Inicial

Antes de codar qualquer coisa, faça o setup do ambiente:

### 1. Clonar e Instalar

```bash
git clone https://github.com/BrGarcia/saa29.git
cd saa29
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/Mac
```

Edite o `.env` com credenciais reais:
- `DATABASE_URL` — PostgreSQL local ou Docker
- `APP_SECRET_KEY` — uma string longa e aleatória (use `python -c "import secrets; print(secrets.token_hex(32))"`)

### 3. Subir o Banco de Dados

```bash
docker compose up -d db
```

Aguarde o healthcheck ficar healthy:
```bash
docker compose ps
```

### 4. Rodar os Testes (Validar o Estado Atual)

```bash
pytest tests/ -v
```

> ✅ **Todos os 26 testes devem passar.** Se algo falhar, resolva antes de prosseguir.

---

## ⚠️ PRÓXIMO PASSO IMEDIATO: Fase 3.5 – Migração e Seed

> Estes 3 itens ficaram pendentes da Fase 3. **São pré-requisito para tudo o que vem depois.**

### Passo 1 – Gerar a Migração Inicial

```bash
alembic revision --autogenerate -m "initial_schema"
```

Revise o arquivo gerado em `migrations/versions/` — verifique se todas as 11 tabelas estão presentes:
- `usuarios`, `aeronaves`
- `equipamentos`, `tipos_controle`, `equipamento_controles`
- `itens_equipamento`, `instalacoes`, `controles_vencimento`
- `panes`, `anexos`, `pane_responsaveis`

### Passo 2 – Aplicar a Migração

```bash
alembic upgrade head
```

Conecte no PostgreSQL e confirme que as tabelas foram criadas:
```bash
docker exec -it saa29_db psql -U saa29_user -d saa29_db -c "\dt"
```

### Passo 3 – Criar o Script de Seed

Crie o arquivo `scripts/seed.py` com dados iniciais:

```python
"""
scripts/seed.py
Popula o banco de dados com dados iniciais para desenvolvimento.
Executar: python -m scripts.seed
"""
import asyncio
from app.database import async_session
from app.auth.security import hash_senha
from app.auth.models import Usuario
from app.aeronaves.models import Aeronave

async def seed():
    async with async_session() as session:
        # Usuário admin
        admin = Usuario(
            username="admin",
            nome_completo="Administrador SAA29",
            senha_hash=hash_senha("admin123"),
            is_admin=True,
        )
        session.add(admin)

        # Aeronaves A-29 (exemplos)
        matriculas = ["FAB 5700", "FAB 5701", "FAB 5702", "FAB 5703", "FAB 5704"]
        for mat in matriculas:
            session.add(Aeronave(matricula=mat))

        await session.commit()
        print(f"✅ Seed concluído: 1 admin + {len(matriculas)} aeronaves")

if __name__ == "__main__":
    asyncio.run(seed())
```

> ⚠️ **Adapte os models e imports** conforme a implementação real. O exemplo acima é um template.

Execute:
```bash
python -m scripts.seed
```

### ✅ Critério de Aceite da Fase 3.5
- [x] Migração gerada e revisada
- [x] `alembic upgrade head` sem erros
- [x] Tabelas visíveis no PostgreSQL
- [x] Script de seed funciona e popula dados iniciais
- [x] Testes continuam 100% PASSED

---

## 🔲 Fase 4 – Otimização (Dia 5)

> **Pré-requisito:** Fase 3.5 concluída + todos os testes passando.

### Checklist de Tarefas

| # | Tarefa | Comando/Ação | Prioridade |
|---|--------|-------------|-----------|
| 1 | Resolver queries N+1 | Adicionar `selectinload` / `joinedload` nos services | 🔴 Alta |
| 2 | Criar índices no banco | Nova migração Alembic com `op.create_index(...)` conforme [`03_MODEL_DB.md §6`](./docs/architecture/03_MODEL_DB.md) | 🔴 Alta |
| 3 | Implementar paginação | Adicionar `limit`/`offset` nos endpoints de listagem | 🟡 Média |
| 4 | Cache de aeronaves | Implementar cache in-memory (TTL de 5 min) para `listar_aeronaves()` | 🟡 Média |
| 5 | Refatorar métodos longos | Quebrar services com mais de 50 linhas em métodos menores | 🟢 Baixa |
| 6 | Cobertura de testes ≥ 80% | `pytest --cov=app --cov-report=term-missing tests/` | 🔴 Alta |
| 7 | Linter | `pip install ruff && ruff check app/` — corrigir tudo | 🟡 Média |
| 8 | Type checking | `pip install mypy && mypy app/` — corrigir erros | 🟡 Média |

### Sequência Recomendada

```
1. ruff check app/          → limpar warnings/erros de estilo
2. mypy app/                → garantir tipagem correta
3. Resolver N+1 queries     → editar services
4. Criar migração de índices → alembic + aplicar
5. Implementar paginação    → editar routers e services
6. Cache de aeronaves       → implementar
7. Refatorar métodos longos → dividir
8. pytest --cov             → garantir ≥ 80%
```

### ✅ Critério de Aceite da Fase 4
- [x] `ruff check app/` — zero erros
- [x] `mypy app/` — zero erros
- [x] `pytest --cov=app tests/` — cobertura adequada (testes críticos rodados)
- [x] Nenhuma query N+1 nos endpoints principais
- [x] Paginação funcionando em `/panes` e `/aeronaves`

---

## ✅ Fase 5 – Interface Frontend (Concluída)

> **Pré-requisito:** Fase 4 concluída (API estável e otimizada).

### Decisão de Stack

Discutir com a equipe qual abordagem utilizar:

| Opção | Prós | Contras |
|-------|------|---------|
| **HTML + HTMX + Jinja2** | Simples, sem build step, ideal para MVP | Menos interativo |
| **Next.js** | SPA moderna, excelente UX | Complexidade, precisa de Node.js |
| **HTML + Vanilla JS** | Zero dependências extras | Mais código manual |

> **Implementação Concluída:** HTML + Vanilla JS + Jinja2 Templates com CSS Glassmorphism nativo.

### Telas Implementadas

| # | Tela | Requisito | Descrição |
|---|------|-----------|-----------|
| 1 | **Login** | RF-01 | Formulário username/senha integrado ao JWT e RBAC |
| 2 | **Dashboard** | RF-03, 04, 05 | Tabela Operacional e Cards Dinâmicos (abertas/pesquisa) |
| 3 | **Histórico** | RF-06 | Tabela com log de ocorrências, formato DDD/YY e Lixeira (Soft Delete) |
| 4 | **Nova Pane** | RF-07 | Cadastro Ágil + Upload Transparente de Arquivo |
| 5 | **Detalhe da Pane** | RF-09 | Modo analise exclusivo com botões de fluxo |
| 6 | **Ações na Pane** | RF-10, 11, 12 | Atualização em tempo real do workflow e responsáveis (`Concluir`/`Assumir`) |
| 7 | **Cadastro de Efetivo** | RF-14 | Modal de usuários restrito `ADMINISTRADOR` |
| 8 | **Cadastro de Aeronaves** | RF-15 | Lista operacional e modal de baseamento de Frota |

### ✅ Critério de Aceite da Fase 5
- [x] Todas as telas Essenciais (RF-01, 15) prontas
- [x] Autenticação JWT gravada no Client via LocalStorage
- [x] Upload multi-part funcionando para imagens nativamente
- [x] Layout master Glassmorphism escuro de alta performance (UI/UX limpa)
- [x] Regras de restrição RBAC atuando no Sidebar

---

## 🔲 Fase 6 – Deploy e CI/CD (Dia 7)

> **Pré-requisito:** Frontend funcional (Fase 5).

### Checklist de Tarefas

| # | Tarefa | Detalhes |
|---|--------|---------|
| 1 | **GitHub Actions – Testes** | Pipeline que roda `pytest tests/ -v` a cada push |
| 2 | **GitHub Actions – Linter** | `ruff check app/` no CI |
| 3 | **GitHub Actions – Types** | `mypy app/` no CI |
| 4 | **Ambiente de Produção** | Configurar VPS ou Coolify |
| 5 | **Variáveis Seguras** | `.env` de produção com secrets reais |
| 6 | **HTTPS** | Certificado SSL (Let's Encrypt via Caddy ou Nginx) |
| 7 | **Backup PostgreSQL** | Cron job com `pg_dump` diário |
| 8 | **Monitoramento** | Uptime monitor (UptimeRobot ou similar) |

### Exemplo de GitHub Actions (`.github/workflows/ci.yml`)

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
          POSTGRES_DB: test_db
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
      - run: ruff check app/
```

### ✅ Critério de Aceite da Fase 6
- [ ] CI rodando a cada push (testes + linter)
- [ ] Aplicação acessível via URL pública
- [ ] HTTPS ativo com certificado válido
- [ ] Backup automático configurado
- [ ] Monitoramento de uptime ativo

---

## 📋 Resumo Executivo: O Que Fazer

```
┌─────────────────────────────────────────────────────────────┐
│                    ORDEM DE EXECUÇÃO                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CONCLUÍDO → Fase 5: Interface Master (0.5.0)              │
│                                                             │
│  AGORA     → Fase 6: Deploy + CI/CD                        │
│             (Deploy de Produção ou CI em Actions)           │
│                                                             │
│  FUTURO    → Implementação de Telas de Equipamentos        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Comando Rápido para Começar

```bash
# 1. Ativar ambiente
.venv\Scripts\activate

# 2. Subir banco
docker compose up -d db

# 3. Validar estado atual
pytest tests/ -v

# 4. Gerar migração (PRÓXIMO PASSO)
alembic revision --autogenerate -m "initial_schema"
```

---

> **Referências:**
> - [ROADMAP.md](./ROADMAP.md) — roteiro completo de fases
> - [CHANGELOG.md](./CHANGELOG.md) — histórico de versões
> - [CONTRIBUTING.md](./CONTRIBUTING.md) — guia de contribuição
> - [README.md](./README.md) — visão geral do projeto
> - [docs/requirements/00_SRS.md](./docs/requirements/00_SRS.md) — especificação de requisitos
> - [docs/requirements/01_SPECS.md](./docs/requirements/01_SPECS.md) — especificação de algoritmos
> - [docs/architecture/03_MODEL_DB.md](./docs/architecture/03_MODEL_DB.md) — modelo de banco de dados
