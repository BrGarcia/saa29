"""
app/panes/service.py
Camada de serviço para gestão de panes aeronáuticas.
"""

import os
import uuid
from datetime import datetime, timezone

import anyio
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.panes.models import Pane, Anexo, PaneResponsavel
from app.panes.schemas import PaneCreate, PaneUpdate, FiltroPane, AdicionarResponsavel
from app.core.enums import StatusPane
from app.config import get_settings


# Transições de status permitidas (SPECS §8)
_TRANSICOES_VALIDAS = {
    StatusPane.ABERTA: {StatusPane.EM_PESQUISA, StatusPane.RESOLVIDA},
    StatusPane.EM_PESQUISA: {StatusPane.RESOLVIDA},
    StatusPane.RESOLVIDA: set(),  # Pane resolvida não pode transicionar
}

# Extensões permitidas para upload
_EXTENSOES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".pdf"}


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
    
    # Garantir que as coleções estejam inicializadas para evitar erro de lazy-load no router
    await db.refresh(pane, ["anexos", "responsaveis"])
    
    return pane


async def listar_panes(db: AsyncSession, filtros: FiltroPane | None = None) -> list[Pane]:
    """
    Lista panes com filtros opcionais (RF-06).

    Algoritmo (SPECS §10 – Filtrar Panes):
        1. Receber parâmetros: texto, status, aeronave, data
        2. Construir query dinâmica com AND condicional
        3. Executar busca ordenada por data_abertura DESC

    Args:
        db: sessão de banco de dados.
        filtros: schema com os filtros a aplicar.

    Returns:
        Lista de Panes filtradas.
    """
    query = select(Pane).order_by(Pane.data_abertura.desc())

    if filtros:
        if filtros.status:
            query = query.where(Pane.status == filtros.status.value)

        if filtros.aeronave_id:
            query = query.where(Pane.aeronave_id == filtros.aeronave_id)

        if filtros.texto:
            texto_like = f"%{filtros.texto}%"
            query = query.where(
                or_(
                    Pane.descricao.ilike(texto_like),
                    Pane.sistema_subsistema.ilike(texto_like),
                )
            )

        if filtros.data_inicio:
            query = query.where(Pane.data_abertura >= filtros.data_inicio)

        if filtros.data_fim:
            query = query.where(Pane.data_abertura <= filtros.data_fim)
            
        if filtros.excluidas:
            query = query.where(Pane.ativo == False)
        else:
            query = query.where(Pane.ativo == True)

        query = query.offset(filtros.skip).limit(filtros.limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane | None:
    """
    Busca uma pane pelo ID com seus anexos e responsáveis carregados.

    Returns:
        Objeto Pane com relacionamentos ou None.
    """
    result = await db.execute(
        select(Pane)
        .where(Pane.id == pane_id)
        .options(
            selectinload(Pane.anexos),
            selectinload(Pane.responsaveis),
            selectinload(Pane.aeronave),
            selectinload(Pane.criador),
            selectinload(Pane.responsavel_conclusao),
        )
    )
    return result.scalar_one_or_none()


async def editar_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    dados: PaneUpdate,
) -> Pane:
    """
    Edita descrição e/ou status de uma pane.

    RN-03: Apenas panes com status ABERTA ou EM_PESQUISA podem ser editadas.
    Validar transições de status permitidas (SPECS §8):
        ABERTA → EM_PESQUISA ✓
        ABERTA → RESOLVIDA ✓
        EM_PESQUISA → RESOLVIDA ✓
        RESOLVIDA → qualquer ✗

    Raises:
        ValueError: se a pane já estiver resolvida ou transição inválida.
    """
    pane = await buscar_pane(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")

    status_atual = StatusPane(pane.status)

    # RN-03: Pane resolvida não pode ser editada
    if status_atual == StatusPane.RESOLVIDA:
        raise ValueError("Pane já resolvida. Não é possível editar.")

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

        # Se transicionou para RESOLVIDA, preencher data_conclusao
        if novo_status == StatusPane.RESOLVIDA:
            pane.data_conclusao = datetime.now(timezone.utc)

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
    pane = await buscar_pane(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")

    if StatusPane(pane.status) == StatusPane.RESOLVIDA:
        raise ValueError("Pane já está resolvida.")

    pane.status = StatusPane.RESOLVIDA.value
    pane.data_conclusao = datetime.now(timezone.utc)
    pane.concluido_por_id = concluido_por_id
    pane.observacao_conclusao = observacao_conclusao

    await db.flush()
    return pane


async def excluir_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane:
    """Realiza Soft Delete inativando a pane."""
    pane = await buscar_pane(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")
    pane.ativo = False
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
    pane = await buscar_pane(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")

    # Validar extensão
    nome_original = nome_original or "arquivo"
    extensao = os.path.splitext(nome_original)[1].lower()
    if extensao not in _EXTENSOES_PERMITIDAS:
        raise ValueError(
            f"Tipo de arquivo não permitido: '{extensao}'. "
            f"Permitidos: {_EXTENSOES_PERMITIDAS}"
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
    pane = await buscar_pane(db, pane_id)
    if not pane:
        raise ValueError("Pane não encontrada.")

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
    return responsavel
