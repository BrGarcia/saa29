"""
scripts/publicacoes/publicar.py
Estação de publicação — ciclo de republicação anual do acervo de manuais (M4).

    python -m scripts.publicacoes.publicar --edicao 2027
    python -m scripts.publicacoes.publicar --edicao 2027 --dry-run
    python -m scripts.publicacoes.publicar --edicao 2027 --pular-upload

Fluxo (M4 tarefa 2), nesta ordem:

1. Inventaria `--acervo` (hash SHA-256 por PDF, reaproveitando
   `indexar.hash_arquivo`) e compara com a edição VIGENTE hoje no banco
   principal → diff por (manual, arquivo): novos, alterados, removidos,
   inalterados.
2. Escreve o relatório de diff (markdown, em disco e em
   `manuais_edicoes.relatorio_diff` da edição nova).
3. Reindexação: chama `scripts.publicacoes.indexar` sobre o acervo inteiro,
   criando a edição nova como `AGUARDANDO_ATIVACAO` — ativar é uma ação
   administrativa separada (tarefa 4), fora deste script.
4. Snapshot: zip do acervo inteiro, upload ao R2, poda de snapshots além de
   `PUBLICACOES_SNAPSHOTS_RETIDOS`.

**Sobre "extração incremental do delta" do plano original:** este script
recalcula o diff antes de reindexar (para o relatório e para decidir se vale
a pena publicar), mas a reindexação em si ainda reprocessa o acervo inteiro
via `indexar.py` — que já é rápido o bastante no piloto (2,6s/411 PDFs) para
não justificar, por ora, o trabalho de copiar páginas inalteradas do
`catalog.db` antigo para o novo. Registrado como limitação conhecida, não
bug: a correção (diff) é o que importa para o relatório e para a decisão de
publicar; a velocidade da reindexação é uma otimização de "quando incomodar".

**Este script nunca ativa a edição.** Ativar/reverter é a tarefa 4 do M4
(card em `/configuracoes`), uma decisão humana feita depois de ler o
relatório de diff — publicar e ativar são deliberadamente ações separadas.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bootstrap.config import get_settings
from app.bootstrap.database import get_session_factory

import app.modules.aeronaves.models     # noqa: F401
import app.modules.auth.models          # noqa: F401
import app.modules.calendario.models    # noqa: F401
import app.modules.efetivo.models       # noqa: F401
import app.modules.equipamentos.models  # noqa: F401
import app.modules.inspecoes.models     # noqa: F401
import app.modules.panes.models         # noqa: F401
import app.modules.vencimentos.models   # noqa: F401
from app.modules.publicacoes import service
from app.modules.publicacoes.models import Manual, ManualDocumento
from app.shared.core.enums import StatusEdicao
from scripts.publicacoes import indexar as indexar_mod

logger = logging.getLogger("publicacoes.publicar")

ChaveDocumento = tuple[str, str]
"""(manual_codigo, file_key) — a mesma chave natural de `uq_manuais_documentos_manual_file`."""


@dataclass
class DiffAcervo:
    novos: list[ChaveDocumento] = field(default_factory=list)
    alterados: list[ChaveDocumento] = field(default_factory=list)
    removidos: list[ChaveDocumento] = field(default_factory=list)
    inalterados: int = 0

    @property
    def total_mudancas(self) -> int:
        return len(self.novos) + len(self.alterados) + len(self.removidos)


# --------------------------------------------------------------------------
# Inventário e diff
# --------------------------------------------------------------------------


def inventariar_acervo(acervo_dir: Path) -> dict[ChaveDocumento, str]:
    """
    Hash de cada PDF do acervo, chaveado por (manual, caminho relativo).

    Reaproveita `indexar.descobrir_manuais`/`hash_arquivo` — a mesma noção de
    "manual" e de "arquivo" usada na indexação, para que a chave bata com a
    de `manuais_documentos` sem tradução.
    """
    inventario: dict[ChaveDocumento, str] = {}
    for manual in indexar_mod.descobrir_manuais(acervo_dir, None):
        for pdf_path in manual.pdfs:
            file_key = pdf_path.relative_to(manual.raiz).as_posix()
            hash_arquivo = indexar_mod.hash_arquivo(pdf_path)
            if hash_arquivo is not None:
                inventario[(manual.codigo, file_key)] = hash_arquivo
    return inventario


async def inventario_da_edicao_vigente(db) -> dict[ChaveDocumento, str]:
    """
    Hash de cada documento da edição VIGENTE hoje, ou vazio se não houver
    edição vigente (primeira publicação).
    """
    edicao = await service.obter_edicao_vigente(db)
    if edicao is None:
        return {}

    from sqlalchemy import select

    linhas = (
        await db.execute(
            select(Manual.codigo, ManualDocumento.file_key, ManualDocumento.hash_sha256)
            .join(ManualDocumento, ManualDocumento.manual_id == Manual.id)
            .where(Manual.edicao_id == edicao.id)
        )
    ).all()
    return {
        (codigo, file_key): (hash_sha256 or "")
        for codigo, file_key, hash_sha256 in linhas
    }


def calcular_diff(
    antigo: dict[ChaveDocumento, str], novo: dict[ChaveDocumento, str]
) -> DiffAcervo:
    chaves_antigas = set(antigo)
    chaves_novas = set(novo)
    comuns = chaves_antigas & chaves_novas

    return DiffAcervo(
        novos=sorted(chaves_novas - chaves_antigas),
        alterados=sorted(k for k in comuns if antigo[k] != novo[k]),
        removidos=sorted(chaves_antigas - chaves_novas),
        inalterados=len(comuns) - len([k for k in comuns if antigo[k] != novo[k]]),
    )


def gerar_relatorio_markdown(
    diff: DiffAcervo, *, edicao_nova: str, edicao_anterior: str | None
) -> str:
    """
    Relatório de diff, no formato que a tarefa 2 espera
    (`relatorio_publicacao_<ano>.md`) — texto simples o bastante para ser
    lido por um humano decidindo se ativa a edição, sem precisar abrir o
    banco.
    """
    linhas = [
        f"# Relatório de publicação — edição {edicao_nova}",
        "",
        f"Comparado com: {edicao_anterior or '(nenhuma edição vigente — primeira publicação)'}",
        f"Gerado em: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Resumo",
        "",
        f"- Novos: {len(diff.novos)}",
        f"- Alterados: {len(diff.alterados)}",
        f"- Removidos: {len(diff.removidos)}",
        f"- Inalterados: {diff.inalterados}",
    ]

    def _secao(titulo: str, chaves: list[ChaveDocumento], limite: int = 200) -> list[str]:
        if not chaves:
            return [f"## {titulo}", "", "(nenhum)", ""]
        bloco = [f"## {titulo} ({len(chaves)})", ""]
        for manual, file_key in chaves[:limite]:
            bloco.append(f"- `{manual}/{file_key}`")
        if len(chaves) > limite:
            bloco.append(f"- … e mais {len(chaves) - limite}")
        bloco.append("")
        return bloco

    linhas.append("")
    linhas += _secao("Documentos novos", diff.novos)
    linhas += _secao("Documentos alterados", diff.alterados)
    linhas += _secao("Documentos removidos", diff.removidos)

    return "\n".join(linhas)


# --------------------------------------------------------------------------
# Snapshot e R2
# --------------------------------------------------------------------------


def criar_snapshot_zip(acervo_dir: Path, destino_zip: Path) -> Path:
    """Zip de todo o acervo — o snapshot retido no R2 para uma edição."""
    destino_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in acervo_dir.rglob("*"):
            if arquivo.is_file():
                zf.write(arquivo, arquivo.relative_to(acervo_dir))
    return destino_zip


def _obter_cliente_s3(settings):
    """
    Mesmo padrão de `scripts/maintenance/r2_manager.py` — boto3 direto, sem
    passar por `StorageService` (que força o prefixo `anexos/` e a allowlist
    de extensão de upload de usuário, nenhum dos dois cabível para um
    snapshot interno `.zip`).
    """
    if not all([
        settings.r2_endpoint, settings.r2_access_key_id,
        settings.r2_secret_access_key, settings.r2_bucket_name,
    ]):
        raise RuntimeError("Variáveis de ambiente R2 incompletas — upload de snapshot abortado.")

    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


_PREFIXO_SNAPSHOTS = "publicacoes/snapshots/"


def enviar_snapshot(cliente_s3, bucket: str, caminho_zip: Path, edicao: str) -> str:
    chave = f"{_PREFIXO_SNAPSHOTS}{edicao}.zip"
    cliente_s3.upload_file(str(caminho_zip), bucket, chave)
    return chave


def podar_snapshots_antigos(cliente_s3, bucket: str, manter: int) -> list[str]:
    """Remove snapshots além de `PUBLICACOES_SNAPSHOTS_RETIDOS`, mais recentes primeiro."""
    resposta = cliente_s3.list_objects_v2(Bucket=bucket, Prefix=_PREFIXO_SNAPSHOTS)
    objetos = sorted(
        resposta.get("Contents", []), key=lambda o: o["LastModified"], reverse=True
    )
    excedentes = objetos[manter:]
    for obj in excedentes:
        cliente_s3.delete_object(Bucket=bucket, Key=obj["Key"])
    return [o["Key"] for o in excedentes]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def montar_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="python -m scripts.publicacoes.publicar",
        description="Publica uma edição do acervo: diff, reindexação, snapshot e upload.",
    )
    parser.add_argument("--edicao", required=True, help="Rótulo da nova edição (ex: '2027').")
    parser.add_argument(
        "--acervo",
        type=Path,
        default=Path(settings.publicacoes_acervo_dir) / "Manuais",
        help="Diretório do acervo (um subdiretório por manual).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só calcula e imprime o diff — não reindexa, não publica snapshot.",
    )
    parser.add_argument(
        "--pular-indexacao", action="store_true", help="Não chama scripts.publicacoes.indexar."
    )
    parser.add_argument(
        "--pular-upload", action="store_true", help="Não gera nem envia o snapshot ao R2."
    )
    parser.add_argument(
        "--relatorio-dir",
        type=Path,
        default=Path("var/publicacoes/relatorios"),
        help="Diretório onde salvar relatorio_publicacao_<edicao>.md.",
    )
    return parser


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    args = montar_parser().parse_args(argv)
    settings = get_settings()

    if not args.acervo.is_dir():
        logger.error("Acervo não encontrado: %s", args.acervo)
        return 1

    session_factory = get_session_factory()
    async with session_factory() as db:
        edicao_vigente = await service.obter_edicao_vigente(db)
        antigo = await inventario_da_edicao_vigente(db)

    logger.info("Inventariando %s…", args.acervo)
    novo = inventariar_acervo(args.acervo)
    diff = calcular_diff(antigo, novo)
    logger.info(
        "Diff: %d novo(s), %d alterado(s), %d removido(s), %d inalterado(s).",
        len(diff.novos), len(diff.alterados), len(diff.removidos), diff.inalterados,
    )

    relatorio = gerar_relatorio_markdown(
        diff,
        edicao_nova=args.edicao,
        edicao_anterior=edicao_vigente.rotulo if edicao_vigente else None,
    )
    args.relatorio_dir.mkdir(parents=True, exist_ok=True)
    caminho_relatorio = args.relatorio_dir / f"relatorio_publicacao_{args.edicao}.md"
    caminho_relatorio.write_text(relatorio, encoding="utf-8")
    logger.info("Relatório salvo em %s.", caminho_relatorio)

    if args.dry_run:
        logger.info("--dry-run: nada foi reindexado nem publicado.")
        return 0

    if diff.total_mudancas == 0 and edicao_vigente is not None:
        logger.warning(
            "Nenhuma mudança detectada em relação à edição vigente (%s) — "
            "publicando mesmo assim, a pedido explícito de --edicao %s.",
            edicao_vigente.rotulo, args.edicao,
        )

    if not args.pular_indexacao:
        # Pré-cria a edição como AGUARDANDO_ATIVACAO ANTES de indexar: o
        # indexador (`indexar.gravar_no_banco_principal`) faz um get-or-create
        # com status VIGENTE por padrão (comportamento certo para o piloto do
        # M1, que não tem conceito de ativação) — se a linha já existir, o
        # status informado ali é ignorado e o que ficou gravado aqui prevalece.
        # Sem este passo, toda reindexação publicaria a edição já vigente,
        # pulando a revisão humana do relatório de diff que a tarefa 4 exige.
        async with session_factory() as db:
            await service.obter_ou_criar_edicao(
                db, args.edicao, status=StatusEdicao.AGUARDANDO_ATIVACAO
            )
            await db.commit()

        logger.info("Reindexando o acervo inteiro sob a edição %r…", args.edicao)
        codigo = await indexar_mod.main([
            "--entrada", str(args.acervo),
            "--edicao", args.edicao,
            "--acervo", str(Path(settings.publicacoes_acervo_dir)),
        ])
        if codigo != 0:
            logger.error("Indexação falhou (código %d) — publicação abortada.", codigo)
            return codigo

        async with session_factory() as db:
            nova_edicao = await service.obter_ou_criar_edicao(db, args.edicao)
            nova_edicao.relatorio_diff = relatorio
            await db.commit()

    if not args.pular_upload:
        with __import__("tempfile").TemporaryDirectory() as tmp:
            caminho_zip = Path(tmp) / f"{args.edicao}.zip"
            logger.info("Gerando snapshot ZIP de %s…", args.acervo)
            criar_snapshot_zip(args.acervo, caminho_zip)
            tamanho_mb = caminho_zip.stat().st_size / (1024 * 1024)
            logger.info("Snapshot: %.1f MB.", tamanho_mb)

            try:
                cliente_s3 = _obter_cliente_s3(settings)
                chave = enviar_snapshot(cliente_s3, settings.r2_bucket_name, caminho_zip, args.edicao)
                logger.info("Snapshot enviado: %s.", chave)
                removidos = podar_snapshots_antigos(
                    cliente_s3, settings.r2_bucket_name, settings.publicacoes_snapshots_retidos
                )
                if removidos:
                    logger.info("Snapshots antigos removidos (retenção=%d): %s",
                                settings.publicacoes_snapshots_retidos, ", ".join(removidos))
            except RuntimeError as exc:
                logger.warning("Upload ao R2 pulado: %s", exc)

    logger.info(
        "Publicação da edição %r concluída — status AGUARDANDO_ATIVACAO. "
        "Ativar é uma ação administrativa separada (M4 tarefa 4).",
        args.edicao,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
