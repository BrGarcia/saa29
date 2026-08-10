"""
scripts/seed/seed_pedidos.py
Gera pedidos de exemplo (NORMAL/EMERGENCIA, em cada status do ciclo de vida)
para popular a Central de Pedidos em ambiente de desenvolvimento.

Dados de teste — bloqueado em produção (mesma trava usada por seed_panes.py e
seed_vencimentos.py: `APP_ENV=production` interrompe o seed antes de inserir).
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.pedidos.models import Pedido
from app.shared.core.enums import StatusPedido, TipoPedido

# Cenários fictícios cobrindo os dois tipos e os três status finais — mesmos
# P/Ns de exemplo usados no mockup aprovado (docs/backlog/modulo_pedidos/mockup_pedidos.html).
PEDIDOS_EXEMPLO = [
    {
        "part_number": "622-4795-001",
        "nomenclatura": "MDP1 - Módulo de Processamento de Dados",
        "tipo_pedido": TipoPedido.EMERGENCIA.value,
        "status": StatusPedido.PENDENTE.value,
        "quantidade": 2,
        "dias_atras": 2,
        "observacao": "MDP1 danificado durante voo operacional. Substituição urgente para manter aeronave DISPONÍVEL.",
    },
    {
        "part_number": "CMFD2-STD",
        "nomenclatura": "CMFD2 - Display Multifunção",
        "tipo_pedido": TipoPedido.NORMAL.value,
        "status": StatusPedido.PENDENTE.value,
        "quantidade": 1,
        "dias_atras": 5,
        "observacao": "Slot vazio identificado no inventário. Aguardando recebimento do COMLOG.",
    },
    {
        "part_number": "AN/ARC-210",
        "nomenclatura": "VUHF1 - Rádio VHF/UHF",
        "tipo_pedido": TipoPedido.NORMAL.value,
        "status": StatusPedido.PENDENTE.value,
        "quantidade": 1,
        "dias_atras": 8,
        "observacao": "TBV vencido. Equipamento necessita calibração — pedido de substituição.",
    },
    {
        "part_number": "GPA-2024-1188",
        "nomenclatura": "GPS1 - Sistema de Posicionamento",
        "tipo_pedido": TipoPedido.NORMAL.value,
        "status": StatusPedido.ATENDIDO.value,
        "quantidade": 1,
        "dias_atras": 15,
        "observacao": "GPS1 recebido e instalado com sucesso. S/N: GPA-2024-1188.",
    },
    {
        "part_number": "174521-10-01",
        "nomenclatura": "VADR - Válvula de Descarga Rápida",
        "tipo_pedido": TipoPedido.EMERGENCIA.value,
        "status": StatusPedido.CANCELADO.value,
        "quantidade": 1,
        "dias_atras": 20,
        "observacao": "Pane inicial motivou a abertura do pedido de emergência.",
        "motivo_cancelamento": "Pane solucionada sem necessidade de substituição de equipamento.",
    },
    {
        "part_number": "453-5000-710",
        "nomenclatura": "ELT - Transmissor de Localização",
        "tipo_pedido": TipoPedido.EMERGENCIA.value,
        "status": StatusPedido.ATENDIDO.value,
        "quantidade": 3,
        "dias_atras": 25,
        "observacao": "Emergência atendida. Unidades recebidas e instaladas para exercício operacional.",
    },
]


async def _proximo_numero_pedido(session: AsyncSession, ano: int) -> str:
    """Mesma lógica de app/modules/pedidos/service.py:_gerar_numero_pedido —
    baseada no maior numero_pedido já emitido no ano, não em COUNT(*)."""
    prefixo = f"P-{ano}-"
    resultado = await session.execute(
        select(Pedido.numero_pedido)
        .where(Pedido.numero_pedido.like(f"{prefixo}%", escape="\\"))
        .order_by(Pedido.numero_pedido.desc())
        .limit(1)
    )
    ultimo = resultado.scalar_one_or_none()
    proxima_seq = int(ultimo[len(prefixo):]) + 1 if ultimo else 1
    return f"{prefixo}{proxima_seq:04d}"


async def run(session: AsyncSession):
    if os.getenv("APP_ENV", "development").lower() == "production":
        print("🛡️ [Pedidos] Modo Produção: dados de teste da Central de Pedidos não são carregados.")
        return

    print("🚀 [Pedidos] Gerando pedidos de exemplo (NORMAL/EMERGENCIA, PENDENTE/ATENDIDO/CANCELADO)...")

    res_acfts = await session.execute(select(Aeronave))
    aeronaves = list(res_acfts.scalars().all())

    res_users = await session.execute(select(Usuario))
    usuarios = list(res_users.scalars().all())

    if not aeronaves or not usuarios:
        print("   ! Aeronaves ou usuários não encontrados. Pulando pedidos.")
        return

    admin = usuarios[0]

    # Idempotência: reexecuções de `python scripts/seed/seed.py` não devem
    # duplicar este lote a cada chamada — âncora no P/N do primeiro item.
    primeiro_pn = PEDIDOS_EXEMPLO[0]["part_number"]
    ja_existe = await session.execute(
        select(Pedido.id).where(Pedido.part_number == primeiro_pn).limit(1)
    )
    if ja_existe.scalar_one_or_none() is not None:
        print("   ↺ Pedidos de exemplo já existentes. Pulando (idempotente).")
        return

    ano_atual = datetime.now(timezone.utc).year
    criados = 0

    for i, dados in enumerate(PEDIDOS_EXEMPLO):
        aeronave = aeronaves[i % len(aeronaves)]
        solicitante = usuarios[i % len(usuarios)]
        data_pedido = date.today() - timedelta(days=dados["dias_atras"])

        pedido = Pedido(
            id=uuid.uuid4(),
            numero_pedido=await _proximo_numero_pedido(session, ano_atual),
            aeronave_id=aeronave.id,
            part_number=dados["part_number"],
            nomenclatura=dados["nomenclatura"],
            tipo_pedido=dados["tipo_pedido"],
            numero_emergencia=f"EMG-{1000 + i:04d}" if dados["tipo_pedido"] == TipoPedido.EMERGENCIA.value else None,
            quantidade=dados["quantidade"],
            status=dados["status"],
            observacao=dados["observacao"],
            data_pedido=data_pedido,
            solicitante_id=solicitante.id,
            ativo=True,
        )

        if dados["status"] == StatusPedido.ATENDIDO.value:
            pedido.data_atendimento = datetime.now(timezone.utc) - timedelta(days=max(dados["dias_atras"] - 1, 0))
            pedido.atendido_por_id = admin.id
        elif dados["status"] == StatusPedido.CANCELADO.value:
            pedido.data_cancelamento = datetime.now(timezone.utc) - timedelta(days=max(dados["dias_atras"] - 1, 0))
            pedido.cancelado_por_id = admin.id
            pedido.motivo_cancelamento = dados.get("motivo_cancelamento", "Cancelado durante seed de teste.")

        session.add(pedido)
        # Flush por item: garante que o próximo `_proximo_numero_pedido` desta
        # mesma execução veja o numero_pedido recém-inserido (a query é
        # baseada no maior valor já persistido, não num contador em memória).
        await session.flush()
        criados += 1

    print(f"   ✅ Total: {criados} pedidos de exemplo criados.")
