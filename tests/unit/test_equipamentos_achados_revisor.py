"""
tests/unit/test_equipamentos_achados_revisor.py
Testes de regressão para os achados de docs/backlog/revisor/achados_equipamentos.md.

Cobertura:
    MELHORIA-04  criar_slot valida modelo_id antes do insert (404, não 400 cru)
    RISCO-05     índice único (slot_id, aeronave_id) WHERE data_remocao IS NULL
    MELHORIA-06  remover_modelo bloqueia PN com EquipamentoControle dependente
"""

import uuid
import pytest
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos import service
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario, ItemEquipamento, Instalacao
from app.modules.equipamentos.schemas import SlotInventarioCreate
from app.modules.vencimentos.models import EquipamentoControle, TipoControle
from app.shared.core import exceptions as domain_exc


async def _criar_modelo(db: AsyncSession, pn: str) -> ModeloEquipamento:
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=pn, nome_generico="RADIO")
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_aeronave(db: AsyncSession, matricula: str) -> Aeronave:
    aeronave = Aeronave(
        id=uuid.uuid4(),
        serial_number=f"SN-{matricula}",
        matricula=matricula,
        modelo="A-29",
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_item(db: AsyncSession, modelo_id: uuid.UUID, sn: str) -> ItemEquipamento:
    item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo_id, numero_serie=sn)
    db.add(item)
    await db.flush()
    return item


# ------------------------------------------------------------------ #
#  MELHORIA-04 — criar_slot valida modelo_id
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_slot_modelo_inexistente_levanta_404_nao_400_cru(db: AsyncSession):
    """Antes, um `modelo_id` inexistente estourava `IntegrityError` de FK no
    flush, capturada pelo `except Exception` genérico do router e devolvida
    como 400 com a mensagem crua do SQLAlchemy (incluindo SQL e parâmetros)."""
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await service.criar_slot(
            db, SlotInventarioCreate(nome_posicao="TESTE", sistema="CEI", modelo_id=uuid.uuid4())
        )


@pytest.mark.asyncio
async def test_criar_slot_modelo_existente_sucede(db: AsyncSession):
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = await service.criar_slot(
        db, SlotInventarioCreate(nome_posicao="TESTE", sistema="CEI", modelo_id=modelo.id)
    )
    assert slot.modelo_id == modelo.id


# ------------------------------------------------------------------ #
#  RISCO-05 — no máximo uma instalação ativa por (slot, aeronave)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_indice_unico_barra_duas_instalacoes_ativas_no_mesmo_slot_e_aeronave(db: AsyncSession):
    """A invariante real (confirmada contra `_obter_instalacao_ativa_no_slot`,
    que filtra por `slot_id` E `aeronave_id`) é por par (slot, aeronave) — não
    por slot isolado, já que um slot é uma posição compartilhada por toda a
    frota (cada aeronave tem sua própria instalação ativa no mesmo slot_id).
    Confirmado contra `var/db`: 0 violações agrupando por (slot_id, aeronave_id);
    agrupar só por slot_id (como o texto do achado sugere) dá dezenas de
    "duplicatas" falsas — são aeronaves diferentes, não uma corrida real."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao="SLOT-X", sistema="CEI", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    aeronave = await _criar_aeronave(db, f"RC-{uuid.uuid4().hex[:6]}")
    item1 = await _criar_item(db, modelo.id, f"SN-A-{uuid.uuid4().hex[:8]}")
    item2 = await _criar_item(db, modelo.id, f"SN-B-{uuid.uuid4().hex[:8]}")

    db.add(Instalacao(
        id=uuid.uuid4(), item_id=item1.id, aeronave_id=aeronave.id, slot_id=slot.id,
        data_instalacao=date.today(),
    ))
    await db.flush()

    db.add(Instalacao(
        id=uuid.uuid4(), item_id=item2.id, aeronave_id=aeronave.id, slot_id=slot.id,
        data_instalacao=date.today(),
    ))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_mesmo_slot_aceita_instalacoes_ativas_em_aeronaves_diferentes(db: AsyncSession):
    """Confirma que o índice NÃO bloqueia o caso normal e mais comum da
    frota: o mesmo slot (posição física) tem uma instalação ativa própria em
    cada aeronave diferente."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao="SLOT-Y", sistema="CEI", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    aeronave1 = await _criar_aeronave(db, f"RC1-{uuid.uuid4().hex[:6]}")
    aeronave2 = await _criar_aeronave(db, f"RC2-{uuid.uuid4().hex[:6]}")
    item1 = await _criar_item(db, modelo.id, f"SN-A-{uuid.uuid4().hex[:8]}")
    item2 = await _criar_item(db, modelo.id, f"SN-B-{uuid.uuid4().hex[:8]}")

    db.add(Instalacao(
        id=uuid.uuid4(), item_id=item1.id, aeronave_id=aeronave1.id, slot_id=slot.id,
        data_instalacao=date.today(),
    ))
    db.add(Instalacao(
        id=uuid.uuid4(), item_id=item2.id, aeronave_id=aeronave2.id, slot_id=slot.id,
        data_instalacao=date.today(),
    ))
    await db.flush()  # não deve levantar


@pytest.mark.asyncio
async def test_instalar_item_concorrente_no_mesmo_slot_levanta_conflito_de_dominio(db: AsyncSession):
    """Simula a corrida real do RISCO-05: duas chamadas de `instalar_item`
    para o mesmo slot/aeronave sem que a primeira instalação tenha sido
    encerrada entre elas (ex.: duas requisições concorrentes que leram
    "nenhuma instalação ativa" antes de qualquer commit)."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao="SLOT-Z", sistema="CEI", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    aeronave = await _criar_aeronave(db, f"RC-{uuid.uuid4().hex[:6]}")
    item1 = await _criar_item(db, modelo.id, f"SN-A-{uuid.uuid4().hex[:8]}")
    item2 = await _criar_item(db, modelo.id, f"SN-B-{uuid.uuid4().hex[:8]}")
    usuario_id = uuid.uuid4()

    await service.instalar_item(db, item1.id, aeronave.id, slot.id, date.today(), usuario_id)

    # item1 continua "ativo" no slot (não foi removido) — segunda instalação
    # no MESMO slot/aeronave deve ser rejeitada como conflito, não corromper
    # o estado com duas instalações ativas simultâneas.
    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.instalar_item(db, item2.id, aeronave.id, slot.id, date.today(), usuario_id)


# ------------------------------------------------------------------ #
#  MELHORIA-06 — remover_modelo bloqueia EquipamentoControle dependente
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_remover_modelo_com_equipamento_controle_dependente_levanta_409(db: AsyncSession):
    """Decisão do desenvolvedor (achados_equipamentos.md): bloquear a
    exclusão do PN quando existem `EquipamentoControle` (templates de
    vencimento) configurados, no mesmo padrão já usado para itens físicos e
    slots dependentes — antes, o `ondelete=CASCADE` apagava esses templates
    silenciosamente."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=12))
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.remover_modelo(db, modelo.id)


@pytest.mark.asyncio
async def test_remover_modelo_sem_dependentes_sucede(db: AsyncSession):
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    await service.remover_modelo(db, modelo.id)

    resultado = await db.get(ModeloEquipamento, modelo.id)
    assert resultado is None
