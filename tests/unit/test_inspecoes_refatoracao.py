"""
tests/unit/test_inspecoes_refatoracao.py
Testes de regressão para os achados de docs/backlog/Fable5/Etapa3.md
(módulo inspeções):

    #5  Sincronização de status da aeronave delegada a
        panes.service.sincronizar_status_aeronave (elimina duplicação
        entre concluir_inspecao/cancelar_inspecao)
    #13 calcular_progresso usa o enum StatusTarefaInspecao em vez de
        strings mágicas ("CONCLUIDA"/"N/A")

Os itens de média prioridade (#6-#11) que também tocam este módulo (N+1 em
abrir_inspecao, contrato HTTP, paginação) têm cobertura própria adicionada
na fase seguinte deste mesmo arquivo.
"""

import uuid
import pytest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.inspecoes import schemas, service
from app.modules.panes.models import Pane
from app.shared.core.enums import StatusAeronave, StatusPane, StatusTarefaInspecao


async def criar_usuario_teste(db: AsyncSession, funcao: str = "ENCARREGADO") -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Usuario Refac {suffix}",
        posto="Sgt",
        especialidade="ELT",
        funcao=funcao,
        ramal="2500",
        trigrama=suffix[:3].upper(),
        username=f"refac_{funcao.lower()}_{suffix}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def criar_aeronave_teste(db: AsyncSession) -> Aeronave:
    suffix = uuid.uuid4().hex[:8].upper()
    aeronave = Aeronave(
        serial_number=f"SN-REF-{suffix}",
        matricula=f"RF-{suffix[:6]}",
        modelo="A-29",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def criar_tipo_com_tarefas(db: AsyncSession, obrigatorias: int = 1):
    codigo = f"IF-{uuid.uuid4().hex[:6].upper()}"
    tipo = await service.criar_tipo_inspecao(
        db, schemas.TipoInspecaoCreate(codigo=codigo, nome=f"Inspecao {codigo}")
    )
    tarefas = []
    for idx in range(obrigatorias):
        catalogo = await service.criar_tarefa_catalogo(
            db, schemas.TarefaCatalogoCreate(titulo=f"Tarefa {idx + 1}", sistema="AVI", ativa=True)
        )
        tarefa = await service.criar_tarefa_template(
            db, tipo.id,
            schemas.TarefaTemplateCreate(tarefa_catalogo_id=catalogo.id, ordem=idx + 1, obrigatoria=True),
        )
        tarefas.append(tarefa)
    return tipo, tarefas


async def _criar_pane_aberta(db: AsyncSession, aeronave_id: uuid.UUID, criado_por_id: uuid.UUID) -> Pane:
    pane = Pane(
        id=uuid.uuid4(),
        aeronave_id=aeronave_id,
        descricao="Pane de teste (bloqueia disponibilidade)",
        status=StatusPane.ABERTA.value,
        ativo=True,
        data_abertura=datetime.now(timezone.utc),
        criado_por_id=criado_por_id,
    )
    db.add(pane)
    await db.flush()
    return pane


# ------------------------------------------------------------------ #
#  #5 — sincronização de status delegada, cobrindo o ramo antes
#       duplicado (INDISPONIVEL quando há pane aberta remanescente)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_concluir_inspecao_com_pane_aberta_mantem_aeronave_indisponivel(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)

    inspecao = await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]),
        usuario.id,
    )
    await _criar_pane_aberta(db, aeronave.id, usuario.id)

    tarefa = inspecao.tarefas[0]
    await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA),
        usuario_padrao_id=usuario.id,
    )
    await service.concluir_inspecao(db, inspecao.id, usuario.id)

    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.INDISPONIVEL


@pytest.mark.asyncio
async def test_cancelar_inspecao_sem_pendencias_retorna_aeronave_disponivel(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)

    inspecao = await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]),
        usuario.id,
    )
    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.INSPECAO

    await service.cancelar_inspecao(db, inspecao.id)

    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.DISPONIVEL


@pytest.mark.asyncio
async def test_cancelar_inspecao_com_pane_aberta_mantem_indisponivel(db: AsyncSession):
    """Mesmo ramo do teste de conclusão, agora via cancelamento — prova que
    a lógica unificada (sincronizar_status_aeronave) cobre os dois callers
    que antes duplicavam o bloco de forma idêntica."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)

    inspecao = await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]),
        usuario.id,
    )
    await _criar_pane_aberta(db, aeronave.id, usuario.id)

    await service.cancelar_inspecao(db, inspecao.id)

    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.INDISPONIVEL


@pytest.mark.asyncio
async def test_concluir_inspecao_mantem_status_inspecao_se_outra_ativa(db: AsyncSession):
    """Se ainda houver outra inspeção ativa na mesma aeronave, o status deve
    permanecer INSPECAO (não voltar para DISPONIVEL) — comportamento
    preservado da lógica original, agora centralizada."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo1, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    tipo2, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)

    insp1 = await service.abrir_inspecao(
        db, schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo1.id]), usuario.id
    )
    await service.abrir_inspecao(
        db, schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo2.id]), usuario.id
    )

    tarefa = insp1.tarefas[0]
    await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA),
        usuario_padrao_id=usuario.id,
    )
    await service.concluir_inspecao(db, insp1.id, usuario.id)

    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.INSPECAO


# ------------------------------------------------------------------ #
#  #13 — calcular_progresso usa o enum, não strings mágicas
# ------------------------------------------------------------------ #

def test_calcular_progresso_considera_concluida_e_na_como_progresso():
    inspecao_fake = SimpleNamespace(tarefas=[
        SimpleNamespace(status=StatusTarefaInspecao.CONCLUIDA.value),
        SimpleNamespace(status=StatusTarefaInspecao.NA.value),
        SimpleNamespace(status=StatusTarefaInspecao.PENDENTE.value),
    ])

    total, concluidas, percentual = service.calcular_progresso(inspecao_fake)

    assert total == 3
    assert concluidas == 2
    assert percentual == 67


def test_calcular_progresso_sem_tarefas_nao_divide_por_zero():
    inspecao_fake = SimpleNamespace(tarefas=[])
    assert service.calcular_progresso(inspecao_fake) == (0, 0, 0)
