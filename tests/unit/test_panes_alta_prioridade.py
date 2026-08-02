"""
tests/unit/test_panes_alta_prioridade.py
Testes de regressão para os itens de ALTA prioridade de
docs/backlog/Fable5/relatorio_panes_service.md (linhas 300-312 do relatório):

    #9  editar_pane não sincroniza status da aeronave ao resolver
    #20 _escape_like sem parâmetro escape no .like()
    #5  Background task não durável — anexos presos em "processando"
    #34 Race entre exclusão de anexo e processamento background
    #2  Race conditions (responsável duplicado)
    #3  Race condition em _sincronizar_status_aeronave_pane

Nota de isolamento: o banco de testes é SQLite in-memory compartilhado por
toda a sessão de pytest (`test_engine`, escopo "session" em conftest.py). A
fixture `db` só garante isolamento via ROLLBACK ao final do teste — qualquer
`db.commit()` explícito persiste os dados para os testes seguintes. Por isso,
aqui sempre usamos identificadores únicos (uuid) e usuários criados localmente
(nunca a fixture `usuario_no_banco`, que usa username fixo).
"""

import uuid
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.panes import service
from app.modules.panes.models import Anexo, Pane, PaneResponsavel
from app.modules.panes.schemas import AdicionarResponsavel, PaneCreate, PaneUpdate
from app.shared.core.enums import StatusAeronave, StatusPane, TipoPapel


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def _criar_aeronave(db: AsyncSession, matricula: str, status: StatusAeronave = StatusAeronave.DISPONIVEL) -> Aeronave:
    aeronave = Aeronave(
        id=uuid.uuid4(),
        serial_number=f"SN-{matricula}",
        matricula=matricula,
        modelo="A-29",
        status=status,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_usuario(db: AsyncSession, prefixo: str, funcao: str = "MANTENEDOR") -> Usuario:
    """Cria um usuário com username único — nunca colide entre testes, mesmo com commit real."""
    usuario = Usuario(
        id=uuid.uuid4(),
        nome=f"Usuario Teste {prefixo}",
        posto="Sgt",
        especialidade="ELT",
        funcao=funcao,
        ramal="0000",
        username=f"user.{prefixo}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


def _mock_session_factory(db: AsyncSession):
    """Patch de app.bootstrap.database.get_session_factory que reutiliza a
    MESMA sessão de teste (padrão já usado em tests/architecture/test_quality_helpers.py)."""
    mock_factory = MagicMock()
    mock_factory.return_value.return_value.__aenter__.return_value = db
    mock_factory.return_value.return_value.__aexit__.return_value = MagicMock()
    return mock_factory


# ================================================================== #
#  #9 + #3 — sincronização de status ao editar/resolver + lock
# ================================================================== #

class TestSincronizacaoStatusAeronave:
    @pytest.mark.asyncio
    async def test_editar_pane_para_resolvida_libera_aeronave(self, db: AsyncSession):
        """Antes: editar_pane não chamava _sincronizar_status_aeronave_pane."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"E{prefixo}", StatusAeronave.DISPONIVEL)
        usuario = await _criar_usuario(db, prefixo)

        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane teste"), usuario.id
        )
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.INDISPONIVEL

        await service.editar_pane(
            db, pane.id, PaneUpdate(status=StatusPane.RESOLVIDA), usuario.id
        )
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.DISPONIVEL

    @pytest.mark.asyncio
    async def test_editar_pane_sem_mudar_status_nao_forca_sincronizacao(self, db: AsyncSession):
        """Editar apenas a descrição não deve mexer no status da aeronave."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"D{prefixo}", StatusAeronave.DISPONIVEL)
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane teste"), usuario.id
        )
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.INDISPONIVEL

        await service.editar_pane(db, pane.id, PaneUpdate(descricao="Nova descrição"), usuario.id)
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.INDISPONIVEL

    @pytest.mark.asyncio
    async def test_sincronizar_status_usa_db_get_com_lock(self, db: AsyncSession):
        """Item #3: a função passou a usar db.get(..., with_for_update=True) — sem erros no SQLite."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"L{prefixo}", StatusAeronave.INDISPONIVEL)
        await service._sincronizar_status_aeronave_pane(db, aeronave.id)
        await db.refresh(aeronave)
        assert aeronave.status == StatusAeronave.DISPONIVEL

    @pytest.mark.asyncio
    async def test_sincronizar_status_aeronave_inexistente_nao_falha(self, db: AsyncSession):
        """Sem aeronave, a função deve retornar silenciosamente (sem NameError/AttributeError)."""
        await service._sincronizar_status_aeronave_pane(db, uuid.uuid4())


# ================================================================== #
#  #20 — _escape_like sem parâmetro escape
# ================================================================== #

class TestEscapeLikeComEscapeParam:
    @pytest.mark.asyncio
    async def test_busca_por_percentual_literal_encontra_o_registro(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict
    ):
        """Sem o parâmetro escape, o '%' escapado não teria efeito e a busca falharia."""
        headers = usuario_e_token["headers"]
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"P{prefixo}")

        resp = await client.post(
            "/panes/",
            json={"aeronave_id": str(aeronave.id), "descricao": f"Falha em 100% do sistema {prefixo}"},
            headers=headers,
        )
        assert resp.status_code == 201

        busca = await client.get("/panes/", params={"texto": f"100% do sistema {prefixo}"}, headers=headers)
        assert busca.status_code == 200
        descricoes = [p["descricao"] for p in busca.json()]
        assert any(f"100% do sistema {prefixo}" in d for d in descricoes)

    @pytest.mark.asyncio
    async def test_busca_por_underscore_nao_vira_coringa(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict
    ):
        """'_' escapado não deve casar com qualquer caractere — só com '_' literal."""
        headers = usuario_e_token["headers"]
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"U{prefixo}")

        await client.post(
            "/panes/",
            json={"aeronave_id": str(aeronave.id), "descricao": f"COD_{prefixo} com underscore literal"},
            headers=headers,
        )
        await client.post(
            "/panes/",
            json={"aeronave_id": str(aeronave.id), "descricao": f"CODX{prefixo} sem underscore"},
            headers=headers,
        )

        busca = await client.get("/panes/", params={"texto": f"cod_{prefixo}"}, headers=headers)
        assert busca.status_code == 200
        descricoes = [p["descricao"] for p in busca.json()]
        assert any(f"COD_{prefixo}" in d for d in descricoes)
        assert not any(f"CODX{prefixo}" in d for d in descricoes)


# ================================================================== #
#  #5 — job de limpeza de anexos travados em "processando"
# ================================================================== #

class TestLimpezaAnexosTravados:
    @pytest.mark.asyncio
    async def test_marca_como_erro_apenas_anexos_antigos(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"T{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane com anexo travado"), usuario.id
        )

        antigo = Anexo(id=uuid.uuid4(), pane_id=pane.id, caminho_arquivo="processando", tipo="IMAGEM")
        recente = Anexo(id=uuid.uuid4(), pane_id=pane.id, caminho_arquivo="processando", tipo="IMAGEM")
        db.add_all([antigo, recente])
        await db.flush()

        # Simula que o anexo "antigo" foi criado há 60 minutos
        await db.execute(
            update(Anexo).where(Anexo.id == antigo.id).values(
                created_at=datetime.now(timezone.utc) - timedelta(minutes=60)
            )
        )
        await db.flush()

        quantidade = await service.limpar_anexos_processando_antigos(db, minutos_limite=30)
        assert quantidade == 1

        await db.refresh(antigo)
        await db.refresh(recente)
        assert antigo.caminho_arquivo == "ERRO"
        assert recente.caminho_arquivo == "processando"


# ================================================================== #
#  #34 — race entre exclusão de anexo e processamento background
# ================================================================== #

class TestRaceProcessamentoBackground:
    @pytest.mark.asyncio
    async def test_nao_atualiza_anexo_excluido(self, db: AsyncSession):
        """O anexo foi excluído antes do background terminar: não deve ser ressuscitado."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"X{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane com race"), usuario.id
        )
        anexo_id = uuid.uuid4()
        anexo = Anexo(id=anexo_id, pane_id=pane.id, caminho_arquivo="processando", tipo="IMAGEM")
        db.add(anexo)
        await db.flush()

        # Simula a exclusão do anexo enquanto o background "processava"
        await db.delete(anexo)
        await db.flush()

        with patch("app.bootstrap.database.get_session_factory", _mock_session_factory(db)):
            atualizado = await service._atualizar_caminho_anexo_se_pendente(anexo_id, "novo/caminho.webp")
        assert atualizado is False

        res = await db.execute(select(Anexo).where(Anexo.id == anexo_id))
        assert res.scalar_one_or_none() is None  # não foi ressuscitado

    @pytest.mark.asyncio
    async def test_nao_atualiza_anexo_ja_processado(self, db: AsyncSession):
        """Se outra execução já atualizou o anexo, esta não deve sobrescrever."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"J{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane já processada"), usuario.id
        )
        anexo_id = uuid.uuid4()
        anexo = Anexo(id=anexo_id, pane_id=pane.id, caminho_arquivo="ja_processado.webp", tipo="IMAGEM")
        db.add(anexo)
        await db.flush()

        with patch("app.bootstrap.database.get_session_factory", _mock_session_factory(db)):
            atualizado = await service._atualizar_caminho_anexo_se_pendente(anexo_id, "outro/caminho.webp")
        assert atualizado is False

        await db.refresh(anexo)
        assert anexo.caminho_arquivo == "ja_processado.webp"

    @pytest.mark.asyncio
    async def test_atualiza_anexo_ainda_pendente(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"Q{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane pendente"), usuario.id
        )
        anexo_id = uuid.uuid4()
        anexo = Anexo(id=anexo_id, pane_id=pane.id, caminho_arquivo="processando", tipo="IMAGEM")
        db.add(anexo)
        await db.flush()

        with patch("app.bootstrap.database.get_session_factory", _mock_session_factory(db)):
            atualizado = await service._atualizar_caminho_anexo_se_pendente(anexo_id, "final/caminho.webp")
        assert atualizado is True

        await db.refresh(anexo)
        assert anexo.caminho_arquivo == "final/caminho.webp"


# ================================================================== #
#  #2 — race condition em adicionar_responsavel / concluir_pane
# ================================================================== #

class TestRaceResponsaveis:
    @pytest.mark.asyncio
    async def test_adicionar_responsavel_recupera_de_integrity_error(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Simula duas requisições passando na checagem prévia antes do insert (TOCTOU):
        a checagem de duplicidade é enganada para retornar False, e apenas a
        constraint UNIQUE (via IntegrityError) impede a duplicata."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"R{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane com race de responsável"), usuario.id
        )

        # Responsável já existe (simula que outra transação inseriu primeiro)
        db.add(PaneResponsavel(pane_id=pane.id, usuario_id=usuario.id, papel=usuario.funcao))
        await db.flush()

        async def checagem_enganada(*args, **kwargs):
            return False  # finge que ainda não é responsável — só o insert vai revelar o conflito

        monkeypatch.setattr(service, "_ja_e_responsavel", checagem_enganada)

        with pytest.raises(ValueError, match="já é responsável"):
            await service.adicionar_responsavel(
                db, pane.id, AdicionarResponsavel(usuario_id=usuario.id, papel=TipoPapel.MANTENEDOR)
            )

    @pytest.mark.asyncio
    async def test_constraint_unique_impede_duplicata_direta(self, db: AsyncSession):
        """A constraint UNIQUE(pane_id, usuario_id) é a rede de segurança real (migration f3c2b8a1d4e6)."""
        from sqlalchemy.exc import IntegrityError

        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"C{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane unicidade"), usuario.id
        )
        db.add(PaneResponsavel(pane_id=pane.id, usuario_id=usuario.id, papel=usuario.funcao))
        await db.flush()

        db.add(PaneResponsavel(pane_id=pane.id, usuario_id=usuario.id, papel=usuario.funcao))
        with pytest.raises(IntegrityError):
            await db.flush()

    @pytest.mark.asyncio
    async def test_concluir_pane_nao_falha_se_ja_e_responsavel_por_corrida(self, db: AsyncSession):
        """concluir_pane tenta adicionar o concluinte como responsável; se outra
        transação já o adicionou, o IntegrityError deve ser absorvido (sem 500)."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"K{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane concluir com corrida"), usuario.id
        )

        await db.refresh(pane, ["responsaveis"])
        assert pane.responsaveis == []

        # Insere o responsável "por fora" para simular a corrida com concluir_pane
        db.add(PaneResponsavel(pane_id=pane.id, usuario_id=usuario.id, papel=usuario.funcao))
        await db.flush()

        # concluir_pane vai crer que ainda não é responsável (pane.responsaveis desatualizado
        # até o refresh interno) e tentar inserir de novo — não deve estourar exceção.
        resultado = await service.concluir_pane(db, pane.id, usuario.id, "Resolvido")
        assert resultado.status == StatusPane.RESOLVIDA.value
