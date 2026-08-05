"""
app/modules/publicacoes/catalog.py
Leitura dos metadados do acervo de manuais.

Três fontes, todas OFFLINE — nada aqui é chamado durante uma requisição:

1. o índice Lucene legado (`<MANUAL>/index_2.0/`), que dá título em português,
   capítulo e estado de revisão para 5.719 dos 5.724 PDFs do acervo;
2. `fim.json`, que mapeia mensagem de falha → procedimento do FIM;
3. `config/categorias_manuais.toml`, que dá categoria e descrição por manual.

O índice Lucene é um artefato READ-ONLY do sistema de origem (Embraer
TechPubs) que viajou junto com o acervo. Ele é lido uma vez, durante a
indexação, e nunca é servido nem copiado para produção. Não confundir com o
`catalog.db` que o módulo constrói — esse é gerado por
`scripts/publicacoes/indexar.py` e é o índice de busca de verdade.

O formato binário foi obtido por engenharia reversa e está documentado em
docs/backlog/modulo_publicacoes/02_formato_indice_lucene.md. Se este arquivo
divergir daquele documento, o documento é a referência.
"""

from __future__ import annotations

import contextlib
import json
import logging
import mmap
import re
import struct
import tomllib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.shared.core.enums import RevisionStatus

logger = logging.getLogger(__name__)


# Namespace do UUID v5 dos documentos. Constante do módulo: nunca gerar
# aleatoriamente, nunca mudar depois do primeiro índice publicado — mudá-lo
# invalida todo link já compartilhado.
_NAMESPACE_PUBLICACOES = uuid.UUID("6f5a1c9e-6a3b-4b1a-9f0e-2c8d4a7b1e3f")

# Os 6 valores reais do campo `revision` do Lucene, achatados nos 4 estados
# que o sistema modela. '0'/'1'/'2' aparecem residualmente e não têm
# significado conhecido — viram DESCONHECIDO em vez de serem chutados em um
# dos três estados documentados.
_MAPA_REVISION = {
    "U": RevisionStatus.UNCHANGED,
    "R": RevisionStatus.REVISED,
    "N": RevisionStatus.NOVO,
}

# Capítulo ATA: 2 dígitos no começo de um nome de capítulo/arquivo. Casa tanto
# `CHAPTER_21` quanto `040_FISEC_CHAPTER_21` (os dois formatos convivem no
# acervo) e também procedimentos como `21-26-00-810-801-A`.
_RE_ATA_CAPITULO = re.compile(r"CHAPTER[_-](\d{2})", re.IGNORECASE)
_RE_ATA_PROCEDIMENTO = re.compile(r"\b(\d{2})-\d{2}-\d{2}")

# Prefixo numérico de ordenação: `010_FRONTMATTER`, `020-FIM1741_...`.
_RE_PREFIXO_ORDEM = re.compile(r"^(\d{1,4})[_-]")

# Campos que o catálogo leve consome. `data` (texto integral) fica de fora de
# propósito — ver iter_index.
_CAMPOS_CATALOGO = frozenset({"title", "revision", "filename", "chapter"})


@dataclass(frozen=True)
class MetadadoLucene:
    """Metadados de um documento, lidos do índice legado."""

    titulo: str
    revisao: str
    capitulo: str
    nome_pdf: str
    """Basename do PDF físico correspondente, em MAIÚSCULAS (chave de casamento)."""

    @property
    def revision_status(self) -> RevisionStatus:
        return _MAPA_REVISION.get(self.revisao, RevisionStatus.DESCONHECIDO)


# --------------------------------------------------------------------------
# Parser do formato Lucene 2.9/3.x (era pré-compound-file)
# --------------------------------------------------------------------------


def _vint(b: bytes, p: int) -> tuple[int, int]:
    """Lê um VInt do Lucene a partir de `p`. Retorna (valor, nova_posição)."""
    x, sh = 0, 0
    while True:
        by = b[p]
        p += 1
        x |= (by & 0x7F) << sh
        if by < 0x80:
            return x, p
        sh += 7


def _nomes_de_campo(fnm_bytes: bytes) -> list[str]:
    """
    Extrai os nomes de campo de `_0.fnm`, na ordem (o índice é o número do
    campo usado em `_0.fdt`).

    Os 34 índices do acervo têm os mesmos 6 campos, na mesma ordem:
    data · title · revision · tsn · filename · chapter.
    """
    p = 0
    _formato, p = _vint(fnm_bytes, p)   # header de formato — descartado
    count, p = _vint(fnm_bytes, p)
    nomes = []
    for _ in range(count):
        tamanho, p = _vint(fnm_bytes, p)
        nomes.append(fnm_bytes[p:p + tamanho].decode("latin-1"))
        p += tamanho
        p += 1  # 1 byte de flags do campo — não precisamos decodificar
    return nomes


def iter_index(
    index_dir: Path, campos: frozenset[str] | None = None
) -> Iterator[dict[str, str]]:
    """
    Percorre um diretório `index_2.0/` e produz um dicionário por documento.

    Lê apenas `_0.fnm`, `_0.fdx` e `_0.fdt`; os demais arquivos do índice são
    as estruturas de busca invertida do Lucene, que não reaproveitamos — o
    texto é reindexado no FTS5 próprio do módulo.

    Duas decisões de memória, ambas necessárias para o gate do M4 (RSS por
    worker < 200 MB rodando sobre o acervo inteiro):

    1. `_0.fdt` é acessado por **mmap**, não carregado inteiro. O parser faz
       acesso aleatório por offset — exatamente o caso de uso do mmap — e o
       maior arquivo do acervo tem 25 MB, somando 80 MB entre os 34 manuais.

    2. `campos` limita **quais campos são decodificados**. O campo `data`
       carrega o texto integral do documento e responde por quase todo o
       volume do índice; quem só quer título e capítulo passa
       `campos=frozenset({"title", "chapter"})` e o parser pula o valor sem
       nunca materializá-lo como str. `None` decodifica tudo.

    Gerador de propósito: nada fica vivo além do documento corrente.

    ATENÇÃO: este parser é calibrado para ESTES 34 índices, não para o formato
    Lucene em geral. Ver a nota de robustez em 02_formato_indice_lucene.md §2
    antes de apontá-lo para um índice de outra origem.
    """
    nomes = _nomes_de_campo((index_dir / "_0.fnm").read_bytes())
    fdx = (index_dir / "_0.fdx").read_bytes()
    num_docs = (len(fdx) - 4) // 8
    if num_docs <= 0:
        return

    with open(index_dir / "_0.fdt", "rb") as fh, \
            mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as fdt:
        for i in range(num_docs):
            offset = struct.unpack(">q", fdx[4 + i * 8: 12 + i * 8])[0]
            p = offset
            qtd_campos, p = _vint(fdt, p)
            doc: dict[str, str] = {}
            for _ in range(qtd_campos):
                num_campo, p = _vint(fdt, p)
                p += 1  # bits (binário/comprimido) — nunca observado ligado
                tamanho, p = _vint(fdt, p)
                nome = nomes[num_campo]
                if campos is None or nome in campos:
                    doc[nome] = fdt[p:p + tamanho].decode("utf-8", errors="replace")
                p += tamanho
            yield doc


def parse_index(index_dir: Path) -> list[dict[str, str]]:
    """
    Versão materializada de `iter_index`, para uso em teste e inspeção pontual.

    Não usar sobre o acervo inteiro em código de produção: mantém vivo o texto
    de todos os documentos do manual ao mesmo tempo (25 MB no maior deles).
    O indexador usa `iter_index`.
    """
    return list(iter_index(index_dir))


# --------------------------------------------------------------------------
# Normalizações — cada uma existe por causa de uma armadilha medida
# --------------------------------------------------------------------------


def nome_pdf_de_filename(filename: str) -> str:
    """
    Converte o campo `filename` do Lucene no basename do PDF físico.

    O valor armazenado é um caminho ABSOLUTO do servidor de publicação da
    Embraer, apontando para o XML de origem — nunca para o disco local:

        /prod/techpubs/.../FIM_1741_update/040_FISEC_CHAPTER_28/020-FIM...xml

    Só o último segmento interessa, com a extensão trocada para .PDF.
    Devolvido em MAIÚSCULAS porque o acervo mistura `.PDF` e `.pdf` e o
    casamento precisa ser insensível a caixa.
    """
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    return f"{base}.PDF".upper()


def capitulo_de_chapter(chapter: str) -> str:
    """
    Extrai o nome do capítulo do campo `chapter`, que é um CAMINHO e não um
    nome pronto. O último segmento é o nome real da pasta — coerente com o
    diretório físico onde o PDF está (`CHAPTER_21`, `040_FISEC_CHAPTER_28`).
    """
    return chapter.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()


def extrair_ata(*candidatos: str) -> str | None:
    """
    Deduz o código ATA (2 dígitos) a partir do capítulo ou do nome do arquivo.

    Reconhece os dois formatos que convivem no acervo (`CHAPTER_21` e
    `040_FISEC_CHAPTER_21`) por regex, nunca por posição fixa na string, e
    também o formato de procedimento do FIM (`21-26-00-810-801-A`).

    Devolve None quando nenhum candidato casa — `ata_codigo` é nullable de
    propósito: o acervo cobre 28 capítulos ATA e o SAA29 cataloga 8, então
    não há FK aqui e a ausência é normal, não erro.
    """
    for c in candidatos:
        if not c:
            continue
        m = _RE_ATA_CAPITULO.search(c)
        if m:
            return m.group(1)
        m = _RE_ATA_PROCEDIMENTO.search(c)
        if m:
            return m.group(1)
    return None


def ordem_de_nome(nome: str) -> int:
    """
    Prefixo numérico do nome do arquivo/diretório, que dá a ordenação natural
    do acervo (RN-05): `010_FRONTMATTER` vem antes de `CHAPTER_21`.

    Sem prefixo devolve 9999, jogando o item para o fim em vez de para o
    começo — um documento sem ordem declarada não deve encabeçar a lista.
    """
    m = _RE_PREFIXO_ORDEM.match(nome)
    return int(m.group(1)) if m else 9999


def titulo_de_arquivo(nome_pdf: str) -> str:
    """
    Título de fallback derivado do nome do arquivo — nível 3 da RN-02, usado
    quando o documento não tem entrada no índice Lucene (5 casos no acervo
    inteiro) ou quando o manual não trouxe `index_2.0/`.

    Nunca falha: é o último nível da cadeia de fallback, então precisa
    devolver algo legível para qualquer entrada.
    """
    base = Path(nome_pdf).stem
    base = _RE_PREFIXO_ORDEM.sub("", base)          # tira o prefixo de ordem
    base = base.replace("_", " ").replace("-", " ")
    base = re.sub(r"\s+", " ", base).strip()
    return base or Path(nome_pdf).stem


def documento_id_deterministico(
    edicao_rotulo: str, manual_codigo: str, file_key: str
) -> uuid.UUID:
    """
    UUID v5 de um documento, derivado de (edição, manual, caminho relativo).

    Estável entre reindexações DA MESMA edição — é o que faz um link
    compartilhado continuar abrindo o mesmo documento (CA-07) — e distinto
    entre edições diferentes.

    A edição faz parte do input de propósito: o ciclo de republicação mantém
    duas edições online ao mesmo tempo, e o mesmo arquivo existe nas duas. Sem
    o rótulo no input, as duas gerariam o mesmo UUID e a primeira publicação
    anual morreria com violação de PK.
    """
    return uuid.uuid5(
        _NAMESPACE_PUBLICACOES, f"{edicao_rotulo}/{manual_codigo}/{file_key}"
    )


# --------------------------------------------------------------------------
# Carga das três fontes
# --------------------------------------------------------------------------


def carregar_indice_manual(manual_dir: Path) -> dict[str, MetadadoLucene]:
    """
    Lê o `index_2.0/` de um manual e devolve {NOME_PDF_MAIUSCULO: metadado}.

    O enriquecimento por Lucene é OPCIONAL: manual sem `index_2.0/` devolve
    dicionário vazio e o indexador cai em `titulo_de_arquivo` para todos os
    seus PDFs, sem erro. Isso é o comportamento esperado para publicações
    futuras, que não necessariamente trazem o índice legado junto.

    O dicionário é por manual, nunca global: dois manuais podem ter arquivos
    de mesmo basename em capítulos homônimos, então o casamento tem de ficar
    contido na árvore do próprio manual.
    """
    index_dir = manual_dir / "index_2.0"
    if not index_dir.is_dir():
        logger.info("Manual %s sem index_2.0/ — usando nome de arquivo como título.",
                    manual_dir.name)
        return {}

    indice: dict[str, MetadadoLucene] = {}
    try:
        # `data` fica de fora do conjunto de campos de propósito: é o texto
        # integral do documento, responde por quase todo o volume do índice, e
        # o catálogo leve não tem uso para ele. O texto que vai ao índice de
        # busca é o extraído página a página do PDF, não este.
        for doc in iter_index(index_dir, _CAMPOS_CATALOGO):
            filename = doc.get("filename", "")
            if not filename:
                continue
            nome_pdf = nome_pdf_de_filename(filename)
            indice[nome_pdf] = MetadadoLucene(
                titulo=doc.get("title", "").strip(),
                revisao=doc.get("revision", "").strip(),
                capitulo=capitulo_de_chapter(doc.get("chapter", "")),
                nome_pdf=nome_pdf,
            )
    except (OSError, ValueError, IndexError, struct.error, UnicodeDecodeError):
        # Índice ilegível não derruba o lote: o manual inteiro cai no fallback
        # de nome de arquivo, que é exatamente o nível 3 da RN-02. Devolve o
        # que já leu ser parcial é pior que não enriquecer nada — descarta.
        logger.exception(
            "Falha ao ler o índice Lucene de %s — seguindo sem enriquecimento.",
            manual_dir.name,
        )
        return {}
    return indice


def texto_do_documento(index_dir: Path, nome_pdf: str) -> str | None:
    """
    Texto integral de UM documento segundo o Lucene, ou None se não houver.

    Existe para o gabarito de qualidade da extração: comparar um trecho deste
    texto com o que o pypdfium2 extraiu detecta extração corrompida sem
    inspeção manual. Não tem quebra de página — foram medidas zero ocorrências
    de form feed — então não construir paginação a partir dele.
    """
    alvo = nome_pdf.upper()
    with contextlib.suppress(OSError, ValueError, IndexError, struct.error):
        for doc in iter_index(index_dir, frozenset({"filename", "data"})):
            if nome_pdf_de_filename(doc.get("filename", "")) == alvo:
                return doc.get("data", "")
    return None


def carregar_fim_json(caminho: Path) -> list[tuple[str, str]]:
    """
    Lê `fim.json` e devolve [(mensagem, procedimento)], sem duplicatas de
    mensagem e em ordem estável.

    O arquivo real tem 1.377 entradas com 1.377 mensagens únicas apontando
    para 253 procedimentos — a unicidade da mensagem foi verificada contra o
    dado, e é o que sustenta a UniqueConstraint da tabela. A deduplicação
    aqui é defesa para remessas futuras, não correção do arquivo atual.
    """
    bruto = json.loads(caminho.read_text(encoding="utf-8"))

    vistas: set[str] = set()
    pares: list[tuple[str, str]] = []
    for entrada in bruto:
        mensagem = (entrada.get("mensagem") or "").strip()
        procedimento = (entrada.get("procedimento") or "").strip()
        if not mensagem or not procedimento:
            continue
        if mensagem in vistas:
            logger.warning(
                "fim.json: mensagem duplicada %r ignorada (primeira ocorrência vence).",
                mensagem,
            )
            continue
        vistas.add(mensagem)
        pares.append((mensagem, procedimento))
    return pares


def nome_pdf_de_procedimento(procedimento: str) -> str:
    """
    Nome do PDF que contém um procedimento do FIM.

    Convenção medida em `docs/fim/` e no `FIM_1741` do acervo:
    `34-15-00-810-801-A` → `FIM1741_34-15-00-810-801-A-.PDF` (o hífen antes da
    extensão faz parte do nome, não é engano).
    """
    return f"FIM1741_{procedimento}-.PDF".upper()


@dataclass(frozen=True)
class CategoriaManual:
    categoria: str
    descricao_pt: str


def carregar_categorias(caminho: Path) -> dict[str, CategoriaManual]:
    """
    Lê `categorias_manuais.toml`. A chave `_default` é obrigatória e é o que
    garante que um manual desconhecido seja indexado em vez de derrubar o
    lote (E-04). Arquivo ausente também cai no default embutido.
    """
    padrao = CategoriaManual(categoria="Outros", descricao_pt="{codigo}")
    if not caminho.is_file():
        logger.warning(
            "categorias_manuais.toml não encontrado em %s — todo manual cairá em 'Outros'.",
            caminho,
        )
        return {"_default": padrao}

    dados = tomllib.loads(caminho.read_text(encoding="utf-8"))
    mapa: dict[str, CategoriaManual] = {}
    for codigo, valores in dados.items():
        mapa[codigo] = CategoriaManual(
            categoria=valores.get("categoria", padrao.categoria),
            descricao_pt=valores.get("descricao_pt", padrao.descricao_pt),
        )
    mapa.setdefault("_default", padrao)
    return mapa


def categoria_de_manual(
    mapa: dict[str, CategoriaManual], codigo: str
) -> CategoriaManual:
    """
    Resolve categoria/descrição de um manual, aplicando o fallback e
    substituindo o placeholder `{codigo}` pelo nome real do diretório.
    """
    entrada = mapa.get(codigo) or mapa["_default"]
    return CategoriaManual(
        categoria=entrada.categoria,
        descricao_pt=entrada.descricao_pt.replace("{codigo}", codigo),
    )
