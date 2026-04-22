# Migracao: SQLite para PostgreSQL

Este guia descreve o que precisa mudar se voce quiser rodar o SAA29 com PostgreSQL em vez de SQLite.

## 1. Status Atual

Hoje o projeto roda com:

- `DATABASE_URL` padrao apontando para SQLite;
- `app/bootstrap/database.py` usando `create_async_engine`;
- `app/bootstrap/config.py` lendo a URL do banco via `.env`.

Ou seja, a aplicacao suporta um `DATABASE_URL` de Postgres, mas o ambiente precisa ter os drivers corretos instalados.

## 2. Dependencias Necessarias

Para PostgreSQL async, adicione no ambiente:

```text
asyncpg
```

Se voce usar scripts ou ferramentas sincronas externas, pode precisar de:

```text
psycopg2-binary
```

## 3. Variavel de Ambiente

No `.env`, use:

```env
DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/saa29
```

Observacoes:

- o formato `postgresql://...` nao e suficiente para o driver async;
- o projeto nao possui hoje um helper automatico para reescrever a URL;
- a configuracao em `app/bootstrap/config.py` apenas consome o valor informado.

## 4. O Que Rever no Ambiente

### Banco e migracoes

1. Crie um banco vazio no PostgreSQL.
2. Execute `python -m alembic upgrade head`.
3. Valide se as tabelas foram criadas com os tipos nativos de Postgres.

### Seed e bootstrap

- `python scripts/db/init_db.py`
- `python scripts/db/seed.py`

Esses scripts continuam validos, desde que o banco configurado em `DATABASE_URL` seja acessivel.

## 5. Pontos de Atenção

### R2 e backup

O fluxo de backup em `scripts/maintenance/r2_manager.py` e voltado para SQLite. Em PostgreSQL, esse script nao faz sentido como estrategia de persistencia do banco.

### Arquivos e anexos

O backend de arquivos continua independente do banco:

- `app/shared/core/storage.py`
- `STORAGE_BACKEND=local` ou `r2`

### UUID

Os modelos ja usam UUID. PostgreSQL lida bem com esse tipo nativamente, entao a migracao costuma ser tranquila nesse ponto.

## 6. Docker

Se voce quiser subir PostgreSQL via Docker, use um service `postgres:16` e aponte `DATABASE_URL` para o container.

## 7. Checklist

- instalar `asyncpg`;
- configurar `DATABASE_URL` para `postgresql+asyncpg://...`;
- rodar `alembic upgrade head`;
- validar `scripts/db/init_db.py` e `scripts/db/seed.py`;
- revisar qualquer automatizacao de backup SQLite;
- executar `pytest tests -q`.

## 8. Conclusao

A migracao e viavel, mas nao e transparente enquanto o projeto mantiver scripts de backup SQLite e dependencias de ambiente ainda focadas em desenvolvimento local. Antes de usar em producao, revise o fluxo operacional inteiro.
