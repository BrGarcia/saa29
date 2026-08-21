"""
tests/unit/test_publicacoes_indexar.py
Descoberta de manuais (`scripts.publicacoes.indexar.descobrir_manuais`) e a
mescla de categorias TOML + XML do disco (`categorias_mescladas`).

Contexto (docs/backlog/modulo_publicacoes/11_achados_disco_completo.md §1):
o disco cru do TechData tem `Program/Data/` (manutenção) e
`Program_Operational/Data/` (operacional), cada um com um subdiretório por
manual — um nível a mais do que o layout simples `Manuais/<código>/` que o
acervo já normalizado usa. Uma tentativa de ingestão anterior sem esse
terceiro layout colapsou tudo numa pasta "Data" só (captura de tela "Acervo
› Outros › Data" no histórico do card de publicações) — os testes aqui
prendem exatamente esse regresso.
"""

from pathlib import Path

import pytest

from app.modules.publicacoes import catalog
from app.shared.core.enums import OrigemManual
from scripts.publicacoes import indexar


# --------------------------------------------------------------------------
# Fixtures — disco cru sintético
# --------------------------------------------------------------------------


@pytest.fixture
def disco_cru(tmp_path: Path) -> Path:
    """
    `<raiz>/Program/Data/<MANUAL>/<CAP>/*.pdf` e
    `<raiz>/Program_Operational/Data/<MANUAL>/<CAP>/*.pdf`, com uma
    `Data-ALX/` (réplica descartável, doc 11 §2.2) e um manual sem PDF
    (deve ser ignorado, não quebrar).
    """
    raiz = tmp_path / "19MAIO26"

    fim_manutencao = raiz / "Program" / "Data" / "FIM_1741" / "010_FRONTMATTER"
    fim_manutencao.mkdir(parents=True)
    (fim_manutencao / "A.PDF").write_bytes(b"%PDF-1.4 fim manutencao")

    amm_manutencao = raiz / "Program" / "Data" / "AMM_PART1_1651" / "020_CAP"
    amm_manutencao.mkdir(parents=True)
    (amm_manutencao / "B.PDF").write_bytes(b"%PDF-1.4 amm")

    fim_operacional = raiz / "Program_Operational" / "Data" / "FIM_1741" / "010_FRONTMATTER"
    fim_operacional.mkdir(parents=True)
    (fim_operacional / "A.PDF").write_bytes(b"%PDF-1.4 fim operacional")

    data_alx = raiz / "Program" / "Data" / "Data-ALX" / "FIM_1741"
    data_alx.mkdir(parents=True)
    (data_alx / "A.PDF").write_bytes(b"%PDF-1.4 replica")

    vazio = raiz / "Program" / "Data" / "MANUAL_SEM_PDF"
    vazio.mkdir(parents=True)

    return raiz


# --------------------------------------------------------------------------
# descobrir_manuais — layout C (disco cru)
# --------------------------------------------------------------------------


def test_layout_c_descobre_as_duas_origens(disco_cru: Path):
    manuais = indexar.descobrir_manuais(disco_cru, None)
    chaves = {(m.codigo, m.origem) for m in manuais}

    assert chaves == {
        ("FIM_1741", OrigemManual.MANUTENCAO),
        ("AMM_PART1_1651", OrigemManual.MANUTENCAO),
        ("FIM_1741", OrigemManual.OPERACIONAL),
    }


def test_layout_c_exclui_data_alx(disco_cru: Path):
    manuais = indexar.descobrir_manuais(disco_cru, None)
    assert not any(m.codigo == "Data-ALX" for m in manuais)


def test_layout_c_ignora_manual_sem_pdf(disco_cru: Path):
    manuais = indexar.descobrir_manuais(disco_cru, None)
    assert not any(m.codigo == "MANUAL_SEM_PDF" for m in manuais)


def test_layout_c_raiz_de_cada_manual_e_o_diretorio_do_manual_nao_data(disco_cru: Path):
    """
    O bug original: `manual.raiz` virava a pasta `Data` (um nível acima do
    manual real), e `_capitulo_do_caminho` mantinha só o último segmento do
    caminho — o código do manual real se perdia. Aqui `raiz` precisa ser
    `.../FIM_1741`, não `.../Data`.
    """
    manuais = indexar.descobrir_manuais(disco_cru, None)
    fim_manutencao = next(
        m for m in manuais if m.codigo == "FIM_1741" and m.origem == OrigemManual.MANUTENCAO
    )
    assert fim_manutencao.raiz.name == "FIM_1741"

    file_key = fim_manutencao.pdfs[0].relative_to(fim_manutencao.raiz).as_posix()
    assert file_key == "010_FRONTMATTER/A.PDF"
    capitulo = indexar._capitulo_do_caminho(fim_manutencao.pdfs[0], fim_manutencao.raiz)
    assert capitulo == "010_FRONTMATTER"


def test_layout_c_mesmo_codigo_duas_origens_pdfs_diferentes(disco_cru: Path):
    manuais = indexar.descobrir_manuais(disco_cru, None)
    fim_manutencao = next(
        m for m in manuais if m.codigo == "FIM_1741" and m.origem == OrigemManual.MANUTENCAO
    )
    fim_operacional = next(
        m for m in manuais if m.codigo == "FIM_1741" and m.origem == OrigemManual.OPERACIONAL
    )
    assert fim_manutencao.pdfs[0].read_bytes() != fim_operacional.pdfs[0].read_bytes()


def test_layout_c_so_program_presente(tmp_path: Path):
    """Uma remessa futura pode trazer só um dos dois discos."""
    raiz = tmp_path / "disco"
    manual = raiz / "Program" / "Data" / "FIM_1741"
    manual.mkdir(parents=True)
    (manual / "A.PDF").write_bytes(b"%PDF-1.4 x")

    manuais = indexar.descobrir_manuais(raiz, None)
    assert {m.origem for m in manuais} == {OrigemManual.MANUTENCAO}


# --------------------------------------------------------------------------
# descobrir_manuais — layouts A e B continuam MANUTENCAO fixo
# --------------------------------------------------------------------------


def test_layout_b_acervo_normalizado_origem_manutencao(tmp_path: Path):
    raiz = tmp_path / "acervo"
    manual = raiz / "FIM_1741"
    manual.mkdir(parents=True)
    (manual / "A.PDF").write_bytes(b"%PDF-1.4 x")

    manuais = indexar.descobrir_manuais(raiz, None)
    assert len(manuais) == 1
    assert manuais[0].origem == OrigemManual.MANUTENCAO


def test_layout_a_amostra_solta_origem_manutencao(tmp_path: Path):
    raiz = tmp_path / "fim"
    raiz.mkdir()
    (raiz / "A.PDF").write_bytes(b"%PDF-1.4 x")

    manuais = indexar.descobrir_manuais(raiz, "FIM_1741")
    assert len(manuais) == 1
    assert manuais[0].codigo == "FIM_1741"
    assert manuais[0].origem == OrigemManual.MANUTENCAO


# --------------------------------------------------------------------------
# categorias_mescladas — TOML tem prioridade sobre o XML do disco
# --------------------------------------------------------------------------


def test_categorias_mescladas_usa_xml_quando_toml_nao_cobre(tmp_path: Path):
    raiz = tmp_path / "19MAIO26"
    data_dir = raiz / "Program" / "Data"
    data_dir.mkdir(parents=True)
    (data_dir / "manual_details.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><manuals>'
        '<manual partnumber="5206" type="GP">'
        "<custom-description>Publicação Geral</custom-description></manual>"
        "</manuals>",
        encoding="utf-8",
    )
    (data_dir / "manual_type.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><types>'
        '<type typeid="GP" catid="7"><language/></type>'
        "</types>",
        encoding="utf-8",
    )
    toml_path = tmp_path / "categorias_manuais.toml"
    toml_path.write_text('[_default]\ncategoria = "Outros"\ndescricao_pt = "{codigo}"\n', encoding="utf-8")

    mapa = indexar.categorias_mescladas(raiz, toml_path)
    assert mapa["GP_5206"].descricao_pt == "Publicação Geral"
    assert mapa["GP_5206"].categoria == "Operacional / Voo"


def test_categorias_mescladas_toml_vence_sobre_xml(tmp_path: Path):
    raiz = tmp_path / "19MAIO26"
    data_dir = raiz / "Program" / "Data"
    data_dir.mkdir(parents=True)
    (data_dir / "manual_details.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><manuals>'
        '<manual partnumber="1741" type="FIM">'
        "<custom-description>Nome cru do disco</custom-description></manual>"
        "</manuals>",
        encoding="utf-8",
    )
    toml_path = tmp_path / "categorias_manuais.toml"
    toml_path.write_text(
        '[FIM_1741]\ncategoria = "Manutenção"\ndescricao_pt = "Nome curado"\n'
        '[_default]\ncategoria = "Outros"\ndescricao_pt = "{codigo}"\n',
        encoding="utf-8",
    )

    mapa = indexar.categorias_mescladas(raiz, toml_path)
    assert mapa["FIM_1741"].descricao_pt == "Nome curado"


def test_categorias_mescladas_sem_layout_c_usa_so_toml(tmp_path: Path):
    """Acervo normalizado (sem Program/Data) — nada de XML a mesclar, só o TOML."""
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    toml_path = tmp_path / "categorias_manuais.toml"
    toml_path.write_text('[_default]\ncategoria = "Outros"\ndescricao_pt = "{codigo}"\n', encoding="utf-8")

    mapa = indexar.categorias_mescladas(raiz, toml_path)
    assert catalog.categoria_de_manual(mapa, "QUALQUER").categoria == "Outros"
