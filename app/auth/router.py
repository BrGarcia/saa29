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
    db: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> schemas.Token:
    """
    Fluxo de autenticação:
        1. Receber username e senha via form
        2. Buscar usuário no banco
        3. Verificar senha com bcrypt
        4. Gerar e retornar JWT
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
async def logout(usuario_atual: CurrentUser) -> None:
    """
    Invalida a sessão do usuário.
    (Stateless JWT: orientação para o cliente descartar o token.)
    """
    # Stateless JWT — o cliente simplesmente descarta o token.
    # Implementação de blacklist pode ser adicionada futuramente.
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
) -> schemas.UsuarioOut:
    """Cria um novo membro do efetivo com acesso ao sistema."""
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
) -> list[schemas.UsuarioOut]:
    """Retorna a lista completa de usuários cadastrados."""
    usuarios = await service.listar_usuarios(db)
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
