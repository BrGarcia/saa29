"""
app/database.py
Configuração do banco de dados: engine, sessão e Base declarativa.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


# --- Engine assíncrono ---
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# --- Fábrica de sessão ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Classe base para todos os modelos ORM do projeto.
    Todos os modelos devem herdar de Base para serem detectados
    pelo Alembic e pelo engine.
    """
    pass


async def create_all_tables() -> None:
    """
    Cria todas as tabelas no banco de dados.
    Usar apenas em desenvolvimento / testes.
    Em produção usar as migrações Alembic.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Remove todas as tabelas. Usar apenas em testes.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
