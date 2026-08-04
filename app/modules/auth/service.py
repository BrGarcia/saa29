"""
app/auth/service.py
Camada de serviço (regras de negócio) para autenticação e usuários.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.config import get_settings
from app.modules.auth import roles
from app.modules.auth.models import TokenBlacklist, TokenRefresh, Usuario
from app.modules.auth.schemas import UsuarioCreate, UsuarioUpdate
from app.modules.auth.security import hash_senha, verificar_senha
from app.shared.core import exceptions as domain_exc
from app.shared.core import helpers

logger = logging.getLogger(__name__)

_LOCKOUT_MAX_TENTATIVAS = 5
_LOCKOUT_DURACAO_MINUTOS = 15

# Hash dummy fixo para equalizar o tempo de resposta do login quando o
# usuário não existe ou está inativo (item #9/Etapa 4). Medido: o caminho
# com hashing bcrypt real leva ~227ms; o early-return sem hashing leva
# <1ms — um oráculo de timing trivial para enumerar usernames válidos,
# mesmo com o rate limit de 5/min do endpoint (a diferença é grande o
# suficiente para ser distinguível numa única requisição). O valor em si é
# irrelevante — nunca precisa bater com nada, só pagar o custo do bcrypt.
_DUMMY_HASH = hash_senha("dummy-timing-equalizer-nao-e-senha-real")


async def autenticar_usuario(
    db: AsyncSession,
    username: str,
    senha: str,
) -> Usuario | None:
    """
    Valida as credenciais de login com proteção contra brute force (Account Lockout).
    Em APP_ENV=development, o bloqueio é ignorado para facilitar testes locais.
    """
    usuario = await buscar_por_username(db, username)
    if not usuario or not usuario.ativo:
        # Paga o custo do bcrypt mesmo quando o usuário não existe/está
        # inativo, para que a resposta não revele — pelo tempo — se o
        # username é válido. Roda em threadpool (RISCO-05): bcrypt é
        # CPU-bound e síncrono, e chamá-lo direto no event loop travaria
        # todas as outras requisições em andamento no mesmo worker.
        await asyncio.to_thread(verificar_senha, senha, _DUMMY_HASH)
        return None

    # Fonte única de verdade para o ambiente (settings.app_env, não os.getenv
    # direto — duas fontes divergentes para a mesma decisão de segurança era
    # o próprio risco: settings.app_env é o valor validado/cacheado usado no
    # resto da aplicação, inclusive no middleware de CSRF).
    _is_dev = get_settings().app_env == "development"

    if not _is_dev:
        # Verificar se a conta está bloqueada
        agora = datetime.now(timezone.utc)
        if usuario.locked_until and usuario.locked_until.tzinfo is None:
            usuario.locked_until = usuario.locked_until.replace(tzinfo=timezone.utc)

        if usuario.locked_until and agora < usuario.locked_until:
            minutos_restantes = int((usuario.locked_until - agora).total_seconds() / 60)
            raise domain_exc.ContaBloqueadaError(
                f"Conta temporariamente bloqueada após múltiplas tentativas falhas. Tente novamente em {max(1, minutos_restantes)} minutos."
            )

    # Validar senha (threadpool — ver comentário acima sobre RISCO-05)
    if not await asyncio.to_thread(verificar_senha, senha, usuario.senha_hash):
        if not _is_dev:
            # Incrementar contador de falhas apenas em produção
            usuario.failed_login_attempts += 1
            agora = datetime.now(timezone.utc)
            if usuario.failed_login_attempts >= _LOCKOUT_MAX_TENTATIVAS:
                usuario.locked_until = agora + timedelta(minutes=_LOCKOUT_DURACAO_MINUTOS)
            await db.flush()
        return None

    # Sucesso: Resetar contador
    usuario.failed_login_attempts = 0
    usuario.locked_until = None
    await db.flush()

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
        raise domain_exc.ConflitoNegocioError(f"Username '{dados.username}' já está em uso.")
    usuario = Usuario(
        nome=dados.nome,
        posto=dados.posto,
        especialidade=dados.especialidade,
        funcao=dados.funcao,
        ramal=dados.ramal,
        trigrama=dados.trigrama.upper() if dados.trigrama else None,
        username=username_lower,
        senha_hash=await asyncio.to_thread(hash_senha, dados.password),
    )
    try:
        # SAVEPOINT: em caso de criação concorrente com o mesmo username,
        # desfaz apenas este insert e mantém a transação da requisição
        # utilizável (mesmo padrão das Etapas 1-3).
        async with db.begin_nested():
            db.add(usuario)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar usuário %s: %s", username_lower, exc.orig)
        raise domain_exc.ConflitoNegocioError(f"Username '{dados.username}' já está em uso.") from exc
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
    db: AsyncSession,
    incluir_inativos: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[Usuario]:
    """
    Retorna a lista de usuários do sistema (efetivo).

    `limit`/`offset` são opcionais (MELHORIA-22) — sem eles, mantém o
    comportamento anterior de retornar o efetivo completo.
    """
    query = select(Usuario)
    if not incluir_inativos:
        query = query.where(Usuario.ativo.is_(True))
    query = query.order_by(Usuario.nome).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
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
        raise domain_exc.EntidadeNaoEncontradaError("Usuário não encontrado.")

    CAMPOS_EDITAVEIS = {"nome", "posto", "especialidade", "funcao", "ramal", "trigrama"}
    updates = {
        campo: valor
        for campo, valor in dados.model_dump(exclude_unset=True).items()
        if campo in CAMPOS_EDITAVEIS
    }
    if updates.get("trigrama"):
        updates["trigrama"] = updates["trigrama"].upper()

    # BUG-03: trocar a função do último administrador ativo para outro papel
    # contornava a proteção do AUD-17 (que só existia em excluir_usuario).
    # A checagem+update precisa ser uma única instrução atômica (RISCO-07),
    # senão duas requisições concorrentes podem ler a mesma contagem antes
    # de qualquer uma comitar.
    remove_ultimo_admin = (
        "funcao" in updates
        and usuario.funcao in roles.ADMIN_FUNCTIONS
        and updates["funcao"] not in roles.ADMIN_FUNCTIONS
    )
    if remove_ultimo_admin:
        admins_ativos = (
            select(func.count(Usuario.id))
            .where(Usuario.funcao.in_(roles.ADMIN_FUNCTIONS), Usuario.ativo.is_(True))
            .scalar_subquery()
        )
        resultado = await db.execute(
            update(Usuario)
            .where(Usuario.id == usuario_id, admins_ativos > 1)
            .values(**updates)
        )
        if resultado.rowcount == 0:
            raise domain_exc.ConflitoNegocioError(
                "Não é possível remover o papel de administrador do último administrador ativo do sistema (AUD-17)."
            )
        await db.refresh(usuario)
        return usuario

    for campo, valor in updates.items():
        setattr(usuario, campo, valor)
    await db.flush()
    return usuario


async def _revogar_refresh_tokens_ativos(db: AsyncSession, usuario_id: uuid.UUID) -> None:
    """Revoga todos os refresh tokens ainda ativos do usuário (BUG-02).

    Trocar/resetar a senha precisa encerrar as sessões já emitidas — senão
    um refresh token vazado continua válido e renovável por até
    `settings.refresh_token_expire_days` dias mesmo depois da senha trocada,
    o que derrota o propósito de um reset de senha em resposta a incidente.
    """
    await db.execute(
        update(TokenRefresh)
        .where(TokenRefresh.usuario_id == usuario_id, TokenRefresh.revogado_em.is_(None))
        .values(revogado_em=datetime.now(timezone.utc))
    )


async def alterar_senha(
    db: AsyncSession,
    usuario: Usuario,
    senha_atual: str,
    nova_senha: str,
) -> None:
    """
    Altera a senha de um usuário autenticado.
    """
    if not await asyncio.to_thread(verificar_senha, senha_atual, usuario.senha_hash):
        raise domain_exc.ConflitoNegocioError("Senha atual incorreta.")
    usuario.senha_hash = await asyncio.to_thread(hash_senha, nova_senha)
    await _revogar_refresh_tokens_ativos(db, usuario.id)
    await db.flush()

async def admin_resetar_senha(
    db: AsyncSession,
    usuario_id: uuid.UUID,
    nova_senha: str,
) -> None:
    """
    Permite que um Administrador redefina a senha de qualquer usuário
    sem precisar da senha atual.
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuário não encontrado.")

    usuario.senha_hash = await asyncio.to_thread(hash_senha, nova_senha)
    await _revogar_refresh_tokens_ativos(db, usuario.id)
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
        raise domain_exc.ConflitoNegocioError("Não é possível desativar o próprio usuário (AUD-17).")

    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuário não encontrado.")

    # RISCO-07 (TOCTOU): a contagem de admins ativos e o UPDATE precisam ser
    # a mesma instrução atômica — senão duas requisições concorrentes contra
    # os dois últimos admins podem ambas ler a contagem "2" antes de
    # qualquer uma comitar, e as duas passam.
    condicoes = [Usuario.id == usuario_id]
    if usuario.funcao in roles.ADMIN_FUNCTIONS:
        admins_ativos = (
            select(func.count(Usuario.id))
            .where(Usuario.funcao.in_(roles.ADMIN_FUNCTIONS), Usuario.ativo.is_(True))
            .scalar_subquery()
        )
        condicoes.append(admins_ativos > 1)

    resultado = await db.execute(update(Usuario).where(*condicoes).values(ativo=False))
    if resultado.rowcount == 0:
        raise domain_exc.ConflitoNegocioError("Não é possível desativar o último administrador do sistema (AUD-17).")


async def restaurar_usuario(
    db: AsyncSession,
    usuario_id: uuid.UUID,
) -> Usuario:
    """
    Reativa um usuário desativado.
    """
    usuario = await buscar_por_id(db, usuario_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuário não encontrado.")

    usuario.ativo = True
    await db.flush()
    return usuario


async def garantir_usuarios_essenciais(db: AsyncSession) -> None:
    """
    Garante que os usuários vitais (Admin) e de teste existam.
    Esta função centraliza a lógica que antes estava espalhada em scripts de fix/seed.
    Invocada manualmente por `scripts/db/init_db.py` / `scripts/seed/seed_auth.py`
    (não faz parte do lifespan da aplicação).
    """
    settings = get_settings()

    # 1. Garantir Admin Oficial (via Settings/.env)
    # BUG-04: normalizado para minúsculas — criar_usuario/buscar_por_username
    # sempre operam em lowercase, então uma busca com case cru aqui não
    # encontra um admin já existente com DEFAULT_ADMIN_USER de case
    # diferente, insere um segundo registro "duplicado" e a próxima busca de
    # login (via func.lower()) explode com MultipleResultsFound.
    admin_user = settings.default_admin_user.strip().lower()
    admin_pass = settings.default_admin_password

    if admin_pass:
        res = await db.execute(select(Usuario).where(Usuario.username == admin_user))
        admin = res.scalar_one_or_none()
        if not admin:
            logger.info("Criando admin padrão (%s).", admin_user)
            admin = Usuario(
                nome="Administrador Sistema",
                posto="Cap",
                especialidade="ENG",
                funcao=roles.ADMINISTRADOR,
                ramal="1234",
                username=admin_user,
                senha_hash=await asyncio.to_thread(hash_senha, admin_pass),
            )
            db.add(admin)
        else:
            # Garantir que o admin tenha o papel correto
            if admin.funcao != roles.ADMINISTRADOR:
                admin.funcao = roles.ADMINISTRADOR
                logger.warning("Corrigindo papel do admin (%s) para ADMINISTRADOR.", admin_user)

            # A senha do admin NÃO é sobrescrita aqui a cada execução — isso
            # tornava impossível rotacionar a senha pela UI (ela "voltava"
            # sozinha ao valor do .env no próximo boot/seed). Redefinição só
            # ocorre com o flag explícito e temporário settings.admin_password_reset,
            # para o cenário legítimo de restore de banco após backup do R2.
            if settings.admin_password_reset:
                if not await asyncio.to_thread(verificar_senha, admin_pass, admin.senha_hash):
                    admin.senha_hash = await asyncio.to_thread(hash_senha, admin_pass)
                    logger.warning(
                        "ADMIN_PASSWORD_RESET ativo: senha do admin (%s) redefinida para o valor do .env.",
                        admin_user,
                    )

    # 2. Garantir Usuários de Teste — exige DOIS gatilhos explícitos (defesa
    # em profundidade): app_env=="development" E enable_test_users=True. Um
    # único gatilho (só APP_ENV) é frágil — um deploy com a variável
    # ausente/errada instalaria 3 contas privilegiadas com senha trivial.
    if settings.app_env == "development" and settings.enable_test_users:
        usuarios_teste = [
            ("encarregado", roles.ENCARREGADO, "Chefe de Linha", "Cap"),
            ("inspetor", roles.INSPETOR, "Inspetor de Qualidade", "SO"),
            ("mantenedor", roles.MANTENEDOR, "Técnico Especialista", "Sgt"),
        ]
        for user, role, nome, posto in usuarios_teste:
            user = user.lower()
            res = await db.execute(select(Usuario).where(Usuario.username == user))
            u = res.scalar_one_or_none()
            if not u:
                logger.info("Criando usuário de teste (%s).", user)
                u = Usuario(
                    nome=nome,
                    posto=posto,
                    especialidade="BMB",
                    funcao=role,
                    ramal="0000",
                    username=user,
                    senha_hash=await asyncio.to_thread(hash_senha, "123456"),
                )
                db.add(u)
                await db.flush()

                # Opcionalmente, inicializar indisponibilidade para o mantenedor em dev
                if user == "mantenedor":
                    from app.modules.efetivo.models import Indisponibilidade
                    from app.shared.core.enums import TipoIndisponibilidade
                    logger.info("Adicionando indisponibilidade de teste para %s.", user)
                    # Atalho consciente: grava direto via ORM, contornando
                    # efetivo.service.registrar_indisponibilidade (e suas validações
                    # de sobreposição de período e data_fim >= data_inicio) — aceitável
                    # aqui porque é dado de seed fixo e controlado, não input de usuário.
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
    agora = datetime.now(timezone.utc)

    # Limpa blacklist
    await db.execute(delete(TokenBlacklist).where(TokenBlacklist.expira_em < agora))
    # Limpa refresh tokens
    await db.execute(delete(TokenRefresh).where(TokenRefresh.expira_em < agora))
    await db.flush()
