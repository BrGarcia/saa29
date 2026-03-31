"""
app/equipamentos/router.py
Endpoints de gestão de equipamentos, itens e controle de vencimentos.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.equipamentos import schemas, service
from app.dependencies import DBSession, CurrentUser, EncarregadoOuAdmin

router = APIRouter()


# ---- Tipos de Controle ----

@router.get(
    "/tipos-controle",
    response_model=list[schemas.TipoControleOut],
    summary="Listar tipos de controle",
)
async def listar_tipos_controle(db: DBSession, _: CurrentUser):
    tipos = await service.listar_tipos_controle(db)
    return [schemas.TipoControleOut.model_validate(t) for t in tipos]


@router.post(
    "/tipos-controle",
    response_model=schemas.TipoControleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tipo de controle",
)
async def criar_tipo_controle(
    dados: schemas.TipoControleCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        tipo = await service.criar_tipo_controle(db, dados)
        return schemas.TipoControleOut.model_validate(tipo)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---- Equipamentos (Tipos / Part Numbers) ----

@router.get("/", response_model=list[schemas.EquipamentoOut], summary="Listar equipamentos")
async def listar_equipamentos(db: DBSession, _: CurrentUser):
    equipamentos = await service.listar_equipamentos(db)
    return [schemas.EquipamentoOut.model_validate(e) for e in equipamentos]


@router.post(
    "/",
    response_model=schemas.EquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar equipamento",
)
async def criar_equipamento(
    dados: schemas.EquipamentoCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        equipamento = await service.criar_equipamento(db, dados)
        return schemas.EquipamentoOut.model_validate(equipamento)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{equipamento_id}", response_model=schemas.EquipamentoOut)
async def buscar_equipamento(
    equipamento_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    equipamento = await service.buscar_equipamento(db, equipamento_id)
    if not equipamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipamento não encontrado.",
        )
    return schemas.EquipamentoOut.model_validate(equipamento)


@router.post(
    "/{equipamento_id}/controles/{tipo_controle_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Associar tipo de controle a equipamento",
)
async def associar_controle(
    equipamento_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    """
    Associa um TipoControle ao Equipamento e propaga
    automaticamente para todos os itens existentes.
    """
    try:
        await service.associar_controle_a_equipamento(
            db, equipamento_id, tipo_controle_id
        )
        return {"detail": "Controle associado com sucesso."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# ---- Itens (Serial Number) ----

@router.get("/itens/", response_model=list[schemas.ItemEquipamentoOut], summary="Listar itens")
async def listar_itens(
    db: DBSession,
    _: CurrentUser,
    equipamento_id: uuid.UUID | None = None,
):
    itens = await service.listar_itens(db, equipamento_id)
    return [schemas.ItemEquipamentoOut.model_validate(i) for i in itens]


@router.post(
    "/itens/",
    response_model=schemas.ItemEquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar item (herda controles do equipamento)",
)
async def criar_item(
    dados: schemas.ItemEquipamentoCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        item = await service.criar_item_com_heranca(db, dados)
        return schemas.ItemEquipamentoOut.model_validate(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/itens/{item_id}/controles",
    response_model=list[schemas.ControleVencimentoOut],
    summary="Listar controles de um item",
)
async def listar_controles_item(
    item_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    vencimentos = await service.listar_vencimentos_por_item(db, item_id)
    return [schemas.ControleVencimentoOut.model_validate(v) for v in vencimentos]


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
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        instalacao = await service.instalar_item(
            db, item_id, dados.aeronave_id, dados.data_instalacao
        )
        return schemas.InstalacaoOut.model_validate(instalacao)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/instalacoes/{instalacao_id}/remover",
    response_model=schemas.InstalacaoOut,
    summary="Registrar remoção de item",
)
async def remover_item(
    instalacao_id: uuid.UUID,
    dados: schemas.InstalacaoRemocao,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        instalacao = await service.remover_item(db, instalacao_id, dados.data_remocao)
        return schemas.InstalacaoOut.model_validate(instalacao)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---- Controles de Vencimento ----

@router.patch(
    "/vencimentos/{vencimento_id}/executar",
    response_model=schemas.ControleVencimentoOut,
    summary="Registrar execução de controle de vencimento",
)
async def registrar_execucao(
    vencimento_id: uuid.UUID,
    dados: schemas.ControleVencimentoUpdate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        vencimento = await service.registrar_execucao(
            db, vencimento_id, dados.data_ultima_exec
        )
        return schemas.ControleVencimentoOut.model_validate(vencimento)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
