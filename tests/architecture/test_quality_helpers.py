import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario

# --- Módulos que serão criados/refatorados ---
# from app.shared.core import helpers # Planejado

@pytest.mark.asyncio
async def test_helper_buscar_aeronave_por_matricula(db: AsyncSession):
    """
    TESTE DE QUALIDADE: Valida se o novo helper de busca de aeronave funciona.
    (Deve falhar inicialmente por falta do helper)
    """
    from app.shared.core import helpers
    
    # Setup
    from datetime import date
    anv = Aeronave(id=uuid.uuid4(), matricula="5900", serial_number="SN5900", modelo="A-29", data_inicio_operacao=date(2020, 1, 1))
    db.add(anv)
    await db.commit()

    # Execução via helper
    resultado = await helpers.buscar_aeronave_por_matricula(db, "5900")
    assert resultado is not None
    assert resultado.matricula == "5900"

@pytest.mark.asyncio
async def test_ensure_default_aeronaves_bulk_efficiency(db: AsyncSession):
    """
    TESTE DE PERFORMANCE: Valida se a inicialização da frota é eficiente.
    (Otimização de loop N queries -> 1 query)
    """
    from app.bootstrap.main import _ensure_default_aeronaves, FROTA_PADRAO
    from sqlalchemy import select, func
    
    # 1. Executar a inicialização
    # Patch get_session_factory to return a factory that produces our test session
    from unittest.mock import patch, MagicMock
    from app.bootstrap.database import get_session_factory
    
    with patch("app.bootstrap.database.get_session_factory") as mock_factory:
        # Mocking the async session factory
        mock_session = MagicMock()
        # We need to mock the async context manager behavior
        mock_factory.return_value.return_value.__aenter__.return_value = db
        mock_factory.return_value.return_value.__aexit__.return_value = MagicMock()
        
        await _ensure_default_aeronaves()
    
    # 2. Verificar se os dados foram persistidos
    result = await db.execute(select(func.count(Aeronave.id)).where(Aeronave.matricula.in_(FROTA_PADRAO)))
    count = result.scalar()
    assert count == len(FROTA_PADRAO)

