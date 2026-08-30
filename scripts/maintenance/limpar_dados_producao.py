"""
scripts/maintenance/limpar_dados_producao.py

Limpa todos os dados operacionais temporários de Panes e Inspeções no ambiente de produção,
mantendo intactos o cadastro da Frota (Aeronaves), o Inventário de Equipamentos (Loc, Slot, PN, SN, etc.),
o Catálogo de Tipos de Inspeção, Usuários e o Módulo de Publicações.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from sqlalchemy import delete, update
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

from app.modules.inspecoes.models import Inspecao, InspecaoTarefa, InspecaoEventoTipo, TarefaTemplate, TarefaCatalogo
from app.modules.panes.models import Pane, Anexo, PaneResponsavel
from app.modules.aeronaves.models import Aeronave
from app.shared.core.enums import StatusAeronave

async def limpar_dados():
    print("🧹 [Produção] Iniciando limpeza de Panes, Inspeções e Tarefas Template...")
    
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Limpar tarefas instanciadas, templates e catálogo de tarefas
        res_t = await session.execute(delete(InspecaoTarefa))
        res_tmpl = await session.execute(delete(TarefaTemplate))
        res_cat = await session.execute(delete(TarefaCatalogo))
        res_et = await session.execute(delete(InspecaoEventoTipo))
        res_i = await session.execute(delete(Inspecao))
        
        # 2. Limpar anexos, responsáveis e panes
        res_an = await session.execute(delete(Anexo))
        res_pr = await session.execute(delete(PaneResponsavel))
        res_p = await session.execute(delete(Pane))

        # 3. Resetar o status de todas as aeronaves ativas para DISPONIVEL
        res_acft = await session.execute(
            update(Aeronave)
            .where(Aeronave.status != StatusAeronave.INATIVA)
            .values(status=StatusAeronave.DISPONIVEL)
        )

        await session.commit()

        print("✅ Clean-up concluído com sucesso:")
        print(f"   - Inspeções removidas: {res_i.rowcount}")
        print(f"   - Tarefas instanciadas removidas: {res_t.rowcount}")
        print(f"   - Tarefas template removidas: {res_tmpl.rowcount}")
        print(f"   - Tarefas do catálogo removidas: {res_cat.rowcount}")
        print(f"   - Vínculos de eventos de inspeção removidos: {res_et.rowcount}")
        print(f"   - Panes removidas: {res_p.rowcount}")
        print(f"   - Anexos de panes removidos: {res_an.rowcount}")
        print(f"   - Responsáveis de panes removidos: {res_pr.rowcount}")
        print(f"   - Aeronaves atualizadas para DISPONIVEL: {res_acft.rowcount}")
        print("🛡️ Frota, Equipamentos (PN, SN, Slot, Loc) e Tipos de Inspeção (Y, 2A, 2C, etc.) foram mantidos INTACTOS.")

if __name__ == "__main__":
    asyncio.run(limpar_dados())
