"""
app/equipamentos/router.py
Endpoints de gestão de equipamentos, itens e controle de vencimentos.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.modules.equipamentos import schemas, service
from app.bootstrap.dependencies import DBSession, CurrentUser, EncarregadoOuAdmin

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

@router.get("/", response_model=list[schemas.ModeloEquipamentoOut], summary="Listar equipamentos")
async def listar_equipamentos(db: DBSession, _: CurrentUser):
    equipamentos = await service.listar_modelos(db)
    return [schemas.ModeloEquipamentoOut.model_validate(e) for e in equipamentos]


@router.post(
    "/",
    response_model=schemas.ModeloEquipamentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar equipamento",
)
async def criar_equipamento(
    dados: schemas.ModeloEquipamentoCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        equipamento = await service.criar_modelo(db, dados)
        return schemas.ModeloEquipamentoOut.model_validate(equipamento)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{equipamento_id}", response_model=schemas.ModeloEquipamentoOut)
async def buscar_equipamento(
    equipamento_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
):
    # Nota: No service.py atual só existe buscar_modelo_por_pn. 
    # Vou assumir que precisamos de um buscar_modelo genérico ou usar ModeloEquipamento diretamente se simples.
    # Por enquanto, mantendo a estrutura mas corrigindo o schema.
    from app.modules.equipamentos.models import ModeloEquipamento
    from sqlalchemy import select
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.id == equipamento_id))
    equipamento = result.scalar_one_or_none()
    
    if not equipamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipamento não encontrado.",
        )
    return schemas.ModeloEquipamentoOut.model_validate(equipamento)


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


# ---- Slots de Inventário (Posições na ANV) ----

@router.get(
    "/slots/",
    response_model=list[schemas.SlotInventarioOut],
    summary="Listar todos os slots configurados",
)
async def listar_slots(db: DBSession, _: CurrentUser):
    from app.modules.equipamentos.models import SlotInventario
    from sqlalchemy import select
    result = await db.execute(select(SlotInventario))
    return [schemas.SlotInventarioOut.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/slots/",
    response_model=schemas.SlotInventarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Configurar novo slot/posição",
)
async def criar_slot(
    dados: schemas.SlotInventarioCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        slot = await service.criar_slot(db, dados)
        await db.commit()
        return schemas.SlotInventarioOut.model_validate(slot)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
    instalacao = await service.instalar_item(
        db, item_id, dados.aeronave_id, dados.data_instalacao
    )
    return schemas.InstalacaoOut.model_validate(instalacao)


@router.patch(
    "/instalacoes/{instalacao_id}/remover",
    response_model=schemas.InstalacaoOut,
    summary="Registrar remoção de item",
)
async def remover_item(
    instalacao_id: uuid.UUID,
    dados: schemas.InstalacaoRemocao,
    db: DBSession,
    current_user: EncarregadoOuAdmin,
):
    instalacao = await service.remover_item(
        db, instalacao_id, dados.data_remocao, usuario_id=current_user.id
    )
    return schemas.InstalacaoOut.model_validate(instalacao)


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
    vencimento = await service.registrar_execucao(
        db, vencimento_id, dados.data_ultima_exec
    )
    return schemas.ControleVencimentoOut.model_validate(vencimento)

# ---- Inventário ----

@router.get(
    "/inventario/historico",
    response_model=list[schemas.InventarioHistoricoOut],
    summary="Listar últimas alterações no inventário",
)
async def listar_historico_inventario(
    db: DBSession, 
    _: CurrentUser,
    limit: int = 15,
    offset: int = 0
):
    """Retorna as últimas movimentações de equipamentos com paginação."""
    return await service.listar_historico_recente(db, limit=limit, offset=offset)


@router.get(
    "/inventario/{aeronave_id}",
    response_model=list[schemas.InventarioItemOut],
    summary="Listar inventário da aeronave",
)
async def listar_inventario(
    aeronave_id: uuid.UUID,
    db: DBSession,
    _: CurrentUser,
    nome: str | None = None,
):
    """Retorna inventário de itens instalados na aeronave.
    Aceita filtro opcional por nome de equipamento (?nome=...).
    """
    return await service.listar_inventario_aeronave(db, aeronave_id, nome=nome)


@router.post(
    "/inventario/ajuste",
    response_model=schemas.AjusteInventarioResponse,
    summary="Ajustar (sincronizar) S/N de uma aeronave/equipamento",
)
async def ajustar_inventario(
    dados: schemas.AjusteInventarioCreate,
    db: DBSession,
    _: CurrentUser,
):
    """
    Ajusta o número de série físico de um equipamento.
    Lida com transferências e criação de novos itens.
    """
    return await service.ajustar_inventario_item(db, dados)

