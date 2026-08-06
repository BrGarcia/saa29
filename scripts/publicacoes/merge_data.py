"""
scripts/publicacoes/merge_data.py
Merge de uma remessa nova (mídia/DVD) no acervo existente — RN-08, M4 tarefa 3.

    python -m scripts.publicacoes.merge_data --origem var/publicacoes/acervo/Manuais --remessa /caminho/da/midia
    python -m scripts.publicacoes.merge_data --origem ... --remessa ... --executar

Regra (RN-08, `docs/backlog/manuais/Especificacao.MD` §5 — script da Fase 0
externa, aproveitado quase como está):

- Mesmo caminho relativo (`<manual>/<file_key>`) nos dois lados:
  - hash igual → é a mesma coisa, mantém a que já está no acervo, sem ação;
  - hash diferente → mantém a de **mtime mais recente**; a preterida vai para
    `_merge_conflicts/` (nunca é descartada silenciosamente) e o par entra no
    relatório para revisão humana;
- Caminho que só existe na remessa → é novo, copiado para o acervo;
- Caminho que só existe no acervo → não é tocado (a remessa é um incremento,
  não uma substituição completa).

`--dry-run` é o padrão: o script só relata o que faria. `--executar` aplica
de fato as cópias/movimentações. Essa inversão (seguro por padrão) é
deliberada — mexer no acervo de 1 GB por engano é caro de reverter.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logger = logging.getLogger("publicacoes.merge_data")

_NOME_PASTA_CONFLITOS = "_merge_conflicts"


def _hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _listar_pdfs(raiz: Path) -> dict[str, Path]:
    """{caminho_relativo_posix: caminho_absoluto} de todo `.pdf`/`.PDF` sob `raiz`."""
    return {
        p.relative_to(raiz).as_posix(): p
        for p in raiz.rglob("*")
        if p.is_file() and p.suffix.upper() == ".PDF"
    }


@dataclass
class ResultadoMerge:
    novos: list[str] = field(default_factory=list)
    identicos: list[str] = field(default_factory=list)
    conflitos: list[tuple[str, str, str]] = field(default_factory=list)
    """(caminho_relativo, motivo, arquivo_preterido) por conflito resolvido."""

    @property
    def total_alteracoes(self) -> int:
        return len(self.novos) + len(self.conflitos)


def planejar_merge(origem: Path, remessa: Path) -> ResultadoMerge:
    """
    Decide o que fazer para cada arquivo da remessa, sem tocar em disco —
    a mesma função alimenta tanto o `--dry-run` quanto a execução real, para
    que o relatório nunca diga uma coisa e o script faça outra.
    """
    existentes = _listar_pdfs(origem)
    novos_arquivos = _listar_pdfs(remessa)

    resultado = ResultadoMerge()
    for caminho_relativo, caminho_remessa in sorted(novos_arquivos.items()):
        caminho_origem = existentes.get(caminho_relativo)
        if caminho_origem is None:
            resultado.novos.append(caminho_relativo)
            continue

        hash_origem = _hash_arquivo(caminho_origem)
        hash_remessa = _hash_arquivo(caminho_remessa)
        if hash_origem == hash_remessa:
            resultado.identicos.append(caminho_relativo)
            continue

        mtime_origem = caminho_origem.stat().st_mtime
        mtime_remessa = caminho_remessa.stat().st_mtime
        if mtime_remessa >= mtime_origem:
            motivo = "remessa mais recente — substitui o acervo"
            preterido = "origem"
        else:
            motivo = "acervo mais recente — remessa descartada"
            preterido = "remessa"
        resultado.conflitos.append((caminho_relativo, motivo, preterido))

    return resultado


def aplicar_merge(origem: Path, remessa: Path, resultado: ResultadoMerge) -> None:
    """
    Executa de fato o que `planejar_merge` decidiu. Nunca apaga: o lado
    preterido de um conflito vai para `<origem>/_merge_conflicts/<caminho>`,
    com sufixo de timestamp se o destino já existir.
    """
    pasta_conflitos = origem / _NOME_PASTA_CONFLITOS

    for caminho_relativo in resultado.novos:
        destino = origem / caminho_relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(remessa / caminho_relativo, destino)

    for caminho_relativo, _motivo, preterido in resultado.conflitos:
        destino = origem / caminho_relativo
        origem_preterida = destino if preterido == "origem" else remessa / caminho_relativo
        vencedora = (remessa / caminho_relativo) if preterido == "origem" else destino

        alvo_conflito = pasta_conflitos / caminho_relativo
        alvo_conflito.parent.mkdir(parents=True, exist_ok=True)
        if alvo_conflito.exists():
            carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            alvo_conflito = alvo_conflito.with_name(f"{alvo_conflito.stem}.{carimbo}{alvo_conflito.suffix}")

        if preterido == "origem":
            # A origem perde: move o arquivo atual para _merge_conflicts/ e
            # só então copia o vencedor (remessa) no lugar dela.
            shutil.move(str(destino), str(alvo_conflito))
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vencedora, destino)
        else:
            # A remessa perde: registra a cópia preterida em _merge_conflicts/
            # e não toca no arquivo já presente no acervo.
            shutil.copy2(origem_preterida, alvo_conflito)


def gerar_relatorio(resultado: ResultadoMerge, *, origem: Path, remessa: Path) -> str:
    linhas = [
        "# Relatório de merge de remessa",
        "",
        f"Acervo: `{origem}`",
        f"Remessa: `{remessa}`",
        f"Gerado em: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Resumo",
        "",
        f"- Novos: {len(resultado.novos)}",
        f"- Idênticos (sem ação): {len(resultado.identicos)}",
        f"- Conflitos resolvidos: {len(resultado.conflitos)}",
        "",
    ]
    if resultado.novos:
        linhas.append("## Arquivos novos")
        linhas.append("")
        linhas += [f"- `{c}`" for c in resultado.novos]
        linhas.append("")
    if resultado.conflitos:
        linhas.append("## Conflitos — revisar `_merge_conflicts/`")
        linhas.append("")
        for caminho, motivo, preterido in resultado.conflitos:
            linhas.append(f"- `{caminho}` — {motivo} (preterido: {preterido})")
        linhas.append("")
    return "\n".join(linhas)


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.publicacoes.merge_data",
        description="Mescla uma remessa nova (mídia/DVD) no acervo existente (RN-08).",
    )
    parser.add_argument("--origem", type=Path, required=True, help="Acervo existente (é alterado se --executar).")
    parser.add_argument("--remessa", type=Path, required=True, help="Diretório da remessa/mídia nova.")
    parser.add_argument(
        "--relatorio",
        type=Path,
        default=None,
        help="Caminho do merge_report.txt (padrão: <origem>/merge_report.txt).",
    )
    parser.add_argument(
        "--executar",
        action="store_true",
        help="Aplica o merge de verdade. Sem esta flag, só relata (padrão seguro).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    args = montar_parser().parse_args(argv)

    if not args.origem.is_dir():
        logger.error("Acervo de origem não encontrado: %s", args.origem)
        return 1
    if not args.remessa.is_dir():
        logger.error("Remessa não encontrada: %s", args.remessa)
        return 1

    resultado = planejar_merge(args.origem, args.remessa)
    logger.info(
        "Merge: %d novo(s), %d idêntico(s), %d conflito(s).",
        len(resultado.novos), len(resultado.identicos), len(resultado.conflitos),
    )

    relatorio = gerar_relatorio(resultado, origem=args.origem, remessa=args.remessa)
    caminho_relatorio = args.relatorio or (args.origem / "merge_report.txt")
    caminho_relatorio.write_text(relatorio, encoding="utf-8")
    logger.info("Relatório salvo em %s.", caminho_relatorio)

    if not args.executar:
        logger.info("Modo relatório (padrão) — nada foi copiado ou movido. Use --executar para aplicar.")
        return 0

    if resultado.total_alteracoes == 0:
        logger.info("Nada a aplicar.")
        return 0

    aplicar_merge(args.origem, args.remessa, resultado)
    logger.info(
        "Merge aplicado: %d arquivo(s) novo(s) copiado(s), %d conflito(s) resolvido(s) "
        "(preteridos em %s).",
        len(resultado.novos), len(resultado.conflitos), args.origem / _NOME_PASTA_CONFLITOS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
