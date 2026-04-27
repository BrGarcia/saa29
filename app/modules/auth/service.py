"""
app/auth/service.py
Camada de serviço (regras de negócio) para autenticação e usuários.
"""

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Usuario
from app.modules.auth.schemas import UsuarioCreate, UsuarioUpdate
from app.modules.auth.security import hash_senha, verificar_senha
from app.shared.core import helpers


async def autenticar_usuario(
    db: AsyncSession,
    username: str,
    senha: str,
) -> Usuario | None:
    """
    Valida as credenciais de login com proteção contra brute force (Account Lockout).
    """
    from datetime import datetime, timezone, timedelta
    from fastapi import HTTPException, status

    usuario = await buscar_por_username(db, username)
    if not usuario:
        return None
    if not usuario.ativo:
        return None

    # Verificar se a conta está bloqueada
    agora = datetime.now(timezone.utc)
    if usuario.locked_until and usuario.locked_until.tzinfo is None:
        # Fallback para naive datetime se necessário, embora o ideal seja timezone-aware
        usuario.locked_until = usuario.locked_until.replace(tzinfo=timezone.utc)

    if usuario.locked_until and agora < usuario.locked_until:
        minutos_restantes = int((usuario.locked_until - agora).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Conta temporariamente bloqueada após múltiplas tentativas falhas. Tente novamente em {max(1, minutos_restantes)} minutos."
        )

    # Validar senha
    if not verificar_senha(senha, usuario.senha_hash):
        # Incrementar contador de falhas
        usuario.failed_login_attempts += 1
        
        # Bloquear se atingir o limite (ex: 5 tentativas)
        if usuario.failed_login_attempts >= 5:
            usuario.locked_until = agora + timedelta(minutes=15)
        
        await db.commit()
        return None

    # Sucesso: Resetar contador
    usuario.failed_login_attempts = 0
    usuario.locked_until = None
    await db.commit()
    
    return usuario


async def criar_usuario(
    db: AsyncSession,
    dados: UsuarioCreate,
) -> Usuario:
    """
    Cria um novo usuário no banco de dados.
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
    """Busca um usuário pelo username de forma case-insensitive."""
    return await helpers.buscar_usuario_por_username(db, username)


async def buscar_por_id(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> Usuario | None:
    """Busca um usuário pelo ID."""
    return await helpers.buscar_usuario_por_id(db, usuario_id)


async def listar_usuarios(
    db: AsyncSession, incluir_inativos: bool = False
) -> list[Usuario]:
    """
    Retorna a lista completa de usuários do sistema (efetivo).
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
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")
    
    CAMPOS_EDITAVEIS = {"nome", "posto", "especialidade", "funcao", "ramal", "trigrama"}

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo not in CAMPOS_EDITAVEIS:
            continue
        
        if campo == "trigrama" and valor:
            valor = valor.upper()
            
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
    """
    if not verificar_senha(senha_atual, usuario.senha_hash):
        raise ValueError("Senha atual incorreta.")
    usuario.senha_hash = hash_senha(nova_senha)
    await db.flush()


async def excluir_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    usuario_logado_id: uuid.UUID | None = None,
) -> None:
    """
    Desativa (exclusão lógica) um usuário do efetivo.
    """
    if usuario_id == usuario_logado_id:
        raise ValueError("Não é possível desativar o próprio usuário (AUD-17).")

    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    if usuario.funcao == "ADMINISTRADOR":
        result = await db.execute(
            select(func.count(Usuario.id)).where(
                Usuario.funcao == "ADMINISTRADOR",
                Usuario.ativo == True
            )
        )
        admins_ativos = result.scalar()
        if admins_ativos <= 1:
            raise ValueError("Não é possível desativar o último administrador do sistema (AUD-17).")

    usuario.ativo = False
    await db.flush()


async def restaurar_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> Usuario:
    """
    Reativa um usuário desativado.
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    usuario.ativo = True
    await db.flush()
    return usuario


async def garantir_usuarios_essenciais(db: AsyncSession) -> None:
    """
    Garante que os usuários vitais (Admin) e de teste existam.
    Esta função centraliza a lógica que antes estava espalhada em scripts de fix/seed.
    """
    import os
    from app.modules.auth.models import Usuario
    from app.modules.auth.security import hash_senha
    from sqlalchemy import select

    # 1. Garantir Admin Oficial (via .env)
    admin_user = os.getenv("DEFAULT_ADMIN_USER", "admin").strip()
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD")

    if admin_pass:
        res = await db.execute(select(Usuario).where(Usuario.username == admin_user))
        admin = res.scalar_one_or_none()
        if not admin:
            print(f"AuthService: Criando admin padrão ({admin_user})...")
            admin = Usuario(
                nome="Administrador Sistema",
                posto="Cap",
                especialidade="ENG",
                funcao="ADMINISTRADOR",
                ramal="1234",
                username=admin_user,
                senha_hash=hash_senha(admin_pass),
            )
            db.add(admin)
        else:
            # Garantir que o admin tenha o papel correto
            if admin.funcao != "ADMINISTRADOR":
                admin.funcao = "ADMINISTRADOR"
                print(f"AuthService: Corrigindo papel do admin para ADMINISTRADOR.")

    # 2. Garantir Usuários de Teste (apenas se APP_ENV for development)
    if os.getenv("APP_ENV") == "development":
        usuarios_teste = [
            ("encarregado", "ENCARREGADO", "Chefe de Linha", "Cap"),
            ("mantenedor", "MANTENEDOR", "Técnico Especialista", "Sgt"),
        ]
        for user, role, nome, posto in usuarios_teste:
            res = await db.execute(select(Usuario).where(Usuario.username == user))
            u = res.scalar_one_or_none()
            if not u:
                print(f"AuthService: Criando usuário de teste ({user})...")
                u = Usuario(
                    nome=nome,
                    posto=posto,
                    especialidade="BMB",
                    funcao=role,
                    ramal="0000",
                    username=user,
                    senha_hash=hash_senha("123456"),
                )
                db.add(u)
                await db.flush()
                
                # Opcionalmente, inicializar indisponibilidade para o mantenedor em dev
                if user == "mantenedor":
                    from app.modules.efetivo.models import Indisponibilidade
                    from app.shared.core.enums import TipoIndisponibilidade
                    from datetime import date, timedelta
                    print(f"AuthService: Adicionando indisponibilidade de teste para {user}.")
                    indisp = Indisponibilidade(
                        usuario_id=u.id,
                        tipo=TipoIndisponibilidade.FERIAS.value,
                        data_inicio=date.today() + timedelta(days=1),
                        data_fim=date.today() + timedelta(days=15),
                        observacao="Férias programadas (Seed Automático)"
                    )
                    db.add(indisp)

                    await db.flush()

async def limpar_tokens_expirados(db: AsyncSession) -> None:
    from sqlalchemy import delete
    from datetime import datetime, timezone
    from app.modules.auth.models import TokenBlacklist, TokenRefresh
    agora = datetime.now(timezone.utc)

    # Limpa blacklist
    await db.execute(delete(TokenBlacklist).where(TokenBlacklist.expira_em < agora))
    # Limpa refresh tokens
    await db.execute(delete(TokenRefresh).where(TokenRefresh.expira_em < agora))
    await db.flush()
