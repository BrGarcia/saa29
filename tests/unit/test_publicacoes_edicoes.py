"""
tests/unit/test_publicacoes_edicoes.py
Ciclo de vida das edições — M4 tarefa 4, Fase 1 de `09_plano_configuracoes.md`.

O teste que prova que ativar muda o **resultado da busca** é de integração
(`test_publicacoes_busca.py::test_trocar_edicao_vigente_muda_o_que_a_busca_devolve`,
Fase 0). Aqui ficam as transições de estado, as recusas e o RBAC.

A recusa que mais importa é `ativar sem índice em disco`: sem ela, o botão
mudaria o status no banco e a busca continuaria servindo a edição antiga pela
queda de compatibilidade — pareceria funcionar e mentiria.
"""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicacoes import service
from app.shared.core.enums import StatusEdicao

URL = "/publicacoes/api/edicoes"


@pytest.fixture
def indices(tmp_path: Path, monkeypatch) -> Path:
    """
    Diretório-base dos índices, isolado do `var/` da máquina.

    Nenhum `catalog.*.db` existe de saída — cada teste cria os que precisa,
    porque a presença do arquivo é justamente o que decide se ativar é aceito.
    """

    class _SettingsFake:
        publicacoes_index_path = str(tmp_path / "catalog.db")

    monkeypatch.setattr(service, "get_settings", lambda: _SettingsFake())
    return tmp_path


def criar_indice(base: Path, rotulo: str) -> Path:
    caminho = base / f"catalog.{rotulo}.db"
    caminho.write_bytes(b"")
    return caminho


@pytest_asyncio.fixture
async def duas_edicoes(db: AsyncSession, indices: Path):
    """`vigente` (VIGENTE, com índice) e `nova` (AGUARDANDO, com índice)."""
    vigente = await service.obter_ou_criar_edicao(db, "vigente", status=StatusEdicao.VIGENTE)
    nova = await service.obter_ou_criar_edicao(
        db, "nova", status=StatusEdicao.AGUARDANDO_ATIVACAO
    )
    criar_indice(indices, "vigente")
    criar_indice(indices, "nova")
    await db.flush()
    return vigente, nova


# --------------------------------------------------------------------------
# Listagem
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_edicoes_traz_estado_do_indice(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    await service.obter_ou_criar_edicao(db, "com-indice", status=StatusEdicao.VIGENTE)
    await service.obter_ou_criar_edicao(db, "sem-indice", status=StatusEdicao.ANTERIOR)
    criar_indice(indices, "com-indice")
    await db.flush()

    corpo = (await client_autenticado.get(URL)).json()
    por_rotulo = {e["rotulo"]: e for e in corpo}

    assert por_rotulo["com-indice"]["indice_disponivel"] is True
    assert por_rotulo["sem-indice"]["indice_disponivel"] is False


@pytest.mark.asyncio
async def test_listar_edicoes_conta_manuais_e_documentos(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """Edição sem manual nenhum conta zero — não some da listagem (outerjoin)."""
    await service.obter_ou_criar_edicao(db, "vazia", status=StatusEdicao.AGUARDANDO_ATIVACAO)
    await db.flush()

    corpo = (await client_autenticado.get(URL)).json()
    vazia = next(e for e in corpo if e["rotulo"] == "vazia")
    assert vazia["manuais"] == 0
    assert vazia["documentos"] == 0


# --------------------------------------------------------------------------
# Ativar
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ativar_promove_e_rebaixa_a_anterior(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    vigente, nova = duas_edicoes

    resposta = await client_autenticado.post(f"{URL}/{nova.id}/ativar")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "VIGENTE"

    await db.refresh(vigente)
    await db.refresh(nova)
    assert nova.status == StatusEdicao.VIGENTE
    assert vigente.status == StatusEdicao.ANTERIOR


@pytest.mark.asyncio
async def test_reverter_e_ativar_a_anterior(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    """
    Não existe endpoint de "reverter" — reverter É ativar a edição ANTERIOR.
    Um caminho de código só, e o mesmo comportamento nos dois sentidos.
    """
    vigente, nova = duas_edicoes

    await client_autenticado.post(f"{URL}/{nova.id}/ativar")
    resposta = await client_autenticado.post(f"{URL}/{vigente.id}/ativar")
    assert resposta.status_code == 200

    await db.refresh(vigente)
    await db.refresh(nova)
    assert vigente.status == StatusEdicao.VIGENTE
    assert nova.status == StatusEdicao.ANTERIOR


@pytest.mark.asyncio
async def test_ativar_sem_indice_em_disco_retorna_409_com_o_comando_de_correcao(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """
    A recusa que sustenta a honestidade do botão.

    Sem ela o status mudaria no banco e a busca continuaria devolvendo a edição
    antiga (queda para o índice legado) — o operador veria "ativada" e o
    mecânico continuaria lendo o manual velho.

    A mensagem carrega o comando de reindexação porque quem toma esse 409 é um
    administrador na tela, não um desenvolvedor lendo log.
    """
    await service.obter_ou_criar_edicao(db, "vigente", status=StatusEdicao.VIGENTE)
    criar_indice(indices, "vigente")
    orfa = await service.obter_ou_criar_edicao(
        db, "sem-indice", status=StatusEdicao.AGUARDANDO_ATIVACAO
    )
    await db.flush()

    resposta = await client_autenticado.post(f"{URL}/{orfa.id}/ativar")
    assert resposta.status_code == 409
    detalhe = resposta.json()["detail"]
    assert "indexar --edicao sem-indice" in detalhe


@pytest.mark.asyncio
async def test_ativar_sem_indice_nao_altera_o_status(db: AsyncSession, indices: Path):
    """
    Complemento do teste acima, no nível de serviço e não por HTTP.

    Motivo: `override_get_db` do conftest faz `rollback()` da transação de
    teste inteira em QUALQUER exceção que passe pela dependência — inclusive um
    409 intencional. Depois da requisição, as linhas apenas "flushadas" deste
    teste já não existem, e `db.refresh()` falha com "not persistent". Chamar o
    serviço direto mantém a sessão viva e permite afirmar o que interessa: a
    recusa não deixou efeito colateral.
    """
    from app.shared.core.exceptions import ConflitoNegocioError

    vigente = await service.obter_ou_criar_edicao(db, "vig", status=StatusEdicao.VIGENTE)
    criar_indice(indices, "vig")
    orfa = await service.obter_ou_criar_edicao(
        db, "orfa", status=StatusEdicao.AGUARDANDO_ATIVACAO
    )
    await db.flush()

    with pytest.raises(ConflitoNegocioError):
        await service.ativar_edicao(db, orfa.id, usuario_id=uuid.uuid4())

    assert orfa.status == StatusEdicao.AGUARDANDO_ATIVACAO
    assert vigente.status == StatusEdicao.VIGENTE, "a vigente não pode ser rebaixada em vão"


@pytest.mark.asyncio
async def test_ativar_a_que_ja_e_vigente_retorna_409(
    client_autenticado: AsyncClient, duas_edicoes
):
    """Não é no-op silencioso: um clique sem efeito precisa dizer que não teve efeito."""
    vigente, _ = duas_edicoes
    resposta = await client_autenticado.post(f"{URL}/{vigente.id}/ativar")
    assert resposta.status_code == 409


@pytest.mark.asyncio
async def test_ativar_arquivada_retorna_409(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    await service.obter_ou_criar_edicao(db, "vigente", status=StatusEdicao.VIGENTE)
    arquivada = await service.obter_ou_criar_edicao(
        db, "velha", status=StatusEdicao.ARQUIVADA
    )
    criar_indice(indices, "vigente")
    criar_indice(indices, "velha")  # arquivo até existe; o status é que barra
    await db.flush()

    resposta = await client_autenticado.post(f"{URL}/{arquivada.id}/ativar")
    assert resposta.status_code == 409
    assert "arquivada" in resposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ativar_edicao_inexistente_retorna_404(
    client_autenticado: AsyncClient, indices: Path
):
    resposta = await client_autenticado.post(f"{URL}/{uuid.uuid4()}/ativar")
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_ativar_registra_quem_ativou(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    """
    `publicado_por_id` fica nulo quando a edição nasce de script offline. A
    ativação pela tela é a primeira vez que há alguém a quem atribuir a decisão.
    """
    _, nova = duas_edicoes
    assert nova.publicado_por_id is None

    await client_autenticado.post(f"{URL}/{nova.id}/ativar")
    await db.refresh(nova)
    assert nova.publicado_por_id is not None


@pytest.mark.asyncio
async def test_invariante_uma_unica_vigente_apos_sequencia_de_ativacoes(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """Qualquer sequência de ativações termina com exatamente uma VIGENTE."""
    from sqlalchemy import func, select

    from app.modules.publicacoes.models import ManualEdicao

    edicoes = []
    for rotulo in ("e1", "e2", "e3"):
        status_inicial = (
            StatusEdicao.VIGENTE if rotulo == "e1" else StatusEdicao.AGUARDANDO_ATIVACAO
        )
        edicoes.append(await service.obter_ou_criar_edicao(db, rotulo, status=status_inicial))
        criar_indice(indices, rotulo)
    await db.flush()

    for alvo in (edicoes[1], edicoes[2], edicoes[0], edicoes[2]):
        await client_autenticado.post(f"{URL}/{alvo.id}/ativar")

    total_vigentes = (
        await db.execute(
            select(func.count(ManualEdicao.id)).where(
                ManualEdicao.status == StatusEdicao.VIGENTE
            )
        )
    ).scalar_one()
    assert total_vigentes == 1


# --------------------------------------------------------------------------
# Validação de rótulo (BUG-01)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("rotulo", ["2024/R1", "a b", "x" * 21])
async def test_obter_ou_criar_edicao_rejeita_rotulo_invalido(db: AsyncSession, rotulo: str):
    """
    Raiz do BUG-01: só `caminho_indice_da_edicao` validava, tarde demais — uma
    edição com rótulo inválido conseguia ser criada e persistida.
    """
    with pytest.raises(service.RotuloInvalidoError):
        await service.obter_ou_criar_edicao(db, rotulo)


@pytest.mark.asyncio
async def test_edicao_com_rotulo_invalido_nao_derruba_api_status(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """
    Uma edição com rótulo inválido só existe hoje se tiver sido gravada antes
    desta validação, ou por acesso direto ao ORM (simulado aqui). `/api/status`
    resolve o índice da vigente e precisa cair no legado, não estourar 500.
    """
    from app.modules.publicacoes.models import ManualEdicao

    db.add(ManualEdicao(rotulo="2024/R1", status=StatusEdicao.VIGENTE))
    await db.flush()

    resposta = await client_autenticado.get("/publicacoes/api/status")
    assert resposta.status_code == 200


@pytest.mark.asyncio
async def test_ativar_edicao_com_rotulo_invalido_retorna_409_nao_500(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """
    `_indice_existe` já devolve False para rótulo inválido, entrando no ramo
    que monta a mensagem de 409 com `caminho_indice_da_edicao` — sem proteção
    ali, o 409 informativo vira 500.
    """
    from app.modules.publicacoes.models import ManualEdicao

    orfa = ManualEdicao(rotulo="2024/R1", status=StatusEdicao.AGUARDANDO_ATIVACAO)
    db.add(orfa)
    await db.flush()

    resposta = await client_autenticado.post(f"{URL}/{orfa.id}/ativar")
    assert resposta.status_code == 409


# --------------------------------------------------------------------------
# Arquivar
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arquivar_edicao_anterior(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    vigente, nova = duas_edicoes
    await client_autenticado.post(f"{URL}/{nova.id}/ativar")

    resposta = await client_autenticado.post(f"{URL}/{vigente.id}/arquivar")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ARQUIVADA"


@pytest.mark.asyncio
async def test_arquivar_a_vigente_retorna_409(
    client_autenticado: AsyncClient, duas_edicoes
):
    """Arquivar a edição em vigor deixaria o acervo sem vigente nenhuma."""
    vigente, _ = duas_edicoes
    resposta = await client_autenticado.post(f"{URL}/{vigente.id}/arquivar")
    assert resposta.status_code == 409


@pytest.mark.asyncio
async def test_ativar_nao_arquiva_a_anterior_automaticamente(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    """
    Descartar artefatos de disco é decisão humana explícita, nunca efeito
    colateral de publicar outra coisa — daí `arquivar` ser endpoint separado.
    """
    vigente, nova = duas_edicoes
    await client_autenticado.post(f"{URL}/{nova.id}/ativar")

    await db.refresh(vigente)
    assert vigente.status == StatusEdicao.ANTERIOR


# --------------------------------------------------------------------------
# Excluir (hard delete — fase de implementação: arquivar não basta para
# tirar uma edição enviada errada do caminho, ver docstring de
# `service.excluir_edicao`)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluir_edicao_apaga_a_linha(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes
):
    from app.modules.publicacoes.models import ManualEdicao

    _, nova = duas_edicoes
    edicao_id = nova.id

    resposta = await client_autenticado.delete(f"{URL}/{edicao_id}")
    assert resposta.status_code == 204
    assert await db.get(ManualEdicao, edicao_id) is None


@pytest.mark.asyncio
async def test_excluir_edicao_vigente_nao_e_bloqueada(
    client_autenticado: AsyncClient, duas_edicoes
):
    """Sem restrição de status, de propósito — cobre o caso de ativação errada."""
    vigente, _ = duas_edicoes
    resposta = await client_autenticado.delete(f"{URL}/{vigente.id}")
    assert resposta.status_code == 204


@pytest.mark.asyncio
async def test_excluir_edicao_apaga_auditoria_de_acesso_associada(
    client_autenticado: AsyncClient, db: AsyncSession, duas_edicoes, usuario_no_banco
):
    """
    `publicacoes_acessos.edicao_id` é RESTRICT — sem apagar essas linhas
    primeiro, o DELETE estouraria IntegrityError. A auditoria daquela edição
    é o preço consciente desta fase (docstring de `service.excluir_edicao`).
    """
    from sqlalchemy import func, select

    from app.modules.publicacoes.models import PublicacaoAcesso

    _, nova = duas_edicoes
    db.add(
        PublicacaoAcesso(
            usuario_id=usuario_no_banco.id,
            documento_id=None,
            documento_titulo="Doc de teste",
            edicao_id=nova.id,
        )
    )
    await db.flush()

    resposta = await client_autenticado.delete(f"{URL}/{nova.id}")
    assert resposta.status_code == 204

    restantes = (
        await db.execute(
            select(func.count(PublicacaoAcesso.id)).where(
                PublicacaoAcesso.edicao_id == nova.id
            )
        )
    ).scalar_one()
    assert restantes == 0


@pytest.mark.asyncio
async def test_excluir_edicao_remove_o_indice_de_busca_do_disco(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    edicao = await service.obter_ou_criar_edicao(
        db, "com-indice-del", status=StatusEdicao.ANTERIOR
    )
    caminho = criar_indice(indices, "com-indice-del")
    await db.flush()
    assert caminho.is_file()

    resposta = await client_autenticado.delete(f"{URL}/{edicao.id}")
    assert resposta.status_code == 204
    assert not caminho.is_file()


@pytest.mark.asyncio
async def test_excluir_edicao_inexistente_retorna_404(
    client_autenticado: AsyncClient, indices: Path
):
    resposta = await client_autenticado.delete(f"{URL}/{uuid.uuid4()}")
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_encarregado_nao_exclui_edicao(
    client: AsyncClient,
    db: AsyncSession,
    usuario_encarregado_e_token: dict,
    indices: Path,
):
    edicao = await service.obter_ou_criar_edicao(
        db, "alvo-excluir", status=StatusEdicao.ANTERIOR
    )
    criar_indice(indices, "alvo-excluir")
    await db.flush()

    resposta = await client.delete(
        f"{URL}/{edicao.id}", headers=usuario_encarregado_e_token["headers"]
    )
    assert resposta.status_code == 403


# --------------------------------------------------------------------------
# Relatório de diff
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relatorio_devolve_o_markdown_gravado(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    edicao = await service.obter_ou_criar_edicao(db, "com-rel", status=StatusEdicao.VIGENTE)
    edicao.relatorio_diff = "# Relatório\n\n- novos: 12"
    await db.flush()

    corpo = (await client_autenticado.get(f"{URL}/{edicao.id}/relatorio")).json()
    assert corpo["rotulo"] == "com-rel"
    assert "novos: 12" in corpo["relatorio"]


@pytest.mark.asyncio
async def test_relatorio_ausente_e_200_com_nulo_nao_404(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    """A edição existe; só não veio de `publicar.py`. É o caso do `piloto-fim`."""
    edicao = await service.obter_ou_criar_edicao(db, "sem-rel", status=StatusEdicao.VIGENTE)
    await db.flush()

    resposta = await client_autenticado.get(f"{URL}/{edicao.id}/relatorio")
    assert resposta.status_code == 200
    assert resposta.json()["relatorio"] is None


# --------------------------------------------------------------------------
# Duplicação por hash (endpoint que faltava para a medição do M4 tarefa 5)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicacao_sem_anterior_devolve_zeros(
    client_autenticado: AsyncClient, db: AsyncSession, indices: Path
):
    await service.obter_ou_criar_edicao(db, "so-uma", status=StatusEdicao.VIGENTE)
    await db.flush()

    corpo = (await client_autenticado.get("/publicacoes/api/duplicacao")).json()
    assert corpo["vigente"] == "so-uma"
    assert corpo["anterior"] is None
    assert corpo["duplicados_por_hash"] == 0
    assert corpo["bytes_potencialmente_economizaveis"] is None


# --------------------------------------------------------------------------
# Card em /configuracoes (Fase 2) — fumaça
#
# Sem verificação visual em navegador nesta sessão (ver dívidas do
# 08_status_de_implementacao.md). O que dá para afirmar por teste é o que
# quebraria de forma silenciosa: um id renomeado no template deixa o listener
# do JS sem alvo, e o botão simplesmente não faz nada — sem erro em lugar
# nenhum. Estes testes amarram template e JS pelos ids.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_configuracoes_traz_o_card_de_publicacoes(client_autenticado: AsyncClient):
    resposta = await client_autenticado.get("/configuracoes")
    assert resposta.status_code == 200
    html = resposta.text

    assert 'id="btn-gerenciar-edicoes"' in html
    assert 'id="btn-status-acervo"' in html
    assert 'id="btn-ir-avulsas"' in html
    assert "configuracoes_publicacoes.js" in html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "elemento_id",
    [
        "modal-edicoes",
        "lista-edicoes-body",
        "aviso-retencao-edicoes",
        "modal-relatorio-edicao",
        "conteudo-relatorio-edicao",
        "modal-status-acervo",
        "grid-status-acervo",
    ],
)
async def test_configuracoes_tem_os_alvos_que_o_js_procura(
    client_autenticado: AsyncClient, elemento_id: str
):
    html = (await client_autenticado.get("/configuracoes")).text
    assert f'id="{elemento_id}"' in html


# --------------------------------------------------------------------------
# RBAC — D-S6: gerir edição é privilégio de Admin
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "caminho",
    ["", "/{id}/ativar", "/{id}/arquivar", "/{id}/relatorio"],
)
async def test_encarregado_nao_gerencia_edicoes(
    client: AsyncClient,
    db: AsyncSession,
    usuario_encarregado_e_token: dict,
    indices: Path,
    caminho: str,
):
    """
    Setup via `service` direto, não via `client_autenticado`: aquele
    fixture sobrescreve `get_current_user` e passa a ignorar o header de
    Authorization pelo resto do teste (mesma armadilha de
    `test_publicacoes_avulsas.py::_inserir_avulsa_direto`).
    """
    edicao = await service.obter_ou_criar_edicao(db, "alvo", status=StatusEdicao.ANTERIOR)
    criar_indice(indices, "alvo")
    await db.flush()

    url = f"{URL}{caminho.format(id=edicao.id)}"
    headers = usuario_encarregado_e_token["headers"]
    resposta = (
        await client.get(url, headers=headers)
        if caminho in ("", "/{id}/relatorio")
        else await client.post(url, headers=headers)
    )
    assert resposta.status_code == 403
