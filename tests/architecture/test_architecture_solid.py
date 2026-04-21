import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.core import exceptions as domain_exc

@pytest.mark.asyncio
async def test_domain_exception_handling_manual(db: AsyncSession):
    """
    TESTE DE DOMÍNIO: Verifica se as novas exceções de domínio podem ser disparadas.
    (Deve falhar inicialmente porque app.core.exceptions ainda não existe)
    """
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError) as excinfo:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada")
    assert excinfo.value.status_code == 404
    assert "Aeronave não encontrada" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_global_exception_handler_integration(client: AsyncClient, db: AsyncSession, usuario_e_token: dict):
    """
    TESTE DE INTEGRAÇÃO: Verifica se o Global Handler converte a exceção de domínio 
    em uma resposta HTTP formatada corretamente (sem try/except no router).
    """
    # Simulando um ID que não existe para disparar 404 via exceção de domínio
    random_id = uuid.uuid4()
    response = await client.get(
        f"/equipamentos/inventario/{random_id}",
        headers=usuario_e_token["headers"]
    )
    
    # O objetivo é que o service lance EntidadeNaoEncontradaError 
    # e o FastAPI retorne 404 automaticamente.
    assert response.status_code == 404
    assert "Aeronave não encontrada" in response.json()["detail"]

@pytest.mark.asyncio
async def test_conflito_inventario_exception(client: AsyncClient, db: AsyncSession):
    """
    TESTE DE CONFLITO: Verifica se erros de regra de negócio (conflito) retornam 409.
    """
    with pytest.raises(domain_exc.ConflitoNegocioError) as excinfo:
        raise domain_exc.ConflitoNegocioError("Item já instalado")
    assert excinfo.value.status_code == 409
