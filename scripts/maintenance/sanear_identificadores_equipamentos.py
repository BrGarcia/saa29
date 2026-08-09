"""
scripts/maintenance/sanear_identificadores_equipamentos.py
Saneia PNs e S/Ns gravados fora da forma canônica (sem espaços, maiúsculas).

Contexto (relatorio_equipamentos_services.md, item #14): a normalização passou a
ser feita nos schemas Pydantic, mas registros antigos podem ter sido gravados sem
`.strip().upper()`. Isso cria duplicatas lógicas ("abc123" vs "ABC123").

Uso:
    python scripts/maintenance/sanear_identificadores_equipamentos.py           # diagnóstico
    python scripts/maintenance/sanear_identificadores_equipamentos.py --apply   # grava

O modo diagnóstico é o padrão e NÃO altera o banco. Colisões (dois registros que
virariam o mesmo identificador) são apenas reportadas — precisam de decisão
humana, pois a correção exige mesclar histórico de instalações/vencimentos.
"""
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

# Ajustar PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bootstrap.database import get_session_factory

# Todos os models precisam estar registrados para o SQLAlchemy resolver
# os relacionamentos declarados por nome (mesma lista de migrations/env.py).
import app.modules.auth.models         # noqa: F401
import app.modules.efetivo.models      # noqa: F401
import app.modules.aeronaves.models    # noqa: F401
import app.modules.equipamentos.models # noqa: F401
import app.modules.vencimentos.models  # noqa: F401
import app.modules.panes.models        # noqa: F401
import app.modules.inspecoes.models    # noqa: F401
import app.modules.calendario.models   # noqa: F401

from app.modules.equipamentos.models import ItemEquipamento, ModeloEquipamento


def _canonico(valor: str) -> str:
    """Mesma regra do schema Pydantic (`_normalizar_identificador`)."""
    return valor.strip().upper()


async def sanear(aplicar: bool) -> int:
    """Executa o diagnóstico/saneamento. Retorna a quantidade de colisões."""
    AsyncSessionLocal = get_session_factory()

    async with AsyncSessionLocal() as session:
        # ---------- Part Numbers ----------
        modelos = list((await session.execute(select(ModeloEquipamento))).scalars().all())
        pn_por_canonico: dict[str, list[ModeloEquipamento]] = defaultdict(list)
        for modelo in modelos:
            pn_por_canonico[_canonico(modelo.part_number)].append(modelo)

        pn_fora_do_padrao = [m for m in modelos if m.part_number != _canonico(m.part_number)]
        pn_colisoes = {pn: ms for pn, ms in pn_por_canonico.items() if len(ms) > 1}

        # ---------- Serial Numbers (unicidade é por modelo_id + numero_serie) ----------
        itens = list((await session.execute(select(ItemEquipamento))).scalars().all())
        sn_por_chave: dict[tuple, list[ItemEquipamento]] = defaultdict(list)
        for item in itens:
            sn_por_chave[(item.modelo_id, _canonico(item.numero_serie))].append(item)

        sn_fora_do_padrao = [i for i in itens if i.numero_serie != _canonico(i.numero_serie)]
        sn_colisoes = {k: v for k, v in sn_por_chave.items() if len(v) > 1}

        # ---------- Relatório ----------
        print("=" * 64)
        print(f"PNs analisados: {len(modelos)} | fora do padrão: {len(pn_fora_do_padrao)}")
        for m in pn_fora_do_padrao:
            print(f"  PN  {m.part_number!r} -> {_canonico(m.part_number)!r}")

        print(f"S/Ns analisados: {len(itens)} | fora do padrão: {len(sn_fora_do_padrao)}")
        for i in sn_fora_do_padrao:
            print(f"  S/N {i.numero_serie!r} -> {_canonico(i.numero_serie)!r} (PN id {i.modelo_id})")

        total_colisoes = len(pn_colisoes) + len(sn_colisoes)
        if total_colisoes:
            print("-" * 64)
            print(f"⚠️  {total_colisoes} colisão(ões) detectada(s) — exigem decisão manual:")
            for pn, ms in pn_colisoes.items():
                print(f"  PN {pn!r}: {[str(m.id) for m in ms]}")
            for (modelo_id, sn), lista in sn_colisoes.items():
                print(f"  S/N {sn!r} no PN {modelo_id}: {[str(i.id) for i in lista]}")
            print("  Mescle o histórico (instalações/controles) antes de normalizar.")

        # ---------- Aplicação ----------
        alteraveis_pn = [m for m in pn_fora_do_padrao if len(pn_por_canonico[_canonico(m.part_number)]) == 1]
        alteraveis_sn = [
            i for i in sn_fora_do_padrao
            if len(sn_por_chave[(i.modelo_id, _canonico(i.numero_serie))]) == 1
        ]

        if not aplicar:
            print("-" * 64)
            print(
                f"Modo diagnóstico. Rode com --apply para normalizar "
                f"{len(alteraveis_pn)} PN(s) e {len(alteraveis_sn)} S/N(s) sem colisão."
            )
            return total_colisoes

        for m in alteraveis_pn:
            m.part_number = _canonico(m.part_number)
        for i in alteraveis_sn:
            i.numero_serie = _canonico(i.numero_serie)

        await session.commit()
        print("-" * 64)
        print(f"✅ Normalizados {len(alteraveis_pn)} PN(s) e {len(alteraveis_sn)} S/N(s).")
        if total_colisoes:
            print("⚠️  Colisões acima permanecem inalteradas.")
        return total_colisoes


if __name__ == "__main__":
    aplicar = "--apply" in sys.argv
    colisoes = asyncio.run(sanear(aplicar))
    # Exit code != 0 sinaliza que há colisões pendentes de decisão humana.
    sys.exit(1 if colisoes else 0)
