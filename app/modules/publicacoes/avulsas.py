"""
app/modules/publicacoes/avulsas.py
Regras de negócio do acervo B — BO/BS/NPO/BT.

Independente do M1: fala só com o banco principal, nunca com `catalog.db`
nem `pypdfium2`. `service.py` cobre o acervo A (manuais) e o transversal
(auditoria); este arquivo cobre cadastro, vigência, substituição e busca por
metadados das publicações avulsas.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.publicacoes import schemas
from app.modules.publicacoes.models import (
    PublicacaoAvulsa,
    PublicacaoAvulsaAeronave,
    PublicacaoAvulsaAnexo,
)
from app.shared.core import exceptions as domain_exc
from app.shared.core.db_utils import escape_like
from app.shared.core.enums import StatusPublicacaoAvulsa, TipoPublicacao

logger = logging.getLogger(__name__)

# Mesmo precedente de `inspecoes/service.py:36` — teto defensivo aplicado no
# service, não só no `Query` do router, porque scripts também podem chamar
# estas funções sem passar pelo FastAPI.
LIMITE_MAXIMO_LISTAGEM = 100


def construir_snippet(texto: str, termo: str, *, janela: int = 60) -> str:
    """
    Trecho de `texto` ao redor da primeira ocorrência de `termo`, com o termo
    delimitado por sentinelas `\\x02`/`\\x03` — mesma receita do `catalog.db`
    (`search.py`), nunca `<mark>` cru.

    `ementa`/`titulo` são entrada de usuário e vão direto para a resposta da
    API de busca — é o mesmo risco que o snippet do acervo A tem (achado B8),
    só que aqui o texto nem passa por FTS: a busca é `ILIKE` no banco
    principal. O cliente escapa a resposta inteira e só então troca os
    sentinelas por `<mark>` (mesma função `snippetSeguro` de `publicacoes.js`,
    reaproveitada para os dois acervos).
    """
    match = re.search(re.escape(termo), texto, re.IGNORECASE)
    if match is None:
        return texto[:120]

    inicio = max(0, match.start() - janela)
    fim = min(len(texto), match.end() + janela)
    prefixo = "…" if inicio > 0 else ""
    sufixo = "…" if fim < len(texto) else ""
    trecho = (
        texto[inicio:match.start()]
        + "\x02" + texto[match.start():match.end()] + "\x03"
        + texto[match.end():fim]
    )
    return f"{prefixo}{trecho}{sufixo}"


async def criar_avulsa(
    db: AsyncSession, dados: schemas.PublicacaoAvulsaCreate, *, usuario_id: uuid.UUID
) -> PublicacaoAvulsa:
    """
    Cadastra uma publicação avulsa.

    `UniqueConstraint(tipo, numero, ano)` é a defesa contra duplicata; a
    violação vira `ConflitoNegocioError` via `IntegrityError` — savepoint em
    vez de checar existência antes (mesmo padrão de
    `vencimentos/service.py`, evita TOCTOU entre o SELECT e o INSERT).
    """
    from sqlalchemy.exc import IntegrityError

    avulsa = PublicacaoAvulsa(
        tipo=dados.tipo,
        numero=dados.numero,
        ano=dados.ano,
        data_emissao=dados.data_emissao,
        data_recebimento=dados.data_recebimento,
        emissor=dados.emissor,
        titulo=dados.titulo,
        ementa=dados.ementa,
        sistema_ata_id=dados.sistema_ata_id,
        cadastrada_por_id=usuario_id,
    )
    db.add(avulsa)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise domain_exc.ConflitoNegocioError(
            f"Já existe {dados.tipo.value} {dados.numero!r}/{dados.ano} cadastrado."
        ) from exc

    for aeronave_id in dados.aplicabilidade:
        db.add(
            PublicacaoAvulsaAeronave(avulsa_id=avulsa.id, aeronave_id=aeronave_id)
        )
    await db.flush()

    # Recarrega com `anexos` já carregado (selectinload) — o objeto recém-
    # criado nunca tocou essa relationship, e o serializer do schema
    # (`from_attributes=True`) dispararia um lazy-load fora do contexto
    # assíncrono do SQLAlchemy (`MissingGreenlet`) se devolvido cru.
    return await obter_avulsa(db, avulsa.id)


async def obter_avulsa(
    db: AsyncSession, avulsa_id: uuid.UUID, *, incluir_inativas: bool = False
) -> PublicacaoAvulsa:
    """Publicação por id, com anexos carregados. 404 se não existir (ou inativa)."""
    query = select(PublicacaoAvulsa).options(
        selectinload(PublicacaoAvulsa.anexos)
    ).where(PublicacaoAvulsa.id == avulsa_id)
    if not incluir_inativas:
        query = query.where(PublicacaoAvulsa.ativo.is_(True))

    avulsa = (await db.execute(query)).scalar_one_or_none()
    if avulsa is None:
        raise domain_exc.EntidadeNaoEncontradaError("Publicação não encontrada.")
    return avulsa


async def atualizar_avulsa(
    db: AsyncSession, avulsa_id: uuid.UUID, dados: schemas.PublicacaoAvulsaUpdate
) -> PublicacaoAvulsa:
    """
    Correção de metadados e/ou transição de vigência.

    Substituir (`status=SUBSTITUIDO`) exige `substituida_por_id` — sem isso a
    cadeia de substituição fica com um elo cego, que é exatamente o que ela
    existe para evitar. A publicação apontada precisa existir e estar ativa.
    """
    avulsa = await obter_avulsa(db, avulsa_id)

    if dados.status_novo == StatusPublicacaoAvulsa.SUBSTITUIDO:
        if dados.substituida_por_id is None:
            raise domain_exc.ConflitoNegocioError(
                "Substituição exige o id da publicação que sucede esta."
            )
        # Confere que o alvo existe e está ativo — reaproveita obter_avulsa,
        # que já levanta 404 se não achar.
        await obter_avulsa(db, dados.substituida_por_id)
        avulsa.substituida_por_id = dados.substituida_por_id

    if dados.status_novo is not None:
        avulsa.status = dados.status_novo
    if dados.titulo is not None:
        avulsa.titulo = dados.titulo
    if dados.ementa is not None:
        avulsa.ementa = dados.ementa
    if dados.emissor is not None:
        avulsa.emissor = dados.emissor
    if dados.sistema_ata_id is not None:
        avulsa.sistema_ata_id = dados.sistema_ata_id

    await db.flush()
    return avulsa


async def excluir_avulsa(db: AsyncSession, avulsa_id: uuid.UUID) -> None:
    """Soft delete (D-S6) — a linha nunca é removida, só marcada `ativo=False`."""
    avulsa = await obter_avulsa(db, avulsa_id)
    avulsa.ativo = False
    await db.flush()


async def buscar_avulsas(
    db: AsyncSession,
    *,
    numero: str | None = None,
    ano: int | None = None,
    tipo: TipoPublicacao | None = None,
    status_filtro: StatusPublicacaoAvulsa | None = None,
    ata_codigo: str | None = None,
    texto: str | None = None,
    incluir_inativas: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[PublicacaoAvulsa]]:
    """
    Busca por metadados — número, ano, tipo, ATA (join com `sistemas_ata`) e
    texto livre (LIKE em `titulo`/`ementa`, com `escape_like` para não deixar
    `%`/`_` digitados pelo usuário virarem curinga — SEC-07, portável para
    Postgres por não depender de FTS nenhum).
    """
    limit = min(max(limit, 1), LIMITE_MAXIMO_LISTAGEM)
    offset = max(offset, 0)

    condicoes = []
    if not incluir_inativas:
        condicoes.append(PublicacaoAvulsa.ativo.is_(True))
    if numero:
        condicoes.append(
            PublicacaoAvulsa.numero.ilike(f"%{escape_like(numero)}%", escape="\\")
        )
    if ano:
        condicoes.append(PublicacaoAvulsa.ano == ano)
    if tipo:
        condicoes.append(PublicacaoAvulsa.tipo == tipo)
    if status_filtro:
        condicoes.append(PublicacaoAvulsa.status == status_filtro)
    if texto:
        padrao = f"%{escape_like(texto)}%"
        condicoes.append(
            or_(
                PublicacaoAvulsa.titulo.ilike(padrao, escape="\\"),
                PublicacaoAvulsa.ementa.ilike(padrao, escape="\\"),
            )
        )

    query = select(PublicacaoAvulsa)
    count_query = select(func.count(PublicacaoAvulsa.id))
    if ata_codigo:
        from app.modules.panes.models import SistemaAta

        query = query.join(SistemaAta, SistemaAta.id == PublicacaoAvulsa.sistema_ata_id)
        count_query = count_query.join(
            SistemaAta, SistemaAta.id == PublicacaoAvulsa.sistema_ata_id
        )
        condicoes.append(SistemaAta.codigo == ata_codigo)

    for condicao in condicoes:
        query = query.where(condicao)
        count_query = count_query.where(condicao)

    total = (await db.execute(count_query)).scalar_one()
    resultados = (
        await db.execute(
            query.order_by(PublicacaoAvulsa.data_recebimento.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return total, list(resultados)


async def adicionar_anexo(
    db: AsyncSession,
    avulsa_id: uuid.UUID,
    *,
    conteudo: bytes,
    nome_original: str,
    principal: bool = False,
) -> PublicacaoAvulsaAnexo:
    """
    Registra um anexo já validado e já enviado ao storage.

    Deliberadamente recebe `conteudo`/`nome_original` (não `UploadFile`): a
    validação de MIME/tamanho e o upload em si acontecem no router, que é
    quem tem acesso a `StorageService` e ao limite configurado — esta função
    só grava o resultado no catálogo. Mantém `avulsas.py` livre de I/O de
    storage, que já tem seu próprio ponto único (`shared/core/storage.py`).
    """
    from app.shared.core.storage import get_storage_service

    await obter_avulsa(db, avulsa_id)  # 404 se não existir/inativa

    storage = get_storage_service()
    file_key = await storage.upload(conteudo, nome_original, "application/pdf")

    anexo = PublicacaoAvulsaAnexo(
        avulsa_id=avulsa_id,
        file_key=file_key,
        nome_original=nome_original,
        tamanho_bytes=len(conteudo),
        principal=principal,
    )
    db.add(anexo)
    await db.flush()
    return anexo


async def obter_anexo(
    db: AsyncSession, avulsa_id: uuid.UUID, anexo_id: uuid.UUID
) -> PublicacaoAvulsaAnexo:
    anexo = (
        await db.execute(
            select(PublicacaoAvulsaAnexo).where(
                PublicacaoAvulsaAnexo.id == anexo_id,
                PublicacaoAvulsaAnexo.avulsa_id == avulsa_id,
            )
        )
    ).scalar_one_or_none()
    if anexo is None:
        raise domain_exc.EntidadeNaoEncontradaError("Anexo não encontrado.")
    return anexo
