"""
Schemas Pydantic do modulo de calendario.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


VisibilityType = Literal["public", "private"]


class EventTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    visibility_type: VisibilityType = "public"
    color: str = Field(min_length=1, max_length=20)
    icon: str = Field(min_length=1, max_length=20)
    active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class EventTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    visibility_type: VisibilityType | None = None
    color: str | None = Field(default=None, min_length=1, max_length=20)
    icon: str | None = Field(default=None, min_length=1, max_length=20)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class EventTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    visibility_type: VisibilityType
    color: str
    icon: str
    active: bool
    created_at: datetime
    updated_at: datetime | None


class CalendarEventCreate(BaseModel):
    owner_user_id: uuid.UUID
    event_type_id: uuid.UUID
    start_date: datetime
    end_date: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "CalendarEventCreate":
        if self.end_date < self.start_date:
            raise ValueError("A data de termino nao pode ser anterior a data de inicio.")
        return self


class CalendarEventUpdate(BaseModel):
    owner_user_id: uuid.UUID | None = None
    event_type_id: uuid.UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "CalendarEventUpdate":
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("A data de termino nao pode ser anterior a data de inicio.")
        return self


class CalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_user_id: uuid.UUID
    created_by_user_id: uuid.UUID
    event_type_id: uuid.UUID
    start_date: datetime
    end_date: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


class CalendarEventPayload(BaseModel):
    id: uuid.UUID
    title: str
    start: datetime
    end: datetime
    backgroundColor: str
    icon: str
    owner_trigram: str | None
    notes: str | None = None
    source: str = "calendario"
    event_type_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    can_edit: bool = False
    can_delete: bool = False
