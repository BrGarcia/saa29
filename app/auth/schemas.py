"""
app/auth/schemas.py
Schemas Pydantic v2 para autenticação e gestão de usuários.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TipoPapel


# ============================================================
# Schemas de Entrada (Requests)
# ============================================================

class LoginRequest(BaseModel):
    """Payload da tela de login (RF-01)."""
    username: str = Field(..., min_length=3, max_length=50, examples=["joao.silva"])
    password: str = Field(..., min_length=6, examples=["senha123"])


class UsuarioCreate(BaseModel):
    """Payload para criação de novo usuário (efetivo)."""
    nome: str = Field(..., min_length=3, max_length=150)
    posto: str = Field(..., max_length=30)
    especialidade: str | None = Field(default=None, max_length=50)
    funcao: TipoPapel = Field(..., description="ADMINISTRADOR | ENCARREGADO | MANTENEDOR")
    ramal: str | None = Field(default=None, max_length=20)
    trigrama: str | None = Field(default=None, max_length=3)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UsuarioUpdate(BaseModel):
    """Payload para atualização parcial de usuário."""
    nome: str | None = Field(default=None, max_length=150)
    posto: str | None = Field(default=None, max_length=30)
    especialidade: str | None = Field(default=None, max_length=50)
    funcao: TipoPapel | None = None
    ramal: str | None = Field(default=None, max_length=20)
    trigrama: str | None = Field(default=None, max_length=3)


class SenhaUpdate(BaseModel):
    """Payload para troca de senha do usuário autenticado."""
    senha_atual: str
    nova_senha: str = Field(..., min_length=6)


# ============================================================
# Schemas de Saída (Responses)
# ============================================================

class UsuarioOut(BaseModel):
    """Representação pública de um usuário (sem senha)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    posto: str
    especialidade: str | None
    funcao: str
    ramal: str | None
    trigrama: str | None
    username: str
    ativo: bool
    created_at: datetime


class Token(BaseModel):
    """Resposta do endpoint de login."""
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class TokenPayload(BaseModel):
    """Payload decodificado do JWT."""
    sub: str           # username
    exp: int           # timestamp de expiração
    iat: int           # timestamp de criação
