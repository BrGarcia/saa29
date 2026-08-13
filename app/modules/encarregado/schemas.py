"""
app/modules/encarregado/schemas.py
Schemas Pydantic v2 do módulo Encarregado — Ciência de Alterações.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.shared.core.enums import CategoriaCiencia, EventoCiencia


class AlteracaoPendenteItem(BaseModel):
    """Um item pendente de ciência, já formatado para exibição em card."""

    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str
    aeronave_matricula: str | None
    titulo: str
    detalhe: str | None
    responsavel_trigrama: str | None
    data_evento: datetime


class ListaPendentesResponse(BaseModel):
    """Resposta de `GET /pendentes` — itens agrupados por categoria."""

    total: int
    itens_por_categoria: dict[CategoriaCiencia, list[AlteracaoPendenteItem]]


class DarCienciaRequest(BaseModel):
    """Payload de `POST /ciencia` — identifica o item de origem pela mesma
    chave usada no anti-join (categoria, evento, registro_id)."""

    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str

    @field_validator("registro_id")
    @classmethod
    def _normalizar_registro_id(cls, valor: str) -> str:
        """Remove hífens: o hex sem hífens é o formato de armazenamento real
        de `Uuid` no SQLite (ver `service._sem_ciencia`) — normalizar aqui
        torna o endpoint tolerante a um cliente que envie `str(uuid.UUID)`
        com hífens em vez do `registro_id` opaco devolvido por `/pendentes`.

        `uuid.UUID(hex=...)` também valida o formato: sem isso, um
        `registro_id` malformado (bug de cliente, ex.: id não inicializado)
        seria aceito e persistiria como linha órfã em `encarregado_ciencias`
        com 200 OK em vez de 422 — o anti-join nunca a encontraria (não
        casa com nenhum `cast(<pk>, String)` real), mas o dado ficaria
        acumulado sem que ninguém percebesse o bug de origem."""
        normalizado = valor.replace("-", "").strip().lower()
        uuid.UUID(hex=normalizado)
        return normalizado


class CienciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str
    usuario_trigrama: str | None
    dado_em: datetime
