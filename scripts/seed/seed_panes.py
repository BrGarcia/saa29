"""
scripts/seed/seed_panes.py
Gera panes aleatórias para as aeronaves para popular o dashboard.
"""
import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.panes.models import Pane

SISTEMAS = ["COM", "NAV", "ENG", "HUD", "ELEC", "ARM"]
DESCRICOES = [
    "Falha na comunicação UHF", "Divergência no GPS", "Vazamento hidráulico trem de pouso",
    "HUD piscando intermitente", "Luz de gerador acesa", "Falha no disparo do casulo"
]

async def run(session: AsyncSession):
    print("🚀 [Panes] Gerando panes aleatórias...")
    
    # Buscar Aeronaves e Usuários
    res_acfts = await session.execute(select(Aeronave))
    acfts = res_acfts.scalars().all()
    
    res_users = await session.execute(select(Usuario))
    users = res_users.scalars().all()
    
    if not acfts or not users:
        print("   ! Aeronaves ou usuários não encontrados. Pulando panes.")
        return

    admin = users[0]

    for _ in range(10):  # Criar 10 panes aleatórias
        acft = random.choice(acfts)
        pane = Pane(
            id=uuid.uuid4(),
            aeronave_id=acft.id,
            sistema_subsistema=random.choice(SISTEMAS),
            descricao=random.choice(DESCRICOES),
            status="ABERTA",
            data_abertura=datetime.now() - timedelta(hours=random.randint(1, 100)),
            criado_por_id=admin.id,
            ativo=True
        )
        session.add(pane)
    
    await session.flush()
