"""
app/database.py
Configuração do banco de dados: engine e sessão.
Focado exclusivamente em SQLite para o MVP SAA29.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Engine e SessionLocal são None até a primeira chamada a get_engine()
_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker | None = None


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM do projeto."""
    pass


def get_engine() -> AsyncEngine:
    """
    Retorna a engine assíncrona para SQLite.
    Habilita PRAGMAs foreign_keys e WAL para melhor desempenho e integridade.
    """
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_debug,
            pool_pre_ping=True,
        )

        # SQLite: habilitar foreign keys e WAL via listener no connect
        _register_sqlite_pragmas(_engine)

    return _engine


def _register_sqlite_pragmas(engine: AsyncEngine) -> None:
    """Registra PRAGMAs essenciais para SQLite."""
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def get_session_factory() -> async_sessionmaker:
    """Retorna a fábrica de sessões, criando-a na primeira chamada."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal


async def create_all_tables() -> None:
    """Cria todas as tabelas no banco de dados."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Remove todas as tabelas."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
