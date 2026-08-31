"""
tests/integration/test_publicacoes_upload_api.py
Teste de integração para o endpoint POST /publicacoes/api/edicoes/uploads.
Garante que requisições válidas com payload JSON são aceitas com HTTP 201 e não retornam HTTP 422.
"""

import pytest
import uuid
from sqlalchemy import delete
from app.modules.auth.models import Usuario
from app.modules.auth.security import criar_token
from app.modules.auth.roles import ADMINISTRADOR
from app.modules.publicacoes.models import PublicacoesUploadJob
from app.shared.core.enums import StatusUploadJob


@pytest.mark.asyncio
async def test_iniciar_upload_edicao_retorna_201_sucesso(client, db):
    u = Usuario(
        nome="Admin Teste Upload",
        posto="Cap",
        especialidade="ENG",
        funcao=ADMINISTRADOR,
        ramal="1234",
        username=f"admin_upload_{uuid.uuid4().hex[:6]}",
        senha_hash="hash",
    )
    db.add(u)
    await db.commit()

    token = criar_token(dados={"sub": u.username})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "rotulo": f"EDI-TEST-{uuid.uuid4().hex[:4]}",
        "tamanho_bytes": 5000000,
        "nome_arquivo": "manual_edicao_2026.zip",
    }

    res = await client.post("/publicacoes/api/edicoes/uploads", json=payload, headers=headers)
    
    assert res.status_code == 201, f"Esperado 201, recebido {res.status_code}: {res.text}"
    body = res.json()
    assert "job_id" in body
    assert "file_key" in body
    assert "upload_id_r2" in body


@pytest.mark.asyncio
async def test_upload_parte_local_dev_put_e_post_sucesso(client, db):
    u = Usuario(
        nome="Admin Parte Local",
        posto="Cap",
        especialidade="ENG",
        funcao=ADMINISTRADOR,
        ramal="1234",
        username=f"admin_parte_{uuid.uuid4().hex[:6]}",
        senha_hash="hash",
    )
    db.add(u)
    await db.commit()

    token = criar_token(dados={"sub": u.username})
    headers = {"Authorization": f"Bearer {token}"}
    upload_id = uuid.uuid4().hex

    # Teste com PUT
    res_put = await client.put(
        f"/publicacoes/api/edicoes/uploads/local-parte?upload_id={upload_id}&numero=1",
        content=b"conteudo_parte_1",
        headers=headers,
    )
    assert res_put.status_code == 200, f"Esperado 200 no PUT, recebido {res_put.status_code}: {res_put.text}"
    assert "etag" in res_put.json()

    # Teste com POST
    res_post = await client.post(
        f"/publicacoes/api/edicoes/uploads/local-parte?upload_id={upload_id}&numero=2",
        content=b"conteudo_parte_2",
        headers=headers,
    )
    assert res_post.status_code == 200, f"Esperado 200 no POST, recebido {res_post.status_code}: {res_post.text}"
    assert "etag" in res_post.json()


@pytest.mark.asyncio
async def test_listar_upload_jobs_apenas_ativos_retorna_job_ativo(client, db):
    """
    Item 3.7: GET /publicacoes/api/edicoes/uploads?apenas_ativos=true deve
    devolver o job em PROCESSANDO — é o caso que a retomada de polling usa
    para religar o acompanhamento após um reload de /configuracoes.
    """
    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    u = Usuario(
        nome="Admin Teste Uploads Ativos",
        posto="Cap",
        especialidade="ENG",
        funcao=ADMINISTRADOR,
        ramal="1234",
        username=f"admin_ativos_{uuid.uuid4().hex[:6]}",
        senha_hash="hash",
    )
    db.add(u)
    await db.flush()

    job_ativo = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-ativo",
        status=StatusUploadJob.PROCESSANDO,
        etapa="Processando pacote...",
        progresso_pct=60,
        file_key="publicacoes/uploads/test/ativo.zip",
        tamanho_declarado=1048576,
        criado_por_id=u.id,
    )
    db.add(job_ativo)
    await db.commit()

    token = criar_token(dados={"sub": u.username})
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/publicacoes/api/edicoes/uploads?apenas_ativos=true&limit=1", headers=headers)

    assert res.status_code == 200, f"Esperado 200, recebido {res.status_code}: {res.text}"
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == str(job_ativo.id)
    assert body[0]["status"] == "PROCESSANDO"


@pytest.mark.asyncio
async def test_listar_upload_jobs_apenas_ativos_omite_job_concluido_mais_recente(client, db):
    """
    Sem o filtro `apenas_ativos`, um job CONCLUIDO criado depois do ativo
    apareceria primeiro na ordenação por created_at e esconderia o job que
    a retomada de polling precisa achar — é exatamente a armadilha que o
    `?limit=1` sozinho (sugerido no backlog original) não evita.
    """
    await db.execute(delete(PublicacoesUploadJob))
    await db.commit()

    u = Usuario(
        nome="Admin Teste Uploads Ativos 2",
        posto="Cap",
        especialidade="ENG",
        funcao=ADMINISTRADOR,
        ramal="1234",
        username=f"admin_ativos2_{uuid.uuid4().hex[:6]}",
        senha_hash="hash",
    )
    db.add(u)
    await db.flush()

    job_ativo = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2027-ativo",
        status=StatusUploadJob.PROCESSANDO,
        etapa="Processando pacote...",
        progresso_pct=60,
        file_key="publicacoes/uploads/test/ativo.zip",
        tamanho_declarado=1048576,
        criado_por_id=u.id,
    )
    db.add(job_ativo)
    await db.flush()

    # Criado depois do ativo, e terminal — não conta para o índice único
    # parcial (só cobre ENVIANDO/AGUARDANDO_PROCESSAMENTO/PROCESSANDO).
    job_concluido = PublicacoesUploadJob(
        id=uuid.uuid4(),
        rotulo="2026-concluido",
        status=StatusUploadJob.CONCLUIDO,
        etapa="Concluído.",
        progresso_pct=100,
        file_key="publicacoes/uploads/test/concluido.zip",
        tamanho_declarado=2048,
        criado_por_id=u.id,
    )
    db.add(job_concluido)
    await db.commit()

    token = criar_token(dados={"sub": u.username})
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/publicacoes/api/edicoes/uploads?apenas_ativos=true&limit=1", headers=headers)

    assert res.status_code == 200, f"Esperado 200, recebido {res.status_code}: {res.text}"
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == str(job_ativo.id), "O filtro apenas_ativos não deve deixar o CONCLUIDO mais recente esconder o job ativo"

