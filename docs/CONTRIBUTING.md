# CONTRIBUTING.md – Guia de Contribuição

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29  
**Metodologia:** Método Akita · **Fase atual:** Dia 3 → Dia 4

---

## 1. Contexto

A estrutura do projeto foi criada no **Dia 2 (Fundação)** do Método Akita. Todo código funcional está declarado com `raise NotImplementedError` e um comentário `# TODO (Dia 4)` que descreve o algoritmo a ser implementado.

**Sua missão como equipe de implementação:**
1. **Dia 3:** Implementar os testes nos stubs de `tests/test_*.py`
2. **Dia 4:** Substituir cada `raise NotImplementedError` pela lógica real
3. **Nunca** implementar lógica sem o teste correspondente escrito antes

---

## 2. Pré-requisitos

- Python **3.12+**
- PostgreSQL **16** (local ou Docker)
- Git configurado com seu nome e e-mail

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu@email.com"
```

---

## 3. Setup do Ambiente

```bash
# 1. Clonar repositório
git clone https://github.com/BrGarcia/saa29.git
cd saa29

# 2. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais locais

# 5. Subir banco com Docker (recomendado)
docker-compose up -d db

# 6. Aplicar migrações
alembic upgrade head

# 7. Iniciar servidor de dev
uvicorn app.main:app --reload --port 8000
```

Acesse a documentação interativa em: **http://localhost:8000/docs**

---

## 4. Fluxo de Trabalho Git

### 4.1 Nomeação de Branches

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Funcionalidade | `feat/<modulo>/<descricao>` | `feat/auth/implementar-login` |
| Correção | `fix/<modulo>/<descricao>` | `fix/panes/status-transition` |
| Teste | `test/<modulo>/<descricao>` | `test/equipamentos/heranca-controles` |
| Refatoração | `refactor/<modulo>/<descricao>` | `refactor/service/query-otimizada` |

```bash
# Sempre a partir do branch main atualizado
git checkout main
git pull
git checkout -b feat/auth/implementar-login
```

### 4.2 Convenção de Commits (Conventional Commits)

```
<tipo>(<escopo>): <descrição curta em português>

[corpo opcional explicando o porquê]
```

**Tipos válidos:**

| Tipo | Quando usar |
|------|------------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `test` | Adicionar/corrigir testes |
| `refactor` | Refatoração sem mudar comportamento |
| `docs` | Documentação |
| `chore` | Configuração, build, dependências |

**Exemplos:**
```
feat(auth): implementa login com JWT e bcrypt
test(panes): adiciona casos de teste para concluir pane
fix(equipamentos): corrige calculo de data de vencimento
```

### 4.3 Pull Request

- **Título:** seguir convenção de commits
- **Descrição:** descrever o que foi implementado e como testar
- **Checklist obrigatório antes de abrir PR:**
  - [ ] Testes escritos e passando (`pytest tests/ -v`)
  - [ ] Nenhum `raise NotImplementedError` remanescente no escopo do PR
  - [ ] Sem credenciais ou dados sensíveis no código
  - [ ] Migrações geradas se houver mudança de model

---

## 5. Regras de Implementação (Invioláveis)

> [!IMPORTANT]
> Estas regras seguem o Método Akita e **não podem ser ignoradas**.

### 5.1 TDD (Test-Driven Development)

**Primeiro o teste, depois a lógica.** Nesta ordem:

```
1. Escrever o teste (que falha)
2. Implementar o mínimo para o teste passar
3. Refatorar se necessário
```

Nunca submeta código funcional sem o teste correspondente.

### 5.2 Cada função tem um único responsável

- Cada método de `service.py` contém **uma** responsabilidade
- Não adicionar lógica de negócio nos `router.py`
- Não acessar o banco diretamente nos `router.py` — sempre via `service.py`

### 5.3 Proibido nos arquivos de router

```python
# ❌ ERRADO — lógica de negócio no router
@router.post("/panes/")
async def criar_pane(dados, db):
    if not dados.descricao:
        dados.descricao = "AGUARDANDO EDICAO"  # regra de negócio aqui!
    pane = Pane(**dados.model_dump())
    db.add(pane)

# ✅ CORRETO — delegar ao service
@router.post("/panes/")
async def criar_pane(dados, db, usuario_atual):
    return await service.criar_pane(db, dados, usuario_atual.id)
```

### 5.4 Tratamento de erros

- **ValueError** nos services → converter para `HTTPException` no router
- Todos os endpoints devem retornar erros estruturados
- Nunca expor tracebacks em produção (`app_debug=False`)

```python
# Padrão de tratamento no router
try:
    return await service.criar_usuario(db, dados)
except ValueError as e:
    raise HTTPException(status_code=409, detail=str(e))
```

---

## 6. Onde Implementar: Mapa dos TODO

Cada arquivo de serviço contém comentários com o algoritmo completo. Exemplo:

```python
# app/panes/service.py

async def concluir_pane(db, pane_id, concluido_por_id):
    """
    Algoritmo (SPECS §7 – Concluir Pane):
        1. Verificar se já está RESOLVIDA
        2. status = RESOLVIDA
        3. data_conclusao = NOW() (RN-04)
        4. concluido_por = usuário logado
        5. Salvar alterações
    """
    # TODO (Dia 4):
    # pane = await buscar_pane(db, pane_id)
    # if pane.status == StatusPane.RESOLVIDA:
    #     raise ValueError("Pane já está resolvida.")
    # ...
    raise NotImplementedError  # ← substituir pela lógica
```

### Ordem de implementação recomendada

1. `app/auth/security.py` — `hash_senha`, `verificar_senha`, `criar_token`, `decodificar_token`
2. `app/dependencies.py` — `get_current_user`
3. `app/auth/service.py` e `router.py`
4. `app/aeronaves/service.py` e `router.py`
5. `app/panes/service.py` e `router.py`
6. `app/equipamentos/service.py` e `router.py` (mais complexo — herança de controles)

---

## 7. Banco de Dados e Migrações

### Ao alterar um Model ORM:

```bash
# 1. Editar o model em app/<modulo>/models.py
# 2. Gerar a migração
alembic revision --autogenerate -m "descricao_da_mudanca"

# 3. Revisar o arquivo gerado em migrations/versions/
# 4. Aplicar
alembic upgrade head
```

> [!WARNING]
> **Nunca editar manualmente** os arquivos em `migrations/versions/`. Use sempre o Alembic.

---

## 8. Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Rodar apenas um módulo
pytest tests/test_auth.py -v

# Rodar com cobertura
pytest tests/ -v --cov=app --cov-report=html
# Relatório em: htmlcov/index.html

# Rodar apenas testes marcados
pytest tests/ -m unit
pytest tests/ -m integration
```

### Banco de testes

Os testes usam **SQLite in-memory** (via `conftest.py`). Nenhum teste deve:
- Acessar o banco PostgreSQL de desenvolvimento
- Deixar dados persistidos entre testes (rollback automático garantido pelo conftest)
- Chamar APIs externas reais (usar mocks)

---

## 9. Variáveis de Ambiente

Nunca faça commit do arquivo `.env`. O arquivo `.env.example` é o template versionado.

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | URL de conexão PostgreSQL (asyncpg) |
| `APP_SECRET_KEY` | Chave para assinar JWT — deve ser aleatória e longa |
| `JWT_EXPIRE_MINUTES` | Expiração do token (padrão: 480 = 8h) |
| `UPLOAD_DIR` | Diretório local para uploads |
| `MAX_UPLOAD_SIZE_MB` | Tamanho máximo de upload |

---

## 10. Dúvidas e Referências

- **SRS:** [`00_SRS.md`](./docs/requirements/00_SRS.md) — Requisitos funcionais e não funcionais
- **Algoritmos:** [`01_SPECS.md`](./docs/requirements/01_SPECS.md) — Fluxos e algoritmos detalhados
- **Modelo de Dados:** [`03_MODEL_DB.md`](./docs/architecture/03_MODEL_DB.md) — Entidades, relações e regras de negócio
- **Metodologia:** [`04_AKITA.MD`](./docs/methodology/04_AKITA.MD) — Método Akita completo
- **API Docs:** `http://localhost:8000/docs` (após subir o servidor)
