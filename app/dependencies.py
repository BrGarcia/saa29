"""
app/dependencies.py
Dependências reutilizáveis do FastAPI (injeção de dependência).
"""

from typing import AsyncGenerator, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_factory
from app.auth.models import Usuario

# Esquema OAuth2 – endpoint de token em /auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency que fornece uma sessão de banco de dados assíncrona.
    A sessão é fechada automaticamente ao final de cada requisição.

    Uso:
        @router.get("/rota")
        async def endpoint(db: DBSession):
            ...
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """
    Dependency que valida o token JWT e retorna o usuário autenticado.

    Lança HTTPException 401 se o token for inválido ou expirado.
    Lança HTTPException 401 se o usuário não existir mais no banco.

    Uso:
        @router.get("/protegida")
        async def endpoint(usuario: CurrentUser):
            return {"usuario": usuario.username}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from app.auth.security import decodificar_token
        payload = decodificar_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from app.auth.service import buscar_por_username
    usuario = await buscar_por_username(db, username)
    if usuario is None:
        raise credentials_exception

    return usuario


# Anotações de tipo para uso nos endpoints (DX ergonômica)
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]
