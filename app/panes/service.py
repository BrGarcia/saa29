"""
app/panes/service.py
Camada de serviço para gestão de panes aeronáuticas.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anyio
try:
    import magic
    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.panes.models import Pane, Anexo, PaneResponsavel
from app.panes.schemas import PaneCreate, PaneUpdate, FiltroPane, AdicionarResponsavel
from app.core.enums import StatusPane
from app.config import get_settings


# Transições de status permitidas (SPECS §8)
_TRANSICOES_VALIDAS = {
    StatusPane.ABERTA: {StatusPane.RESOLVIDA},
    StatusPane.RESOLVIDA: set(),  # Pane resolvida não pode transicionar
}

# Extensões permitidas para upload
_EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf"}

# MIME types reais permitidos (SEC-05: validação por conteúdo, não só extensão)
_MIMES_PERMITIDOS = {"image/jpeg", "image/png", "application/pdf"}


def _escape_like(text: str) -> str:
    """Escapa caracteres especiais de LIKE para evitar pattern matching indesejado (SEC-07)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _get_ranking_subquery():
    """Retorna a subquery de ranking para cálculo do código ddd/yy."""
    return select(
        Pane.id.label("pane_id"),
        func.row_number().over(
            partition_by=func.extract("year", Pane.data_abertura),
            order_by=(Pane.data_abertura.asc(), Pane.id.asc()),
        ).label("sequencia"),
        func.extract("year", Pane.data_abertura).label("ano"),
    ).subquery()


async def criar_pane(
    db: AsyncSession,
    dados: PaneCreate,
    criado_por_id: uuid.UUID,
) -> Pane:
    """
    Abre uma nova pane no sistema.

    Algoritmo (SPECS §3 – Nova Pane):
        1. Validar se a aeronave existe
        2. Definir status = ABERTA (RN-02)
        3. Definir descricao = "AGUARDANDO EDICAO" se vazia (RN-05)
        4. Definir data_abertura = NOW() automático
        5. Vincular criado_por = usuário logado
        6. Salvar no banco

    Args:
        db: sessão de banco de dados.
        dados: schema com dados da pane.
        criado_por_id: UUID do usuário autenticado.

    Returns:
        Objeto Pane recém-criado.
    """
    # Validar existência da aeronave
    from app.aeronaves.service import buscar_aeronave
    aeronave = await buscar_aeronave(db, dados.aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    if aeronave.status == "INATIVA":
        raise ValueError("Aeronave inativa. Reative a aeronave antes de registrar uma pane.")

    # RN-05: descrição padrão se vazia
    descricao = dados.descricao.strip() if dados.descricao else ""
    if not descricao:
        descricao = "AGUARDANDO EDICAO"

    pane = Pane(
        aeronave_id=dados.aeronave_id,
        status=StatusPane.ABERTA.value,
        sistema_subsistema=dados.sistema_subsistema,
        descricao=descricao,
        criado_por_id=criado_por_id,
    )
    db.add(pane)
    await db.flush()

    if dados.mantenedor_responsavel_id:
        from app.auth.service import buscar_por_id
        usuario_responsavel = await buscar_por_id(db, dados.mantenedor_responsavel_id)
        if not usuario_responsavel:
            raise ValueError("Mantenedor responsável não encontrado.")
        if usuario_responsavel.funcao not in ["MANTENEDOR", "ENCARREGADO"]:
            raise ValueError("O responsável selecionado deve ser um mantenedor ou encarregado.")

        resp = PaneResponsavel(
            pane_id=pane.id,
            usuario_id=usuario_responsavel.id,
            papel=usuario_responsavel.funcao,
        )
        db.add(resp)
        await db.flush()
        # Importante: Carregar o usuário para que o trigrama esteja disponível na serialização
        await db.refresh(resp, ["usuario"])
    
    # Garantir que as coleções estejam inicializadas para evitar erro de lazy-load no router
    # Note: refresh(pane, ["responsaveis"]) carregará a lista, e o refresh(resp, ["usuario"]) acima garante o objeto interno
    await db.refresh(pane, ["aeronave", "anexos", "responsaveis"])
    
    return pane


async def listar_panes(
    db: AsyncSession,
    filtros: FiltroPane | None = None,
) -> list[tuple[Pane, int, int]]:
    """
    Lista panes com filtros opcionais (RF-06).

    Algoritmo (SPECS §10 – Filtrar Panes):
        1. Receber parâmetros: texto, status, aeronave, data
        2. Construir query dinâmica com AND condicional
        3. Executar busca ordenada por data_abertura DESC

    COR-01: filtro ativo/inativo é SEMPRE aplicado, mesmo sem filtros.

    Args:
        db: sessão de banco de dados.
        filtros: schema com os filtros a aplicar.

    Returns:
        Lista de Panes filtradas.
    """
    ranking_subquery = select(
        Pane.id.label("pane_id"),
        func.row_number().over(
            partition_by=func.extract("year", Pane.data_abertura),
            order_by=(Pane.data_abertura.asc(), Pane.id.asc()),
        ).label("sequencia"),
        func.extract("year", Pane.data_abertura).label("ano"),
    ).subquery()

    query = (
        select(Pane, ranking_subquery.c.sequencia, ranking_subquery.c.ano)
        .join(ranking_subquery, ranking_subquery.c.pane_id == Pane.id)
        .order_by(Pane.data_abertura.desc())
    )

    # COR-01: sempre filtrar por ativo, exceto se explicitamente pedido
    mostrar_excluidas = filtros.excluidas if filtros else False
    if mostrar_excluidas:
        query = query.where(Pane.ativo == False)  # noqa: E712
    else:
        query = query.where(Pane.ativo == True)  # noqa: E712

    if filtros:
        if filtros.status:
            query = query.where(Pane.status == filtros.status.value)

        if filtros.aeronave_id:
            query = query.where(Pane.aeronave_id == filtros.aeronave_id)

        if filtros.texto:
            from app.aeronaves.models import Aeronave
            texto_like = f"%{_escape_like(filtros.texto)}%"
            query = query.outerjoin(Aeronave, Pane.aeronave_id == Aeronave.id).where(
                or_(
                    Pane.descricao.ilike(texto_like),
                    Pane.sistema_subsistema.ilike(texto_like),
                    Aeronave.matricula.ilike(texto_like),
                )
            )

        if filtros.data_inicio:
            query = query.where(Pane.data_abertura >= filtros.data_inicio)

        if filtros.data_fim:
            query = query.where(Pane.data_abertura <= filtros.data_fim)

        query = query.offset(filtros.skip).limit(filtros.limit)
    else:
        # AUD-14: Garante que nunca retorne todos os registros sem limite
        query = query.limit(100)

    # Eager-load aeronave para exibir matricula no frontend e responsaveis para o dashboard
    query = query.options(
        selectinload(Pane.aeronave),
        selectinload(Pane.criador),
        selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario)
    )

    result = await db.execute(query)
    return [
        (row[0], int(row[1]), int(row[2]))
        for row in result.all()
    ]


async def buscar_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> tuple[Pane, int, int] | None:
    """
    Busca uma pane pelo ID com seus anexos e responsáveis carregados.
    Também calcula sequencia e ano para o código ddd/yy.

    Args:
        db: sessão de banco de dados.
        pane_id: UUID da pane.
        incluir_inativos: se True, inclui panes soft-deleted.

    Returns:
        Tupla (Pane, sequencia, ano) ou None.
    """
    ranking_sub = await _get_ranking_subquery()

    query = (
        select(Pane, ranking_sub.c.sequencia, ranking_sub.c.ano)
        .join(ranking_sub, ranking_sub.c.pane_id == Pane.id)
        .where(Pane.id == pane_id)
        .options(
            selectinload(Pane.anexos),
            selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario),
            selectinload(Pane.aeronave),
            selectinload(Pane.criador),
            selectinload(Pane.responsavel_conclusao),
        )
    )
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)  # noqa: E712
    
    result = await db.execute(query)
    row = result.first()
    if not row:
        return None
    
    return (row[0], int(row[1]), int(row[2]))


async def _buscar_pane_por_id(
    db: AsyncSession,
    pane_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> Pane | None:
    """
    Busca apenas o objeto Pane pelo ID sem ranking (usado em operações de escrita).
    """
    query = (
        select(Pane)
        .where(Pane.id == pane_id)
        .options(
            selectinload(Pane.anexos),
            selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario),
            selectinload(Pane.aeronave),
            selectinload(Pane.criador),
            selectinload(Pane.responsavel_conclusao),
        )
    )
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)  # noqa: E712
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def editar_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    dados: PaneUpdate,
    usuario_id: uuid.UUID | None = None,
) -> Pane:
    """
    Edita descrição e/ou status de uma pane.

    RN-03: Apenas panes com status ABERTA podem ser editadas.
    Validar transições de status permitidas (SPECS §8):
        ABERTA → RESOLVIDA ✓
        RESOLVIDA → qualquer ✗

    COR-03: Ao transicionar para RESOLVIDA via edição, preenche
    concluido_por_id com o usuário que fez a edição.

    Raises:
        ValueError: se a pane não estiver aberta ou houver transição inválida.
    """
    pane = await _buscar_pane_por_id(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")

    status_atual = StatusPane(pane.status)

    # RN-03: apenas panes abertas podem ser editadas por este fluxo
    if status_atual != StatusPane.ABERTA:
        raise ValueError("Apenas panes abertas podem ser editadas.")

    # Atualizar campos
    if dados.descricao is not None:
        pane.descricao = dados.descricao

    if dados.sistema_subsistema is not None:
        pane.sistema_subsistema = dados.sistema_subsistema

    # Validar transição de status
    if dados.status is not None:
        novo_status = dados.status
        transicoes_permitidas = _TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in transicoes_permitidas:
            raise ValueError(
                f"Transição inválida: {status_atual.value} → {novo_status.value}. "
                f"Transições permitidas: {[s.value for s in transicoes_permitidas]}"
            )
        pane.status = novo_status.value

        # COR-03: Se transicionou para RESOLVIDA, preencher rastreabilidade
        if novo_status == StatusPane.RESOLVIDA:
            pane.data_conclusao = datetime.now(timezone.utc)
            pane.concluido_por_id = usuario_id

    await db.flush()
    return pane


async def concluir_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    concluido_por_id: uuid.UUID,
    observacao_conclusao: str | None = None
) -> Pane:
    """
    Conclui uma pane e armazena a acao corretiva.

    Algoritmo (SPECS §7 – Concluir Pane):
        1. Verificar se já está RESOLVIDA
        2. status = RESOLVIDA
        3. data_conclusao = NOW() (RN-04)
        4. concluido_por = usuário logado
        5. Salvar alterações

    Raises:
        ValueError: se a pane já estiver resolvida.
    """
    resultado = await _buscar_pane_por_id(db, pane_id)
    if not resultado:
        raise ValueError("Pane não encontrada.")

    pane = resultado
    if StatusPane(pane.status) == StatusPane.RESOLVIDA:
        raise ValueError("Pane já está resolvida.")

    pane.status = StatusPane.RESOLVIDA.value
    pane.data_conclusao = datetime.now(timezone.utc)
    pane.concluido_por_id = concluido_por_id
    pane.observacao_conclusao = observacao_conclusao

    # RN: Se o usuário que concluiu não é um dos responsáveis, adicioná-lo.
    # Isso garante que ele apareça na listagem de panes como responsável.
    await db.refresh(pane, ["responsaveis"])
    ja_responsavel = any(r.usuario_id == concluido_por_id for r in pane.responsaveis)
    
    if not ja_responsavel:
        from app.auth.service import buscar_por_id
        usuario = await buscar_por_id(db, concluido_por_id)
        if usuario:
            resp = PaneResponsavel(
                pane_id=pane_id,
                usuario_id=concluido_por_id,
                papel=usuario.funcao,
            )
            db.add(resp)
            await db.flush()
            await db.refresh(resp, ["usuario"])

    await db.flush()
    await db.refresh(pane, ["aeronave", "anexos", "responsaveis", "responsavel_conclusao"])
    return pane


async def excluir_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane:
    """
    Realiza Soft Delete inativando a pane.

    COR-02: Verifica idempotência (pane já inativa).
    """
    resultado = await _buscar_pane_por_id(db, pane_id, incluir_inativos=True)
    if not resultado:
        raise ValueError("Pane não encontrada.")
    
    pane = resultado
    if not pane.ativo:
        raise ValueError("Pane já está inativa.")
    pane.ativo = False
    await db.flush()
    return pane


async def restaurar_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane:
    """
    Restaura uma pane que foi inativada via Soft Delete.
    """
    resultado = await _buscar_pane_por_id(db, pane_id, incluir_inativos=True)
    if not resultado:
        raise ValueError("Pane não encontrada.")
    
    pane = resultado
    if pane.ativo:
        raise ValueError("Pane já está ativa.")
    pane.ativo = True
    await db.flush()
    return pane


async def upload_anexo(
    db: AsyncSession,
    pane_id: uuid.UUID,
    arquivo_bytes: bytes,
    nome_original: str,
    tipo_mime: str,
) -> Anexo:
    """
    Faz upload e registra um anexo em uma pane.

    Algoritmo (SPECS §6 – Upload):
        1. Validar tipo (jpg, png, pdf)
        2. Validar tamanho (< MAX_UPLOAD_SIZE_MB)
        3. Gerar nome único (UUID + extensão)
        4. Armazenar no diretório de uploads
        5. Criar registro em anexos

    Raises:
        ValueError: se tipo ou tamanho inválidos.
    """
    settings = get_settings()
    resultado = await _buscar_pane_por_id(db, pane_id)
    if not resultado:
        raise ValueError("Pane não encontrada.")

    pane = resultado
    # Validar extensão
    nome_original = nome_original or "arquivo"
    extensao = os.path.splitext(nome_original)[1].lower()
    if extensao not in _EXTENSOES_PERMITIDAS:
        raise ValueError(
            f"Tipo de arquivo não permitido: '{extensao}'. "
            f"Permitidos: {_EXTENSOES_PERMITIDAS}"
        )

    # SEC-05: Validar MIME type real do conteúdo (não confiar na extensão) (AUD-09)
    if not _MAGIC_AVAILABLE:
        raise ValueError("Validação de tipo de arquivo indisponível (python-magic ausente). Contacte o administrador.")

    mime_real = magic.from_buffer(arquivo_bytes[:2048], mime=True)
    if mime_real not in _MIMES_PERMITIDOS:
        raise ValueError(
            f"Conteúdo real do arquivo ({mime_real}) não é um tipo permitido. "
            f"Permitidos: {_MIMES_PERMITIDOS}"
        )

    # Validar tamanho
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(arquivo_bytes) > max_bytes:
        raise ValueError(
            f"Arquivo excede o tamanho máximo de {settings.max_upload_size_mb} MB."
        )

    # Determinar tipo do anexo
    from app.core.enums import TipoAnexo
    tipo_anexo = TipoAnexo.IMAGEM if extensao in {".jpg", ".jpeg", ".png"} else TipoAnexo.DOCUMENTO

    # Gerar nome único e salvar arquivo de forma não bloqueante
    nome_unico = f"{uuid.uuid4()}{extensao}"
    caminho = os.path.join(settings.upload_dir, nome_unico)

    def _salvar_arquivo():
        os.makedirs(settings.upload_dir, exist_ok=True)
        with open(caminho, "wb") as f:
            f.write(arquivo_bytes)

    await anyio.to_thread.run_sync(_salvar_arquivo)

    # Criar registro no banco
    anexo = Anexo(
        pane_id=pane_id,
        caminho_arquivo=nome_unico,
        tipo=tipo_anexo.value,
    )
    db.add(anexo)
    await db.flush()
    return anexo


async def listar_anexos(db: AsyncSession, pane_id: uuid.UUID) -> list[Anexo]:
    """Lista todos os anexos de uma pane."""
    result = await db.execute(
        select(Anexo).where(Anexo.pane_id == pane_id).order_by(Anexo.created_at)
    )
    return list(result.scalars().all())


async def buscar_anexo(
    db: AsyncSession,
    pane_id: uuid.UUID,
    anexo_id: uuid.UUID,
) -> Anexo | None:
    """Busca um anexo de uma pane ativa."""
    result = await db.execute(
        select(Anexo)
        .join(Pane, Pane.id == Anexo.pane_id)
        .where(
            Anexo.id == anexo_id,
            Anexo.pane_id == pane_id,
            Pane.ativo == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


def resolver_caminho_anexo(caminho_relativo: str) -> Path:
    """
    Resolve o caminho físico do anexo garantindo permanência dentro de upload_dir.
    """
    settings = get_settings()
    base_dir = Path(settings.upload_dir).resolve()
    arquivo = base_dir / Path(caminho_relativo).name
    arquivo = arquivo.resolve()
    if arquivo.parent != base_dir:
        raise ValueError("Caminho de anexo inválido.")
    return arquivo


async def adicionar_responsavel(
    db: AsyncSession,
    pane_id: uuid.UUID,
    dados: AdicionarResponsavel,
) -> PaneResponsavel:
    """
    Vincula um responsável a uma pane com papel definido.

    Raises:
        ValueError: se usuário já for responsável por esta pane.
    """
    resultado = await _buscar_pane_por_id(db, pane_id)
    if not resultado:
        raise ValueError("Pane não encontrada.")

    pane = resultado

    # Verificar duplicidade
    result = await db.execute(
        select(PaneResponsavel).where(
            PaneResponsavel.pane_id == pane_id,
            PaneResponsavel.usuario_id == dados.usuario_id,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Usuário já é responsável por esta pane.")

    responsavel = PaneResponsavel(
        pane_id=pane_id,
        usuario_id=dados.usuario_id,
        papel=dados.papel.value,
    )
    db.add(responsavel)
    await db.flush()
    
    # Refresh 'usuario' para garantir que o trigrama esteja carregado para o schema Pydantic
    await db.refresh(responsavel, ["usuario"])
    
    return responsavel
