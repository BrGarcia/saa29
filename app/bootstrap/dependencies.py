"""
app/dependencies.py
Dependências reutilizáveis do FastAPI (injeção de dependência).
"""

from typing import AsyncGenerator, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.database import get_session_factory
from app.modules.auth.models import Usuario

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


from fastapi import Request

def get_token_from_request(
    request: Request,
    token_header: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False))
) -> str:
    """Extrai JWT: tenta primeiro do header (Swagger/API), depois do Cookie (Web)."""
    if token_header:
        return token_header
    token_cookie = request.cookies.get("saa29_token")
    if token_cookie:
        return token_cookie
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user(
    token: Annotated[str, Depends(get_token_from_request)],
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
        from app.modules.auth.security import decodificar_token
        payload = decodificar_token(token)
        username: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if username is None or jti is None:
            raise credentials_exception
            
        # Verificar Blacklist no banco de dados
        from sqlalchemy import select
        from app.modules.auth.models import TokenBlacklist
        result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
        if result.scalar_one_or_none() is not None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception

    from app.modules.auth.service import buscar_por_username
    usuario = await buscar_por_username(db, username)
    if usuario is None:
        raise credentials_exception

    return usuario


# Anotações de tipo para uso nos endpoints (DX ergonômica)
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def ensure_role(usuario: Usuario, *roles: str) -> Usuario:
    """
    Valida, em código de aplicação, se o usuário possui um dos papéis exigidos.
    """
    if usuario.funcao not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso restrito a: {', '.join(roles)}.",
        )
    return usuario


def require_role(*roles: str):
    """
    Factory de dependency para RBAC.
    Verifica se o usuário autenticado possui uma das funções permitidas.

    Uso:
        @router.post("/admin", dependencies=[Depends(require_role("INSPETOR"))])
        async def admin_endpoint(...): ...

    Ou via Annotated:
        InspetorRequired = Annotated[Usuario, Depends(require_role("INSPETOR"))]
    """
    async def _check_role(
        usuario: CurrentUser,
    ) -> Usuario:
        return ensure_role(usuario, *roles)
    return _check_role


# Atalhos de RBAC para uso direto nos routers
AdminRequired = Annotated[Usuario, Depends(require_role("ADMINISTRADOR"))]
EncarregadoRequired = Annotated[Usuario, Depends(require_role("ENCARREGADO"))]
InspetorRequired = Annotated[Usuario, Depends(require_role("INSPETOR"))]

EncarregadoOuAdmin = Annotated[
    Usuario, Depends(require_role("ENCARREGADO", "ADMINISTRADOR"))
]

InspetorOuAdmin = Annotated[
    Usuario, Depends(require_role("INSPETOR", "ADMINISTRADOR"))
]

EncarregadoInspetorOuAdmin = Annotated[
    Usuario, Depends(require_role("ENCARREGADO", "INSPETOR", "ADMINISTRADOR"))
]

ExecucaoPermitida = Annotated[
    Usuario, Depends(require_role("MANTENEDOR", "ENCARREGADO", "ADMINISTRADOR"))
]
