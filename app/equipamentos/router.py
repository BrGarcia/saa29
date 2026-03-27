"""
app/equipamentos/router.py
Endpoints de gestão de equipamentos, itens e controle de vencimentos.
"""

import uuid

from fastapi import APIRouter, Depends, status

from app.equipamentos import schemas, service
from app.dependencies import DBSession, CurrentUser

router = APIRouter()


# ---- Tipos de Controle ----

@router.get(
    "/tipos-controle",
    response_model=list[schemas.TipoControleOut],
    summary="Listar tipos de controle",
)
async def listar_tipos_controle(db: DBSession = Depends(), _: CurrentUser = Depends()):
    # TODO (Dia 4)
    raise NotImplementedError


@router.post(
    "/tipos-controle",
    response_model=schemas.TipoControleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tipo de controle",
)
async def criar_tipo_controle(
    dados: schemas.TipoControleCreate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


# ---- Equipamentos (Tipos / Part Numbers) ----

@router.get("/", response_model=list[schemas.EquipamentoOut], summary="Listar equipamentos")
async def listar_equipamentos(db: DBSession = Depends(), _: CurrentUser = Depends()):
    # TODO (Dia 4)
    raise NotImplementedError


@router.post(
    "/",
    response_model=schemas.EquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar equipamento",
)
async def criar_equipamento(
    dados: schemas.EquipamentoCreate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


@router.get("/{equipamento_id}", response_model=schemas.EquipamentoOut)
async def buscar_equipamento(
    equipamento_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


@router.post(
    "/{equipamento_id}/controles/{tipo_controle_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Associar tipo de controle a equipamento",
)
async def associar_controle(
    equipamento_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    """
    Associa um TipoControle ao Equipamento e propaga
    automaticamente para todos os itens existentes.
    """
    # TODO (Dia 4)
    raise NotImplementedError


# ---- Itens (Serial Number) ----

@router.get("/itens", response_model=list[schemas.ItemEquipamentoOut], summary="Listar itens")
async def listar_itens(
    equipamento_id: uuid.UUID | None = None,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


@router.post(
    "/itens",
    response_model=schemas.ItemEquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar item (herda controles do equipamento)",
)
async def criar_item(
    dados: schemas.ItemEquipamentoCreate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


# ---- Instalações ----

@router.post(
    "/itens/{item_id}/instalar",
    response_model=schemas.InstalacaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Instalar item em aeronave",
)
async def instalar_item(
    item_id: uuid.UUID,
    dados: schemas.InstalacaoCreate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


@router.patch(
    "/instalacoes/{instalacao_id}/remover",
    response_model=schemas.InstalacaoOut,
    summary="Registrar remoção de item",
)
async def remover_item(
    instalacao_id: uuid.UUID,
    dados: schemas.InstalacaoRemocao,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError


# ---- Controles de Vencimento ----

@router.patch(
    "/vencimentos/{vencimento_id}/executar",
    response_model=schemas.ControleVencimentoOut,
    summary="Registrar execução de controle de vencimento",
)
async def registrar_execucao(
    vencimento_id: uuid.UUID,
    dados: schemas.ControleVencimentoUpdate,
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
):
    # TODO (Dia 4)
    raise NotImplementedError
