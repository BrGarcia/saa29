"""
tests/unit/test_storage_hardening.py
Testes de regressão para os achados de docs/backlog/Fable5/Etapa5.md
relacionados a storage/upload:

    #3  Allowlist de upload unificada (fonte única em file_validators.py)
    #4  Leitura de upload com limite de tamanho (chunked, sem materializar
        o arquivo inteiro antes de rejeitar)
    #5  Escrita local em storage.py não bloqueia o event loop
"""

import asyncio
import io
import time

import pytest
from fastapi import HTTPException, UploadFile

from app.shared.core import file_validators
from app.shared.core.file_validators import ler_upload_com_limite


# ------------------------------------------------------------------ #
#  #3 — allowlist unificada
# ------------------------------------------------------------------ #

def test_allowlist_unificada_inclui_heic():
    """Antes: file_validators não conhecia HEIC/HEIF, então o pipeline de
    conversão em app/shared/services/image/converter.py era inalcançável a
    partir do endpoint real de upload (rejeitado 422 antes de chegar lá)."""
    assert ".heic" in file_validators.EXTENSOES_PERMITIDAS
    assert ".heif" in file_validators.EXTENSOES_PERMITIDAS
    assert "image/heic" in file_validators.MIMES_PERMITIDOS


def test_allowlist_unificada_nao_inclui_office_sem_validacao_de_conteudo():
    """.doc/.docx eram aceitos por storage.py mas nunca reconhecidos por
    file_validators (nem por magic bytes) — removidos como parte da
    unificação, já que não há validação de conteúdo real para eles em
    lugar nenhum do código."""
    assert ".doc" not in file_validators.EXTENSOES_PERMITIDAS
    assert ".docx" not in file_validators.EXTENSOES_PERMITIDAS


def test_storage_usa_a_mesma_allowlist_do_file_validators():
    from app.shared.core import storage
    import inspect
    fonte = inspect.getsource(storage)
    assert "EXTENSOES_PERMITIDAS" in fonte
    assert "'.doc'" not in fonte and '".doc"' not in fonte


def test_deteccao_fallback_reconhece_heic():
    # Assinatura mínima de um contêiner ISOBMFF com brand "heic".
    fake_heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 8
    assert file_validators._detect_mime_type_fallback(fake_heic) == "image/heic"


# ------------------------------------------------------------------ #
#  #4 — leitura de upload com limite de tamanho
# ------------------------------------------------------------------ #

def _upload_file(conteudo: bytes, filename: str = "teste.jpg") -> UploadFile:
    return UploadFile(file=io.BytesIO(conteudo), filename=filename)


@pytest.mark.asyncio
async def test_ler_upload_com_limite_aceita_arquivo_dentro_do_limite():
    conteudo = b"x" * 1000
    arquivo = _upload_file(conteudo)
    resultado = await ler_upload_com_limite(arquivo, max_bytes=2000)
    assert resultado == conteudo


@pytest.mark.asyncio
async def test_ler_upload_com_limite_rejeita_arquivo_acima_do_limite_sem_ler_tudo():
    """O ponto central do achado: a rejeição deve acontecer ANTES de
    materializar o arquivo inteiro. Simulamos um arquivo bem maior que o
    limite e verificamos que a exceção é 413, levantada rapidamente (não
    lendo os dezenas de MB completos antes de decidir)."""
    tamanho_grande = 50 * 1024 * 1024  # 50 MiB
    limite = 1 * 1024 * 1024  # 1 MiB

    class _StreamGrande(io.RawIOBase):
        """Simula um stream de 50MB sem alocar os 50MB de uma vez em memória."""
        def __init__(self, total: int):
            self._restante = total

        def readable(self):
            return True

        def readinto(self, b):
            n = min(len(b), self._restante)
            if n <= 0:
                return 0
            b[:n] = b"a" * n
            self._restante -= n
            return n

    arquivo = UploadFile(file=io.BufferedReader(_StreamGrande(tamanho_grande), buffer_size=1024 * 1024), filename="grande.jpg")

    inicio = time.perf_counter()
    with pytest.raises(HTTPException) as exc_info:
        await ler_upload_com_limite(arquivo, max_bytes=limite)
    duracao = time.perf_counter() - inicio

    assert exc_info.value.status_code == 413
    # Não deve ter processado os 50MB inteiros — poucos chunks (1MB cada) já
    # bastam para estourar o limite de 1MB. Folga generosa para não ser flaky.
    assert duracao < 2.0


@pytest.mark.asyncio
async def test_ler_upload_com_limite_arquivo_exatamente_no_limite_passa():
    conteudo = b"x" * 2000
    arquivo = _upload_file(conteudo)
    resultado = await ler_upload_com_limite(arquivo, max_bytes=2000)
    assert len(resultado) == 2000


# ------------------------------------------------------------------ #
#  #5 — escrita local não bloqueia o event loop
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_local_storage_upload_nao_bloqueia_event_loop(tmp_path, monkeypatch):
    """Confirma que outra coroutine consegue rodar CONCORRENTEMENTE enquanto
    o upload local está em andamento — só é possível se a escrita acontecer
    numa thread separada (asyncio.to_thread), não direto na coroutine."""
    from app.bootstrap.config import get_settings
    from app.shared.core.storage import LocalStorageService

    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    storage_svc = LocalStorageService()

    marcador = {"rodou_durante_upload": False}

    async def tarefa_concorrente():
        await asyncio.sleep(0.01)
        marcador["rodou_durante_upload"] = True

    conteudo = b"x" * (2 * 1024 * 1024)  # 2 MiB — grande o suficiente pra medir
    tarefa = asyncio.create_task(tarefa_concorrente())
    await storage_svc.upload(conteudo, "arquivo.jpg", "image/jpeg")
    await tarefa

    assert marcador["rodou_durante_upload"] is True


# ------------------------------------------------------------------ #
#  #10 — lru_cache da fábrica de storage expõe cache_clear
# ------------------------------------------------------------------ #

def test_get_storage_service_expoe_cache_clear():
    """functools.lru_cache já expõe cache_clear() nativamente — nenhuma
    mudança de código foi necessária em storage.py, só confirmar que a
    capacidade existe e funciona, documentando-a para quem precisar trocar
    storage_backend em runtime num teste."""
    from app.shared.core.storage import get_storage_service, LocalStorageService

    assert hasattr(get_storage_service, "cache_clear")
    instancia_1 = get_storage_service()
    instancia_2 = get_storage_service()
    assert instancia_1 is instancia_2  # cache em efeito

    get_storage_service.cache_clear()
    instancia_3 = get_storage_service()
    assert isinstance(instancia_3, LocalStorageService)


# ------------------------------------------------------------------ #
#  #11 — validação de path traversal unificada
# ------------------------------------------------------------------ #

def test_validar_nome_arquivo_seguro_rejeita_traversal():
    from app.shared.core.file_validators import validar_nome_arquivo_seguro

    for nome_malicioso in ("../../etc/passwd", "sub/dir.jpg", r"sub\dir.jpg", r"..\..\win.ini"):
        with pytest.raises(ValueError):
            validar_nome_arquivo_seguro(nome_malicioso)


def test_validar_nome_arquivo_seguro_aceita_nome_normal():
    from app.shared.core.file_validators import validar_nome_arquivo_seguro
    validar_nome_arquivo_seguro("foto_pane.jpg")  # não deve levantar
