"""
scripts/seed/seed_inventario.py
Instala itens físicos em todas as aeronaves específicas para testes.
(Responsabilidade exclusiva: criar ItemEquipamento e Instalacao física).
"""
import uuid
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import SlotInventario, ItemEquipamento, Instalacao
from app.shared.core.enums import StatusItem

async def run(session: AsyncSession):
    print("🚀 [Inventário] Instalando itens de teste nas aeronaves...")
    
    # 1. Buscar Aeronaves
    res_acft = await session.execute(select(Aeronave))
    aeronaves = res_acft.scalars().all()
    if not aeronaves:
        print("   ! Nenhuma aeronave encontrada. Pulando inventário.")
        return

    # 2. Buscar Slots disponíveis
    res_slots = await session.execute(select(SlotInventario))
    slots = res_slots.scalars().all()

    itens_instalados = 0

    for acft in aeronaves:
        for slot in slots:
            # Verificar se já tem instalação ativa neste slot e aeronave
            res_ins = await session.execute(
                select(Instalacao).where(
                    Instalacao.slot_id == slot.id, 
                    Instalacao.aeronave_id == acft.id, 
                    Instalacao.data_remocao.is_(None)
                )
            )
            
            if not res_ins.scalar_one_or_none():
                sn = f"SN-{slot.nome_posicao}-{acft.matricula}"
                
                # Criar Item (Equipamento Físico)
                item = ItemEquipamento(
                    id=uuid.uuid4(),
                    modelo_id=slot.modelo_id,
                    numero_serie=sn,
                    status=StatusItem.ATIVO
                )
                session.add(item)
                
                # É necessário dar flush para usar o ID do item
                await session.flush()

                # Instalar fisicamente na aeronave
                inst = Instalacao(
                    id=uuid.uuid4(),
                    item_id=item.id,
                    aeronave_id=acft.id,
                    slot_id=slot.id,
                    data_instalacao=date.today() - timedelta(days=30)
                )
                session.add(inst)
                itens_instalados += 1
                
    await session.flush()
    print(f"   ✅ Total: {itens_instalados} itens físicos instalados nas aeronaves.")
