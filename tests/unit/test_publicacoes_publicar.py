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


@pytest.fixture
def disco_cru_amostra(tmp_path: Path) -> Path:
    """
    Disco cru sintético (11_achados_disco_completo.md §1): `Program/Data/` e
    `Program_Operational/Data/`, cada um com um manual — o mesmo código
    (`FIM_1741`) nos dois lados, com `file_key` idêntico e conteúdo diferente,
    para exercitar o caso que motivou origem na chave. `Data-ALX/` é a réplica
    que o layout C descarta (doc 11 §2.2).
    """
    raiz = tmp_path / "19MAIO26"
    manutencao = raiz / "Program" / "Data" / "FIM_1741" / "010_FRONTMATTER"
    operacional = raiz / "Program_Operational" / "Data" / "FIM_1741" / "010_FRONTMATTER"
    data_alx = raiz / "Program" / "Data" / "Data-ALX" / "FIM_1741"
    manutencao.mkdir(parents=True)
    operacional.mkdir(parents=True)
    data_alx.mkdir(parents=True)

    (manutencao / "A.PDF").write_bytes(b"%PDF-1.4 revisao 2016")
    (operacional / "A.PDF").write_bytes(b"%PDF-1.4 revisao 2013")
    (data_alx / "A.PDF").write_bytes(b"%PDF-1.4 replica descartada")
    return raiz


# --------------------------------------------------------------------------
# Inventário
# --------------------------------------------------------------------------


def test_inventariar_acervo_produz_uma_entrada_por_pdf(acervo_amostra: Path):
    inventario = publicar.inventariar_acervo(acervo_amostra)

    # Layout B (um diretório por manual, sem Program/Program_Operational):
    # `descobrir_manuais` fixa origem="MANUTENCAO" — é o valor compatível com
    # o acervo de fonte única já publicado.
    assert set(inventario) == {
        ("MANUTENCAO", "MANUAL_A", "DOC1.PDF"),
        ("MANUTENCAO", "MANUAL_A", "DOC2.PDF"),
        ("MANUTENCAO", "MANUAL_B", "DOC3.PDF"),
    }
    # Hash de verdade, não placeholder — dois conteúdos diferentes não podem colidir.
    assert (
        inventario[("MANUTENCAO", "MANUAL_A", "DOC1.PDF")]
        != inventario[("MANUTENCAO", "MANUAL_A", "DOC2.PDF")]
    )


def test_inventariar_acervo_mesmo_conteudo_mesmo_hash(tmp_path: Path):
    raiz = tmp_path / "acervo"
    manual = raiz / "MANUAL_A"
    manual.mkdir(parents=True)
    (manual / "DOC1.PDF").write_bytes(b"%PDF-1.4 identico")
    (manual / "DOC2.PDF").write_bytes(b"%PDF-1.4 identico")

    inventario = publicar.inventariar_acervo(raiz)
    assert (
        inventario[("MANUTENCAO", "MANUAL_A", "DOC1.PDF")]
        == inventario[("MANUTENCAO", "MANUAL_A", "DOC2.PDF")]
    )


def test_inventariar_disco_cru_nao_colide_entre_origens(disco_cru_amostra: Path):
    """
    `FIM_1741/010_FRONTMATTER/A.PDF` existe nos dois discos com o MESMO
    `file_key` e hash diferente — é exatamente o cenário que fez a origem
    entrar na chave (achado desta sessão: sem ela, um dos dois some do
    inventário por colisão silenciosa de dict).
    """
    inventario = publicar.inventariar_acervo(disco_cru_amostra)

    assert set(inventario) == {
        ("MANUTENCAO", "FIM_1741", "010_FRONTMATTER/A.PDF"),
        ("OPERACIONAL", "FIM_1741", "010_FRONTMATTER/A.PDF"),
    }
    assert (
        inventario[("MANUTENCAO", "FIM_1741", "010_FRONTMATTER/A.PDF")]
        != inventario[("OPERACIONAL", "FIM_1741", "010_FRONTMATTER/A.PDF")]
    )
    # Data-ALX/ é réplica de revisão intermediária — nunca vira "manual" à parte.
    assert not any(manual == "Data-ALX" for _origem, manual, _fk in inventario)


# --------------------------------------------------------------------------
# Diff
# --------------------------------------------------------------------------


def test_diff_classifica_novo_alterado_removido_inalterado():
    antigo = {
        ("MANUTENCAO", "M", "a.pdf"): "hash_a",
        ("MANUTENCAO", "M", "b.pdf"): "hash_b",
        ("MANUTENCAO", "M", "c.pdf"): "hash_c",
    }
    novo = {
        ("MANUTENCAO", "M", "a.pdf"): "hash_a",       # inalterado
        ("MANUTENCAO", "M", "b.pdf"): "hash_b_novo",  # alterado
        ("MANUTENCAO", "M", "d.pdf"): "hash_d",       # novo
        # c.pdf sumiu -> removido
    }

    diff = publicar.calcular_diff(antigo, novo)

    assert diff.novos == [("MANUTENCAO", "M", "d.pdf")]
    assert diff.alterados == [("MANUTENCAO", "M", "b.pdf")]
    assert diff.removidos == [("MANUTENCAO", "M", "c.pdf")]
    assert diff.inalterados == 1
    assert diff.total_mudancas == 3


def test_diff_mesmo_manual_e_arquivo_em_origens_diferentes_nao_colide():
    """
    Os dois discos podem ter o mesmo (manual, file_key) apontando para PDFs
    diferentes — sem a origem na chave, um pareceria "alterado" quando na
    verdade são dois documentos distintos que nunca se relacionam.
    """
    antigo = {("MANUTENCAO", "FIM_1741", "a.pdf"): "hash_manutencao"}
    novo = {
        ("MANUTENCAO", "FIM_1741", "a.pdf"): "hash_manutencao",  # inalterado
        ("OPERACIONAL", "FIM_1741", "a.pdf"): "hash_operacional",  # novo, não "alterado"
    }

    diff = publicar.calcular_diff(antigo, novo)

    assert diff.novos == [("OPERACIONAL", "FIM_1741", "a.pdf")]
    assert diff.alterados == []
    assert diff.inalterados == 1


def test_diff_contra_acervo_vazio_e_tudo_novo():
    novo = {("MANUTENCAO", "M", "a.pdf"): "h1", ("MANUTENCAO", "M", "b.pdf"): "h2"}
    diff = publicar.calcular_diff({}, novo)

    assert set(diff.novos) == set(novo)
    assert diff.alterados == []
    assert diff.removidos == []
    assert diff.inalterados == 0


def test_diff_acervo_completo_removido_e_tudo_removido():
    """Simula uma edição sem sucessora (acervo esvaziado) — não deve quebrar."""
    antigo = {("MANUTENCAO", "M", "a.pdf"): "h1"}
    diff = publicar.calcular_diff(antigo, {})

    assert diff.removidos == [("MANUTENCAO", "M", "a.pdf")]
    assert diff.novos == []


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def test_relatorio_markdown_contem_contagens_e_secoes():
    diff = publicar.DiffAcervo(
        novos=[("MANUTENCAO", "M", "novo.pdf")],
        alterados=[("MANUTENCAO", "M", "alt.pdf")],
        removidos=[("MANUTENCAO", "M", "rem.pdf")],
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
    assert "[MANUTENCAO] M/novo.pdf" in relatorio


def test_relatorio_primeira_publicacao_sem_edicao_anterior():
    diff = publicar.DiffAcervo(novos=[("MANUTENCAO", "M", "a.pdf")])
    relatorio = publicar.gerar_relatorio_markdown(
        diff, edicao_nova="2026", edicao_anterior=None
    )
    assert "primeira publicação" in relatorio


def test_relatorio_trunca_listas_muito_longas():
    diff = publicar.DiffAcervo(novos=[("MANUTENCAO", "M", f"{i}.pdf") for i in range(250)])
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
