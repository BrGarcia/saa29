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
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.bootstrap.config import get_settings
from app.bootstrap.dependencies import AdminRequired, CurrentUser, DBSession, EncarregadoInspetorOuAdmin, InspetorOuAdmin
from app.modules.publicacoes import avulsas, schemas, search, service
from app.shared.core.enums import (
    ModoProcessamentoUpload,
    StatusEdicao,
    StatusPublicacaoAvulsa,
    StatusUploadJob,
    TipoPublicacao,
)
from app.shared.core.file_validators import ler_upload_com_limite, validate_file_upload
from app.shared.core.limiter import limiter
from app.shared.core.storage import LocalStorageService, get_storage_service

logger = logging.getLogger(__name__)

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
    p_raiz = Path(raiz)
    if p_raiz.is_absolute():
        base = p_raiz.resolve()
    else:
        acervo_base = (Path(get_settings().publicacoes_acervo_dir) / p_raiz).resolve()
        if acervo_base.is_dir():
            base = acervo_base
        else:
            base = p_raiz.resolve()

    caminho = (base / file_key).resolve()
    if caminho.is_relative_to(base) and caminho.is_file():
        return caminho

    # Fallback para fixtures do piloto FIM (apenas em dev/test, com contenção de caminho)
    settings = get_settings()
    if settings.app_env in ("development", "testing") or settings.app_debug:
        fixture_base = Path("tests/fixtures/fim").resolve()
        if fixture_base.is_dir():
            fixture_fallback = (fixture_base / file_key).resolve()
            if fixture_fallback.is_relative_to(fixture_base) and fixture_fallback.is_file():
                return fixture_fallback

    return None


@router.get(
    "/api/busca",
    response_model=schemas.RespostaBusca,
    summary="Busca full-text no acervo de manuais",
)
@limiter.limit("30/minute")
async def buscar(
    request: Request,
    db: DBSession,
    _: CurrentUser,
    q: str = Query(..., min_length=1, max_length=200, description="Termo de busca"),
    manual: str | None = Query(default=None, max_length=40),
    capitulo: str | None = Query(default=None, max_length=80),
    categoria: str | None = Query(default=None, max_length=60),
    ata: str | None = Query(default=None, max_length=4, description="Código ATA, ex: 34"),
    documento_id: uuid.UUID | None = Query(
        default=None,
        description=(
            "Restringe a busca a um único documento — a busca de texto DENTRO "
            "do documento que o viewer usa (publicacoes_viewer.js)."
        ),
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> schemas.RespostaBusca:
    """
    Busca por página, ordenada por relevância (BM25).

    `request: Request` na assinatura não é decoração: o decorator do slowapi
    **exige** o parâmetro e falha em runtime sem ele (precedente
    `panes/router.py:107`).

    `db` entra aqui só para resolver QUAL índice abrir: cada edição tem o seu
    `catalog.<rotulo>.db`, e a edição VIGENTE no banco é que decide (ADR-004,
    "Resolução do índice por edição"). É o que faz ativar uma edição mudar de
    fato o que a busca devolve.
    """
    caminho_indice = await service.caminho_indice_vigente(db)
    try:
        bruto = await search.buscar(
            caminho_indice,
            q,
            manual=manual,
            capitulo=capitulo,
            categoria=categoria,
            ata=ata,
            documento_id=str(documento_id) if documento_id else None,
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
    "/api/fim/por-ata/{ata_codigo}",
    response_model=schemas.RespostaFim,
    summary="Procedimentos do FIM para um código ATA",
)
async def listar_fim_por_ata(
    ata_codigo: str, db: DBSession, _: CurrentUser
) -> schemas.RespostaFim:
    """
    Alimenta o bloco "Procedimentos FIM do ATA XX" no detalhe da pane (M3
    tarefa 1) — filtrado por `sistema_ata.codigo` da pane aberta.
    """
    pares = await service.listar_fim_por_ata(db, ata_codigo)
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
    catalogo = await service.status_do_catalogo(db)
    indice = await search.status_indice(await service.caminho_indice_vigente(db))

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


# ==========================================================================
# Navegação do catálogo (Etapa 2 de 09_plano_configuracoes.md — lacuna do M1)
# ==========================================================================
#
# `/publicacoes` era só busca: sem digitar um termo, ou sem já saber o código
# do manual, o acervo de 34 manuais / 5.724 documentos não tinha por onde ser
# descoberto. Estas três rotas — sempre `CurrentUser`, a matriz RBAC §7
# libera "navegar catálogo" para os quatro perfis — alimentam as páginas de
# navegação (`pages/router.py`) e os `<select>` de refino da busca.


@router.get(
    "/api/manuais",
    response_model=list[schemas.ManualListItem],
    summary="Manuais da edição vigente, para o índice do acervo",
)
async def listar_manuais(db: DBSession, _: CurrentUser) -> list[schemas.ManualListItem]:
    """Sem paginação — 34 manuais cabem numa resposta só; o agrupamento por categoria é do cliente."""
    linhas = await service.listar_manuais_vigentes(db)
    return [schemas.ManualListItem(**linha) for linha in linhas]  # type: ignore[arg-type]


@router.get(
    "/api/manuais/{codigo}/capitulos",
    response_model=schemas.RespostaCapitulos,
    summary="Capítulos de um manual da edição vigente",
)
async def listar_capitulos_do_manual(
    codigo: str, db: DBSession, _: CurrentUser
) -> schemas.RespostaCapitulos:
    dados = await service.obter_manual_com_capitulos(db, codigo)
    return schemas.RespostaCapitulos(
        manual=schemas.ManualResumo(**dados["manual"]),  # type: ignore[arg-type]
        capitulos=[schemas.CapituloItem(**c) for c in dados["capitulos"]],  # type: ignore[arg-type]
    )


@router.get(
    "/api/manuais/{codigo}/documentos",
    response_model=schemas.RespostaDocumentosCatalogo,
    summary="Documentos de um manual da edição vigente (opcionalmente por capítulo)",
)
async def listar_documentos_do_manual(
    codigo: str,
    db: DBSession,
    _: CurrentUser,
    capitulo: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> schemas.RespostaDocumentosCatalogo:
    """
    `viewer_url` sem `#page` — a navegação abre o documento no começo; quem
    quer a página do trecho vem pela busca, que já monta a âncora.
    """
    total, documentos = await service.listar_documentos_do_manual(
        db, codigo, capitulo=capitulo, limit=limit, offset=offset
    )
    return schemas.RespostaDocumentosCatalogo(
        total=total,
        results=[
            schemas.DocumentoCatalogoItem(
                doc_id=doc.id,
                titulo=doc.titulo,
                capitulo=doc.capitulo,
                ata_codigo=doc.ata_codigo,
                paginas=doc.paginas,
                has_text=doc.has_text,
                viewer_url=_viewer_url(doc.id),
            )
            for doc in documentos
        ],
    )


@router.get(
    "/api/catalogo/busca",
    response_model=schemas.RespostaCatalogoBusca,
    summary="Busca por NOME e CAMINHO no catálogo (não por conteúdo)",
)
@limiter.limit("60/minute")
async def buscar_no_catalogo(
    request: Request,
    db: DBSession,
    _: CurrentUser,
    q: str = Query(..., min_length=1, max_length=200, description="Termo de busca"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> schemas.RespostaCatalogoBusca:
    """
    Busca por NOME/CAMINHO no catálogo, usada pelo explorador
    (`publicacoes_explorador.js`) — casa contra título, capítulo, `file_key` e
    o manual (código e descrição), escopado à edição vigente. Complementa, não
    substitui, `GET /api/busca`: aquele indexa texto de PÁGINA (`catalog.db`);
    este indexa NOME (banco principal) — "AMM CHAPTER_21" ou "sangria.pdf" só
    voltam daqui.

    Limite próprio (60/min, contra 30/min de `/api/busca`): é consulta ao banco
    principal via índice de coluna, não full-text sobre um SQLite de 155 MB —
    mais barata, e a caixa de busca do explorador pode chamar isto a cada
    tecla (com debounce no cliente).
    """
    total, linhas = await service.buscar_no_catalogo(db, q, limit=limit, offset=offset)
    return schemas.RespostaCatalogoBusca(
        total=total,
        results=[
            schemas.CatalogoBuscaItem(
                doc_id=doc.id,
                titulo=doc.titulo,
                manual=schemas.ManualRef(path=manual.codigo, description=manual.descricao_pt),
                capitulo=doc.capitulo,
                caminho=f"{manual.categoria} › {manual.codigo} › {doc.capitulo}",
                viewer_url=_viewer_url(doc.id),
            )
            for doc, manual in linhas
        ],
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
# Ciclo de vida das edições (M4 tarefa 4 — card de /configuracoes)
# ==========================================================================
#
# Todo endpoint aqui é `AdminRequired`. A página /configuracoes já exige Admin
# (`app/web/pages/router.py`), mas gate de página não é autorização: quem chama
# a API não passa necessariamente pela página.


@router.get(
    "/api/edicoes",
    response_model=list[schemas.EdicaoListItem],
    summary="Edições do acervo, com estado do índice de cada uma",
)
async def listar_edicoes(db: DBSession, _: AdminRequired) -> list[schemas.EdicaoListItem]:
    linhas = await service.listar_edicoes(db)
    return [schemas.EdicaoListItem(**linha) for linha in linhas]  # type: ignore[arg-type]


@router.get(
    "/api/edicoes/{edicao_id}/relatorio",
    response_model=schemas.RelatorioEdicaoOut,
    summary="Relatório de diff gravado na publicação",
)
async def obter_relatorio_edicao(
    edicao_id: uuid.UUID, db: DBSession, _: AdminRequired
) -> schemas.RelatorioEdicaoOut:
    """
    É este relatório que alguém lê **antes** de decidir ativar (runbook §2).

    `relatorio` nulo é resposta válida, não 404: a edição existe, só não foi
    publicada por `publicar.py` — é o caso da linha sintética `piloto-fim`.
    """
    edicao = await service.obter_edicao(db, edicao_id)
    return schemas.RelatorioEdicaoOut(
        edicao_id=edicao.id, rotulo=edicao.rotulo, relatorio=edicao.relatorio_diff
    )


@router.post(
    "/api/edicoes/{edicao_id}/ativar",
    response_model=schemas.EdicaoListItem,
    summary="Tornar esta a edição vigente (reverter = ativar a anterior)",
)
async def ativar_edicao(
    edicao_id: uuid.UUID, db: DBSession, usuario_atual: AdminRequired
) -> schemas.EdicaoListItem:
    """
    Muda o que toda a organização lê como manual em vigor.

    Não há endpoint de "reverter": reverter é ativar a edição ANTERIOR, o mesmo
    caminho de código. Recusas em 409 — já vigente, arquivada, ou sem índice em
    disco (ver `service.ativar_edicao`).
    """
    edicao = await service.ativar_edicao(db, edicao_id, usuario_id=usuario_atual.id)
    return await _item_da_edicao(db, edicao.id)


@router.post(
    "/api/edicoes/{edicao_id}/arquivar",
    response_model=schemas.EdicaoListItem,
    summary="Arquivar edição (libera os artefatos de disco para descarte)",
)
async def arquivar_edicao(
    edicao_id: uuid.UUID, db: DBSession, _: AdminRequired
) -> schemas.EdicaoListItem:
    edicao = await service.arquivar_edicao(db, edicao_id)
    return await _item_da_edicao(db, edicao.id)


@router.delete(
    "/api/edicoes/{edicao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir edição em definitivo (linha + auditoria + snapshot + índice)",
)
async def excluir_edicao(edicao_id: uuid.UUID, db: DBSession, _: AdminRequired) -> None:
    """
    Hard delete — fase de implementação em que erros de exportação são
    frequentes e "arquivar" não basta para tirar uma edição enviada errada do
    caminho (ver `service.excluir_edicao`). Some com a linha do catálogo, a
    auditoria de acesso daquela edição, o snapshot no storage e o índice de
    busca (`catalog.<rotulo>.db`); a árvore de PDFs do acervo, compartilhada
    entre edições, não é tocada — mesmo limite de `arquivar_edicao`.
    """
    edicao = await service.excluir_edicao(db, edicao_id)
    rotulo, snapshot_key = edicao.rotulo, edicao.snapshot_key

    storage = get_storage_service()
    if snapshot_key:
        try:
            await storage.delete(snapshot_key)
        except Exception as exc:
            logger.warning("Falha ao apagar snapshot da edição excluída %r: %s", rotulo, exc)

    try:
        caminho_indice = service.caminho_indice_da_edicao(rotulo)
    except service.RotuloInvalidoError:
        caminho_indice = None
    if caminho_indice is not None:
        try:
            await asyncio.to_thread(caminho_indice.unlink, True)
        except Exception as exc:
            logger.warning("Falha ao apagar índice de busca da edição excluída %r: %s", rotulo, exc)


async def _item_da_edicao(db: DBSession, edicao_id: uuid.UUID) -> schemas.EdicaoListItem:
    """
    Relê a edição pela mesma consulta da listagem.

    Devolver o item completo (com contagens e `indice_disponivel` recalculado)
    deixa a UI atualizar a linha sem uma segunda chamada — e garante que ela
    veja exatamente o que a listagem mostraria.
    """
    item = next(
        (linha for linha in await service.listar_edicoes(db) if linha["id"] == edicao_id),
        None,
    )
    if item is None:  # pragma: no cover - a edição acabou de ser lida na mesma transação
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Edição não encontrada."
        )
    return schemas.EdicaoListItem(**item)  # type: ignore[arg-type]


@router.get(
    "/api/duplicacao",
    response_model=schemas.DuplicacaoOut,
    summary="Sobreposição por hash entre a edição vigente e a anterior",
)
async def medir_duplicacao(db: DBSession, _: AdminRequired) -> schemas.DuplicacaoOut:
    """
    Dimensiona quanto um esquema de dedup física economizaria — dado que falta
    para o gate do M4 ("disco da VPS < 60% após duas edições retidas").

    **Mede, não deduplica.** As edições apontam para a mesma árvore em disco
    hoje; não há cópia física a eliminar ainda.
    """
    medicao = await service.medir_duplicacao_entre_edicoes(db)
    return schemas.DuplicacaoOut(**medicao)  # type: ignore[arg-type]


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


# ==========================================================================
# Favoritos (transversal aos dois acervos, M3)
# ==========================================================================


@router.get(
    "/api/favoritos",
    response_model=list[schemas.FavoritoOut],
    summary="Favoritos do usuário logado",
)
async def listar_favoritos(db: DBSession, usuario_atual: CurrentUser) -> list[schemas.FavoritoOut]:
    favoritos = await service.listar_favoritos(db, usuario_atual.id)
    return [schemas.FavoritoOut.model_validate(f) for f in favoritos]


@router.post(
    "/api/favoritos",
    response_model=schemas.FavoritoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Favoritar um documento do acervo A ou uma publicação avulsa",
)
async def criar_favorito(
    dados: schemas.FavoritoCreate, db: DBSession, usuario_atual: CurrentUser
) -> schemas.FavoritoOut:
    """
    Exatamente um dos dois campos — mesmo XOR do `CheckConstraint` do model
    (achado B1), validado aqui em vez de deixar o banco rejeitar com um erro
    de integridade pouco legível para quem consome a API.
    """
    if (dados.documento_id is None) == (dados.avulsa_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe exatamente um de documento_id ou avulsa_id.",
        )

    if dados.documento_id is not None:
        favorito = await service.favoritar_documento(db, usuario_atual.id, dados.documento_id)
    else:
        favorito = await service.favoritar_avulsa(db, usuario_atual.id, dados.avulsa_id)
    return schemas.FavoritoOut.model_validate(favorito)


@router.delete(
    "/api/favoritos/{favorito_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover favorito",
)
async def remover_favorito(favorito_id: uuid.UUID, db: DBSession, usuario_atual: CurrentUser) -> None:
    await service.remover_favorito(db, usuario_atual.id, favorito_id)


# --------------------------------------------------------------------------
# Upload de Edições (M4.Web)
# --------------------------------------------------------------------------

_FERRAMENTAS_DOWNLOAD = {
    "zipar_disco.py": "text/x-python",
    "zipar_disco.bat": "application/x-bat",
}


@router.get(
    "/api/ferramentas/{nome_arquivo}",
    summary="Baixar script auxiliar (ex.: zipar disco inteiro antes do envio)",
    response_class=FileResponse,
)
async def baixar_ferramenta(nome_arquivo: str, usuario_atual: InspetorOuAdmin) -> FileResponse:
    """
    Serve os scripts de scripts/publicacoes/ (fonte única, sem duplicar em
    app/web/static/) para o usuário rodar localmente antes de enviar o zip
    pela tela de configurações.
    """
    media_type = _FERRAMENTAS_DOWNLOAD.get(nome_arquivo)
    if media_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada.")

    caminho = Path("scripts/publicacoes") / nome_arquivo
    if not caminho.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada.")

    return FileResponse(path=caminho, filename=nome_arquivo, media_type=media_type)


@router.post(
    "/api/edicoes/uploads",
    response_model=schemas.UploadIniciarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar upload de nova edição (.zip)",
)
@limiter.limit("5/hour")
async def iniciar_upload_edicao(
    request: Request,
    dados: schemas.UploadIniciarIn,
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
) -> schemas.UploadIniciarOut:
    """
    Valida rótulo e tamanho declarado, e cria o job de upload (status ENVIANDO).
    Inicia o multipart no storage e retorna as credenciais/chaves para envio das partes.
    """
    # 1. Validar rótulo
    try:
        service._validar_rotulo(dados.rotulo)
    except service.RotuloInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 2. Teto de tamanho declarado, configurável via publicacoes_upload_max_gb
    max_gb = get_settings().publicacoes_upload_max_gb
    max_bytes = max_gb * 1024 * 1024 * 1024
    if dados.tamanho_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tamanho do arquivo excede o limite máximo permitido de {max_gb} GB.",
        )

    # 3. Recusar se já existe edição com esse rótulo que esteja VIGENTE
    from sqlalchemy import select
    from app.modules.publicacoes.models import ManualEdicao, PublicacoesUploadJob
    edicao_existente = (
        await db.execute(select(ManualEdicao).where(ManualEdicao.rotulo == dados.rotulo))
    ).scalar_one_or_none()
    if edicao_existente is not None and edicao_existente.status == StatusEdicao.VIGENTE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A edição {dados.rotulo!r} já está VIGENTE. Para atualizar o acervo, crie uma nova edição.",
        )

    # 4. Auto-healing de jobs estagnados/órfãos antes de tentar iniciar novo envio
    await service.limpar_jobs_upload_estagnados(db)

    # 5. Iniciar multipart no storage
    job_id = uuid.uuid4()
    file_key = f"publicacoes/uploads/{job_id}/edicao.zip"
    storage = get_storage_service()

    try:
        upload_id_r2 = await storage.iniciar_multipart(file_key, content_type="application/zip")
    except Exception as exc:
        logger.error("Falha ao iniciar multipart no storage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível iniciar a sessão de upload no storage.",
        ) from exc

    # 6. Criar registro do job (com trava single-flight)
    job = PublicacoesUploadJob(
        id=job_id,
        rotulo=dados.rotulo,
        status=StatusUploadJob.ENVIANDO,
        modo_processamento=dados.modo_processamento,
        etapa="Aguardando upload das partes...",
        progresso_pct=0,
        file_key=file_key,
        upload_id_r2=upload_id_r2,
        tamanho_declarado=dados.tamanho_bytes,
        criado_por_id=usuario_atual.id,
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # Abortar multipart no storage se falhou no banco
        try:
            await storage.abortar_multipart(file_key, upload_id_r2)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um envio ou processamento de publicação em andamento.",
        ) from exc

    return schemas.UploadIniciarOut(
        job_id=job.id,
        file_key=file_key,
        upload_id_r2=upload_id_r2,
        tamanho_parte_mb=100,
    )


@router.post(
    "/api/edicoes/uploads/{job_id}/partes",
    response_model=schemas.ParteUrlOut,
    summary="Obter URL pré-assinada para upload da parte N",
)
async def obter_url_parte_upload(
    job_id: uuid.UUID,
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
    numero: int = Query(..., ge=1, le=10000, description="Número da parte (1-based)"),
) -> schemas.ParteUrlOut:
    from sqlalchemy import select
    from app.modules.publicacoes.models import PublicacoesUploadJob
    job = (
        await db.execute(select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job de upload não encontrado.")

    if job.status != StatusUploadJob.ENVIANDO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Upload não está mais aguardando partes (status atual: {job.status.value}).",
        )

    storage = get_storage_service()
    url = await storage.presign_parte(job.file_key, job.upload_id_r2 or "", numero)
    return schemas.ParteUrlOut(numero=numero, url=url)


@router.api_route(
    "/api/edicoes/uploads/local-parte",
    methods=["PUT", "POST"],
    summary="Endpoint dev local para upload de partes (LocalStorageService)",
)
async def upload_parte_local_dev(
    request: Request,
    upload_id: str = Query(..., description="ID de upload gerado pelo LocalStorageService"),
    numero: int = Query(..., ge=1, description="Número da parte"),
    usuario_atual: InspetorOuAdmin = None,
):
    storage = get_storage_service()
    if not isinstance(storage, LocalStorageService):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Endpoint exclusivo para modo de armazenamento local.",
        )
    body_bytes = await request.body()
    etag = await storage.salvar_parte_local(upload_id, numero, body_bytes)
    return {"etag": etag}


@router.post(
    "/api/edicoes/uploads/{job_id}/concluir",
    response_model=schemas.UploadJobOut,
    summary="Concluir upload das partes e iniciar processamento em segundo plano",
)
async def concluir_upload_edicao(
    job_id: uuid.UUID,
    dados: schemas.UploadConcluirIn,
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
) -> schemas.UploadJobOut:
    from sqlalchemy import select
    from app.modules.publicacoes.models import PublicacoesUploadJob
    job = (
        await db.execute(select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job de upload não encontrado.")

    if job.status != StatusUploadJob.ENVIANDO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Upload não está em estado de envio (status atual: {job.status.value}).",
        )

    storage = get_storage_service()
    partes_dict = [{"numero": p.numero, "etag": p.etag} for p in dados.partes]

    try:
        await storage.concluir_multipart(job.file_key, job.upload_id_r2 or "", partes_dict)
    except Exception as exc:
        logger.error("Falha ao concluir multipart no storage para job %s: %s", job_id, exc)
        job.status = StatusUploadJob.FALHOU
        job.erro = f"Falha ao consolidar o arquivo no storage: {exc}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível concluir o upload das partes: {exc}",
        ) from exc

    if job.modo_processamento == ModoProcessamentoUpload.AGENDADO:
        hora_utc = get_settings().publicacoes_processamento_hora_utc
        job.status = StatusUploadJob.AGUARDANDO_PROCESSAMENTO
        job.etapa = f"Upload concluído. Processamento agendado para ~{hora_utc}h UTC."
        job.progresso_pct = 5
        await db.commit()
    else:
        try:
            await service.disparar_worker_processamento(db, job)
        except service.DisparoWorkerError as exc:
            logger.error("Falha ao disparar subprocesso worker para job %s: %s", job_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao iniciar o processo de tratamento da publicação no servidor.",
            ) from exc

    return schemas.UploadJobOut.model_validate(job)


@router.post(
    "/api/edicoes/uploads/{job_id}/cancelar",
    response_model=schemas.UploadJobOut,
    summary="Cancelar upload/processamento de edição",
)
async def cancelar_upload_edicao(
    job_id: uuid.UUID,
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
) -> schemas.UploadJobOut:
    from sqlalchemy import select
    from app.modules.publicacoes.models import PublicacoesUploadJob
    job = (
        await db.execute(select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job de upload não encontrado.")

    if job.status not in (
        StatusUploadJob.ENVIANDO,
        StatusUploadJob.AGUARDANDO_PROCESSAMENTO,
        StatusUploadJob.PROCESSANDO,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job não pode ser cancelado no status atual ({job.status.value}).",
        )

    storage = get_storage_service()
    if job.status == StatusUploadJob.ENVIANDO:
        try:
            await storage.abortar_multipart(job.file_key, job.upload_id_r2 or "")
        except Exception as exc:
            logger.warning("Falha ao abortar multipart para job cancelado %s: %s", job_id, exc)
    elif job.status == StatusUploadJob.AGUARDANDO_PROCESSAMENTO:
        # O multipart já foi concluído (arquivo consolidado no storage) —
        # abortar_multipart não se aplica mais aqui, é preciso apagar o
        # objeto já fechado para não deixar lixo de 3+ GB no storage.
        try:
            await storage.delete(job.file_key)
        except Exception as exc:
            logger.warning("Falha ao apagar arquivo do job cancelado %s: %s", job_id, exc)

    if job.status == StatusUploadJob.PROCESSANDO and job.processo_pid:
        import os, signal
        try:
            os.kill(job.processo_pid, signal.SIGTERM)
        except OSError:
            pass

    job.status = StatusUploadJob.CANCELADO
    job.etapa = "Cancelado pelo usuário"
    await db.commit()
    return schemas.UploadJobOut.model_validate(job)


@router.get(
    "/api/edicoes/uploads/{job_id}",
    response_model=schemas.UploadJobOut,
    summary="Consultar status de um job de upload",
)
async def obter_upload_job(
    job_id: uuid.UUID,
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
) -> schemas.UploadJobOut:
    from sqlalchemy import select
    from app.modules.publicacoes.models import PublicacoesUploadJob
    job = (
        await db.execute(select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job de upload não encontrado.")
    return schemas.UploadJobOut.model_validate(job)


@router.get(
    "/api/edicoes/uploads",
    response_model=list[schemas.UploadJobOut],
    summary="Listar últimos jobs de upload",
)
async def listar_upload_jobs(
    db: DBSession,
    usuario_atual: InspetorOuAdmin,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[schemas.UploadJobOut]:
    from sqlalchemy import select
    from app.modules.publicacoes.models import PublicacoesUploadJob
    jobs = (
        await db.execute(
            select(PublicacoesUploadJob)
            .order_by(PublicacoesUploadJob.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [schemas.UploadJobOut.model_validate(j) for j in jobs]

