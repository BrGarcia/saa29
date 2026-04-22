"""
migrations/env.py
Ambiente Alembic para o projeto SAA29.
Suporta migração síncrona (padrão Alembic) e async (via asyncio.run).
Compatível com SQLite (render_as_batch) e PostgreSQL.
"""

import asyncio
from logging.config import fileConfig
import os

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# --- Importar todos os models para que o Alembic detecte as tabelas ---
# IMPORTANTE: Esta seção deve ser mantida atualizada com todos os módulos.
from app.bootstrap.database import Base  # noqa: F401 – Base com metadata
from app.bootstrap.config import get_settings

# Módulos de models (garante que as tabelas estejam no metadata)
import app.modules.auth.models         # noqa: F401
import app.modules.aeronaves.models    # noqa: F401
import app.modules.equipamentos.models # noqa: F401
import app.modules.panes.models        # noqa: F401

# Objeto de metadata que o Alembic usará para detectar mudanças
target_metadata = Base.metadata

# Configuração do arquivo alembic.ini
config = context.config

# Sobrescrever DATABASE_URL a partir das configurações (que lêem do .env)
settings = get_settings()
database_url = settings.database_url

# Definir a URL no config do Alembic (mantendo o driver async para online mode)
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Detectar se estamos usando SQLite para habilitar batch mode
_using_sqlite = "sqlite" in database_url.lower()


def run_migrations_offline() -> None:
    """
    Executa as migrações em modo 'offline' (sem conexão ativa).
    Gera scripts SQL para revisão manual antes de aplicar.
    """
    url = config.get_main_option("sqlalchemy.url")
    # Para o modo offline (que é síncrono), precisamos garantir um driver síncrono para SQLite
    if url and "aiosqlite" in url:
        url = url.replace("sqlite+aiosqlite", "sqlite")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=_using_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Executa migrações com uma conexão ativa."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=_using_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Versão assíncrona para compatibilidade com asyncpg/aiosqlite."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Executa as migrações em modo 'online'.
    Chamado pelo alembic upgrade/downgrade.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
