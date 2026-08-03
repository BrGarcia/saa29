"""
app/panes/service.py
Camada de serviço para gestão de panes aeronáuticas.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

try:
    import magic
    _MAGIC_AVAILABLE = True
except Exception:
    _MAGIC_AVAILABLE = False
from sqlalchemy import select, or_, exists, func, Integer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.panes.models import Pane, Anexo, PaneResponsavel, SistemaAta
from app.modules.aeronaves.models import Aeronave # Importar aqui para evitar InvalidRequestError
from app.modules.panes.schemas import PaneCreate, PaneUpdate, FiltroPane, AdicionarResponsavel
from app.shared.core.enums import StatusPane, StatusAeronave
from app.shared.core.db_utils import escape_like
from app.shared.core import exceptions as domain_exc
from app.shared.core import file_validators
from app.bootstrap.config import get_settings
from app.shared.core.storage import get_storage_service


def _get_year_func(db: AsyncSession, column):
    """Retorna a função de extração de ano compatível com o banco atual.

    Item #18 (relatorio_panes_service.md): detecta o dialeto via
    `db.bind.dialect.name` (atributo já resolvido pela engine, sem I/O) em vez
    de chamar `get_settings()` e fazer parsing de string a cada invocação.
    """
    if db.bind.dialect.name == "sqlite":
        # SQLite: strftime('%Y', data) retorna string, convertemos para int
        return func.cast(func.strftime("%Y", column), Integer)
    # PostgreSQL / Outros: extract(year from data)
    return func.extract("year", column).cast(Integer)


# Transições de status permitidas (SPECS §8)
_TRANSICOES_VALIDAS = {
    StatusPane.ABERTA: {StatusPane.RESOLVIDA},
    StatusPane.RESOLVIDA: set(),  # Pane resolvida não pode transicionar
}

# Extensões/MIMEs permitidos para upload — fonte única em
# app/shared/core/file_validators.py (item #3/Etapa 5). Antes, este módulo
# mantinha sua própria cópia com HEIC/HEIF, mas o router chama
# `file_validators.validate_file_upload` ANTES de qualquer código deste
# arquivo — como aquele validador não conhecia HEIC/HEIF, todo upload real
# desse formato já era rejeitado com 422 ali, tornando esta allowlist (e o
# pipeline de conversão HEIC em app/shared/services/image/) inalcançável.
_EXTENSOES_PERMITIDAS = file_validators.EXTENSOES_PERMITIDAS
_MIMES_PERMITIDOS = file_validators.MIMES_PERMITIDOS

# Item #31 (relatorio_panes_service.md): extensão e MIME eram validados
# separadamente, sem checar coerência entre eles — um "foto.pdf" com bytes de
# PNG passava (extensão .pdf permitida, MIME image/png permitido) e virava
# imagem com extensão de PDF.
_EXTENSAO_MIME_MAP = file_validators.EXTENSAO_MIME_MAP

logger = logging.getLogger(__name__)


def _get_ranking_subquery(db: AsyncSession):
    """Retorna a subquery de ranking para cálculo do código ddd/yy.

    Item #14 (relatorio_panes_service.md): função síncrona (não tem `await`
    no corpo) — `listar_panes` chamava esta lógica duplicada inline em vez de
    reutilizar este helper.
    """
    year_func = _get_year_func(db, Pane.data_abertura)
    return select(
        Pane.id.label("pane_id"),
        func.row_number().over(
            partition_by=[year_func],
            order_by=[Pane.data_abertura.asc(), Pane.id.asc()],
        ).label("sequencia"),
        year_func.label("ano"),
    ).subquery()


async def sincronizar_status_aeronave(db: AsyncSession, aeronave_id: uuid.UUID) -> None:
    """
    Sincroniza o status da aeronave com base nas regras de negócio da frota:
    1. Se possui inspeção ativa ➔ status é INSPEÇÃO (prioridade sobre as demais regras).
    2. Senão, se possui pane aberta ➔ status muda para INDISPONIVEL (a menos que esteja inativa ou estocada).
    3. Senão ➔ status retorna para DISPONIVEL (caso estivesse INDISPONIVEL ou INSPEÇÃO).

    Item #3 (relatorio_panes_service.md): usa `with_for_update` para reduzir a
    janela de "lost update" quando duas panes da mesma aeronave são
    criadas/resolvidas concorrentemente. Em SQLite (backend atual) a cláusula
    é compilada como no-op — o ganho real de exclusão mútua vale para quando
    o projeto migrar para um banco que a suporte (ex.: PostgreSQL); mesmo
    assim, mantém a leitura+escrita da aeronave dentro da mesma linha lógica.
    """
    from app.modules.inspecoes.models import Inspecao
    from app.modules.inspecoes.service import STATUS_ATIVOS

    aeronave = await db.get(Aeronave, aeronave_id, with_for_update=True)
    if not aeronave:
        return

    # Item #15 (relatorio_panes_service.md): EXISTS é mais barato que COUNT
    # para checagens booleanas — o banco pode parar na primeira linha.
    q_panes = select(exists().where(
        Pane.aeronave_id == aeronave_id,
        Pane.status == StatusPane.ABERTA.value,
        Pane.ativo == True,
    ))
    tem_panes_abertas = bool((await db.execute(q_panes)).scalar())

    q_insp = select(exists().where(
        Inspecao.aeronave_id == aeronave_id,
        Inspecao.status.in_(STATUS_ATIVOS),
    ))
    tem_inspecao_ativa = bool((await db.execute(q_insp)).scalar())

    status_str = aeronave.status.value if hasattr(aeronave.status, 'value') else str(aeronave.status)

    # `tem_inspecao_ativa` já é a fonte de verdade (consulta ao vivo) sobre se a
    # aeronave está sob inspeção — por isso os ramos abaixo não reexaminam o
    # status "INSPECAO"/"INSPEÇÃO" gravado anteriormente. Fazer isso é o bug
    # original: quando uma inspeção é concluída/cancelada com uma pane ainda
    # aberta, o status gravado no momento da chamada ainda é INSPECAO (foi
    # setado pela própria inspeção que está sendo encerrada), e um guard que
    # excluísse a transição nesse caso deixaria a aeronave presa em INSPECAO
    # para sempre.
    if tem_inspecao_ativa:
        aeronave.status = StatusAeronave.INSPECAO
    elif tem_panes_abertas:
        if status_str not in [StatusAeronave.INATIVA.value, StatusAeronave.ESTOCADA.value]:
            aeronave.status = StatusAeronave.INDISPONIVEL
    else:
        if status_str in [StatusAeronave.INDISPONIVEL.value, StatusAeronave.INSPECAO.value, "INSPEÇÃO"]:
            aeronave.status = StatusAeronave.DISPONIVEL

    db.add(aeronave)
    await db.flush()


async def criar_pane(
    db: AsyncSession,
    dados: PaneCreate,
    criado_por_id: uuid.UUID,
) -> Pane:
    """
    Abre uma nova pane no sistema.

    Algoritmo (SPECS §3 – Nova Pane):
        1. Validar se a aeronave existe
        2. Definir status = ABERTA (RN-02)
        3. Definir descricao = "AGUARDANDO EDICAO" se vazia (RN-05)
        4. Definir data_abertura = NOW() automático
        5. Vincular criado_por = usuário logado
        6. Salvar no banco

    Args:
        db: sessão de banco de dados.
        dados: schema com dados da pane.
        criado_por_id: UUID do usuário autenticado.

    Returns:
        Objeto Pane recém-criado.
    """
    # Validar existência da aeronave
    from app.modules.aeronaves.service import buscar_aeronave
    aeronave = await buscar_aeronave(db, dados.aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")
    if aeronave.status == StatusAeronave.INATIVA:
        raise ValueError("Aeronave inativa. Reative a aeronave antes de registrar uma pane.")

    # RN-05: descrição padrão se vazia
    descricao = dados.descricao.strip() if dados.descricao else ""
    if not descricao:
        descricao = "AGUARDANDO EDICAO"

    pane = Pane(
        aeronave_id=dados.aeronave_id,
        status=StatusPane.ABERTA.value,
        sistema_ata_id=dados.sistema_ata_id,
        descricao=descricao,
        criado_por_id=criado_por_id,
    )
    db.add(pane)
    await db.flush()

    if dados.mantenedor_responsavel_id:
        from app.modules.auth.service import buscar_por_id
        usuario_responsavel = await buscar_por_id(db, dados.mantenedor_responsavel_id)
        if not usuario_responsavel:
            raise ValueError("Mantenedor responsável não encontrado.")
        if usuario_responsavel.funcao not in ["MANTENEDOR", "ENCARREGADO"]:
            raise ValueError("O responsável selecionado deve ser um mantenedor ou encarregado.")

        resp = PaneResponsavel(
            pane_id=pane.id,
            usuario_id=usuario_responsavel.id,
            papel=usuario_responsavel.funcao,
        )
        db.add(resp)
        await db.flush()
        # Importante: Carregar o usuário para que o trigrama esteja disponível na serialização
        await db.refresh(resp, ["usuario"])

    # Sincroniza o status da aeronave para INDISPONIVEL (se estava DISPONIVEL)
    await sincronizar_status_aeronave(db, dados.aeronave_id)

    # Garantir que as coleções estejam inicializadas para evitar erro de lazy-load no router.
    #
    # Item #16 (relatorio_panes_service.md) — tentativa revertida: cheguei a
    # substituir isto por população manual (assumindo que uma coleção nunca
    # tocada permanece "vazia e carregada" após o flush), mas medi errado —
    # após `db.flush()`, um objeto passa a "persistent" e suas relações viram
    # not-loaded de verdade; acessá-las fora de um refresh dispara lazy-load
    # síncrono, que quebra em contexto async (`MissingGreenlet`). Confirmado
    # com um teste direto antes de decidir reverter. Mantido como estava.
    await db.refresh(pane, ["aeronave", "anexos", "responsaveis", "sistema_ata"])

    return pane


async def listar_panes(
    db: AsyncSession,
    filtros: FiltroPane | None = None,
) -> list[tuple[Pane, int, int]]:
    """
    Lista panes com filtros opcionais (RF-06).

    Algoritmo (SPECS §10 – Filtrar Panes):
        1. Receber parâmetros: texto, status, aeronave, data
        2. Construir query dinâmica com AND condicional
        3. Executar busca ordenada por data_abertura DESC

    COR-01: filtro ativo/inativo é SEMPRE aplicado, mesmo sem filtros.

    Args:
        db: sessão de banco de dados.
        filtros: schema com os filtros a aplicar.

    Returns:
        Lista de Panes filtradas.
    """
    ranking_subquery = _get_ranking_subquery(db)

    query = (
        select(Pane, ranking_subquery.c.sequencia, ranking_subquery.c.ano)
        .join(ranking_subquery, ranking_subquery.c.pane_id == Pane.id)
        .order_by(Pane.data_abertura.desc())
    )

    # COR-01: sempre filtrar por ativo, exceto se explicitamente pedido
    mostrar_excluidas = filtros.excluidas if filtros else False
    if mostrar_excluidas:
        query = query.where(Pane.ativo == False)  # noqa: E712
    else:
        query = query.where(Pane.ativo == True)  # noqa: E712

    if filtros:
        if filtros.status:
            query = query.where(Pane.status == filtros.status.value)

        if filtros.aeronave_id:
            query = query.where(Pane.aeronave_id == filtros.aeronave_id)

        if filtros.texto:
            texto_like = f"%{escape_like(filtros.texto.lower())}%"
            query = query.outerjoin(Aeronave, Pane.aeronave_id == Aeronave.id).outerjoin(SistemaAta, Pane.sistema_ata_id == SistemaAta.id).where(
                or_(
                    func.lower(Pane.descricao).like(texto_like, escape="\\"),
                    func.lower(SistemaAta.descricao).like(texto_like, escape="\\"),
                    func.lower(Aeronave.matricula).like(texto_like, escape="\\"),
                )
            )

        if filtros.data_inicio:
            query = query.where(Pane.data_abertura >= filtros.data_inicio)

        if filtros.data_fim:
            # Item #28 (relatorio_panes_service.md): data_fim normalmente chega
            # como uma DATA (ex.: <input type="date"> vira meia-noite UTC ao
            # ser parseado como datetime). Comparar com `<=` excluía panes
            # abertas depois de 00:00 no próprio dia final. `< data_fim + 1 dia`
            # inclui o dia inteiro, tratando data_fim como limite de dia.
            query = query.where(Pane.data_abertura < filtros.data_fim + timedelta(days=1))

        query = query.offset(filtros.skip).limit(filtros.limit)
    else:
        # AUD-14: Garante que nunca retorne todos os registros sem limite
        query = query.limit(100)

    # Eager-load aeronave para exibir matricula no frontend e responsaveis para o dashboard
    query = query.options(
        selectinload(Pane.aeronave),
        selectinload(Pane.criador),
        selectinload(Pane.sistema_ata),
        selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario)
    )

    result = await db.execute(query)
    return [
        (row[0], int(row[1]), int(row[2]))
        for row in result.all()
    ]


async def buscar_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> tuple[Pane, int, int] | None:
    """
    Busca uma pane pelo ID com seus anexos e responsáveis carregados.
    Também calcula sequencia e ano para o código ddd/yy.

    Args:
        db: sessão de banco de dados.
        pane_id: UUID da pane.
        incluir_inativos: se True, inclui panes soft-deleted.

    Returns:
        Tupla (Pane, sequencia, ano) ou None.
    """
    ranking_sub = _get_ranking_subquery(db)

    query = (
        select(Pane, ranking_sub.c.sequencia, ranking_sub.c.ano)
        .join(ranking_sub, ranking_sub.c.pane_id == Pane.id)
        .where(Pane.id == pane_id)
        .options(
            selectinload(Pane.anexos),
            selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario),
            selectinload(Pane.aeronave),
            selectinload(Pane.criador),
            selectinload(Pane.responsavel_conclusao),
            selectinload(Pane.sistema_ata),
        )
    )
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)  # noqa: E712
    
    result = await db.execute(query)
    row = result.first()
    if not row:
        return None
    
    return (row[0], int(row[1]), int(row[2]))


async def _buscar_pane_por_id(
    db: AsyncSession,
    pane_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> Pane | None:
    """
    Busca apenas o objeto Pane pelo ID sem ranking (usado em operações de escrita).
    """
    query = (
        select(Pane)
        .where(Pane.id == pane_id)
        .options(
            selectinload(Pane.anexos),
            selectinload(Pane.responsaveis).selectinload(PaneResponsavel.usuario),
            selectinload(Pane.aeronave),
            selectinload(Pane.criador),
            selectinload(Pane.responsavel_conclusao),
            selectinload(Pane.sistema_ata),
        )
    )
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)  # noqa: E712
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def editar_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    dados: PaneUpdate,
    usuario_id: uuid.UUID | None = None,
) -> Pane:
    """
    Edita descrição e/ou status de uma pane.

    RN-03: Apenas panes com status ABERTA podem ser editadas.
    Validar transições de status permitidas (SPECS §8):
        ABERTA → RESOLVIDA ✓
        RESOLVIDA → qualquer ✗

    COR-03: Ao transicionar para RESOLVIDA via edição, preenche
    concluido_por_id com o usuário que fez a edição.

    Raises:
        EntidadeNaoEncontradaError: pane inexistente (404).
        ConflitoNegocioError: pane não está aberta, ou transição de status
            inválida (409).
    """
    pane = await _buscar_pane_por_id(db, pane_id)
    if not pane:
        raise domain_exc.EntidadeNaoEncontradaError("Pane não encontrada.")

    status_atual = StatusPane(pane.status)

    # Permitir atualização de comentários independente do status
    if dados.comentarios is not None:
        pane.comentarios = dados.comentarios

    # RN-03: apenas panes abertas podem ser editadas (exceto comentários)
    if status_atual != StatusPane.ABERTA and (dados.descricao is not None or dados.sistema_ata_id is not None or dados.status is not None):
        raise domain_exc.ConflitoNegocioError("Apenas panes abertas podem ter descrição ou status alterados.")

    # Atualizar campos
    if dados.descricao is not None:
        pane.descricao = dados.descricao

    if dados.sistema_ata_id is not None:
        pane.sistema_ata_id = dados.sistema_ata_id

    # Validar transição de status
    if dados.status is not None:
        novo_status = dados.status
        transicoes_permitidas = _TRANSICOES_VALIDAS.get(status_atual, set())
        if novo_status not in transicoes_permitidas:
            raise domain_exc.ConflitoNegocioError(
                f"Transição inválida: {status_atual.value} → {novo_status.value}. "
                f"Transições permitidas: {[s.value for s in transicoes_permitidas]}"
            )
        pane.status = novo_status.value

        # COR-03: Se transicionou para RESOLVIDA, preencher rastreabilidade
        if novo_status == StatusPane.RESOLVIDA:
            pane.data_conclusao = datetime.now(timezone.utc)
            pane.concluido_por_id = usuario_id

    await db.flush()

    # Item #9 (relatorio_panes_service.md): editar_pane transicionava para
    # RESOLVIDA sem sincronizar o status da aeronave — ela permanecia
    # INDISPONIVEL mesmo sem panes abertas restantes.
    if dados.status == StatusPane.RESOLVIDA:
        await sincronizar_status_aeronave(db, pane.aeronave_id)

    return pane


async def concluir_pane(
    db: AsyncSession,
    pane_id: uuid.UUID,
    concluido_por_id: uuid.UUID,
    observacao_conclusao: str | None = None
) -> Pane:
    """
    Conclui uma pane e armazena a acao corretiva.

    Algoritmo (SPECS §7 – Concluir Pane):
        1. Verificar se já está RESOLVIDA
        2. status = RESOLVIDA
        3. data_conclusao = NOW() (RN-04)
        4. concluido_por = usuário logado
        5. Salvar alterações

    Raises:
        EntidadeNaoEncontradaError: pane inexistente (404).
        ConflitoNegocioError: pane já está resolvida (409).
    """
    pane = await _buscar_pane_por_id(db, pane_id)
    if not pane:
        raise domain_exc.EntidadeNaoEncontradaError("Pane não encontrada.")

    if StatusPane(pane.status) == StatusPane.RESOLVIDA:
        raise domain_exc.ConflitoNegocioError("Pane já está resolvida.")

    pane.status = StatusPane.RESOLVIDA.value
    pane.data_conclusao = datetime.now(timezone.utc)
    pane.concluido_por_id = concluido_por_id
    pane.observacao_conclusao = observacao_conclusao

    # RN: Se o usuário que concluiu não é um dos responsáveis, adicioná-lo.
    # Isso garante que ele apareça na listagem de panes como responsável.
    # Item #16 (relatorio_panes_service.md): `pane.responsaveis` já foi
    # carregado por `_buscar_pane_por_id` linhas acima e nada o invalidou
    # desde então — dispensa um refresh só para reler o que já temos.
    ja_responsavel = any(r.usuario_id == concluido_por_id for r in pane.responsaveis)
    tentou_inserir_responsavel = not ja_responsavel

    if not ja_responsavel:
        from app.modules.auth.service import buscar_por_id
        usuario = await buscar_por_id(db, concluido_por_id)
        if usuario:
            resp = PaneResponsavel(
                pane_id=pane_id,
                usuario_id=concluido_por_id,
                papel=usuario.funcao,
            )
            try:
                # Item #2: mesma janela de corrida de adicionar_responsavel —
                # o usuário pode ter sido adicionado como responsável por uma
                # chamada concorrente entre o check acima e este insert.
                async with db.begin_nested():
                    db.add(resp)
                    await db.flush()
                await db.refresh(resp, ["usuario"])
            except IntegrityError:
                pass  # já é responsável (inserido por outra transação) — ok, segue o fluxo

    await db.flush()
    await sincronizar_status_aeronave(db, pane.aeronave_id)

    # Item #16: só recarrega o que pode de fato ter mudado desde o load
    # inicial. `aeronave` foi mutada em memória (mesmo objeto identity-mapped)
    # por `sincronizar_status_aeronave`, sem precisar de refresh; `anexos`
    # nunca é tocado nesta função. `responsavel_conclusao` sempre precisa —
    # o FK `concluido_por_id` acabou de mudar. `responsaveis` só se um insert
    # foi tentado (com ou sem sucesso — bypassa a coleção via `db.add`).
    relacoes_a_recarregar = ["responsavel_conclusao"]
    if tentou_inserir_responsavel:
        relacoes_a_recarregar.append("responsaveis")
    await db.refresh(pane, relacoes_a_recarregar)
    return pane


async def excluir_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane:
    """
    Realiza Soft Delete inativando a pane.

    COR-02: Verifica idempotência (pane já inativa).
    """
    pane = await _buscar_pane_por_id(db, pane_id, incluir_inativos=True)
    if not pane:
        raise ValueError("Pane não encontrada.")

    if not pane.ativo:
        raise ValueError("Pane já está inativa.")
    pane.ativo = False
    await db.flush()
    await sincronizar_status_aeronave(db, pane.aeronave_id)
    return pane


async def restaurar_pane(db: AsyncSession, pane_id: uuid.UUID) -> Pane:
    """
    Restaura uma pane que foi inativada via Soft Delete.
    """
    pane = await _buscar_pane_por_id(db, pane_id, incluir_inativos=True)
    if not pane:
        raise ValueError("Pane não encontrada.")

    if pane.ativo:
        raise ValueError("Pane já está ativa.")
    pane.ativo = True
    await db.flush()
    await sincronizar_status_aeronave(db, pane.aeronave_id)
    return pane


async def upload_anexo(
    db: AsyncSession,
    pane_id: uuid.UUID,
    arquivo_bytes: bytes,
    nome_original: str,
    tipo_mime: str,
    *,
    is_background: bool = False,
) -> tuple[Anexo, bool]:
    """
    Faz upload e registra um anexo em uma pane.

    Algoritmo (SPECS §6 – Upload):
        1. Validar tipo (jpg, png, pdf)
        2. Validar tamanho (< MAX_UPLOAD_SIZE_MB)
        3. Gerar nome único (UUID + extensão)
        4. Armazenar no diretório de uploads
        5. Criar registro em anexos

    Se is_background=True e for uma imagem, registra "processando" e retorna
    (anexo, True) para que o chamador execute a otimização em background.

    Raises:
        ValueError: se tipo ou tamanho inválidos.
    """
    settings = get_settings()
    if not await _buscar_pane_por_id(db, pane_id):
        raise ValueError("Pane não encontrada.")

    # Validar extensão
    nome_original = nome_original or "arquivo"
    extensao = os.path.splitext(nome_original)[1].lower()
    if extensao not in _EXTENSOES_PERMITIDAS:
        raise ValueError(
            f"Tipo de arquivo não permitido: '{extensao}'. "
            f"Permitidos: {_EXTENSOES_PERMITIDAS}"
        )

    # SEC-05: Validar MIME type real do conteúdo (não confiar na extensão) (AUD-09)
    if _MAGIC_AVAILABLE:
        try:
            mime_real = magic.from_buffer(arquivo_bytes[:2048], mime=True)
        except Exception as e:
            from app.shared.core.file_validators import _detect_mime_type_fallback
            mime_real = _detect_mime_type_fallback(arquivo_bytes[:2048])
    else:
        from app.shared.core.file_validators import _detect_mime_type_fallback
        mime_real = _detect_mime_type_fallback(arquivo_bytes[:2048])

    if not mime_real:
        raise ValueError("Não foi possível identificar o tipo de arquivo de forma segura por sua assinatura.")

    if mime_real not in _MIMES_PERMITIDOS:
        raise ValueError(
            f"Conteúdo real do arquivo ({mime_real}) não é um tipo permitido. "
            f"Permitidos: {_MIMES_PERMITIDOS}"
        )

    # Item #31: extensão declarada e conteúdo real precisam ser coerentes
    if mime_real not in _EXTENSAO_MIME_MAP.get(extensao, set()):
        raise ValueError(
            f"A extensão '{extensao}' não corresponde ao conteúdo real do arquivo ({mime_real})."
        )

    # Validar tamanho
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(arquivo_bytes) > max_bytes:
        raise ValueError(
            f"Arquivo excede o tamanho máximo de {settings.max_upload_size_mb} MB."
        )

    from app.shared.core.enums import TipoAnexo
    is_image = extensao in {".jpg", ".jpeg", ".png", ".heic", ".heif"} or mime_real in {"image/jpeg", "image/png", "image/heic", "image/heif"}

    if is_image and is_background:        # Retorna placeholder para processamento em background (Etapa 5)
        anexo = Anexo(
            pane_id=pane_id,
            caminho_arquivo="processando",
            tipo=TipoAnexo.IMAGEM.value,
        )
        db.add(anexo)
        await db.flush()
        return anexo, True

    # Determinar tipo do anexo para arquivos normais / processamento síncrono
    tipo_anexo = TipoAnexo.IMAGEM if is_image else TipoAnexo.DOCUMENTO

    # Gerar nome único e salvar arquivo através do StorageService
    storage_svc = get_storage_service()
    caminho_salvo = await storage_svc.upload(arquivo_bytes, nome_original, mime_real)

    # Criar registro no banco
    anexo = Anexo(
        pane_id=pane_id,
        caminho_arquivo=caminho_salvo,
        tipo=tipo_anexo.value,
    )
    try:
        # Item #4 (relatorio_panes_service.md): se o registro não puder ser
        # persistido após o upload ter sucesso, o arquivo ficaria órfão no
        # storage sem nenhum registro apontando para ele — compensar.
        db.add(anexo)
        await db.flush()
    except Exception:
        await storage_svc.delete(caminho_salvo)
        raise
    return anexo, False


async def _atualizar_caminho_anexo_se_pendente(
    anexo_id: uuid.UUID,
    caminho_novo: str,
    *,
    arquivo_para_limpar: str | None = None,
) -> bool:
    """Atualiza o caminho do anexo somente se ele ainda estiver 'processando'.

    Item #34 (relatorio_panes_service.md): sem esta checagem, um anexo
    excluído (ou já atualizado por outra execução) enquanto o background task
    rodava seria "ressuscitado" com o caminho novo. Quando o anexo não está
    mais pendente e `arquivo_para_limpar` foi informado, o arquivo recém
    enviado é removido do storage para não ficar órfão.

    Returns:
        True se o anexo foi atualizado; False se a atualização foi descartada.
    """
    from app.bootstrap.database import get_session_factory

    SessionMaker = get_session_factory()
    async with SessionMaker() as session:
        result = await session.execute(select(Anexo).where(Anexo.id == anexo_id))
        anexo = result.scalar_one_or_none()
        if anexo and anexo.caminho_arquivo == "processando":
            anexo.caminho_arquivo = caminho_novo
            await session.commit()
            return True

    if arquivo_para_limpar:
        storage_svc = get_storage_service()
        await storage_svc.delete(arquivo_para_limpar)
    return False


async def processar_imagem_background(
    anexo_id: uuid.UUID,
    arquivo_bytes: bytes,
    nome_original: str,
    mime_real: str,
) -> None:
    """
    Tarefa em background para otimização de imagem via imgdiet. (IMGDIET - Etapa 4 e 5)
    Processa e salva o arquivo otimizado no Storage, atualizando o Anexo.
    """
    import asyncio
    from app.shared.services.image.pipeline import process_image

    try:
        # 1. Processar a imagem (CPU intensive, rodar em threadpool)
        # Item #21: asyncio.to_thread() no lugar de loop.run_in_executor(None, lambda: ...)
        webp_bytes = await asyncio.to_thread(process_image, arquivo_bytes, filename_hint=nome_original)

        # 2. Upload para Storage do arquivo otimizado
        storage_svc = get_storage_service()
        novo_nome = os.path.splitext(nome_original)[0] + ".webp"
        caminho_salvo = await storage_svc.upload(webp_bytes, novo_nome, "image/webp")

        # 3. Atualizar caminho no banco de dados (só se o anexo ainda existir e estiver pendente)
        await _atualizar_caminho_anexo_se_pendente(
            anexo_id, caminho_salvo, arquivo_para_limpar=caminho_salvo
        )
    except Exception as exc:
        logger.error("Falha ao processar imagem %s em background: %s", nome_original, exc)
        # Lógica de Fallback (Etapa 4): salva a original em caso de erro
        try:
            storage_svc = get_storage_service()
            caminho_salvo = await storage_svc.upload(arquivo_bytes, nome_original, mime_real)
            await _atualizar_caminho_anexo_se_pendente(
                anexo_id, caminho_salvo, arquivo_para_limpar=caminho_salvo
            )
        except Exception as fallback_exc:
            logger.error("Falha no fallback de upload da imagem %s: %s", nome_original, fallback_exc)
            # Etapa 6: Se tudo falhar, marcar como ERRO para não travar a UI em "processando"
            try:
                await _atualizar_caminho_anexo_se_pendente(anexo_id, "ERRO")
            except Exception as final_exc:
                logger.error("Erro crítico: não foi possível nem marcar o anexo %s como ERRO: %s", anexo_id, final_exc)


async def limpar_anexos_processando_antigos(db: AsyncSession, minutos_limite: int = 30) -> int:
    """Marca como 'ERRO' anexos presos em 'processando' além do limite de tempo.

    Item #5 (relatorio_panes_service.md): `BackgroundTasks` do FastAPI não é
    durável — se o processo reiniciar entre o registro do placeholder
    "processando" e a execução da task, os bytes originais se perdem e o
    anexo fica eternamente pendente. Esta é a mitigação mínima recomendada
    pelo relatório (job de limpeza); a solução definitiva exigiria persistir
    o arquivo original antes de otimizar, ou uma fila durável (Celery/ARQ/RQ).

    Chamada periodicamente por `app.bootstrap.tasks.anexos_travados_cleanup_task`.

    Args:
        minutos_limite: idade mínima (em minutos) para considerar um anexo
            "processando" como travado.

    Returns:
        Quantidade de anexos marcados como ERRO.
    """
    from datetime import timedelta

    limite = datetime.now(timezone.utc) - timedelta(minutes=minutos_limite)
    result = await db.execute(
        select(Anexo).where(
            Anexo.caminho_arquivo == "processando",
            Anexo.created_at < limite,
        )
    )
    travados = list(result.scalars().all())
    for anexo in travados:
        anexo.caminho_arquivo = "ERRO"

    if travados:
        await db.flush()
    return len(travados)


async def listar_anexos(db: AsyncSession, pane_id: uuid.UUID) -> list[Anexo]:
    """Lista todos os anexos de uma pane."""
    result = await db.execute(
        select(Anexo).where(Anexo.pane_id == pane_id).order_by(Anexo.created_at)
    )
    return list(result.scalars().all())


async def buscar_anexo(
    db: AsyncSession,
    pane_id: uuid.UUID,
    anexo_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> Anexo | None:
    """Busca um anexo de uma pane, opcionalmente incluindo panes inativas."""
    query = (
        select(Anexo)
        .join(Pane, Pane.id == Anexo.pane_id)
        .where(
            Anexo.id == anexo_id,
            Anexo.pane_id == pane_id,
        )
    )
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)  # noqa: E712

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def excluir_anexo(
    db: AsyncSession,
    pane_id: uuid.UUID,
    anexo_id: uuid.UUID,
) -> bool:
    """
    Remove um anexo do banco e deleta o arquivo físico.

    Item #4 (relatorio_panes_service.md): o banco é a fonte de verdade — o
    registro é removido primeiro. Se a exclusão física falhar depois, ela é
    apenas logada (não interrompe a operação): um arquivo órfão no storage é
    preferível a um registro no banco apontando para um arquivo que o usuário
    já não pode ver nem re-tentar excluir pela UI.
    """
    anexo = await buscar_anexo(db, pane_id, anexo_id)
    if not anexo:
        raise ValueError("Anexo não encontrado.")

    caminho_arquivo = anexo.caminho_arquivo

    await db.delete(anexo)
    await db.flush()

    if caminho_arquivo and caminho_arquivo not in ["processando", "ERRO"]:
        storage_svc = get_storage_service()
        try:
            sucesso = await storage_svc.delete(caminho_arquivo)
            if not sucesso:
                logger.warning(
                    "Falha ao excluir arquivo físico do anexo %s (caminho=%s): storage retornou False.",
                    anexo_id, caminho_arquivo,
                )
        except Exception as exc:
            logger.warning(
                "Falha ao excluir arquivo físico do anexo %s (caminho=%s): %s",
                anexo_id, caminho_arquivo, exc,
            )

    return True


async def obter_url_anexo(caminho_relativo: str) -> str:
    """
    Retorna a URL assinada (R2) ou caminho relativo (Local) para o anexo.
    """
    storage_svc = get_storage_service()
    return await storage_svc.get_url(caminho_relativo)


async def _ja_e_responsavel(db: AsyncSession, pane_id: uuid.UUID, usuario_id: uuid.UUID) -> bool:
    """Verifica se o usuário já consta como responsável pela pane."""
    result = await db.execute(
        select(PaneResponsavel).where(
            PaneResponsavel.pane_id == pane_id,
            PaneResponsavel.usuario_id == usuario_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def adicionar_responsavel(
    db: AsyncSession,
    pane_id: uuid.UUID,
    dados: AdicionarResponsavel,
) -> PaneResponsavel:
    """
    Vincula um responsável a uma pane com papel definido.

    Raises:
        ValueError: se a pane/usuário não existir, ou se o usuário já for
            responsável por esta pane (verificação prévia ou, em caso de
            requisições concorrentes, violação da constraint UNIQUE).
    """
    if not await _buscar_pane_por_id(db, pane_id):
        raise ValueError("Pane não encontrada.")

    # Verificar duplicidade (mensagem amigável no caso comum; a constraint
    # UNIQUE(pane_id, usuario_id) é a rede de segurança para o caso concorrente)
    if await _ja_e_responsavel(db, pane_id, dados.usuario_id):
        raise ValueError("Usuário já é responsável por esta pane.")

    from app.modules.auth.service import buscar_por_id
    usuario = await buscar_por_id(db, dados.usuario_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")

    responsavel = PaneResponsavel(
        pane_id=pane_id,
        usuario_id=dados.usuario_id,
        papel=usuario.funcao,
    )
    try:
        # Item #2 (relatorio_panes_service.md): SAVEPOINT + IntegrityError cobre
        # a janela de corrida entre a checagem acima e este insert (TOCTOU).
        async with db.begin_nested():
            db.add(responsavel)
            await db.flush()
    except IntegrityError as exc:
        raise ValueError("Usuário já é responsável por esta pane.") from exc

    # Refresh 'usuario' para garantir que o trigrama esteja carregado para o schema Pydantic
    await db.refresh(responsavel, ["usuario"])

    return responsavel


async def listar_sistemas_ata(db: AsyncSession) -> list[SistemaAta]:
    """Lista todos os Sistemas ATA ativos."""
    result = await db.execute(
        select(SistemaAta).where(SistemaAta.ativo == True).order_by(SistemaAta.codigo)
    )
    return list(result.scalars().all())

