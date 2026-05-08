import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.dependencies import get_current_user, get_db
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.calendario import schemas, service
from app.modules.calendario.models import CalendarEvent, EventType
from app.modules.calendario.router import router as calendario_router


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
    assert payload.owner_trigram == "OWN"


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
    assert eventos[0]["owner_trigram"] == "OWN"
    assert eventos[0]["notes"] is None


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

