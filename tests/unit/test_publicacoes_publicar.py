"""
tests/unit/test_publicacoes_publicar.py
Estação de publicação (M4 tarefa 2) — inventário, diff, relatório e snapshot.

O upload ao R2 é mockado (mesmo padrão de `tests/unit/test_r2_manager.py`):
nada aqui toca rede de verdade. O que É exercitado de ponta a ponta, com
PDFs reais, é o inventário e o diff — a parte que decide o que vale a pena
publicar.
"""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.publicacoes import publicar


@pytest.fixture
def acervo_amostra(tmp_path: Path) -> Path:
    """
    Um "acervo" sintético com 2 manuais, imitando o layout de
    `var/publicacoes/acervo/Manuais/` (um diretório por manual).
    """
    raiz = tmp_path / "acervo"
    manual_a = raiz / "MANUAL_A"
    manual_b = raiz / "MANUAL_B"
    manual_a.mkdir(parents=True)
    manual_b.mkdir(parents=True)

    (manual_a / "DOC1.PDF").write_bytes(b"%PDF-1.4 conteudo do doc1")
    (manual_a / "DOC2.PDF").write_bytes(b"%PDF-1.4 conteudo do doc2")
    (manual_b / "DOC3.PDF").write_bytes(b"%PDF-1.4 conteudo do doc3")
    return raiz


# --------------------------------------------------------------------------
# Inventário
# --------------------------------------------------------------------------


def test_inventariar_acervo_produz_uma_entrada_por_pdf(acervo_amostra: Path):
    inventario = publicar.inventariar_acervo(acervo_amostra)

    assert set(inventario) == {
        ("MANUAL_A", "DOC1.PDF"),
        ("MANUAL_A", "DOC2.PDF"),
        ("MANUAL_B", "DOC3.PDF"),
    }
    # Hash de verdade, não placeholder — dois conteúdos diferentes não podem colidir.
    assert inventario[("MANUAL_A", "DOC1.PDF")] != inventario[("MANUAL_A", "DOC2.PDF")]


def test_inventariar_acervo_mesmo_conteudo_mesmo_hash(tmp_path: Path):
    raiz = tmp_path / "acervo"
    manual = raiz / "MANUAL_A"
    manual.mkdir(parents=True)
    (manual / "DOC1.PDF").write_bytes(b"%PDF-1.4 identico")
    (manual / "DOC2.PDF").write_bytes(b"%PDF-1.4 identico")

    inventario = publicar.inventariar_acervo(raiz)
    assert inventario[("MANUAL_A", "DOC1.PDF")] == inventario[("MANUAL_A", "DOC2.PDF")]


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------


def test_diff_classifica_novo_alterado_removido_inalterado():
    antigo = {
        ("M", "a.pdf"): "hash_a",
        ("M", "b.pdf"): "hash_b",
        ("M", "c.pdf"): "hash_c",
    }
    novo = {
        ("M", "a.pdf"): "hash_a",       # inalterado
        ("M", "b.pdf"): "hash_b_novo",  # alterado
        ("M", "d.pdf"): "hash_d",       # novo
        # c.pdf sumiu -> removido
    }

    diff = publicar.calcular_diff(antigo, novo)

    assert diff.novos == [("M", "d.pdf")]
    assert diff.alterados == [("M", "b.pdf")]
    assert diff.removidos == [("M", "c.pdf")]
    assert diff.inalterados == 1
    assert diff.total_mudancas == 3


def test_diff_contra_acervo_vazio_e_tudo_novo():
    novo = {("M", "a.pdf"): "h1", ("M", "b.pdf"): "h2"}
    diff = publicar.calcular_diff({}, novo)

    assert set(diff.novos) == set(novo)
    assert diff.alterados == []
    assert diff.removidos == []
    assert diff.inalterados == 0


def test_diff_acervo_completo_removido_e_tudo_removido():
    """Simula uma edição sem sucessora (acervo esvaziado) — não deve quebrar."""
    antigo = {("M", "a.pdf"): "h1"}
    diff = publicar.calcular_diff(antigo, {})

    assert diff.removidos == [("M", "a.pdf")]
    assert diff.novos == []


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def test_relatorio_markdown_contem_contagens_e_secoes():
    diff = publicar.DiffAcervo(
        novos=[("M", "novo.pdf")],
        alterados=[("M", "alt.pdf")],
        removidos=[("M", "rem.pdf")],
        inalterados=42,
    )
    relatorio = publicar.gerar_relatorio_markdown(
        diff, edicao_nova="2027", edicao_anterior="2026"
    )

    assert "edição 2027" in relatorio
    assert "2026" in relatorio
    assert "Novos: 1" in relatorio
    assert "Alterados: 1" in relatorio
    assert "Removidos: 1" in relatorio
    assert "Inalterados: 42" in relatorio
    assert "M/novo.pdf" in relatorio


def test_relatorio_primeira_publicacao_sem_edicao_anterior():
    diff = publicar.DiffAcervo(novos=[("M", "a.pdf")])
    relatorio = publicar.gerar_relatorio_markdown(
        diff, edicao_nova="2026", edicao_anterior=None
    )
    assert "primeira publicação" in relatorio


def test_relatorio_trunca_listas_muito_longas():
    diff = publicar.DiffAcervo(novos=[("M", f"{i}.pdf") for i in range(250)])
    relatorio = publicar.gerar_relatorio_markdown(diff, edicao_nova="2027", edicao_anterior=None)
    assert "e mais 50" in relatorio


# --------------------------------------------------------------------------
# Snapshot ZIP
# --------------------------------------------------------------------------


def test_criar_snapshot_zip_inclui_todos_os_pdfs(acervo_amostra: Path, tmp_path: Path):
    destino = tmp_path / "snapshot.zip"
    publicar.criar_snapshot_zip(acervo_amostra, destino)

    assert destino.is_file()
    with zipfile.ZipFile(destino) as zf:
        nomes = set(zf.namelist())
    assert nomes == {
        "MANUAL_A/DOC1.PDF", "MANUAL_A/DOC2.PDF", "MANUAL_B/DOC3.PDF",
    } or nomes == {
        # zipfile normaliza separador para '/' independente do SO — mas
        # confere sem depender de barra invertida no Windows.
        str(Path("MANUAL_A/DOC1.PDF")), str(Path("MANUAL_A/DOC2.PDF")), str(Path("MANUAL_B/DOC3.PDF")),
    }


# --------------------------------------------------------------------------
# R2 (mockado — precedente: tests/unit/test_r2_manager.py)
# --------------------------------------------------------------------------


def test_obter_cliente_s3_sem_credenciais_leva_erro_claro():
    settings_fake = MagicMock(
        r2_endpoint=None, r2_access_key_id=None,
        r2_secret_access_key=None, r2_bucket_name=None,
    )
    with pytest.raises(RuntimeError, match="R2 incompletas"):
        publicar._obter_cliente_s3(settings_fake)


@patch("boto3.client")
def test_enviar_snapshot_faz_upload_com_a_chave_esperada(mock_boto_client, tmp_path: Path):
    cliente = MagicMock()
    arquivo = tmp_path / "2027.zip"
    arquivo.write_bytes(b"zip fake")

    chave = publicar.enviar_snapshot(cliente, "meu-bucket", arquivo, "2027")

    assert chave == "publicacoes/snapshots/2027.zip"
    cliente.upload_file.assert_called_once_with(str(arquivo), "meu-bucket", chave)


def test_podar_snapshots_antigos_mantem_so_os_mais_recentes():
    from datetime import datetime, timedelta

    agora = datetime.now()
    cliente = MagicMock()
    cliente.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "publicacoes/snapshots/2024.zip", "LastModified": agora - timedelta(days=730)},
            {"Key": "publicacoes/snapshots/2025.zip", "LastModified": agora - timedelta(days=365)},
            {"Key": "publicacoes/snapshots/2026.zip", "LastModified": agora - timedelta(days=1)},
            {"Key": "publicacoes/snapshots/2027.zip", "LastModified": agora},
        ]
    }

    removidos = publicar.podar_snapshots_antigos(cliente, "bucket", manter=2)

    assert set(removidos) == {
        "publicacoes/snapshots/2024.zip", "publicacoes/snapshots/2025.zip",
    }
    assert cliente.delete_object.call_count == 2


def test_podar_snapshots_dentro_do_limite_nao_remove_nada():
    cliente = MagicMock()
    cliente.list_objects_v2.return_value = {
        "Contents": [{"Key": "publicacoes/snapshots/2027.zip", "LastModified": "x"}]
    }
    removidos = publicar.podar_snapshots_antigos(cliente, "bucket", manter=3)
    assert removidos == []
    cliente.delete_object.assert_not_called()

# `publicar.main()` não é exercitado ponta a ponta aqui de propósito: ele usa
# `app.bootstrap.database.get_session_factory()`, que por padrão aponta para
# `saa29_local.db` — o arquivo de banco REAL de desenvolvimento, não o SQLite
# em memória de `tests/conftest.py`. Um teste automatizado que chamasse
# `main()` (mesmo em `--dry-run`) leria/gravaria nesse arquivo em qualquer
# máquina que rodar a suíte, o que é exatamente o tipo de vazamento
# teste↔produção que este projeto evita em todo o resto do código. As funções
# puras acima (inventário, diff, relatório, zip, R2 mockado) cobrem toda a
# lógica que `main()` orquestra; a orquestração em si foi verificada
# manualmente contra o acervo real nesta sessão (34 manuais, 5.724
# documentos, 0 sem texto — ver 08_status_de_implementacao.md).
