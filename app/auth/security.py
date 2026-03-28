"""
app/auth/security.py
Funções de segurança: hashing de senha e operações JWT.
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Contexto bcrypt para hashing de senhas
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha_plana: str) -> str:
    """
    Gera o hash bcrypt de uma senha em texto plano.

    Args:
        senha_plana: senha em texto claro fornecida pelo usuário.

    Returns:
        Hash bcrypt da senha para armazenamento seguro no banco.
    """
    return _pwd_context.hash(senha_plana)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """
    Compara a senha em texto plano com o hash armazenado.

    Args:
        senha_plana: senha fornecida no login.
        senha_hash: hash armazenado no banco de dados.

    Returns:
        True se a senha for válida, False caso contrário.
    """
    return _pwd_context.verify(senha_plana, senha_hash)


def criar_token(dados: dict) -> str:
    """
    Cria um JWT assinado com os dados fornecidos.

    O campo 'exp' (expiração) é adicionado automaticamente com base
    em settings.jwt_expire_minutes.

    Args:
        dados: dicionário com o payload do token (deve incluir 'sub').

    Returns:
        Token JWT assinado como string.
    """
    payload = dados.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload.update({"exp": expira, "iat": datetime.now(timezone.utc)})
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decodificar_token(token: str) -> dict:
    """
    Decodifica e valida um token JWT.

    Args:
        token: string JWT recebida na requisição.

    Returns:
        Dicionário com o payload decodificado.

    Raises:
        JWTError: se o token for inválido, expirado ou adulterado.
    """
    return jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
