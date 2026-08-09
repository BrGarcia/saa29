"""
scripts/maintenance/limpar_dados_producao.py

Limpa todos os dados operacionais temporários de Panes e Inspeções no ambiente de produção,
mantendo intactos o cadastro da Frota (Aeronaves), o Inventário de Equipamentos (Loc, Slot, PN, SN, etc.),
o Catálogo de Tipos de Inspeção, Usuários e o Módulo de Publicações.
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from sqlalchemy import delete
from app.bootstrap.database import get_session_factory

# Importar TODOS os modelos para resolução do SQLAlchemy
import app.modules.auth.models         # noqa: F401
import app.modules.efetivo.models      # noqa: F401
import app.modules.aeronaves.models    # noqa: F401
import app.modules.equipamentos.models # noqa: F401
import app.modules.vencimentos.models  # noqa: F401
import app.modules.panes.models        # noqa: F401
import app.modules.inspecoes.models    # noqa: F401
import app.modules.calendario.models   # noqa: F401
import app.modules.publicacoes.models  # noqa: F401

from app.modules.inspecoes.models import Inspecao, InspecaoTarefa, InspecaoEventoTipo
from app.modules.panes.models import Pane, Anexo, PaneResponsavel

async def limpar_dados():
    print("🧹 [Produção] Iniciando limpeza de Panes e Inspeções...")
    
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Limpar tarefas de inspeção e vínculos
        res_t = await session.execute(delete(InspecaoTarefa))
        res_et = await session.execute(delete(InspecaoEventoTipo))
        res_i = await session.execute(delete(Inspecao))
        
        # 2. Limpar anexos, responsáveis e panes
        res_an = await session.execute(delete(Anexo))
        res_pr = await session.execute(delete(PaneResponsavel))
        res_p = await session.execute(delete(Pane))

        await session.commit()

        print("✅ Clean-up concluído com sucesso:")
        print(f"   - Inspeções removidas: {res_i.rowcount}")
        print(f"   - Tarefas de inspeção removidas: {res_t.rowcount}")
        print(f"   - Vínculos de eventos de inspeção removidos: {res_et.rowcount}")
        print(f"   - Panes removidas: {res_p.rowcount}")
        print(f"   - Anexos de panes removidos: {res_an.rowcount}")
        print(f"   - Responsáveis de panes removidos: {res_pr.rowcount}")
        print("🛡️ Frota (Aeronaves) e Equipamentos (PN, SN, Slot, Loc) foram mantidos INTACTOS.")

if __name__ == "__main__":
    asyncio.run(limpar_dados())
