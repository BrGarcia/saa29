"""
tests/conftest.py
Fixtures compartilhadas entre todos os testes do SAA29.

Estratégia (Método Akita – Dia 3):
    - Banco de dados em memória (SQLite) para isolamento
    - TestClient assíncrono via httpx
    - Rollback automático após cada teste
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base
from app.dependencies import get_db

# --- Engine de testes (SQLite in-memory) ---
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def criar_tabelas():
    """
    Cria todas as tabelas no banco de testes antes da sessão de testes.
    Remove após o fim da sessão.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """
    Fornece uma sessão de banco isolada para cada teste.
    Faz rollback automático após o teste para evitar contaminação de dados.
    """
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """
    TestClient assíncrono com a dependência get_db sobrescrita
    para usar o banco de testes.
    """
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# --- Fixtures de dados mockados ---

@pytest.fixture
def dados_usuario_valido() -> dict:
    """Dados válidos para criação de um usuário de teste."""
    return {
        "nome": "Ten João Silva",
        "posto": "Ten",
        "especialidade": "ELT",
        "funcao": "INSPETOR",
        "ramal": "2501",
        "username": "joao.silva",
        "password": "senha_segura_123",
    }


@pytest.fixture
def dados_aeronave_valida() -> dict:
    """Dados válidos para criação de uma aeronave de teste."""
    return {
        "serial_number": "SN-0001",
        "matricula": "5900",
        "modelo": "A-29",
        "status": "OPERACIONAL",
    }


@pytest.fixture
def dados_pane_valida(dados_aeronave_valida: dict) -> dict:
    """Dados válidos para criação de uma pane de teste."""
    return {
        "sistema_subsistema": "COMUNICAÇÃO / VUHF",
        "descricao": "Rádio não transmite na frequência 120.500 MHz",
    }


@pytest.fixture
def dados_equipamento_valido() -> dict:
    """Dados válidos para criação de um equipamento de teste."""
    return {
        "part_number": "AN/ARC-182",
        "nome": "VUHF2",
        "sistema": "COM",
        "descricao": "Rádio VHF/UHF principal",
    }
