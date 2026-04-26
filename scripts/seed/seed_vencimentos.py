"""
scripts/seed/seed_vencimentos.py
Configura Tipos de Controle e Periodicidades (Regras de Negócio).
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.vencimentos.models import TipoControle, EquipamentoControle
from app.modules.equipamentos.models import ModeloEquipamento

TIPOS = {
    "CRI": "Controle de Revisão de Itens",
    "TLV": "Tempo de Limite de Vida",
    "TBO": "Time Between Overhaul",
    "RBA": "Revisão Baseada em Anos",
    "DWL": "Diretiva Semanal",
}

async def run(session: AsyncSession):
    print("🚀 [Vencimentos] Configurando tipos de controle e regras...")
    
    # 1. Criar Tipos
    tp_map = {}
    for nome, desc in TIPOS.items():
        res = await session.execute(select(TipoControle).where(TipoControle.nome == nome))
        obj = res.scalar_one_or_none()
        if not obj:
            obj = TipoControle(id=uuid.uuid4(), nome=nome, descricao=desc)
            session.add(obj)
        tp_map[nome] = obj
    await session.flush()

    # 2. Configurar Algumas Regras de Exemplo (PN -> Tipo -> Meses)
    # Buscamos os modelos já criados (pelo seed_equipamentos)
    res_mod = await session.execute(select(ModeloEquipamento))
    modelos = {m.part_number: m for m in res_mod.scalars().all()}

    REGRAS = [
        ("453-5000-710", "CRI", 12),  # ELT
        ("453-5000-710", "TLV", 60),  # ELT
        ("174521-10-01", "CRI", 24),  # VADR
        ("MA902B-02", "CRI", 36),     # MDP
    ]

    for pn, ctrl, meses in REGRAS:
        if pn in modelos:
            mod = modelos[pn]
            tipo = tp_map[ctrl]
            res_reg = await session.execute(
                select(EquipamentoControle).where(
                    EquipamentoControle.modelo_id == mod.id,
                    EquipamentoControle.tipo_controle_id == tipo.id
                )
            )
            if not res_reg.scalar_one_or_none():
                regra = EquipamentoControle(
                    id=uuid.uuid4(),
                    modelo_id=mod.id,
                    tipo_controle_id=tipo.id,
                    periodicidade_meses=meses
                )
                session.add(regra)
                print(f"   + Regra: PN {pn} -> {ctrl} ({meses}m)")
    
    await session.flush()
