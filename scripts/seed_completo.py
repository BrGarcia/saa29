"""
scripts/seed_completo.py
Popula o banco com um cenário realista para testes manuais da Matriz de Vencimentos.
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Ajustar PYTHONPATH para encontrar o pacote 'app'
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# IMPORTAÇÃO CRÍTICA: Garantir que todos os modelos sejam registrados no SQLAlchemy
# antes de qualquer operação de banco, para evitar erros de mapeamento (relacionamentos).
import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.panes.models
import app.modules.equipamentos.models

from sqlalchemy import select
from sqlalchemy.orm import configure_mappers
from app.bootstrap.database import get_session_factory
from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import (
    ModeloEquipamento, SlotInventario, ItemEquipamento, 
    Instalacao, TipoControle, EquipamentoControle, 
    ControleVencimento, ProrrogacaoVencimento
)
from app.shared.core.enums import StatusItem, StatusVencimento

# Garantir que os mappers do SQLAlchemy estejam configurados
configure_mappers()

# Configuração do Cenário
AERONAVES = [
    {"mat": "5916", "sn": "SN-5916"},
    {"mat": "5902", "sn": "SN-5902"},
    {"mat": "5900", "sn": "SN-5900"},
]

TIPOS_CONTROLE = [
    {"nome": "CRI", "desc": "Controle de Revisão de Itens"},
    {"nome": "TLV", "desc": "Tempo de Limite de Vida"},
    {"nome": "TBO", "desc": "Time Between Overhaul"},
]

EQUIPAMENTOS_BASE = [
    {"posicao": "EGIR1", "nome": "EGIR", "pn": "34200802-80RB", "sistema": "CEI", "regras": {"TBO": 48}},
    {"posicao": "VADR", "nome": "VADR", "pn": "174521-10-01", "sistema": "CES", "regras": {"TLV": 60, "CRI": 24}},
    {"posicao": "ELT", "nome": "ELT", "pn": "453-5000-710", "sistema": "CES", "regras": {"CRI": 12}},
    {"posicao": "MDP1", "nome": "MDP", "pn": "MA902B-02", "sistema": "CEI", "regras": {"CRI": 36}},
]

async def seed_completo():
    factory = get_session_factory()
    async with factory() as session:
        print("--- Iniciando Seed Completo ---")
        
        # 1. Criar Aeronaves Adicionais se Necessário
        for a in AERONAVES:
            res = await session.execute(select(Aeronave).where(Aeronave.matricula == a["mat"]))
            obj = res.scalar_one_or_none()
            if not obj:
                obj = Aeronave(id=uuid.uuid4(), matricula=a["mat"], serial_number=a["sn"], status="OPERACIONAL")
                session.add(obj)
                print(f"Aeronave {a['mat']} criada.")
        await session.flush()

        # Buscar TODAS as aeronaves ativas para o seed
        res_all_acft = await session.execute(select(Aeronave).where(Aeronave.status == "OPERACIONAL"))
        acft_objs = res_all_acft.scalars().all()
        print(f"Alimentando {len(acft_objs)} aeronaves com dados de inventário...")

        # 2. Criar Tipos de Controle
        tp_map = {}
        for tc in TIPOS_CONTROLE:
            res = await session.execute(select(TipoControle).where(TipoControle.nome == tc["nome"]))
            obj = res.scalar_one_or_none()
            if not obj:
                obj = TipoControle(id=uuid.uuid4(), nome=tc["nome"], descricao=tc["desc"])
                session.add(obj)
                print(f"Tipo Controle {tc['nome']} criado.")
            tp_map[tc["nome"]] = obj
        await session.flush()

        # 3. Criar Catálogo e Regras
        for eq in EQUIPAMENTOS_BASE:
            # Modelo
            res_mod = await session.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == eq["pn"]))
            modelo = res_mod.scalar_one_or_none()
            if not modelo:
                modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=eq["pn"], nome_generico=eq["nome"])
                session.add(modelo)
                print(f"Modelo PN {eq['pn']} criado.")
            await session.flush()

            # Regras de Periodicidade
            for ctrl_nome, meses in eq["regras"].items():
                tp_id = tp_map[ctrl_nome].id
                res_reg = await session.execute(
                    select(EquipamentoControle).where(
                        EquipamentoControle.modelo_id == modelo.id,
                        EquipamentoControle.tipo_controle_id == tp_id
                    )
                )
                if not res_reg.scalar_one_or_none():
                    regra = EquipamentoControle(
                        id=uuid.uuid4(), 
                        modelo_id=modelo.id, 
                        tipo_controle_id=tp_id, 
                        periodicidade_meses=meses
                    )
                    session.add(regra)
                    print(f"Regra {eq['pn']} + {ctrl_nome} = {meses}m criada.")

            # Slot
            res_slot = await session.execute(select(SlotInventario).where(SlotInventario.nome_posicao == eq["posicao"]))
            slot = res_slot.scalar_one_or_none()
            if not slot:
                slot = SlotInventario(id=uuid.uuid4(), nome_posicao=eq["posicao"], sistema=eq["sistema"], modelo_id=modelo.id)
                session.add(slot)
                print(f"Slot {eq['posicao']} criado.")
            await session.flush()

            # 4. Criar Itens Físicos e Instalações para cada Aeronave
            for anv in acft_objs:
                # Verificar se ja tem algo instalado nesse slot
                res_ins = await session.execute(
                    select(Instalacao).where(Instalacao.slot_id == slot.id, Instalacao.aeronave_id == anv.id, Instalacao.data_remocao.is_(None))
                )
                if not res_ins.scalar_one_or_none():
                    sn = f"SN-{eq['posicao']}-{anv.matricula}"
                    # Garantir item
                    res_item = await session.execute(select(ItemEquipamento).where(ItemEquipamento.numero_serie == sn))
                    item = res_item.scalar_one_or_none()
                    if not item:
                        item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=sn, status=StatusItem.ATIVO)
                        session.add(item)
                    await session.flush()

                    # Instalação
                    inst = Instalacao(id=uuid.uuid4(), item_id=item.id, aeronave_id=anv.id, slot_id=slot.id, data_instalacao=date.today() - timedelta(days=30))
                    session.add(inst)

                    # 5. Criar Controles de Vencimento baseados nas regras do Modelo
                    for ctrl_nome, meses in eq["regras"].items():
                        tp_id = tp_map[ctrl_nome].id
                        res_venc = await session.execute(
                            select(ControleVencimento).where(ControleVencimento.item_id == item.id, ControleVencimento.tipo_controle_id == tp_id)
                        )
                        venc = res_venc.scalar_one_or_none()
                        if not venc:
                            # Variar datas para simular estados diferentes
                            offset_days = (int(anv.matricula) % 100) * 5
                            data_base = date.today() - timedelta(days=offset_days)
                            
                            # Simular Vencido se 5916, OK se 5902, Vencendo se 5900
                            if anv.matricula == "5916":
                                # Vencido: última execução há muito tempo
                                data_exec = data_base - timedelta(days=meses*30 + 10)
                                data_venc = data_exec + timedelta(days=meses*30)
                                status = StatusVencimento.VENCIDO.value
                            elif anv.matricula == "5902":
                                # OK: executado recentemente
                                data_exec = date.today() - timedelta(days=15)
                                data_venc = data_exec + timedelta(days=meses*30)
                                status = StatusVencimento.OK.value
                            else:
                                # Vencendo: vence em 15 dias
                                data_venc = date.today() + timedelta(days=15)
                                data_exec = data_venc - timedelta(days=meses*30)
                                status = StatusVencimento.VENCENDO.value

                            venc = ControleVencimento(
                                id=uuid.uuid4(),
                                item_id=item.id,
                                tipo_controle_id=tp_id,
                                data_ultima_exec=data_exec,
                                data_vencimento=data_venc,
                                status=status,
                                origem="PADRAO"
                            )
                            session.add(venc)
                            
                            # 6. Adicionar uma Prorrogação para o ELT da 5916 (que estaria vencido)
                            if anv.matricula == "5916" and eq["posicao"] == "ELT":
                                prorrog = ProrrogacaoVencimento(
                                    id=uuid.uuid4(),
                                    controle_id=venc.id,
                                    numero_documento="DIR-ENG-2026-001",
                                    data_concessao=date.today(),
                                    data_nova_vencimento=date.today() + timedelta(days=45),
                                    dias_adicionais=45,
                                    motivo="Aguardando recebimento de bateria",
                                    ativo=True
                                )
                                session.add(prorrog)
                                print(f"Prorrogação aplicada ao ELT da 5916.")

        await session.commit()
        print("\n--- Seed Completo Concluído com Sucesso! ---")
        print("Cenário disponível:")
        print("- Aeronaves: 5916 (Vencidos/Prorrogados), 5902 (OK), 5900 (Vencendo)")
        print("- Equipamentos: EGIR, VADR, ELT, MDP")
        print("- Tipos: CRI, TLV, TBO")

if __name__ == "__main__":
    asyncio.run(seed_completo())
