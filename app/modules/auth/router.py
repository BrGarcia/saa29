"""
app/auth/router.py
Endpoints de autenticação e gestão de usuários.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update

from app.bootstrap.config import get_settings
from app.bootstrap.dependencies import (
    DBSession, CurrentUser, AdminRequired,
    get_token_from_request,
)
from app.modules.auth import schemas, service
from app.modules.auth.models import TokenBlacklist, TokenRefresh, Usuario
from app.modules.auth.security import criar_token, criar_refresh_token, decodificar_token
from app.shared.core.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


def _cookies_secure(settings) -> bool:
    """Retorna True se cookies seguros forem explicitamente exigidos via HTTPS (force_secure_cookies)."""
    return settings.force_secure_cookies


# ------------------------------------------------------------------ #
#  Autenticação
# ------------------------------------------------------------------ #

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
        # Commit manual para persistir o incremento de falhas (feito via flush no service)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Criar access token (15 min)
    access_token = criar_token(dados={"sub": usuario.username})
    
    # Criar refresh token (settings.refresh_token_expire_days)
    settings = get_settings()

    refresh_token_str, jti = criar_refresh_token(usuario.id)

    # Armazenar refresh token no banco (para rastreamento e revogação)
    refresh_token_model = TokenRefresh(
        usuario_id=usuario.id,
        jti=str(jti),
        expira_em=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_token_model)
    # O commit é feito automaticamente pela dependência get_db ao final do request

    # Set secure cookie for access token (HttpOnly, Secure em produção)
    secure = _cookies_secure(settings)
    response.set_cookie(
        key="saa29_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        secure=secure
    )

    # BUG-01: path="/" (não mais restrito a "/auth/refresh") — com o path
    # restrito, o POST para /auth/logout não estava sob esse path e o
    # browser nunca enviava o cookie, então a revogação do refresh token no
    # logout nunca executava de fato via navegador.
    response.set_cookie(
        key="saa29_refresh_token",
        value=refresh_token_str,
        httponly=True,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
        secure=secure
    )

    # noqa S106: os tokens reais vao nos cookies HttpOnly acima; estes campos
    # sao placeholders literais para nao expor credencial no corpo da resposta.
    # "bearer" e o tipo definido pelo OAuth2, nao um segredo.
    return schemas.Token(
        access_token="hidden",  # noqa: S106
        refresh_token="hidden",  # noqa: S106
        token_type="bearer",  # noqa: S106
        usuario=schemas.UsuarioOut.model_validate(usuario),
    )


@router.post(
    "/refresh",
    response_model=schemas.Token,
    summary="Refresh access token",
    description="Usa um refresh token válido para obter um novo access token (15 min)",
)
@limiter.limit("20/minute")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: DBSession,
) -> schemas.Token:
    """
    Fluxo de refresh:
        1. Client envia refresh token válido via cookie
        2. Validar e decodificar refresh token
        3. Buscar usuário correspondente
        4. Gerar novo access token
        5. Opcionalmente gerar novo refresh token (rotate) e setar nos cookies
    """
    refresh_token = request.cookies.get("saa29_refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token não fornecido.",
        )
    
    try:
        # Decodificar refresh token
        payload = decodificar_token(refresh_token)
        
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
            select(TokenRefresh).where(TokenRefresh.jti == jti)
        )
        stored_token = result.scalar_one_or_none()
        
        # Garantir comparação segura de timezone (especialmente para SQLite)
        agora = datetime.now(timezone.utc)
        if stored_token:
            expira_em = stored_token.expira_em
            if expira_em.tzinfo is None:
                expira_em = expira_em.replace(tzinfo=timezone.utc)
            
            if expira_em < agora:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expirado",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token inválido",
            )
            
        if stored_token.revogado_em is not None:
            await db.execute(
                update(TokenRefresh)
                .where(
                    (TokenRefresh.usuario_id == stored_token.usuario_id) &
                    (TokenRefresh.revogado_em.is_(None))
                )
                .values(revogado_em=agora)
            )
            # Commit explícito: sem isso, o HTTPException abaixo propaga pela
            # dependência get_db, que faz rollback em qualquer exceção — a
            # revogação de família seria desfeita e a mensagem "todos os
            # tokens foram revogados" ficaria falsa. Mesmo padrão já usado no
            # login para persistir o incremento de tentativas falhas.
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reuso de token detectado. Todos os tokens foram revogados por segurança.",
            )

        # RISCO-08: claim atômico via UPDATE condicional — evita que duas
        # requisições concorrentes com o mesmo refresh token (duas abas,
        # retry de rede) leiam o mesmo estado "ainda não revogado" antes de
        # qualquer commit e ambas rotacionem o mesmo token pai. Só quem
        # conseguir marcar revogado_em nesta instrução (rowcount == 1)
        # segue; o perdedor da corrida cai no mesmo caminho de reuso acima.
        claim = await db.execute(
            update(TokenRefresh)
            .where(TokenRefresh.jti == jti, TokenRefresh.revogado_em.is_(None))
            .values(revogado_em=agora)
        )
        if claim.rowcount == 0:
            await db.execute(
                update(TokenRefresh)
                .where(
                    (TokenRefresh.usuario_id == stored_token.usuario_id) &
                    (TokenRefresh.revogado_em.is_(None))
                )
                .values(revogado_em=agora)
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Reuso de token detectado. Todos os tokens foram revogados por segurança.",
            )

        # Buscar usuário
        try:
            val_usuario_id = uuid.UUID(usuario_id)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ID de usuário inválido no token",
            ) from exc
            
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
        settings = get_settings()
        new_refresh_token, new_jti = criar_refresh_token(usuario.id)
        new_token_model = TokenRefresh(
            usuario_id=usuario.id,
            jti=str(new_jti),
            expira_em=agora + timedelta(days=settings.refresh_token_expire_days),
        )
        db.add(new_token_model)

        # Refresh token antigo já foi revogado atomicamente pelo claim acima.

        # O commit é feito automaticamente pela dependência get_db ao final do request

        # Set cookies
        secure = _cookies_secure(settings)
        response.set_cookie(
            key="saa29_token",
            value=new_access_token,
            httponly=True,
            samesite="lax",
            max_age=settings.jwt_expire_minutes * 60,
            secure=secure
        )

        response.set_cookie(
            key="saa29_refresh_token",
            value=new_refresh_token,
            httponly=True,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/",
            secure=secure
        )
        
        # noqa S106: mesmos placeholders do login — ver comentario acima.
        return schemas.Token(
            access_token="hidden",  # noqa: S106
            refresh_token="hidden",  # noqa: S106
            token_type="bearer",  # noqa: S106
            usuario=schemas.UsuarioOut.model_validate(usuario),
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        # RISCO-09: antes engolia qualquer exceção sem log — inclusive
        # falha de infraestrutura (banco fora do ar, erro de driver), que
        # ficava indistinguível de "token inválido" e sem rastro para
        # diagnóstico.
        logger.exception("Erro inesperado em /auth/refresh")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido",
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout de usuário",
)
async def logout(
    request: Request,
    usuario_atual: CurrentUser,
    db: DBSession,
    response: Response,
    token: str = Depends(get_token_from_request)
) -> None:
    """
    Invalida a sessão do usuário via blacklist do JTI e expurga o Cookie (HttpOnly).
    Também revoga o Refresh Token se presente.
    """
    # Deleta cookies do lado do client (BUG-01: path="/" para bater com o
    # path usado ao setar o cookie — ver comentário em login/refresh)
    response.delete_cookie(key="saa29_token")
    response.delete_cookie(key="saa29_refresh_token", path="/")

    # 1. Invalida Access Token (Blacklist)
    try:
        payload = decodificar_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            db.add(TokenBlacklist(
                jti=jti,
                expira_em=datetime.fromtimestamp(exp, tz=timezone.utc)
            ))
    except Exception:
        # RISCO-10: sem log, uma falha aqui (ex.: erro transitório de banco)
        # respondia 204 como se o logout tivesse funcionado, mas o access
        # token continuava válido e utilizável até expirar naturalmente.
        logger.warning("Falha ao adicionar access token à blacklist no logout do usuário %s.", usuario_atual.id, exc_info=True)

    # 2. Revoga Refresh Token no Banco
    refresh_token = request.cookies.get("saa29_refresh_token")
    if refresh_token:
        try:
            rt_payload = decodificar_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            if rt_jti:
                result = await db.execute(
                    select(TokenRefresh).where(TokenRefresh.jti == rt_jti)
                )
                stored_rt = result.scalar_one_or_none()
                if stored_rt:
                    stored_rt.revogado_em = datetime.now(timezone.utc)
        except Exception:
            logger.warning("Falha ao revogar refresh token no logout do usuário %s.", usuario_atual.id, exc_info=True)

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
    usuario = await service.criar_usuario(db, dados)
    return schemas.UsuarioOut.model_validate(usuario)


@router.get(
    "/usuarios",
    response_model=list[schemas.UsuarioOut],
    summary="Listar efetivo",
)
async def listar_usuarios(
    db: DBSession,
    _: CurrentUser,
    inativos: bool = False,
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[schemas.UsuarioOut]:
    """Retorna a lista de usuários cadastrados. `limit`/`offset` são opcionais."""
    usuarios = await service.listar_usuarios(db, incluir_inativos=inativos, limit=limit, offset=offset)
    return [schemas.UsuarioOut.model_validate(u) for u in usuarios]


@router.put(
    "/usuarios/senha",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha do usuário autenticado",
)
@limiter.limit("5/minute")
async def alterar_senha(
    request: Request,
    dados: schemas.SenhaUpdate,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> None:
    """Permite ao usuário autenticado trocar sua própria senha.

    MELHORIA-24: `senha_atual` é um segundo oráculo de senha (compara contra
    o hash armazenado) e, sem rate limit próprio, podia ser atacado por
    força bruta sem o lockout dedicado que o login tem.
    """
    await service.alterar_senha(
        db, usuario_atual, dados.senha_atual, dados.nova_senha
    )


@router.put(
    "/usuarios/{usuario_id}/senha",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Redefinir senha de um usuário (Admin)",
)
async def admin_resetar_senha(
    usuario_id: uuid.UUID,
    dados: schemas.AdminSenhaUpdate,
    db: DBSession,
    _: AdminRequired,
) -> None:
    """Redefine a senha de um membro do efetivo sem precisar da senha atual. Restrito a Administradores."""
    await service.admin_resetar_senha(db, usuario_id, dados.nova_senha)


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
    usuario = await service.atualizar_usuario(db, usuario_id, dados)
    return schemas.UsuarioOut.model_validate(usuario)


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
    await service.excluir_usuario(db, usuario_id, usuario_atual.id)


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
    usuario = await service.restaurar_usuario(db, usuario_id)
    return schemas.UsuarioOut.model_validate(usuario)
