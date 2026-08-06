"""
scripts/publicacoes/__init__.py
Pacote dos scripts OFFLINE do módulo de publicações.

Existe porque os scripts daqui importam de `app.*` e rodam como módulo
(`python -m scripts.publicacoes.indexar`) — mesmo precedente de
`scripts/seed/__init__.py`. Sem este arquivo, o `-m` não resolve o pacote.

Nada aqui roda dentro do servidor: são processos de uso único, executados na
estação de publicação ou na máquina de desenvolvimento.
"""
