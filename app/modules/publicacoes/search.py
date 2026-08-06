"""
app/modules/publicacoes/search.py
Busca full-text no `catalog.db` — camada isolada, `sqlite3` puro.

Três regras que este arquivo existe para cumprir:

1. **Nunca SQLAlchemy.** Abrir o `catalog.db` por `create_async_engine`
   dispararia o listener global de backup R2 do banco principal — poluição de
   log e upload espúrio a cada busca (ADR-004, risco R21). Precedente de
   `sqlite3` read-only no repositório: `scripts/maintenance/r2_manager.py:122`.

2. **Uma conexão por consulta, nunca cacheada.** Além de eliminar qualquer
   questão de thread-safety, é o que torna a ativação de edição do M4 atômica:
   trocar o índice é um `os.replace`, e como nenhum handle fica aberto entre
   consultas, a busca seguinte já lê o arquivo novo. Uma conexão cacheada
   continuaria lendo o inode antigo, em silêncio. O custo de abertura (~1 ms)
   é irrelevante frente ao alvo de p95 < 300 ms.

3. **Tudo dentro de `asyncio.to_thread`.** `sqlite3` é bloqueante e o projeto é
   async de ponta a ponta; a regra ASYNC do ruff reprova o contrário.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Sentinelas de realce. Caracteres de controle, não `<mark>`: o cliente escapa
# o snippet inteiro e só então troca os sentinelas pela tag. Emitir `<mark>`
# aqui seria XSS — o texto ao redor vem de PDF e, nas avulsas, de ementa
# digitada por usuário (achado B8).
MARCA_INICIO = "\x02"
MARCA_FIM = "\x03"

# Tokens da query do usuário: letras/dígitos/`_` (com acento), mais `-` e `/`
# no meio da palavra, que é o formato dos códigos de procedimento
# (`34-15-00-810-801-A`) e dos capítulos (`36-11-00/200`).
_RE_TOKEN = re.compile(r"[^\W_]+(?:[-/][^\W_]+)*", re.UNICODE)

_MAX_TOKENS = 12
_LIMITE_MAXIMO = 100

_SELECT_RESULTADOS = """
SELECT p.document_id  AS document_id,
       p.page_number  AS page_number,
       d.manual_codigo AS manual_codigo,
       d.capitulo      AS capitulo,
       d.titulo        AS titulo,
       d.categoria     AS categoria,
       d.ata_codigo    AS ata_codigo,
       snippet(pages_fts, 0, char(2), char(3), '…', 20) AS snippet,
       bm25(pages_fts) AS score
FROM pages_fts
JOIN pages     p ON p.rowid = pages_fts.rowid
JOIN documents d ON d.document_id = p.document_id
WHERE pages_fts MATCH ?
  AND (? IS NULL OR d.manual_codigo = ?)
  AND (? IS NULL OR d.capitulo = ?)
  AND (? IS NULL OR d.categoria = ?)
  AND (? IS NULL OR d.ata_codigo = ?)
-- `bm25()` do SQLite é NEGATIVO: mais negativo = mais relevante, então a
-- ordenação correta é ASC. `DESC` inverteria o ranking inteiro e passaria em
-- qualquer teste que só verifique "veio resultado".
ORDER BY score ASC
LIMIT ? OFFSET ?
"""

_COUNT_RESULTADOS = """
SELECT count(*)
FROM pages_fts
JOIN pages     p ON p.rowid = pages_fts.rowid
JOIN documents d ON d.document_id = p.document_id
WHERE pages_fts MATCH ?
  AND (? IS NULL OR d.manual_codigo = ?)
  AND (? IS NULL OR d.capitulo = ?)
  AND (? IS NULL OR d.categoria = ?)
  AND (? IS NULL OR d.ata_codigo = ?)
"""


class IndiceIndisponivelError(RuntimeError):
    """`catalog.db` ausente ou ilegível — o acervo ainda não foi indexado."""


class QueryInvalidaError(ValueError):
    """A query do usuário não sobrou nada depois da sanitização (E-06)."""


def sanitizar_query(bruta: str) -> str:
    """
    Converte texto livre em uma expressão MATCH segura (RN-10).

    O FTS5 tem sintaxe própria — `AND`, `OR`, `NOT`, `NEAR`, `*`, `"`, `(`, `:`
    — e um usuário digitando `sangria "` produz erro de sintaxe do SQLite, que
    sem tratamento vira 500 (E-06). Em vez de tentar escapar a sintaxe, a
    entrada é reduzida a tokens e cada um vira uma **frase entre aspas**: aí
    nenhum caractere do usuário é operador, e o comportamento fica previsível.

    Consequência aceita: não há como o usuário pedir OR ou proximidade pela
    caixa de busca. É a troca certa — a alternativa é expor sintaxe de motor de
    busca a mecânico de linha de voo e transformar erro de digitação em 500.

    `*` no fim de um token é preservado como prefixo, que é a única funcionali-
    dade avançada com uso real ("procedimento 36-11*").
    """
    if not bruta or not bruta.strip():
        raise QueryInvalidaError("Informe um termo de busca.")

    termos: list[str] = []
    for match in _RE_TOKEN.finditer(bruta):
        token = match.group(0)
        prefixo = bruta[match.end():match.end() + 1] == "*"
        # Aspas duplas dentro do token são impossíveis (o regex não as captura),
        # então a frase entre aspas é sempre bem formada.
        termos.append(f'"{token}"*' if prefixo else f'"{token}"')
        if len(termos) >= _MAX_TOKENS:
            break

    if not termos:
        raise QueryInvalidaError(
            "A busca precisa de ao menos uma palavra ou número."
        )
    return " ".join(termos)


def _abrir_catalog_ro(caminho: Path) -> sqlite3.Connection:
    """
    Abre o índice em modo somente-leitura.

    `mode=ro` na URI, e não apenas "não escrever": é o que impede o SQLite de
    criar um arquivo vazio quando o índice não existe — sem isso, o sintoma de
    "acervo não indexado" viraria "busca sempre vazia", que aponta para o lugar
    errado.
    """
    if not caminho.is_file():
        raise IndiceIndisponivelError(f"Índice de busca ausente: {caminho}")
    conn = sqlite3.connect(f"file:{caminho.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _buscar_sincrono(
    caminho: Path,
    expressao: str,
    *,
    manual: str | None,
    capitulo: str | None,
    categoria: str | None,
    ata: str | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, object]]]:
    conn = _abrir_catalog_ro(caminho)
    try:
        filtros = (
            manual, manual, capitulo, capitulo, categoria, categoria, ata, ata,
        )
        try:
            total = conn.execute(
                _COUNT_RESULTADOS, (expressao, *filtros)
            ).fetchone()[0]
            linhas = conn.execute(
                _SELECT_RESULTADOS, (expressao, *filtros, limit, offset)
            ).fetchall()
        except sqlite3.OperationalError as exc:
            # A sanitização já deveria ter impedido isto; se chegou aqui, é bug
            # nosso e não do usuário — mas ainda assim vira 400, nunca 500.
            logger.warning("Expressão MATCH rejeitada pelo SQLite: %r", expressao)
            raise QueryInvalidaError("Termo de busca inválido.") from exc
        return total, [dict(linha) for linha in linhas]
    finally:
        conn.close()


async def buscar(
    caminho_indice: Path,
    query: str,
    *,
    manual: str | None = None,
    capitulo: str | None = None,
    categoria: str | None = None,
    ata: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """
    Busca full-text paginada.

    `total` é a contagem de **páginas** que casam, não de documentos — coerente
    com o contrato da API, em que cada resultado é uma página. Um documento com
    o termo em 3 páginas contribui 3.

    `ata` filtra por `documents.ata_codigo` (M3 tarefa 5) — coluna derivada por
    `catalog.extrair_ata` no indexador, não confiável para 100% do acervo (nem
    todo capítulo/nome de arquivo expõe o código), mas cobre a maioria.
    """
    expressao = sanitizar_query(query)
    limit = max(1, min(limit, _LIMITE_MAXIMO))
    offset = max(0, offset)

    inicio = time.perf_counter()
    total, linhas = await asyncio.to_thread(
        _buscar_sincrono,
        caminho_indice,
        expressao,
        manual=manual,
        capitulo=capitulo,
        categoria=categoria,
        ata=ata,
        limit=limit,
        offset=offset,
    )
    return {
        "query": query,
        "total": total,
        "took_ms": int((time.perf_counter() - inicio) * 1000),
        "results": linhas,
    }


def _status_sincrono(caminho: Path) -> dict[str, object]:
    conn = _abrir_catalog_ro(caminho)
    try:
        documentos = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
        paginas = conn.execute("SELECT count(*) FROM pages").fetchone()[0]
        manuais = conn.execute(
            "SELECT count(DISTINCT manual_codigo) FROM documents"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "disponivel": True,
        "caminho": str(caminho),
        "documentos": documentos,
        "paginas": paginas,
        "manuais": manuais,
        "atualizado_em": caminho.stat().st_mtime,
    }


async def status_indice(caminho_indice: Path) -> dict[str, object]:
    """
    Estado do índice para `GET /publicacoes/api/status`.

    Índice ausente é resposta válida (`disponivel: False`), não erro: é o estado
    normal antes da primeira indexação, e é o que faz a UI mostrar estado vazio
    em vez de erro (E-12).
    """
    try:
        return await asyncio.to_thread(_status_sincrono, caminho_indice)
    except IndiceIndisponivelError:
        return {
            "disponivel": False,
            "caminho": str(caminho_indice),
            "documentos": 0,
            "paginas": 0,
            "manuais": 0,
            "atualizado_em": None,
        }
