import asyncio
from app.bootstrap.database import get_session_factory
from app.modules.inspecoes import service, schemas

async def test():
    async with get_session_factory()() as session:
        inspecoes = await service.listar_inspecoes(session, schemas.FiltroInspecao())
        for inspecao in inspecoes:
            print(inspecao.id)

asyncio.run(test())
