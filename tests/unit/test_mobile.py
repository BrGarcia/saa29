"""
tests/unit/test_mobile.py
Suíte de testes automatizados para a interface mobile (/m/) do SAA29.

Validações cobertas:
- Rotas HTML mobile (/m/, /m/aeronave/{id}, /m/pane/nova, /m/pane/{id}) exigem autenticação.
- Retorno 200 HTTP com Content-Type "text/html" para acessos autenticados.
- Disponibilidade dos arquivos estáticos PWA (manifest.json, sw.js, ícones, mobile.css, JS mobile).
- Conformidade estrita com a política CSP (ausência de scripts inline nos templates mobile).
- Ausência de rota /m duplicada entre mobile_router.py e pages/router.py (achado #4).
- Fluxo de conclusão de pane em 1 toque, incluindo a regressão real de CSRF
  (achado #1) via HTTP com o CSRFMiddleware ativo, não apenas via override de dependency.
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
from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import Pane
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.shared.core.enums import StatusAeronave, StatusPane


def criar_app_mobile(db: AsyncSession, usuario: Usuario | None = None) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(mobile_router)
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


# ===========================================================================
# Rotas HTML — autenticação e render básico
# ===========================================================================

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
async def test_mobile_aeronave_hub_autenticado_retorna_200_html_com_4_abas(db: AsyncSession):
    """Garante que o hub /m/aeronave/{id} renderiza as 4 abas (RF-M10)."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/aeronave/{aeronave.id}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert str(aeronave.id) in response.text
    assert "aeronave_mobile.js" in response.text
    assert "panes_mobile.js" in response.text
    for rotulo in ("Panes", "Inspeções", "Vencimentos", "Inventário"):
        assert rotulo in response.text
    for aba in ("panes", "inspecoes", "vencimentos", "inventario"):
        assert f'data-tab="{aba}"' in response.text
        assert f'id="tab-{aba}"' in response.text


@pytest.mark.asyncio
async def test_mobile_pane_nova_sem_autenticacao_retorna_401(db: AsyncSession):
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/m/pane/nova?aeronave_id=12345")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mobile_pane_nova_autenticado_retorna_200_html(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/pane/nova?aeronave_id={aeronave.id}")

    assert response.status_code == 200
    assert f'data-aeronave-id="{aeronave.id}"' in response.text
    assert "panes_mobile.js" in response.text


@pytest.mark.asyncio
async def test_mobile_pane_detalhe_autenticado_retorna_200_html(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    app = criar_app_mobile(db, usuario=usuario)
    pane_id_falso = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/pane/{pane_id_falso}")

    assert response.status_code == 200
    assert f'data-pane-id="{pane_id_falso}"' in response.text


@pytest.mark.asyncio
async def test_mobile_inspecao_checklist_requer_autenticacao(db: AsyncSession):
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/inspecao/{uuid.uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mobile_inspecao_checklist_autenticado_retorna_200_html(db: AsyncSession):
    """Etapa 4: checklist de inspeção renderiza com o ID injetado via
    data-inspecao-id (sem HTML inline, mesma conformidade CSP das demais telas)."""
    usuario = await criar_usuario_teste(db)
    app = criar_app_mobile(db, usuario=usuario)
    inspecao_id_falso = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/inspecao/{inspecao_id_falso}")

    assert response.status_code == 200
    assert f'data-inspecao-id="{inspecao_id_falso}"' in response.text
    assert "inspecoes_mobile.js" in response.text


@pytest.mark.asyncio
async def test_mobile_drawer_nova_pane_usa_contexto_da_aeronave_quando_disponivel(db: AsyncSession):
    """RF-M92: o item 'Nova Pane' do drawer deixa de ser placeholder — no hub
    da aeronave, ele já aponta para o relato rápido daquela mesma aeronave."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/aeronave/{aeronave.id}")

    assert f"/m/pane/nova?aeronave_id={aeronave.id}" in response.text


def test_mobile_rotas_m_nao_duplicadas():
    """Achado #4: /m/ e /m/aeronave/{id} estavam definidos duas vezes
    (mobile_router.py e pages/router.py). O bloco morto foi removido de
    pages/router.py — cada rota deve aparecer só uma vez na aplicação real."""
    from collections import Counter
    from app.bootstrap.main import app as full_app

    paths_mobile = [
        r.path for r in full_app.routes
        if getattr(r, "path", "").startswith("/m") and getattr(r, "path", "") != "/m/publicacoes"
    ]
    contagem = Counter(paths_mobile)
    duplicadas = {p: c for p, c in contagem.items() if c > 1}
    assert duplicadas == {}, f"Rota(s) /m duplicada(s): {duplicadas}"


# ===========================================================================
# PWA — manifesto, ícones e Service Worker
# ===========================================================================

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
async def test_pwa_manifest_contem_icones_e_theme_color(db: AsyncSession):
    """Valida as propriedades estritas do PWA Web App Manifest."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/manifest.json")

    assert response.status_code == 200
    data = response.json()
    assert data["theme_color"] == "#0B1015"
    assert data["start_url"] == "/m/"
    assert len(data["icons"]) >= 2


def test_pwa_icones_existem_em_disco():
    """Achado #3: sem os arquivos, a instalação do PWA na tela inicial falhava."""
    from pathlib import Path

    for nome in ("icon-192.png", "icon-512.png", "apple-touch-icon.png"):
        caminho = Path(f"app/web/static/img/{nome}")
        assert caminho.exists(), f"Ícone {nome} não encontrado em disco."


@pytest.mark.asyncio
async def test_pwa_service_worker_estatico_disponivel(db: AsyncSession):
    """O arquivo físico do SW continua acessível também em /static/sw.js
    (é o caminho referenciado dentro de si mesmo/pela cache do PWA)."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/sw.js")

    assert response.status_code == 200
    assert "CACHE_NAME" in response.text


@pytest.mark.asyncio
async def test_pwa_service_worker_servido_na_raiz_com_scope_correto(db: AsyncSession):
    """Achado #2: app_mobile.js registra literalmente '/sw.js' — sem esta
    rota (servida por pages/router.py, sem prefixo), o registro do SW
    resultava em 404 e o PWA nunca instalava de fato."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/sw.js")

    assert response.status_code == 200
    assert response.headers.get("Service-Worker-Allowed") == "/"
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
    assert "--mobile-status-vencido" in response.text


@pytest.mark.asyncio
async def test_mobile_js_scripts_disponiveis(db: AsyncSession):
    """Valida o carregamento dos scripts JavaScript mobile."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_app = await client.get("/static/js/mobile/app_mobile.js")
        res_frota = await client.get("/static/js/mobile/frota_mobile.js")
        res_aeronave = await client.get("/static/js/mobile/aeronave_mobile.js")
        res_panes = await client.get("/static/js/mobile/panes_mobile.js")

    assert res_app.status_code == 200
    assert res_frota.status_code == 200
    assert res_aeronave.status_code == 200
    assert res_panes.status_code == 200
    assert "calcularPrioridadeOperacional" in res_frota.text
    assert "carregarAbaPanes" in res_panes.text
    assert "carregarAbaPanes" in res_aeronave.text


@pytest.mark.asyncio
async def test_app_js_renovacao_silenciosa_de_sessao_presente(db: AsyncSession):
    """RF-M91/RNF: apiFetch deve tentar POST /auth/refresh antes de expulsar
    o usuário para /login num 401."""
    app = criar_app_mobile(db, usuario=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/static/js/app.js")

    assert response.status_code == 200
    assert "tentarRefresh" in response.text
    assert "/auth/refresh" in response.text
    assert "_retried" in response.text


# ===========================================================================
# CSP — zero scripts/atributos inline (RN-16)
# ===========================================================================

@pytest.mark.asyncio
async def test_templates_mobile_conformidade_csp_zero_inline(db: AsyncSession):
    """
    Audita os templates mobile (incluindo os novos de Panes) para garantir
    ausência total de scripts inline ou atributos de evento inline.
    """
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_frota = await client.get("/m/")
        res_aeronave = await client.get(f"/m/aeronave/{aeronave.id}")
        res_pane_nova = await client.get(f"/m/pane/nova?aeronave_id={aeronave.id}")
        res_pane_detalhe = await client.get(f"/m/pane/{uuid.uuid4()}")

    for html_content in [res_frota.text, res_aeronave.text, res_pane_nova.text, res_pane_detalhe.text]:
        assert "onclick=" not in html_content.lower()
        assert "onchange=" not in html_content.lower()
        assert "onsubmit=" not in html_content.lower()
        assert "onload=" not in html_content.lower()
        assert "javascript:" not in html_content.lower()


@pytest.mark.asyncio
async def test_mobile_menu_sanduiche_estrutura_e_links(db: AsyncSession):
    """Valida a presença do botão de menu sanduíche, estrutura do drawer
    off-canvas e ausência de itens placeholder desabilitados (RF-M92)."""
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
    assert "Nova Pane" in response.text
    assert "Sincronização Offline" not in response.text
    assert "mobile-drawer-item disabled" not in response.text


# ===========================================================================
# Fluxo de Panes (via override de dependency — mecânica dos endpoints)
# ===========================================================================

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
async def test_mobile_aeronave_hub_valida_contexto_oculto_csp(db: AsyncSession):
    """Garante que o ID da aeronave é injetado via atributo data-aeronave-id sem injeção inline."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    app = criar_app_mobile(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/m/aeronave/{aeronave.id}")

    assert response.status_code == 200
    assert f'data-aeronave-id="{aeronave.id}"' in response.text
    assert "<script>const" not in response.text


# ===========================================================================
# Regressão de CSRF de ponta a ponta (achado #1) — app real, CSRFMiddleware ativo
# ===========================================================================

@pytest.mark.asyncio
async def test_mobile_csrf_meta_tag_renderiza_token_real(
    client: AsyncClient, usuario_mantenedor_e_token: dict,
):
    """Sem a meta tag, apiFetch nunca tinha token para enviar no
    X-CSRF-Token e todo POST/PATCH mobile respondia 403 (achado #1)."""
    response = await client.get("/m/", headers=usuario_mantenedor_e_token["headers"])

    assert response.status_code == 200
    assert 'name="csrf-token"' in response.text
    assert 'content=""' not in response.text


@pytest.mark.asyncio
async def test_mobile_sw_js_real_servido_na_raiz(client: AsyncClient):
    response = await client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers.get("Service-Worker-Allowed") == "/"


@pytest.mark.asyncio
async def test_mobile_concluir_pane_via_http_real_nao_retorna_403_csrf(
    client: AsyncClient,
    db: AsyncSession,
    usuario_mantenedor_e_token: dict,
):
    """Regressão de ponta a ponta do achado #1 (base_mobile.html sem meta
    CSRF ⇒ 403 em todo POST mobile), via HTTP real com o CSRFMiddleware
    ativo — não apenas via override de dependency como o resto da suíte."""
    headers = usuario_mantenedor_e_token["headers"]

    # Bootstrap: GET /m/ para receber o par de token CSRF real (cookie assinado + header)
    boot = await client.get("/m/", headers=headers)
    assert boot.status_code == 200
    token = boot.headers.get("X-CSRF-Token")
    assert token, "GET /m/ não devolveu X-CSRF-Token — meta tag ficaria sem valor para sincronizar."

    aeronave = Aeronave(
        serial_number=f"SN-{uuid.uuid4().hex[:8]}",
        matricula=f"FAB-{uuid.uuid4().hex[:4]}",
        modelo="A-29B",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()

    pane = Pane(
        aeronave_id=aeronave.id,
        descricao="Falha simulada para regressão de CSRF mobile",
        status=StatusPane.ABERTA.value,
        criado_por_id=usuario_mantenedor_e_token["usuario"].id,
    )
    db.add(pane)
    await db.flush()

    response = await client.post(
        f"/panes/{pane.id}/concluir",
        json={"observacao_conclusao": "Concluído via regressão de CSRF mobile"},
        headers={**headers, "X-CSRF-Token": token, "X-Skip-CSRF": "false"},
    )

    assert response.status_code != 403, response.text
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVIDA"
