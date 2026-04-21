"""
app/auth/security.py
Funções de segurança: hashing de senha e operações JWT.
"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Contexto bcrypt para hashing de senhas
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")




def hash_senha(senha_plana: str) -> str:
    """
    Gera o hash bcrypt de uma senha em texto plano.
    Bcrypt limita a entrada a 72 bytes.
    """
    # Truncate to 72 chars to avoid ValueError (SEC-18)
    senha_ajustada = senha_plana[:72]
    return _pwd_context.hash(senha_ajustada)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """
    Compara a senha em texto plano com o hash armazenado.
    """
    senha_ajustada = senha_plana[:72]
    return _pwd_context.verify(senha_ajustada, senha_hash)


def criar_token(dados: dict) -> str:
    """
    Cria um JWT assinado com os dados fornecidos.

    O campo 'exp' (expiração) é adicionado automaticamente com base
    em settings.jwt_expire_minutes.
    O campo 'jti' (JWT ID) é adicionado para controle de blacklist.

    Args:
        dados: dicionário com o payload do token (deve incluir 'sub').

    Returns:
        Token JWT assinado como string.
    """
    payload = dados.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload.update({
        "exp": expira,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "access"
    })
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def criar_refresh_token(usuario_id: str | uuid.UUID) -> tuple[str, uuid.UUID]:
    """
    Cria um refresh token válido por 7 dias.
    
    Returns:
        Tupla (token_jwt, jti) onde jti é o ID único para rastreamento no DB
    """
    jti = str(uuid.uuid4())
    expira = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {
        "sub": str(usuario_id),
        "exp": expira,
        "iat": datetime.now(timezone.utc),
        "jti": jti,
        "type": "refresh"
    }
    token = jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)
    return token, uuid.UUID(jti)


def decodificar_token(token: str) -> dict:
    """
    Decodifica e valida um token JWT.

    A verificação se o JTI está na blacklist (SEC-03) será delegada 
    à dependency que tem acesso ao banco de dados, para suportar multi-workers.

    Args:
        token: string JWT recebida na requisição.

    Returns:
        Dicionário com o payload decodificado.

    Raises:
        JWTError: se o token for inválido, expirado ou adulterado.
    """
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    return payload
