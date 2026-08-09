"""
tests/unit/test_equipamentos_correcoes_urgentes.py
Testes de regressão para as correções urgentes (#1 a #4) apontadas em
docs/backlog/Fable5/relatorio_equipamentos_services.md.

Cobertura:
    #1 Import de Aeronave      -> caminho de conflito de transferência (NameError)
    #2 N+1 query no inventário -> nº de queries constante com N slots vazios
    #4 Race conditions         -> recuperação de IntegrityError via SAVEPOINT
"""

import uuid
import pytest
from datetime import date, timedelta

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos import service
from app.modules.equipamentos.models import (
    ModeloEquipamento,
    SlotInventario,
    ItemEquipamento,
    Instalacao,
)
from app.modules.equipamentos.schemas import AjusteInventarioCreate
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusItem


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

class ContadorDeQueries:
    """Conta SELECTs executados no bloco (detecta N+1 sem depender de echo)."""

    def __init__(self) -> None:
        self.total = 0

    def __enter__(self) -> "ContadorDeQueries":
        event.listen(Engine, "before_cursor_execute", self._registrar)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(Engine, "before_cursor_execute", self._registrar)

    def _registrar(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.total += 1


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


async def _criar_modelo(db: AsyncSession, pn: str) -> ModeloEquipamento:
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=pn, nome_generico="RADIO")
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_slot(db: AsyncSession, modelo_id: uuid.UUID, nome: str) -> SlotInventario:
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao=nome, sistema="CEI", modelo_id=modelo_id)
    db.add(slot)
    await db.flush()
    return slot


async def _criar_slot_com_historico_de_remocao(
    db: AsyncSession, aeronave: Aeronave, modelo: ModeloEquipamento, sufixo: str
) -> SlotInventario:
    """Slot vazio, mas com uma instalação já removida (caminho do antigo N+1)."""
    slot = await _criar_slot(db, modelo.id, f"SLOT-{sufixo}")
    item = ItemEquipamento(
        id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-{sufixo}", status=StatusItem.ATIVO.value
    )
    db.add(item)
    await db.flush()
    db.add(
        Instalacao(
            id=uuid.uuid4(),
            item_id=item.id,
            aeronave_id=aeronave.id,
            slot_id=slot.id,
            data_instalacao=date.today() - timedelta(days=10),
            data_remocao=date.today() - timedelta(days=1),
        )
    )
    await db.flush()
    return slot


# ================================================================== #
#  #1 – Import de Aeronave (NameError em _validar_e_resolver_conflitos)
# ================================================================== #

class TestImportAeronave:
    @pytest.mark.asyncio
    async def test_conflito_de_transferencia_retorna_matricula(self, db: AsyncSession):
        """O caminho que antes quebrava com NameError deve retornar a matrícula."""
        prefixo = uuid.uuid4().hex[:6]
        anv_origem = await _criar_aeronave(db, f"O{prefixo}")
        anv_destino = await _criar_aeronave(db, f"D{prefixo}")
        modelo = await _criar_modelo(db, f"PN-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-{prefixo}")
        sn = f"SN-{prefixo}"

        # Item instalado na aeronave de origem
        primeiro = await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(aeronave_id=anv_origem.id, slot_id=slot.id, numero_serie_real=sn),
        )
        assert primeiro.sucesso is True

        # Mesmo S/N em outra aeronave, sem forçar: exige confirmação e informa a origem
        conflito = await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(aeronave_id=anv_destino.id, slot_id=slot.id, numero_serie_real=sn),
        )
        assert conflito.sucesso is False
        assert conflito.requer_confirmacao is True
        assert conflito.aeronave_conflito == f"O{prefixo}"

    @pytest.mark.asyncio
    async def test_transferencia_forcada_efetiva_troca(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        anv_origem = await _criar_aeronave(db, f"E{prefixo}")
        anv_destino = await _criar_aeronave(db, f"F{prefixo}")
        modelo = await _criar_modelo(db, f"PN-F-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-F-{prefixo}")
        sn = f"SN-F-{prefixo}"

        await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(aeronave_id=anv_origem.id, slot_id=slot.id, numero_serie_real=sn),
        )
        resp = await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(
                aeronave_id=anv_destino.id,
                slot_id=slot.id,
                numero_serie_real=sn,
                forcar_transferencia=True,
            ),
        )
        assert resp.sucesso is True

        inventario = await service.listar_inventario_aeronave(db, anv_destino.id)
        linha = next(i for i in inventario if i.slot_id == slot.id)
        assert linha.numero_serie == sn.upper()  # o service normaliza o S/N
        assert linha.aeronave_anterior == f"E{prefixo}"


# ================================================================== #
#  #2 – N+1 query no inventário
# ================================================================== #

class TestInventarioSemNMais1:
    @pytest.mark.asyncio
    async def test_numero_de_queries_independe_da_quantidade_de_slots(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"N{prefixo}")
        modelo = await _criar_modelo(db, f"PN-N-{prefixo}")

        for i in range(3):
            await _criar_slot_com_historico_de_remocao(db, aeronave, modelo, f"{prefixo}-{i}")

        with ContadorDeQueries() as contador_3:
            await service.listar_inventario_aeronave(db, aeronave.id)

        for i in range(3, 15):
            await _criar_slot_com_historico_de_remocao(db, aeronave, modelo, f"{prefixo}-{i}")

        with ContadorDeQueries() as contador_15:
            inventario = await service.listar_inventario_aeronave(db, aeronave.id)

        assert len([i for i in inventario if prefixo in i.nome_posicao]) == 15
        assert contador_15.total == contador_3.total, (
            f"N+1 detectado: {contador_3.total} queries com 3 slots "
            f"vs {contador_15.total} com 15 slots"
        )
        assert contador_15.total <= 8

    @pytest.mark.asyncio
    async def test_slot_vazio_preserva_rastreio_da_ultima_remocao(self, db: AsyncSession):
        """A window function deve trazer os mesmos dados da antiga query por slot."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"R{prefixo}")
        modelo = await _criar_modelo(db, f"PN-R-{prefixo}")
        slot = await _criar_slot_com_historico_de_remocao(db, aeronave, modelo, f"R{prefixo}")

        inventario = await service.listar_inventario_aeronave(db, aeronave.id)
        linha = next(i for i in inventario if i.slot_id == slot.id)

        assert linha.numero_serie is None  # slot está vazio
        assert linha.data_atualizacao is not None  # mas mantém a data de rastreio


# ================================================================== #
#  #4 – Race conditions (verificar → criar)
# ================================================================== #

class TestRaceConditions:
    @pytest.mark.asyncio
    async def test_get_or_create_recupera_item_criado_em_paralelo(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """IntegrityError no insert concorrente deve devolver o item existente."""
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-RC-{prefixo}")
        sn = f"SN-RC-{prefixo}"

        item_existente = ItemEquipamento(
            id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=sn, status=StatusItem.ATIVO.value
        )
        db.add(item_existente)
        await db.flush()

        # Simula a leitura anterior ao commit da transação concorrente:
        # a 1ª busca não encontra nada, o insert colide com uq_item_sn_per_pn.
        busca_real = service._buscar_item_por_sn
        chamadas = {"n": 0}

        async def busca_com_race(db_, modelo_id, numero_serie):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return None
            return await busca_real(db_, modelo_id, numero_serie)

        monkeypatch.setattr(service, "_buscar_item_por_sn", busca_com_race)

        item = await service._obter_ou_criar_item_por_pn(db, modelo.id, sn)

        assert item.id == item_existente.id
        assert chamadas["n"] == 2  # houve a re-busca após o IntegrityError
        # Sessão continua utilizável após o rollback do SAVEPOINT
        assert await busca_real(db, modelo.id, sn) is not None

    @pytest.mark.asyncio
    async def test_criar_modelo_converte_integrity_error_em_conflito(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Violação de UNIQUE no PN vira ConflitoNegocioError (409), não erro 500."""
        from app.modules.equipamentos.schemas import ModeloEquipamentoCreate

        # PN em maiúsculas: é assim que criar_modelo normaliza antes de inserir
        pn = f"PN-DUP-{uuid.uuid4().hex[:6].upper()}"
        await _criar_modelo(db, pn)

        # Simula a verificação prévia "passando" (janela da race condition)
        async def sem_duplicata(db_, pn_):
            return None

        monkeypatch.setattr(service, "buscar_modelo_por_pn", sem_duplicata)

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.criar_modelo(
                db, ModeloEquipamentoCreate(part_number=pn, nome_generico="RADIO DUP")
            )
        assert exc_info.value.status_code == 409
        assert pn in exc_info.value.detail

        # Sessão segue viva: o SAVEPOINT isolou a falha
        assert await service._buscar_item_por_sn(db, uuid.uuid4(), "X") is None
