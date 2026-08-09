"""
tests/integration/test_publicacoes_upload_api.py
Teste de integração para o endpoint POST /publicacoes/api/edicoes/uploads.
Garante que requisições válidas com payload JSON são aceitas com HTTP 201 e não retornam HTTP 422.
"""

import pytest
import uuid
from app.modules.auth.models import Usuario
from app.modules.auth.security import criar_token
from app.modules.auth.roles import ADMINISTRADOR


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
