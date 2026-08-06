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

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.publicacoes.models import (
    Manual,
    ManualDocumento,
    ManualEdicao,
    ManualFimMap,
    PublicacaoAcesso,
    PublicacaoFavorito,
)
from app.shared.core.enums import RevisionStatus, StatusEdicao

logger = logging.getLogger(__name__)

# Teto defensivo de listagem. Existe além dos `le=` do FastAPI porque o service
# também é chamado por scripts, que não passam por Query (precedente:
# inspecoes/service.py).
LIMITE_MAXIMO_LISTAGEM = 100


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
    documentos: list[DocumentoPayload] = field(default_factory=list)


# --------------------------------------------------------------------------
# Edições
# --------------------------------------------------------------------------


async def obter_ou_criar_edicao(
    db: AsyncSession, rotulo: str, *, status: StatusEdicao = StatusEdicao.VIGENTE
) -> ManualEdicao:
    """
    Edição de rótulo `rotulo`, criando-a se ainda não existir.

    O rótulo é o que entra no UUID v5 dos documentos (§2.2), então reindexar a
    mesma edição precisa encontrar a MESMA linha — criar uma segunda edição com
    outro `id` não quebraria os UUIDs (eles derivam do rótulo, não do id), mas
    duplicaria o catálogo inteiro. Daí o get-or-create em vez de insert.
    """
    edicao = (
        await db.execute(select(ManualEdicao).where(ManualEdicao.rotulo == rotulo))
    ).scalar_one_or_none()
    if edicao is not None:
        return edicao

    edicao = ManualEdicao(rotulo=rotulo, status=status)
    db.add(edicao)
    await db.flush()
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
# Sincronização do catálogo (chamada pelo indexador offline)
# --------------------------------------------------------------------------


async def sincronizar_catalogo(
    db: AsyncSession, edicao: ManualEdicao, manuais: list[ManualPayload]
) -> dict[str, int]:
    """
    Reconcilia o catálogo leve de `edicao` com o que o indexador encontrou.

    Idempotente por construção: as chaves são determinísticas
    (`uq_manuais_edicao_codigo` e o UUID v5 do documento), então rodar duas
    vezes sobre o mesmo acervo produz exatamente o mesmo estado.

    Reconcilia só os manuais presentes em `manuais` — indexar `docs/fim/`
    sozinho não pode apagar o catálogo dos outros 33 manuais da mesma edição.
    Dentro de cada manual processado, documentos que sumiram do disco são
    removidos (RN-09); a auditoria sobrevive porque `publicacoes_acessos` usa
    SET NULL + snapshot do título (B4).
    """
    contagem = {"manuais": 0, "inseridos": 0, "atualizados": 0, "removidos": 0}

    for payload in manuais:
        manual = (
            await db.execute(
                select(Manual).where(
                    Manual.edicao_id == edicao.id, Manual.codigo == payload.codigo
                )
            )
        ).scalar_one_or_none()

        if manual is None:
            manual = Manual(
                edicao_id=edicao.id,
                codigo=payload.codigo,
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
    Reconstrói `manuais_fim_map` a partir de [(mensagem, procedimento)].

    `documento_id` é resolvido por `file_key` dentro da edição: o nome do PDF de
    um procedimento é convenção medida (`catalog.nome_pdf_de_procedimento`).
    Procedimento sem PDF grava `documento_id = NULL` em vez de ser descartado —
    a mensagem continua resolvendo para um código que o mecânico procura no
    manual em papel (4 dos 253 casos do piloto).
    """
    from app.modules.publicacoes.catalog import nome_pdf_de_procedimento

    documentos = (
        await db.execute(
            select(ManualDocumento.id, ManualDocumento.file_key)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id == edicao.id)
        )
    ).all()
    # Chaveado pelo BASENAME em maiúsculas: o `file_key` carrega o caminho
    # relativo (com capítulo, quando existe) e o procedimento só conhece o nome
    # do arquivo.
    por_nome = {
        file_key.rsplit("/", 1)[-1].upper(): doc_id for doc_id, file_key in documentos
    }

    await db.execute(delete(ManualFimMap))

    resolvidos = 0
    for mensagem, procedimento in pares:
        documento_id = por_nome.get(nome_pdf_de_procedimento(procedimento))
        if documento_id is not None:
            resolvidos += 1
        db.add(
            ManualFimMap(
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
    """
    from app.shared.core.db_utils import escape_like

    limit = min(limit, LIMITE_MAXIMO_LISTAGEM)
    padrao = f"{escape_like(termo.strip().upper())}%"

    linhas = (
        await db.execute(
            select(ManualFimMap, ManualDocumento)
            .outerjoin(
                ManualDocumento, ManualDocumento.id == ManualFimMap.documento_id
            )
            .where(func.upper(ManualFimMap.mensagem).like(padrao, escape="\\"))
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
    """
    from app.shared.core.db_utils import escape_like

    limit = min(limit, LIMITE_MAXIMO_LISTAGEM)
    padrao = f"{escape_like(ata_codigo)}-%"
    linhas = (
        await db.execute(
            select(ManualFimMap, ManualDocumento)
            .outerjoin(
                ManualDocumento, ManualDocumento.id == ManualFimMap.documento_id
            )
            .where(ManualFimMap.procedimento.like(padrao, escape="\\"))
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

    hashes_vigente = dict(
        (await db.execute(
            select(ManualDocumento.hash_sha256, func.count(ManualDocumento.id))
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id == vigente.id, ManualDocumento.hash_sha256.is_not(None))
            .group_by(ManualDocumento.hash_sha256)
        )).all()
    )
    total_vigente, total_anterior = (
        await db.execute(
            select(
                func.count(ManualDocumento.id).filter(Manual.edicao_id == vigente.id),
                func.count(ManualDocumento.id).filter(Manual.edicao_id == anterior.id),
            )
            .select_from(ManualDocumento)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
        )
    ).one()

    hashes_anteriores = (
        await db.execute(
            select(ManualDocumento.hash_sha256)
            .join(Manual, Manual.id == ManualDocumento.manual_id)
            .where(Manual.edicao_id == anterior.id, ManualDocumento.hash_sha256.is_not(None))
        )
    ).scalars().all()

    duplicados = sum(1 for h in hashes_anteriores if h in hashes_vigente)

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
    total_fim = (await db.execute(select(func.count(ManualFimMap.id)))).scalar_one()

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


async def favoritar_documento(
    db: AsyncSession, usuario_id: uuid.UUID, documento_id: uuid.UUID
) -> PublicacaoFavorito:
    """
    Idempotente: favoritar duas vezes o mesmo documento devolve o favorito já
    existente em vez de violar a `UniqueConstraint` (achado B1) — poupa o
    cliente de precisar checar antes de tentar.
    """
    from app.shared.core import exceptions as domain_exc

    if await obter_documento(db, documento_id) is None:
        raise domain_exc.EntidadeNaoEncontradaError("Documento não encontrado.")

    existente = (
        await db.execute(
            select(PublicacaoFavorito).where(
                PublicacaoFavorito.usuario_id == usuario_id,
                PublicacaoFavorito.documento_id == documento_id,
            )
        )
    ).scalar_one_or_none()
    if existente is not None:
        return existente

    favorito = PublicacaoFavorito(usuario_id=usuario_id, documento_id=documento_id)
    db.add(favorito)
    await db.flush()
    return favorito


async def favoritar_avulsa(
    db: AsyncSession, usuario_id: uuid.UUID, avulsa_id: uuid.UUID
) -> PublicacaoFavorito:
    from app.modules.publicacoes import avulsas as avulsas_module

    await avulsas_module.obter_avulsa(db, avulsa_id)  # 404 se não existir/inativa

    existente = (
        await db.execute(
            select(PublicacaoFavorito).where(
                PublicacaoFavorito.usuario_id == usuario_id,
                PublicacaoFavorito.avulsa_id == avulsa_id,
            )
        )
    ).scalar_one_or_none()
    if existente is not None:
        return existente

    favorito = PublicacaoFavorito(usuario_id=usuario_id, avulsa_id=avulsa_id)
    db.add(favorito)
    await db.flush()
    return favorito


async def remover_favorito(db: AsyncSession, usuario_id: uuid.UUID, favorito_id: uuid.UUID) -> None:
    from app.shared.core import exceptions as domain_exc

    favorito = (
        await db.execute(
            select(PublicacaoFavorito).where(
                PublicacaoFavorito.id == favorito_id,
                PublicacaoFavorito.usuario_id == usuario_id,
            )
        )
    ).scalar_one_or_none()
    if favorito is None:
        raise domain_exc.EntidadeNaoEncontradaError("Favorito não encontrado.")

    await db.delete(favorito)
    await db.flush()
