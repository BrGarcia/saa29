"""
app/modules/publicacoes/router.py
Endpoints do módulo de publicações.

Registrado em main.py com prefix="/publicacoes". Todo endpoint JSON vive sob
o sub-prefixo "/api/..." (portanto "/publicacoes/api/..." na aplicação), para
que API_PREFIXES possa registrar "/publicacoes/api/" sem capturar as páginas
HTML do módulo — ver 03_especificacao_tecnica.md §3.

M1: busca, mensagens do FIM, status do índice e entrega do PDF.
M2: avulsas (CRUD + anexos).
"""

# SEM `from __future__ import annotations` — de propósito, e não por esquecimento.
# Com ele, as anotações viram strings e o FastAPI precisa resolvê-las por
# `get_type_hints`; para um endpoint embrulhado pelo `@limiter.limit`, essa
# resolução acontece no namespace do slowapi, onde `CurrentUser`/`DBSession` não
# existem. O efeito é silencioso e absurdo: `_: CurrentUser` deixa de ser
# dependência e vira query param obrigatório, e a busca passa a devolver 422
# pedindo um parâmetro chamado `_`. Nenhum router do projeto usa o import.
import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse

from app.bootstrap.config import get_settings
from app.bootstrap.dependencies import AdminRequired, CurrentUser, DBSession, EncarregadoInspetorOuAdmin
from app.modules.publicacoes import avulsas, schemas, search, service
from app.shared.core.enums import StatusEdicao, StatusPublicacaoAvulsa, TipoPublicacao
from app.shared.core.file_validators import ler_upload_com_limite, validate_file_upload
from app.shared.core.limiter import limiter

router = APIRouter()


def _viewer_url(doc_id: uuid.UUID | str, pagina: int | None = None) -> str:
    base = f"/publicacoes/viewer/{doc_id}"
    return f"{base}#page={pagina}" if pagina else base


def _resolver_pdf(raiz: str, file_key: str) -> Path | None:
    """
    Caminho absoluto do PDF, ou None se não existir ou escapar do manual.

    Síncrona de propósito: `resolve()` e `is_file()` tocam o disco, e a regra
    ASYNC do ruff (com razão) proíbe isso dentro de `async def` — quem chama
    passa por `asyncio.to_thread`.

    A verificação de contenção é defesa em profundidade: `file_key` é gerado
    pelo indexador, mas um catálogo adulterado não deve virar leitura arbitrária
    de disco.
    """
    base = Path(raiz).resolve()
    caminho = (base / file_key).resolve()
    if not caminho.is_relative_to(base) or not caminho.is_file():
        return None
    return caminho


@router.get(
    "/api/busca",
    response_model=schemas.RespostaBusca,
    summary="Busca full-text no acervo de manuais",
)
@limiter.limit("30/minute")
async def buscar(
    request: Request,
    _: CurrentUser,
    q: str = Query(..., min_length=1, max_length=200, description="Termo de busca"),
    manual: str | None = Query(default=None, max_length=40),
    capitulo: str | None = Query(default=None, max_length=80),
    categoria: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> schemas.RespostaBusca:
    """
    Busca por página, ordenada por relevância (BM25).

    `request: Request` na assinatura não é decoração: o decorator do slowapi
    **exige** o parâmetro e falha em runtime sem ele (precedente
    `panes/router.py:107`).
    """
    settings = get_settings()
    try:
        bruto = await search.buscar(
            Path(settings.publicacoes_index_path),
            q,
            manual=manual,
            capitulo=capitulo,
            categoria=categoria,
            limit=limit,
            offset=offset,
        )
    except search.QueryInvalidaError as exc:
        # Sintaxe FTS inválida vira 400, nunca 500 (E-06).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except search.IndiceIndisponivelError:
        # Acervo ainda não indexado: resposta vazia, não erro (E-12). A UI
        # mostra o estado vazio e /api/status explica o porquê.
        return schemas.RespostaBusca(query=q, total=0, took_ms=0, results=[])

    resultados = [
        schemas.ResultadoBusca(
            # `uuid.UUID(...)`, não a string crua: o contrato entre os dois
            # bancos exige a conversão explícita (§2.2.1, achado B5).
            doc_id=uuid.UUID(str(linha["document_id"])),
            title=str(linha["titulo"]),
            manual=schemas.ManualRef(
                path=str(linha["manual_codigo"]),
                description=str(linha["categoria"]),
            ),
            chapter=str(linha["capitulo"]),
            page=int(linha["page_number"]),
            snippet=str(linha["snippet"]),
            viewer_url=_viewer_url(linha["document_id"], int(linha["page_number"])),
        )
        for linha in bruto["results"]  # type: ignore[union-attr]
    ]
    return schemas.RespostaBusca(
        query=q,
        total=int(bruto["total"]),  # type: ignore[arg-type]
        took_ms=int(bruto["took_ms"]),  # type: ignore[arg-type]
        results=resultados,
    )


@router.get(
    "/api/fim",
    response_model=schemas.RespostaFim,
    summary="Mensagem de falha (CAS) → procedimento do FIM",
)
async def buscar_fim(
    db: DBSession,
    _: CurrentUser,
    mensagem: str = Query(..., min_length=1, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
) -> schemas.RespostaFim:
    """
    Resolve a mensagem exibida no CAS para o procedimento correspondente.

    Casamento por prefixo: `ADC` devolve `ADC 001`, `ADC 002`… É a forma como o
    mecânico usa — ele lê a mensagem no painel e digita o começo dela.
    """
    pares = await service.buscar_por_mensagem_fim(db, mensagem, limit=limit)
    return schemas.RespostaFim(
        total=len(pares),
        results=[
            schemas.ProcedimentoFim(
                mensagem=mapa.mensagem,
                procedimento=mapa.procedimento,
                doc_id=documento.id if documento else None,
                title=documento.titulo if documento else None,
                viewer_url=_viewer_url(documento.id) if documento else None,
            )
            for mapa, documento in pares
        ],
    )


@router.get(
    "/api/status",
    response_model=schemas.StatusPublicacoes,
    summary="Estado do índice e do catálogo",
)
async def status_publicacoes(
    db: DBSession,
    _: CurrentUser,
) -> schemas.StatusPublicacoes:
    """Junta os dois lados: catálogo (banco principal) e índice (`catalog.db`)."""
    settings = get_settings()
    catalogo = await service.status_do_catalogo(db)
    indice = await search.status_indice(Path(settings.publicacoes_index_path))

    return schemas.StatusPublicacoes(
        indice_disponivel=bool(indice["disponivel"]),
        edicao=catalogo["edicao"],  # type: ignore[arg-type]
        manuais=int(catalogo["manuais"]),  # type: ignore[arg-type]
        documentos=int(catalogo["documentos"]),  # type: ignore[arg-type]
        documentos_sem_texto=int(catalogo["documentos_sem_texto"]),  # type: ignore[arg-type]
        paginas_indexadas=int(indice["paginas"]),  # type: ignore[arg-type]
        mensagens_fim=int(catalogo["mensagens_fim"]),  # type: ignore[arg-type]
        atualizado_em=indice["atualizado_em"],  # type: ignore[arg-type]
    )


@router.get(
    "/api/documentos/{doc_id}",
    response_model=schemas.DocumentoViewerOut,
    summary="Metadados de um documento, para o cabeçalho do viewer",
)
async def obter_documento_viewer(
    doc_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
) -> schemas.DocumentoViewerOut:
    documento = await service.obter_documento(db, doc_id)
    if documento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado."
        )

    equivalente = await service.obter_equivalente_vigente(db, documento)
    return schemas.DocumentoViewerOut(
        id=documento.id,
        titulo=documento.titulo,
        manual=schemas.ManualRef(
            path=documento.manual.codigo, description=documento.manual.descricao_pt
        ),
        capitulo=documento.capitulo,
        paginas=documento.paginas,
        edicao_rotulo=documento.manual.edicao.rotulo,
        edicao_vigente=documento.manual.edicao.status == StatusEdicao.VIGENTE,
        equivalente_vigente_id=equivalente,
    )


@router.get(
    "/doc/{doc_id}/pdf",
    summary="Entrega o PDF de um documento do acervo",
    response_class=FileResponse,
)
async def obter_pdf(
    doc_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
    pagina: int | None = Query(default=None, ge=1, description="Página aberta, para auditoria"),
) -> FileResponse:
    """
    Devolve o arquivo do disco e registra o acesso.

    Rota declarada sob `/doc/`, fora de `/api/`, de propósito: é resposta
    binária consumida pelo viewer, e um 401 aqui deve redirecionar para o login
    como qualquer página, não devolver JSON (risco R20).
    """
    documento = await service.obter_documento(db, doc_id)
    if documento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado."
        )

    # Disco em thread: bloquear o event loop aqui atrasa toda requisição
    # concorrente do mesmo worker (padrão de panes/router.py:395).
    caminho = await asyncio.to_thread(
        _resolver_pdf, documento.manual.path, documento.file_key
    )
    if caminho is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo físico do documento não encontrado.",
        )

    await service.registrar_acesso(
        db, usuario_id=usuario_atual.id, documento=documento, pagina=pagina
    )
    return FileResponse(
        path=caminho,
        filename=caminho.name,
        media_type="application/pdf",
    )


# ==========================================================================
# Publicações avulsas (acervo B, M2)
# ==========================================================================


@router.get(
    "/api/avulsas",
    response_model=schemas.RespostaListaAvulsas,
    summary="Busca de publicações avulsas por metadados",
)
async def buscar_avulsas(
    db: DBSession,
    _: CurrentUser,
    numero: str | None = Query(default=None, max_length=60),
    ano: int | None = Query(default=None, ge=1990, le=2100),
    tipo: TipoPublicacao | None = Query(default=None),
    # Nunca `status`: sombrearia `fastapi.status`, importado neste mesmo
    # arquivo — trap real já documentado em `panes/router.py:71-75`.
    status_filtro: StatusPublicacaoAvulsa | None = Query(default=None, alias="status"),
    ata: str | None = Query(default=None, max_length=4, description="Código ATA, ex: 34"),
    texto: str | None = Query(default=None, max_length=200, description="Busca em título/ementa"),
    incluir_inativas: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> schemas.RespostaListaAvulsas:
    total, resultados = await avulsas.buscar_avulsas(
        db,
        numero=numero,
        ano=ano,
        tipo=tipo,
        status_filtro=status_filtro,
        ata_codigo=ata,
        texto=texto,
        incluir_inativas=incluir_inativas,
        limit=limit,
        offset=offset,
    )

    def _item(a) -> schemas.PublicacaoAvulsaListItem:
        snippet = None
        if texto:
            fonte = a.ementa if texto.lower() in a.ementa.lower() else a.titulo
            snippet = avulsas.construir_snippet(fonte, texto)
        return schemas.PublicacaoAvulsaListItem(
            id=a.id, tipo=a.tipo, numero=a.numero, ano=a.ano, titulo=a.titulo,
            status=a.status, data_recebimento=a.data_recebimento, snippet=snippet,
        )

    return schemas.RespostaListaAvulsas(
        total=total, results=[_item(a) for a in resultados]
    )


@router.get(
    "/api/avulsas/{avulsa_id}",
    response_model=schemas.PublicacaoAvulsaOut,
    summary="Detalhe de uma publicação avulsa",
)
async def obter_avulsa(avulsa_id: uuid.UUID, db: DBSession, _: CurrentUser) -> schemas.PublicacaoAvulsaOut:
    avulsa = await avulsas.obter_avulsa(db, avulsa_id)
    return schemas.PublicacaoAvulsaOut.model_validate(avulsa)


@router.post(
    "/api/avulsas",
    response_model=schemas.PublicacaoAvulsaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar publicação avulsa",
)
async def criar_avulsa(
    dados: schemas.PublicacaoAvulsaCreate,
    db: DBSession,
    usuario_atual: EncarregadoInspetorOuAdmin,
) -> schemas.PublicacaoAvulsaOut:
    avulsa = await avulsas.criar_avulsa(db, dados, usuario_id=usuario_atual.id)
    return schemas.PublicacaoAvulsaOut.model_validate(avulsa)


@router.patch(
    "/api/avulsas/{avulsa_id}",
    response_model=schemas.PublicacaoAvulsaOut,
    summary="Corrigir metadados ou transicionar vigência",
)
async def atualizar_avulsa(
    avulsa_id: uuid.UUID,
    dados: schemas.PublicacaoAvulsaUpdate,
    db: DBSession,
    _: EncarregadoInspetorOuAdmin,
) -> schemas.PublicacaoAvulsaOut:
    avulsa = await avulsas.atualizar_avulsa(db, avulsa_id, dados)
    return schemas.PublicacaoAvulsaOut.model_validate(avulsa)


@router.delete(
    "/api/avulsas/{avulsa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir publicação avulsa (soft delete)",
)
async def excluir_avulsa(avulsa_id: uuid.UUID, db: DBSession, _: AdminRequired) -> None:
    """D-S6: exclusão é privilégio de Admin, mesmo cadastro sendo de Encarregado/Inspetor/Admin."""
    await avulsas.excluir_avulsa(db, avulsa_id)


@router.post(
    "/api/avulsas/{avulsa_id}/anexos",
    response_model=schemas.AnexoAvulsaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo (PDF/imagem escaneada)",
)
@limiter.limit("10/minute")
async def upload_anexo_avulsa(
    request: Request,
    avulsa_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoInspetorOuAdmin,
    arquivo: UploadFile = File(description="PDF escaneado ou imagem do documento"),
    principal: bool = False,
) -> schemas.AnexoAvulsaOut:
    """
    Fora do pipeline de imagem de propósito: `shared/services/image/pipeline.py`
    reprocessa fotos de pane para exibição — um PDF escaneado de BO/BS vai
    direto ao storage, sem recompressão nem conversão.
    """
    await validate_file_upload(arquivo)
    max_bytes = int(get_settings().publicacoes_avulsas_max_upload_mb * 1024 * 1024)
    conteudo = await ler_upload_com_limite(arquivo, max_bytes)

    anexo = await avulsas.adicionar_anexo(
        db,
        avulsa_id,
        conteudo=conteudo,
        nome_original=arquivo.filename or "anexo",
        principal=principal,
    )
    return schemas.AnexoAvulsaOut.model_validate(anexo)


@router.get(
    "/avulsas/{avulsa_id}/anexo/{anexo_id}",
    summary="Entrega o anexo de uma publicação avulsa",
)
async def obter_anexo_avulsa(
    avulsa_id: uuid.UUID, anexo_id: uuid.UUID, db: DBSession, _: CurrentUser
):
    from app.shared.core.storage import get_storage_service

    anexo = await avulsas.obter_anexo(db, avulsa_id, anexo_id)
    storage = get_storage_service()
    url_ou_caminho = await storage.get_url(anexo.file_key)

    if url_ou_caminho.startswith(("http://", "https://")):
        return RedirectResponse(url_ou_caminho)

    caminho = Path(url_ou_caminho)
    # Disco em thread: mesmo motivo do PDF do acervo A (panes/router.py:395).
    existe = await asyncio.to_thread(caminho.is_file)
    if not existe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo físico do anexo não encontrado.",
        )
    return FileResponse(path=caminho, filename=anexo.nome_original)
