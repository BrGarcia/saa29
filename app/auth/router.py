"""
app/auth/router.py
Endpoints de autenticação e gestão de usuários.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import schemas, service
from app.auth.security import criar_token
from app.dependencies import DBSession, CurrentUser

router = APIRouter()


# ------------------------------------------------------------------ #
#  Autenticação
# ------------------------------------------------------------------ #

@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login de usuário",
    description="Autentica o usuário e retorna um JWT de acesso. (RF-01)",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: DBSession = Depends(),
) -> schemas.Token:
    """
    Fluxo de autenticação:
        1. Receber username e senha via form
        2. Buscar usuário no banco
        3. Verificar senha com bcrypt
        4. Gerar e retornar JWT
    """
    # TODO (Dia 4): implementar
    raise NotImplementedError


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout de usuário",
)
async def logout(usuario_atual: CurrentUser) -> None:
    """
    Invalida a sessão do usuário.
    (Stateless JWT: orientação para o cliente descartar o token.)
    """
    # TODO (Dia 4): implementar blacklist de tokens se necessário
    raise NotImplementedError


@router.get(
    "/me",
    response_model=schemas.UsuarioOut,
    summary="Dados do usuário autenticado",
)
async def me(usuario_atual: CurrentUser) -> schemas.UsuarioOut:
    """Retorna os dados do usuário autenticado via token JWT."""
    # TODO (Dia 4): return usuario_atual
    raise NotImplementedError


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
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> schemas.UsuarioOut:
    """Cria um novo membro do efetivo com acesso ao sistema."""
    # TODO (Dia 4): return await service.criar_usuario(db, dados)
    raise NotImplementedError


@router.get(
    "/usuarios",
    response_model=list[schemas.UsuarioOut],
    summary="Listar efetivo",
)
async def listar_usuarios(
    db: DBSession = Depends(),
    _: CurrentUser = Depends(),
) -> list[schemas.UsuarioOut]:
    """Retorna a lista completa de usuários cadastrados."""
    # TODO (Dia 4): return await service.listar_usuarios(db)
    raise NotImplementedError


@router.put(
    "/usuarios/senha",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Alterar senha do usuário autenticado",
)
async def alterar_senha(
    dados: schemas.SenhaUpdate,
    db: DBSession = Depends(),
    usuario_atual: CurrentUser = Depends(),
) -> None:
    """Permite ao usuário autenticado trocar sua própria senha."""
    # TODO (Dia 4): await service.alterar_senha(db, usuario_atual, dados.senha_atual, dados.nova_senha)
    raise NotImplementedError
