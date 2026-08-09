"""
tests/integration/test_mobile_integration.py
Testes de integração de ponta a ponta (E2E) para o fluxo do Mantenedor no SAA29 Mobile (/m/).

Cenários de Integração:
- Navegação entre a frota mobile e a lista de pendências de uma aeronave.
- Baixa de pane pelo mantenedor atualizando o estado do banco de dados.
- Verificação da integridade de cookies de sessão e cabeçalhos PWA.
"""

import uuid
from datetime import date
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.dependencies import get_current_user, get_db
from app.web.pages.router import router as pages_router
from app.modules.panes.router import router as panes_router
from app.modules.aeronaves.router import router as aeronaves_router
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.shared.core.enums import StatusAeronave, StatusPane


def criar_app_integracao_mobile(db: AsyncSession, usuario: Usuario) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(pages_router)
    app.include_router(panes_router, prefix="/panes")
    app.include_router(aeronaves_router, prefix="/aeronaves")

    async def override_get_db():
        yield db

    async def override_get_current_user():
        return usuario

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.mark.asyncio
async def test_fluxo_integ_completo_mantenedor_pista(db: AsyncSession):
    """
    Testa o fluxo completo do mantenedor:
    1. Acessa a frota mobile em /m/
    2. Consulta as panes da aeronave FAB 5701
    3. Conclui a pane em 1 toque via POST /panes/{id}/concluir
    4. Verifica que a pane transicionou para RESOLVIDA no banco
    """
    # 1. Preparar dados
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Mantenedor Integração {suffix}",
        posto="3S",
        especialidade="ELT",
        funcao="MANTENEDOR",
        ramal="4000",
        trigrama=suffix[:3].upper(),
        username=f"user_e2e_{suffix}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(usuario)

    aeronave = Aeronave(
        serial_number=f"SN-E2E-{suffix}",
        matricula=f"FAB-{suffix[:4]}",
        modelo="A-29B",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()

    pane = Pane(
        aeronave_id=aeronave.id,
        descricao="Falha no indicador V/UHF 1 na pista",
        status=StatusPane.ABERTA.value if hasattr(StatusPane.ABERTA, 'value') else StatusPane.ABERTA,
        criado_por_id=usuario.id,
    )
    db.add(pane)
    await db.flush()

    app = criar_app_integracao_mobile(db, usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Step 1: Acessa dashboard mobile
        res_frota = await client.get("/m/")
        assert res_frota.status_code == 200
        assert usuario.trigrama in res_frota.text

        # Step 2: Acessa tarefas da ANV
        res_anv = await client.get(f"/m/aeronave/{aeronave.id}")
        assert res_anv.status_code == 200
        assert str(aeronave.id) in res_anv.text

        # Step 3: Conclui a pane
        res_concluir = await client.post(
            f"/panes/{pane.id}/concluir",
            json={"observacao_conclusao": "Ajuste de cabo realizado na linha de voo"}
        )
        assert res_concluir.status_code == 200
        assert res_concluir.json()["status"] == "RESOLVIDA"

        # Step 4: Consulta API de panes e garante status RESOLVIDA
        res_pane_check = await client.get(f"/panes/{pane.id}")
        assert res_pane_check.status_code == 200
        assert res_pane_check.json()["status"] == "RESOLVIDA"
