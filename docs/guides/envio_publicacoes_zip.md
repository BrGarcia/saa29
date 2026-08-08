# Guia — Envio de Publicações (.zip) e Processamento do Acervo

> Este documento detalha por que **não existe um botão de upload de arquivos ZIP na interface Web** (menu `/configuracoes`) e explica a arquitetura e os procedimentos corretos para o envio e atualização do acervo de publicações no SAA29.

---

## 1. Por que não há botão de upload `.zip` na tela `/configuracoes`?

A ausência de um botão para carregar arquivos `.zip` ou pastas completas pelo navegador no menu de configurações é uma **decisão de arquitetura e segurança deliberada**. 

Conforme registrado na **seção 5.11** do documento [opus_plano_de_incorporacao.md](file:///c:/Users/brgar/Projetos/SAA29/docs/backlog/modulo_publicacoes/opus_plano_de_incorporacao.md#L610-L637), o envio de acervos de manuais ou arquivos comprimidos `.zip` (que costumam ter centenas de MBs ou múltiplos GBs) via protocolo HTTP no navegador inviabilizaria o sistema devido a 4 limites técnicos:

| # | Limite / Vulnerabilidade | Consequência |
|---|---|---|
| 1 | **Estouro de Memória (OOM Kill)** | O aplicativo lê arquivos de upload materializando o conteúdo completo em memória RAM (`bytes`). Em arquivos grandes (ex: 3 GB), o processo sofre *Out Of Memory* kill pelo sistema operacional na VPS. |
| 2 | **Timeout de Requisição HTTP** | Servidores de aplicação (como Gunicorn) possuem timeout de requisição estipulado (ex: 30s). Uploads volumosos via navegador são abortados antes da conclusão. |
| 3 | **Riscos de Segurança (Zip-Slip & Zip Bomb)** | Liberar extração de pacotes `.zip` via web expõe o servidor a ataques como *Zip-Slip* (arquivos maliciosos com `../` que escapam do diretório e sobrescrevem arquivos do sistema) e *Zip Bombs* (arquivos altamente comprimidos que travam o disco). |
| 4 | **Restrição de Allowlist** | Arquivos `.zip` e `.doc` foram propositalmente mantidos fora da allowlist de extensões permitidas para upload via web (`file_validators.py`). |

---

## 2. Como é realizado o envio e publicação das edições?

O envio e a geração de snapshots comprimidos `.zip` são realizados **via linha de comando (CLI)** utilizando a Estação de Publicação / scripts de automação.

### Passo 1: Processamento da publicação (Estação de Publicação)
Na máquina de desenvolvimento/operação onde o acervo original está localizado:

```bash
python -m scripts.publicacoes.publicar --edicao 2027
```

**O que o script `publicar.py` faz:**
1. Realiza o inventário, extração de texto e cálculo de diff por hash SHA-256 entre as edições.
2. Gera localmente o snapshot comprimido `.zip` da edição.
3. Envia o snapshot `.zip` e deltas de PDFs diretamente para o storage em nuvem (**Cloudflare R2**), **sem passar pelo tráfego HTTP do servidor web**.
4. Cria a edição no banco de dados com status `AGUARDANDO_ATIVACAO` e gera o relatório `relatorio_publicacao_<edicao>.md`.

### Passo 2: Transferência de arquivos para a VPS (se necessário)
Caso seja necessário sincronizar os arquivos do acervo com o disco da VPS de produção, utiliza-se transferência segura de infraestrutura via SSH (`rsync`), nunca HTTP:

```bash
rsync -avz --checksum \
    var/publicacoes/acervo/ \
    deploy@<host-da-vps>:/srv/saa29/var/publicacoes/acervo/
```

---

## 3. Qual a função do menu `/configuracoes` (Card de Publicações)?

A interface Web em `/configuracoes` serve exclusivamente para a **gestão e ativação/reversão atômica** de edições previamente processadas:

1. O administrador acessa a tela e visualiza o Card **"Publicações"**.
2. Verifica as edições cadastradas no banco (ex: `Edição 2027 · aguardando ativação`) e o relatório de diffs.
3. Clica no botão **`[ ATIVAR ]`** ou **`[ REVERTER ]`**.
4. A ativação faz apenas a troca do ponteiro (`manuais_edicoes.status`) no banco de dados. A troca é **instantânea, atômica e reversível**, sem envolver upload ou movimentação de arquivos via browser.

---

## 4. Referências

- [opcoes_upload_inspetor.md](file:///c:/Users/brgar/Projetos/SAA29/docs/guides/opcoes_upload_inspetor.md) — Guia completo com as opções de upload autônomo na Web para a role INSPETOR.
- [operacao_publicacoes.md](file:///c:/Users/brgar/Projetos/SAA29/docs/guides/operacao_publicacoes.md) — Runbook operacional completo do módulo de publicações.
- [opus_plano_de_incorporacao.md](file:///c:/Users/brgar/Projetos/SAA29/docs/backlog/modulo_publicacoes/opus_plano_de_incorporacao.md) — Parecer arquitetural e análise de limites de upload (§5.11 e §8.3).
- [08_status_de_implementacao.md](file:///c:/Users/brgar/Projetos/SAA29/docs/backlog/modulo_publicacoes/08_status_de_implementacao.md) — Status de implementação das tarefas M4.

