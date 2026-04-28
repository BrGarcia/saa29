"""
app/modules/vencimentos/router.py
Endpoints para a inteligência temporal de manutenções e vencimentos.
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from app.modules.vencimentos import schemas, service
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

@router.put(
    "/tipos-controle/{tipo_id}",
    response_model=schemas.TipoControleOut,
    summary="Atualizar tipo de controle",
)
async def atualizar_tipo_controle(
    tipo_id: uuid.UUID,
    dados: schemas.TipoControleUpdate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        tipo = await service.atualizar_tipo_controle(db, tipo_id, dados)
        return schemas.TipoControleOut.model_validate(tipo)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

# ---- Regras de Periodicidade (EquipamentoControle) ----

@router.get(
    "/regras",
    response_model=list[schemas.EquipamentoControleOut],
    summary="Listar todas as regras de periodicidade por equipamento",
)
async def listar_regras_periodicidade(db: DBSession, _: CurrentUser):
    regras = await service.listar_equipamento_controles(db)
    out = []
    for r in regras:
        item = schemas.EquipamentoControleOut.model_validate(r)
        item.pn = r.modelo.part_number
        item.tipo_nome = r.tipo_controle.nome
        out.append(item)
    return out

@router.post(
    "/regras",
    response_model=schemas.EquipamentoControleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Associar tipo de controle a equipamento com periodicidade",
)
async def associar_controle(
    dados: schemas.EquipamentoControleCreate,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    try:
        assoc = await service.associar_controle_a_equipamento(
            db, dados.modelo_id, dados.tipo_controle_id, dados.periodicidade_meses
        )
        # O commit é feito automaticamente pela dependência get_db ao final do request
        return schemas.EquipamentoControleOut.model_validate(assoc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.delete(
    "/regras/{modelo_id}/{tipo_controle_id}",
    summary="Remover regra de periodicidade",
)
async def remover_regra(
    modelo_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    await service.remover_controle_de_equipamento(db, modelo_id, tipo_controle_id)
    return {"success": True, "message": "Regra removida"}

# ---- Vencimentos ----

@router.get(
    "/itens/{item_id}",
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

@router.patch(
    "/{vencimento_id}/executar",
    response_model=schemas.ControleVencimentoOut,
    summary="Registrar execução de controle de vencimento",
)
async def registrar_execucao(
    vencimento_id: uuid.UUID,
    dados: schemas.ControleVencimentoUpdate,
    db: DBSession,
    current_user: EncarregadoOuAdmin,
):
    vencimento = await service.registrar_execucao(
        db, vencimento_id, dados.data_ultima_exec, current_user.id
    )
    return schemas.ControleVencimentoOut.model_validate(vencimento)

@router.post(
    "/{vencimento_id}/prorrogar",
    response_model=schemas.ProrrogacaoVencimentoOut,
    summary="Conceder prorrogação de prazo (Engenharia)",
)
async def prorrogar_prazo(
    vencimento_id: uuid.UUID,
    dados: schemas.ProrrogacaoVencimentoCreate,
    db: DBSession,
    user: CurrentUser,
):
    prorrogacao = await service.prorrogar_vencimento(db, vencimento_id, dados, user.id)
    return schemas.ProrrogacaoVencimentoOut.model_validate(prorrogacao)

@router.delete(
    "/{vencimento_id}/prorrogar",
    summary="Cancelar prorrogação ativa",
)
async def cancelar_prorrogacao(
    vencimento_id: uuid.UUID,
    db: DBSession,
    _: EncarregadoOuAdmin,
):
    sucesso = await service.cancelar_prorrogacao(db, vencimento_id)
    return {"success": sucesso}

@router.get(
    "/matriz",
    summary="Visão matricial de vencimentos (Frota x Slot x Controle)",
)
async def matriz_vencimentos(db: DBSession, _: CurrentUser):
    return await service.montar_matriz_vencimentos(db)
