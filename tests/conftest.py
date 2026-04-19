"""
tests/conftest.py
Fixtures compartilhadas para toda a suite de testes do SAA29.

Estratégia (Método Akita – Dia 3):
    - Banco SQLite in-memory para isolamento
    - TestClient assíncrono via httpx
    - Rollback automático após cada teste
    - Fixtures de dados e autenticação reutilizáveis
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base
from app.dependencies import get_db, get_current_user
from app.auth.models import Usuario
from app.auth.security import hash_senha, criar_token

# --- Engine de testes (SQLite in-memory) ---
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

@event.listens_for(test_engine.sync_engine, "connect")
def _enable_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def criar_tabelas():
    """Cria todas as tabelas antes da sessão e derruba ao final."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Fundamental para evitar que o pytest "trave" após rodar todos os testes
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Sessão de banco com rollback automático após cada teste."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """AsyncClient com substituição de get_db pelo banco de testes."""
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ------------------------------------------------------------------ #
#  Fixtures de dados mockados
# ------------------------------------------------------------------ #

@pytest.fixture
def dados_usuario_valido() -> dict:
    return {
        "nome": "Ten João Silva",
        "posto": "Ten",
        "especialidade": "ELT",
        "funcao": "ADMINISTRADOR",
        "ramal": "2501",
        "username": "joao.silva",
        "password": "senha_segura_123",
    }


@pytest.fixture
def dados_usuario_secundario() -> dict:
    """Segundo usuário para testes de duplicidade."""
    return {
        "nome": "Cap Maria Santos",
        "posto": "Cap",
        "especialidade": "ELT",
        "funcao": "ENCARREGADO",
        "ramal": "2502",
        "username": "maria.santos",
        "password": "outra_senha_456",
    }


@pytest.fixture
def dados_usuario_mantenedor() -> dict:
    return {
        "nome": "Sgt Carlos Lima",
        "posto": "Sgt",
        "especialidade": "ELT",
        "funcao": "MANTENEDOR",
        "ramal": "2503",
        "username": "carlos.lima",
        "password": "senha_mantenedor_789",
    }


@pytest.fixture
def dados_aeronave_valida() -> dict:
    return {
        "serial_number": "SN-0001",
        "matricula": "5916",
        "modelo": "A-29",
        "status": "OPERACIONAL",
    }


@pytest.fixture
def dados_aeronave_secundaria() -> dict:
    return {
        "serial_number": "SN-0002",
        "matricula": "5901",
        "modelo": "A-29",
        "status": "OPERACIONAL",
    }


@pytest.fixture
def dados_equipamento_valido() -> dict:
    return {
        "part_number": "AN/ARC-182",
        "nome_generico": "VUHF2",
        "sistema": "COM",
        "descricao": "Rádio VHF/UHF principal",
    }


@pytest.fixture
def dados_tipo_controle_valido() -> dict:
    return {
        "nome": "TBV",
        "descricao": "Teste de Bancada de Verificação",
        "periodicidade_meses": 12,
    }


# ------------------------------------------------------------------ #
#  Fixture de usuário autenticado (helper reutilizável)
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture
async def usuario_no_banco(db: AsyncSession, dados_usuario_valido: dict) -> Usuario:
    """
    Cria um usuário diretamente no banco (bypass de API).
    Retorna o objeto Usuario ORM.
    """
    usuario = Usuario(
        nome=dados_usuario_valido["nome"],
        posto=dados_usuario_valido["posto"],
        especialidade=dados_usuario_valido["especialidade"],
        funcao=dados_usuario_valido["funcao"],
        ramal=dados_usuario_valido["ramal"],
        username=dados_usuario_valido["username"],
        senha_hash=hash_senha(dados_usuario_valido["password"]),
    )
    db.add(usuario)
    await db.flush()
    return usuario


@pytest_asyncio.fixture
async def usuario_e_token(
    client: AsyncClient,
    db: AsyncSession,
    dados_usuario_valido: dict,
) -> dict:
    """
    Cria um usuário no banco e gera um token JWT válido.
    Retorna {usuario, token, headers} para uso nos testes.
    """
    # Criar usuário direto no banco
    unique_username = f"{dados_usuario_valido['username']}_{uuid.uuid4().hex[:6]}"
    usuario = Usuario(
        nome=dados_usuario_valido["nome"],
        posto=dados_usuario_valido["posto"],
        especialidade=dados_usuario_valido["especialidade"],
        funcao=dados_usuario_valido["funcao"],
        ramal=dados_usuario_valido["ramal"],
        username=unique_username,
        senha_hash=hash_senha(dados_usuario_valido["password"]),
    )
    db.add(usuario)
    await db.flush()

    # Gerar token JWT
    token = criar_token(dados={"sub": usuario.username})

    return {
        "usuario": usuario,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture
async def client_autenticado(
    client: AsyncClient,
    db: AsyncSession,
    dados_usuario_valido: dict,
) -> AsyncClient:
    """
    Retorna um AsyncClient com get_current_user sobrescrito
    para retornar um usuário fixo sem precisar de token.
    Útil para testes de módulos que não são de autenticação.
    """
    # Criar usuário direto no banco
    unique_username = f"{dados_usuario_valido['username']}_{uuid.uuid4().hex[:6]}"
    usuario = Usuario(
        nome=dados_usuario_valido["nome"],
        posto=dados_usuario_valido["posto"],
        especialidade=dados_usuario_valido["especialidade"],
        funcao=dados_usuario_valido["funcao"],
        ramal=dados_usuario_valido["ramal"],
        username=unique_username,
        senha_hash=hash_senha(dados_usuario_valido["password"]),
    )
    db.add(usuario)
    await db.flush()

    # Sobrescrever get_current_user para retornar este usuário direto
    async def override_get_current_user():
        return usuario

    app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Limpar apenas get_current_user, mantendo get_db
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]


@pytest_asyncio.fixture
async def usuario_mantenedor_e_token(
    db: AsyncSession,
    dados_usuario_mantenedor: dict,
) -> dict:
    """Cria um mantenedor autenticado para testes de autorização."""
    usuario = Usuario(
        nome=dados_usuario_mantenedor["nome"],
        posto=dados_usuario_mantenedor["posto"],
        especialidade=dados_usuario_mantenedor["especialidade"],
        funcao=dados_usuario_mantenedor["funcao"],
        ramal=dados_usuario_mantenedor["ramal"],
        username=dados_usuario_mantenedor["username"],
        senha_hash=hash_senha(dados_usuario_mantenedor["password"]),
    )
    db.add(usuario)
    await db.flush()

    token = criar_token(dados={"sub": usuario.username})
    return {
        "usuario": usuario,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture
async def usuario_encarregado_e_token(
    db: AsyncSession,
    dados_usuario_secundario: dict,
) -> dict:
    """Cria um encarregado autenticado para testes de autorização."""
    usuario = Usuario(
        nome=dados_usuario_secundario["nome"],
        posto=dados_usuario_secundario["posto"],
        especialidade=dados_usuario_secundario["especialidade"],
        funcao=dados_usuario_secundario["funcao"],
        ramal=dados_usuario_secundario["ramal"],
        username=dados_usuario_secundario["username"],
        senha_hash=hash_senha(dados_usuario_secundario["password"]),
    )
    db.add(usuario)
    await db.flush()

    token = criar_token(dados={"sub": usuario.username})
    return {
        "usuario": usuario,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }
