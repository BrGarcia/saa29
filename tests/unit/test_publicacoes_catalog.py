"""
tests/unit/test_publicacoes_catalog.py
Testes do parser do índice Lucene legado e das normalizações do catálogo.

DUAS CAMADAS, de propósito:

1. Testes sobre um índice SINTÉTICO, montado byte a byte pelo helper deste
   arquivo. Rodam sempre, inclusive no CI. O acervo real é 1 GB, está no
   .gitignore e NUNCA entra no repositório — nem como fixture "pequena": o
   campo `data` do índice carrega o texto integral dos manuais, que é
   conteúdo técnico proprietário. Montar o binário aqui também documenta o
   formato de forma executável.

2. Um teste de regressão contra o acervo REAL, que afirma os números medidos
   em 02_formato_indice_lucene.md §7. Só roda em máquina que tem o acervo no
   disco; no CI é pulado. É a rede que pega "o parser mudou de comportamento"
   e "o acervo mudou" — nessa ordem de suspeita.
"""

import struct
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.modules.publicacoes import catalog
from app.shared.core.enums import RevisionStatus

# Caminho do acervo real; ausente no CI.
ACERVO = Path("var/publicacoes/acervo/Manuais")
sem_acervo = pytest.mark.skipif(
    not ACERVO.is_dir(),
    reason="acervo real ausente (esperado no CI — 1 GB fora do repositório)",
)

CAMPOS = ["data", "title", "revision", "tsn", "filename", "chapter"]


# --------------------------------------------------------------------------
# Helper: escreve um índice Lucene 2.9/3.x no formato real
# --------------------------------------------------------------------------


def _vint(valor: int) -> bytes:
    """Codifica um inteiro no VInt do Lucene (7 bits por byte, MSB=continuação)."""
    out = bytearray()
    while True:
        bits = valor & 0x7F
        valor >>= 7
        if valor:
            out.append(bits | 0x80)
        else:
            out.append(bits)
            return bytes(out)


def escrever_indice(destino: Path, documentos: list[dict[str, str]]) -> Path:
    """
    Monta um `index_2.0/` válido em `destino` com os documentos dados.

    Reproduz o layout descrito em 02_formato_indice_lucene.md §2/§3/§4:
    `_0.fnm` (schema), `_0.fdx` (offsets int64 big-endian) e `_0.fdt` (valores).
    """
    index_dir = destino / "index_2.0"
    index_dir.mkdir(parents=True, exist_ok=True)

    # _0.fnm — header de formato + contagem + (tamanho, nome, flags) por campo
    fnm = bytearray()
    fnm += _vint(0xFD)            # header de formato, descartado pelo parser
    fnm += _vint(len(CAMPOS))
    for nome in CAMPOS:
        crus = nome.encode("utf-8")
        fnm += _vint(len(crus))
        fnm += crus
        fnm += b"\x01"            # bitset de flags
    (index_dir / "_0.fnm").write_bytes(bytes(fnm))

    # _0.fdt — os valores; _0.fdx — o offset de cada documento
    fdt = bytearray()
    offsets: list[int] = []
    for doc in documentos:
        offsets.append(len(fdt))
        presentes = [(i, doc[c]) for i, c in enumerate(CAMPOS) if c in doc]
        fdt += _vint(len(presentes))
        for num_campo, valor in presentes:
            crus = valor.encode("utf-8")
            fdt += _vint(num_campo)
            fdt += b"\x00"        # bits: nem binário nem comprimido
            fdt += _vint(len(crus))
            fdt += crus
    (index_dir / "_0.fdt").write_bytes(bytes(fdt))

    fdx = bytearray(b"\x00\x00\x00\x00")   # 4 bytes de header
    for off in offsets:
        fdx += struct.pack(">q", off)
    (index_dir / "_0.fdx").write_bytes(bytes(fdx))

    return index_dir


@pytest.fixture
def manual_sintetico(tmp_path: Path) -> Path:
    """Um manual com 3 documentos cobrindo os casos que importam."""
    manual = tmp_path / "FIM_1741"
    escrever_indice(
        manual,
        [
            {
                "data": "texto do procedimento de sangria do compressor",
                "title": "fim-1741 - 21-26-00-810-801-a - sobretemperatura",
                "revision": "R",
                "tsn": "1",
                "filename": "/prod/techpubs/Data-ALX/FIM_1741_update/"
                            "040_FISEC_CHAPTER_21/020-FIM1741_21-26-00-810-801-A-.xml",
                "chapter": "/prod/techpubs/FIM_1741_update/040_FISEC_CHAPTER_21",
            },
            {
                "data": "lista de mensagens cas",
                "title": "fim-1741 - lista de mensagens cas",
                "revision": "U",
                "tsn": "2",
                "filename": "/prod/techpubs/FIM_1741_update/010_FRONTMATTER/010-LISTA.xml",
                "chapter": "/prod/techpubs/FIM_1741_update/010_FRONTMATTER",
            },
            {
                # revision '2' — um dos valores residuais não documentados
                "data": "conteudo qualquer",
                "title": "fim-1741 - documento com revision residual",
                "revision": "2",
                "tsn": "3",
                "filename": "/prod/techpubs/FIM_1741_update/CHAPTER_34/030-OUTRO.xml",
                "chapter": "/prod/techpubs/FIM_1741_update/CHAPTER_34",
            },
        ],
    )
    return manual


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def test_parse_index_le_todos_os_campos(manual_sintetico: Path):
    docs = catalog.parse_index(manual_sintetico / "index_2.0")
    assert len(docs) == 3
    assert docs[0]["title"] == "fim-1741 - 21-26-00-810-801-a - sobretemperatura"
    assert docs[0]["revision"] == "R"
    assert set(docs[0]) == set(CAMPOS)


def test_carregar_indice_manual_chaveia_por_nome_de_pdf(manual_sintetico: Path):
    indice = catalog.carregar_indice_manual(manual_sintetico)
    assert set(indice) == {
        "020-FIM1741_21-26-00-810-801-A-.PDF",
        "010-LISTA.PDF",
        "030-OUTRO.PDF",
    }


def test_iter_index_e_streaming_nao_materializa(manual_sintetico: Path):
    """
    `iter_index` é gerador: o texto de cada documento é liberado assim que o
    consumidor passa adiante. É o que mantém o indexador dentro do orçamento
    de RSS do M4 sobre o acervo inteiro (80 MB de `data` somados).
    """
    it = catalog.iter_index(manual_sintetico / "index_2.0")
    assert isinstance(it, Iterator)
    primeiro = next(it)
    assert primeiro["revision"] == "R"


def test_iter_index_pula_campos_nao_pedidos(manual_sintetico: Path):
    """
    `campos` é o que impede o texto integral (`data`) de ser materializado
    quando ninguém precisa dele — a diferença entre ler alguns KB e 80 MB
    sobre o acervo inteiro.
    """
    doc = next(catalog.iter_index(
        manual_sintetico / "index_2.0", frozenset({"title", "revision"})
    ))
    assert set(doc) == {"title", "revision"}
    assert "data" not in doc

    # Sem filtro, tudo continua vindo — os offsets seguem corretos mesmo
    # depois de pular valores.
    completo = next(catalog.iter_index(manual_sintetico / "index_2.0"))
    assert set(completo) == set(CAMPOS)
    assert completo["data"].startswith("texto do procedimento")


def test_carregar_indice_nao_retem_o_texto(manual_sintetico: Path):
    """O índice leve não carrega o campo `data` — só os metadados."""
    meta = catalog.carregar_indice_manual(manual_sintetico)["010-LISTA.PDF"]
    assert not hasattr(meta, "texto")
    assert meta.titulo == "fim-1741 - lista de mensagens cas"


def test_texto_do_documento_recupera_sob_demanda(manual_sintetico: Path):
    """O texto continua acessível quando alguém quiser o gabarito de qualidade."""
    idx = manual_sintetico / "index_2.0"
    assert catalog.texto_do_documento(idx, "010-LISTA.PDF") == "lista de mensagens cas"
    assert catalog.texto_do_documento(idx, "NAO_EXISTE.PDF") is None


def test_manual_sem_index_nao_quebra(tmp_path: Path):
    """Enriquecimento por Lucene é opcional — ausência cai no fallback, sem erro."""
    (tmp_path / "MANUAL_NOVO").mkdir()
    assert catalog.carregar_indice_manual(tmp_path / "MANUAL_NOVO") == {}


def test_indice_corrompido_nao_derruba_o_lote(tmp_path: Path, caplog):
    """Índice ilegível degrada para 'sem enriquecimento', não para exceção."""
    manual = tmp_path / "MANUAL_QUEBRADO"
    index_dir = manual / "index_2.0"
    index_dir.mkdir(parents=True)
    (index_dir / "_0.fnm").write_bytes(b"\xfd\x06lixo")
    (index_dir / "_0.fdt").write_bytes(b"nada disso e valido")
    (index_dir / "_0.fdx").write_bytes(b"\x00\x00\x00\x00\xff")

    assert catalog.carregar_indice_manual(manual) == {}


# --------------------------------------------------------------------------
# Armadilhas documentadas em 02_formato_indice_lucene.md §6
# --------------------------------------------------------------------------


def test_filename_absoluto_do_servidor_vira_basename_pdf():
    """Armadilha 1: `filename` é caminho do servidor da Embraer, não do disco local."""
    origem = ("/prod/techpubs/app/webupdate-embnetwork/bin/Update_Delta/Output/"
              "Data-ALX/Data/FIM_1741_update/040_FISEC_CHAPTER_28/"
              "020-FIM1741_CHAPTER28-TITLEPAGE.xml")
    assert catalog.nome_pdf_de_filename(origem) == "020-FIM1741_CHAPTER28-TITLEPAGE.PDF"


def test_chapter_e_caminho_nao_nome_pronto():
    """Armadilha 4: só o último segmento de `chapter` é o nome real da pasta."""
    assert catalog.capitulo_de_chapter(
        "/prod/techpubs/FIM_1741_update/040_FISEC_CHAPTER_28"
    ) == "040_FISEC_CHAPTER_28"


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("U", RevisionStatus.UNCHANGED),
        ("R", RevisionStatus.REVISED),
        ("N", RevisionStatus.NOVO),
        # Armadilha 3: os três valores residuais não viram um dos estados
        # documentados por chute — viram DESCONHECIDO.
        ("0", RevisionStatus.DESCONHECIDO),
        ("1", RevisionStatus.DESCONHECIDO),
        ("2", RevisionStatus.DESCONHECIDO),
        ("", RevisionStatus.DESCONHECIDO),
    ],
)
def test_revision_seis_valores_achatados_em_quatro(bruto, esperado):
    meta = catalog.MetadadoLucene(
        titulo="t", revisao=bruto, capitulo="c", nome_pdf="X.PDF"
    )
    assert meta.revision_status is esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("CHAPTER_21", "21"),
        ("040_FISEC_CHAPTER_28", "28"),          # o outro formato do acervo
        ("chapter_34", "34"),                     # insensível a caixa
        ("21-26-00-810-801-A", "21"),             # procedimento do FIM
        ("010_FRONTMATTER", None),                # não tem ATA e isso é normal
        ("", None),
    ],
)
def test_extrair_ata_reconhece_os_formatos_que_convivem(entrada, esperado):
    assert catalog.extrair_ata(entrada) == esperado


def test_extrair_ata_usa_o_primeiro_candidato_que_casa():
    assert catalog.extrair_ata("010_FRONTMATTER", "CHAPTER_71") == "71"


def test_ordem_manda_sem_prefixo_para_o_fim():
    assert catalog.ordem_de_nome("010_FRONTMATTER") == 10
    assert catalog.ordem_de_nome("040_FISEC_CHAPTER_21") == 40
    # Sem prefixo vai para o fim, não para o começo: um documento sem ordem
    # declarada não deve encabeçar a lista.
    assert catalog.ordem_de_nome("CHAPTER_21") == 9999


def test_titulo_de_arquivo_e_fallback_que_nunca_falha():
    """Armadilha 6: RN-02 nível 3, para os documentos sem entrada no índice."""
    assert catalog.titulo_de_arquivo("020-FIM1741_CHAPTER28-TITLEPAGE.PDF") == (
        "FIM1741 CHAPTER28 TITLEPAGE"
    )
    assert catalog.titulo_de_arquivo("Código de Panes.PDF") == "Código de Panes"
    assert catalog.titulo_de_arquivo(".PDF")  # não devolve string vazia


# --------------------------------------------------------------------------
# document_id determinístico
# --------------------------------------------------------------------------


def test_document_id_estavel_entre_reindexacoes_da_mesma_edicao():
    """CA-07: link compartilhado continua abrindo o mesmo documento."""
    a = catalog.documento_id_deterministico("2026", "FIM_1741", "CHAPTER_21/X.PDF")
    b = catalog.documento_id_deterministico("2026", "FIM_1741", "CHAPTER_21/X.PDF")
    assert a == b
    assert isinstance(a, uuid.UUID)


def test_document_id_difere_entre_edicoes():
    """
    B2: sem a edição no input, o mesmo arquivo nas duas edições retidas
    online geraria o mesmo UUID e a primeira publicação anual morreria com
    violação de PK.
    """
    a = catalog.documento_id_deterministico("2026", "FIM_1741", "CHAPTER_21/X.PDF")
    b = catalog.documento_id_deterministico("2027", "FIM_1741", "CHAPTER_21/X.PDF")
    assert a != b


def test_document_id_difere_entre_manuais_e_arquivos():
    base = catalog.documento_id_deterministico("2026", "FIM_1741", "C/X.PDF")
    assert base != catalog.documento_id_deterministico("2026", "AMM_PART1_1651", "C/X.PDF")
    assert base != catalog.documento_id_deterministico("2026", "FIM_1741", "C/Y.PDF")


def test_namespace_nao_mudou():
    """
    Guarda de contrato: mudar o namespace invalida TODO link já compartilhado.
    Se este teste falhar, a mudança foi deliberada? Quase certamente não.
    """
    assert catalog._NAMESPACE_PUBLICACOES == uuid.UUID(
        "6f5a1c9e-6a3b-4b1a-9f0e-2c8d4a7b1e3f"
    )


# --------------------------------------------------------------------------
# fim.json e categorias
# --------------------------------------------------------------------------


def test_carregar_fim_json_deduplica_mensagem(tmp_path: Path):
    caminho = tmp_path / "fim.json"
    caminho.write_text(
        '[{"mensagem": "ADC 001", "procedimento": "34-15-00-810-801-A"},'
        ' {"mensagem": "ADC 001", "procedimento": "OUTRO-PROC"},'
        ' {"mensagem": "ADC 002", "procedimento": "34-15-00-810-801-A"},'
        ' {"mensagem": "", "procedimento": "SEM-MENSAGEM"}]',
        encoding="utf-8",
    )
    pares = catalog.carregar_fim_json(caminho)
    assert pares == [
        ("ADC 001", "34-15-00-810-801-A"),   # primeira ocorrência vence
        ("ADC 002", "34-15-00-810-801-A"),
    ]


def test_nome_pdf_de_procedimento():
    assert catalog.nome_pdf_de_procedimento("34-15-00-810-801-A") == (
        "FIM1741_34-15-00-810-801-A-.PDF"
    )


def test_categorias_aplicam_default_e_substituem_placeholder(tmp_path: Path):
    caminho = tmp_path / "cats.toml"
    caminho.write_text(
        '[FIM_1741]\ncategoria = "Manutenção"\ndescricao_pt = "FIM — panes"\n'
        '[_default]\ncategoria = "Outros"\ndescricao_pt = "{codigo}"\n',
        encoding="utf-8",
    )
    mapa = catalog.carregar_categorias(caminho)

    conhecido = catalog.categoria_de_manual(mapa, "FIM_1741")
    assert (conhecido.categoria, conhecido.descricao_pt) == ("Manutenção", "FIM — panes")

    # E-04: manual desconhecido é indexado, não derruba o lote
    novo = catalog.categoria_de_manual(mapa, "MANUAL_QUE_NAO_EXISTE")
    assert novo.categoria == "Outros"
    assert novo.descricao_pt == "MANUAL_QUE_NAO_EXISTE"


def test_categorias_arquivo_ausente_nao_quebra(tmp_path: Path):
    mapa = catalog.carregar_categorias(tmp_path / "nao_existe.toml")
    assert catalog.categoria_de_manual(mapa, "QUALQUER").categoria == "Outros"


def test_categorias_reais_cobrem_o_toml_do_repositorio():
    """O TOML versionado precisa ser válido e ter o _default (E-04)."""
    mapa = catalog.carregar_categorias(Path("config/categorias_manuais.toml"))
    assert "_default" in mapa
    assert len([k for k in mapa if not k.startswith("_")]) == 34
    assert catalog.categoria_de_manual(mapa, "FIM_1741").categoria == "Manutenção"


# --------------------------------------------------------------------------
# Regressão contra o acervo real (pulada no CI)
# --------------------------------------------------------------------------


@sem_acervo
def test_regressao_acervo_real_numeros_do_documento():
    """
    Os números de 02_formato_indice_lucene.md §7, afirmados como regressão.

    Se isto falhar, a primeira hipótese é 'o acervo mudou'; a segunda é 'o
    parser regrediu'. Não as duas ao mesmo tempo.
    """
    total_docs = 0
    indices_ok = 0
    revisions: dict[str, int] = {}

    for manual_dir in sorted(ACERVO.iterdir()):
        if not (manual_dir / "index_2.0").is_dir():
            continue
        indices_ok += 1
        # Só o campo `revision`: são 80 MB de texto somados no acervo e este
        # teste não tem uso nenhum para eles.
        for d in catalog.iter_index(manual_dir / "index_2.0", frozenset({"revision"})):
            total_docs += 1
            rev = d.get("revision", "")
            revisions[rev] = revisions.get(rev, 0) + 1

    assert indices_ok == 34
    assert total_docs == 5719
    assert revisions == {"U": 2256, "R": 3266, "N": 181, "0": 8, "1": 2, "2": 6}


@sem_acervo
def test_regressao_acervo_real_todo_filename_casa_com_pdf_fisico():
    """
    §7: mapeamento filename→PDF existente = 5.719/5.719 (100%).

    Prova que `nome_pdf_de_filename` está correto contra o disco de verdade,
    e não só contra o exemplo do documento.
    """
    casados = 0
    total = 0
    for manual_dir in sorted(ACERVO.iterdir()):
        indice = catalog.carregar_indice_manual(manual_dir)
        if not indice:
            continue
        fisicos = {p.name.upper() for p in manual_dir.rglob("*") if p.suffix.upper() == ".PDF"}
        total += len(indice)
        casados += len(set(indice) & fisicos)

    assert total == 5719
    assert casados == 5719


@sem_acervo
def test_regressao_fim_json_e_cobertura_do_piloto():
    """
    1.377 mensagens únicas → 253 procedimentos, e **todos** têm PDF no acervo.

    Era 249/253 enquanto a contagem era feita contra a cópia versionada em
    `docs/fim/`. Aquela cópia estava incompleta: faltavam 4 procedimentos, e as
    revisões dos PDFs eram diferentes das do acervo. Ao medir contra o acervo
    real — que é o que a aplicação indexa — a cobertura fecha em 100%.
    """
    pares = catalog.carregar_fim_json(Path("fim.json"))
    assert len(pares) == 1377
    assert len({m for m, _ in pares}) == 1377

    procedimentos = {p for _, p in pares}
    assert len(procedimentos) == 253

    # `rglob`, não `glob`: no acervo os PDFs ficam sob
    # `FIM_1741/040_FISEC_CHAPTER_NN/`, não soltos na raiz do manual.
    pdfs = {p.name.upper() for p in (ACERVO / "FIM_1741").rglob("*.PDF")}
    com_pdf = {p for p in procedimentos if catalog.nome_pdf_de_procedimento(p) in pdfs}
    assert len(com_pdf) == 253, (
        f"todo procedimento do fim.json deve ter PDF no acervo; "
        f"sem PDF: {sorted(procedimentos - com_pdf)}"
    )
