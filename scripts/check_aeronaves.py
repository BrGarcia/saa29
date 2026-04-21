import asyncio
from sqlalchemy import select
from app.bootstrap.database import get_session_factory
import app.modules.aeronaves.models
from app.modules.aeronaves.models import Aeronave

async def check_aeronaves():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Aeronave))
        aeronaves = result.scalars().all()
        print(f"✈️  Aeronaves no banco: {len(aeronaves)}")
        for ac in aeronaves:
            print(f" - {ac.matricula} (id: {ac.id})")

if __name__ == "__main__":
    asyncio.run(check_aeronaves())
