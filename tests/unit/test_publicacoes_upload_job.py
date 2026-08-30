import pytest
import uuid
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from app.shared.core.enums import StatusUploadJob
from app.modules.publicacoes.models import PublicacoesUploadJob
from app.modules.auth.models import Usuario


async def _criar_usuario_teste(db, prefix="user"):
    u = Usuario(
        nome=f"Usuario Teste {prefix}",
        posto="Ten",
        especialidade="ELT",
        funcao="ADMINISTRADOR",
        ramal="2501",
        username=f"user_{uuid.uuid4().hex[:8]}",
        senha_hash="hash",
    )
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_criar_e_obter_upload_job(db):
    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    user = await _criar_usuario_teste(db, "job1")
    job = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-test",
        status=StatusUploadJob.ENVIANDO,
        etapa="Iniciando...",
        progresso_pct=0,
        file_key="publicacoes/uploads/test/edicao.zip",
        upload_id_r2="upload-id-123",
        tamanho_declarado=1048576,
        criado_por_id=user.id,
    )
    db.add(job)
    await db.commit()

    from sqlalchemy import select
    res = (await db.execute(select(PublicacoesUploadJob).where(PublicacoesUploadJob.id == job.id))).scalar_one()
    assert res.rotulo == "2027-test"
    assert res.status == StatusUploadJob.ENVIANDO
    assert res.tamanho_declarado == 1048576


@pytest.mark.asyncio
async def test_single_flight_lock_upload_job(db):
    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    user = await _criar_usuario_teste(db, "job2")
    job1 = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-a",
        status=StatusUploadJob.ENVIANDO,
        file_key="publicacoes/uploads/test1/edicao.zip",
        tamanho_declarado=100,
        criado_por_id=user.id,
    )
    db.add(job1)
    await db.commit()

    job2 = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-b",
        status=StatusUploadJob.PROCESSANDO,
        file_key="publicacoes/uploads/test2/edicao.zip",
        tamanho_declarado=100,
        criado_por_id=user.id,
    )
    db.add(job2)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_limpar_jobs_upload_estagnados(db):
    from datetime import datetime, timezone, timedelta
    from app.modules.publicacoes import service

    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    user = await _criar_usuario_teste(db, "job_stale")

    # 1. Testar limpeza de job ENVIANDO antigo (estagnado há 2 horas)
    job_enviando_antigo = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-old",
        status=StatusUploadJob.ENVIANDO,
        file_key="publicacoes/uploads/old/edicao.zip",
        tamanho_declarado=100,
        criado_por_id=user.id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add(job_enviando_antigo)
    await db.commit()

    limpados = await service.limpar_jobs_upload_estagnados(db, timeout_minutos=60)
    assert limpados == 1
    await db.refresh(job_enviando_antigo)
    assert job_enviando_antigo.status == StatusUploadJob.FALHOU
    assert "expirado" in job_enviando_antigo.etapa.lower()

    # 2. Testar limpeza de job PROCESSANDO com PID inexistente
    job_processando_orfeo = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-dead",
        status=StatusUploadJob.PROCESSANDO,
        file_key="publicacoes/uploads/dead/edicao.zip",
        processo_pid=99999999,  # PID fake inativo
        tamanho_declarado=100,
        criado_por_id=user.id,
    )
    db.add(job_processando_orfeo)
    await db.commit()

    limpados2 = await service.limpar_jobs_upload_estagnados(db, timeout_minutos=60)
    assert limpados2 == 1
    await db.refresh(job_processando_orfeo)
    assert job_processando_orfeo.status == StatusUploadJob.FALHOU
    assert "interrompido" in job_processando_orfeo.etapa.lower()


@pytest.mark.asyncio
async def test_recuperar_jobs_upload_interrompidos_startup(db):
    from app.bootstrap import tasks

    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    user = await _criar_usuario_teste(db, "job_startup")
    job_enviando = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-startup",
        status=StatusUploadJob.ENVIANDO,
        file_key="publicacoes/uploads/startup/edicao.zip",
        tamanho_declarado=100,
        criado_por_id=user.id,
    )
    db.add(job_enviando)
    await db.commit()

    recuperados = await tasks.recuperar_jobs_upload_interrompidos(db)
    assert recuperados >= 1

    await db.refresh(job_enviando)
    assert job_enviando.status == StatusUploadJob.FALHOU
    assert "reinicialização" in job_enviando.erro.lower()

