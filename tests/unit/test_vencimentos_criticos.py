"""
tests/unit/test_vencimentos_criticos.py
Testes de regressão para os achados CRÍTICOS de
docs/backlog/Fable5/Etapa3.md / relatorio_vencimentos_inspecoes.md:

    #1  AttributeError: domain_exc.NotFoundError não existe
    #2  Código morto (stmt_update nunca executado) removido
    #3  Status de vencimento derivado em tempo de leitura (não fica stale)
    #4  Recálculo de periodicidade reflete no status derivado

Nota de isolamento: segue o padrão dos testes de panes/equipamentos — banco
in-memory compartilhado por sessão, isolado por ROLLBACK; identificadores
sempre únicos via uuid.
"""

import uuid
import pytest
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipamentos.models import ItemEquipamento, ModeloEquipamento
from app.modules.vencimentos import service
from app.modules.vencimentos.models import ControleVencimento, EquipamentoControle, TipoControle
from app.modules.vencimentos.schemas import ProrrogacaoVencimentoCreate
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusVencimento


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def _criar_modelo(db: AsyncSession, pn: str) -> ModeloEquipamento:
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=pn, nome_generico="RADIO")
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_item(db: AsyncSession, modelo_id: uuid.UUID, sn: str) -> ItemEquipamento:
    item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo_id, numero_serie=sn)
    db.add(item)
    await db.flush()
    return item


async def _criar_tipo_controle(db: AsyncSession, nome: str) -> TipoControle:
    tipo = TipoControle(id=uuid.uuid4(), nome=nome)
    db.add(tipo)
    await db.flush()
    return tipo


async def _criar_controle_vencimento(
    db: AsyncSession,
    item_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
    data_vencimento: date | None,
    status: StatusVencimento = StatusVencimento.OK,
) -> ControleVencimento:
    venc = ControleVencimento(
        id=uuid.uuid4(),
        item_id=item_id,
        tipo_controle_id=tipo_controle_id,
        data_ultima_exec=date.today() - timedelta(days=30) if data_vencimento else None,
        data_vencimento=data_vencimento,
        status=status.value,
    )
    db.add(venc)
    await db.flush()
    return venc


# ------------------------------------------------------------------ #
#  #1 — NotFoundError inexistente
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_prorrogar_vencimento_inexistente_levanta_404_nao_500(db: AsyncSession):
    """Antes da correção: `domain_exc.NotFoundError` não existe → AttributeError (500).
    Depois: `EntidadeNaoEncontradaError` → HTTP 404, como o restante do módulo."""
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await service.prorrogar_vencimento(
            db,
            uuid.uuid4(),
            ProrrogacaoVencimentoCreate(
                numero_documento="DOC-001",
                data_concessao=date.today(),
                dias_adicionais=30,
            ),
        )


# ------------------------------------------------------------------ #
#  #2 — código morto removido (regressão estrutural: comportamento preservado)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_associar_controle_recalcula_data_vencimento_ao_mudar_periodicidade(db: AsyncSession):
    """Garante que a remoção do bloco de update morto não alterou o comportamento:
    a data de vencimento de itens já executados continua sendo recalculada via ORM
    quando a periodicidade de um EquipamentoControle muda."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    item = await _criar_item(db, modelo.id, f"SN-{uuid.uuid4().hex[:8]}")
    tipo = await _criar_tipo_controle(db, f"TC-{uuid.uuid4().hex[:6]}")

    assoc = EquipamentoControle(
        id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=6
    )
    db.add(assoc)
    await db.flush()

    data_exec = date(2026, 1, 1)
    venc = ControleVencimento(
        id=uuid.uuid4(),
        item_id=item.id,
        tipo_controle_id=tipo.id,
        data_ultima_exec=data_exec,
        data_vencimento=date(2026, 7, 1),  # +6 meses
        status=StatusVencimento.OK.value,
    )
    db.add(venc)
    await db.flush()

    # Muda a periodicidade de 6 para 12 meses
    await service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12)

    await db.refresh(venc)
    assert venc.data_vencimento == date(2027, 1, 1)


# ------------------------------------------------------------------ #
#  #3 — status derivado em tempo de leitura (matriz)
# ------------------------------------------------------------------ #

def test_calcular_status_vencimento_puro():
    hoje = date(2026, 8, 2)
    assert service.calcular_status_vencimento(None, hoje) == StatusVencimento.VENCIDO.value
    assert service.calcular_status_vencimento(date(2026, 7, 1), hoje) == StatusVencimento.VENCIDO.value
    assert service.calcular_status_vencimento(date(2026, 8, 15), hoje) == StatusVencimento.VENCENDO.value
    assert service.calcular_status_vencimento(date(2027, 1, 1), hoje) == StatusVencimento.OK.value


@pytest.mark.asyncio
async def test_matriz_vencimentos_nao_fica_stale_com_status_persistido_desatualizado(db: AsyncSession):
    """Reproduz o bug: um controle gravado como OK cujo prazo já passou deve
    aparecer VENCIDO na matriz, mesmo sem nenhuma nova execução registrada
    (o valor persistido em `status` nunca é recalculado pela passagem do tempo)."""
    from app.modules.aeronaves.models import Aeronave
    from app.modules.equipamentos.models import Instalacao, SlotInventario
    from app.shared.core.enums import StatusAeronave

    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = await _criar_tipo_controle(db, f"TC-{uuid.uuid4().hex[:6]}")
    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=12))
    await db.flush()

    slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"SLOT-{uuid.uuid4().hex[:6]}", sistema="CEI", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()

    item = await _criar_item(db, modelo.id, f"SN-{uuid.uuid4().hex[:8]}")

    # Status gravado como OK, mas o vencimento já passou -> stale por definição.
    venc = await _criar_controle_vencimento(
        db, item.id, tipo.id, data_vencimento=date.today() - timedelta(days=5), status=StatusVencimento.OK
    )

    aeronave = Aeronave(
        id=uuid.uuid4(),
        serial_number=f"SN-ACFT-{uuid.uuid4().hex[:6]}",
        matricula=f"VC-{uuid.uuid4().hex[:6]}",
        modelo="A-29",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()

    db.add(Instalacao(
        id=uuid.uuid4(),
        item_id=item.id,
        aeronave_id=aeronave.id,
        slot_id=slot.id,
        data_instalacao=date(2020, 1, 1),
    ))
    await db.flush()

    matriz = await service.montar_matriz_vencimentos(db)

    linha = next(a for a in matriz["aeronaves"] if a["aeronave_id"] == str(aeronave.id))
    controle_out = linha["slots"][0]["controles"][0]

    # A coluna persistida continua OK (não é sobrescrita por uma leitura)...
    await db.refresh(venc)
    assert venc.status == StatusVencimento.OK.value
    # ...mas a matriz exibe o status real, derivado da data.
    assert controle_out["status"] == StatusVencimento.VENCIDO.value
    assert linha["status_vencimento"] == "VENCIDO"


@pytest.mark.asyncio
async def test_matriz_nao_persiste_status_derivado_como_efeito_colateral(db: AsyncSession):
    """A leitura da matriz (endpoint GET) não deve gravar o status derivado de
    volta no banco — senão uma requisição de leitura teria efeito colateral
    de escrita, o que é surpreendente e arriscado em concorrência."""
    from app.modules.aeronaves.models import Aeronave
    from app.modules.equipamentos.models import Instalacao, SlotInventario
    from app.shared.core.enums import StatusAeronave

    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = await _criar_tipo_controle(db, f"TC-{uuid.uuid4().hex[:6]}")
    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=12))
    await db.flush()
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"SLOT-{uuid.uuid4().hex[:6]}", sistema="CEI", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    item = await _criar_item(db, modelo.id, f"SN-{uuid.uuid4().hex[:8]}")
    venc = await _criar_controle_vencimento(
        db, item.id, tipo.id, data_vencimento=date.today() - timedelta(days=5), status=StatusVencimento.OK
    )
    aeronave = Aeronave(
        id=uuid.uuid4(), serial_number=f"SN-{uuid.uuid4().hex[:6]}", matricula=f"VC-{uuid.uuid4().hex[:6]}",
        modelo="A-29", status=StatusAeronave.DISPONIVEL, data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    db.add(Instalacao(id=uuid.uuid4(), item_id=item.id, aeronave_id=aeronave.id, slot_id=slot.id, data_instalacao=date(2020, 1, 1)))
    await db.flush()

    await service.montar_matriz_vencimentos(db)

    res = await db.execute(select(ControleVencimento.status).where(ControleVencimento.id == venc.id))
    assert res.scalar_one() == StatusVencimento.OK.value


# ------------------------------------------------------------------ #
#  #4 — recálculo de periodicidade reflete no status derivado
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_status_derivado_reflete_mudanca_de_periodicidade(db: AsyncSession):
    """Antes do fix, o comentário no código admitia que o status "seria
    recalculado na próxima visualização", o que não acontecia (a coluna
    persistida ficava congelada). Agora o status é sempre derivado a partir
    de `data_vencimento`, que É recalculada — logo o problema desaparece
    estruturalmente."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    item = await _criar_item(db, modelo.id, f"SN-{uuid.uuid4().hex[:8]}")
    tipo = await _criar_tipo_controle(db, f"TC-{uuid.uuid4().hex[:6]}")
    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=1))
    await db.flush()

    data_exec = date.today() - timedelta(days=40)
    venc = ControleVencimento(
        id=uuid.uuid4(), item_id=item.id, tipo_controle_id=tipo.id,
        data_ultima_exec=data_exec,
        data_vencimento=data_exec + timedelta(days=30),  # ~1 mês -> já vencido hoje
        status=StatusVencimento.OK.value,
    )
    db.add(venc)
    await db.flush()

    assert service.calcular_status_vencimento(venc.data_vencimento) == StatusVencimento.VENCIDO.value

    # Aumenta a periodicidade para 12 meses -> data de vencimento recalculada para o futuro
    await service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12)
    await db.refresh(venc)

    assert service.calcular_status_vencimento(venc.data_vencimento) == StatusVencimento.OK.value
