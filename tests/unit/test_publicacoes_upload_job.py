import pytest
import uuid
from sqlalchemy import delete
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
    with pytest.raises(Exception):
        await db.commit()
    await db.rollback()
