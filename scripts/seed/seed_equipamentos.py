"""
scripts/seed/seed_equipamentos.py
DEPRECADO — mantido apenas para compatibilidade histórica.

A lógica foi dividida em:
  - seed_modelos.py: catálogo de Part Numbers (ModeloEquipamento)
  - seed_slots.py:   mapa físico de posições (SlotInventario)

Este arquivo delega para os módulos acima e será removido em refatoração futura.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from scripts.seed import seed_modelos, seed_slots

async def run(session: AsyncSession):
    print("⚠️  [seed_equipamentos] Delegando para seed_modelos + seed_slots (módulo legado)...")
    await seed_modelos.run(session)
    await seed_slots.run(session)
