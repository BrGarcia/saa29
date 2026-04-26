"""
scripts/seed/seed_inventario.py
Instala itens físicos em aeronaves específicas para testes.
"""
import uuid
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import SlotInventario, ItemEquipamento, Instalacao, ControleVencimento, TipoControle
from app.shared.core.enums import StatusItem, StatusVencimento

async def run(session: AsyncSession):
    print("🚀 [Inventário] Instalando itens de teste na 5902...")
    
    # 1. Buscar Aeronave 5902
    res_acft = await session.execute(select(Aeronave).where(Aeronave.matricula == "5902"))
    acft = res_acft.scalar_one_or_none()
    if not acft:
        print("   ! Aeronave 5902 não encontrada. Pulando inventário.")
        return

    # 2. Buscar Slots disponíveis
    res_slots = await session.execute(select(SlotInventario))
    slots = res_slots.scalars().all()

    # 3. Buscar Tipos de Controle (CRI)
    res_cri = await session.execute(select(TipoControle).where(TipoControle.nome == "CRI"))
    tipo_cri = res_cri.scalar_one_or_none()

    for slot in slots:
        # Verificar se já tem instalação
        res_ins = await session.execute(
            select(Instalacao).where(Instalacao.slot_id == slot.id, Instalacao.aeronave_id == acft.id, Instalacao.data_remocao.is_(None))
        )
        if not res_ins.scalar_one_or_none():
            sn = f"SN-{slot.nome_posicao}-5902"
            
            # Criar Item
            item = ItemEquipamento(
                id=uuid.uuid4(),
                modelo_id=slot.modelo_id,
                numero_serie=sn,
                status=StatusItem.ATIVO
            )
            session.add(item)
            await session.flush()

            # Instalar
            inst = Instalacao(
                id=uuid.uuid4(),
                item_id=item.id,
                aeronave_id=acft.id,
                slot_id=slot.id,
                data_instalacao=date.today() - timedelta(days=30)
            )
            session.add(inst)

            # Criar Controle de Vencimento (Pendente por padrão)
            if tipo_cri:
                venc = ControleVencimento(
                    id=uuid.uuid4(),
                    item_id=item.id,
                    tipo_controle_id=tipo_cri.id,
                    status=StatusVencimento.PENDENTE.value,
                    origem="PADRAO"
                )
                session.add(venc)
            
            print(f"   + Instalado {sn} no slot {slot.nome_posicao}")
    
    await session.flush()
