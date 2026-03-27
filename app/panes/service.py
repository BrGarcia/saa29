"""
app/panes/service.py
Camada de serviço para gestão de panes aeronáuticas.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.panes.models import Pane, Anexo, PaneResponsavel
from app.panes.schemas import PaneCreate, PaneUpdate, FiltroPane, AdicionarResponsavel
from app.core.enums import StatusPane


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
    # TODO (Dia 4)
    raise NotImplementedError


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
    # TODO (Dia 4)
    raise NotImplementedError


async def buscar_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane | None:
    """
    Busca uma pane pelo ID com seus anexos e responsáveis carregados.

    Returns:
        Objeto Pane com relacionamentos ou None.
    """
    # TODO (Dia 4)
    raise NotImplementedError


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
    # TODO (Dia 4)
    raise NotImplementedError


async def concluir_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    concluido_por_id: uuid.UUID,
) -> Pane:
    """
    Conclui uma pane.

    Algoritmo (SPECS §7 – Concluir Pane):
        1. Verificar se já está RESOLVIDA
        2. status = RESOLVIDA
        3. data_conclusao = NOW() (RN-04)
        4. concluido_por = usuário logado
        5. Salvar alterações

    Raises:
        ValueError: se a pane já estiver resolvida.
    """
    # TODO (Dia 4)
    raise NotImplementedError


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
    # TODO (Dia 4)
    raise NotImplementedError


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
    # TODO (Dia 4)
    raise NotImplementedError
