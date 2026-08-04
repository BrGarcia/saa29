import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.dependencies import get_current_user, get_db
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.calendario import schemas, service
from app.modules.calendario.models import CalendarEvent, EventType
from app.modules.calendario.router import router as calendario_router
from app.modules.inspecoes.models import Inspecao, InspecaoEventoTipo, TipoInspecao
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusAeronave, StatusInspecao


CALENDARIO_URL = "/api/v1/calendario"


async def criar_usuario_teste(
    db: AsyncSession,
    funcao: str = "MANTENEDOR",
    trigrama: str = "TST",
) -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Usuario Calendario {suffix}",
        posto="Sgt",
        especialidade="ELT",
        funcao=funcao,
        ramal="2500",
        trigrama=trigrama,
        username=f"calendario_{funcao.lower()}_{suffix}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def criar_tipo_evento(
    db: AsyncSession,
    visibility_type: str = "public",
    name: str = "Servico",
) -> EventType:
    tipo = EventType(
        name=f"{name} {uuid.uuid4().hex[:6]}",
        visibility_type=visibility_type,
        color="#2563eb",
        icon="S",
        active=True,
    )
    db.add(tipo)
    await db.flush()
    return tipo


async def criar_evento_teste(
    db: AsyncSession,
    owner: Usuario,
    event_type: EventType,
    created_by: Usuario | None = None,
    notes: str | None = "Observacao sigilosa",
) -> CalendarEvent:
    start = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc)
    evento = CalendarEvent(
        owner_user_id=owner.id,
        created_by_user_id=(created_by or owner).id,
        event_type_id=event_type.id,
        start_date=start,
        end_date=end,
        notes=notes,
    )
    db.add(evento)
    await db.flush()
    return evento


async def criar_inspecao_com_dpe(db: AsyncSession, usuario: Usuario) -> Inspecao:
    aeronave = Aeronave(
        serial_number=f"SN-CAL-{uuid.uuid4().hex[:8].upper()}",
        matricula=f"CA-{uuid.uuid4().hex[:4].upper()}",
        modelo="A-29",
        status=StatusAeronave.INSPECAO,
        data_inicio_operacao=datetime(2020, 1, 1, tzinfo=timezone.utc).date(),
    )
    tipo = TipoInspecao(
        codigo=f"IF-{uuid.uuid4().hex[:4].upper()}",
        nome="Inspecao calendario",
        duracao_dias=5,
        ativo=True,
    )
    db.add_all([aeronave, tipo])
    await db.flush()

    inspecao = Inspecao(
        aeronave_id=aeronave.id,
        status=StatusInspecao.ABERTA.value,
        data_inicio=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        data_fim_prevista=datetime(2026, 5, 15, 17, 0, tzinfo=timezone.utc),
        observacoes="DPE projetada",
        aberto_por_id=usuario.id,
        aberto_por_trigrama=usuario.trigrama,
    )
    db.add(inspecao)
    await db.flush()
    db.add(InspecaoEventoTipo(inspecao_id=inspecao.id, tipo_inspecao_id=tipo.id))
    await db.flush()
    return inspecao


def criar_app_isolado(db: AsyncSession, usuario: Usuario | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(calendario_router, prefix=CALENDARIO_URL)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if usuario is not None:
        async def override_get_current_user():
            return usuario

        app.dependency_overrides[get_current_user] = override_get_current_user

    return app


def test_schema_event_type_restringe_visibilidade():
    tipo = schemas.EventTypeCreate(
        name="Consulta",
        visibility_type="private",
        color="#dc2626",
        icon="C",
    )

    assert tipo.visibility_type == "private"

    with pytest.raises(ValidationError):
        schemas.EventTypeCreate(
            name="Invalido",
            visibility_type="restrito",
            color="#000000",
            icon="X",
        )


def test_schema_calendar_event_bloqueia_periodo_invertido():
    owner_id = uuid.uuid4()
    event_type_id = uuid.uuid4()

    with pytest.raises(ValidationError):
        schemas.CalendarEventCreate(
            owner_user_id=owner_id,
            event_type_id=event_type_id,
            start_date=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc),
            notes="Periodo invalido",
        )


def test_schema_calendar_event_bloqueia_notes_excedente():
    owner_id = uuid.uuid4()
    event_type_id = uuid.uuid4()

    with pytest.raises(ValidationError) as exc_info:
        schemas.CalendarEventCreate(
            owner_user_id=owner_id,
            event_type_id=event_type_id,
            start_date=datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
            notes="a" * 2001,
        )
    assert "at most 2000 characters" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        schemas.CalendarEventUpdate(
            notes="a" * 2001,
        )
    assert "at most 2000 characters" in str(exc_info.value)


@pytest.mark.asyncio
async def test_modelos_event_type_e_calendar_event_persistem_relacionamentos(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    tipo = await criar_tipo_evento(db)
    evento = await criar_evento_teste(db, usuario, tipo)

    assert tipo.id is not None
    assert tipo.visibility_type == "public"
    assert evento.owner_user_id == usuario.id
    assert evento.created_by_user_id == usuario.id
    assert evento.event_type_id == tipo.id


@pytest.mark.asyncio
async def test_rbac_censura_privado_para_terceiro_sem_privilegio(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    viewer = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="VIS")
    tipo_privado = await criar_tipo_evento(db, visibility_type="private", name="Consulta")
    evento = await criar_evento_teste(db, owner, tipo_privado, notes="Consulta as 14h")

    payload = service.format_event_for_user(evento, viewer)

    assert payload.title == "Particular"
    assert payload.icon == "L"
    assert payload.notes is None
    assert payload.owner_trigram is None
    assert payload.event_type_id is None
    assert payload.owner_user_id is None
    assert payload.can_edit is False
    assert payload.can_delete is False


@pytest.mark.asyncio
async def test_rbac_mostra_privado_para_dono_e_perfil_privilegiado(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    encarregado = await criar_usuario_teste(db, funcao="ENCARREGADO", trigrama="ENC")
    tipo_privado = await criar_tipo_evento(db, visibility_type="private", name="Consulta")
    evento = await criar_evento_teste(db, owner, tipo_privado, notes="Consulta as 14h")

    payload_dono = service.format_event_for_user(evento, owner)
    payload_encarregado = service.format_event_for_user(evento, encarregado)

    assert payload_dono.title == tipo_privado.name
    assert payload_dono.notes == "Consulta as 14h"
    assert payload_encarregado.title == tipo_privado.name
    assert payload_encarregado.notes == "Consulta as 14h"


@pytest.mark.asyncio
async def test_router_lista_eventos_com_censura_backend(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    viewer = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="VIS")
    tipo_privado = await criar_tipo_evento(db, visibility_type="private", name="Consulta")
    await criar_evento_teste(db, owner, tipo_privado, notes="Consulta as 14h")
    app = criar_app_isolado(db, viewer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            f"{CALENDARIO_URL}/eventos",
            params={"start_date": "2026-05-01T00:00:00Z", "end_date": "2026-05-31T23:59:59Z"},
        )

    assert response.status_code == 200
    eventos = response.json()
    assert len(eventos) == 1
    assert eventos[0]["title"] == "Particular"
    assert eventos[0]["owner_trigram"] is None
    assert eventos[0]["notes"] is None
    assert eventos[0]["event_type_id"] is None
    assert eventos[0]["owner_user_id"] is None
    assert eventos[0]["can_edit"] is False
    assert eventos[0]["can_delete"] is False


@pytest.mark.asyncio
async def test_router_crud_eventos_basico(db: AsyncSession):
    usuario = await criar_usuario_teste(db, funcao="ADMINISTRADOR", trigrama="ADM")
    tipo = await criar_tipo_evento(db, visibility_type="public", name="Ferias")
    app = criar_app_isolado(db, usuario)

    payload = {
        "owner_user_id": str(usuario.id),
        "event_type_id": str(tipo.id),
        "start_date": "2026-05-12T08:00:00Z",
        "end_date": "2026-05-12T12:00:00Z",
        "notes": "Lancamento inicial",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        create_response = await client.post(f"{CALENDARIO_URL}/eventos", json=payload)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]

        update_response = await client.put(
            f"{CALENDARIO_URL}/eventos/{event_id}",
            json={"notes": "Lancamento ajustado"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["notes"] == "Lancamento ajustado"

        delete_response = await client.delete(f"{CALENDARIO_URL}/eventos/{event_id}")
        assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_router_lista_tipos_evento_para_modal(db: AsyncSession):
    usuario = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="USR")
    tipo = await criar_tipo_evento(db, visibility_type="public", name="Servico")
    app = criar_app_isolado(db, usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{CALENDARIO_URL}/tipos")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == str(tipo.id) for item in payload)


@pytest.mark.asyncio
async def test_router_atualiza_tipo_evento_com_payload_do_modal(db: AsyncSession):
    usuario = await criar_usuario_teste(db, funcao="ADMINISTRADOR", trigrama="ADM")
    tipo = await criar_tipo_evento(db, visibility_type="public", name="Servico")
    app = criar_app_isolado(db, usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.put(
            f"{CALENDARIO_URL}/tipos/{tipo.id}",
            json={
                "name": "Servico Operacional",
                "icon": "SHIELD",
                "visibility_type": "private",
                "color": "#2563eb",
                "private_color": "#94a3b8",
                "active": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Servico Operacional"
    assert payload["icon"] == "SHIELD"
    assert payload["visibility_type"] == "private"
    assert payload["private_color"] == "#94a3b8"
    assert payload["active"] is True


@pytest.mark.asyncio
async def test_router_bloqueia_mantenedor_criar_evento_para_terceiro(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    viewer = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="VIS")
    tipo = await criar_tipo_evento(db, visibility_type="public", name="Servico")
    app = criar_app_isolado(db, viewer)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"{CALENDARIO_URL}/eventos",
            json={
                "owner_user_id": str(owner.id),
                "event_type_id": str(tipo.id),
                "start_date": "2026-05-12T08:00:00Z",
                "end_date": "2026-05-12T12:00:00Z",
                "notes": "Tentativa invalida",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_router_bloqueia_delete_para_nao_admin(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    tipo = await criar_tipo_evento(db, visibility_type="public", name="Servico")
    evento = await criar_evento_teste(db, owner, tipo)
    app = criar_app_isolado(db, owner)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.delete(f"{CALENDARIO_URL}/eventos/{evento.id}")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_eventos_agrega_dpe_de_inspecoes(db: AsyncSession):
    usuario = await criar_usuario_teste(db, funcao="ENCARREGADO", trigrama="ENC")
    inspecao = await criar_inspecao_com_dpe(db, usuario)
    app = criar_app_isolado(db, usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            f"{CALENDARIO_URL}/eventos",
            params={"start_date": "2026-05-01T00:00:00Z", "end_date": "2026-05-31T23:59:59Z"},
        )

    assert response.status_code == 200
    eventos = response.json()
    evento_dpe = next(item for item in eventos if item["id"] == str(inspecao.id))
    assert evento_dpe["source"] == "inspecao"
    assert evento_dpe["title"].startswith("DPE")
    assert evento_dpe["can_edit"] is False


# ------------------------------------------------------------------ #
#  BUG-02 — round-trip de timezone no SQLite
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_datas_evento_mantem_timezone_ao_reler_do_banco(db: AsyncSession):
    """Antes, DateTime(timezone=True) no SQLite perdia o offset na leitura:
    o valor voltava do banco como datetime naive, mesmo gravado com tzinfo.
    Usa offset não-UTC (-03:00) para não passar "por acaso" só porque o
    valor já nasceria em UTC."""
    usuario = await criar_usuario_teste(db)
    tipo = await criar_tipo_evento(db)
    fuso = timezone(timedelta(hours=-3))
    start = datetime(2026, 6, 1, 9, 0, tzinfo=fuso)
    end = datetime(2026, 6, 1, 10, 0, tzinfo=fuso)
    evento = CalendarEvent(
        owner_user_id=usuario.id,
        created_by_user_id=usuario.id,
        event_type_id=tipo.id,
        start_date=start,
        end_date=end,
    )
    db.add(evento)
    await db.flush()

    # Força a releitura real das colunas a partir do banco — não do objeto
    # Python ainda "quente" na sessão, que nunca passaria pelo result
    # processor e mascararia o bug.
    await db.refresh(evento, ["start_date", "end_date"])

    assert evento.start_date.tzinfo is not None
    assert evento.end_date.tzinfo is not None
    assert evento.start_date == start  # mesmo instante absoluto
    assert evento.end_date == end


# ------------------------------------------------------------------ #
#  BUG-01 — comparação aware x naive em update parcial
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_atualizar_evento_com_apenas_end_date_nao_derruba_com_typeerror(db: AsyncSession):
    """Editar só end_date usa o start_date recarregado do banco para a
    comparação de período — antes do BUG-02 corrigido, isso comparava um
    datetime aware (payload) contra um naive (banco) e levantava TypeError
    não tratado (500) em vez de aplicar a atualização."""
    owner = await criar_usuario_teste(db, funcao="ADMINISTRADOR", trigrama="ADM")
    tipo = await criar_tipo_evento(db)
    evento = await criar_evento_teste(db, owner, tipo)

    # Simula uma request posterior num objeto já persistido: força a
    # releitura real das colunas de data a partir do banco.
    db.expire(evento, ["start_date", "end_date"])

    atualizado = await service.update_event(
        db, evento.id,
        schemas.CalendarEventUpdate(end_date=datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)),
        owner,
    )

    assert atualizado.end_date == datetime(2026, 5, 10, 11, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ #
#  RISCO-03 — corrida de UNIQUE em EventType.name
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_tipo_evento_com_nome_duplicado_levanta_valueerror_via_savepoint(db: AsyncSession):
    """RISCO-03: sem pre-check separado, a checagem de duplicidade agora
    acontece só no SAVEPOINT/UNIQUE — mesmo assim continua devolvendo o
    ValueError/400 já usado pelo resto do módulo (não um novo status)."""
    nome_alvo = f"Conflito {uuid.uuid4().hex[:6]}"
    conflitante = EventType(name=nome_alvo, color="#000000", icon="X")
    db.add(conflitante)
    await db.flush()

    with pytest.raises(ValueError, match="Ja existe um tipo de evento"):
        await service.create_event_type(
            db, schemas.EventTypeCreate(name=nome_alvo, color="#111111", icon="Y")
        )

    # Sessão segue viva: o SAVEPOINT isolou a falha, não derrubou a transação.
    outro = await service.create_event_type(
        db, schemas.EventTypeCreate(name=f"Outro {uuid.uuid4().hex[:6]}", color="#222222", icon="Z")
    )
    assert outro.id is not None


@pytest.mark.asyncio
async def test_atualizar_tipo_evento_com_nome_duplicado_levanta_valueerror_via_savepoint(db: AsyncSession):
    """RISCO-03 (update): sem o SAVEPOINT/except, essa colisão vazava como
    IntegrityError cru (500); agora vira o mesmo ValueError/400 do resto do
    módulo. (Diferente do caso de create, reutilizar a MESMA sessão para uma
    operação seguinte após esta falha específica de UPDATE não é coberto —
    fora do escopo do achado, que pede só a tradução de erro.)"""
    nome_alvo = f"Conflito {uuid.uuid4().hex[:6]}"
    tipo_a = await criar_tipo_evento(db, name="Original")
    tipo_b = EventType(name=nome_alvo, color="#000000", icon="X")
    db.add(tipo_b)
    await db.flush()

    with pytest.raises(ValueError, match="Ja existe um tipo de evento"):
        await service.update_event_type(db, tipo_a.id, schemas.EventTypeUpdate(name=nome_alvo))


# ------------------------------------------------------------------ #
#  MELHORIA-05 — exceções de domínio tipadas (fim de LookupError/PermissionError)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_update_event_type_inexistente_levanta_domain_exc_tipado(db: AsyncSession):
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await service.update_event_type(db, uuid.uuid4(), schemas.EventTypeUpdate(name="X"))


@pytest.mark.asyncio
async def test_create_event_para_terceiro_sem_privilegio_levanta_domain_exc_tipado(db: AsyncSession):
    owner = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="OWN")
    viewer = await criar_usuario_teste(db, funcao="MANTENEDOR", trigrama="VIS")
    tipo = await criar_tipo_evento(db)

    with pytest.raises(domain_exc.PermissaoNegadaError):
        await service.create_event(
            db,
            schemas.CalendarEventCreate(
                owner_user_id=owner.id,
                event_type_id=tipo.id,
                start_date=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                end_date=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            ),
            viewer,
        )


# ------------------------------------------------------------------ #
#  MELHORIA-06 — _get_task_events removida (código morto)
# ------------------------------------------------------------------ #

def test_get_task_events_foi_removida():
    assert not hasattr(service, "_get_task_events")
