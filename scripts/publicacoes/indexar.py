"""
scripts/publicacoes/indexar.py
Indexação OFFLINE do acervo de manuais.

    python -m scripts.publicacoes.indexar --entrada docs/fim --edicao piloto-fim
    python -m scripts.publicacoes.indexar --entrada var/publicacoes/acervo/Manuais --edicao 2026
    python -m scripts.publicacoes.indexar --entrada docs/fim --dry-run

O que faz, nesta ordem:

1. descobre os manuais dentro de `--entrada` (um diretório por manual, ou o
   próprio diretório quando os PDFs estão soltos — é o caso de `docs/fim/`);
2. enriquece os metadados com o índice Lucene legado do manual correspondente
   no acervo, quando ele existir (opcional — sem ele o título vem do nome do
   arquivo, RN-02 nível 3);
3. extrai o texto **página a página** com `pypdfium2` e monta o `catalog.db`
   (`documents` + `pages` + `pages_fts`), com `rebuild` + `optimize` ao final;
4. grava o catálogo leve no banco principal via `publicacoes.service`;
5. resolve `manuais_fim_map` quando há um `fim.json` na entrada.

Duas regras que este script existe para respeitar:

- **`rebuild` não é opcional.** O FTS5 de conteúdo externo não se popula ao
  inserir em `pages`, e `count(*) FROM pages_fts` devolve o número certo mesmo
  assim — um teste de fumaça por contagem passa enquanto toda busca retorna
  zero (achado B7). Por isso o final da carga faz `rebuild`/`optimize` e o
  script **valida por busca real**, nunca por contagem.
- **PDF corrompido nunca derruba o lote** (E-02): o documento entra no catálogo
  com `has_text=False` e simplesmente não aparece na busca full-text — segue
  navegável e abrível no viewer, que é o que E-01 exige.

Escopo de uma execução: o `catalog.db` é **reconstruído por inteiro** a partir
de `--entrada`; o banco principal é reconciliado apenas para os manuais desta
execução. Indexar um subconjunto depois de ter indexado o acervo inteiro
encolhe o índice de busca — o script avisa quando detecta esse caso, em vez de
deixá-lo silencioso.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pypdfium2 as pdfium

from app.bootstrap.config import get_settings
from app.bootstrap.database import get_session_factory

# Registro completo dos models, como em `migrations/env.py`. Um script não
# carrega o `main.py`, que é quem normalmente faz isso — e o registro do
# SQLAlchemy é tudo-ou-nada: importar só `auth` resolve a FK de
# `manuais_edicoes.publicado_por_id` para `usuarios` e então falha no
# `relationship` que Usuario tem com Pane. Ou vem tudo, ou não mapeia.
import app.modules.aeronaves.models     # noqa: F401
import app.modules.auth.models          # noqa: F401
import app.modules.calendario.models    # noqa: F401
import app.modules.efetivo.models       # noqa: F401
import app.modules.equipamentos.models  # noqa: F401
import app.modules.inspecoes.models     # noqa: F401
import app.modules.panes.models         # noqa: F401
import app.modules.vencimentos.models   # noqa: F401
from app.modules.publicacoes import catalog, service
from app.modules.publicacoes.models import Manual
from app.shared.core.enums import RevisionStatus

logger = logging.getLogger("publicacoes.indexar")

# Extensões aceitas. O acervo mistura as duas caixas no mesmo diretório.
_SUFIXOS_PDF = {".pdf", ".PDF"}

# Páginas acumuladas antes de cada `executemany`. Segura o pico de RSS sem
# transformar a carga em um INSERT por página — o gate do M4 é 200 MB por
# worker sobre um acervo de 1 GB.
_LOTE_PAGINAS = 500

# Schema do índice de busca. Fica aqui, e não em migration: `catalog.db` é
# artefato derivado e descartável, fora do Alembic e fora do backup (ADR-004).
_SCHEMA_CATALOG = """
CREATE TABLE documents (
    document_id   TEXT PRIMARY KEY,
    manual_codigo TEXT NOT NULL,
    capitulo      TEXT NOT NULL,
    titulo        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    ata_codigo    TEXT
);
CREATE INDEX ix_documents_manual   ON documents(manual_codigo);
CREATE INDEX ix_documents_capitulo ON documents(capitulo);
CREATE INDEX ix_documents_ata      ON documents(ata_codigo);

CREATE TABLE pages (
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (document_id, page_number)
);
CREATE INDEX ix_pages_document ON pages(document_id);

CREATE VIRTUAL TABLE pages_fts USING fts5(
    text,
    content='pages',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
"""


@dataclass
class ManualEncontrado:
    """Um manual localizado no diretório de entrada."""

    codigo: str
    raiz: Path
    """Diretório a partir do qual os `file_key` são relativos."""
    pdfs: list[Path]


# --------------------------------------------------------------------------
# Descoberta
# --------------------------------------------------------------------------


def _listar_pdfs(diretorio: Path) -> list[Path]:
    return sorted(
        p for p in diretorio.rglob("*") if p.is_file() and p.suffix in _SUFIXOS_PDF
    )


def descobrir_manuais(entrada: Path, codigo_forcado: str | None) -> list[ManualEncontrado]:
    """
    Descobre os manuais em `entrada`, aceitando os dois layouts do projeto.

    - **Acervo** (`var/publicacoes/acervo/Manuais/`): um subdiretório por
      manual, capítulos dentro dele.
    - **Plano** (`docs/fim/`): PDFs soltos na raiz. Vira um manual único, cujo
      código é `--manual` quando informado e o nome do diretório caso contrário.

    A distinção é feita por onde os PDFs estão, não por convenção de nome: um
    diretório com PDFs na raiz é um manual, mesmo que também tenha subpastas.
    """
    if not entrada.is_dir():
        raise FileNotFoundError(f"Diretório de entrada não existe: {entrada}")

    soltos = sorted(
        p for p in entrada.iterdir() if p.is_file() and p.suffix in _SUFIXOS_PDF
    )
    if soltos:
        codigo = codigo_forcado or entrada.name
        return [ManualEncontrado(codigo=codigo, raiz=entrada, pdfs=soltos)]

    manuais: list[ManualEncontrado] = []
    for sub in sorted(p for p in entrada.iterdir() if p.is_dir()):
        pdfs = _listar_pdfs(sub)
        if not pdfs:
            logger.info("Diretório %s não tem PDF — ignorado.", sub.name)
            continue
        manuais.append(ManualEncontrado(codigo=sub.name, raiz=sub, pdfs=pdfs))
    return manuais


def localizar_index_lucene(manual: ManualEncontrado, acervo: Path) -> Path | None:
    """
    Diretório do manual que contém o `index_2.0/`, ou None.

    Procura primeiro dentro do próprio manual (layout do acervo) e depois em
    `<acervo>/Manuais/<codigo>` — é o que permite indexar `docs/fim/` (que não
    traz índice) enriquecido pelo Lucene do `FIM_1741` do acervo, quando o disco
    o tiver. Sem índice, o enriquecimento simplesmente não acontece.
    """
    if (manual.raiz / "index_2.0").is_dir():
        return manual.raiz
    candidato = acervo / "Manuais" / manual.codigo
    if (candidato / "index_2.0").is_dir():
        return candidato
    return None


# --------------------------------------------------------------------------
# Extração
# --------------------------------------------------------------------------


def hash_arquivo(caminho: Path) -> str | None:
    """SHA-256 do arquivo, lido em blocos. None quando o arquivo é ilegível."""
    digest = hashlib.sha256()
    try:
        with open(caminho, "rb") as fh:
            for bloco in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(bloco)
    except OSError:
        logger.exception("Não foi possível ler %s para hash.", caminho)
        return None
    return digest.hexdigest()


def extrair_paginas(caminho: Path) -> tuple[list[str], bool]:
    """
    Texto de cada página do PDF. Devolve (páginas, extração_ok).

    `extração_ok=False` cobre os dois modos de falha que E-02 exige tolerar:
    PDF corrompido (não abre) e PDF sem camada de texto (abre e devolve tudo
    vazio — típico de escaneado). Nos dois casos o documento continua no
    catálogo; só não entra no índice full-text.

    Páginas vazias são preservadas na lista para que o índice de página bata
    com a numeração real do PDF — é o que faz o viewer abrir na página do
    trecho. Elas são descartadas só na hora de gravar em `pages`.
    """
    try:
        pdf = pdfium.PdfDocument(caminho)
    except Exception:  # noqa: BLE001 — a lib levanta tipos variados por página corrompida
        logger.warning("PDF ilegível, seguindo sem texto: %s", caminho.name)
        return [], False

    paginas: list[str] = []
    try:
        for numero in range(len(pdf)):
            try:
                pagina = pdf[numero]
                textpage = pagina.get_textpage()
                # `get_text_bounded`, não `get_text_range`: sem argumentos, o
                # segundo emite UserWarning e redireciona para o primeiro.
                paginas.append(textpage.get_text_bounded() or "")
                textpage.close()
                pagina.close()
            except Exception:  # noqa: BLE001 — uma página ruim não invalida o documento
                logger.warning(
                    "Página %d ilegível em %s — indexada como vazia.",
                    numero + 1,
                    caminho.name,
                )
                paginas.append("")
    finally:
        pdf.close()

    tem_texto = any(p.strip() for p in paginas)
    if not tem_texto:
        logger.info("Sem camada de texto (E-01): %s", caminho.name)
    return paginas, tem_texto


# --------------------------------------------------------------------------
# catalog.db
# --------------------------------------------------------------------------


def abrir_catalog_novo(destino: Path) -> tuple[sqlite3.Connection, Path]:
    """
    Cria um `catalog.db` vazio em um caminho TEMPORÁRIO ao lado do destino.

    A troca pelo arquivo final é um `os.replace` no fim (mesmo filesystem, logo
    atômico): reindexar a edição VIGENTE nunca deixa a busca enxergar um índice
    pela metade.

    Não confundir com ativação de edição: ativar NÃO move arquivo — cada edição
    tem seu `catalog.<rotulo>.db` permanente e o banco é que aponta qual está em
    vigor (ADR-004, "Resolução do índice por edição"). Este `os.replace` é só o
    commit da própria indexação.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".tmp")
    temporario.unlink(missing_ok=True)

    conn = sqlite3.connect(temporario)
    conn.executescript(_SCHEMA_CATALOG)
    conn.commit()
    return conn, temporario


def finalizar_catalog(conn: sqlite3.Connection) -> None:
    """
    `rebuild` + `optimize` do FTS5 — a etapa que não pode ser esquecida (B7).

    Com `content='pages'`, o FTS5 não indexa nada durante os INSERTs em `pages`.
    Sem o `rebuild` abaixo, todo `MATCH` devolve zero enquanto
    `count(*) FROM pages_fts` segue devolvendo o número certo.
    """
    conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    conn.commit()


def validar_por_busca_real(conn: sqlite3.Connection) -> bool:
    """
    Aceite do índice: pega um termo real de uma página gravada e busca por ele.

    Deliberadamente **não** valida por contagem — é a única métrica que não pega
    o B7. Índice legitimamente vazio (nenhum PDF com texto) passa, porque não há
    o que buscar.
    """
    linha = conn.execute(
        "SELECT text FROM pages WHERE length(text) > 40 LIMIT 1"
    ).fetchone()
    if linha is None:
        logger.warning("Nenhuma página com texto — índice vazio (acervo sem OCR?).")
        return True

    termo = next(
        (p for p in linha[0].split() if p.isalpha() and len(p) > 4), None
    )
    if termo is None:
        return True

    achados = conn.execute(
        "SELECT count(*) FROM pages_fts WHERE pages_fts MATCH ?", (termo,)
    ).fetchone()[0]
    if achados == 0:
        logger.error(
            "Índice construído mas a busca por %r não devolve nada — "
            "o rebuild do FTS5 falhou (achado B7).",
            termo,
        )
        return False
    logger.info("Aceite por busca real: %r devolveu %d página(s).", termo, achados)
    return True


# --------------------------------------------------------------------------
# Indexação
# --------------------------------------------------------------------------


def processar_manual(
    manual: ManualEncontrado,
    *,
    edicao_rotulo: str,
    categorias: dict[str, catalog.CategoriaManual],
    acervo: Path,
    conn: sqlite3.Connection | None,
) -> service.ManualPayload:
    """
    Extrai e grava um manual inteiro; devolve o payload do catálogo leve.

    `conn=None` é o modo `--dry-run`: o texto continua sendo extraído (é onde os
    erros de PDF aparecem, e escondê-los tornaria o dry-run inútil), só não é
    gravado.
    """
    dir_lucene = localizar_index_lucene(manual, acervo)
    indice = catalog.carregar_indice_manual(dir_lucene) if dir_lucene else {}
    if dir_lucene:
        logger.info(
            "Manual %s: %d entradas do índice Lucene (%s).",
            manual.codigo,
            len(indice),
            dir_lucene,
        )

    categoria = catalog.categoria_de_manual(categorias, manual.codigo)
    payload = service.ManualPayload(
        codigo=manual.codigo,
        descricao_pt=categoria.descricao_pt[:200],
        categoria=categoria.categoria,
        path=manual.raiz.as_posix(),
    )

    lote: list[tuple[str, int, str]] = []
    documentos: list[tuple[str, str, str, str, str, str | None]] = []
    casados = 0

    for pdf_path in manual.pdfs:
        file_key = pdf_path.relative_to(manual.raiz).as_posix()
        nome = pdf_path.name.upper()
        meta = indice.get(nome)
        if meta is not None:
            casados += 1

        capitulo = meta.capitulo if meta and meta.capitulo else _capitulo_do_caminho(
            pdf_path, manual.raiz
        )
        titulo = (
            meta.titulo
            if meta and meta.titulo
            else catalog.titulo_de_arquivo(pdf_path.name)
        )
        ata_codigo = catalog.extrair_ata(capitulo, pdf_path.name)
        doc_id = catalog.documento_id_deterministico(
            edicao_rotulo, manual.codigo, file_key
        )

        paginas, tem_texto = extrair_paginas(pdf_path)
        payload.documentos.append(
            service.DocumentoPayload(
                id=doc_id,
                capitulo=capitulo[:80],
                ata_codigo=ata_codigo,
                file_key=file_key[:500],
                titulo=titulo[:300],
                sort_order=catalog.ordem_de_nome(pdf_path.name),
                paginas=len(paginas) or None,
                has_text=tem_texto,
                revision_status=(
                    meta.revision_status if meta else RevisionStatus.DESCONHECIDO
                ),
                hash_sha256=hash_arquivo(pdf_path),
            )
        )

        if conn is None:
            continue

        # `str(doc_id)` — forma canônica COM hífens. É o contrato de identidade
        # entre os dois bancos (§2.2.1): quem lê daqui converte de volta com
        # uuid.UUID() antes de qualquer query ORM.
        documentos.append(
            (
                str(doc_id),
                manual.codigo,
                capitulo,
                titulo,
                categoria.categoria,
                ata_codigo,
            )
        )
        for numero, texto in enumerate(paginas, start=1):
            if texto.strip():
                lote.append((str(doc_id), numero, texto))
        if len(lote) >= _LOTE_PAGINAS:
            _gravar_lote(conn, lote)
            lote.clear()

    if conn is not None:
        if lote:
            _gravar_lote(conn, lote)
        conn.executemany(
            "INSERT OR REPLACE INTO documents "
            "(document_id, manual_codigo, capitulo, titulo, categoria, ata_codigo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            documentos,
        )
        conn.commit()

    if indice:
        logger.info(
            "Manual %s: %d/%d PDFs casaram com o índice Lucene.",
            manual.codigo,
            casados,
            len(manual.pdfs),
        )
    return payload


def _capitulo_do_caminho(pdf_path: Path, raiz: Path) -> str:
    """
    Capítulo deduzido do diretório físico — nível 2 da cadeia, usado quando o
    índice Lucene não cobre o documento.

    PDF na raiz do manual (layout de `docs/fim/`) não tem capítulo: devolve
    string vazia em vez de inventar um, e a UI trata isso como "sem capítulo".
    """
    relativo = pdf_path.relative_to(raiz).parent
    return "" if relativo == Path(".") else relativo.parts[-1]


def _gravar_lote(conn: sqlite3.Connection, lote: list[tuple[str, int, str]]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO pages (document_id, page_number, text) VALUES (?, ?, ?)",
        lote,
    )
    conn.commit()


# --------------------------------------------------------------------------
# Banco principal
# --------------------------------------------------------------------------


async def gravar_no_banco_principal(
    payloads: list[service.ManualPayload],
    *,
    edicao_rotulo: str,
    fim_json: Path | None,
) -> None:
    """Persiste o catálogo leve e o mapa do FIM, em uma transação só."""
    from sqlalchemy import select

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            edicao = await service.obter_ou_criar_edicao(session, edicao_rotulo)

            codigos_da_execucao = {p.codigo for p in payloads}
            ja_no_banco = set(
                (
                    await session.execute(
                        select(Manual.codigo).where(Manual.edicao_id == edicao.id)
                    )
                ).scalars()
            )
            fora_da_execucao = ja_no_banco - codigos_da_execucao
            if fora_da_execucao:
                # Não é erro — mas o catalog.db acabou de ser reconstruído só
                # com esta entrada, então estes manuais continuam navegáveis e
                # somem da busca. Avisar é o que impede o sintoma silencioso.
                logger.warning(
                    "%d manual(is) da edição %r estão no catálogo mas fora desta "
                    "execução (%s) — eles saíram do índice de busca. Reindexe o "
                    "acervo inteiro se isso não for intencional.",
                    len(fora_da_execucao),
                    edicao_rotulo,
                    ", ".join(sorted(fora_da_execucao)),
                )

            contagem = await service.sincronizar_catalogo(session, edicao, payloads)
            logger.info(
                "Banco principal: %d manuais, %d documentos novos, %d atualizados, "
                "%d removidos.",
                contagem["manuais"],
                contagem["inseridos"],
                contagem["atualizados"],
                contagem["removidos"],
            )

            if fim_json is not None and fim_json.is_file():
                pares = catalog.carregar_fim_json(fim_json)
                resultado = await service.sincronizar_fim_map(session, pares, edicao)
                logger.info(
                    "Mapa do FIM: %d mensagens, %d com PDF correspondente.",
                    resultado["total"],
                    resultado["com_documento"],
                )

            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def montar_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="python -m scripts.publicacoes.indexar",
        description="Indexa um diretório de PDFs no catálogo e no índice de busca.",
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        default=Path("docs/fim"),
        help="Diretório varrido. Padrão: docs/fim (piloto do M1).",
    )
    parser.add_argument(
        "--edicao",
        default="piloto-fim",
        help="Rótulo da edição. Entra no UUID v5 dos documentos — mudá-lo gera "
        "um catálogo novo, não atualiza o existente.",
    )
    parser.add_argument(
        "--manual",
        default=None,
        help="Código do manual quando os PDFs estão soltos na entrada "
        "(ex: FIM_1741 para docs/fim). Ignorado no layout do acervo.",
    )
    parser.add_argument(
        "--indice",
        type=Path,
        default=None,
        help="Destino do catalog.db. Padrão: catalog.<edicao>.db ao lado de "
        f"{settings.publicacoes_index_path} — um índice POR EDIÇÃO, para que "
        "reindexar uma edição nova não destrua o índice da edição vigente.",
    )
    parser.add_argument(
        "--acervo",
        type=Path,
        default=Path(settings.publicacoes_acervo_dir),
        help="Acervo consultado apenas para achar o índice Lucene legado.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extrai e relata sem gravar nada (nem catalog.db, nem banco).",
    )
    return parser


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s"
    )
    args = montar_parser().parse_args(argv)

    # O default de `--indice` não pode sair do argparse: ele depende de
    # `--edicao`, que só é conhecida depois do parse.
    indice: Path = args.indice or service.caminho_indice_da_edicao(args.edicao)

    inicio = time.perf_counter()
    entrada: Path = args.entrada
    manuais = descobrir_manuais(entrada, args.manual)
    if not manuais:
        logger.error("Nenhum PDF encontrado em %s.", entrada)
        return 1

    total_pdfs = sum(len(m.pdfs) for m in manuais)
    logger.info(
        "%d manual(is), %d PDF(s) em %s — edição %r%s.",
        len(manuais),
        total_pdfs,
        entrada,
        args.edicao,
        " [DRY-RUN]" if args.dry_run else "",
    )

    categorias = catalog.carregar_categorias(
        Path(get_settings().publicacoes_categorias_path)
    )

    conn: sqlite3.Connection | None = None
    temporario: Path | None = None
    if not args.dry_run:
        conn, temporario = abrir_catalog_novo(indice)

    payloads: list[service.ManualPayload] = []
    try:
        for manual in manuais:
            payloads.append(
                processar_manual(
                    manual,
                    edicao_rotulo=args.edicao,
                    categorias=categorias,
                    acervo=args.acervo,
                    conn=conn,
                )
            )

        if conn is not None and temporario is not None:
            finalizar_catalog(conn)
            if not validar_por_busca_real(conn):
                conn.close()
                temporario.unlink(missing_ok=True)
                return 1
            conn.close()
            conn = None
            os.replace(temporario, indice)
            logger.info("Índice de busca gravado em %s.", indice)
    finally:
        if conn is not None:
            conn.close()

    sem_texto = sum(
        1 for p in payloads for d in p.documentos if not d.has_text
    )
    total_paginas = sum(d.paginas or 0 for p in payloads for d in p.documentos)

    if not args.dry_run:
        fim_json = entrada / "fim.json"
        await gravar_no_banco_principal(
            payloads,
            edicao_rotulo=args.edicao,
            fim_json=fim_json if fim_json.is_file() else None,
        )

    logger.info(
        "Concluído em %.1fs: %d documentos, %d páginas, %d sem camada de texto.",
        time.perf_counter() - inicio,
        sum(len(p.documentos) for p in payloads),
        total_paginas,
        sem_texto,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
