"""
app/bootstrap/seed.py
Rotinas de inicialização de dados (Seed) para o banco de dados.
"""

from datetime import date
from sqlalchemy import select
from app.modules.aeronaves.models import Aeronave
from app.bootstrap.database import get_session_factory

FROTA_PADRAO = (
    "5902", "5905", "5906", "5912", "5914", "5915", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
)

async def ensure_default_aeronaves() -> None:
    """
    Garante que as aeronaves da frota padrão existam no banco de dados.
    """
    async with get_session_factory()() as session:
        try:
            # 1. Buscar todas as matrículas existentes da frota padrão
            result = await session.execute(
                select(Aeronave.matricula).where(Aeronave.matricula.in_(FROTA_PADRAO))
            )
            existentes = {row[0] for row in result.all()}

            # 2. Identificar quais faltam e adicionar
            faltantes = [m for m in FROTA_PADRAO if m not in existentes]
            
            if faltantes:
                print(f"Seed: Adicionando {len(faltantes)} aeronaves à frota padrão...")
                for matricula in faltantes:
                    session.add(
                        Aeronave(
                            matricula=matricula,
                            serial_number=f"SN-{matricula}",
                            modelo="A-29",
                            data_inicio_operacao=date(2020, 1, 1)
                        )
                    )
                await session.commit()
        except Exception as e:
            print(f"Erro ao inicializar frota: {e}")
            await session.rollback()
            raise
