"""
tests/unit/test_equipamentos_refatoracao.py
Testes de regressão para as correções de design e menores (#5 a #15) de
docs/backlog/Fable5/relatorio_equipamentos_services.md.

Cobertura:
    #5  Herança de controles delegada a vencimentos
    #6  Exceções de domínio no lugar de ValueError
    #8  slot_id resolvido no schema
    #10 removido_em como timestamp do evento de remoção
    #13 Paginação de listagens
    #14 Normalização de PN/SN nos schemas
    + Bug adjacente: endpoint /inventario/export
"""

import uuid
import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos import service
from app.modules.equipamentos.models import (
    ModeloEquipamento,
    SlotInventario,
    ItemEquipamento,
    Instalacao,
)
from app.modules.equipamentos.schemas import (
    AjusteInventarioCreate,
    ItemEquipamentoCreate,
    ModeloEquipamentoCreate,
)
from app.modules.vencimentos.models import (
    ControleVencimento,
    EquipamentoControle,
    TipoControle,
)
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusItem, StatusVencimento


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

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


async def _criar_controle_template(db: AsyncSession, modelo_id: uuid.UUID, nome_tipo: str) -> TipoControle:
    """Vincula um TipoControle ao PN (template herdado pelos itens)."""
    tipo = TipoControle(id=uuid.uuid4(), nome=nome_tipo)
    db.add(tipo)
    await db.flush()
    db.add(
        EquipamentoControle(
            id=uuid.uuid4(),
            modelo_id=modelo_id,
            tipo_controle_id=tipo.id,
            periodicidade_meses=12,
        )
    )
    await db.flush()
    return tipo


async def _controles_do_item(db: AsyncSession, item_id: uuid.UUID) -> list[ControleVencimento]:
    res = await db.execute(select(ControleVencimento).where(ControleVencimento.item_id == item_id))
    return list(res.scalars().all())


# ================================================================== #
#  #5 – Herança de controles delegada ao domínio de vencimentos
# ================================================================== #

class TestHerancaDeControles:
    @pytest.mark.asyncio
    async def test_criar_item_herda_controles_do_pn(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-H1-{prefixo}")
        await _criar_controle_template(db, modelo.id, f"T{prefixo[:4]}A")
        await _criar_controle_template(db, modelo.id, f"T{prefixo[:4]}B")

        item = await service.criar_item_com_heranca(
            db, ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=f"SN-H1-{prefixo}")
        )

        controles = await _controles_do_item(db, item.id)
        assert len(controles) == 2
        assert {c.status for c in controles} == {StatusVencimento.VENCIDO.value}

    @pytest.mark.asyncio
    async def test_get_or_create_no_ajuste_tambem_herda(self, db: AsyncSession):
        """Os dois caminhos de criação de item usam a mesma função de herança."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"H{prefixo}")
        modelo = await _criar_modelo(db, f"PN-H2-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-H2-{prefixo}")
        await _criar_controle_template(db, modelo.id, f"T{prefixo[:4]}C")

        resp = await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(
                aeronave_id=aeronave.id, slot_id=slot.id, numero_serie_real=f"SN-H2-{prefixo}"
            ),
        )
        assert resp.sucesso is True

        item = await service._buscar_item_por_sn(db, modelo.id, f"SN-H2-{prefixo}".upper())
        assert item is not None
        controles = await _controles_do_item(db, item.id)
        assert len(controles) == 1
        assert controles[0].status == StatusVencimento.VENCIDO.value

    @pytest.mark.asyncio
    async def test_item_de_pn_sem_template_nao_cria_controles(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-H3-{prefixo}")

        item = await service.criar_item_com_heranca(
            db, ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=f"SN-H3-{prefixo}")
        )
        assert await _controles_do_item(db, item.id) == []


# ================================================================== #
#  #6 – Exceções de domínio
# ================================================================== #

class TestExcecoesDeDominio:
    @pytest.mark.asyncio
    async def test_pn_duplicado_levanta_conflito_409(self, db: AsyncSession):
        pn = f"PN-DOM-{uuid.uuid4().hex[:6].upper()}"
        await service.criar_modelo(db, ModeloEquipamentoCreate(part_number=pn, nome_generico="A"))

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.criar_modelo(db, ModeloEquipamentoCreate(part_number=pn, nome_generico="B"))
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_sn_duplicado_levanta_conflito_409(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-DOM2-{prefixo}")
        dados = ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=f"SN-{prefixo}")
        await service.criar_item_com_heranca(db, dados)

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.criar_item_com_heranca(db, dados)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_remover_pn_com_dependencias_levanta_conflito(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-DOM3-{prefixo}")
        await _criar_slot(db, modelo.id, f"POS-{prefixo}")

        with pytest.raises(domain_exc.ConflitoNegocioError) as exc_info:
            await service.remover_modelo(db, modelo.id)
        assert exc_info.value.status_code == 409
        assert "slots" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_pn_inexistente_levanta_nao_encontrado_404(self, db: AsyncSession):
        with pytest.raises(domain_exc.EntidadeNaoEncontradaError) as exc_info:
            await service.buscar_modelo(db, uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_router_propaga_409_sem_try_except(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict
    ):
        """O handler global converte a exceção de domínio; o router não traduz erro."""
        headers = usuario_e_token["headers"]
        pn = f"PN-API-{uuid.uuid4().hex[:6].upper()}"
        payload = {"part_number": pn, "nome_generico": "RADIO API"}

        primeira = await client.post("/equipamentos/", json=payload, headers=headers)
        assert primeira.status_code == 201

        segunda = await client.post("/equipamentos/", json=payload, headers=headers)
        assert segunda.status_code == 409
        assert pn in segunda.json()["detail"]


# ================================================================== #
#  #8 – slot_id resolvido no schema
# ================================================================== #

class TestResolucaoDeSlotId:
    def test_equipamento_id_legado_preenche_slot_id(self):
        equipamento_id = uuid.uuid4()
        dados = AjusteInventarioCreate(
            aeronave_id=uuid.uuid4(), equipamento_id=equipamento_id, numero_serie_real="SN1"
        )
        assert dados.slot_id == equipamento_id

    def test_slot_id_tem_precedencia_sobre_equipamento_id(self):
        slot_id = uuid.uuid4()
        dados = AjusteInventarioCreate(
            aeronave_id=uuid.uuid4(),
            slot_id=slot_id,
            equipamento_id=uuid.uuid4(),
            numero_serie_real="SN1",
        )
        assert dados.slot_id == slot_id

    def test_sem_nenhum_identificador_falha_na_validacao(self):
        with pytest.raises(ValidationError):
            AjusteInventarioCreate(aeronave_id=uuid.uuid4(), numero_serie_real="SN1")


# ================================================================== #
#  #10 – removido_em como timestamp do evento
# ================================================================== #

class TestTimestampDeRemocao:
    @pytest.mark.asyncio
    async def test_remocao_grava_removido_em(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"T{prefixo}")
        modelo = await _criar_modelo(db, f"PN-T-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-T-{prefixo}")

        await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(
                aeronave_id=aeronave.id, slot_id=slot.id, numero_serie_real=f"SN-T-{prefixo}"
            ),
        )
        # S/N vazio = remoção
        await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(aeronave_id=aeronave.id, slot_id=slot.id, numero_serie_real=""),
        )
        await db.flush()

        res = await db.execute(select(Instalacao).where(Instalacao.slot_id == slot.id))
        instalacao = res.scalar_one()
        await db.refresh(instalacao)
        assert instalacao.data_remocao == date.today()
        assert instalacao.removido_em is not None

    @pytest.mark.asyncio
    async def test_update_posterior_nao_corrompe_removido_em(self, db: AsyncSession):
        """O ganho estrutural do item #10: histórico imune a updates no registro."""
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"U{prefixo}")
        modelo = await _criar_modelo(db, f"PN-U-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-U-{prefixo}")
        item = ItemEquipamento(
            id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-U-{prefixo}",
            status=StatusItem.ATIVO.value,
        )
        db.add(item)
        await db.flush()
        instalacao = Instalacao(
            id=uuid.uuid4(),
            item_id=item.id,
            aeronave_id=aeronave.id,
            slot_id=slot.id,
            data_instalacao=date.today() - timedelta(days=5),
        )
        db.add(instalacao)
        await db.flush()

        await service.remover_item(db, instalacao.id, date.today())
        await db.refresh(instalacao)
        removido_em_original = instalacao.removido_em
        assert removido_em_original is not None

        # Update alheio à remoção (ex.: correção de responsável)
        instalacao.data_instalacao = date.today() - timedelta(days=4)
        await db.flush()
        await db.refresh(instalacao)

        assert instalacao.removido_em == removido_em_original

    @pytest.mark.asyncio
    async def test_historico_lista_remocao_por_removido_em(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict
    ):
        headers = usuario_e_token["headers"]
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"V{prefixo}")
        modelo = await _criar_modelo(db, f"PN-V-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-V-{prefixo}")
        sn = f"SN-V-{prefixo}".upper()

        for numero_serie in (sn, ""):
            await service.ajustar_inventario_item(
                db,
                AjusteInventarioCreate(
                    aeronave_id=aeronave.id, slot_id=slot.id, numero_serie_real=numero_serie
                ),
            )
        await db.flush()

        resp = await client.get("/equipamentos/inventario/historico?limit=100", headers=headers)
        assert resp.status_code == 200
        acoes = {log["tipo_acao"] for log in resp.json() if log["item_sn"] == sn}
        assert "REMOÇÃO" in acoes


# ================================================================== #
#  #13 – Paginação
# ================================================================== #

class TestPaginacao:
    @pytest.mark.asyncio
    async def test_listar_modelos_respeita_limit_e_offset(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6].upper()
        for i in range(3):
            await _criar_modelo(db, f"PN-PAG-{prefixo}-{i}")

        pagina = await service.listar_modelos(db, limit=2)
        assert len(pagina) == 2

        todos = await service.listar_modelos(db)
        assert len(todos) >= 3  # sem limit, catálogo completo

        segunda_pagina = await service.listar_modelos(db, limit=2, offset=2)
        assert [m.id for m in segunda_pagina] != [m.id for m in pagina]

    @pytest.mark.asyncio
    async def test_listar_itens_respeita_limit(self, db: AsyncSession):
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-PAGI-{prefixo}")
        for i in range(3):
            await service.criar_item_com_heranca(
                db, ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=f"SN-{prefixo}-{i}")
            )

        assert len(await service.listar_itens(db, modelo.id, limit=2)) == 2
        assert len(await service.listar_itens(db, modelo.id)) == 3

    @pytest.mark.asyncio
    async def test_limit_acima_do_teto_e_truncado(self, db: AsyncSession):
        """O teto protege o banco mesmo se o chamador pedir mais."""
        pagina = await service.listar_modelos(db, limit=10_000)
        assert len(pagina) <= service.LIMITE_MAXIMO_LISTAGEM


# ================================================================== #
#  #14 – Normalização de PN/SN no schema
# ================================================================== #

class TestNormalizacaoDeIdentificadores:
    def test_schema_normaliza_pn_e_sn(self):
        modelo = ModeloEquipamentoCreate(part_number="  pn-abc  ", nome_generico="X")
        assert modelo.part_number == "PN-ABC"

        item = ItemEquipamentoCreate(modelo_id=uuid.uuid4(), numero_serie=" sn-123 ")
        assert item.numero_serie == "SN-123"

        ajuste = AjusteInventarioCreate(
            aeronave_id=uuid.uuid4(), slot_id=uuid.uuid4(), numero_serie_real=" abc123 "
        )
        assert ajuste.numero_serie_real == "ABC123"

    @pytest.mark.asyncio
    async def test_criar_item_nao_cria_duplicata_logica(self, db: AsyncSession):
        """Antes, criar_item_com_heranca não normalizava e aceitava 'abc' + 'ABC'."""
        prefixo = uuid.uuid4().hex[:6]
        modelo = await _criar_modelo(db, f"PN-NORM-{prefixo}")
        sn_minusculo = f"sn-norm-{prefixo}"

        item = await service.criar_item_com_heranca(
            db, ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=sn_minusculo)
        )
        assert item.numero_serie == sn_minusculo.upper()

        with pytest.raises(domain_exc.ConflitoNegocioError):
            await service.criar_item_com_heranca(
                db, ItemEquipamentoCreate(modelo_id=modelo.id, numero_serie=sn_minusculo.upper())
            )


# ================================================================== #
#  Bug adjacente – endpoint /inventario/export
# ================================================================== #

class TestExportInventario:
    @pytest.mark.asyncio
    async def test_export_csv_responde_200(
        self, client: AsyncClient, db: AsyncSession, usuario_e_token: dict
    ):
        """Antes: 422 (rota capturada por /{aeronave_id}) e AttributeError nos campos."""
        headers = usuario_e_token["headers"]
        prefixo = uuid.uuid4().hex[:6]
        aeronave = await _criar_aeronave(db, f"X{prefixo}")
        modelo = await _criar_modelo(db, f"PN-X-{prefixo}")
        slot = await _criar_slot(db, modelo.id, f"POS-X-{prefixo}")
        await service.ajustar_inventario_item(
            db,
            AjusteInventarioCreate(
                aeronave_id=aeronave.id, slot_id=slot.id, numero_serie_real=f"SN-X-{prefixo}"
            ),
        )
        await db.flush()

        resp = await client.get(
            f"/equipamentos/inventario/export?aeronave_id={aeronave.id}&format=csv",
            headers=headers,
        )
        assert resp.status_code == 200
        conteudo = resp.content.decode("utf-8-sig")
        assert f"POS-X-{prefixo}" in conteudo
        assert f"SN-X-{prefixo}".upper() in conteudo
