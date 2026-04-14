"""
app/auth/router.py
Endpoints de autenticação e gestão de usuários.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import schemas, service
from app.auth.security import criar_token, decodificar_token
from app.dependencies import DBSession, CurrentUser, AdminRequired, EncarregadoRequired, oauth2_scheme

router = APIRouter()


# ------------------------------------------------------------------ #
#  Autenticação
# ------------------------------------------------------------------ #

from fastapi import Response
from app.dependencies import get_token_from_request

@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login de usuário",
    description="Autentica o usuário e retorna um JWT (agora também via Cookie HttpOnly). (RF-01)",
)
async def login(
    db: DBSession,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> schemas.Token:
    """
    Fluxo de autenticação:
        1. Receber username e senha via form
        2. Buscar usuário no banco
        3. Verificar senha com bcrypt
        4. Gerar e retornar JWT
        5. Lançar o token também via Cookie seguro
    """
    usuario = await service.autenticar_usuario(
        db, form_data.username, form_data.password
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = criar_token(dados={"sub": usuario.username})
    
    # Prevenção contra XSS: o browser guardará e enviará automaticamente o token (HttpOnly)
    response.set_cookie(
        key="saa29_token",
        value=token,
        httponly=True,
        samesite="lax"
        # secure=True  # Ativar em produção num ambiente puramente HTTPS
    )

    return schemas.Token(
        access_token=token,
        token_type="bearer",
        usuario=schemas.UsuarioOut.model_validate(usuario),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout de usuário",
)
async def logout(
    usuario_atual: CurrentUser,
    db: DBSession,
    response: Response,
    token: str = Depends(get_token_from_request)
) -> None:
    """
    Invalida a sessão do usuário via blacklist do JTI e expurga o Cookie (HttpOnly).
    A blacklist é persistida no banco, sobrevivendo a restarts e escalonamento.
    """
    # Deleta cookie do lado do client
    response.delete_cookie(key="saa29_token")
    try:
        payload = decodificar_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            from datetime import datetime, timezone
            from app.auth.models import TokenBlacklist
            db.add(TokenBlacklist(
                jti=jti,
                expira_em=datetime.fromtimestamp(exp, tz=timezone.utc)
            ))
            await db.commit()
    except Exception:
        # Se o token já for inválido, logout é considerado ok.
        pass
    return None


@router.get(
    "/me",
    response_model=schemas.UsuarioOut,
    summary="Dados do usuário autenticado",
)
async def me(usuario_atual: CurrentUser) -> schemas.UsuarioOut:
    """Retorna os dados do usuário autenticado via token JWT."""
    return schemas.UsuarioOut.model_validate(usuario_atual)


# ------------------------------------------------------------------ #
#  Gestão de Usuários (Efetivo)
# ------------------------------------------------------------------ #

@router.post(
    "/usuarios",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário no efetivo",
)
async def criar_usuario(
    dados: schemas.UsuarioCreate,
    db: DBSession,
    _: AdminRequired,
) -> schemas.UsuarioOut:
    """Cria um novo membro do efetivo. Restrito a Administradores."""
    try:
        usuario = await service.criar_usuario(db, dados)
        return schemas.UsuarioOut.model_validate(usuario)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/usuarios",
    response_model=list[schemas.UsuarioOut],
    summary="Listar efetivo",
)
async def listar_usuarios(
    db: DBSession,
    _: CurrentUser,
    inativos: bool = False,
) -> list[schemas.UsuarioOut]:
    """Retorna a lista de usuários cadastrados."""
    usuarios = await service.listar_usuarios(db, incluir_inativos=inativos)
    return [schemas.UsuarioOut.model_validate(u) for u in usuarios]


@router.put(
    "/usuarios/senha",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha do usuário autenticado",
)
async def alterar_senha(
    dados: schemas.SenhaUpdate,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> None:
    """Permite ao usuário autenticado trocar sua própria senha."""
    try:
        await service.alterar_senha(
            db, usuario_atual, dados.senha_atual, dados.nova_senha
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/usuarios/{usuario_id}",
    response_model=schemas.UsuarioOut,
    summary="Atualizar dados de um usuário (Admin)",
)
async def atualizar_usuario(
    usuario_id: uuid.UUID,
    dados: schemas.UsuarioUpdate,
    db: DBSession,
    _: AdminRequired,
) -> schemas.UsuarioOut:
    """Atualiza os dados de um membro do efetivo. Restrito a Administradores."""
    try:
        usuario = await service.atualizar_usuario(db, usuario_id, dados)
        return schemas.UsuarioOut.model_validate(usuario)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar usuário do efetivo (Admin)",
)
async def excluir_usuario(
    usuario_id: uuid.UUID,
    db: DBSession,
    usuario_atual: AdminRequired,
) -> None:
    """Desativa um membro do efetivo. Restrito a Administradores."""
    try:
        await service.excluir_usuario(db, usuario_id, usuario_atual.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/usuarios/{usuario_id}/restaurar",
    response_model=schemas.UsuarioOut,
    summary="Reativar usuário do efetivo (Admin)",
)
async def restaurar_usuario(
    usuario_id: uuid.UUID,
    db: DBSession,
    _: AdminRequired,
) -> schemas.UsuarioOut:
    """Reativa um membro do efetivo que foi desativado. Restrito a Administradores."""
    try:
        usuario = await service.restaurar_usuario(db, usuario_id)
        return schemas.UsuarioOut.model_validate(usuario)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
