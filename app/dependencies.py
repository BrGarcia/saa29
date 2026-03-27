"""
app/dependencies.py
Dependências reutilizáveis do FastAPI (injeção de dependência).
"""

from typing import AsyncGenerator, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

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
    async with AsyncSessionLocal() as session:
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
):
    """
    Dependency que valida o token JWT e retorna o usuário autenticado.

    Lança HTTPException 401 se o token for inválido ou expirado.
    Lança HTTPException 404 se o usuário não existir mais no banco.

    Uso:
        @router.get("/protegida")
        async def endpoint(usuario: CurrentUser):
            return {"usuario": usuario.username}
    """
    # TODO: Implementar na Fase de Codificação (Dia 4)
    # 1. Decodificar token via app.auth.security.decodificar_token(token)
    # 2. Extrair username do payload
    # 3. Buscar usuário no banco via app.auth.service.buscar_por_username(db, username)
    # 4. Verificar se usuário está ativo
    # 5. Retornar objeto Usuario
    raise NotImplementedError("get_current_user ainda não implementado")


# Anotações de tipo para uso nos endpoints (DX ergonômica)
DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[object, Depends(get_current_user)]
