"""
app/auth/router.py
Endpoints de autenticação e gestão de usuários.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.auth import schemas, service
from app.modules.auth.security import criar_token, decodificar_token
from app.bootstrap.dependencies import DBSession, CurrentUser, AdminRequired, EncarregadoRequired, oauth2_scheme

router = APIRouter()


# ------------------------------------------------------------------ #
#  Autenticação
# ------------------------------------------------------------------ #

from fastapi import Response, Request
from app.bootstrap.dependencies import get_token_from_request

from app.shared.core.limiter import limiter

@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login de usuário",
    description="Autentica o usuário e retorna um JWT + Refresh Token (via Cookie HttpOnly). (RF-01)",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    db: DBSession,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> schemas.Token:
    """
    Fluxo de autenticação com proteção contra força bruta.
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

    # Criar access token (15 min)
    access_token = criar_token(dados={"sub": usuario.username})
    
    # Criar refresh token (7 dias)
    from app.modules.auth.security import criar_refresh_token
    from app.modules.auth.models import TokenRefresh
    from datetime import datetime, timezone, timedelta
    
    refresh_token_str, jti = criar_refresh_token(usuario.id)
    
    # Armazenar refresh token no banco (para rastreamento e revogação)
    refresh_token_model = TokenRefresh(
        usuario_id=usuario.id,
        jti=str(jti),
        expira_em=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(refresh_token_model)
    await db.commit()
    
    # Set secure cookie for access token (HttpOnly, Secure em produção)
    response.set_cookie(
        key="saa29_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=15*60,  # 15 minutos
        # secure=True  # Ativar em produção num ambiente puramente HTTPS
    )

    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        usuario=schemas.UsuarioOut.model_validate(usuario),
    )


@router.post(
    "/refresh",
    response_model=schemas.Token,
    summary="Refresh access token",
    description="Usa um refresh token válido para obter um novo access token (15 min)",
)
async def refresh_access_token(
    db: DBSession,
    request_data: schemas.RefreshTokenRequest,
) -> schemas.Token:
    """
    Fluxo de refresh:
        1. Client envia refresh token válido
        2. Validar e decodificar refresh token
        3. Buscar usuário correspondente
        4. Gerar novo access token
        5. Opcionalmente gerar novo refresh token (rotate)
    """
    from app.modules.auth.security import decodificar_token, criar_refresh_token
    from app.modules.auth.models import TokenRefresh
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    
    try:
        # Decodificar refresh token
        payload = decodificar_token(request_data.refresh_token)
        
        # Validar que é um refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido (não é um refresh token)",
            )
        
        usuario_id = payload.get("sub")
        jti = payload.get("jti")
        
        # Buscar no banco para verificar se não foi revogado
        result = await db.execute(
            select(TokenRefresh).where(
                (TokenRefresh.jti == jti) &
                (TokenRefresh.revogado_em.is_(None)) &
                (TokenRefresh.expira_em > datetime.now(timezone.utc))
            )
        )
        stored_token = result.scalar_one_or_none()
        
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expirado ou revogado",
            )
        
        # Buscar usuário
        from app.modules.auth.models import Usuario
        import uuid
        try:
            val_usuario_id = uuid.UUID(usuario_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ID de usuário inválido no token",
            )
            
        user_result = await db.execute(
            select(Usuario).where(Usuario.id == val_usuario_id)
        )
        usuario = user_result.scalar_one_or_none()
        
        if not usuario or not usuario.ativo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário inativo ou não encontrado",
            )
        
        # Gerar novo access token
        new_access_token = criar_token(dados={"sub": usuario.username})
        
        # Gerar novo refresh token (token rotation)
        new_refresh_token, new_jti = criar_refresh_token(usuario.id)
        new_token_model = TokenRefresh(
            usuario_id=usuario.id,
            jti=str(new_jti),
            expira_em=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(new_token_model)
        
        # Revogar refresh token antigo (opcional, mas mais seguro)
        stored_token.revogado_em = datetime.now(timezone.utc)
        
        await db.commit()
        
        return schemas.Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            usuario=schemas.UsuarioOut.model_validate(usuario),
        )
        
    except Exception as e:
        # Qualquer erro na decodificação é acesso negado
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Refresh token inválido: {str(e)[:50]}",
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
            from app.modules.auth.models import TokenBlacklist
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
