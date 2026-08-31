"""
app/modules/equipamentos/auditoria_service.py
Trilha append-only de escritas em dados mestres do inventário
(ModeloEquipamento, SlotInventario, ItemEquipamento).

Nenhuma função aqui faz UPDATE ou DELETE sobre AuditoriaDadosMestres — mesmo
padrão já usado para ExecucaoVencimentoHistorico no módulo de vencimentos.

Regra que não pode ser relaxada (RN-05): `usuario_id` vem SEMPRE da sessão
autenticada, nunca de payload do cliente. Aceitar o autor por payload foi o
BUG-01 já corrigido em `ajustar_inventario_item` — "a trilha de auditoria do
inventário era forjável".
"""

import uuid
from datetime import date, datetime

from sqlalchemy import desc, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipamentos.models import AuditoriaDadosMestres
from app.shared.core.enums import AcaoAuditoria, EntidadeAuditada

# Campos sem valor informativo num diff de auditoria: `id` não muda e os
# timestamps mudam em toda escrita, poluindo o registro.
CAMPOS_IGNORADOS = {"created_at", "updated_at", "id"}

# Teto de itens por página na consulta da trilha.
LIMITE_MAXIMO_AUDITORIA = 200


def _serializavel(valor):
    """Converte um valor de coluna em algo que `json.dumps` aceite.

    Sem isto, gravar um snapshot vindo de `obj.__table__.columns` estoura
    `TypeError: Object of type UUID is not JSON serializable` na coluna JSON —
    `modelo_id` é uuid.UUID e `created_at` é datetime.
    """
    if isinstance(valor, (uuid.UUID, datetime, date)):
        return str(valor)
    return valor


def snapshot(obj, campos: list[str] | None = None) -> dict:
    """Retrato serializável de uma instância ORM.

    Usar sempre isto em vez de montar o dict à mão: garante que todo valor
    passe por `_serializavel` antes de chegar à coluna JSON.

    Lê apenas atributos já carregados. Depois de um `flush()`, colunas com
    `onupdate` (como `updated_at`) ficam expiradas, e um `getattr` nelas
    dispararia um SELECT de refresh — em contexto async isso levanta
    `MissingGreenlet`, não um simples N+1. Os campos assim omitidos são os
    mesmos que `CAMPOS_IGNORADOS` já descarta do diff, então nada de útil
    se perde.
    """
    nomes = campos or [c.name for c in obj.__table__.columns]
    nao_carregados = inspect(obj).unloaded
    return {
        nome: _serializavel(getattr(obj, nome))
        for nome in nomes
        if nome not in nao_carregados
    }


def diff_campos(antes: dict | None, depois: dict | None) -> tuple[dict, dict]:
    """Retorna (anteriores, novos) contendo apenas os campos que mudaram.

    `antes=None` (CREATE) devolve `depois` inteiro em `novos`.
    `depois=None` (DELETE) devolve `antes` inteiro em `anteriores`.
    """
    antes = antes or {}
    depois = depois or {}
    chaves = (set(antes) | set(depois)) - CAMPOS_IGNORADOS

    anteriores: dict = {}
    novos: dict = {}
    for chave in chaves:
        valor_antes = antes.get(chave)
        valor_depois = depois.get(chave)
        if valor_antes != valor_depois:
            anteriores[chave] = valor_antes
            novos[chave] = valor_depois
    return anteriores, novos


async def registrar(
    db: AsyncSession,
    *,
    entidade: EntidadeAuditada,
    entidade_id: uuid.UUID,
    acao: AcaoAuditoria,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
    anteriores: dict | None = None,
    novos: dict | None = None,
    justificativa: str | None = None,
) -> None:
    """Grava um registro na trilha.

    `usuario_id` deve vir da sessão autenticada (RN-05) — o router é quem o
    obtém de `current_user.id`; nenhum schema de entrada expõe esse campo.
    """
    db.add(
        AuditoriaDadosMestres(
            id=uuid.uuid4(),
            entidade=entidade.value,
            entidade_id=entidade_id,
            acao=acao.value,
            # Rede de segurança: mesmo que um chamador esqueça de usar
            # snapshot(), nada não-serializável chega à coluna JSON.
            valores_anteriores={k: _serializavel(v) for k, v in (anteriores or {}).items()} or None,
            valores_novos={k: _serializavel(v) for k, v in (novos or {}).items()} or None,
            justificativa=justificativa,
            usuario_id=usuario_id,
            ip_origem=ip_origem,
        )
    )
    await db.flush()


async def listar(
    db: AsyncSession,
    entidade: EntidadeAuditada | None = None,
    entidade_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditoriaDadosMestres]:
    """Consulta a trilha, da escrita mais recente para a mais antiga."""
    stmt = select(AuditoriaDadosMestres).order_by(desc(AuditoriaDadosMestres.criado_em))
    if entidade:
        stmt = stmt.where(AuditoriaDadosMestres.entidade == entidade.value)
    if entidade_id:
        stmt = stmt.where(AuditoriaDadosMestres.entidade_id == entidade_id)
    stmt = stmt.limit(min(limit, LIMITE_MAXIMO_AUDITORIA)).offset(offset)
    resultado = await db.execute(stmt)
    return list(resultado.scalars().all())
