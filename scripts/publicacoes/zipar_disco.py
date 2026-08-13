"""
Compacta um disco/pasta inteira (ex.: um CD/DVD/pendrive de manuais) em um
único arquivo .zip pronto para envio pela tela /configuracoes do SAA29.

Uso:
    python scripts/publicacoes/zipar_disco.py <pasta_ou_disco> [destino.zip]

Sem argumentos, o script pergunta interativamente — pensado para ser
executado por duplo-clique via zipar_disco.bat por quem não usa terminal.

Só usa a biblioteca padrão do Python (nenhuma dependência externa), então
roda em qualquer máquina com Python instalado, sem precisar do ambiente
virtual do projeto.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# Nomes de pastas/arquivos de sistema que não fazem sentido num acervo de
# manuais e só inflam o zip (Windows/macOS os recriam sozinhos).
IGNORAR_NOMES = {
    "system volume information",
    "$recycle.bin",
    "thumbs.db",
    ".ds_store",
    "desktop.ini",
}


def _deve_ignorar(caminho: Path) -> bool:
    return caminho.name.lower() in IGNORAR_NOMES


def _caminho_longo(caminho: Path) -> Path:
    """No Windows, prefixa \\\\?\\ para suportar caminhos > 260 caracteres."""
    if sys.platform == "win32":
        resolvido = str(caminho.resolve())
        if not resolvido.startswith("\\\\?\\"):
            return Path("\\\\?\\" + resolvido)
    return caminho


def listar_arquivos(origem: Path) -> list[Path]:
    arquivos: list[Path] = []
    for item in origem.rglob("*"):
        if _deve_ignorar(item):
            continue
        if any(_deve_ignorar(pai) for pai in item.relative_to(origem).parents):
            continue
        if item.is_file():
            arquivos.append(item)
    return arquivos


def formatar_tamanho(num_bytes: float) -> str:
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unidade}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def zipar_disco(origem: Path, destino: Path) -> None:
    if not origem.is_dir():
        raise SystemExit(f"Pasta/disco de origem não encontrado: {origem}")

    destino.parent.mkdir(parents=True, exist_ok=True)

    print(f"Listando arquivos em {origem} ...")
    arquivos = listar_arquivos(origem)
    total = len(arquivos)
    if total == 0:
        raise SystemExit("Nenhum arquivo encontrado na origem informada.")

    tamanho_total = sum(a.stat().st_size for a in arquivos)
    print(f"{total} arquivo(s) encontrados, {formatar_tamanho(tamanho_total)} no total.")
    print(f"Gravando {destino} ...")

    processados = 0
    ultimo_pct = -1
    with zipfile.ZipFile(_caminho_longo(destino), "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in arquivos:
            nome_no_zip = str(arquivo.relative_to(origem))
            try:
                zf.write(_caminho_longo(arquivo), nome_no_zip)
            except OSError as exc:
                print(f"  [aviso] pulei {nome_no_zip!r}: {exc}")
            processados += 1
            pct = int(processados / total * 100)
            if pct != ultimo_pct:
                print(f"  {pct}% ({processados}/{total})", end="\r")
                ultimo_pct = pct

    print()
    tamanho_zip = destino.stat().st_size
    print(f"Concluído: {destino} ({formatar_tamanho(tamanho_zip)}).")
    print("Agora envie esse arquivo pela tela Configurações > Publicações do SAA29.")


def _perguntar(mensagem: str, padrao: str = "") -> str:
    sufixo = f" [{padrao}]" if padrao else ""
    resposta = input(f"{mensagem}{sufixo}: ").strip().strip('"')
    return resposta or padrao


def main(argv: list[str]) -> int:
    if len(argv) >= 1:
        origem = Path(argv[0]).expanduser()
    else:
        origem = Path(_perguntar("Pasta ou letra do disco a compactar (ex.: D:\\ ou C:\\Manuais)"))

    if len(argv) >= 2:
        destino = Path(argv[1]).expanduser()
    else:
        sugestao = str(Path.home() / "Desktop" / f"{origem.name or 'disco'}.zip")
        destino = Path(_perguntar("Arquivo .zip de saída", sugestao))

    zipar_disco(origem, destino)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nCancelado.")
        raise SystemExit(1)
