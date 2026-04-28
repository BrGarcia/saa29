"""
scripts/seed/seed_vencimentos.py
Configura Tipos de Controle, Regras de Periodicidade e aplica esses controles aos Itens (S/N) instalados.
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.vencimentos.models import TipoControle, EquipamentoControle, ControleVencimento
from app.modules.equipamentos.models import ModeloEquipamento, ItemEquipamento
from app.shared.core.enums import StatusVencimento

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
                print(f"   + Regra de Vencimento criada: PN {pn} -> {ctrl} ({meses}m)")
    
    await session.flush()

    print("🚀 [Vencimentos] Aplicando regras aos equipamentos físicos (S/N) instalados...")
    
    # 3. Aplicar as regras aos itens físicos (ControleVencimento)
    res_regras = await session.execute(select(EquipamentoControle))
    regras_ativas = res_regras.scalars().all()
    
    # Mapear modelo_id para lista de regras (tipo_controle_id)
    regras_map = {}
    for regra in regras_ativas:
        if regra.modelo_id not in regras_map:
            regras_map[regra.modelo_id] = []
        regras_map[regra.modelo_id].append(regra.tipo_controle_id)

    res_itens = await session.execute(select(ItemEquipamento))
    itens = res_itens.scalars().all()

    controles_gerados = 0
    for item in itens:
        tipos_aplicaveis = regras_map.get(item.modelo_id, [])
        for tipo_id in tipos_aplicaveis:
            # Verifica se já existe o controle para este item
            res_venc = await session.execute(
                select(ControleVencimento).where(
                    ControleVencimento.item_id == item.id,
                    ControleVencimento.tipo_controle_id == tipo_id
                )
            )
            if not res_venc.scalar_one_or_none():
                venc = ControleVencimento(
                    id=uuid.uuid4(),
                    item_id=item.id,
                    tipo_controle_id=tipo_id,
                    status=StatusVencimento.VENCIDO.value, # Status inicial VENCIDO para testes e validação visual
                    origem="PADRAO"
                )
                session.add(venc)
                controles_gerados += 1
                
    await session.flush()
    print(f"   ✅ Total: {controles_gerados} controles de vencimento gerados e associados aos itens.")
