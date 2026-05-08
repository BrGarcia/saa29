"""
Seed idempotente dos tipos base do calendario.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendario.models import EventType


BASE_EVENT_TYPES = [
    {
        "name": "Ferias",
        "visibility_type": "public",
        "color": "#16a34a",
        "icon": "PALM",
    },
    {
        "name": "Consulta",
        "visibility_type": "private",
        "color": "#dc2626",
        "icon": "MED",
    },
    {
        "name": "Servico",
        "visibility_type": "public",
        "color": "#2563eb",
        "icon": "SHIELD",
    },
]


async def run(session: AsyncSession) -> None:
    for item in BASE_EVENT_TYPES:
        result = await session.execute(select(EventType).where(EventType.name == item["name"]))
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(EventType(**item, active=True))
        else:
            existing.visibility_type = item["visibility_type"]
            existing.color = item["color"]
            existing.icon = item["icon"]
            existing.active = True
    await session.flush()

