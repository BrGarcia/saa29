"""
tests/unit/test_panes_baixa_prioridade.py
Testes de regressão para os itens de BAIXA prioridade de
docs/backlog/Fable5/relatorio_panes_service.md:

    #14 Duplicação da subquery de ranking (listar_panes vs _get_ranking_subquery)
    #15 count() desnecessário para verificar existência (EXISTS)
    #16 Excesso de db.refresh com relacionamentos em concluir_pane
    #18 _get_year_func chama get_settings() a cada invocação

Itens #6 (imports mortos) e #23 (variáveis `resultado`→`pane`) não têm
comportamento observável — verificados por leitura de código e pela ausência
de regressão na suíte completa.
"""

import uuid
import pytest
from datetime import date

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.panes import service
from app.modules.panes.schemas import FiltroPane, PaneCreate
from app.shared.core.enums import StatusAeronave, StatusPane


# ------------------------------------------------------------------ #
#  Helpers (mesmo padrão dos demais arquivos de teste de panes)
# ------------------------------------------------------------------ #

async def _criar_aeronave(db: AsyncSession, matricula: str) -> Aeronave:
    aeronave = Aeronave(
        id=uuid.uuid4(),
        serial_number=f"SN-{matricula}",
        matricula=matricula,
        modelo="A-29",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_usuario(db: AsyncSession, prefixo: str) -> Usuario:
    usuario = Usuario(
        id=uuid.uuid4(),
        nome=f"Usuario Teste {prefixo}",
        posto="Sgt",
        especialidade="ELT",
        funcao="MANTENEDOR",
        ramal="0000",
        username=f"user.{prefixo}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


class ContadorDeQueries:
    """Conta SELECTs executados no bloco (mesmo helper usado no módulo de equipamentos)."""

    def __init__(self) -> None:
        self.total = 0

    def __enter__(self) -> "ContadorDeQueries":
        event.listen(Engine, "before_cursor_execute", self._registrar)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(Engine, "before_cursor_execute", self._registrar)

    def _registrar(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.total += 1


# ================================================================== #
#  #14 — subquery de ranking compartilhada (sem duplicação)
# ================================================================== #

class TestRankingConsistente:
    @pytest.mark.asyncio
    async def test_listar_panes_e_buscar_pane_concordam_no_codigo(self, db: AsyncSession):
        """listar_panes e buscar_pane usam o mesmo helper — o código (sequência/ano) deve bater."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"R{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane ranking {prefixo}"), usuario.id
        )

        resultado_busca = await service.buscar_pane(db, pane.id)
        assert resultado_busca is not None
        _, seq_busca, ano_busca = resultado_busca

        resultados_lista = await service.listar_panes(db, FiltroPane(aeronave_id=aeronave.id))
        item_lista = next(p for p in resultados_lista if p[0].id == pane.id)
        _, seq_lista, ano_lista = item_lista

        assert seq_busca == seq_lista
        assert ano_busca == ano_lista


# ================================================================== #
#  #15 — EXISTS no lugar de COUNT (correção comportamental preservada)
# ================================================================== #

class TestExistsPreservaComportamento:
    @pytest.mark.asyncio
    async def test_sincronizacao_com_multiplas_panes_abertas_continua_correta(self, db: AsyncSession):
        """EXISTS deve continuar detectando 'há pelo menos uma pane aberta' com N panes."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"E{prefixo}")
        usuario = await _criar_usuario(db, prefixo)

        for i in range(3):
            await service.criar_pane(
                db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane {i} {prefixo}"), usuario.id
            )
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.INDISPONIVEL

        await service._sincronizar_status_aeronave_pane(db, aeronave.id)
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.INDISPONIVEL  # ainda há panes abertas


# ================================================================== #
#  #16 — menos refresh() em concluir_pane
# ================================================================== #

class TestRefreshReduzidoEmConcluirPane:
    @pytest.mark.asyncio
    async def test_concluir_pane_retorna_relacoes_completas_sem_lazy_load_sincrono(self, db: AsyncSession):
        """Todas as relações devem continuar acessíveis sem disparar MissingGreenlet."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"Q{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane refresh {prefixo}"), usuario.id
        )

        resultado = await service.concluir_pane(db, pane.id, usuario.id, "Resolvido")

        assert resultado.status == StatusPane.RESOLVIDA.value
        assert resultado.aeronave is not None
        assert resultado.anexos == []
        assert any(r.usuario_id == usuario.id for r in resultado.responsaveis)
        assert resultado.responsavel_conclusao is not None
        assert resultado.responsavel_conclusao.id == usuario.id

    @pytest.mark.asyncio
    async def test_refresh_de_responsaveis_e_condicional_a_necessidade(self, db: AsyncSession):
        """Item #16: só recarrega `responsaveis` quando um insert foi de fato
        tentado — quando o usuário já é responsável, essa query é dispensada."""
        prefixo = uuid.uuid4().hex[:6]

        # Cenário A: concluinte NÃO é responsável ainda -> precisa inserir e recarregar.
        aeronave_a = await _criar_aeronave(db, f"A{prefixo}")
        usuario_a = await _criar_usuario(db, f"a{prefixo}")
        pane_a = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave_a.id, descricao="Pane A"), usuario_a.id
        )
        with ContadorDeQueries() as contador_com_insert:
            await service.concluir_pane(db, pane_a.id, usuario_a.id, "Resolvido")

        # Cenário B: concluinte já é o criador E foi registrado como responsável
        # na criação (mantenedor_responsavel_id) -> não precisa inserir nem recarregar.
        aeronave_b = await _criar_aeronave(db, f"B{prefixo}")
        usuario_b = await _criar_usuario(db, f"b{prefixo}")
        pane_b = await service.criar_pane(
            db,
            PaneCreate(
                aeronave_id=aeronave_b.id,
                descricao="Pane B",
                mantenedor_responsavel_id=usuario_b.id,
            ),
            usuario_b.id,
        )
        with ContadorDeQueries() as contador_sem_insert:
            await service.concluir_pane(db, pane_b.id, usuario_b.id, "Resolvido")

        assert contador_sem_insert.total < contador_com_insert.total


# ================================================================== #
#  #18 — detecção de dialeto sem parsear settings a cada chamada
# ================================================================== #

class TestDeteccaoDialeto:
    @pytest.mark.asyncio
    async def test_codigo_ddd_yy_continua_correto_apos_mudanca_de_deteccao(self, db: AsyncSession):
        """Troca de `get_settings()` por `db.bind.dialect.name` não muda o resultado do código."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"D{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane dialeto {prefixo}"), usuario.id
        )

        resultado = await service.buscar_pane(db, pane.id)
        assert resultado is not None
        _, sequencia, ano = resultado
        assert ano == date.today().year
        assert sequencia >= 1
