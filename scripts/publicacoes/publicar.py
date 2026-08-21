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
import shutil
from app.modules.publicacoes import service
from app.modules.publicacoes.models import Manual, ManualDocumento
from app.shared.core.enums import StatusEdicao, StatusUploadJob
from scripts.publicacoes import indexar as indexar_mod

logger = logging.getLogger("publicacoes.publicar")

ChaveDocumento = tuple[str, str, str]
"""
(origem, manual_codigo, file_key) — a origem entra porque os dois discos
(Manutenção/Operacional) podem trazer o mesmo `manual_codigo`+`file_key`
apontando para PDFs diferentes (11_achados_disco_completo.md §1); sem ela, o
inventário perderia metade dos documentos por colisão de chave silenciosa.
"""


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
                inventario[(manual.origem.value, manual.codigo, file_key)] = hash_arquivo
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
            select(
                Manual.origem, Manual.codigo, ManualDocumento.file_key, ManualDocumento.hash_sha256
            )
            .join(ManualDocumento, ManualDocumento.manual_id == Manual.id)
            .where(Manual.edicao_id == edicao.id)
        )
    ).all()
    return {
        (origem.value, codigo, file_key): (hash_sha256 or "")
        for origem, codigo, file_key, hash_sha256 in linhas
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
        for origem, manual, file_key in chaves[:limite]:
            bloco.append(f"- `[{origem}] {manual}/{file_key}`")
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
# Validação de Segurança do ZIP (M4.Web §4)
# --------------------------------------------------------------------------

EXTENSOES_ZIP_PROIBIDAS = {
    ".exe", ".bat", ".cmd", ".sh", ".py", ".dll", ".so", ".pif", ".application",
    ".gadget", ".msi", ".msp", ".com", ".scr", ".hta", ".cpl", ".msc", ".jar",
    ".vbs", ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh", ".ps1", ".ps1xml",
    ".ps2", ".ps2xml", ".psc1", ".psc2", ".msh", ".msh1", ".msh2", ".mshxml",
    ".msh1xml", ".msh2xml", ".scf", ".lnk", ".inf", ".reg"
}


class ValidacaoZipError(ValueError):
    """Exceção para pacotes ZIP maliciosos ou fora do padrão aceito."""
    pass


def validar_pacote_zip(
    caminho_zip: Path,
    *,
    max_descomprimido_bytes: int = 16 * 1024 * 1024 * 1024,  # 16 GB — cobre disco bruto
    max_entradas: int = 200_000,
    max_compressao_ratio: float = 50.0,
) -> tuple[int, list[str]]:
    """
    Valida a integridade e segurança do arquivo ZIP antes da extração.
    Retorna (número de entradas no arquivo ZIP, lista de nomes com extensão
    proibida — que devem ser IGNORADOS na extração, não fazem o pacote inteiro
    ser rejeitado).

    Lança ValidacaoZipError apenas para riscos reais e extensão-agnósticos:
    Zip-Slip (contenção de caminho) e Zip Bomb (tamanho/razão de compressão).

    `max_entradas`/`max_descomprimido_bytes` foram elevados (de 10 mil/8 GB
    para 200 mil/16 GB) porque um disco bruto de manuais zipado por inteiro
    (não apenas os PDFs de uma edição) facilmente ultrapassa os tetos
    anteriores, pensados só para o ZIP curado de uma edição.
    """
    if not caminho_zip.is_file():
        raise ValidacaoZipError(f"Arquivo ZIP não encontrado: {caminho_zip}")

    total_descomprimido = 0
    total_entradas = 0
    entradas_ignoradas: list[str] = []

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        infolist = zf.infolist()
        if len(infolist) > max_entradas:
            raise ValidacaoZipError(
                f"O arquivo ZIP contém muitas entradas ({len(infolist)} > máximo de {max_entradas})."
            )

        for member in infolist:
            total_entradas += 1
            filename = member.filename

            # 1. Contenção de caminho (Zip-Slip) — sempre fatal, independe de extensão
            if filename.startswith("/") or filename.startswith("\\") or ".." in filename or ":" in filename:
                raise ValidacaoZipError(
                    f"Caminho suspeito detectado no pacote ZIP (Zip-Slip risk): {filename!r}"
                )

            # 2. Extensões proibidas: um disco bruto legitimamente contém
            # instaladores/autorun (.exe, .dll, .js) do leitor de manuais.
            # Em vez de rejeitar o pacote inteiro, marcamos para não extrair
            # esses arquivos — eles nunca chegam a tocar o disco de staging.
            p = Path(filename)
            ext = p.suffix.lower()
            if ext in EXTENSOES_ZIP_PROIBIDAS:
                entradas_ignoradas.append(filename)
                continue

            if not member.is_dir():
                # 3. Zip bomb (teto total e razão por entrada) — sempre fatal
                uncompressed_size = member.file_size
                compressed_size = member.compress_size
                total_descomprimido += uncompressed_size

                if total_descomprimido > max_descomprimido_bytes:
                    raise ValidacaoZipError(
                        f"Tamanho total descomprimido excede o limite máximo permitido ({max_descomprimido_bytes // (1024 * 1024)} MB)."
                    )

                if compressed_size > 0:
                    ratio = uncompressed_size / compressed_size
                    if ratio > max_compressao_ratio and uncompressed_size > 10 * 1024 * 1024:
                        raise ValidacaoZipError(
                            f"Razão de compressão suspeita na entrada {filename!r} (ratio: {ratio:.1f}x > {max_compressao_ratio}x)."
                        )

    return total_entradas, entradas_ignoradas


def extrair_pacote_zip_seguro(caminho_zip: Path, destino: Path, entradas_ignoradas: list[str]) -> None:
    """
    Extrai o ZIP já validado por `validar_pacote_zip`, pulando as entradas
    com extensão proibida (nunca tocam o disco de staging) e resolvendo cada
    caminho contra `destino` para reforçar a contenção Zip-Slip em profundidade.
    """
    ignoradas = set(entradas_ignoradas)
    destino_resolvido = destino.resolve()

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        for member in zf.infolist():
            if member.filename in ignoradas:
                continue
            caminho_final = (destino_resolvido / member.filename).resolve()
            if destino_resolvido not in caminho_final.parents and caminho_final != destino_resolvido:
                raise ValidacaoZipError(
                    f"Caminho resolvido fora do destino de extração: {member.filename!r}"
                )
            zf.extract(member, destino_resolvido)


async def atualizar_progresso_job(
    job_id: str | None,
    etapa: str,
    pct: int,
    *,
    status: StatusUploadJob | None = None,
    erro: str | None = None,
    edicao_id: uuid.UUID | None = None,
) -> None:
    """Atualiza a linha de publicacoes_upload_jobs no banco principal em sessão própria."""
    if not job_id:
        return
    try:
        from sqlalchemy import select
        import uuid as uuid_mod
        from app.modules.publicacoes.models import PublicacoesUploadJob
        session_factory = get_session_factory()
        async with session_factory() as session:
            job_uuid = uuid_mod.UUID(job_id) if isinstance(job_id, str) else job_id
            job = (
                await session.execute(
                    select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job_uuid)
                )
            ).scalar_one_or_none()
            if job:
                job.etapa = etapa
                job.progresso_pct = pct
                if status is not None:
                    job.status = status
                if erro is not None:
                    job.erro = erro
                if edicao_id is not None:
                    job.edicao_id = edicao_id
                await session.commit()
    except Exception as exc:
        logger.warning("Não foi possível atualizar o progresso do job %s: %s", job_id, exc)


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
        "--de-upload",
        help="Caminho ou key do arquivo ZIP de upload no storage.",
    )
    parser.add_argument(
        "--job-id",
        help="UUID do job de upload para acompanhamento de progresso no banco.",
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

    staging_dir: Path | None = None
    if args.de_upload:
        await atualizar_progresso_job(args.job_id, "Iniciando download do pacote do storage...", 10)
        staging_dir = Path("var/publicacoes/staging") / (args.job_id or args.edicao)
        staging_dir.mkdir(parents=True, exist_ok=True)
        caminho_zip_staging = staging_dir / "edicao.zip"

        try:
            # Baixar ou copiar arquivo do storage para staging
            if settings.storage_backend.lower() == "r2":
                cliente_s3 = _obter_cliente_s3(settings)
                logger.info("Baixando %s do R2 para %s...", args.de_upload, caminho_zip_staging)
                cliente_s3.download_file(settings.r2_bucket_name, args.de_upload, str(caminho_zip_staging))
            else:
                caminho_origem = Path(settings.upload_dir) / args.de_upload
                if not caminho_origem.is_file():
                    caminho_origem = Path(args.de_upload)
                if not caminho_origem.is_file():
                    raise FileNotFoundError(f"Arquivo de upload local não encontrado: {args.de_upload}")
                shutil.copyfile(caminho_origem, caminho_zip_staging)

            await atualizar_progresso_job(args.job_id, "Validando integridade e segurança do ZIP...", 20)
            _total_entradas, entradas_ignoradas = validar_pacote_zip(caminho_zip_staging)
            if entradas_ignoradas:
                logger.warning(
                    "%d entrada(s) com extensão não permitida foram ignoradas (não extraídas): %s",
                    len(entradas_ignoradas),
                    ", ".join(entradas_ignoradas[:10]) + ("…" if len(entradas_ignoradas) > 10 else ""),
                )

            # Extração para pasta temporária de Manuais
            pasta_manuais_staging = staging_dir / "Manuais"
            pasta_manuais_staging.mkdir(parents=True, exist_ok=True)
            await atualizar_progresso_job(args.job_id, "Descompactando manuais...", 30)

            extrair_pacote_zip_seguro(caminho_zip_staging, pasta_manuais_staging, entradas_ignoradas)

            # Se o ZIP descompactado tiver uma subpasta "Manuais" ou com o nome da edição, ajusta
            if (pasta_manuais_staging / "Manuais").is_dir():
                args.acervo = pasta_manuais_staging / "Manuais"
            elif (pasta_manuais_staging / args.edicao).is_dir():
                args.acervo = pasta_manuais_staging / args.edicao
            else:
                args.acervo = pasta_manuais_staging

        except Exception as exc:
            logger.error("Erro no processamento do upload: %s", exc)
            await atualizar_progresso_job(
                args.job_id,
                "Falha na validação ou extração do pacote ZIP",
                0,
                status=StatusUploadJob.FALHOU,
                erro=str(exc),
            )
            if staging_dir and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            return 1

    if not args.acervo.is_dir():
        logger.error("Acervo não encontrado: %s", args.acervo)
        await atualizar_progresso_job(
            args.job_id, "Diretório de acervo não encontrado", 0, status=StatusUploadJob.FALHOU, erro=f"Acervo não encontrado: {args.acervo}"
        )
        return 1

    session_factory = get_session_factory()
    async with session_factory() as db:
        edicao_vigente = await service.obter_edicao_vigente(db)
        antigo = await inventario_da_edicao_vigente(db)

    await atualizar_progresso_job(args.job_id, "Calculando inventário e diff do acervo...", 40)
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

    nova_edicao_obj = None
    if not args.pular_indexacao:
        await atualizar_progresso_job(args.job_id, "Reindexando acervo...", 50)
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
            await atualizar_progresso_job(
                args.job_id, "Indexação do acervo falhou", 0, status=StatusUploadJob.FALHOU, erro=f"Erro na indexação (código {codigo})"
            )
            return codigo

        async with session_factory() as db:
            nova_edicao_obj = await service.obter_ou_criar_edicao(db, args.edicao)
            nova_edicao_obj.relatorio_diff = relatorio
            await db.commit()

    if not args.pular_upload:
        await atualizar_progresso_job(args.job_id, "Gerando snapshot da edição e enviando ao storage...", 85)
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

    # Limpeza explícita da key temporária de upload no R2/storage local
    if args.de_upload:
        try:
            if settings.storage_backend.lower() == "r2":
                cliente_s3 = _obter_cliente_s3(settings)
                cliente_s3.delete_object(Bucket=settings.r2_bucket_name, Key=args.de_upload)
                logger.info("Key temporária de upload removida do R2: %s", args.de_upload)
            else:
                caminho_temp = Path(settings.upload_dir) / args.de_upload
                if caminho_temp.is_file():
                    caminho_temp.unlink()
        except Exception as exc:
            logger.warning("Falha ao apagar arquivo de upload temporário %s: %s", args.de_upload, exc)

    # Limpar pasta local de staging se existia
    if staging_dir and staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    await atualizar_progresso_job(
        args.job_id,
        "Publicação concluída com sucesso (aguardando ativação)",
        100,
        status=StatusUploadJob.CONCLUIDO,
        edicao_id=nova_edicao_obj.id if nova_edicao_obj else None,
    )

    logger.info(
        "Publicação da edição %r concluída — status AGUARDANDO_ATIVACAO. "
        "Ativar é uma ação administrativa separada (M4 tarefa 4).",
        args.edicao,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
