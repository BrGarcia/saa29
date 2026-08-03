"""
tests/unit/test_bootstrap_resiliencia.py
Testes de regressão para os achados de docs/backlog/Fable5/Etapa5.md
relacionados a infraestrutura (app/bootstrap/):

    #2  PRAGMA busy_timeout ausente no listener de conexão SQLite
    #6  Cancelamento de tasks de background sem espera no shutdown
    #8  Prefixo do calendário ausente no handler de redirect
    #9  Nenhum handler para exceções não tratadas
"""

import asyncio
import os
import tempfile

import pytest
from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.bootstrap.database import _register_sqlite_pragmas


# ------------------------------------------------------------------ #
#  #2 — busy_timeout
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_register_sqlite_pragmas_configura_busy_timeout():
    """Verifica diretamente que o listener de conexão usado pela aplicação
    real (`app.bootstrap.database._register_sqlite_pragmas`) aplica um
    busy_timeout maior que o default de 5000ms do driver — sem repetir aqui
    o teste de estresse com 30 escritores concorrentes que motivou a
    correção (lento demais para rodar a cada suíte; foi feito manualmente
    antes de aplicar o fix, ver Etapa5.md)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _register_sqlite_pragmas(engine)

    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA busy_timeout"))
        valor = result.scalar()

    await engine.dispose()
    assert valor is not None and valor > 5000, (
        f"busy_timeout={valor} — deve ser maior que o default de 5000ms do driver."
    )


@pytest.mark.asyncio
async def test_escritores_concorrentes_nao_falham_com_busy_timeout_configurado():
    """Reproduz, em escala menor (rápida o suficiente para CI), a contenção
    que motivou o item #2: múltiplos escritores tentando BEGIN IMMEDIATE ao
    mesmo tempo no mesmo arquivo SQLite. Sem busy_timeout suficiente, uma
    fração falha com `database is locked`."""
    db_path = os.path.join(tempfile.gettempdir(), f"busy_test_{os.getpid()}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    _register_sqlite_pragmas(engine)

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))

        SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
        erros = []

        async def escritor(n: int):
            try:
                async with SessionLocal() as s:
                    await s.execute(text("BEGIN IMMEDIATE"))
                    await asyncio.sleep(0.1)
                    await s.execute(text(f"INSERT INTO t (v) VALUES ('w{n}')"))
                    await s.commit()
            except Exception as exc:
                erros.append((n, exc))

        await asyncio.gather(*[escritor(i) for i in range(10)])
        assert not erros, f"{len(erros)}/10 escritores falharam mesmo com busy_timeout configurado: {erros[:2]}"
    finally:
        await engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


# ------------------------------------------------------------------ #
#  #6 — shutdown aguarda cancelamento das tasks
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_gather_apos_cancel_aguarda_tasks_sem_propagar_cancelled_error():
    """Reproduz o padrão aplicado em app/bootstrap/events.py: cancelar uma
    task e aguardá-la via asyncio.gather(..., return_exceptions=True) não
    deve propagar CancelledError nem deixar a task "solta" (pending) depois
    do shutdown — o problema original era não aguardar de jeito nenhum."""
    async def tarefa_de_fundo():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            raise

    t1 = asyncio.create_task(tarefa_de_fundo())
    t2 = asyncio.create_task(tarefa_de_fundo())
    await asyncio.sleep(0)  # deixa as tasks iniciarem

    t1.cancel()
    t2.cancel()
    # Não deve levantar CancelledError nem qualquer outra exceção aqui.
    await asyncio.gather(t1, t2, return_exceptions=True)

    assert t1.done() and t2.done()
    assert t1.cancelled() and t2.cancelled()


# ------------------------------------------------------------------ #
#  #8 — prefixo do calendário no handler de redirect
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_calendario_sem_auth_com_accept_html_retorna_401_json_nao_redirect(
    client: AsyncClient,
):
    """Antes: /api/v1/calendario/ não estava na lista de prefixos de API do
    handler global, então um 401 vindo de um cliente que aceitasse
    text/html virava um redirect 307 para /login em vez de JSON 401."""
    resp = await client.get(
        "/api/v1/calendario/tipos",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert resp.headers.get("content-type", "").startswith("application/json")


# ------------------------------------------------------------------ #
#  #9 — handler genérico para exceções não tratadas
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_excecao_nao_tratada_retorna_500_json_sem_stack_trace():
    """Monta uma rota que propositalmente levanta uma exceção não tipada,
    num app isolado com os mesmos handlers da aplicação real, e confirma
    que o cliente recebe um 500 JSON genérico — sem stack trace."""
    from fastapi import APIRouter, FastAPI
    from httpx import ASGITransport
    from app.shared.core.exceptions import setup_exception_handlers

    app = FastAPI()
    setup_exception_handlers(app, api_prefixes=[])
    router = APIRouter()

    @router.get("/explode")
    async def explode():
        raise RuntimeError("segredo interno que não deve vazar ao cliente")

    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        resp = await c.get("/explode")

    assert resp.status_code == 500
    body = resp.json()
    assert body == {"detail": "Erro interno do servidor."}
    assert "segredo interno" not in resp.text
    assert "Traceback" not in resp.text
