# Guia de Desenvolvimento – SAA29

## Ambiente de Desenvolvimento

### Requisitos
- Python 3.12+
- Git 2.x
- SQLite (padrão dev/local) ou PostgreSQL 16+ (opcional para produção)

### Setup rápido

```bash
# Clonar e configurar
git clone https://github.com/BrGarcia/saa29.git
cd saa29
python -m venv .venv
# Ativar venv:
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Editar .env se necessário

# Migrações e inicialização de dados (Frota padrão)
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

---

## Banco de Dados (SQLite)

O SAA29 utiliza **SQLite** + **aiosqlite** como stack padrão.

### Características implementadas:
- **Integridade:** `PRAGMA foreign_keys=ON` ativado via listener.
- **Performance:** `PRAGMA journal_mode=WAL` para reduzir bloqueios de leitura.
- **Migrações:** Configurado com `render_as_batch=True` no Alembic.

### Manutenção Básica:
- **Backup:** Basta copiar o arquivo `.db` (Ex: `cp saa29_local.db backup.db`).
- **Inspeção:** Utilize `sqlite3 saa29_local.db` ou ferramentas como DBeaver/DB Browser for SQLite.

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
    """
    aeronave = await db.get(Aeronave, dados.aeronave_id)
    if not aeronave:
        raise ValueError(f"Aeronave {dados.aeronave_id} não encontrada.")
    
    pane = Pane(
        aeronave_id=dados.aeronave_id,
        descricao=dados.descricao or "AGUARDANDO EDICAO",
        status=StatusPane.ABERTA,
        criado_por_id=criado_por_id,
    )
    db.add(pane)
    await db.flush()
    return pane
```

---

## Migrações Alembic

```bash
# 1. Editar model em app/<modulo>/models.py
# 2. Gerar migração (Batch mode automático para SQLite)
alembic revision --autogenerate -m "nome_da_migracao"

# 3. REVISAR o arquivo gerado em migrations/versions/
# 4. Aplicar
alembic upgrade head
```

> [!WARNING]
> Para SQLite, o Alembic usa `batch_alter_table`. Verifique se o script gerado segue este padrão para evitar erros de "Table locked" ou falhas em `ALTER COLUMN`.

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | URL do banco (Ex: `sqlite+aiosqlite:///./saa29.db`) |
| `APP_SECRET_KEY` | ✅ | Chave JWT (Não use a palavra "INSECURE" em produção) |
| `ALLOWED_HOSTS` | ✅ | `*` ou lista separada por vírgula para domínios permitidos |
| `ALLOWED_ORIGINS` | ✅ | `*` ou lista separada por vírgula para CORS |
| `GUNICORN_WORKERS` | ❌ | Número de workers (Padrão: 2. Recomendado: 1 ou 2 para SQLite) |
| `APP_ENV` | ❌ | `development` ou `production` |
| `JWT_EXPIRE_MINUTES` | ❌ | Expiração do token em minutos (Padrão: 120) |
| `UPLOAD_DIR` | ❌ | Diretório de uploads (Padrão: `uploads`) |

---

## Deploy no Railway (SQLite)

O SAA29 está pronto para o Railway utilizando SQLite.

### Passos:
1.  **Networking:** Configure a porta **8000** em *Settings -> Networking*.
2.  **Variables:** Use o editor *Raw* e cole as variáveis do `.env`.
3.  **Persistência:** Para manter os dados após deploys, crie um **Volume** e monte em `/app/data`. Ajuste a `DATABASE_URL` para `sqlite+aiosqlite:////app/data/saa29.db`.


Gerar uma chave segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
