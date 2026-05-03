"""
scripts/seed/seed_inspecoes.py

Define os tipos de inspeção e abre instâncias de inspeção na frota.

Regras do modelo:
- Y é calendarizada.
- A e C são controladas por horas de voo.
- Os sufixos numéricos representam ciclos acumulados:
  Y, 2Y, 3Y...
  A, 2A, 3A...
  C, 2C, 3C...

Este seed usa variáveis de ambiente para simular o estado da aeronave:
- INSPECAO_HORAS_VOO_ATUAL: horas de voo atuais para cálculo das fases A/C.
- INSPECAO_DATA_INICIO_OPERACAO: data de início da operação para cálculo das fases Y.
- INSPECAO_DATA_REFERENCIA (opcional): data usada como "hoje" na simulação.
"""
from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes.models import TipoInspecao
from app.modules.inspecoes.schemas import InspecaoCreate
from app.modules.inspecoes.service import abrir_inspecao
from scripts.seed import seed_tarefas

# ----------------------------------------------------------------------
# Configuração da simulação
# ----------------------------------------------------------------------
FH_BASE_A = 700
FH_BASE_C = 3000
DIAS_BASE_A = 5
DIAS_BASE_C = 10
DIAS_BASE_Y = 7

HORAS_VOO_ATUAL = float(os.getenv("INSPECAO_HORAS_VOO_ATUAL", "3500"))
DATA_INICIO_OPERACAO = os.getenv("INSPECAO_DATA_INICIO_OPERACAO", "2020-01-01")
DATA_REFERENCIA = os.getenv("INSPECAO_DATA_REFERENCIA")  # opcional

FROTA_ALVO = ["5902", "5905", "5906", "5912", "5914", "5915", "5916", "5919"]

# ----------------------------------------------------------------------
# Tipos de Inspeção
# ----------------------------------------------------------------------
# Observação:
# - duracao_dias = 0 nas inspeções controladas por horas de voo.
# - O campo permanece apenas para compatibilidade com o modelo atual.
TIPOS_DATA = [
    # Calendárias
    {"codigo": "Y",     "nome": "Inspeção Y",     "descricao": "Inspeção calendarizada base do ciclo Y",           "duracao_dias": DIAS_BASE_Y},
    {"codigo": "2Y",    "nome": "Inspeção 2Y",    "descricao": "Inspeção calendarizada de 2 ciclos Y",             "duracao_dias": DIAS_BASE_Y * 2},
    {"codigo": "3Y",    "nome": "Inspeção 3Y",    "descricao": "Inspeção calendarizada de 3 ciclos Y",             "duracao_dias": DIAS_BASE_Y * 3},
    {"codigo": "4Y",    "nome": "Inspeção 4Y",    "descricao": "Inspeção calendarizada de 4 ciclos Y",             "duracao_dias": DIAS_BASE_Y * 4},

    # Por horas de voo - fase A
    {"codigo": "A",     "nome": "Inspeção A",     "descricao": "Inspeção por horas de voo do ciclo A",             "duracao_dias": DIAS_BASE_A},
    {"codigo": "2A",    "nome": "Inspeção 2A",    "descricao": "Inspeção por horas de voo de 2 ciclos A",          "duracao_dias": DIAS_BASE_A * 2},
    {"codigo": "3A",    "nome": "Inspeção 3A",    "descricao": "Inspeção por horas de voo de 3 ciclos A",          "duracao_dias": DIAS_BASE_A * 3},
    {"codigo": "4A",    "nome": "Inspeção 4A",    "descricao": "Inspeção por horas de voo de 4 ciclos A",          "duracao_dias": DIAS_BASE_A * 4},
    {"codigo": "5A",    "nome": "Inspeção 5A",    "descricao": "Inspeção por horas de voo de 5 ciclos A",          "duracao_dias": DIAS_BASE_A * 5},

    # Por horas de voo - fase C
    {"codigo": "C",     "nome": "Inspeção C",     "descricao": "Inspeção pesada por horas de voo do ciclo C",      "duracao_dias": DIAS_BASE_C},
    {"codigo": "2C",    "nome": "Inspeção 2C",    "descricao": "Inspeção pesada por horas de voo de 2 ciclos C",   "duracao_dias": DIAS_BASE_C * 2},
    {"codigo": "3C",    "nome": "Inspeção 3C",    "descricao": "Inspeção pesada por horas de voo de 3 ciclos C",   "duracao_dias": DIAS_BASE_C * 3},

    # Não programadas
    {"codigo": "ESP",   "nome": "Inspeção Especial",   "descricao": "Inspeção não programada ou sob demanda",                 "duracao_dias": 2},
    {"codigo": "PMAINT","nome": "Pós-Manutenção",      "descricao": "Inspeção executada após manutenção relevante",           "duracao_dias": 2},
    {"codigo": "PPANE", "nome": "Pós-Pane",            "descricao": "Inspeção executada após pane ou ocorrência técnica",     "duracao_dias": 1},
    {"codigo": "ARMAZ", "nome": "Pós-Armazenamento",   "descricao": "Inspeção executada após armazenamento prolongado",       "duracao_dias": 5},
]

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _add_years(base: date, years: int) -> date:
    try:
        return base.replace(year=base.year + years)
    except ValueError:
        # 29/02 -> 28/02 em anos não bissextos
        return base.replace(month=2, day=28, year=base.year + years)


def _normalize_codes(codes: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered


def _calcular_tipos_aplicaveis(
    horas_voo: float,
    data_inicio_operacao: date,
    data_referencia: date,
) -> list[str]:
    codigos: list[str] = []

    # Y = calendarizada
    for ciclo in range(1, 5):
        if data_referencia >= _add_years(data_inicio_operacao, ciclo):
            codigos.append("Y" if ciclo == 1 else f"{ciclo}Y")

    # A = 700 FH por ciclo
    for ciclo in range(1, 6):
        if horas_voo >= FH_BASE_A * ciclo:
            codigos.append("A" if ciclo == 1 else f"{ciclo}A")

    # C = 3000 FH por ciclo
    for ciclo in range(1, 4):
        if horas_voo >= FH_BASE_C * ciclo:
            codigos.append("C" if ciclo == 1 else f"{ciclo}C")

    return _normalize_codes(codigos)


async def run(session: AsyncSession):
    print("🚀 [Inspeções] Iniciando carga de tipos e instâncias...")

    data_inicio_operacao = _parse_date(DATA_INICIO_OPERACAO)
    data_referencia = _parse_date(DATA_REFERENCIA) if DATA_REFERENCIA else datetime.now(timezone.utc).date()

    print(
        f"   > Simulação: horas_voo={HORAS_VOO_ATUAL}, "
        f"início_operação={data_inicio_operacao.isoformat()}, "
        f"referência={data_referencia.isoformat()}"
    )

    # 1. Obter usuário admin
    res_user = await session.execute(select(Usuario).limit(1))
    admin_user = res_user.scalars().first()
    if not admin_user:
        print("   ! Admin não encontrado. Pulando.")
        return

    # 2. Popular/Atualizar Tipos de Inspeção
    tipos_dict: dict[str, TipoInspecao] = {}
    for tdata in TIPOS_DATA:
        res = await session.execute(select(TipoInspecao).where(TipoInspecao.codigo == tdata["codigo"]))
        tipo = res.scalar_one_or_none()
        if not tipo:
            tipo = TipoInspecao(**tdata)
            session.add(tipo)
        else:
            tipo.nome = tdata["nome"]
            tipo.descricao = tdata["descricao"]
            tipo.duracao_dias = tdata["duracao_dias"]
        await session.flush()
        tipos_dict[tdata["codigo"]] = tipo

    # 3. Processar Templates de Tarefas (delegado ao seed_tarefas)
    await seed_tarefas.run(session)
    print("   + Tipos e Templates (via seed_tarefas) configurados.")

    # 4. Determinar tipos aplicáveis pela simulação
    tipos_aplicaveis = _calcular_tipos_aplicaveis(
        horas_voo=HORAS_VOO_ATUAL,
        data_inicio_operacao=data_inicio_operacao,
        data_referencia=data_referencia,
    )

    print(f"   > Tipos aplicáveis calculados: {', '.join(tipos_aplicaveis) if tipos_aplicaveis else 'nenhum'}")

    # 5. Abrir Inspeções para aeronaves alvo
    res_acft = await session.execute(
        select(Aeronave).where(Aeronave.matricula.in_(FROTA_ALVO))
    )
    aeronaves_alvo = res_acft.scalars().all()

    inspecoes_criadas = 0
    for acft in aeronaves_alvo:
        if acft.status != "DISPONIVEL":
            continue

        # Selecionar aleatoriamente entre 2 e 4 tipos dos aplicáveis para diversificar o seed
        n_sortear = min(len(tipos_aplicaveis), random.randint(2, 4))
        tipos_sorteados = random.sample(tipos_aplicaveis, k=n_sortear)

        tipos_ids = [
            tipos_dict[codigo].id
            for codigo in tipos_sorteados
            if codigo in tipos_dict
        ]

        if not tipos_ids:
            print(f"   - {acft.matricula}: nenhum tipo aplicável sorteado.")
            continue

        dados = InspecaoCreate(
            aeronave_id=acft.id,
            tipos_inspecao_ids=tipos_ids,
            data_inicio=datetime.now(timezone.utc) - timedelta(days=1),
            observacoes="Inspeção automática de seed baseada em horas de voo e data de início de operação.",
        )
        try:
            await abrir_inspecao(session, dados, admin_user.id)
            inspecoes_criadas += 1
            print(f"   + {acft.matricula}: inspeção aberta com {len(tipos_ids)} tipo(s).")
        except Exception as e:
            print(f"   ! Falha ao abrir inspeção para {acft.matricula}: {e}")

    await session.flush()
    if inspecoes_criadas > 0:
        print(f"   + {inspecoes_criadas} inspeções ativas abertas.")
    else:
        print("   ! Nenhuma inspeção foi aberta.")
