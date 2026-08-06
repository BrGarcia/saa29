"""
tests/unit/test_publicacoes_indice_edicao.py
Resolução do índice de busca por edição — Fase 0 de `09_plano_configuracoes.md`.

O que estas funções resolvem: até aqui a aplicação abria UM arquivo fixo
(`publicacoes_index_path`), sobrescrito a cada indexação. Cada edição passa a
ter o seu `catalog.<rotulo>.db`, e a edição VIGENTE no banco é que decide qual
deles a busca abre — sem mover arquivo, sem janela em que banco e disco
discordem (ADR-004, "Resolução do índice por edição").

O teste que realmente prova que isso funciona é de integração e vive em
`tests/integration/test_publicacoes_busca.py`
(`test_trocar_edicao_vigente_muda_o_que_a_busca_devolve`): aqui ficam as regras
de composição e de queda para o índice legado.
"""

from pathlib import Path

import pytest

from app.modules.publicacoes import service


@pytest.fixture
def base(tmp_path: Path, monkeypatch) -> Path:
    """Diretório-base dos índices, isolado do `var/` da máquina."""

    class _SettingsFake:
        publicacoes_index_path = str(tmp_path / "catalog.db")

    monkeypatch.setattr(service, "get_settings", lambda: _SettingsFake())
    return tmp_path


# --------------------------------------------------------------------------
# Composição do nome
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rotulo", ["2026", "piloto-fim", "teste_1", "v1.2"])
def test_rotulo_valido_vira_arquivo_ao_lado_do_indice_legado(base: Path, rotulo: str):
    caminho = service.caminho_indice_da_edicao(rotulo)
    assert caminho == base / f"catalog.{rotulo}.db"
    assert caminho.parent == base


def test_edicoes_diferentes_dao_arquivos_diferentes(base: Path):
    """
    É a propriedade inteira da Fase 0: publicar 2027 não pode escrever no
    arquivo que a busca da edição 2026 está lendo.
    """
    assert service.caminho_indice_da_edicao("2026") != service.caminho_indice_da_edicao("2027")


@pytest.mark.parametrize(
    "rotulo",
    [
        "../evil",       # separador POSIX
        "..\\evil",      # separador Windows
        "a/b",
        "",
        "x" * 21,        # acima do String(20) da coluna
        "com espaço",
        "acentuação",
    ],
)
def test_rotulo_perigoso_ou_fora_do_formato_e_recusado(base: Path, rotulo: str):
    """
    `rotulo` é texto livre de 20 caracteres gravado por script offline. Um
    rótulo com separador não pode virar leitura de arquivo arbitrário — mesma
    postura defensiva de `_resolver_pdf` no router.
    """
    with pytest.raises(service.RotuloInvalidoError):
        service.caminho_indice_da_edicao(rotulo)


# --------------------------------------------------------------------------
# Resolução com queda para o índice legado
# --------------------------------------------------------------------------


def test_prefere_o_indice_da_edicao_quando_ele_existe(base: Path):
    por_edicao = base / "catalog.2026.db"
    por_edicao.write_bytes(b"")
    (base / "catalog.db").write_bytes(b"")  # legado presente, deve ser ignorado

    assert service.resolver_caminho_indice("2026") == por_edicao


def test_cai_para_o_legado_quando_a_edicao_ainda_nao_foi_reindexada(base: Path):
    """
    Instalação indexada ANTES desta mudança: só tem `catalog.db`. Sem a queda,
    atualizar o código faria a busca devolver zero resultados em silêncio — o
    sintoma enganoso que `_abrir_catalog_ro` existe para evitar.
    """
    legado = base / "catalog.db"
    legado.write_bytes(b"")

    assert service.resolver_caminho_indice("2026") == legado


def test_sem_nenhum_arquivo_devolve_o_caminho_por_edicao(base: Path):
    """
    Nenhum dos dois existe: o caminho devolvido é o acionável — o arquivo que a
    reindexação vai criar, e o nome que aparece no `IndiceIndisponivelError`.
    """
    assert service.resolver_caminho_indice("2026") == base / "catalog.2026.db"


def test_sem_edicao_vigente_usa_o_caminho_legado(base: Path):
    """Acervo nunca indexado: não há rótulo para compor nome nenhum."""
    assert service.resolver_caminho_indice(None) == base / "catalog.db"
