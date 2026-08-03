"""
tests/security/test_panes_achados_revisor.py
Testes de regressão para os achados de docs/BACKLOG/revisor/achados_panes.md:

    BUG-01   GET /panes/export retornava 500 em toda chamada
    RISCO-04 Content-Type do cliente chegando ao storage no fallback de background
    RISCO-10 Export sem filtros de data/texto e sem sinalização de truncamento
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.panes import service
from tests.unit.test_panes import criar_aeronave, criar_pane


PANES_URL = "/panes/"
EXPORT_URL = "/panes/export"


# ================================================================== #
#  BUG-01 — GET /panes/export não pode mais retornar 500
# ================================================================== #

@pytest.mark.asyncio
async def test_export_csv_nao_retorna_mais_500(
    client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict
):
    """Antes: `schemas.PaneFilter` não existia — toda chamada a
    `/panes/export` levantava `AttributeError`, capturado pelo handler
    genérico e devolvido como 500. Corrigido para `schemas.FiltroPane`."""
    headers = usuario_e_token["headers"]
    aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
    await criar_pane(client, headers, aeronave["id"])

    response = await client.get(EXPORT_URL, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.content.startswith(b"\xef\xbb\xbf")  # BOM utf-8-sig


@pytest.mark.asyncio
async def test_export_xlsx_nao_retorna_mais_500(
    client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict
):
    headers = usuario_e_token["headers"]
    aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
    await criar_pane(client, headers, aeronave["id"])

    response = await client.get(EXPORT_URL, params={"format": "xlsx"}, headers=headers)
    assert response.status_code == 200
    assert response.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_filtra_por_status_e_aeronave(
    client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict
):
    """RISCO-11: `?status=` continua funcionando com o mesmo nome de query
    string após o parâmetro interno ser renomeado para evitar sombrear
    `fastapi.status`."""
    headers = usuario_e_token["headers"]
    aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
    dados_outra_aeronave = {**dados_aeronave_valida, "serial_number": f"SN-{uuid.uuid4().hex[:8]}"}
    outra_aeronave = await criar_aeronave(client, headers, dados_outra_aeronave)
    await criar_pane(client, headers, aeronave["id"], descricao="Pane da aeronave alvo")
    await criar_pane(client, headers, outra_aeronave["id"], descricao="Pane de outra aeronave")

    response = await client.get(
        EXPORT_URL,
        params={"status": "ABERTA", "aeronave_id": aeronave["id"]},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8-sig")
    assert "Pane da aeronave alvo" in body
    assert "Pane de outra aeronave" not in body


# ================================================================== #
#  RISCO-10 — filtros extras e sinalização de truncamento
# ================================================================== #

@pytest.mark.asyncio
async def test_export_aceita_filtro_de_texto(
    client: AsyncClient, dados_aeronave_valida: dict, usuario_e_token: dict
):
    headers = usuario_e_token["headers"]
    aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
    termo = f"TERMO-{uuid.uuid4().hex[:8]}"
    await criar_pane(client, headers, aeronave["id"], descricao=f"Falha {termo} no motor")
    await criar_pane(client, headers, aeronave["id"], descricao="Outra falha qualquer")

    response = await client.get(EXPORT_URL, params={"texto": termo}, headers=headers)
    assert response.status_code == 200
    body = response.content.decode("utf-8-sig")
    assert termo in body
    assert "Outra falha qualquer" not in body


@pytest.mark.asyncio
async def test_export_sinaliza_truncamento_no_teto(
    client: AsyncClient, db: AsyncSession, dados_aeronave_valida: dict, usuario_e_token: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """Sem contagem total disponível, o endpoint sinaliza que o relatório
    pode estar incompleto via header, em vez de truncar silenciosamente."""
    headers = usuario_e_token["headers"]
    aeronave = await criar_aeronave(client, headers, dados_aeronave_valida)
    await criar_pane(client, headers, aeronave["id"])

    original_listar_panes = service.listar_panes

    async def _listar_panes_fake(db_arg, filtros):
        pane_real = (await original_listar_panes(db_arg, filtros))[0]
        # Simula bater no teto do limite fixo de exportação sem precisar
        # criar 1000 panes de verdade.
        return [pane_real] * filtros.limit

    monkeypatch.setattr(service, "listar_panes", _listar_panes_fake)

    response = await client.get(EXPORT_URL, headers=headers)
    assert response.status_code == 200
    assert response.headers.get("x-export-truncated") == "true"


# ================================================================== #
#  RISCO-04 — fallback de background não confia no Content-Type do cliente
# ================================================================== #

@pytest.mark.asyncio
async def test_fallback_background_recalcula_mime_real_dos_bytes(monkeypatch: pytest.MonkeyPatch):
    """Simula o caminho de fallback (pipeline de otimização falhando) com um
    Content-Type de cliente forjado — antes, esse valor forjado seria usado
    como Content-Type real no storage (XSS armazenado via R2 com um
    poliglota: bytes válidos de imagem, mas servidos de volta com
    Content-Type: text/html). Confirma que o storage recebe o MIME
    recalculado a partir dos bytes reais, não o Content-Type do cliente."""
    import app.modules.panes.service as panes_service

    # PNG real de 1x1 (magic bytes válidos) — o "Content-Type" abaixo é o
    # que um atacante enviaria no header HTTP, dissociado do conteúdo real.
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415478da6360606060000000050001a5f645400000000049454e44ae426082"
    )
    content_type_forjado = "text/html"
    uploads = []

    class _StorageFake:
        async def upload(self, conteudo, nome, mime):
            uploads.append(mime)
            return "caminho/fake.png"

        async def delete(self, caminho):
            return True

    monkeypatch.setattr(panes_service, "get_storage_service", lambda: _StorageFake())

    async def _atualizar_noop(*args, **kwargs):
        return True

    monkeypatch.setattr(panes_service, "_atualizar_caminho_anexo_se_pendente", _atualizar_noop)

    def _process_image_falha(*args, **kwargs):
        # process_image é síncrona por natureza (roda via asyncio.to_thread
        # dentro de processar_imagem_background) — precisa ser um stub
        # síncrono, senão asyncio.to_thread só devolveria a coroutine sem
        # nunca executá-la ou propagar a falha.
        raise RuntimeError("Falha simulada no pipeline de otimização")

    monkeypatch.setattr("app.shared.services.image.pipeline.process_image", _process_image_falha)

    await panes_service.processar_imagem_background(
        uuid.uuid4(), png_bytes, "poliglota.png", content_type_forjado
    )

    assert uploads, "Fallback não chegou a chamar storage_svc.upload"
    assert uploads[0] != content_type_forjado
    assert uploads[0] == "image/png"
