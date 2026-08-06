"""
tests/unit/test_publicacoes_merge_data.py
Merge de remessa nova no acervo existente (RN-08, M4 tarefa 3).

Tudo em `tmp_path` — sem banco, sem rede. `merge_data.py` só manipula
arquivos em disco.
"""

import os
import time
from pathlib import Path

import pytest

from scripts.publicacoes import merge_data


@pytest.fixture
def acervo(tmp_path: Path) -> Path:
    raiz = tmp_path / "acervo"
    (raiz / "MANUAL_A").mkdir(parents=True)
    (raiz / "MANUAL_A" / "DOC1.PDF").write_bytes(b"%PDF-1.4 versao antiga do doc1")
    (raiz / "MANUAL_A" / "DOC2.PDF").write_bytes(b"%PDF-1.4 doc2 inalterado")
    return raiz


@pytest.fixture
def remessa(tmp_path: Path) -> Path:
    raiz = tmp_path / "remessa"
    (raiz / "MANUAL_A").mkdir(parents=True)
    (raiz / "MANUAL_B").mkdir(parents=True)
    return raiz


def _tocar_mtime_futuro(caminho: Path) -> None:
    """Garante um mtime estritamente mais novo, robusto à resolução do FS."""
    futuro = time.time() + 5
    os.utime(caminho, (futuro, futuro))


# --------------------------------------------------------------------------
# Planejamento (puro, sem tocar disco além de ler)
# --------------------------------------------------------------------------


def test_arquivo_so_na_remessa_e_novo(acervo: Path, remessa: Path):
    (remessa / "MANUAL_B" / "DOC3.PDF").write_bytes(b"%PDF-1.4 doc3")

    resultado = merge_data.planejar_merge(acervo, remessa)

    assert resultado.novos == ["MANUAL_B/DOC3.PDF"]
    assert resultado.conflitos == []


def test_mesmo_hash_e_identico_sem_conflito(acervo: Path, remessa: Path):
    (remessa / "MANUAL_A" / "DOC2.PDF").write_bytes(b"%PDF-1.4 doc2 inalterado")

    resultado = merge_data.planejar_merge(acervo, remessa)

    assert "MANUAL_A/DOC2.PDF" in resultado.identicos
    assert resultado.conflitos == []
    assert resultado.novos == []


def test_hash_diferente_remessa_mais_nova_vence(acervo: Path, remessa: Path):
    arquivo_remessa = remessa / "MANUAL_A" / "DOC1.PDF"
    arquivo_remessa.write_bytes(b"%PDF-1.4 versao NOVA do doc1")
    _tocar_mtime_futuro(arquivo_remessa)

    resultado = merge_data.planejar_merge(acervo, remessa)

    assert len(resultado.conflitos) == 1
    caminho, motivo, preterido = resultado.conflitos[0]
    assert caminho == "MANUAL_A/DOC1.PDF"
    assert preterido == "origem"
    assert "remessa mais recente" in motivo


def test_hash_diferente_acervo_mais_novo_remessa_descartada(acervo: Path, remessa: Path):
    arquivo_acervo = acervo / "MANUAL_A" / "DOC1.PDF"
    _tocar_mtime_futuro(arquivo_acervo)
    (remessa / "MANUAL_A" / "DOC1.PDF").write_bytes(b"%PDF-1.4 versao antiga trazida de novo")

    resultado = merge_data.planejar_merge(acervo, remessa)

    caminho, motivo, preterido = resultado.conflitos[0]
    assert preterido == "remessa"
    assert "acervo mais recente" in motivo


def test_arquivo_so_no_acervo_nao_aparece_no_plano(acervo: Path, remessa: Path):
    """A remessa é incremento, não espelho — o que só existe no acervo não é tocado."""
    resultado = merge_data.planejar_merge(acervo, remessa)
    todos_mencionados = set(resultado.novos) | {c for c, _, _ in resultado.conflitos} | set(resultado.identicos)
    # DOC2.PDF existe só no acervo (não está na remessa vazia) — não deve
    # aparecer em nenhuma categoria do plano, porque o merge nunca olha para
    # arquivos que a remessa não trouxe.
    assert "MANUAL_A/DOC2.PDF" not in todos_mencionados


# --------------------------------------------------------------------------
# Nada é descartado silenciosamente — o preterido vai para _merge_conflicts/
# --------------------------------------------------------------------------


def test_aplicar_merge_copia_novos(acervo: Path, remessa: Path):
    (remessa / "MANUAL_B" / "DOC3.PDF").write_bytes(b"%PDF-1.4 doc3")
    resultado = merge_data.planejar_merge(acervo, remessa)

    merge_data.aplicar_merge(acervo, remessa, resultado)

    assert (acervo / "MANUAL_B" / "DOC3.PDF").is_file()
    assert (acervo / "MANUAL_B" / "DOC3.PDF").read_bytes() == b"%PDF-1.4 doc3"


def test_aplicar_merge_conflito_preserva_o_preterido(acervo: Path, remessa: Path):
    arquivo_remessa = remessa / "MANUAL_A" / "DOC1.PDF"
    arquivo_remessa.write_bytes(b"%PDF-1.4 versao NOVA do doc1")
    _tocar_mtime_futuro(arquivo_remessa)
    conteudo_antigo = (acervo / "MANUAL_A" / "DOC1.PDF").read_bytes()

    resultado = merge_data.planejar_merge(acervo, remessa)
    merge_data.aplicar_merge(acervo, remessa, resultado)

    # O acervo passa a ter a versão nova...
    assert (acervo / "MANUAL_A" / "DOC1.PDF").read_bytes() == b"%PDF-1.4 versao NOVA do doc1"
    # ...mas a antiga não foi descartada, está em _merge_conflicts/.
    preterido = acervo / "_merge_conflicts" / "MANUAL_A" / "DOC1.PDF"
    assert preterido.is_file()
    assert preterido.read_bytes() == conteudo_antigo


def test_aplicar_merge_quando_remessa_perde_nao_altera_acervo(acervo: Path, remessa: Path):
    arquivo_acervo = acervo / "MANUAL_A" / "DOC1.PDF"
    _tocar_mtime_futuro(arquivo_acervo)
    conteudo_acervo = arquivo_acervo.read_bytes()
    (remessa / "MANUAL_A" / "DOC1.PDF").write_bytes(b"%PDF-1.4 versao que vai perder")

    resultado = merge_data.planejar_merge(acervo, remessa)
    merge_data.aplicar_merge(acervo, remessa, resultado)

    assert arquivo_acervo.read_bytes() == conteudo_acervo
    # A versão preterida da remessa também fica registrada, para auditoria.
    assert (acervo / "_merge_conflicts" / "MANUAL_A" / "DOC1.PDF").is_file()


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def test_relatorio_contem_contagens_e_conflitos(acervo: Path, remessa: Path):
    arquivo_remessa = remessa / "MANUAL_A" / "DOC1.PDF"
    arquivo_remessa.write_bytes(b"%PDF-1.4 nova versao")
    _tocar_mtime_futuro(arquivo_remessa)
    (remessa / "MANUAL_B" / "DOC3.PDF").write_bytes(b"%PDF-1.4 novo")

    resultado = merge_data.planejar_merge(acervo, remessa)
    relatorio = merge_data.gerar_relatorio(resultado, origem=acervo, remessa=remessa)

    assert "Novos: 1" in relatorio
    assert "Conflitos resolvidos: 1" in relatorio
    assert "MANUAL_A/DOC1.PDF" in relatorio
    assert "MANUAL_B/DOC3.PDF" in relatorio


# --------------------------------------------------------------------------
# CLI: --dry-run é o padrão seguro
# --------------------------------------------------------------------------


def test_dry_run_e_o_padrao_nao_copia_nada(acervo: Path, remessa: Path):
    (remessa / "MANUAL_B" / "DOC3.PDF").write_bytes(b"%PDF-1.4 doc3")

    codigo = merge_data.main(["--origem", str(acervo), "--remessa", str(remessa)])

    assert codigo == 0
    assert not (acervo / "MANUAL_B" / "DOC3.PDF").exists()
    assert (acervo / "merge_report.txt").is_file()


def test_executar_aplica_de_verdade(acervo: Path, remessa: Path):
    (remessa / "MANUAL_B" / "DOC3.PDF").write_bytes(b"%PDF-1.4 doc3")

    codigo = merge_data.main([
        "--origem", str(acervo), "--remessa", str(remessa), "--executar",
    ])

    assert codigo == 0
    assert (acervo / "MANUAL_B" / "DOC3.PDF").is_file()


def test_origem_inexistente_retorna_erro(tmp_path: Path, remessa: Path):
    codigo = merge_data.main([
        "--origem", str(tmp_path / "nao_existe"), "--remessa", str(remessa),
    ])
    assert codigo == 1


def test_remessa_inexistente_retorna_erro(acervo: Path, tmp_path: Path):
    codigo = merge_data.main([
        "--origem", str(acervo), "--remessa", str(tmp_path / "nao_existe"),
    ])
    assert codigo == 1
