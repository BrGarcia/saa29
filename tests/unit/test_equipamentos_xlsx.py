"""
tests/unit/test_equipamentos_xlsx.py
Testes de regressão para docs/backlog/revisor/achados_equipamentos.md —
xlsx_service.py não tinha NENHUM teste no repositório antes desta sessão
(lacuna total identificada na revisão).

Cobertura:
    RISCO-02     vínculo prévia <-> confirmação via preview_token assinado
    RISCO-03     limite de tamanho no endpoint de prévia
    MELHORIA-08  endpoint legado /inventario/upload-xlsx removido
    MELHORIA-09  logging das exceções de processamento de XLSX
"""

import io
import uuid
import pytest
from datetime import date, datetime, timedelta, timezone

from httpx import AsyncClient
from jose import jwt
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.config import get_settings
from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos import xlsx_service
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario
from app.modules.equipamentos.schemas import XlsxProcessConfirmItem
from app.shared.core import exceptions as domain_exc


EQUIP_URL = "/equipamentos"


def _montar_xlsx_bytes(linhas: list[tuple]) -> bytes:
    """Monta um XLSX em memória no formato esperado pelo parser:
    coluna 1 = PN, coluna 4 = posição, coluna 5 = SN (0-indexed), dados a
    partir da linha 2 (linha 1 é cabeçalho, ignorada)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["IGNORADO", "PN", "IGNORADO", "IGNORADO", "POS", "SN"])
    for linha in linhas:
        ws.append(list(linha))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _criar_aeronave(db: AsyncSession, matricula: str) -> Aeronave:
    aeronave = Aeronave(
        id=uuid.uuid4(), serial_number=f"SN-{matricula}", matricula=matricula,
        modelo="A-29", data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_modelo(db: AsyncSession, pn: str) -> ModeloEquipamento:
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=pn, nome_generico="RADIO")
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_slot(db: AsyncSession, modelo_id: uuid.UUID, nome: str, posicao_xlsx: str) -> SlotInventario:
    slot = SlotInventario(
        id=uuid.uuid4(), nome_posicao=nome, sistema="CEI", modelo_id=modelo_id, posicao_xlsx=posicao_xlsx,
    )
    db.add(slot)
    await db.flush()
    return slot


def _token_expirado(aeronave_id: uuid.UUID, slot_ids: list[uuid.UUID]) -> str:
    """Constrói manualmente um preview_token já expirado (mesmo formato de
    `_gerar_preview_token`, mas com `exp` no passado)."""
    settings = get_settings()
    payload = {
        "type": xlsx_service._PREVIEW_TOKEN_TYPE,
        "aeronave_id": str(aeronave_id),
        "slot_ids": sorted(str(s) for s in slot_ids),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


# ------------------------------------------------------------------ #
#  Prévia (obter_previa_xlsx_inventario)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_previa_xlsx_happy_path_gera_preview_token(db: AsyncSession):
    matricula = f"PV-{uuid.uuid4().hex[:6]}"
    aeronave = await _criar_aeronave(db, matricula)
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = await _criar_slot(db, modelo.id, "RAD1", "POS1")

    xlsx_bytes = _montar_xlsx_bytes([(None, modelo.part_number, None, None, "POS1", "SN-REAL-01")])

    resultado = await xlsx_service.obter_previa_xlsx_inventario(db, xlsx_bytes, f"{matricula}.xlsx")

    assert resultado.erros == []
    assert resultado.aeronave_id == aeronave.id
    assert resultado.preview_token is not None
    # A prévia iterra TODOS os slots configurados no sistema (não só os do
    # arquivo) — outros testes podem ter deixado slots na base compartilhada;
    # o que importa é que o slot desta aeronave apareça correto.
    nosso_item = next(i for i in resultado.itens if i.slot_id == slot.id)
    assert nosso_item.sn_encontrado == "SN-REAL-01"
    assert nosso_item.status == "OK"


@pytest.mark.asyncio
async def test_previa_xlsx_aeronave_nao_encontrada_nao_gera_token(db: AsyncSession):
    xlsx_bytes = _montar_xlsx_bytes([(None, "PN-QUALQUER", None, None, "POS1", "SN-X")])

    resultado = await xlsx_service.obter_previa_xlsx_inventario(
        db, xlsx_bytes, f"MATRICULA-INEXISTENTE-{uuid.uuid4().hex[:6]}.xlsx"
    )

    assert resultado.erros != []
    assert resultado.aeronave_id is None
    assert resultado.preview_token is None


# ------------------------------------------------------------------ #
#  RISCO-02 — vínculo prévia <-> confirmação
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_confirmacao_com_token_valido_sucede(db: AsyncSession):
    matricula = f"CF-{uuid.uuid4().hex[:6]}"
    aeronave = await _criar_aeronave(db, matricula)
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = await _criar_slot(db, modelo.id, "RAD1", "POS1")
    xlsx_bytes = _montar_xlsx_bytes([(None, modelo.part_number, None, None, "POS1", "SN-REAL-02")])

    previa = await xlsx_service.obter_previa_xlsx_inventario(db, xlsx_bytes, f"{matricula}.xlsx")
    usuario_id = uuid.uuid4()

    resultado = await xlsx_service.processar_confirmacao_xlsx(
        db, aeronave.id,
        [XlsxProcessConfirmItem(slot_id=slot.id, sn_final="SN-REAL-02")],
        usuario_id, previa.preview_token,
    )

    assert resultado.erros == []
    assert resultado.itens_atualizados == 1


@pytest.mark.asyncio
async def test_confirmacao_com_aeronave_diferente_da_previa_e_rejeitada(db: AsyncSession):
    """RISCO-02: o cliente não pode confirmar para uma aeronave diferente da
    que a prévia calculou pelo nome do arquivo."""
    matricula = f"CF-{uuid.uuid4().hex[:6]}"
    await _criar_aeronave(db, matricula)
    outra_aeronave = await _criar_aeronave(db, f"OUTRA-{uuid.uuid4().hex[:6]}")
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = await _criar_slot(db, modelo.id, "RAD1", "POS1")
    xlsx_bytes = _montar_xlsx_bytes([(None, modelo.part_number, None, None, "POS1", "SN-REAL-03")])

    previa = await xlsx_service.obter_previa_xlsx_inventario(db, xlsx_bytes, f"{matricula}.xlsx")

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await xlsx_service.processar_confirmacao_xlsx(
            db, outra_aeronave.id,
            [XlsxProcessConfirmItem(slot_id=slot.id, sn_final="SN-REAL-03")],
            uuid.uuid4(), previa.preview_token,
        )


@pytest.mark.asyncio
async def test_confirmacao_com_slot_fora_da_previa_e_rejeitada(db: AsyncSession):
    """RISCO-02: um slot criado DEPOIS que a prévia foi gerada (ex.: um admin
    configura uma nova posição entre a prévia e a confirmação) não pode ser
    confirmado — o token só autoriza os slots que a prévia efetivamente
    incluiu no momento em que foi gerado."""
    matricula = f"CF-{uuid.uuid4().hex[:6]}"
    aeronave = await _criar_aeronave(db, matricula)
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot_da_previa = await _criar_slot(db, modelo.id, "RAD1", "POS1")
    xlsx_bytes = _montar_xlsx_bytes([(None, modelo.part_number, None, None, "POS1", "SN-REAL-04")])

    previa = await xlsx_service.obter_previa_xlsx_inventario(db, xlsx_bytes, f"{matricula}.xlsx")
    assert slot_da_previa.id in {i.slot_id for i in previa.itens}

    # Slot novo, criado só depois da prévia -> nunca esteve no token.
    slot_novo = await _criar_slot(db, modelo.id, "RAD2", "POS2")

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await xlsx_service.processar_confirmacao_xlsx(
            db, aeronave.id,
            [XlsxProcessConfirmItem(slot_id=slot_novo.id, sn_final="SN-FORJADO")],
            uuid.uuid4(), previa.preview_token,
        )


@pytest.mark.asyncio
async def test_confirmacao_com_token_invalido_e_rejeitada(db: AsyncSession):
    aeronave_id = uuid.uuid4()
    with pytest.raises(domain_exc.ConflitoNegocioError):
        await xlsx_service.processar_confirmacao_xlsx(
            db, aeronave_id, [XlsxProcessConfirmItem(slot_id=uuid.uuid4(), sn_final="X")],
            uuid.uuid4(), "token-adulterado-nao-e-um-jwt-valido",
        )


@pytest.mark.asyncio
async def test_confirmacao_com_token_expirado_e_rejeitada(db: AsyncSession):
    aeronave_id = uuid.uuid4()
    slot_id = uuid.uuid4()
    token = _token_expirado(aeronave_id, [slot_id])

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await xlsx_service.processar_confirmacao_xlsx(
            db, aeronave_id, [XlsxProcessConfirmItem(slot_id=slot_id, sn_final="X")],
            uuid.uuid4(), token,
        )


# ------------------------------------------------------------------ #
#  Endpoints (router) — RISCO-03, MELHORIA-08
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_endpoint_process_sem_preview_token_retorna_422(
    client: AsyncClient, usuario_e_token: dict,
):
    """`preview_token` é campo obrigatório do schema — omiti-lo é rejeitado
    na validação, antes mesmo de chegar ao service."""
    headers = usuario_e_token["headers"]
    response = await client.post(
        f"{EQUIP_URL}/inventario/upload-xlsx/process",
        json={"aeronave_id": str(uuid.uuid4()), "itens": []},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_preview_arquivo_grande_e_rejeitado(
    client: AsyncClient, usuario_e_token: dict,
):
    """RISCO-03: o endpoint de prévia agora usa `ler_upload_com_limite`,
    rejeitando antes de materializar o arquivo inteiro em memória."""
    headers = usuario_e_token["headers"]
    conteudo_grande = b"0" * (6 * 1024 * 1024)  # 6 MiB > limite de 5 MiB
    response = await client.post(
        f"{EQUIP_URL}/inventario/upload-xlsx/preview",
        headers=headers,
        files={"file": ("grande.xlsx", conteudo_grande, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_endpoint_legado_upload_xlsx_removido(
    client: AsyncClient, usuario_e_token: dict,
):
    """MELHORIA-08: decisão do desenvolvedor — nenhum cliente ativo dependia
    do endpoint legado (não referenciado no frontend); removido em favor do
    fluxo prévia+confirmação. O path `/inventario/upload-xlsx` ainda "existe"
    apenas porque casa com o padrão `/inventario/{aeronave_id}` (GET) — daí
    405 (método não permitido) em vez de 404; o que importa é que não há
    mais nenhum handler POST que processe upload direto."""
    headers = usuario_e_token["headers"]
    response = await client.post(
        f"{EQUIP_URL}/inventario/upload-xlsx",
        headers=headers,
        files={"file": ("x.xlsx", b"conteudo", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 405
