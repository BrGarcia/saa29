"""
tests/conftest.py
Fixtures compartilhadas para toda a suite de testes do SAA29.

Estratégia (Método Akita – Dia 3):
    - Banco SQLite in-memory para isolamento
    - TestClient assíncrono via httpx
    - Rollback automático após cada teste
    - Fixtures de dados e autenticação reutilizáveis
"""

import os
import sys
import threading
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Forçar storage local durante os testes
os.environ["STORAGE_BACKEND"] = "local"
os.environ["APP_ENV"] = "testing"
# Chave de assinatura da suíte. O validador de Settings exige no mínimo 32
# caracteres (app/bootstrap/config/__init__.py:144) e não abre exceção para
# APP_ENV=testing; como o CI não tem .env, sem esta linha a importação de
# `app.bootstrap.main` logo abaixo falha antes de qualquer teste rodar.
# Atribuição direta (e não `setdefault`) de propósito: este arquivo é o dono
# único de APP_SECRET_KEY durante os testes, para que o resultado não dependa
# do .env da máquina nem de variável definida no workflow.
os.environ["APP_SECRET_KEY"] = "saa29-suite-de-testes-chave-fixa-sem-valor-de-producao"

from app.bootstrap.main import app
from app.bootstrap.database import Base, dispose_engine
from app.bootstrap.dependencies import get_db, get_current_user
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha, criar_token
from app.shared.middleware.csrf import TESTING_CSRF_BYPASS_SECRET

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
    # Desliga o begin/commit implícito do driver pysqlite/aiosqlite: sem isto,
    # SAVEPOINT (`Session.begin_nested()`, usado por
    # `calendario.service.create_event_type` e — a partir da correção do
    # RISCO-01 — por `publicacoes.service._favoritar`/`obter_ou_criar_edicao`)
    # é "liberado" (RELEASE SAVEPOINT) de um jeito que o driver confunde com
    # commit implícito da transação inteira: um `session.rollback()` LOGO
    # DEPOIS não desfaz nada, e a linha sobrevive para o próximo teste que
    # reusa a mesma conexão do pool — poluição silenciosa entre testes,
    # medida e reproduzida isolando `begin_nested()` num teste mínimo antes
    # desta correção. É o workaround padrão do próprio SQLAlchemy para
    # pysqlite (aplica-se também ao aiosqlite, que envolve o mesmo sqlite3):
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    dbapi_connection.isolation_level = None


@event.listens_for(test_engine.sync_engine, "begin")
def _sqlite_begin_explicito(conn):
    # Par do listener acima: com `isolation_level = None`, o driver não abre
    # transação nenhuma sozinho — o SQLAlchemy precisa pedir o `BEGIN`
    # explicitamente aqui, ou toda escrita roda em autocommit.
    conn.exec_driver_sql("BEGIN")

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Segundos de tolerância entre o fim da suíte e o encerramento do processo.
# A suíte roda em ~2min; 120s de folga só dispara se algo estiver realmente
# travado, nunca por lentidão do runner. Configurável por variável de ambiente
# para permitir ajuste no CI sem editar código — e para tornar o próprio
# watchdog testável (com um valor ínfimo ele dispara em qualquer execução).
_TIMEOUT_ENCERRAMENTO = float(os.environ.get("SAA29_TIMEOUT_ENCERRAMENTO", "120"))


def pytest_sessionfinish(session, exitstatus):
    """Cão de guarda do encerramento do processo.

    Sintoma (só no runner Linux do Actions; não reproduz no macOS, com ou sem
    `--cov`): a suíte imprime "N passed" e o processo do pytest não sai. O job
    morre no teto de 15min do ci.yml — antes desse teto existir, duas vezes no
    limite de 6h do Actions. Na ocorrência de 2026-08-30 o log mostra
    "770 passed ... in 139.03s" seguido de "The operation was canceled" e
    "Terminate orphan process: pid (2651) (pytest)".

    O travamento é DEPOIS de tudo que o pytest reporta — o resumo e o relatório
    de cobertura já saíram —, então está em atexit, join de thread ou GC. O
    diagnóstico anterior (threads não-daemon sobreviventes, na fixture
    `criar_tabelas` abaixo) não imprimiu nada nessa ocorrência, o que descarta
    a hipótese que ele testava.

    Este timer é daemon: se o processo encerrar normalmente ele nunca dispara e
    nada muda no comportamento local. Se travar, despeja o stack de TODAS as
    threads — nomeando o culpado, que é o que faltava — e encerra com o status
    real da suíte, para que um travamento no encerramento não transforme uma
    suíte verde em job vermelho.
    """
    import faulthandler

    status = int(exitstatus)

    def _despejar_e_encerrar() -> None:
        print(
            f"\n⚠️  O processo não encerrou {_TIMEOUT_ENCERRAMENTO}s após o fim da "
            "suíte. Stack de todas as threads abaixo; encerrando à força com o "
            f"status real da suíte ({status}).",
            file=sys.stderr,
            flush=True,
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        sys.stderr.flush()
        os._exit(status)

    watchdog = threading.Timer(_TIMEOUT_ENCERRAMENTO, _despejar_e_encerrar)
    watchdog.daemon = True
    watchdog.start()


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

    # A engine da APLICAÇÃO (app/bootstrap/database.py:35) é diferente da de
    # teste acima e não era fechada por ninguém na suíte. Cada conexão do
    # aiosqlite mantém uma thread não-daemon própria, então uma conexão viva
    # aqui deixa `threading._shutdown()` esperando para sempre — o processo
    # imprime "N passed" e nunca sai.
    #
    # Confirmado pelo despejo do watchdog no run 33332855429: thread principal
    # em `threading.py:1624 _shutdown`, e uma thread viva em
    # `aiosqlite/core.py:59 _connection_worker_thread`.
    await dispose_engine()

    # Diagnóstico de processo pendurado. Agora roda DEPOIS de fechar as duas
    # engines, então qualquer thread não-daemon que apareça aqui é vazamento
    # novo, de outra origem — e o watchdog em `pytest_sessionfinish` continua
    # como rede de segurança caso ela trave a saída do processo.
    sobreviventes = [
        t for t in threading.enumerate()
        if t is not threading.main_thread() and not t.daemon
    ]
    if sobreviventes:
        print(
            f"\n⚠️  {len(sobreviventes)} thread(s) não-daemon sobrevive(m) ao fim "
            "da suíte — candidata(s) a travar a saída do processo:",
            file=sys.stderr,
        )
        for t in sobreviventes:
            print(f"    - {t.name!r} (ident={t.ident}, alive={t.is_alive()})", file=sys.stderr)


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
        try:
            yield db
            await db.flush()
        except Exception:
            await db.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    
    # Desativar rate limiting durante os testes
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
        headers={"X-Skip-CSRF": TESTING_CSRF_BYPASS_SECRET}
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
        "status": "DISPONIVEL",
        "data_inicio_operacao": "2020-01-01",
    }


@pytest.fixture
def dados_aeronave_secundaria() -> dict:
    return {
        "serial_number": "SN-0002",
        "matricula": "5901",
        "modelo": "A-29",
        "status": "DISPONIVEL",
        "data_inicio_operacao": "2020-01-01",
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
