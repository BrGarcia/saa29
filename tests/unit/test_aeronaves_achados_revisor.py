"""
tests/unit/test_aeronaves_achados_revisor.py
Testes de regressão para docs/backlog/revisor/achados_aeronaves.md.

Cobertura:
    BUG-01   criar_aeronave rejeita status=INSPECAO
    BUG-02/RISCO-03  listar_aeronaves não grava mais no banco (GET puro);
                     sincronizar_status_aeronave (chamada nos pontos reais
                     de mutação) continua sendo a fonte de verdade
    RISCO-04 criar_aeronave/atualizar_aeronave protegidos contra corrida de UNIQUE
    RISCO-05 toggle-status preserva o status anterior à inativação
"""

import uuid
import pytest
from datetime import date

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves import service
from app.modules.aeronaves.models import Aeronave
from app.modules.aeronaves.schemas import AeronaveCreate, AeronaveUpdate
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusAeronave


def _dados_aeronave(**overrides) -> dict:
    suffix = uuid.uuid4().hex[:8]
    dados = {
        "serial_number": f"SN-{suffix}",
        "matricula": suffix[:6],
        "modelo": "A-29",
        "data_inicio_operacao": date(2020, 1, 1),
    }
    dados.update(overrides)
    return dados


class _ContadorDeEscritas:
    """Conta INSERT/UPDATE emitidos no bloco (detecta escrita dentro de um GET)."""

    def __init__(self) -> None:
        self.total = 0

    def __enter__(self) -> "_ContadorDeEscritas":
        event.listen(Engine, "before_cursor_execute", self._registrar)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(Engine, "before_cursor_execute", self._registrar)

    def _registrar(self, conn, cursor, statement, parameters, context, executemany):
        primeira_palavra = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
        if primeira_palavra in ("INSERT", "UPDATE"):
            self.total += 1


# ------------------------------------------------------------------ #
#  BUG-01 — status INSPECAO na criação
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_aeronave_com_status_inspecao_e_rejeitada(db: AsyncSession):
    """Antes, `POST /aeronaves/` com status=INSPEÇÃO criava uma aeronave
    presa nesse status sem nenhuma Inspecao real por trás — e nenhum
    endpoint do próprio módulo conseguia tirá-la de lá depois."""
    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.criar_aeronave(
            db, AeronaveCreate(**_dados_aeronave(status=StatusAeronave.INSPECAO))
        )


# ------------------------------------------------------------------ #
#  BUG-02 / RISCO-03 — listar_aeronaves não escreve no banco
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_listar_aeronaves_nao_grava_no_banco(db: AsyncSession):
    aeronave = Aeronave(**_dados_aeronave(status=StatusAeronave.INDISPONIVEL))
    db.add(aeronave)
    await db.flush()

    with _ContadorDeEscritas() as contador:
        await service.listar_aeronaves(db)

    assert contador.total == 0


@pytest.mark.asyncio
async def test_listar_aeronaves_nao_corrige_status_orfao_silenciosamente(db: AsyncSession):
    """RISCO-03: a correção de status órfão deixou de acontecer dentro do
    GET — é responsabilidade exclusiva dos pontos reais de mutação
    (sincronizar_status_aeronave, já chamada por panes/inspecoes). Uma
    aeronave com INDISPONIVEL "preso" sem pane/inspeção real não deve mais
    ser silenciosamente corrigida só por aparecer numa listagem."""
    aeronave = Aeronave(**_dados_aeronave(status=StatusAeronave.INDISPONIVEL))
    db.add(aeronave)
    await db.flush()

    resultado = await service.listar_aeronaves(db)
    encontrada = next(a for a in resultado if a.id == aeronave.id)
    assert encontrada.status == StatusAeronave.INDISPONIVEL


# ------------------------------------------------------------------ #
#  RISCO-04 — corrida de UNIQUE
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_aeronave_savepoint_absorve_integrity_error_sem_derrubar_sessao(db: AsyncSession):
    """Força a colisão no caminho do SAVEPOINT (não no pre-check): insere a
    aeronave conflitante diretamente, simulando uma criação concorrente com
    a mesma matrícula."""
    dados = _dados_aeronave()
    conflitante = Aeronave(**dados)
    db.add(conflitante)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.criar_aeronave(db, AeronaveCreate(**_dados_aeronave(matricula=dados["matricula"])))

    # Sessão segue viva: o SAVEPOINT isolou a falha.
    outra = await service.criar_aeronave(db, AeronaveCreate(**_dados_aeronave()))
    assert outra.id is not None


@pytest.mark.asyncio
async def test_atualizar_aeronave_savepoint_absorve_integrity_error_sem_derrubar_sessao(db: AsyncSession):
    dados_conflitante = _dados_aeronave()
    conflitante = Aeronave(**dados_conflitante)
    db.add(conflitante)
    alvo = Aeronave(**_dados_aeronave())
    db.add(alvo)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.atualizar_aeronave(
            db, alvo.id, AeronaveUpdate(matricula=dados_conflitante["matricula"])
        )

    # Sessão segue viva.
    atualizada = await service.atualizar_aeronave(db, alvo.id, AeronaveUpdate(modelo="A-29B"))
    assert atualizada.modelo == "A-29B"


# ------------------------------------------------------------------ #
#  RISCO-05 — preserva status anterior à inativação
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_toggle_status_preserva_estocada_ao_reativar(db: AsyncSession):
    """Antes, reativar sempre gravava DISPONIVEL, mesmo que a aeronave
    estivesse ESTOCADA antes de ser desativada — perdendo essa informação."""
    aeronave = await service.criar_aeronave(db, AeronaveCreate(**_dados_aeronave()))
    aeronave.status = StatusAeronave.ESTOCADA
    await db.flush()

    inativada = await service.alternar_status_aeronave(db, aeronave.id)
    assert inativada.status == StatusAeronave.INATIVA
    assert inativada.status_anterior_inativacao == StatusAeronave.ESTOCADA

    reativada = await service.alternar_status_aeronave(db, aeronave.id)
    assert reativada.status == StatusAeronave.ESTOCADA
    assert reativada.status_anterior_inativacao is None


@pytest.mark.asyncio
async def test_toggle_status_disponivel_permanece_disponivel_ao_reativar(db: AsyncSession):
    aeronave = await service.criar_aeronave(db, AeronaveCreate(**_dados_aeronave()))
    assert aeronave.status == StatusAeronave.DISPONIVEL

    await service.alternar_status_aeronave(db, aeronave.id)
    reativada = await service.alternar_status_aeronave(db, aeronave.id)
    assert reativada.status == StatusAeronave.DISPONIVEL
