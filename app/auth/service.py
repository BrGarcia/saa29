"""
app/auth/service.py
Camada de serviço (regras de negócio) para autenticação e usuários.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError
from app.auth.models import Usuario
from app.auth.schemas import UsuarioCreate, UsuarioUpdate
from app.auth.security import hash_senha, verificar_senha


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
        Objeto Usuario se as credenciais forem válidas e o usuário estiver ativo, None caso contrário.
    """
    usuario = await buscar_por_username(db, username)
    if not usuario:
        return None
    if not usuario.ativo:
        return None
    if not verificar_senha(senha, usuario.senha_hash):
        return None
    return usuario


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
    username_lower = dados.username.lower()
    existente = await buscar_por_username(db, username_lower)
    if existente:
        raise ValueError(f"Username '{dados.username}' já está em uso.")
    usuario = Usuario(
        nome=dados.nome,
        posto=dados.posto,
        especialidade=dados.especialidade,
        funcao=dados.funcao,
        ramal=dados.ramal,
        trigrama=dados.trigrama.upper() if dados.trigrama else None,
        username=username_lower,
        senha_hash=hash_senha(dados.password),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def buscar_por_username(
    db: AsyncSession,
    username: str,
) -> Usuario | None:
    """
    Busca um usuário pelo username de forma case-insensitive.

    Args:
        db: sessão de banco de dados.
        username: nome de usuário a buscar.

    Returns:
        Objeto Usuario ou None se não encontrado.
    """
    from sqlalchemy import func
    result = await db.execute(
        select(Usuario).where(func.lower(Usuario.username) == username.lower())
    )
    return result.scalar_one_or_none()


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
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    return result.scalar_one_or_none()


async def listar_usuarios(
    db: AsyncSession, incluir_inativos: bool = False
) -> list[Usuario]:
    """
    Retorna a lista completa de usuários do sistema (efetivo).

    Args:
        db: sessão de banco de dados.
        incluir_inativos: se True, traz também usuários desativados.

    Returns:
        Lista de objetos Usuario.
    """
    query = select(Usuario)
    if not incluir_inativos:
        query = query.where(Usuario.ativo == True)
    result = await db.execute(query.order_by(Usuario.nome))
    return list(result.scalars().all())


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
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")
    
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo == "username":
            valor = valor.lower()
            if valor != usuario.username:
                existente = await buscar_por_username(db, valor)
                if existente:
                    raise ValueError(f"Username '{valor}' já está em uso.")
        setattr(usuario, campo, valor)
    await db.flush()
    return usuario


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
    if not verificar_senha(senha_atual, usuario.senha_hash):
        raise ValueError("Senha atual incorreta.")
    usuario.senha_hash = hash_senha(nova_senha)
    await db.flush()


async def excluir_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> None:
    """
    Desativa (exclusão lógica) um usuário do efetivo.

    Args:
        db: sessão de banco de dados.
        usuario_id: UUID do usuário a desativar.

    Raises:
        ValueError: se o usuário não for encontrado.
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    usuario.ativo = False
    await db.flush()


async def restaurar_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> Usuario:
    """
    Reativa um usuário desativado.

    Args:
        db: sessão de banco de dados.
        usuario_id: UUID do usuário a restaurar.

    Returns:
        Objeto Usuario reativado.

    Raises:
        ValueError: se o usuário não for encontrado.
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    usuario.ativo = True
    await db.flush()
    return usuario
