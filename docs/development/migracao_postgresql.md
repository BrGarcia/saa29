# Guia de Migração: SQLite para PostgreSQL

Este documento descreve os passos necessários para migrar o SAA29 de SQLite para PostgreSQL, caso o sistema precise de maior concorrência, escalabilidade ou recursos avançados de banco de dados.

## 1. Dependências do Sistema
O PostgreSQL exige drivers específicos para comunicação assíncrona (via SQLAlchemy) e síncrona (via scripts/Alembic).

No `requirements.txt`, adicione:
```text
asyncpg==0.30.0          # Driver assíncrono para SQLAlchemy
psycopg2-binary==2.9.10  # Driver síncrono para Alembic e scripts
```

No `Dockerfile`, adicione a biblioteca de cliente do Postgres:
```dockerfile
RUN apt-get update && apt-get install -y libpq-dev gcc ...
```

## 2. Variáveis de Ambiente
Altere a `DATABASE_URL` no seu arquivo `.env` ou no painel do Railway:

```env
# Formato para SQLAlchemy 2.0+ com driver assíncrono
DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/nome_do_banco
```

## 3. Ajustes no Código

### app/config.py
Reintroduza o validador para garantir que a URL fornecida pelo Railway (que geralmente começa com `postgresql://`) seja convertida para o formato assíncrono exigido pelo SQLAlchemy (`postgresql+asyncpg://`):

```python
@model_validator(mode="after")
def fix_database_url(self) -> "Settings":
    if self.database_url.startswith("postgresql://"):
        self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return self
```

### app/database.py
Para PostgreSQL, é recomendado configurar o pool de conexões (o SQLite não utiliza pool da mesma forma):

```python
def get_engine() -> AsyncEngine:
    ...
    # Adicione parâmetros de pool para Postgres
    _engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    ...
```

### app/panes/service.py
A função de extração de ano no Postgres utiliza `EXTRACT`. Certifique-se de que a função `_get_year_func` suporte o dialeto `postgresql`:

```python
def _get_year_func(column):
    # No Postgres o padrão é func.extract('year', column)
    return func.extract("year", column)
```

## 4. Migração de Dados (Opcional)
Se você já tiver dados no SQLite e quiser levá-los para o Postgres, a ferramenta recomendada é o **[pgloader](https://pgloader.io/)**:

```bash
pgloader ./saa29_local.db postgresql://usuario:senha@localhost/saa29
```

## 5. Docker Compose
Para rodar um banco Postgres localmente via Docker, adicione o serviço ao `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: saa29
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  pg_data:
```

## 6. Considerações sobre UUIDs
O SAA29 já utiliza `UUID` como chave primária. O PostgreSQL possui um tipo nativo `UUID`, enquanto o SQLite armazena como `CHAR(32)`. Ao migrar, o SQLAlchemy/Alembic tratará a conversão, mas certifique-se de rodar `alembic upgrade head` em um banco Postgres vazio para criar o schema com os tipos nativos corretos.
