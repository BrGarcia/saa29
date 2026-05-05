"""
scripts/seed/seed_sistemas_ata.py
Garante o catálogo de Sistemas ATA no banco.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.panes.models import SistemaAta

SISTEMAS_ATA = [
    {"codigo": "22", "descricao": "VOO AUTOMÁTICO"},
    {"codigo": "23", "descricao": "COMUNICAÇÃO"},
    {"codigo": "27", "descricao": "COMANDOS DE VOO"},
    {"codigo": "31", "descricao": "INDICAÇÃO E REGISTRO"},
    {"codigo": "34", "descricao": "RÁDIO-NAVEGAÇÃO"},
    {"codigo": "42", "descricao": "AVIÔNICA INTEGRADA"},
    {"codigo": "94", "descricao": "HOTAS"},
    {"codigo": "97", "descricao": "SISTEMA DE GRAVAÇÃO"},
]

async def run(session: AsyncSession) -> None:
    print("🚀 [Sistemas ATA] Garantindo catálogo de Sistemas ATA...")
    count = 0
    for ata in SISTEMAS_ATA:
        result = await session.execute(select(SistemaAta).where(SistemaAta.codigo == ata["codigo"]))
        db_ata = result.scalar_one_or_none()
        if not db_ata:
            novo_ata = SistemaAta(
                codigo=ata["codigo"],
                descricao=ata["descricao"]
            )
            session.add(novo_ata)
            count += 1
            print(f"   + Sistema ATA {ata['codigo']} adicionado ({ata['descricao']}).")
        else:
            if db_ata.descricao != ata["descricao"]:
                db_ata.descricao = ata["descricao"]
                print(f"   ~ Sistema ATA {ata['codigo']} atualizado para ({ata['descricao']}).")

    if count > 0:
        await session.flush()
    print("✅ Seed de Sistemas ATA concluído.")
