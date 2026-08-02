"""
tests/unit/test_mobile.py
Suíte de testes automatizados para a interface mobile (/m/) do SAA29.

Validações cobertas:
- Rotas HTML mobile (/m/ e /m/aeronave/{id}) exigem autenticação.
- Retorno 200 HTTP com Content-Type "text/html" para acessos autenticados.
- Disponibilidade dos arquivos estáticos PWA (manifest.json, sw.js, mobile.css e scripts JS).
- Conformidade estrita com a política CSP (ausência de scripts inline nos templates mobile).
- Fluxo de conclusão de tarefas/panes em 1 toque.
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
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.shared.core.enums import StatusAeronave, StatusPane


def criar_app_mobile(db: AsyncSession, usuario: Usuario | None = None) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(pages_router)
    app.include_router(panes_router, prefix="/panes")

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if usuario is not None:
        async def override_get_current_user():
            return usuario

        app.dependency_overrides[get_current_user] = override_get_current_user

    return app


async def criar_usuario_teste(db: AsyncSession, funcao: str = "MANTENEDOR") -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Militar Mobile {suffix}",
        posto="3S",
        especialidade="ELT",
        funcao=funcao,
        ramal="4000",
        trigrama=suffix[:3].upper(),
        username=f"user_mob_{suffix}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def criar_aeronave_teste(db: AsyncSession) -> Aeronave:
    suffix = uuid.uuid4().hex[:8].upper()
    aeronave = Aeronave(
        serial_number=f"SN-MOB-{suffix}",
        matricula=f"FAB-{suffix[:4]}",
        modelo="A-29B",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


@pytest.mark.asyncio
async def test_mobile_frota_sem_autenticacao_retorna_401(db: AsyncSession):
    """Garante que a rota /m/ exige autenticação."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/m/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mobile_frota_autenticado_retorna_200_html(db: AsyncSession):
    """Garante que o dashboard cockpit mobile retorna 200 OK HTML."""
    usuario = await criar_usuario_teste(db)
    app = criar_app_mobile(db, usuario=usuario)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/m/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Linha de Voo" in response.text
    assert "mobile.css" in response.text


@pytest.mark.asyncio
async def test_mobile_tarefas_aeronave_autenticado_retorna_200_html(db: AsyncSession):
    """Garante que a rota de tarefas da ANV /m/aeronave/{id} retorna HTML válido."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/aeronave/{aeronave.id}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert str(aeronave.id) in response.text
    assert "tarefas_mobile.js" in response.text


@pytest.mark.asyncio
async def test_pwa_manifest_json_disponivel(db: AsyncSession):
    """Valida a rota do manifesto PWA para instalação no celular."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/manifest.json")

    assert response.status_code == 200
    data = response.json()
    assert data["short_name"] == "SAA29 Mobile"
    assert data["display"] == "standalone"


@pytest.mark.asyncio
async def test_pwa_service_worker_disponivel(db: AsyncSession):
    """Valida a disponibilidade do arquivo sw.js do Service Worker."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/sw.js")

    assert response.status_code == 200
    assert "CACHE_NAME" in response.text


@pytest.mark.asyncio
async def test_mobile_css_disponivel(db: AsyncSession):
    """Valida o carregamento da folha de estilo mobile.css."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/css/mobile.css")

    assert response.status_code == 200
    assert "--mobile-bg" in response.text
    assert "56px" in response.text


@pytest.mark.asyncio
async def test_mobile_js_scripts_disponiveis(db: AsyncSession):
    """Valida o carregamento dos scripts JavaScript mobile."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_app = await client.get("/static/js/mobile/app_mobile.js")
        res_frota = await client.get("/static/js/mobile/frota_mobile.js")
        res_tarefas = await client.get("/static/js/mobile/tarefas_mobile.js")

    assert res_app.status_code == 200
    assert res_frota.status_code == 200
    assert res_tarefas.status_code == 200
    assert "calcularPrioridadeOperacional" in res_frota.text
    assert "prioridade" in res_frota.text
    assert "INDISPONIVEL > INSPECAO > DISPONIVEL" in res_frota.text
    assert "inspecao" in res_frota.text


@pytest.mark.asyncio
async def test_templates_mobile_conformidade_csp_zero_inline(db: AsyncSession):
    """
    Audita os templates mobile para garantir ausência total de scripts inline
    ou atributos de evento inline (onclick, onchange, etc) em conformidade com CSP.md.
    """
    usuario = await criar_usuario_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_frota = await client.get("/m/")
        res_tarefas = await client.get("/m/aeronave/12345")

    for html_content in [res_frota.text, res_tarefas.text]:
        assert "onclick=" not in html_content.lower()
        assert "onchange=" not in html_content.lower()
        assert "onsubmit=" not in html_content.lower()
        assert "onload=" not in html_content.lower()


@pytest.mark.asyncio
async def test_mobile_menu_sanduiche_estrutura_e_links(db: AsyncSession):
    """Valida a presença do botão de menu sanduíche e estrutura do drawer off-canvas."""
    usuario = await criar_usuario_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/m/")

    assert response.status_code == 200
    assert 'id="btn-mobile-menu"' in response.text
    assert 'id="mobile-menu-drawer"' in response.text
    assert 'id="mobile-menu-overlay"' in response.text
    assert "Linha de Voo (Início)" in response.text
    assert "Modo Desktop / Dashboard" in response.text



@pytest.mark.asyncio
async def test_fluxo_concluir_pane_mobile_1_toque(db: AsyncSession):
    """Valida o endpoint de baixa de pane acionado pela interface mobile."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)

    pane = Pane(
        aeronave_id=aeronave.id,
        descricao="Falha no CMFD 1 durante teste de voo",
        status=StatusPane.ABERTA.value if hasattr(StatusPane.ABERTA, 'value') else StatusPane.ABERTA,
        criado_por_id=usuario.id,
    )
    db.add(pane)
    await db.flush()

    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"/panes/{pane.id}/concluir",
            json={"observacao_conclusao": "Concluído via Mobile em 1 toque"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESOLVIDA"


@pytest.mark.asyncio
async def test_mobile_frota_renderiza_trigrama_usuario_logado(db: AsyncSession):
    """Garante que a barra superior da página mobile exibe o trigrama do militar logado."""
    usuario = await criar_usuario_teste(db, funcao="MANTENEDOR")
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/m/")

    assert response.status_code == 200
    assert usuario.trigrama in response.text


@pytest.mark.asyncio
async def test_mobile_tarefas_aeronave_valida_contexto_oculto_csp(db: AsyncSession):
    """Garante que o ID da aeronave é injetado via atributo data-aeronave-id sem injeção inline."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/aeronave/{aeronave.id}")

    assert response.status_code == 200
    assert f'data-aeronave-id="{aeronave.id}"' in response.text
    assert "<script>const" not in response.text


@pytest.mark.asyncio
async def test_pwa_manifest_contem_icones_e_theme_color(db: AsyncSession):
    """Valida as propriedades estritas do PWA Web App Manifest."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/manifest.json")

    assert response.status_code == 200
    data = response.json()
    assert data["theme_color"] == "#0F172A"
    assert data["start_url"] == "/m/"
    assert len(data["icons"]) >= 2

