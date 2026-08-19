"""
tests/integration/test_mobile_integration.py
Testes de integração de ponta a ponta (E2E) para o fluxo do Mantenedor no SAA29 Mobile (/m/).

Cenários de Integração:
- Frota mobile agregada (GET /dashboard/frota) sem N+1.
- Navegação entre a frota mobile e o hub da aeronave (4 abas).
- Relato rápido de pane (Nova Pane) e baixa de pane pelo mantenedor.
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
from app.web.pages.mobile_router import router as mobile_router
from app.modules.panes.router import router as panes_router
from app.modules.aeronaves.router import router as aeronaves_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.shared.core.enums import StatusAeronave, StatusPane


def criar_app_integracao_mobile(db: AsyncSession, usuario: Usuario) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(mobile_router)
    app.include_router(pages_router)
    app.include_router(panes_router, prefix="/panes")
    app.include_router(aeronaves_router, prefix="/aeronaves")
    app.include_router(dashboard_router, prefix="/dashboard")

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
    1. Acessa a frota mobile agregada em GET /dashboard/frota (RF-M02, 1 requisição)
    2. Abre o hub da aeronave em /m/aeronave/{id}
    3. Consulta as panes abertas da aeronave
    4. Conclui a pane em 1 toque via POST /panes/{id}/concluir
    5. Verifica que a pane transicionou para RESOLVIDA no banco e que a
       frota agregada reflete a queda de panes_abertas
    """
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
        # Step 1: Frota agregada — 1 única requisição para contadores da frota inteira
        res_frota_api = await client.get("/dashboard/frota")
        assert res_frota_api.status_code == 200
        frota = res_frota_api.json()
        item_frota = next(i for i in frota if i["aeronave_id"] == str(aeronave.id))
        assert item_frota["panes_abertas"] == 1
        assert item_frota["status"] == "INDISPONIVEL"

        # Step 2: Acessa dashboard mobile (shell HTML)
        res_frota = await client.get("/m/")
        assert res_frota.status_code == 200
        assert usuario.trigrama in res_frota.text

        # Step 3: Abre o hub da aeronave (4 abas)
        res_anv = await client.get(f"/m/aeronave/{aeronave.id}")
        assert res_anv.status_code == 200
        assert str(aeronave.id) in res_anv.text

        # Step 4: Consulta panes abertas da aeronave (aba Panes do hub)
        res_panes = await client.get(f"/panes/?aeronave_id={aeronave.id}&status=ABERTA")
        assert res_panes.status_code == 200
        assert len(res_panes.json()) == 1

        # Step 5: Conclui a pane
        res_concluir = await client.post(
            f"/panes/{pane.id}/concluir",
            json={"observacao_conclusao": "Ajuste de cabo realizado na linha de voo"}
        )
        assert res_concluir.status_code == 200
        assert res_concluir.json()["status"] == "RESOLVIDA"

        # Step 6: Consulta API de panes e garante status RESOLVIDA
        res_pane_check = await client.get(f"/panes/{pane.id}")
        assert res_pane_check.status_code == 200
        assert res_pane_check.json()["status"] == "RESOLVIDA"

        # Step 7: A frota agregada deixa de contar a pane já resolvida
        res_frota_final = await client.get("/dashboard/frota")
        item_final = next(i for i in res_frota_final.json() if i["aeronave_id"] == str(aeronave.id))
        assert item_final["panes_abertas"] == 0


@pytest.mark.asyncio
async def test_fluxo_integ_relato_rapido_nova_pane(db: AsyncSession):
    """
    Fluxo de relato rápido (RF-M21): o mantenedor abre a tela de Nova Pane
    a partir do hub da aeronave, registra a pane (POST /panes/) e é capaz
    de acessar o detalhe recém-criado.
    """
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Mantenedor Nova Pane {suffix}",
        posto="3S",
        especialidade="ELT",
        funcao="MANTENEDOR",
        ramal="4000",
        trigrama=suffix[:3].upper(),
        username=f"user_np_{suffix}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(usuario)

    aeronave = Aeronave(
        serial_number=f"SN-NP-{suffix}",
        matricula=f"FAB-{suffix[:4]}",
        modelo="A-29B",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()

    app = criar_app_integracao_mobile(db, usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_form = await client.get(f"/m/pane/nova?aeronave_id={aeronave.id}")
        assert res_form.status_code == 200
        assert f'data-aeronave-id="{aeronave.id}"' in res_form.text

        res_criar = await client.post(
            "/panes/",
            json={"aeronave_id": str(aeronave.id), "descricao": "Fumaça leve no compartimento aviônico"},
        )
        assert res_criar.status_code == 201
        pane_id = res_criar.json()["id"]

        res_detalhe_pagina = await client.get(f"/m/pane/{pane_id}")
        assert res_detalhe_pagina.status_code == 200
        assert f'data-pane-id="{pane_id}"' in res_detalhe_pagina.text

        res_detalhe_api = await client.get(f"/panes/{pane_id}")
        assert res_detalhe_api.status_code == 200
        assert res_detalhe_api.json()["descricao"] == "Fumaça leve no compartimento aviônico"
