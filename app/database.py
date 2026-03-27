"""
app/database.py
Configuração do banco de dados: engine lazy, sessão e Base declarativa.

A engine é criada sob demanda (lazy) via get_engine() para permitir
que os testes sobrescrevam a URL sem depender de asyncpg nem de um
.env configurado.
"""

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
    """
    Classe base para todos os modelos ORM do projeto.
    Todos os modelos devem herdar de Base para serem detectados
    pelo Alembic e pelo engine.
    """
    pass


def get_engine() -> AsyncEngine:
    """
    Retorna a engine assíncrona, criando-a na primeira chamada (lazy).
    Isso evita a dependência de asyncpg em tempo de importação nos testes.
    """
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_debug,
            pool_pre_ping=True,
            # pool_size/max_overflow não suportados por SQLite (usado nos testes)
            **_pool_kwargs(settings.database_url),
        )
    return _engine


def _pool_kwargs(url: str) -> dict:
    """SQLite não suporta pool_size/max_overflow — ignorar para SQLite."""
    if "sqlite" in url:
        return {}
    return {"pool_size": 10, "max_overflow": 20}


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
    """
    Cria todas as tabelas no banco de dados.
    Usar apenas em desenvolvimento / testes.
    Em produção usar as migrações Alembic.
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Remove todas as tabelas. Usar apenas em testes."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
