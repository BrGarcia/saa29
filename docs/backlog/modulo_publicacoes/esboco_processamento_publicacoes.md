# Esboço Arquitetural — Processamento Offline Local e Publicação no Cloudflare

> **Data:** 2026-08-11  
> **Status:** Proposta de Arquitetura / Estratégia Temporária ou Alternativa  
> **Referência:** [`11_achados_disco_completo.md`](11_achados_disco_completo.md) e [`12_refinamento_gestao_e_envio.md`](12_refinamento_gestao_e_envio.md)

---

## 1. Visão Geral e Motivação

O envio de acervos pesados (os dois discos do `DISCO_COMPLETO`, somando ~3,1 GB extraídos e 18.746 PDFs) através do fluxo Web via HTTP multipart enfrenta limitações operacionais e técnicas no servidor de produção (VPS), tais como:

1. **Uso de RAM/CPU na VPS:** A extração de texto OCR/FTS de 18.746 PDFs com `pypdfium2` é intensiva em CPU e memória, podendo estourar os limites da VPS (ex: 2 GB RAM / 1 vCPU) ou causar *Out-Of-Memory (OOM)*.
2. **Defeitos do Pipeline de Upload HTTP (B-01 a B-06):** Instabilidades de rede ao enviar pacotes gigantes de 2 GB, limites de parsing no `zipfile` e timeouts.

### A Solução "Offline First" (Processamento Local + Cloudflare R2)

A proposta consiste em **transferir a pesada fase de ingestão, normalização, merge e indexação FTS5 para a máquina do operador (computador local)**. 

Após o processamento local, a máquina do operador envia apenas os artefatos prontos:
1. **PDFs consolidados** → enviados diretamente para o **Cloudflare R2 Storage**.
2. **Índice de Busca (`catalog.<rotulo>.db`)** → enviado ao Cloudflare R2 e/ou sincronizado no servidor.
3. **Metadados da Edição** → sincronizados no banco de dados relacional (PostgreSQL/SQLite) do SAA29 via API ou script CLI.

---

## 2. Diagrama Arquitetural

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MÁQUINA LOCAL (OPERADOR)                         │
│                                                                         │
│  ┌────────────────────┐    ┌────────────────────┐                       │
│  │ Disco Manutenção   │    │ Disco Operacional  │                       │
│  │ (Program/)         │    │ (Program_Op/)      │                       │
│  └─────────┬──────────┘    └─────────┬──────────┘                       │
│            │                         │                                  │
│            └────────────┬────────────┘                                  │
│                         ▼                                               │
│    ┌─────────────────────────────────────────┐                          │
│    │  Script Local: processar_offline.py     │                          │
│    │  - Normalização & Allowlist             │                          │
│    │  - Ignora Data-ALX                      │                          │
│    │  - Merge por versão (version/*.txt)     │                          │
│    │  - Extração FTS5 (pypdfium2)            │                          │
│    └────────────────────┬────────────────────┘                          │
│                         │                                               │
│             ┌───────────┴───────────┐                                   │
│             ▼                       ▼                                   │
│     PDFs Consolidados      catalog.<rotulo>.db                          │
└─────────────┬───────────────────────┬───────────────────────────────────┘
              │                       │
              │ (boto3 / R2 SDK)      │ (Download no Servidor / R2)
              ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLOUDFLARE SERVICES                            │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Cloudflare R2 Bucket (saa29-publicacoes)                          │  │
│  │ - /acervo/<edicao>/<manual>/<pdf>                                 │  │
│  │ - /indices/catalog.<rotulo>.db                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  │ Direct Stream / Download
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SAA29 (APLICAÇÃO WEB / VPS)                      │
│                                                                         │
│  ┌───────────────────────────────┐     ┌─────────────────────────────┐  │
│  │ Banco Principal (Relacional)  │     │ Search Engine (search.py)   │  │
│  │ Sincronizado via POST API     │     │ Lé catalog.<rotulo>.db      │  │
│  │ (Manuais, Capítulos, Docs)    │     │ direto de var/publicacoes/  │  │
│  └───────────────────────────────┘     └─────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Viewer PDF: Serve PDFs gerando presigned URLs / Proxy para R2    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Etapas do Processamento Offline Local

### Passo 1: Ingestão e Mesclagem Local (`scripts/publicacoes/processar_offline.py`)

O script roda no computador do operador e executa o seguinte pipeline:

1. **Descoberta e Allowlist:**
   - Varre as pastas cruas (`Program/` e `Program_Operational/`).
   - Exclui a pasta aninhada `Data-ALX/` (que duplicaria 5.724 PDFs de acordo com o achado §3 do doc 12).
   - Extrai e copia **apenas** arquivos permitidos (Allowlist: `.pdf`, `.fnm`, `.fdx`, `.fdt`, `.xml`, `.ini`, `.txt`, `.lst`), ignorando `.exe`, `.dll` e instaladores.

2. **Resolução de Nomes e Categorias:**
   - Parseia `manual_details.xml` para obter descrições amigáveis em PT-BR (`custom-description`) e mapear apelidos (ex: `BO_314PT_0000` → `BO_314PT`).
   - Parseia `manual_type.xml` + `collections.ini` para inferir categorias dos manuais que não estão em `categorias_manuais.toml`.

3. **Merge por Revisão:**
   - Parseia `version/<CODIGO>.txt` de ambos os discos.
   - Aplica a cascata de desempate definida no doc 12 (§6):
     1. Maior `Rev.` numérico vence.
     2. Empate → `Date:` mais recente (formato MM/DD/YYYY) vence.
     3. Ausência de `version/` → Disco de manutenção vence sobre o operacional.

4. **Geração do Índice de Busca FTS5 (`catalog.<rotulo>.db`):**
   - Instancia a criação do banco SQLite FTS5 chamando as funções de [`scripts/publicacoes/indexar.py`](../../scripts/publicacoes/indexar.py).
   - Processa o texto de todas as páginas usando a CPU local do computador (rápido e sem comprometer a VPS).

5. **Geração da Árvore de Metadados JSON:**
   - Produz um manifesto estruturado `metadados_edicao.json` contendo a lista completa de manuais, capítulos, documentos, revisões e contadores para envio ao servidor.

---

### Passo 2: Upload dos Artefatos para o Cloudflare R2

O script local utiliza a SDK de S3/R2 (via `boto3` ou `wrangler`) com as credenciais de API do Cloudflare R2:

1. **Upload dos PDFs:**
   - Envia cada PDF para a chave no R2: `publicacoes/acervo/<rotulo_edicao>/<codigo_manual>/<pdf_file>`.
2. **Upload do Índice SQLite:**
   - Envia o arquivo `catalog.<rotulo_edicao>.db` para: `publicacoes/indices/catalog.<rotulo_edicao>.db`.

---

### Passo 3: Sincronização com o SAA29 em Produção

Com os arquivos estáticos já salvos no Cloudflare R2, o script local faz uma chamada HTTP autenticada à API do SAA29 (ou executa um comando CLI diretamente no servidor via SSH):

#### Opção A: Via API Admin no SAA29 (`POST /publicacoes/api/edicoes/sincronizar_offline`)
- O payload traz o manifesto `metadados_edicao.json`.
- O backend do SAA29:
  1. Cria/atualiza o registro da edição em `manuais_edicoes`.
  2. Executa `service.sincronizar_catalogo()` gravando os manuais, capítulos e documentos no PostgreSQL/SQLite principal.
  3. Baixa o arquivo `catalog.<rotulo_edicao>.db` do Cloudflare R2 para a pasta local `var/publicacoes/catalog.<rotulo_edicao>.db` (ou o serviço `search.py` lê do volume compartilhado).
  4. Marca a edição como `VIGENTE`.

#### Opção B: Via Script CLI no Servidor (SSH)
```bash
python -m scripts.publicacoes.sincronizar_offline \
  --manifesto metadados_edicao.json \
  --rotulo 2026.1 \
  --r2-sync
```

---

## 4. Alterações Técnicas Necessárias no Código do SAA29

Para suportar essa modalidade sem quebrar a arquitetura existente:

| Arquivo | Mudança Necessária |
|---|---|
| [`app/shared/core/storage.py`](../../app/shared/core/storage.py) | Garantir suporte à geração de presigned URLs para PDFs armazenados em subpastas de acervo no R2 (`storage_backend="r2"`). |
| [`app/modules/publicacoes/search.py`](../../app/modules/publicacoes/search.py) | Nenhuma alteração essencial — o módulo já abre `catalog.<rotulo>.db` por `sqlite3` direto do disco local `var/publicacoes/`. É necessário apenas que o arquivo `.db` esteja presente nesse diretório no VPS. |
| [`app/modules/publicacoes/service.py`](../../app/modules/publicacoes/service.py) | Adicionar/expor a função `sincronizar_manifesto_offline(db, manifesto_data)` para receber a árvore de metadados gerada no desktop. |
| [`scripts/publicacoes/processar_offline.py`](../../scripts/publicacoes/processar_offline.py) | **[NOVO]** Script CLI local contendo o fluxo de leitura dos CDs, merge, indexação FTS5 e envio para R2. |

---

## 5. Comparativo: Workflow Web vs Workflow Offline Local

| Aspecto | Pipeline Web (M4.Web) | Pipeline Offline (Local + Cloudflare) |
|---|---|---|
| **Onde roda a extração de PDFs** | Servidor / VPS | Computador Desktop do Operador |
| **Tempo de Indexação** | 45 min – 2h (limitado pela VPS) | 3 – 8 min (aproveita múltiplos núcleos locais) |
| **Consumo de RAM no Servidor** | Alto (Risco de crash OOM em VPS < 4GB) | Desprezível (Servidor só baixa o `.db` pronto) |
| **Transferência de Dados** | Upload de ZIPs de 2 GB via browser | Upload direto local → Cloudflare R2 |
| **Tolerância a Falhas de Rede** | Média (exige retry de partes no upload web) | Alta (Upload idempotente de PDFs via boto3/R2) |
| **Complexidade de Interface** | Requer UI complexa com progresso/polling | Terminal simples / CLI no computador local |

---

## 6. Plano de Ação Recomendado (Próximos Passos)

1. **Criar o Script Local `scripts/publicacoes/processar_offline.py`:**
   - Unificar a lógica de leitura dos dois discos (`Program` e `Program_Operational`), aplicando as regras descritas no [12_refinamento_gestao_e_envio.md](12_refinamento_gestao_e_envio.md).
2. **Adicionar o módulo de Upload R2 no Script Local:**
   - Integrar com `boto3` para enviar a pasta de PDFs gerada diretamente para o bucket do Cloudflare R2.
3. **Criar o Endpoint/Script de Sincronização no SAA29:**
   - Permitir a importação do manifesto de metadados para atualizar o banco relacional do sistema e baixar o `catalog.<rotulo>.db` correspondente.
4. **Testar com os Discos Reais:**
   - Executar o pipeline localmente para validar a geração do acervo e a busca full-text no SAA29.
