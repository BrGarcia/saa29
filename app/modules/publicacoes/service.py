"""
app/modules/publicacoes/service.py
Serviços do módulo de publicações — camada de acesso ao banco PRINCIPAL.

Divisão de responsabilidade que atravessa o módulo:

- este arquivo fala com o banco principal (catálogo leve, mapa do FIM,
  auditoria de acesso), sempre por `AsyncSession`;
- `search.py` fala com o `catalog.db`, sempre por `sqlite3` puro e read-only.

Os dois nunca se misturam: abrir o `catalog.db` com SQLAlchemy dispararia o
listener global de backup R2 do banco principal (ADR-004, risco R21).

`sincronizar_catalogo` é chamado pelo indexador OFFLINE
(`python -m scripts.publicacoes.indexar`), não por requisição — daí ser a única
função aqui que escreve em lote.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - apenas para anotações
    from app.modules.publicacoes.models import PublicacoesUploadJob

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bootstrap.config import get_settings
from app.modules.publicacoes.models import (
    Manual,
    ManualDocumento,
    ManualEdicao,
    ManualFimMap,
    PublicacaoAcesso,
    PublicacaoFavorito,
)
from app.shared.core.db_utils import escape_like
from app.shared.core.enums import OrigemManual, RevisionStatus, StatusEdicao
from app.shared.core.exceptions import ConflitoNegocioError, EntidadeNaoEncontradaError

logger = logging.getLogger(__name__)

# Teto defensivo de listagem. Existe além dos `le=` do FastAPI porque o service
# também é chamado por scripts, que não passam por Query (precedente:
# inspecoes/service.py).
LIMITE_MAXIMO_LISTAGEM = 100

# Rótulos aceitos na composição do nome de arquivo do índice. `rotulo` é
# `String(20)` de texto livre, criado por script — o regex é o que garante que
# ele não possa introduzir separador de caminho. Como nenhum caractere aceito
# aqui é separador em nenhuma plataforma, `base / f"catalog.{rotulo}.db"` é
# sempre um filho direto de `base`, sem precisar de `resolve()` para provar.
# `\Z` (não `$`) fecha a string de fato — `$` casaria também antes de um `\n`
# final, que a classe de caracteres abaixo não rejeita por si só.
_RE_ROTULO_INDICE = re.compile(r"^[A-Za-z0-9._-]{1,20}\Z")


class RotuloInvalidoError(ValueError):
    """O rótulo da edição não pode compor um nome de arquivo seguro."""


def _validar_rotulo(rotulo: str) -> None:
    """Levanta `RotuloInvalidoError` se `rotulo` não puder compor nome de arquivo."""
    if not _RE_ROTULO_INDICE.match(rotulo):
        raise RotuloInvalidoError(
            f"Rótulo de edição inválido para nome de arquivo: {rotulo!r}. "
            "Aceitos: letras, dígitos, ponto, hífen e sublinhado (até 20)."
        )


@dataclass
class DocumentoPayload:
    """Um documento pronto para gravação, montado pelo indexador."""

    id: uuid.UUID
    capitulo: str
    ata_codigo: str | None
    file_key: str
    titulo: str
    sort_order: int
    paginas: int | None
    has_text: bool
    revision_status: RevisionStatus
    hash_sha256: str | None


@dataclass
class ManualPayload:
    """Um manual e seus documentos, prontos para gravação."""

    codigo: str
    descricao_pt: str
    categoria: str
    path: str
    origem: OrigemManual
    """Qual disco trouxe o manual — entra na identidade (edicao_id, origem, codigo)."""
    documentos: list[DocumentoPayload] = field(default_factory=list)


# --------------------------------------------------------------------------
# Edições
# --------------------------------------------------------------------------


async def obter_ou_criar_edicao(
    db: AsyncSession,
    rotulo: str,
    *,
    status: StatusEdicao | None = None,
) -> ManualEdicao:
    """
    Edição de rótulo `rotulo`, criando-a se ainda não existir.

    O rótulo é o que entra no UUID v5 dos documentos (§2.2), então reindexar a
    mesma edição precisa encontrar a MESMA linha — criar uma segunda edição com
    outro `id` não quebraria os UUIDs (eles derivam do rótulo, não do id), mas
    duplicaria o catálogo inteiro. Daí o get-or-create em vez de insert.

    Se `status` não for informado: se ainda não existir nenhuma edição VIGENTE no
    sistema, a primeira edição é criada como VIGENTE. Caso já exista uma edição
    VIGENTE, a nova é criada como AGUARDANDO_ATIVACAO.
    """
    _validar_rotulo(rotulo)

    edicao = (
        await db.execute(select(ManualEdicao).where(ManualEdicao.rotulo == rotulo))
    ).scalar_one_or_none()
    if edicao is not None:
        return edicao

    if status is None:
        edicao_vigente = await obter_edicao_vigente(db)
        status = StatusEdicao.AGUARDANDO_ATIVACAO if edicao_vigente else StatusEdicao.VIGENTE

    edicao = ManualEdicao(rotulo=rotulo, status=status)
    try:
        async with db.begin_nested():
            db.add(edicao)
            await db.flush()
    except IntegrityError as exc:
        edicao_existente = (
            await db.execute(select(ManualEdicao).where(ManualEdicao.rotulo == rotulo))
        ).scalar_one_or_none()
        if edicao_existente is not None:
            logger.info("Corrida ao criar edição %r (%s); devolvendo a já existente.", rotulo, exc.orig)
            return edicao_existente
        logger.error("Falha ao criar edição %r com status %s: %s", rotulo, status.value, exc.orig)
        raise ConflitoNegocioError(
            f"Não foi possível criar a edição {rotulo!r} com status {status.value!r}. "
            "Já existe outra edição com status VIGENTE no sistema."
        ) from exc

    logger.info("Edição %r criada (status=%s).", rotulo, status.value)
    return edicao


async def obter_equivalente_vigente(
    db: AsyncSession, documento: ManualDocumento
) -> uuid.UUID | None:
    """
    Documento correspondente na edição VIGENTE, ou None quando não há um.

    Casamento por `(manual.codigo, file_key)` — o `document_id` em si NÃO serve
    para achar o equivalente porque inclui a edição no UUID v5 (achado B2), e
    é exatamente por isso que esta função precisa existir: o link do viewer
    aponta para o documento da edição em que foi gerado, e a UI usa isto para
    oferecer o caminho de volta para a edição vigente.

    `.limit(1)` é cinto-e-suspensório deliberado (DÚVIDA-01): o índice único
    parcial `uq_manuais_edicoes_vigente_unica` já garante no máximo uma
    edição VIGENTE — é a garantia primária —, mas `obter_edicao_vigente` usa
    o mesmo `.limit(1)` por segurança, e as duas funções devem concordar em
    vez de uma confiar só no índice e a outra não.
    """
    if documento.manual.edicao.status == StatusEdicao.VIGENTE:
        return None

    return (
        await db.execute(
            select(ManualDocumento.id)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .join(ManualEdicao, ManualEdicao.id == Manual.edicao_id)
            .where(
                Manual.codigo == documento.manual.codigo,
                ManualDocumento.file_key == documento.file_key,
                ManualEdicao.status == StatusEdicao.VIGENTE,
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def obter_edicao_vigente(db: AsyncSession) -> ManualEdicao | None:
    """A edição em vigor, ou None quando o acervo ainda não foi indexado."""
    return (
        await db.execute(
            select(ManualEdicao)
            .where(ManualEdicao.status == StatusEdicao.VIGENTE)
            .order_by(ManualEdicao.data_publicacao.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


# --------------------------------------------------------------------------
# Índice de busca por edição
# --------------------------------------------------------------------------


def caminho_indice_da_edicao(rotulo: str) -> Path:
    """
    Caminho do `catalog.db` da edição `rotulo` — `catalog.<rotulo>.db`.

    Cada edição tem seu próprio índice, lado a lado no mesmo diretório, para
    que ativar uma edição não dependa de mover arquivo nenhum: a edição VIGENTE
    no banco é que decide qual arquivo a busca abre (ver
    `caminho_indice_vigente`, e a seção "Resolução do índice por edição" do
    ADR-004).

    Pura de propósito — não toca o disco, para ser barata e testável isolada.
    """
    _validar_rotulo(rotulo)
    base = Path(get_settings().publicacoes_index_path).parent
    return base / f"catalog.{rotulo}.db"


def resolver_caminho_indice(rotulo: str | None) -> Path:
    """
    Índice a abrir para `rotulo`, com queda para o `catalog.db` legado.

    Síncrona: `is_file()` toca o disco, e a regra ASYNC do ruff (com razão)
    proíbe isso dentro de `async def` — quem chama passa por `asyncio.to_thread`
    (mesmo padrão de `_resolver_pdf` em `router.py`).

    A queda para o legado existe para instalações indexadas ANTES desta
    mudança, que têm um único `var/publicacoes/catalog.db` e nenhum arquivo por
    edição: sem ela, atualizar o código faria a busca devolver zero resultados
    até alguém reindexar — exatamente o sintoma enganoso que o `mode=ro` de
    `_abrir_catalog_ro` existe para evitar. Some sozinha na primeira
    reindexação, e o aviso no log é o que avisa que ainda não aconteceu.
    """
    legado = Path(get_settings().publicacoes_index_path)
    if rotulo is None:
        return legado

    try:
        caminho = caminho_indice_da_edicao(rotulo)
    except RotuloInvalidoError:
        # BUG-01: uma edição com rótulo inválido gravada antes da validação em
        # `obter_ou_criar_edicao` não pode derrubar `/api/busca`/`/api/status`
        # com 500 — mesma queda para o legado do caso "índice ausente" logo
        # abaixo. `search.buscar`/`status_indice` já tratam arquivo ausente
        # como estado vazio, não erro (E-12).
        logger.warning(
            "Edição %r tem rótulo inválido para nome de arquivo; usando o "
            "catalog.db legado (%s).",
            rotulo, legado,
        )
        return legado

    if caminho.is_file():
        return caminho

    if legado.is_file():
        logger.warning(
            "Índice por edição ausente (%s); usando o catalog.db legado (%s). "
            "Rode `python -m scripts.publicacoes.indexar --edicao %s` para migrar.",
            caminho, legado, rotulo,
        )
        return legado

    # Nenhum dos dois existe: devolve o caminho por edição, que é o acionável —
    # é o arquivo que a reindexação vai criar, e é o nome que aparece no erro.
    return caminho


async def _indice_existe(rotulo: str) -> bool:
    """Se o `catalog.<rotulo>.db` daquela edição está em disco."""
    try:
        caminho = caminho_indice_da_edicao(rotulo)
    except RotuloInvalidoError:
        # Rótulo que não compõe nome de arquivo nunca teve índice próprio.
        return False
    return await asyncio.to_thread(caminho.is_file)


async def caminho_indice_vigente(db: AsyncSession) -> Path:
    """
    Índice da edição VIGENTE — o que `GET /api/busca` e `/api/status` abrem.

    Uma consulta indexada a mais por busca (`manuais_edicoes.status` é
    indexado) em troca de a ativação de edição ser um único UPDATE, sem mover
    arquivo e sem janela em que banco e disco discordem. Não há cache aqui de
    propósito: cachear o rótulo exigiria invalidá-lo na ativação, e otimizar
    antes de medir é como se constrói o bug de "ativei e a busca não mudou".
    """
    edicao = await obter_edicao_vigente(db)
    rotulo = edicao.rotulo if edicao is not None else None
    return await asyncio.to_thread(resolver_caminho_indice, rotulo)


# --------------------------------------------------------------------------
# Ciclo de vida da edição (M4 tarefa 4, Fase 1)
# --------------------------------------------------------------------------


async def obter_edicao(db: AsyncSession, edicao_id: uuid.UUID) -> ManualEdicao:
    edicao = await db.get(ManualEdicao, edicao_id)
    if edicao is None:
        raise EntidadeNaoEncontradaError("Edição não encontrada.")
    return edicao


async def listar_edicoes(db: AsyncSession) -> list[dict[str, object]]:
    """
    Todas as edições, com o que a tela de gerência precisa para decidir.

    `indice_disponivel` é conferido no disco, edição por edição: é ele que
    define se "Ativar" pode sequer ser oferecido. Sem essa checagem a tela
    ofereceria um botão que o servidor recusaria — ou, pior, ativaria uma
    edição cuja busca cairia no índice legado.
    """
    linhas = (
        await db.execute(
            select(
                ManualEdicao,
                func.count(func.distinct(Manual.id)),
                func.count(ManualDocumento.id),
            )
            .outerjoin(Manual, Manual.edicao_id == ManualEdicao.id)
            .outerjoin(ManualDocumento, ManualDocumento.manual_id == Manual.id)
            .group_by(ManualEdicao.id)
            .order_by(ManualEdicao.data_publicacao.desc())
        )
    ).all()

    # MELHORIA-02: `_indice_existe` faz `asyncio.to_thread` — despachado em
    # paralelo, não um `await` por vez dentro da comprehension (que seria
    # sequencial, N despachos de thread em série para N edições).
    disponibilidade = await asyncio.gather(
        *(_indice_existe(edicao.rotulo) for edicao, _, _ in linhas)
    )

    return [
        {
            "id": edicao.id,
            "rotulo": edicao.rotulo,
            "status": edicao.status,
            "data_publicacao": edicao.data_publicacao,
            "manuais": int(manuais),
            "documentos": int(documentos),
            "indice_disponivel": indice_disponivel,
            "tem_relatorio": edicao.relatorio_diff is not None,
            "snapshot_key": edicao.snapshot_key,
        }
        for (edicao, manuais, documentos), indice_disponivel in zip(
            linhas, disponibilidade, strict=True
        )
    ]


async def ativar_edicao(
    db: AsyncSession, edicao_id: uuid.UUID, *, usuario_id: uuid.UUID
) -> ManualEdicao:
    """
    Promove `edicao_id` a VIGENTE e rebaixa a vigente atual a ANTERIOR.

    **Reverter é ativar a edição ANTERIOR** — não existe operação inversa
    separada. Um caminho de código, um conjunto de testes, e nenhuma dúvida
    sobre o que "reverter" faz quando há mais de uma edição anterior retida.

    A transação cobre as duas escritas: nunca há instante persistido com duas
    edições vigentes ou nenhuma. E como a busca resolve o índice pela edição
    vigente (`caminho_indice_vigente`), a consulta seguinte ao commit já lê o
    índice novo — sem mover arquivo, sem downtime.

    Três recusas explícitas, todas 409:

    - já VIGENTE: no-op silencioso esconderia um clique que o operador acha
      que fez efeito;
    - ARQUIVADA: os artefatos de disco podem já ter sido descartados;
    - **sem índice em disco**: é a que importa. Sem ela, ativar mudaria o
      status no banco e a busca continuaria devolvendo o conteúdo da edição
      antiga (pela queda para o índice legado) — o botão pareceria funcionar
      e mentiria, que é exatamente o que a Fase 0 existiu para impedir.
    """
    edicao = await obter_edicao(db, edicao_id)

    if edicao.status == StatusEdicao.VIGENTE:
        raise ConflitoNegocioError(f"A edição {edicao.rotulo!r} já é a vigente.")
    if edicao.status == StatusEdicao.ARQUIVADA:
        raise ConflitoNegocioError(
            f"A edição {edicao.rotulo!r} está arquivada — seus artefatos de disco "
            "podem ter sido descartados. Republique-a antes de ativar."
        )
    if not await _indice_existe(edicao.rotulo):
        # `_indice_existe` já devolveu False, o que inclui o caso "rótulo
        # inválido" (BUG-01) — `caminho_indice_da_edicao` levantaria de novo
        # aqui sem proteção, trocando o 409 informativo abaixo por um 500.
        try:
            caminho = caminho_indice_da_edicao(edicao.rotulo)
        except RotuloInvalidoError:
            raise ConflitoNegocioError(
                f"A edição {edicao.rotulo!r} tem um rótulo inválido e não pode "
                "ter índice de busca. Corrija o rótulo antes de ativar."
            ) from None
        raise ConflitoNegocioError(
            f"A edição {edicao.rotulo!r} não tem índice de busca em disco "
            f"({caminho}). Ative apenas depois de "
            f"reindexar: python -m scripts.publicacoes.indexar --edicao {edicao.rotulo}"
        )

    anterior = await obter_edicao_vigente(db)
    if anterior is not None:
        anterior.status = StatusEdicao.ANTERIOR
        # Flush SEPARADO, antes de promover: o índice único parcial
        # `uq_manuais_edicoes_vigente_unica` é verificado por statement, e num
        # flush único o SQLAlchemy pode emitir o UPDATE que promove ANTES do
        # que rebaixa — duas linhas VIGENTE por um instante, e a operação
        # inteira falha com IntegrityError. Libera o lugar, depois ocupa.
        #
        # Continua atômico: os dois flushes estão na MESMA transação, então um
        # rollback desfaz os dois e nunca há commit com o acervo sem vigente.
        await db.flush()

    edicao.status = StatusEdicao.VIGENTE
    # `publicado_por_id` fica nulo quando a edição nasce de script offline (sem
    # usuário logado). A ativação pela tela tem usuário — é a primeira vez que
    # há alguém a quem atribuir a decisão, e é a que importa para auditoria.
    edicao.publicado_por_id = usuario_id
    await db.flush()

    logger.info(
        "Edição %r ativada por %s (anterior: %s).",
        edicao.rotulo, usuario_id, anterior.rotulo if anterior else "nenhuma",
    )
    return edicao


async def excluir_edicao(db: AsyncSession, edicao_id: uuid.UUID) -> ManualEdicao:
    """
    Apaga a edição em definitivo — linha do catálogo + auditoria de acesso.

    Contraria de propósito a garantia "nunca sofre hard delete" do docstring
    de `ManualEdicao` (achado B4): decisão desta fase de implementação, em
    que erros de exportação são frequentes e "arquivar" não tira a edição
    errada do caminho — só descarta artefatos de disco, a linha continua na
    lista. `publicacoes_acessos.edicao_id` é RESTRICT, então as linhas de
    auditoria daquela edição são apagadas antes, na mesma transação: quem usa
    esta função está trocando rastreabilidade por poder de correção rápida,
    conscientemente. Reavaliar quando o sistema for para produção.

    Sem restrição de status — VIGENTE também pode ser excluída. O acervo fica
    sem edição em vigor até outra ser ativada; `obter_edicao_vigente` já trata
    isso como "nenhuma edição", não erro.
    """
    edicao = await obter_edicao(db, edicao_id)
    rotulo = edicao.rotulo

    apagados = (
        await db.execute(
            delete(PublicacaoAcesso).where(PublicacaoAcesso.edicao_id == edicao_id)
        )
    ).rowcount
    if apagados:
        logger.warning(
            "Excluindo edição %r: %d registro(s) de auditoria de acesso apagado(s) junto (RESTRICT).",
            rotulo, apagados,
        )

    await db.delete(edicao)
    await db.flush()

    logger.warning("Edição %r excluída em definitivo.", rotulo)
    return edicao


async def arquivar_edicao(db: AsyncSession, edicao_id: uuid.UUID) -> ManualEdicao:
    """
    Marca a edição como ARQUIVADA.

    Ação **separada** de ativar, e humana: ativar não arquiva a anterior
    sozinha. Arquivar declara que os artefatos de disco daquela edição podem
    ser descartados, e isso não é efeito colateral de publicar outra coisa.

    Não apaga linha nenhuma do catálogo — `publicacoes_acessos` referencia
    documentos de edições velhas e a auditoria precisa sobreviver (achado B4).
    """
    edicao = await obter_edicao(db, edicao_id)

    if edicao.status == StatusEdicao.VIGENTE:
        raise ConflitoNegocioError(
            f"A edição {edicao.rotulo!r} está em vigor — ative outra antes de arquivá-la."
        )
    if edicao.status == StatusEdicao.ARQUIVADA:
        raise ConflitoNegocioError(f"A edição {edicao.rotulo!r} já está arquivada.")

    edicao.status = StatusEdicao.ARQUIVADA
    await db.flush()
    logger.info("Edição %r arquivada.", edicao.rotulo)
    return edicao


# --------------------------------------------------------------------------
# Navegação do catálogo (Etapa 2 de 09_plano_configuracoes.md — lacuna do M1)
#
# Só o banco principal — SQLAlchemy, catálogo LEVE. Nunca toca `catalog.db`;
# isto é navegação, não busca full-text (`search.py` não muda nesta etapa).
# Toda função abaixo é escopada pela edição VIGENTE: navegar mostra o acervo
# em vigor, não a união de edições retidas (um `join` esquecido faria o mesmo
# manual aparecer duas vezes com ids diferentes — achado B2).
# --------------------------------------------------------------------------


async def listar_manuais_vigentes(
    db: AsyncSession, *, origem: str | None = None
) -> list[dict[str, object]]:
    """
    Os manuais da edição vigente, com contagem de capítulos/documentos.

    `outerjoin`, não `join`: um manual sem documento nenhum (indexação falhou
    para ele) não pode sumir da listagem — é como se descobre o problema.

    `origem` filtra por MANUTENCAO/OPERACIONAL quando informado (o toggle do
    explorador); `None` devolve os dois lado a lado — o mesmo `codigo` pode
    aparecer duas vezes, uma por origem, e cabe à UI desambiguar (ver
    `docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md` §6:
    esta rodada não mescla revisão, só lista as duas).
    """
    vigente = await obter_edicao_vigente(db)
    if vigente is None:
        return []

    filtros = [Manual.edicao_id == vigente.id]
    if origem is not None:
        filtros.append(Manual.origem == origem)

    linhas = (
        await db.execute(
            select(
                Manual.codigo,
                Manual.origem,
                Manual.descricao_pt,
                Manual.categoria,
                Manual.revisao,
                func.count(func.distinct(ManualDocumento.capitulo)),
                func.count(ManualDocumento.id),
            )
            .select_from(Manual)
            .outerjoin(ManualDocumento, ManualDocumento.manual_id == Manual.id)
            .where(*filtros)
            .group_by(Manual.id)
            .order_by(Manual.categoria, Manual.codigo, Manual.origem)
        )
    ).all()

    return [
        {
            "codigo": codigo,
            "origem": origem_manual.value,
            "descricao": descricao_pt,
            "categoria": categoria,
            "capitulos": int(capitulos),
            "documentos": int(documentos),
            "revisao": revisao,
        }
        for codigo, origem_manual, descricao_pt, categoria, revisao, capitulos, documentos in linhas
    ]


async def _manual_da_edicao_vigente(
    db: AsyncSession, codigo: str, *, origem: str | None = None
) -> Manual:
    """
    O manual `codigo` na edição VIGENTE, ou 404.

    Escopado pela vigente de propósito: um manual que só existe numa edição
    arquivada não deve aparecer na navegação (achado B2 — o mesmo código de
    manual existe em edições diferentes, com `manual_id` diferente).

    `origem` desambigua quando o mesmo `codigo` existe nos dois discos
    (Manutenção/Operacional) dentro da mesma edição — ver
    `uq_manuais_edicao_origem_codigo`. Quando omitida e há mais de um manual
    com esse código, MANUTENCAO vence (`ORDER BY origem` — "MANUTENCAO" <
    "OPERACIONAL" alfabeticamente): é o caminho de compatibilidade para telas
    que ainda não mandam `origem` (mobile, link antigo); o explorador manda
    sempre que o manual está listado com o filtro "Todos".
    """
    vigente = await obter_edicao_vigente(db)
    if vigente is None:
        raise EntidadeNaoEncontradaError(
            f"Manual {codigo!r} não encontrado na edição vigente."
        )

    filtros = [Manual.edicao_id == vigente.id, Manual.codigo == codigo]
    if origem is not None:
        filtros.append(Manual.origem == origem)

    manual = (
        await db.execute(
            select(Manual).where(*filtros).order_by(Manual.origem).limit(1)
        )
    ).scalar_one_or_none()
    if manual is None:
        raise EntidadeNaoEncontradaError(
            f"Manual {codigo!r} não encontrado na edição vigente."
        )
    return manual


async def obter_cabecalho_manual(
    db: AsyncSession, codigo: str, *, origem: str | None = None
) -> dict[str, str]:
    """Só o cabeçalho (sem capítulos) — usado pelo breadcrumb da página de documentos."""
    manual = await _manual_da_edicao_vigente(db, codigo, origem=origem)
    return {
        "codigo": manual.codigo,
        "origem": manual.origem.value,
        "descricao": manual.descricao_pt,
        "categoria": manual.categoria,
    }


async def obter_manual_com_capitulos(
    db: AsyncSession, codigo: str, *, origem: str | None = None
) -> dict[str, object]:
    """Cabeçalho do manual + capítulos, ordenados pelo prefixo numérico (RN-05)."""
    manual = await _manual_da_edicao_vigente(db, codigo, origem=origem)

    linhas = (
        await db.execute(
            select(
                ManualDocumento.capitulo,
                func.max(ManualDocumento.ata_codigo),
                func.count(ManualDocumento.id),
            )
            .where(ManualDocumento.manual_id == manual.id)
            .group_by(ManualDocumento.capitulo)
            .order_by(ManualDocumento.capitulo)
        )
    ).all()

    return {
        "manual": {
            "codigo": manual.codigo,
            "origem": manual.origem.value,
            "descricao": manual.descricao_pt,
            "categoria": manual.categoria,
        },
        "capitulos": [
            {"capitulo": capitulo, "ata_codigo": ata_codigo, "documentos": int(documentos)}
            for capitulo, ata_codigo, documentos in linhas
        ],
    }


async def listar_documentos_do_manual(
    db: AsyncSession,
    codigo: str,
    *,
    origem: str | None = None,
    capitulo: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[ManualDocumento]]:
    """
    Documentos do manual `codigo` (edição vigente), ordenados por `sort_order`
    (RN-05) — a ordem que o mecânico via no DVD.

    `capitulo=None` devolve todos os capítulos do manual. `origem` desambigua
    quando o mesmo `codigo` existe nos dois discos — ver `_manual_da_edicao_vigente`.
    """
    manual = await _manual_da_edicao_vigente(db, codigo, origem=origem)

    limit = max(1, min(limit, LIMITE_MAXIMO_LISTAGEM))
    offset = max(0, offset)

    filtros = [ManualDocumento.manual_id == manual.id]
    if capitulo is not None:
        filtros.append(ManualDocumento.capitulo == capitulo)

    total = (
        await db.execute(select(func.count(ManualDocumento.id)).where(*filtros))
    ).scalar_one()
    documentos = (
        (
            await db.execute(
                select(ManualDocumento)
                .where(*filtros)
                .order_by(ManualDocumento.sort_order, ManualDocumento.titulo)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return int(total), list(documentos)


async def buscar_no_catalogo(
    db: AsyncSession, termo: str, *, limit: int = 20, offset: int = 0
) -> tuple[int, list[tuple[ManualDocumento, Manual]]]:
    """
    Busca por NOME/CAMINHO na edição vigente, usada pelo explorador do
    acervo: o FTS de `search.buscar` indexa texto de PÁGINA, não nomes, então
    "AMM CHAPTER_21" ou "sangria.pdf" não voltam nada de lá.

    `ilike` casa substring sem diferenciar caixa nos dois dialetos do projeto
    (SQLite e Postgres) — sem sintaxe de operador para o usuário aprender, o
    mesmo motivo por trás de `search.sanitizar_query` tokenizar em vez de
    expor MATCH cru.
    """
    vigente = await obter_edicao_vigente(db)
    if vigente is None:
        return 0, []

    limit = max(1, min(limit, LIMITE_MAXIMO_LISTAGEM))
    offset = max(0, offset)

    # escape_like neutraliza `%`/`_` digitados pelo usuário (SEC-07) — sem
    # isso, buscar "CHAPTER_21" também casaria "CHAPTERX21", já que `_` é
    # curinga de LIKE/ILIKE e o domínio é dominado por nomes com `_`.
    padrao = f"%{escape_like(termo)}%"
    filtros = (
        Manual.edicao_id == vigente.id,
        or_(
            ManualDocumento.titulo.ilike(padrao, escape="\\"),
            ManualDocumento.capitulo.ilike(padrao, escape="\\"),
            ManualDocumento.file_key.ilike(padrao, escape="\\"),
            Manual.codigo.ilike(padrao, escape="\\"),
            Manual.descricao_pt.ilike(padrao, escape="\\"),
        ),
    )

    total = (
        await db.execute(
            select(func.count(ManualDocumento.id))
            .select_from(ManualDocumento)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(*filtros)
        )
    ).scalar_one()

    linhas = (
        await db.execute(
            select(ManualDocumento, Manual)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(*filtros)
            .order_by(Manual.codigo, ManualDocumento.sort_order, ManualDocumento.titulo)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return int(total), [(doc, manual) for doc, manual in linhas]


# --------------------------------------------------------------------------
# Sincronização do catálogo (chamada pelo indexador offline)
# --------------------------------------------------------------------------


async def sincronizar_catalogo(
    db: AsyncSession, edicao: ManualEdicao, manuais: list[ManualPayload]
) -> dict[str, int]:
    """
    Reconcilia o catálogo leve de `edicao` com o que o indexador encontrou.

    Idempotente por construção: as chaves são determinísticas
    (`uq_manuais_edicao_origem_codigo` e o UUID v5 do documento), então rodar
    duas vezes sobre o mesmo acervo produz exatamente o mesmo estado.

    Reconcilia só os manuais presentes em `manuais` — indexar uma amostra ou um
    manual isolado não pode apagar o catálogo dos outros da mesma edição.
    Dentro de cada manual processado, documentos que sumiram do disco são
    removidos (RN-09); a auditoria sobrevive porque `publicacoes_acessos` usa
    SET NULL + snapshot do título (B4).
    """
    contagem = {"manuais": 0, "inseridos": 0, "atualizados": 0, "removidos": 0}

    for payload in manuais:
        manual = (
            await db.execute(
                select(Manual).where(
                    Manual.edicao_id == edicao.id,
                    Manual.origem == payload.origem,
                    Manual.codigo == payload.codigo,
                )
            )
        ).scalar_one_or_none()

        if manual is None:
            manual = Manual(
                edicao_id=edicao.id,
                codigo=payload.codigo,
                origem=payload.origem,
                descricao_pt=payload.descricao_pt,
                categoria=payload.categoria,
                path=payload.path,
            )
            db.add(manual)
            await db.flush()
        else:
            manual.descricao_pt = payload.descricao_pt
            manual.categoria = payload.categoria
            manual.path = payload.path
        contagem["manuais"] += 1

        existentes = {
            doc.id: doc
            for doc in (
                await db.execute(
                    select(ManualDocumento).where(ManualDocumento.manual_id == manual.id)
                )
            ).scalars()
        }

        vistos: set[uuid.UUID] = set()
        for doc_payload in payload.documentos:
            vistos.add(doc_payload.id)
            documento = existentes.get(doc_payload.id)
            if documento is None:
                db.add(
                    ManualDocumento(
                        id=doc_payload.id,
                        manual_id=manual.id,
                        capitulo=doc_payload.capitulo,
                        ata_codigo=doc_payload.ata_codigo,
                        file_key=doc_payload.file_key,
                        titulo=doc_payload.titulo,
                        sort_order=doc_payload.sort_order,
                        paginas=doc_payload.paginas,
                        has_text=doc_payload.has_text,
                        revision_status=doc_payload.revision_status,
                        hash_sha256=doc_payload.hash_sha256,
                    )
                )
                contagem["inseridos"] += 1
            else:
                documento.capitulo = doc_payload.capitulo
                documento.ata_codigo = doc_payload.ata_codigo
                documento.file_key = doc_payload.file_key
                documento.titulo = doc_payload.titulo
                documento.sort_order = doc_payload.sort_order
                documento.paginas = doc_payload.paginas
                documento.has_text = doc_payload.has_text
                documento.revision_status = doc_payload.revision_status
                documento.hash_sha256 = doc_payload.hash_sha256
                contagem["atualizados"] += 1

        obsoletos = [doc_id for doc_id in existentes if doc_id not in vistos]
        if obsoletos:
            await db.execute(
                delete(ManualDocumento).where(ManualDocumento.id.in_(obsoletos))
            )
            contagem["removidos"] += len(obsoletos)

        await db.flush()

    return contagem


async def sincronizar_fim_map(
    db: AsyncSession, pares: list[tuple[str, str]], edicao: ManualEdicao
) -> dict[str, int]:
    """
    Reconstrói a fatia de `manuais_fim_map` da edição `edicao`, a partir de
    [(mensagem, procedimento)].

    `documento_id` é resolvido por `file_key` dentro da edição: o nome do PDF de
    um procedimento é convenção medida (`catalog.nome_pdf_de_procedimento`).
    Procedimento sem PDF grava `documento_id = NULL` em vez de ser descartado —
    a mensagem continua resolvendo para um código que o mecânico procura no
    manual em papel (4 dos 253 casos do piloto).

    Escopado por `edicao_id` (BUG-03): o `DELETE` abaixo só atinge as linhas
    desta edição, então indexar uma edição nova (ainda `AGUARDANDO_ATIVACAO`)
    nunca mais reescreve o mapa da edição VIGENTE.
    """
    from app.modules.publicacoes.catalog import nome_pdf_de_procedimento

    documentos = (
        await db.execute(
            select(ManualDocumento.id, ManualDocumento.file_key)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id == edicao.id)
            # RISCO-02: sem ORDER BY, "a última ocorrência vence" no dict
            # comprehension abaixo dependia da ordem que o banco devolvesse
            # as linhas — não garantida nem estável entre execuções. Ordenar
            # por manual/file_key torna uma colisão real ao menos
            # determinística entre reindexações.
            .order_by(Manual.codigo, ManualDocumento.file_key)
        )
    ).all()
    # Chaveado pelo BASENAME em maiúsculas: o `file_key` carrega o caminho
    # relativo (com capítulo, quando existe) e o procedimento só conhece o
    # nome do arquivo. `file_key` é sempre POSIX — `pdf_path.as_posix()` em
    # `indexar.py` — então `rsplit("/", ...)` vale em qualquer plataforma.
    por_nome: dict[str, uuid.UUID] = {}
    for doc_id, file_key in documentos:
        chave = file_key.rsplit("/", 1)[-1].upper()
        if chave in por_nome:
            logger.warning(
                "Dois documentos da edição %r com o mesmo nome de arquivo "
                "(%r) — mapa do FIM usará %s, não %s.",
                edicao.rotulo, chave, doc_id, por_nome[chave],
            )
        por_nome[chave] = doc_id

    await db.execute(delete(ManualFimMap).where(ManualFimMap.edicao_id == edicao.id))

    resolvidos = 0
    for mensagem, procedimento in pares:
        documento_id = por_nome.get(nome_pdf_de_procedimento(procedimento))
        if documento_id is not None:
            resolvidos += 1
        db.add(
            ManualFimMap(
                edicao_id=edicao.id,
                mensagem=mensagem,
                procedimento=procedimento,
                documento_id=documento_id,
            )
        )
    await db.flush()

    return {"total": len(pares), "com_documento": resolvidos}


# --------------------------------------------------------------------------
# Leitura (requisição)
# --------------------------------------------------------------------------


async def obter_documento(
    db: AsyncSession, documento_id: uuid.UUID
) -> ManualDocumento | None:
    """
    Documento pelo id, com o manual e a edição já carregados.

    ⚠️ `documento_id` tem de chegar aqui como `uuid.UUID`, nunca como a string
    vinda do `catalog.db` — o SQLite grava o tipo `Uuid` em hex sem hífens e a
    comparação crua falha em silêncio, devolvendo None (§2.2.1, achado B5).
    """
    return (
        await db.execute(
            select(ManualDocumento)
            .options(selectinload(ManualDocumento.manual).selectinload(Manual.edicao))
            .where(ManualDocumento.id == documento_id)
        )
    ).scalar_one_or_none()


async def buscar_por_mensagem_fim(
    db: AsyncSession, termo: str, *, limit: int = 20
) -> list[tuple[ManualFimMap, ManualDocumento | None]]:
    """
    Mensagens de falha que casam com `termo`, com o documento resolvido.

    Casamento por prefixo: quem digita `ADC` quer as mensagens `ADC 001`,
    `ADC 002`… O `escape_like` neutraliza `%`/`_` digitados pelo usuário, que
    de outro modo virariam curinga (SEC-07).

    Escopado pela edição VIGENTE (BUG-03): sem isso, uma edição indexada mas
    ainda não ativada poderia responder no lugar da vigente.
    """
    vigente = await obter_edicao_vigente(db)
    if vigente is None:
        return []

    limit = max(1, min(limit, LIMITE_MAXIMO_LISTAGEM))
    padrao = f"{escape_like(termo.strip().upper())}%"

    linhas = (
        await db.execute(
            select(ManualFimMap, ManualDocumento)
            .outerjoin(
                ManualDocumento, ManualDocumento.id == ManualFimMap.documento_id
            )
            .where(
                ManualFimMap.edicao_id == vigente.id,
                func.upper(ManualFimMap.mensagem).like(padrao, escape="\\"),
            )
            .order_by(ManualFimMap.mensagem)
            .limit(limit)
        )
    ).all()
    return [(mapa, documento) for mapa, documento in linhas]


async def listar_fim_por_ata(
    db: AsyncSession, ata_codigo: str, *, limit: int = 20
) -> list[tuple[ManualFimMap, ManualDocumento | None]]:
    """
    Procedimentos do FIM cujo código começa por `<ata_codigo>-` (M3 tarefa 1).

    O código ATA é sempre os dois primeiros dígitos do procedimento
    (`34-15-00-810-801-A` → ATA 34) — convenção do próprio FIM, não uma coluna
    dedicada em `manuais_fim_map`. Alimenta o bloco "Procedimentos FIM do ATA
    XX" no detalhe da pane, filtrado pelo `sistema_ata` da pane aberta.

    Escopado pela edição VIGENTE (BUG-03) — mesmo motivo de
    `buscar_por_mensagem_fim`.
    """
    vigente = await obter_edicao_vigente(db)
    if vigente is None:
        return []

    limit = max(1, min(limit, LIMITE_MAXIMO_LISTAGEM))
    padrao = f"{escape_like(ata_codigo)}-%"
    linhas = (
        await db.execute(
            select(ManualFimMap, ManualDocumento)
            .outerjoin(
                ManualDocumento, ManualDocumento.id == ManualFimMap.documento_id
            )
            .where(
                ManualFimMap.edicao_id == vigente.id,
                ManualFimMap.procedimento.like(padrao, escape="\\"),
            )
            .order_by(ManualFimMap.procedimento)
            .limit(limit)
        )
    ).all()
    return [(mapa, documento) for mapa, documento in linhas]


async def medir_duplicacao_entre_edicoes(db: AsyncSession) -> dict[str, object]:
    """
    Quantos documentos a edição ANTERIOR compartilha, por `hash_sha256`, com a
    edição VIGENTE (M4 tarefa 5).

    Não deduplica fisicamente nada — hoje as duas edições apontam para a
    mesma árvore em disco (`var/publicacoes/acervo/`), então não há cópia
    física a eliminar ainda. O valor desta medição é dimensionar, ANTES de
    qualquer trabalho de reestruturação de disco, quanto espaço um esquema de
    dedup física (hardlink, ou uma segunda cópia por edição) economizaria —
    é exatamente o dado que falta para o gate do M4 ("disco da VPS < 60% após
    duas edições retidas").
    """
    vigente = await obter_edicao_vigente(db)
    anterior = (
        await db.execute(
            select(ManualEdicao)
            .where(ManualEdicao.status == StatusEdicao.ANTERIOR)
            .order_by(ManualEdicao.data_publicacao.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if vigente is None or anterior is None:
        return {
            "vigente": vigente.rotulo if vigente else None,
            "anterior": anterior.rotulo if anterior else None,
            "documentos_vigente": 0,
            "documentos_anterior": 0,
            "duplicados_por_hash": 0,
            "bytes_potencialmente_economizaveis": None,
        }

    # MELHORIA-03: interseção de hashes calculada no banco (`IN (subquery)`),
    # não materializando todos os hashes de uma edição em memória Python. A
    # versão anterior também fazia um `GROUP BY`+`count()` cuja contagem
    # nunca era lida (só o pertencimento da chave importava) — trabalho puro
    # de banco descartado.
    hashes_vigente_subq = (
        select(ManualDocumento.hash_sha256)
        .join(Manual, Manual.id == ManualDocumento.manual_id)
        .where(Manual.edicao_id == vigente.id, ManualDocumento.hash_sha256.is_not(None))
    )

    total_vigente, total_anterior = (
        await db.execute(
            select(
                func.count(ManualDocumento.id).filter(Manual.edicao_id == vigente.id),
                func.count(ManualDocumento.id).filter(Manual.edicao_id == anterior.id),
            )
            .select_from(ManualDocumento)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id.in_((vigente.id, anterior.id)))
        )
    ).one()

    duplicados = (
        await db.execute(
            select(func.count(ManualDocumento.id))
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(
                Manual.edicao_id == anterior.id,
                ManualDocumento.hash_sha256.is_not(None),
                ManualDocumento.hash_sha256.in_(hashes_vigente_subq),
            )
        )
    ).scalar_one()

    return {
        "vigente": vigente.rotulo,
        "anterior": anterior.rotulo,
        "documentos_vigente": total_vigente,
        "documentos_anterior": total_anterior,
        "duplicados_por_hash": duplicados,
        # bytes reais exigiriam o tamanho do arquivo, não guardado hoje —
        # deixado explícito como None em vez de estimado, para não sugerir
        # uma precisão que os dados atuais não sustentam.
        "bytes_potencialmente_economizaveis": None,
    }


async def status_do_catalogo(db: AsyncSession) -> dict[str, object]:
    """
    Contagens do catálogo leve para `GET /publicacoes/api/status`.

    `documentos_sem_texto` é o número que dimensiona a necessidade de OCR (M4
    tarefa 8) — por isso é reportado desde o M1, quando ainda é barato medir.
    """
    edicao = await obter_edicao_vigente(db)
    if edicao is None:
        return {
            "edicao": None,
            "manuais": 0,
            "documentos": 0,
            "documentos_sem_texto": 0,
            "mensagens_fim": 0,
        }

    total_manuais = (
        await db.execute(
            select(func.count(Manual.id)).where(Manual.edicao_id == edicao.id)
        )
    ).scalar_one()
    total_docs, sem_texto = (
        await db.execute(
            select(
                func.count(ManualDocumento.id),
                func.sum(case((ManualDocumento.has_text.is_(False), 1), else_=0)),
            )
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id == edicao.id)
        )
    ).one()
    total_fim = (
        await db.execute(
            select(func.count(ManualFimMap.id)).where(
                ManualFimMap.edicao_id == edicao.id
            )
        )
    ).scalar_one()

    return {
        "edicao": edicao.rotulo,
        "manuais": total_manuais,
        "documentos": total_docs,
        "documentos_sem_texto": int(sem_texto or 0),
        "mensagens_fim": total_fim,
    }


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------


async def registrar_acesso(
    db: AsyncSession,
    *,
    usuario_id: uuid.UUID,
    documento: ManualDocumento,
    pagina: int | None = None,
) -> None:
    """
    Registra a abertura de um documento (RBAC.md §4).

    Grava o título como snapshot: o registro precisa continuar legível depois
    que o documento sair do acervo (B4). `documento.manual.edicao_id` exige que
    o documento tenha vindo de `obter_documento`, que já carrega a cadeia.
    """
    db.add(
        PublicacaoAcesso(
            usuario_id=usuario_id,
            documento_id=documento.id,
            documento_titulo=documento.titulo[:300],
            edicao_id=documento.manual.edicao_id,
            pagina=pagina,
        )
    )
    await db.flush()


# --------------------------------------------------------------------------
# Favoritos (transversal aos dois acervos, M3)
# --------------------------------------------------------------------------


async def listar_favoritos(
    db: AsyncSession, usuario_id: uuid.UUID
) -> list[PublicacaoFavorito]:
    return list(
        (
            await db.execute(
                select(PublicacaoFavorito)
                .where(PublicacaoFavorito.usuario_id == usuario_id)
                .order_by(PublicacaoFavorito.created_at.desc())
            )
        ).scalars()
    )


async def _favoritar(
    db: AsyncSession, favorito: PublicacaoFavorito, *filtros: object
) -> PublicacaoFavorito:
    """
    Insere `favorito`, devolvendo o já existente em vez de propagar
    `IntegrityError` (RISCO-01).

    Sem pre-check separado de "já existe": um SELECT seguido de INSERT deixa
    a mesma janela TOCTOU que `calendario.service.create_event_type` já
    fechou (`achados_calendario.md`, RISCO-03) — duas requisições quase
    simultâneas (duplo toque na estrela de favorito, gesto comum em UI de
    toque) passariam as duas pela checagem. A `UniqueConstraint` de
    `PublicacaoFavorito` é a única fonte de verdade; o SAVEPOINT cobre o
    caminho comum (favoritar duas vezes em série) e a corrida real com o
    mesmo código.
    """
    try:
        async with db.begin_nested():
            db.add(favorito)
            await db.flush()
    except IntegrityError as exc:
        logger.info("Favorito já existente (%s); devolvendo o existente.", exc.orig)
        return (await db.execute(select(PublicacaoFavorito).where(*filtros))).scalar_one()
    return favorito


async def favoritar_documento(
    db: AsyncSession, usuario_id: uuid.UUID, documento_id: uuid.UUID
) -> PublicacaoFavorito:
    """
    Idempotente: favoritar duas vezes o mesmo documento devolve o favorito já
    existente em vez de violar a `UniqueConstraint` (achado B1) — à prova de
    corrida via SAVEPOINT (RISCO-01), não só de repetição em série.
    """
    if await obter_documento(db, documento_id) is None:
        raise EntidadeNaoEncontradaError("Documento não encontrado.")

    favorito = PublicacaoFavorito(usuario_id=usuario_id, documento_id=documento_id)
    return await _favoritar(
        db,
        favorito,
        PublicacaoFavorito.usuario_id == usuario_id,
        PublicacaoFavorito.documento_id == documento_id,
    )


async def favoritar_avulsa(
    db: AsyncSession, usuario_id: uuid.UUID, avulsa_id: uuid.UUID
) -> PublicacaoFavorito:
    """Idempotente e à prova de corrida — mesmo contrato de `favoritar_documento`."""
    from app.modules.publicacoes import avulsas as avulsas_module

    await avulsas_module.obter_avulsa(db, avulsa_id)  # 404 se não existir/inativa

    favorito = PublicacaoFavorito(usuario_id=usuario_id, avulsa_id=avulsa_id)
    return await _favoritar(
        db,
        favorito,
        PublicacaoFavorito.usuario_id == usuario_id,
        PublicacaoFavorito.avulsa_id == avulsa_id,
    )


async def remover_favorito(db: AsyncSession, usuario_id: uuid.UUID, favorito_id: uuid.UUID) -> None:
    favorito = (
        await db.execute(
            select(PublicacaoFavorito).where(
                PublicacaoFavorito.id == favorito_id,
                PublicacaoFavorito.usuario_id == usuario_id,
            )
        )
    ).scalar_one_or_none()
    if favorito is None:
        raise EntidadeNaoEncontradaError("Favorito não encontrado.")

    await db.delete(favorito)
    await db.flush()


# --------------------------------------------------------------------------
# Gestão e Auto-healing de Upload Jobs (M4.Web)
# --------------------------------------------------------------------------


async def limpar_jobs_upload_estagnados(db: AsyncSession, timeout_minutos: int = 60) -> int:
    """
    Busca jobs em ENVIANDO ou PROCESSANDO estagnados ou órfãos e marca como FALHOU,
    desbloqueando o single-flight lock (`uq_publicacoes_upload_jobs_ativo_unico`).

    - Jobs em PROCESSANDO sem processo ativo (PID inativo) são marcados como FALHOU.
    - Jobs em ENVIANDO com inatividade superior a `timeout_minutos` são marcados como FALHOU.
    """
    from datetime import datetime, timezone, timedelta
    from app.modules.publicacoes.models import PublicacoesUploadJob
    from app.shared.core.enums import StatusUploadJob
    from app.shared.core.storage import get_storage_service

    agora = datetime.now(timezone.utc)
    limite_inatividade = agora - timedelta(minutes=timeout_minutos)

    jobs = (
        await db.execute(
            select(PublicacoesUploadJob).where(
                PublicacoesUploadJob.status.in_([StatusUploadJob.ENVIANDO, StatusUploadJob.PROCESSANDO])
            )
        )
    ).scalars().all()

    limpados = 0
    storage = None

    for job in jobs:
        deve_limpar = False
        motivo_erro = ""
        etapa_desc = ""

        if job.status == StatusUploadJob.PROCESSANDO:
            processo_ativo = False
            if job.processo_pid:
                from app.shared.core.processo import processo_esta_ativo
                processo_ativo = processo_esta_ativo(job.processo_pid)

            if not processo_ativo:
                deve_limpar = True
                etapa_desc = "Processo interrompido"
                motivo_erro = "Processo de tratamento do acervo foi interrompido (PID inativo). Reenvie a edição."

        elif job.status == StatusUploadJob.ENVIANDO:
            data_ref = job.updated_at or job.created_at
            if data_ref:
                if data_ref.tzinfo is None:
                    data_ref = data_ref.replace(tzinfo=timezone.utc)
                if data_ref < limite_inatividade:
                    deve_limpar = True
                    etapa_desc = "Upload expirado"
                    motivo_erro = f"Envio de edição anterior abandonado ou expirado por inatividade (> {timeout_minutos} min). Reenvie o arquivo."

        if deve_limpar:
            job.status = StatusUploadJob.FALHOU
            job.etapa = etapa_desc
            job.erro = motivo_erro
            limpados += 1

            if job.upload_id_r2 and job.file_key:
                try:
                    if storage is None:
                        storage = get_storage_service()
                    await storage.abortar_multipart(job.file_key, job.upload_id_r2)
                except Exception as exc_st:
                    logger.warning("Falha ao abortar multipart para job estagnado %s: %s", job.id, exc_st)

    if limpados > 0:
        await db.flush()
        logger.warning("[Uploads] Auto-healing: %d job(s) estagnado(s) marcado(s) como FALHOU.", limpados)

    return limpados


class DisparoWorkerError(Exception):
    """Falha ao iniciar o subprocesso worker de processamento (publicar.py)."""


async def disparar_worker_processamento(db: AsyncSession, job: "PublicacoesUploadJob") -> None:
    """
    Transiciona o job para PROCESSANDO e dispara, isolado em subprocesso
    (ADR-004 — nunca dentro do worker web), o `publicar.py --de-upload` que
    faz o trabalho pesado (download, validação do ZIP, indexação FTS5).

    Compartilhado pelos dois modos de envio: disparo imediato ao concluir o
    upload (modo IMEDIATO) e o loop noturno que processa jobs AGENDADO
    (`app/bootstrap/tasks.py:processamento_noturno_task`).
    """
    import sys
    from app.shared.core.enums import StatusUploadJob

    job.status = StatusUploadJob.PROCESSANDO
    job.etapa = "Upload concluído. Disparando processamento do acervo..."
    job.progresso_pct = 5
    await db.commit()

    cmd = [
        sys.executable,
        "-m",
        "scripts.publicacoes.publicar",
        "--edicao",
        job.rotulo,
        "--de-upload",
        job.file_key,
        "--job-id",
        str(job.id),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        job.processo_pid = proc.pid
        await db.commit()
    except Exception as exc:
        job.status = StatusUploadJob.FALHOU
        job.erro = f"Falha ao iniciar o worker de processamento: {exc}"
        await db.commit()
        raise DisparoWorkerError(str(exc)) from exc

