# Guia de Desenvolvimento – SAA29

## Ambiente de Desenvolvimento

### Requisitos
- Python 3.12+
- PostgreSQL 16 (ou Docker)
- Git 2.x

### Setup rápido

```bash
# Clonar e configurar
git clone https://github.com/BrGarcia/saa29.git
cd saa29
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # Editar .env com credenciais locais

# Banco via Docker
docker-compose up -d db

# Migrações e servidor
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

---

## Estrutura de um Módulo

Cada domínio segue o padrão abaixo. **Não desviar desta estrutura.**

```
app/<modulo>/
├── __init__.py      # Identificação do pacote
├── models.py        # Entidades ORM (SQLAlchemy)
├── schemas.py       # Validação Pydantic (entrada/saída)
├── service.py       # Regras de negócio (testável, sem HTTP)
└── router.py        # Endpoints FastAPI (sem lógica de negócio)
```

### Responsabilidades por arquivo

| Arquivo | Faz | Não faz |
|---------|-----|---------|
| `models.py` | Define tabelas e relacionamentos | Lógica de negócio |
| `schemas.py` | Valida e serializa dados | Acessa banco |
| `service.py` | Implementa algoritmos e RNs | Conhece HTTP (status codes, headers) |
| `router.py` | Recebe request, chama service, retorna response | Contém `if`s de negócio |

---

## Padrão de Implementação

### Service

```python
async def criar_pane(
    db: AsyncSession,
    dados: PaneCreate,
    criado_por_id: uuid.UUID,
) -> Pane:
    """
    Abre uma nova pane no sistema.
    
    Args:
        db: sessão de banco de dados.
        dados: schema validado com os dados da pane.
        criado_por_id: UUID do usuário autenticado.
    
    Returns:
        Objeto Pane persistido.
    
    Raises:
        ValueError: se a aeronave não existir.
    """
    aeronave = await db.get(Aeronave, dados.aeronave_id)
    if not aeronave:
        raise ValueError(f"Aeronave {dados.aeronave_id} não encontrada.")
    
    descricao = dados.descricao or "AGUARDANDO EDICAO"  # RN-05
    
    pane = Pane(
        aeronave_id=dados.aeronave_id,
        descricao=descricao,
        status=StatusPane.ABERTA,               # RN-02
        criado_por_id=criado_por_id,
    )
    db.add(pane)
    await db.flush()
    return pane
```

### Router

```python
@router.post("/", response_model=schemas.PaneOut, status_code=201)
async def criar_pane(
    dados: schemas.PaneCreate,
    db: DBSession = Depends(),
    usuario_atual: CurrentUser = Depends(),
) -> schemas.PaneOut:
    try:
        return await service.criar_pane(db, dados, usuario_atual.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## Boas Práticas de Clean Code

### Nomes
- Funções: verbos descritivos (`criar_pane`, `buscar_por_username`, `calcular_vencimento`)
- Variáveis: substantivos claros (`usuario_atual`, `data_vencimento`, não `u`, `dv`)
- Evitar abreviações desnecessárias

### Funções
- Uma função = uma responsabilidade
- Máximo **20 linhas** de lógica
- Máximo **3 parâmetros** (use schemas para agrupar se necessário)
- Se precisar de comentário para explicar o que faz: renomear

### Comentários
```python
# ✅ Explica o porquê (RN, decisão técnica)
status = StatusPane.ABERTA  # RN-02: status inicial sempre ABERTA

# ❌ Descreve o que o código já diz
status = StatusPane.ABERTA  # define o status como aberta
```

---

## Migrações Alembic

```bash
# 1. Editar model em app/<modulo>/models.py
# 2. Gerar migração
alembic revision --autogenerate -m "add_campo_x_em_tabela_y"

# 3. REVISAR o arquivo gerado em migrations/versions/
#    Verificar se detectou corretamente as mudanças

# 4. Aplicar
alembic upgrade head

# Reverter se necessário
alembic downgrade -1
```

> [!WARNING]
> Nunca editar manualmente tabelas no banco sem gerar uma migração correspondente.

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | URL PostgreSQL asyncpg |
| `APP_SECRET_KEY` | ✅ | Chave JWT (min. 32 chars aleatórios) |
| `APP_ENV` | ❌ | `development` ou `production` |
| `JWT_EXPIRE_MINUTES` | ❌ | Expiração do token (padrão: 480) |
| `UPLOAD_DIR` | ❌ | Diretório de uploads (padrão: `uploads`) |
| `MAX_UPLOAD_SIZE_MB` | ❌ | Tamanho máx upload (padrão: 10) |

Gerar uma chave segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
