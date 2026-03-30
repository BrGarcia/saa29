"""
scripts/seed_30_panes.py
Gera 30 panes aleatórias para teste de interface e filtros.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database import get_session_factory

# Importar TODOS os módulos para resolver os nomes das classes em referências de string cruzadas
import app.auth.models
import app.aeronaves.models
import app.equipamentos.models
import app.panes.models

from app.auth.models import Usuario
from app.aeronaves.models import Aeronave
from app.panes.models import Pane, PaneResponsavel
from app.core.enums import StatusPane

SISTEMAS = [
    ("COM / VUHF", ["Rádio não transmite em 121.5 MHz", "Ruído excessivo na recepção", "Falha no autoteste do rádio 1", "Painel de áudio com mau contato"]),
    ("NAV / GPS", ["GPS 1 perdendo sinal intermitente", "Erro de base de dados desatualizada", "Antena GPS com infiltração"]),
    ("NAV / IFF", ["IFF não responde modo 4", "Falha de código modo C", "Sem indicação de transponder no MFD"]),
    ("ELE / GERACAO", ["Mensagem GEN 1 FAIL no painel", "Bateria principal com carga baixa", "Inversor estático aquecendo"]),
    ("ARM / SMS", ["Falha de comunicação com estação 3", "Lançador de flares travado", "Erro de indicação de munição no MFD"]),
    ("MISC / AR COND", ["Ar condicionado não refrigera", "Ventilador da cabine ruidoso", "Sensor de temperatura inoperante"]),
]

async def seed_panes():
    AsyncSessionLocal = get_session_factory()
    async with AsyncSessionLocal() as session:
        # 1. Buscar Aeronaves
        res_aeronaves = await session.execute(select(Aeronave))
        aeronaves = res_aeronaves.scalars().all()
        if not aeronaves:
            print("❌ Erro: Nenhuma aeronave cadastrada. Rode o scripts/seed.py primeiro.")
            return

        # 2. Buscar Usuários (para criador e responsáveis)
        res_usuarios = await session.execute(select(Usuario))
        usuarios = res_usuarios.scalars().all()
        admin = next((u for u in usuarios if u.funcao == "ADMINISTRADOR"), usuarios[0])
        mantenedores = [u for u in usuarios if u.funcao in ["MANTENEDOR", "ENCARREGADO"]]

        print(f"🚀 Gerando 30 panes aleatórias...")

        for i in range(100):
            aeronave = random.choice(aeronaves)
            sistema, descricoes = random.choice(SISTEMAS)
            descricao = random.choice(descricoes)
            
            # Variar data de abertura (nos últimos 15 dias)
            dias_atras = random.randint(0, 15)
            data_abertura = datetime.now() - timedelta(days=dias_atras, hours=random.randint(1, 23))
            
            status = random.choice([StatusPane.ABERTA, StatusPane.RESOLVIDA])
            
            pane = Pane(
                aeronave_id=aeronave.id,
                sistema_subsistema=sistema,
                descricao=descricao,
                status=status.value,
                criado_por_id=admin.id,
                data_abertura=data_abertura,
                ativo=True
            )
            
            if status == StatusPane.RESOLVIDA:
                pane.data_conclusao = data_abertura + timedelta(hours=random.randint(2, 48))
                pane.observacao_conclusao = "Manutenção realizada conforme manual técnico. Teste funcional OK."
                pane.concluido_por_id = random.choice(mantenedores).id if mantenedores else admin.id

            session.add(pane)
            await session.flush() # Gerar ID da pane

            # Adicionar responsável se for RESOLVIDA (pelo menos um deve estar lá)
            if status == StatusPane.RESOLVIDA and mantenedores:
                resp = random.choice(mantenedores)
                session.add(PaneResponsavel(
                    pane_id=pane.id,
                    usuario_id=resp.id,
                    papel=resp.funcao
                ))

        await session.commit()
        print(f"✅ 30 panes geradas com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed_panes())
