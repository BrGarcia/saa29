import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.modules.auth.models
import app.modules.aeronaves.models
import app.modules.panes.models
import app.modules.equipamentos.models

from app.bootstrap.database import get_session_factory
from app.modules.equipamentos.service import montar_matriz_vencimentos

async def test():
    factory = get_session_factory()
    async with factory() as db:
        print("Buscando matriz...")
        data = await montar_matriz_vencimentos(db)
        print(f"Resultado: {len(data['aeronaves'])} aeronaves encontradas.")
        print(f"Equipamentos no cabeçalho: {list(data['cabecalho'].keys())}")
        
        for anv in data['aeronaves']:
            total_ctrls = sum(len(s['controles']) for s in anv['slots'])
            print(f"- ANV {anv['matricula']}: {len(anv['slots'])} slots, {total_ctrls} controles.")

if __name__ == "__main__":
    asyncio.run(test())
