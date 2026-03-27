"""
app/auth/service.py
Camada de serviço (regras de negócio) para autenticação e usuários.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Usuario
from app.auth.schemas import UsuarioCreate, UsuarioUpdate


async def autenticar_usuario(
    db: AsyncSession,
    username: str,
    senha: str,
) -> Usuario | None:
    """
    Valida as credenciais de login.

    Args:
        db: sessão de banco de dados.
        username: nome de usuário fornecido.
        senha: senha em texto plano fornecida.

    Returns:
        Objeto Usuario se as credenciais forem válidas, None caso contrário.
    """
    # TODO (Dia 4):
    # usuario = await buscar_por_username(db, username)
    # if not usuario:
    #     return None
    # if not verificar_senha(senha, usuario.senha_hash):
    #     return None
    # return usuario
    raise NotImplementedError


async def criar_usuario(
    db: AsyncSession,
    dados: UsuarioCreate,
) -> Usuario:
    """
    Cria um novo usuário no banco de dados.

    Faz o hash da senha antes de persistir.

    Args:
        db: sessão de banco de dados.
        dados: schema com os dados de criação.

    Returns:
        Objeto Usuario recém-criado.

    Raises:
        ValueError: se o username já estiver em uso.
    """
    # TODO (Dia 4):
    # existente = await buscar_por_username(db, dados.username)
    # if existente:
    #     raise ValueError(f"Username '{dados.username}' já está em uso.")
    # usuario = Usuario(
    #     nome=dados.nome, posto=dados.posto, especialidade=dados.especialidade,
    #     funcao=dados.funcao, ramal=dados.ramal, username=dados.username,
    #     senha_hash=hash_senha(dados.password),
    # )
    # db.add(usuario)
    # await db.flush()
    # return usuario
    raise NotImplementedError


async def buscar_por_username(
    db: AsyncSession,
    username: str,
) -> Usuario | None:
    """
    Busca um usuário pelo username.

    Args:
        db: sessão de banco de dados.
        username: nome de usuário a buscar.

    Returns:
        Objeto Usuario ou None se não encontrado.
    """
    # TODO (Dia 4):
    # result = await db.execute(select(Usuario).where(Usuario.username == username))
    # return result.scalar_one_or_none()
    raise NotImplementedError


async def buscar_por_id(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> Usuario | None:
    """
    Busca um usuário pelo ID.

    Args:
        db: sessão de banco de dados.
        usuario_id: UUID do usuário.

    Returns:
        Objeto Usuario ou None se não encontrado.
    """
    # TODO (Dia 4):
    # return await db.get(Usuario, usuario_id)
    raise NotImplementedError


async def listar_usuarios(db: AsyncSession) -> list[Usuario]:
    """
    Retorna a lista completa de usuários do sistema (efetivo).

    Args:
        db: sessão de banco de dados.

    Returns:
        Lista de objetos Usuario.
    """
    # TODO (Dia 4):
    # result = await db.execute(select(Usuario).order_by(Usuario.nome))
    # return list(result.scalars().all())
    raise NotImplementedError


async def atualizar_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    dados: UsuarioUpdate,
) -> Usuario:
    """
    Atualiza parcialmente os dados de um usuário.

    Args:
        db: sessão de banco de dados.
        usuario_id: UUID do usuário a atualizar.
        dados: schema com os campos a modificar.

    Returns:
        Objeto Usuario atualizado.

    Raises:
        ValueError: se o usuário não for encontrado.
    """
    # TODO (Dia 4):
    # usuario = await buscar_por_id(db, usuario_id)
    # if not usuario:
    #     raise ValueError("Usuário não encontrado.")
    # for campo, valor in dados.model_dump(exclude_none=True).items():
    #     setattr(usuario, campo, valor)
    # await db.flush()
    # return usuario
    raise NotImplementedError


async def alterar_senha(
    db: AsyncSession,
    usuario: Usuario,
    senha_atual: str,
    nova_senha: str,
) -> None:
    """
    Altera a senha de um usuário autenticado.

    Args:
        db: sessão de banco de dados.
        usuario: objeto Usuario autenticado.
        senha_atual: senha atual para confirmação.
        nova_senha: nova senha a ser definida.

    Raises:
        ValueError: se a senha atual for incorreta.
    """
    # TODO (Dia 4):
    # if not verificar_senha(senha_atual, usuario.senha_hash):
    #     raise ValueError("Senha atual incorreta.")
    # usuario.senha_hash = hash_senha(nova_senha)
    # await db.flush()
    raise NotImplementedError
