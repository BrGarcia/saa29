"""
tests/unit/test_inspecao_pdf.py
Suíte de testes automatizados para validação da geração e download da Ordem de Inspeção em PDF.

Critérios de Aceite Validados:
- Endpoint exige autenticação (401 se sem token).
- Endpoint retorna 404 para inspeção inexistente.
- Sucesso retorna HTTP 200, Content-Type "application/pdf" e Content-Disposition "attachment".
- O conteúdo gerado consiste em bytes válidos no formato PDF (iniciado por %PDF-).
- A geração do PDF é 100% passiva e mantém os dados e o status da inspeção imutáveis.
"""

import uuid
from datetime import date
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.dependencies import get_current_user, get_db
from app.modules.inspecoes import models as inspecoes_models, schemas, service
from app.modules.inspecoes.router import router as inspecoes_router
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.shared.core.enums import StatusAeronave


INSPECOES_URL = "/inspecoes"


def criar_app_isolado(db: AsyncSession, usuario: Usuario | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(inspecoes_router, prefix=INSPECOES_URL)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if usuario is not None:
        async def override_get_current_user():
            return usuario

        app.dependency_overrides[get_current_user] = override_get_current_user

    return app


async def criar_usuario_teste(db: AsyncSession, funcao: str = "ENCARREGADO") -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Militar Teste {suffix}",
        posto="1S",
        especialidade="ELT",
        funcao=funcao,
        ramal="3000",
        trigrama=suffix[:3].upper(),
        username=f"user_pdf_{suffix}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def criar_aeronave_teste(db: AsyncSession) -> Aeronave:
    suffix = uuid.uuid4().hex[:8].upper()
    aeronave = Aeronave(
        serial_number=f"SN-PDF-{suffix}",
        matricula=f"FAB-{suffix[:4]}",
        modelo="A-29B",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def criar_inspecao_com_tarefas(db: AsyncSession) -> tuple[inspecoes_models.Inspecao, Usuario]:
    usuario = await criar_usuario_teste(db, funcao="ENCARREGADO")
    aeronave = await criar_aeronave_teste(db)

    tipo = await service.criar_tipo_inspecao(
        db,
        schemas.TipoInspecaoCreate(
            codigo=f"PDF-{uuid.uuid4().hex[:4].upper()}",
            nome="Inspeção Periódica PDF Test",
            descricao="Inspeção para teste de emissão de OS em PDF",
            duracao_dias=10,
        ),
    )

    tarefa_cat = await service.criar_tarefa_catalogo(
        db,
        schemas.TarefaCatalogoCreate(
            codigo=f"PDF-T-{uuid.uuid4().hex[:4].upper()}",
            titulo="Testar Sistemas Eletrônicos",
            descricao="Checar barramentos e computadores de bordo",
            sistema_ata="ATA-24",
            obrigatoria=True,
        ),
    )

    await service.criar_tarefa_template(
        db,
        tipo.id,
        schemas.TarefaTemplateCreate(
            tarefa_catalogo_id=tarefa_cat.id,
            ordem=1,
        ),
    )

    inspecao = await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(
            aeronave_id=aeronave.id,
            tipos_inspecao_ids=[tipo.id],
            observacoes="Aeronave em teste de emissão de PDF",
        ),
        aberto_por_id=usuario.id,
    )

    return inspecao, usuario


@pytest.mark.asyncio
async def test_endpoint_pdf_inspecao_sem_autenticacao_retorna_401(db: AsyncSession):
    """Garante que a rota de PDF exige autenticação."""
    app = criar_app_isolado(db, usuario=None)
    inspecao_id_falso = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{INSPECOES_URL}/{inspecao_id_falso}/pdf")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_endpoint_pdf_inspecao_inexistente_retorna_404(db: AsyncSession):
    """Garante erro 404 quando o UUID da inspeção não existe no banco."""
    usuario = await criar_usuario_teste(db)
    app = criar_app_isolado(db, usuario=usuario)
    inspecao_id_falso = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{INSPECOES_URL}/{inspecao_id_falso}/pdf")
    assert response.status_code == 404
    assert "Inspeção não encontrada" in response.json()["detail"]


@pytest.mark.asyncio
async def test_gerar_pdf_inspecao_servico_direto(db: AsyncSession):
    """Valida a chamada direta ao serviço de geração de PDF."""
    from app.modules.inspecoes import pdf_service

    inspecao, _ = await criar_inspecao_com_tarefas(db)
    
    # Chama o serviço de geração de PDF
    pdf_bytes = await pdf_service.gerar_pdf_ordem_inspecao(db, inspecao.id)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # Valida cabeçalho do arquivo PDF
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_gerar_pdf_inspecao_preserva_estado_banco(db: AsyncSession):
    """Garante que a emissão do PDF não altera o status nem persiste dados no banco (somente-leitura)."""
    from app.modules.inspecoes import pdf_service

    inspecao, _ = await criar_inspecao_com_tarefas(db)
    status_inicial = inspecao.status
    updated_at_inicial = inspecao.updated_at

    await pdf_service.gerar_pdf_ordem_inspecao(db, inspecao.id)

    # Recarregar do banco
    inspecao_recarregada = await service.buscar_inspecao(db, inspecao.id)
    assert inspecao_recarregada is not None
    assert inspecao_recarregada.status == status_inicial
    assert inspecao_recarregada.updated_at == updated_at_inicial


@pytest.mark.asyncio
async def test_endpoint_pdf_inspecao_sucesso(db: AsyncSession):
    """Testa a rota completa de download do PDF via cliente HTTP."""
    inspecao, usuario = await criar_inspecao_com_tarefas(db)
    app = criar_app_isolado(db, usuario=usuario)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{INSPECOES_URL}/{inspecao.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert ".pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")
