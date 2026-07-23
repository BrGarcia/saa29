"""
app/shared/contracts.py
Definição de protocolos e contratos de interface para desacoplamento de domínios (DDD).
"""

from typing import Protocol, runtime_checkable, Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class AeronaveLookupProtocol(Protocol):
    """Contrato de interface para consulta desacoplada de Aeronaves."""

    async def buscar_por_id(self, db: AsyncSession, aeronave_id: uuid.UUID) -> Any | None:
        ...

    async def existe(self, db: AsyncSession, aeronave_id: uuid.UUID) -> bool:
        ...
