"""
tests/unit/test_panes_media_prioridade.py
Testes de regressão para os itens de MÉDIA prioridade de
docs/backlog/Fable5/relatorio_panes_service.md:

    #4  Anexo órfão no storage em falha de transação (e inverso em excluir_anexo)
    #28 Filtro data_fim exclui o último dia
    #31 Extensão e MIME não validados em conjunto
    #24 ValueError genérico dificulta mapeamento HTTP

Segue a mesma convenção de isolamento de tests/unit/test_panes_alta_prioridade.py:
identificadores únicos, nunca a fixture `usuario_no_banco`.
"""

import uuid
import pytest
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.panes import service
from app.modules.panes.models import Anexo, Pane
from app.modules.panes.schemas import FiltroPane, PaneCreate, PaneUpdate
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusAeronave, StatusPane


# ------------------------------------------------------------------ #
#  Helpers (mesmo padrão de test_panes_alta_prioridade.py)
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


JPEG_MINIMO = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"\xff\xd9"
)
PNG_MINIMO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeStorage:
    """Storage falso para observar upload/delete sem tocar disco."""

    def __init__(self, falhar_no_delete: bool = False):
        self.uploads: list[str] = []
        self.deletados: list[str] = []
        self._falhar_no_delete = falhar_no_delete

    async def upload(self, content: bytes, filename: str, mime: str) -> str:
        caminho = f"fake/{uuid.uuid4().hex}_{filename}"
        self.uploads.append(caminho)
        return caminho

    async def delete(self, caminho: str) -> bool:
        if self._falhar_no_delete:
            return False
        self.deletados.append(caminho)
        return True

    async def get_url(self, caminho: str) -> str:
        return caminho


# ================================================================== #
#  #4 — Anexo órfão no storage
# ================================================================== #

class TestAnexoOrfaoNoStorage:
    @pytest.mark.asyncio
    async def test_upload_compensa_storage_se_flush_falhar(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Se o registro não puder ser persistido após o upload, o arquivo deve ser removido do storage."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"O{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane upload com falha"), usuario.id
        )

        fake_storage = _FakeStorage()
        monkeypatch.setattr(service, "get_storage_service", lambda: fake_storage)

        original_flush = db.flush
        estado = {"deve_falhar": True}

        async def flush_com_falha_uma_vez():
            if estado["deve_falhar"]:
                estado["deve_falhar"] = False
                raise RuntimeError("Falha simulada no flush (ex.: violação de constraint)")
            return await original_flush()

        monkeypatch.setattr(db, "flush", flush_com_falha_uma_vez)

        with pytest.raises(RuntimeError, match="Falha simulada"):
            await service.upload_anexo(
                db, pane.id, JPEG_MINIMO, "foto.jpg", "image/jpeg", is_background=False
            )

        assert len(fake_storage.uploads) == 1
        assert fake_storage.deletados == fake_storage.uploads  # o arquivo enviado foi removido

    @pytest.mark.asyncio
    async def test_excluir_anexo_remove_registro_mesmo_se_storage_falhar(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Falha ao excluir o arquivo físico não deve impedir a remoção do registro."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"E{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane exclusão de anexo"), usuario.id
        )
        anexo = Anexo(id=uuid.uuid4(), pane_id=pane.id, caminho_arquivo="algum/caminho.jpg", tipo="IMAGEM")
        db.add(anexo)
        await db.flush()

        fake_storage = _FakeStorage(falhar_no_delete=True)
        monkeypatch.setattr(service, "get_storage_service", lambda: fake_storage)

        resultado = await service.excluir_anexo(db, pane.id, anexo.id)
        assert resultado is True

        res = await db.execute(select(Anexo).where(Anexo.id == anexo.id))
        assert res.scalar_one_or_none() is None  # removido do banco apesar da falha no storage

    @pytest.mark.asyncio
    async def test_excluir_anexo_remove_do_storage_em_caso_normal(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"N{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane exclusão normal"), usuario.id
        )
        anexo = Anexo(id=uuid.uuid4(), pane_id=pane.id, caminho_arquivo="algum/caminho2.jpg", tipo="IMAGEM")
        db.add(anexo)
        await db.flush()

        fake_storage = _FakeStorage()
        monkeypatch.setattr(service, "get_storage_service", lambda: fake_storage)

        await service.excluir_anexo(db, pane.id, anexo.id)
        assert fake_storage.deletados == ["algum/caminho2.jpg"]


# ================================================================== #
#  #28 — Filtro data_fim exclui o último dia
# ================================================================== #

class TestFiltroDataFim:
    @pytest.mark.asyncio
    async def test_data_fim_inclui_o_dia_inteiro(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"F{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane tarde {prefixo}"), usuario.id
        )

        hoje = date.today()
        # Pane aberta às 18h de hoje — com o bug antigo (<=), um filtro
        # data_fim = hoje 00:00 excluiria essa pane.
        await db.execute(
            update(Pane).where(Pane.id == pane.id).values(
                data_abertura=datetime.combine(hoje, time(18, 0), tzinfo=timezone.utc)
            )
        )
        await db.flush()

        filtros = FiltroPane(data_fim=datetime.combine(hoje, time(0, 0), tzinfo=timezone.utc))
        resultados = await service.listar_panes(db, filtros)
        ids = {p[0].id for p in resultados}
        assert pane.id in ids

    @pytest.mark.asyncio
    async def test_data_fim_ainda_exclui_o_dia_seguinte(self, db: AsyncSession):
        """Garante que o ajuste não vira um filtro sem limite superior."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"G{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao=f"Pane amanhã {prefixo}"), usuario.id
        )

        hoje = date.today()
        amanha = datetime.combine(hoje, time(10, 0), tzinfo=timezone.utc) + timedelta(days=1)
        await db.execute(update(Pane).where(Pane.id == pane.id).values(data_abertura=amanha))
        await db.flush()

        filtros = FiltroPane(data_fim=datetime.combine(hoje, time(0, 0), tzinfo=timezone.utc))
        resultados = await service.listar_panes(db, filtros)
        ids = {p[0].id for p in resultados}
        assert pane.id not in ids


# ================================================================== #
#  #31 — Coerência extensão × MIME real
# ================================================================== #

class TestCoerenciaExtensaoMime:
    @pytest.mark.asyncio
    async def test_extensao_pdf_com_conteudo_png_e_rejeitada(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"M{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane upload incoerente"), usuario.id
        )

        with pytest.raises(ValueError, match="não corresponde"):
            await service.upload_anexo(
                db, pane.id, PNG_MINIMO, "foto.pdf", "application/pdf", is_background=False
            )

    @pytest.mark.asyncio
    async def test_extensao_coerente_com_conteudo_e_aceita(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"C{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane upload coerente"), usuario.id
        )

        anexo, precisa_bg = await service.upload_anexo(
            db, pane.id, JPEG_MINIMO, "foto.jpg", "image/jpeg", is_background=False
        )
        assert anexo.id is not None
        assert precisa_bg is False


# ================================================================== #
#  #24 — Exceções de domínio no lugar de ValueError genérico
# ================================================================== #

class TestExcecoesDeDominio:
    @pytest.mark.asyncio
    async def test_editar_pane_inexistente_levanta_nao_encontrada(self, db: AsyncSession):
        with pytest.raises(domain_exc.EntidadeNaoEncontradaError) as exc_info:
            await service.editar_pane(db, uuid.uuid4(), PaneUpdate(descricao="x"), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_editar_pane_resolvida_levanta_conflito(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"X{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane já resolvida"), usuario.id
        )
        await service.concluir_pane(db, pane.id, usuario.id, "Resolvido")

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.editar_pane(db, pane.id, PaneUpdate(descricao="Nova"), usuario.id)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_editar_pane_transicao_invalida_levanta_conflito(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"Y{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane transição inválida"), usuario.id
        )
        await service.concluir_pane(db, pane.id, usuario.id, "Resolvido")

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.editar_pane(db, pane.id, PaneUpdate(descricao="Tentativa em concluída"), usuario.id)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_concluir_pane_ja_resolvida_levanta_conflito(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"Z{prefixo}")
        usuario = await _criar_usuario(db, prefixo)
        pane = await service.criar_pane(
            db, PaneCreate(aeronave_id=aeronave.id, descricao="Pane concluída 2x"), usuario.id
        )
        await service.concluir_pane(db, pane.id, usuario.id, "Resolvido")

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.concluir_pane(db, pane.id, usuario.id, "De novo")
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_concluir_pane_inexistente_levanta_nao_encontrada(self, db: AsyncSession):
        with pytest.raises(domain_exc.EntidadeNaoEncontradaError) as exc_info:
            await service.concluir_pane(db, uuid.uuid4(), uuid.uuid4(), None)
        assert exc_info.value.status_code == 404
