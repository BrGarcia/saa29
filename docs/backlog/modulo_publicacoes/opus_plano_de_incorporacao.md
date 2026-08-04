# Plano de Incorporação do Módulo `publicacoes` ao SAA29

> **Parecer técnico de viabilidade e plano de execução.**
> Analisa a incorporação do projeto externo documentado em `docs/backlog/manuais/`
> (Sistema Web de Consulta de Manuais Técnicos — EMB-314 Super Tucano) como novo módulo
> do SAA29, ampliado para abrigar também as publicações avulsas da operação
> (BO, BS, NPO, BT).

**Data:** 04/08/2026 · **Revisão 3** (mesmo dia)
**Autor da análise:** Claude Opus 5
**Branch analisado:** `refactor/fable5-otimizacao-codigo`
**Restrição cumprida:** nenhuma linha de código foi escrita ou alterada. Este documento é
exclusivamente parecer + plano.

> **Revisão 2 — o que mudou:** acrescentadas a §8 (**ciclo de publicação anual via DVD**:
> estação de publicação, diff por hash, snapshot ZIP, ativação/reversão pela UI) e a §9
> (**publicações avulsas — BO, BS, NPO, BT**: cadastro manual, anexos escaneados, busca por
> metadados). Em consequência: §5.11 nova (por que o pacote anual não sobe pelo navegador),
> modelo de dados e rotas ampliados, novo marco **M3**, riscos R11–R15 e decisões D-S5/D-S6.
>
> **Revisão 3 — o que mudou:** o módulo passou a se chamar **`publicacoes`** (era `manuais`),
> refletindo que ele abriga dois acervos e não só o do DVD. Renomeados módulo, rotas, scripts,
> templates, assets, testes, variáveis de ambiente e as tabelas do acervo avulso; a convenção
> adotada está na **§6.0**. O documento passou a viver em `docs/backlog/modulo_publicacoes/`,
> e `docs/backlog/manuais/` permanece **apenas como material de referência** do projeto externo.

---

## 1. Veredito executivo

**A incorporação é viável e recomendada — mas não da forma como o projeto externo foi desenhado.**

O encaixe de *domínio* é excelente: o SAA29 gerencia panes, inspeções e vencimentos da frota
A-29, e o insumo que falta em toda essa operação é justamente o manual técnico. O encaixe de
*stack* é quase perfeito: Python 3.12, FastAPI, SQLite, Jinja2 — as duas bases falam a mesma
língua.

O encaixe de **infraestrutura**, porém, é onde o plano externo colide de frente com a
realidade do SAA29, e é o ponto que decide o formato da entrega:

> O projeto externo foi desenhado para uma **VPS dedicada com disco persistente de 20 GB,
> Caddy próprio e acervo de 3 GB no filesystem**.
> O SAA29 roda em **Railway com filesystem efêmero**, banco SQLite persistido por
> backup/restore no Cloudflare R2, Gunicorn com 2 workers e `timeout=30s`.
>
> **Copiar 3 GB de PDFs para dentro do deploy atual do SAA29 não funciona** — nem no boot,
> nem na imagem Docker, nem no ciclo de backup. Esse é o único bloqueador real, e ele é
> resolúvel; todo o resto é adaptação de padrão.

**Recomendação:** incorporar como módulo interno `app/modules/publicacoes/`, em **fases**,
começando por um piloto que **já pode ser feito hoje sem nenhuma mudança de infraestrutura** —
porque o SAA29 já tem, versionados no repositório, **411 PDFs do FIM (14 MB) e 1.377 mensagens
de falha mapeadas em `fim.json`**. Esse piloto entrega valor operacional imediato (a busca de
pane → procedimento FIM), valida toda a arquitetura de indexação/busca/viewer em escala
pequena, e só então a decisão de infraestrutura para os 3 GB completos precisa ser tomada —
já com o sistema provado.

O módulo cobre **dois acervos de natureza diferente**, tratados em separado ao longo deste
documento:

| | **Manuais técnicos** | **Publicações avulsas** (BO, BS, NPO, BT) |
|---|---|---|
| Origem | DVD anual da Embraer | chegam ao longo do ano, avulsas |
| Metadados | já vêm prontos (`.title`, XML) | **digitados por quem cadastra** |
| Texto | vetorial, extraível | **scans**, sem camada de texto |
| Busca | full-text no **conteúdo** | full-text nos **metadados** |
| Criticidade do dado | **descartável** — regenerável do DVD | **precioso** — só existe no sistema |

Essa distinção não é cosmética: ela determina onde cada coisa é armazenada, o que entra no
backup e o que pode ser jogado fora sem medo (§6.2, §9).

---

## 2. Método e base factual

### 2.1 Documentação externa lida (integralmente)

| Arquivo | Linhas | Conteúdo |
|---|---:|---|
| `docs/backlog/manuais/README.md` | 52 | Visão geral, acervo, mapa de leitura |
| `docs/backlog/manuais/Projeto.MD` | 296 | Arquitetura, stack, modelo de dados, roadmap, infra |
| `docs/backlog/manuais/Especificacao.MD` | 317 | Telas, rotas, API, RN-01..RN-10, E-01..E-12, CA-01..CA-07, D-01..D-05 |
| `docs/backlog/manuais/Runbook.MD` | 282 | Provisionamento, deploy, publicação, backup, triagem |
| `docs/backlog/manuais/RAG.MD` | 191 | Fase 3: chunking, embeddings, busca híbrida, `/api/ask` |
| `docs/backlog/manuais/prompt.md` | 101 | Prompt de execução para repositório autônomo |

### 2.2 Verificações executadas contra o código do SAA29

Os números abaixo **não foram inferidos de documentação** — foram medidos nesta análise:

| Verificação | Resultado | Fonte |
|---|---|---|
| FTS5 disponível no SQLite do ambiente | ✅ **Sim** — `CREATE VIRTUAL TABLE ... USING fts5(tokenize='unicode61 remove_diacritics 2')` funciona; busca por `avião` casa com `aviao` | `sqlite3` 3.50.4 no `.venv` |
| Starlette serve `Range` requests nativamente | ✅ **Sim** — `FileResponse` responde `206 Partial Content` com `Content-Range` e `Accept-Ranges: bytes` | teste executado, starlette 0.41.3 |
| Acervo FIM já presente no repositório | ✅ **411 PDFs, 14 MB**, em `docs/fim/` | `ls` + `du` |
| Mapa de falhas FIM | ✅ **1.377 mensagens → 253 procedimentos únicos**; apenas **4 procedimentos sem PDF** (98,4% de cobertura) | `fim.json` + cruzamento com nomes de arquivo |
| PDFs do FIM têm camada de texto | ✅ **Sim** — amostra de 12 arquivos: todos com `/Font` e operadores `Tj`/`TJ`, **zero imagens** (born-digital, não escaneados) | inspeção de bytes/streams |
| Capítulos ATA no acervo FIM | **28 capítulos distintos** (21..97); os **8 códigos ATA seedados** no SAA29 (22, 23, 27, 31, 34, 42, 94, 97) estão **todos presentes** | `fim.json` + `scripts/seed/seed_sistemas_ata.py` |
| Topologia de deploy | Railway (`PORT`), Gunicorn **2 workers**, `worker_class=UvicornWorker`, **`timeout=30`**, `max_requests=1000` | `gunicorn_conf.py` |
| Persistência em produção | Filesystem **efêmero**; SQLite restaurado do R2 no boot e enviado ao R2 no shutdown/debounce de **120 s** | `scripts/start.sh`, `app/bootstrap/tasks.py`, `docs/backlog/Melhorias Futuras/implementacao_localhost.md` |
| CI | Matriz **SQLite + PostgreSQL**, `ruff` + `mypy` + `pytest` | `.github/workflows/ci.yml` |
| Headers de segurança globais | `X-Frame-Options: DENY` e CSP `default-src 'self'; script-src 'self'` em **todas** as respostas | `app/shared/middleware/security.py` |
| CSRF | Aplica-se **somente** a `POST/PUT/PATCH/DELETE` | `app/shared/middleware/csrf.py` |
| Estrutura de módulos | 10 módulos, 117 endpoints, layout canônico `models/schemas/service/router` | `docs/backlog/00_mapa_arquitetural.md` (verificado por amostragem) |

### 2.3 Documentação interna consultada

`docs/architecture/overview.md`, `docs/architecture/RBAC.md`, `docs/backlog/00_mapa_arquitetural.md`,
`docs/methodology/CSP.md`, `docs/guides/cloudflare_r2.md`, `docs/guides/migracao_postgresql.md`,
`docs/ROADMAP.md`, `docs/backlog/Melhorias Futuras/implementacao_consulta_fim.md`,
`docs/backlog/Melhorias Futuras/implementacao_localhost.md`.

> **Observação de contexto:** já existem em `docs/backlog/` dois pareceres sobre o mesmo tema
> (`codex_plano_de_incorporacao.md` e `gemini_plano_de_incorporacao.md`). Este documento foi
> produzido de forma independente, a partir de leitura direta do código; onde há convergência
> (incorporar como módulo interno, não como sidecar), isso reforça a conclusão. Onde há
> divergência, está sinalizado explicitamente na §5.

---

## 3. O que o projeto externo entrega (resumo fiel)

Uma aplicação Python autônoma que:

1. varre um diretório `data/` com a estrutura `<MANUAL>/<CAPÍTULO>/arquivo.PDF`;
2. extrai o texto **página a página** com PyMuPDF e grava em SQLite FTS5;
3. lê os metadados que a Embraer TechPubs já entrega (`.title`, `manual_details.xml`,
   `manual_type.xml`, `collections.ini`, `version/*.txt`) — sem inventar formato novo;
4. oferece navegação (categoria → manual → capítulo → documento) e busca full-text com
   ranking BM25, snippet destacado e, crucialmente, **o número da página do resultado**;
5. abre o PDF **direto na página do trecho** (`#page=N`) via PDF.js com Range requests;
6. tem como regra de ouro: **publicar manual = copiar pasta, zero código**.

O desenho é bom e as decisões são bem justificadas. A qualidade da especificação
(RN/E/CA numerados, riscos, decisões em aberto) é acima da média e **aproveitável quase
integralmente** — é o *empacotamento* (VPS própria, Caddy, `/` como home, acervo no
filesystem, auth em aberto) que não sobrevive à incorporação.

---

## 4. Aderência ao SAA29

### 4.1 Aderência de domínio — **alta**

| Ponto de contato | Valor operacional |
|---|---|
| `panes` → `sistemas_ata` → capítulo do manual | Ao registrar/diagnosticar uma pane de ATA 34, o mantenedor abre direto os procedimentos FIM do capítulo 34 (**69 PDFs** disponíveis hoje) |
| `fim.json` → mensagem de falha → procedimento | O mantenedor lê "ADC 001" no cockpit e chega ao PDF do procedimento em 2 toques — é exatamente o caso de uso do `implementacao_consulta_fim.md`, hoje parado no backlog |
| `inspecoes` → tarefa do catálogo → subject do AMM | O inspetor abre a página exata do procedimento a partir do item de checklist |
| `equipamentos` → part number → CMM/AIPC | Consulta de peça a partir do P/N do inventário |
| Mobile (`/m/`) | O caso de uso "buscar no hangar, pelo celular" já tem casca pronta no SAA29 (v1.4.0) |

O ROADMAP do SAA29 já previa isso: **"Manual FIM"** aparece listado em *Melhorias Futuras*, e
`docs/backlog/Melhorias Futuras/implementacao_consulta_fim.md` é uma versão embrionária,
mais simples, do mesmo sistema. **A incorporação não abre uma frente nova — ela conclui uma
frente já aberta, com um projeto muito mais maduro.**

### 4.2 Aderência de stack — **alta, com 3 ressalvas**

| Camada | Externo | SAA29 | Veredito |
|---|---|---|---|
| Linguagem | Python 3.12 | Python 3.12 (CI) | ✅ idêntico |
| Framework | FastAPI + Uvicorn | FastAPI 0.115.6 + Uvicorn/Gunicorn | ✅ idêntico |
| Banco | SQLite FTS5 (`catalog.db` próprio) | SQLite async (SQLAlchemy 2.0) + **Postgres na matriz de CI** | ⚠️ ver §5.3 |
| Templates | Jinja2 + htmx + Tailwind | Jinja2 + **Vanilla JS/CSS**, CSP sem inline | ⚠️ htmx e Tailwind **fora** |
| Extração PDF | **PyMuPDF (AGPL-3.0)** | ReportLab (geração), Pillow | ⚠️ ver §5.9 |
| Viewer | PDF.js | — (não existe hoje) | ➕ novo asset |
| Proxy/TLS | Caddy | Railway (TLS gerenciado) | ✅ desnecessário — ver §5.5 |
| Deploy | Docker Compose em VPS | Docker no Railway | ⚠️ ver §5.1 |
| Auth | **Em aberto (D-02)** | JWT (cookie `saa29_token`) + RBAC 4 papéis | ✅ **D-02 resolvido de graça** |

---

## 5. Pontos de fricção — a análise que decide o plano

Esta é a seção central do parecer. Cada item foi verificado no código, não presumido.

### 5.1 🔴 BLOQUEADOR — Volumetria × filesystem efêmero

**O fato.** `scripts/start.sh` mostra o ciclo de vida real em produção: a cada boot o
container faz `pip install`, **restaura o banco do R2**, roda `alembic upgrade head`, faz seed
e sobe o Gunicorn. `app/bootstrap/events.py` + `tasks.py` mostram o retorno: a cada commit
SQLAlchemy o banco é marcado *dirty* e, após **120 s de debounce**, o **arquivo inteiro** é
enviado ao R2. Isso só é sustentável porque o banco atual tem ~1 MB.

**A colisão.** O acervo completo são **~3 GB de PDFs** e o índice estimado em
**~1–2 GB** (`Projeto.MD` §10). Nesse cenário:

- os PDFs **não podem** morar no filesystem do container — somem a cada deploy;
- **não podem** ir na imagem Docker — o `Dockerfile` faz `COPY . .`, e uma imagem de 3 GB
  é inviável em build/pull no Railway;
- o índice **não pode** ficar no `saa29_local.db` — o backup R2 passaria a subir 2 GB a cada
  janela de 120 s, o que estoura custo, tempo de shutdown e a própria janela de deploy;
- baixar 3 GB do R2 no boot **não é opção** — o `start.sh` seria interrompido muito antes.

**A saída (recomendada).**

| Artefato | Onde mora | Como chega ao runtime |
|---|---|---|
| PDFs do acervo | **Cloudflare R2** (bucket já existente, prefixo `publicacoes/`) | Nunca são baixados inteiros: o app gera **URL pré-assinada** (`R2StorageService.get_url`, já implementado) ou faz **proxy com Range**. O R2 já suporta Range nativamente. |
| Índice `catalog.db` | Arquivo SQLite **separado**, gerado **offline** | Baixado do R2 **uma vez por boot** (~50–300 MB no piloto FIM; ver §5.3 sobre o corte para o acervo completo) ou montado em volume Railway |
| Metadados exibíveis | Tabelas no banco principal (Alembic) | Só o catálogo leve: manuais, capítulos, documentos. **Nunca o texto das páginas.** |

**Consequência de projeto:** a "regra de ouro" externa (*publicar manual = copiar pasta*)
**muda de forma, mas não de espírito**: publicar = `rclone/aws s3 sync` da pasta para o R2 +
rodar o indexador offline + subir o `catalog.db` novo. Continua sendo *zero código*, mas
deixa de ser *zero comando*.

---

### 5.2 🟠 Colisão de diretório: `data/`

`docker-compose.yml:13` define `DATABASE_URL=sqlite+aiosqlite:////app/data/saa29.db` e monta
o volume `sqlite_data` em `/app/data`. A pasta `data/` na raiz do SAA29 **já é o ponto de
montagem do banco**. O projeto externo reivindica exatamente esse caminho para o acervo.

**Decisão:** o acervo **nunca** usa `data/`. Caminhos configuráveis, com defaults:

```
PUBLICACOES_ACERVO_DIR=var/publicacoes/acervo     # só em dev/local; em produção, R2
PUBLICACOES_INDEX_PATH=var/publicacoes/catalog.db
```

`var/` já está no `.gitignore` (`var/db`, `var/uploads/`, `var/tmp/`) e no `.dockerignore` —
é o lugar natural. **Ação obrigatória:** adicionar `var/publicacoes/` ao `.gitignore` e garantir
que `.dockerignore` continue excluindo `var/`.

---

### 5.3 🟠 O índice FTS5 não pode entrar no banco principal

Dois motivos independentes, ambos verificados:

1. **A matriz de CI testa PostgreSQL** (`.github/workflows/ci.yml`, `db-type: [sqlite, postgres]`)
   e `docs/methodology/NEXT.md` declara "Portabilidade 100% — suporte nativo e testado a
   SQLite e PostgreSQL". Uma `CREATE VIRTUAL TABLE ... USING fts5` numa migration Alembic
   **quebra o job Postgres do CI** e mata a portabilidade que o projeto já pagou para ter.
2. **O ciclo de backup R2** (§5.1) sobe o arquivo inteiro do `DATABASE_URL`.

**Decisão:** o índice vive em **arquivo SQLite dedicado**, aberto por uma engine própria
(ou por `sqlite3` síncrono em thread), **fora do Alembic e fora do `DATABASE_URL`**. O acesso
fica isolado atrás de uma única função de busca — mesma "fronteira de troca limpa" que o
`Projeto.MD` §10 já defende. Se um dia o SAA29 migrar para Postgres, troca-se a implementação
por `tsvector`/`pg_trgm` sem tocar em router, service ou UI.

Divergência registrada: os pareceres do Codex e do Gemini chegam à mesma conclusão de
"catalog.db separado". **Convergência de três análises independentes — trate como decidido.**

---

### 5.4 🔴 A indexação não pode rodar dentro do processo web

**O fato.** `gunicorn_conf.py` fixa `workers = 2` e **`timeout = 30`**. PyMuPDF é síncrono e
CPU-bound. O `Projeto.MD` §6 estima **15–40 min** para a indexação inicial dos ~12 mil PDFs.

**A colisão.** O desenho externo dispara a indexação **no boot da aplicação** e expõe
`POST /admin/reindex`. Dentro do SAA29 isso produziria:
- worker morto pelo `timeout=30` no meio do lote;
- com 2 workers, **um deles indisponível** durante toda a indexação — 50% da capacidade;
- pior: com 2 workers, **duas indexações concorrentes** escrevendo no mesmo SQLite (o lock
  `index_state` do desenho externo é *in-process* e não protege contra isso);
- e `max_requests=1000` recicla workers periodicamente, reiniciando o trabalho.

**Decisão:**
- indexação é **script offline** (`scripts/publicacoes/indexar.py`), executado na máquina do
  operador ou num job, **não no processo web**;
- o app **consome** o `catalog.db` pronto, somente leitura;
- `POST /publicacoes/reindex` **não existe no MVP**. Se for necessário depois, vira job
  desacoplado — nunca trabalho pesado dentro do request.

Isso também simplifica muita coisa da especificação externa: E-09 (409 em reindexação
concorrente), o lock, o `index_state: running` e boa parte de `/api/status` deixam de ser
problema de runtime.

---

### 5.5 🟡 Servir os PDFs — o Caddy não é necessário, mas há duas armadilhas

**Boa notícia (verificada):** `FileResponse` do Starlette 0.41.3 **já responde `206 Partial
Content` com `Content-Range`** — testado nesta análise. O argumento central do `Projeto.MD`
para o Caddy ("PDFs nunca passam pela aplicação Python") **é dispensável no MVP**: o FastAPI
serve PDFs com Range corretamente, e assim eles ficam **protegidos por autenticação**, o que
é um requisito no SAA29 e era uma pendência em aberto (D-02) no projeto externo.

**Armadilha 1 — `X-Frame-Options: DENY`.** `app/shared/middleware/security.py:27` injeta esse
header em **todas** as respostas. `DENY` bloqueia o enquadramento **inclusive pela própria
origem**. Ou seja: um viewer feito com `<iframe src="/publicacoes/doc/{id}/pdf">` **não vai
renderizar** — e o sintoma (iframe em branco, sem erro de rede) é notoriamente difícil de
diagnosticar. Duas saídas:
- **(preferida)** usar **PDF.js**, que busca os bytes por `fetch`/XHR e desenha em `<canvas>` —
  não há enquadramento, o header não se aplica;
- ou isentar a rota do PDF do `X-Frame-Options` / usar `SAMEORIGIN` **apenas nela**.

**Armadilha 2 — CSP.** A política atual é `default-src 'self'; script-src 'self'` e **não
declara `worker-src`**, que por herança cai em `default-src 'self'`. O PDF.js instancia um
Web Worker e, em várias configurações de build, usa `blob:` para worker e/ou fontes. O
provável delta necessário é:

```
worker-src 'self' blob:;
font-src 'self' https://fonts.gstatic.com;   (avaliar necessidade de blob:)
img-src ... blob:;                            (canvas/thumbnails)
```

**Isso deve ser medido, não presumido** — a validação empírica do console do navegador com o
build escolhido do PDF.js é um item de aceite explícito do plano (§8, M1). O `docs/methodology/CSP.md`
declara "100% de conformidade" hoje; qualquer alargamento precisa ser justificado e
documentado lá, na mesma PR.

**Armadilha 3 (operacional).** Com apenas 2 workers, um download longo de PDF prende um
worker. Para o piloto FIM (arquivos de 13–92 KB, medidos) isso é irrelevante. Para AMMs
grandes do acervo completo, a saída é **URL pré-assinada do R2** — o byte range vai direto do
R2 ao navegador, sem passar pelo app.

---

### 5.6 🟡 Autenticação e RBAC — ganho líquido, com um detalhe

O SAA29 **resolve a decisão D-02** do projeto externo sem discussão: JWT em cookie
`saa29_token` + RBAC de 4 papéis. Nada do módulo fica público.

Detalhe que importa: o PDF.js precisa buscar os bytes **com credencial**. Como o SAA29 aceita
JWT **por cookie** (`get_token_from_request`, `dependencies.py:44-58`), um `fetch` same-origin
com `credentials: 'same-origin'` já autentica — **não é preciso** inventar token na query
string (que vazaria em log de acesso e histórico do navegador). Se, no futuro, os PDFs forem
servidos por URL pré-assinada do R2, a expiração de 60 min já implementada
(`storage.py:129`) é o controle adequado.

**Matriz RBAC proposta** (consulta é insumo universal de manutenção; publicação é ato
controlado):

| Ação | Mant | Enc | Insp | Adm |
|---|:--:|:--:|:--:|:--:|
| Navegar catálogo / buscar / abrir PDF | ✅ | ✅ | ✅ | ✅ |
| Ver status do índice | ✅ | ✅ | ✅ | ✅ |
| Publicar/atualizar acervo e reindexar | ❌ | ❌ | ❌ | ✅ |

---

### 5.7 🟡 UI — htmx e Tailwind ficam de fora

O `Projeto.MD` §3 escolhe htmx + Tailwind. O SAA29 é **Jinja2 + Vanilla JS + CSS próprio**,
com CSP proibindo script inline (`docs/methodology/CSP.md`, regra "Zero Inline Scripts").

Introduzir htmx e Tailwind por causa de um módulo criaria **um segundo dialeto de frontend**
dentro do sistema — exatamente o tipo de divergência que `00_mapa_arquitetural.md` §5 já
cataloga como dívida. O padrão de fato do SAA29 (JS busca dados via `fetch` e monta o DOM com
`escapeHtml`) cobre 100% do que a busca precisa, incluindo o "carregar mais" paginado.

**Decisão:** sem htmx, sem Tailwind. Estender `base.html`, novo item no `<nav>` (`/publicacoes`),
CSS em `index.css`, JS em `app/web/static/js/publicacoes.js`. **Única dependência de frontend
nova: PDF.js**, servida localmente em `app/web/static/js/pdfjs/` (a CSP não permite CDN, e
está correto assim).

---

### 5.8 🟡 A publicação de manuais muda de procedimento

O `Runbook.MD` §5.1 define a operação mais frequente como `rsync` para a VPS + `curl` no
`/admin/reindex`. **No Railway não há shell persistente nem disco para receber `rsync`.**

Além disso, a premissa do documento externo é falsa para este caso: lá, publicar manual é *"a
operação mais frequente"*; aqui, é **anual**. Isso muda o desenho ótimo — um procedimento que
roda uma vez por ano pode ser mais manual e mais lento, desde que seja **seguro e reversível**.

O fluxo completo está na **§8** (ciclo de publicação anual). Em resumo: a parte pesada roda na
máquina do operador e o SAA29 recebe o resultado pronto, ativado por um clique. Continua sendo
"sem código e sem cadastro manual" — o espírito da regra de ouro é preservado.

O `Runbook.MD` externo **não é aproveitável como está**: §2 (provisionamento de VPS),
§3 (Caddyfile/compose), §4 (deploy), §6.2 (cron de backup) e §7 (Uptime Kuma) descrevem uma
infraestrutura que não existe aqui. O que **se aproveita** é a §8 (tabela de triagem de
problemas) e o princípio da §6.1 ("a VPS é descartável; o índice é 100% derivado do acervo") —
que, aliás, é ainda mais verdadeiro no Railway.

---

### 5.9 🟠 Licenciamento do PyMuPDF — decisão que precisa subir para o dono

**PyMuPDF é distribuído sob AGPL-3.0** (ou licença comercial paga da Artifex). A cláusula de
rede da AGPL alcança software **acessado por rede**, não apenas redistribuído — e o SAA29 é
um sistema web acessado por terceiros (Railway, usuários da FAB).

Não sou a autoridade competente para dar parecer jurídico, e a exposição real depende de
como o SAA29 é classificado (uso interno de órgão público, sem distribuição externa, é um
cenário bem menos crítico). Mas é uma decisão consciente que **precisa ser tomada por você**,
não herdada por acidente de uma escolha feita para outro projeto.

Alternativas técnicas equivalentes para o caso de uso, com licenças permissivas:

| Biblioteca | Licença | Extração de texto por página | Velocidade relativa |
|---|---|---|---|
| **PyMuPDF** | **AGPL-3.0** / comercial | ✅ excelente | 1,0× (referência) |
| **pypdfium2** | Apache-2.0 / BSD-3 | ✅ boa (binding do PDFium, o motor do Chrome) | ~1–2× mais lento |
| **pdfminer.six** | MIT | ✅ boa, layout-aware | ~10–30× mais lento |

Como a indexação é **offline e ocorre uma vez** (§5.4), a diferença de velocidade tem peso
muito menor do que teria no desenho original. **Recomendação: avaliar `pypdfium2` no
piloto** — 411 PDFs pequenos são uma amostra perfeita para medir qualidade de extração e
tempo real antes de comprometer o projeto com AGPL.

---

### 5.10 🟠 Classificação do acervo, direitos autorais e a Fase 3 (RAG)

Dois pontos que o projeto externo trata de leve e que, dentro da FAB, pesam mais:

**Acervo controlado.** Manuais técnicos Embraer são material proprietário e de acesso
controlado. O `Especificacao.MD` deixa isso em aberto (D-02) e o `Runbook.MD` chega a servir
`/data/*` publicamente pelo Caddy. **Dentro do SAA29 isso não acontece** — herda-se
autenticação obrigatória, e recomenda-se ir além: registrar auditoria de acesso a documento
(quem abriu qual manual, quando), coerente com a §4 do `RBAC.md` ("toda ação crítica deve ser
auditável").

**RAG (Fase 3).** O `RAG.MD` prevê enviar trechos dos manuais para **API de LLM externa** e
registra isso como decisão em aberto (D-R5). Para conteúdo técnico-militar, essa é a decisão
mais séria de todo o pacote, e ela **não é técnica**: precisa de autorização formal antes de
qualquer piloto. A boa notícia é que o RAG é estritamente incremental — nada na Fase 1 ou 2
depende dele, e as tabelas `chunks`/`chunks_vec` do `RAG.MD` §5 encaixam depois sem
retrabalho, **se e quando** a autorização existir.

**Recomendação:** manter a Fase 3 no documento como visão, mas **fora do plano de execução**
até que D-R5 seja formalmente respondida. As regras R1–R4 do `RAG.MD` §2 (citação
obrigatória, documento oficial prevalece, sem geração de procedimento, temperatura zero) são
excelentes e devem ser preservadas integralmente quando/se a fase for aberta.

---

### 5.11 🔴 Subir o acervo pelo navegador não é caminho viável

A ideia natural — "botão que recebe as pastas do DVD" ou "botão que recebe um ZIP de 3 GB" —
esbarra em quatro limites verificados no código. Registro aqui porque a intenção por trás dela
está **certa** e é atendida por outro mecanismo (§8):

| # | Limite verificado | Onde |
|---|---|---|
| 1 | `ler_upload_com_limite()` lê em chunks mas **materializa o arquivo inteiro em `bytes`** antes de repassar a `storage.upload(file_content: bytes, ...)`. Um pacote de 3 GB vira 3 GB de RAM. | `file_validators.py`, `storage.py:46` |
| 2 | `max_upload_size_mb = 0.5` (500 KB) | `config/__init__.py` |
| 3 | `.zip` **não está** em `EXTENSOES_PERMITIDAS` e **não há validador de magic bytes** para ele. O próprio arquivo documenta a regra: `.doc/.docx` foram *removidos* da allowlist justamente por não terem validação de assinatura — "se o suporte for necessário no futuro, deve entrar aqui primeiro, com magic bytes reais". | `file_validators.py:18-46` |
| 4 | `timeout = 30` no Gunicorn, com **2 workers**. Um upload de 12.100 partes multipart (ou de 3 GB em uma requisição) é morto muito antes de terminar — e enquanto durasse, ocuparia 50% da capacidade do sistema. | `gunicorn_conf.py` |

Some-se a isso que habilitar upload de ZIP abre superfície de ataque nova e não trivial
(**zip-slip** — entradas com `../` que escapam do diretório de extração; **zip bomb** —
compressão que explode em disco), num sistema que hoje tem uma allowlist deliberadamente
estreita e auditada.

**Conclusão:** o pacote anual não sobe pelo app. Ele é processado onde o DVD está — na sua
máquina — e o que chega ao SAA29 é o resultado pronto (§8). O botão na UI continua existindo,
mas **ativa** uma edição já publicada em vez de recebê-la.

---

### 5.12 🟢 Fricções menores (registradas para não virarem surpresa)

| # | Item | Nota |
|---|---|---|
| a | `scripts/start.sh` roda `pip install -r requirements.txt` **a cada boot** | Adicionar a lib de PDF encarece o cold start em alguns segundos. Aceitável; considerar remover o auto-install em outra frente. |
| b | `docs/fim/` (14 MB) **entra na imagem Docker hoje** — `.dockerignore` não exclui `docs/` | Se o acervo crescer dentro de `docs/`, a imagem cresce junto. Mover o acervo para fora de `docs/` **antes** de qualquer expansão. |
| c | `max_upload_size_mb = 0.5` e `EXTENSOES_PERMITIDAS` | Irrelevante: manuais **não** entram por upload HTTP. Não mexer nesses limites. |
| d | CSRF só afeta mutações | O módulo é read-only → **zero impacto**. |
| e | Prefixo de rota | Usar `/publicacoes` (padrão do projeto), **não** `/api/v1/publicacoes` — `calendario` é a única exceção e já causou bug documentado. Registrar `/publicacoes/` em `API_PREFIXES` (`main.py:50`) para os endpoints JSON. |
| f | Convenções internas do módulo | Usar `domain_exc` (`shared/core/exceptions.py`), RBAC por `Annotated` na assinatura, `Schema.model_validate(...)` explícito — os padrões **majoritários**, não os divergentes catalogados em `00_mapa_arquitetural.md` §5. |
| g | `has_text = 0` (E-01) | **Não é risco no piloto FIM** — medido: os PDFs são born-digital com camada de texto. Volta a ser risco real no acervo completo. |
| h | `app/modules/encarregado/` é casca vazia | Precedente de módulo iniciado e abandonado. O `publicacoes` deve nascer com router+service+testes desde o primeiro commit. |

---

## 6. Arquitetura alvo

### 6.0 Nomenclatura adotada

O módulo se chama **`publicacoes`** — o termo guarda-chuva que cobre os dois acervos. Dentro
dele, cada acervo mantém o nome que o descreve, para que nunca haja dúvida sobre qual é qual:

| Nível | Nome | Abrange |
|---|---|---|
| **Módulo** | `publicacoes` | tudo — rotas em `/publicacoes`, `app/modules/publicacoes/` |
| Acervo A | **`manuais_*`** | manuais técnicos do DVD (AMM, AIPC, FIM, CMM…) — §8 |
| Acervo B | **`publicacoes_avulsas*`** | BO, BS, NPO, BT — §9 |
| Transversal | `publicacoes_favoritos`, `publicacoes_acessos` | valem para os dois acervos |

Manter o prefixo `manuais_` nas tabelas do acervo do DVD é deliberado: `manuais_documentos`
ao lado de `publicacoes_avulsas` se lê sozinho, enquanto `publicacoes_documentos` ao lado de
`publicacoes_avulsas` exigiria decorar qual é qual. O nome do módulo não precisa se repetir
em cada tabela dele.

### 6.1 Estrutura de arquivos

```
app/modules/publicacoes/
├── __init__.py
├── models.py            # manuais_* + publicacoes_avulsas* + edições (Alembic)
├── schemas.py           # contratos Pydantic
├── service.py           # regras de negócio; ÚNICO ponto de acesso a dados
├── search.py            # camada isolada de busca (FTS5 hoje; trocável)
├── catalog.py           # parsers de .title / XML / ini  (RN-02, RN-03, RN-07)
├── avulsas.py           # BO / BS / NPO / BT — cadastro manual (§9)
└── router.py            # endpoints JSON sob /publicacoes

app/web/
├── templates/publicacoes/
│   ├── lista.html       # catálogo por categoria + busca global
│   ├── manual.html      # capítulos → documentos
│   ├── avulsas.html     # lista/busca de BO, BS, NPO, BT
│   └── viewer.html      # PDF.js
└── static/
    ├── js/publicacoes.js
    ├── js/publicacoes_avulsas.js
    ├── js/mobile/publicacoes_mobile.js
    └── js/pdfjs/                    # PDF.js local (CSP não permite CDN)

scripts/publicacoes/
├── indexar.py           # indexação OFFLINE (PyMuPDF/pypdfium2 → catalog.db)
├── publicar.py          # ESTAÇÃO DE PUBLICAÇÃO: DVD → diff → índice → R2 (§8)
└── merge_data.py        # Fase 0 externa — só quando o acervo completo entrar

tests/unit/test_publicacoes.py
tests/unit/test_publicacoes_catalog.py     # RN-02, RN-03, RN-07 com fixtures reais
tests/unit/test_publicacoes_avulsas.py     # cadastro, vigência, substituição
tests/integration/test_publicacoes_busca.py
```

### 6.2 Divisão de dados — a decisão estrutural

```
┌─ saa29_local.db  (Alembic, SQLAlchemy async, backup R2) ─────────────┐
│                                                                      │
│  ── ACERVO A: manuais do DVD (catálogo leve; derivado, regenerável)  │
│  manuais_edicoes      id, rotulo, data_publicacao, snapshot_key,     │
│                       hash_sha256, status, publicado_por, relatorio  │
│  manuais              id, edicao_id, codigo, descricao_pt,           │
│                       categoria, path, revisao, revisao_data         │
│  manuais_documentos   id, manual_id, capitulo, ata_codigo, file_key, │
│                       titulo, sort_order, paginas, has_text,         │
│                       revision_status, hash_sha256                   │
│  manuais_fim_map      mensagem, procedimento, documento_id ←fim.json │
│                                                                      │
│  ── ACERVO B: publicações avulsas (dado de usuário; PRECIOSO)        │
│  publicacoes_avulsas  id, tipo, numero, ano, data_emissao,           │
│                       data_recebimento, emissor, titulo, ementa,     │
│                       sistema_ata_id→, status, substituida_por_id→,  │
│                       cadastrada_por_id→, criada_em, atualizada_em   │
│  publicacao_avulsa_anexos     id, avulsa_id, file_key,               │
│                               nome_original, tamanho, principal      │
│  publicacao_avulsa_aeronaves  avulsa_id, aeronave_id (aplicabilidade)│
│                                                                      │
│  ── TRANSVERSAL (valem para os dois acervos)                         │
│  publicacoes_favoritos  usuario_id, documento_id | avulsa_id         │
│  publicacoes_acessos    usuario_id, documento_id, pagina, edicao_id, │
│                         quando                          (auditoria)  │
└──────────────────────────────────────────────────────────────────────┘
        ▲ portável para Postgres, sob RBAC, dentro do backup R2
        │
┌─ catalog.db  (SQLite dedicado, READ-ONLY em runtime, fora do Alembic)┐
│  pages       document_id, page_number, text                          │
│  pages_fts   VIRTUAL fts5(text, unicode61 remove_diacritics 2)       │
└──────────────────────────────────────────────────────────────────────┘
        ▲ gerado offline; volumoso; nunca entra no backup R2 do banco principal
```

**A linha divisória que importa:** `catalog.db` pode ser apagado sem dano — reconstrói-se do
DVD/snapshot em algumas horas. As tabelas `publicacoes_avulsas*` **não existem em nenhum outro lugar
do mundo**: foram digitadas por um militar do esquadrão. Por isso ficam no banco principal,
sob Alembic e dentro do ciclo de backup R2 já existente — mesmo grau de proteção das panes e
inspeções.

**Chave de junção:** `manuais_documentos.id` é a mesma `document_id` usada em `pages` — o
indexador offline grava os dois lados de forma determinística (a partir do caminho relativo
do arquivo), preservando **CA-07** do projeto externo (estabilidade de links entre
reindexações).

Esse corte mantém: (a) portabilidade Postgres do banco principal; (b) o backup R2 leve;
(c) RBAC e auditoria em SQL normal; (d) FTS5 isolado atrás de `search.py`.

### 6.3 Rotas

| Rota | Tipo | Acesso | Observação |
|---|---|---|---|
| `GET /publicacoes` | HTML | autenticado | home do módulo: busca unificada nos dois acervos |
| `GET /publicacoes/manuais` | HTML | autenticado | catálogo de manuais por categoria |
| `GET /publicacoes/manuais/{manual_path}` | HTML | autenticado | capítulos |
| `GET /publicacoes/manuais/{manual_path}/{capitulo}` | HTML | autenticado | documentos |
| `GET /publicacoes/viewer/{doc_id}` | HTML | autenticado | PDF.js; âncora `#page=N` |
| `GET /publicacoes/api/busca` | JSON | autenticado | contrato da `Especificacao.MD` §4, preservado |
| `GET /publicacoes/api/fim?q=` | JSON | autenticado | busca por mensagem de falha (`fim.json`) |
| `GET /publicacoes/api/status` | JSON | autenticado | versão do índice, contagens, `documentos_sem_texto` |
| `GET /publicacoes/doc/{doc_id}/pdf` | binário | autenticado | `FileResponse` com Range (piloto) → redirect para URL pré-assinada R2 (produção) |
| `GET /m/publicacoes` | HTML | autenticado | atalho mobile |
| **Publicações avulsas (§9)** | | | |
| `GET /publicacoes/avulsas` | HTML | autenticado | lista + filtros (tipo, ATA, ano, vigência) |
| `GET /publicacoes/api/avulsas` | JSON | autenticado | busca nos metadados |
| `POST /publicacoes/api/avulsas` | JSON | Enc/Insp/Adm | cadastro (cabeçalho digitado) |
| `PATCH /publicacoes/api/avulsas/{id}` | JSON | Enc/Insp/Adm | correção / mudança de vigência |
| `POST /publicacoes/api/avulsas/{id}/anexos` | multipart | Enc/Insp/Adm | anexo (limite próprio — §9.3) |
| `GET /publicacoes/avulsas/{id}/anexo/{anexo_id}` | binário | autenticado | download/visualização |
| **Administração do acervo (§8)** | | | |
| `GET /publicacoes/api/edicoes` | JSON | `AdminRequired` | edições publicadas, status, relatório de diff |
| `POST /publicacoes/api/edicoes/{id}/ativar` | JSON | `AdminRequired` | troca de ponteiro (atômica, instantânea) |
| `POST /publicacoes/api/edicoes/{id}/reverter` | JSON | `AdminRequired` | volta para a edição anterior |

Contrato de `/publicacoes/api/busca`: **manter o JSON da `Especificacao.MD` §4 sem alterações**
(campos `total`, `took_ms`, `results[].page`, `snippet`, `viewer_url`). É um bom contrato e
preservá-lo mantém a especificação externa viva como documento de referência.

> **Cuidado de roteamento introduzido pelo nome do módulo.** Com o módulo em `/publicacoes`,
> os manuais **precisam** ficar sob `/publicacoes/manuais/...` — se ficassem em
> `/publicacoes/{manual_path}`, esse parâmetro capturaria `avulsas`, `viewer`, `api` e `doc`,
> e as rotas fixas nunca seriam alcançadas. Cada acervo com seu segmento próprio elimina a
> ambiguidade por construção, sem depender da ordem de registro dos handlers no FastAPI.

### 6.4 Configuração nova (`.env.example`)

```env
# --- Módulo Publicações ---
PUBLICACOES_ENABLED=true
PUBLICACOES_MODO=consulta                  # consulta | publicacao  (§8.3)

# Acervo A — manuais técnicos do DVD
PUBLICACOES_ACERVO_DIR=var/publicacoes/acervo      # dev/local; em produção, R2
PUBLICACOES_INDEX_PATH=var/publicacoes/catalog.db
PUBLICACOES_STORAGE=local                  # local | r2
PUBLICACOES_R2_PREFIX=publicacoes/
PUBLICACOES_CATEGORIAS_PATH=config/categorias_manuais.toml  # manual_type.xml (RN-04)
PUBLICACOES_EDICOES_RETIDAS=2              # online: vigente + anterior (§8.6)
PUBLICACOES_SNAPSHOTS_RETIDOS=3            # snapshots ZIP no R2 (§8.4)

# Acervo B — publicações avulsas (BO/BS/NPO/BT)
PUBLICACOES_AVULSAS_MAX_UPLOAD_MB=50       # separado de MAX_UPLOAD_SIZE_MB (§9.3)
```

`PUBLICACOES_ENABLED` é deliberado: permite que o módulo suba desligado (rotas não registradas)
até o acervo estar disponível no ambiente — o SAA29 continua funcionando normalmente
enquanto a decisão de infra da §5.1 amadurece.

---

## 7. Destino de cada regra da especificação externa

Tabela de rastreabilidade. Nada da `Especificacao.MD` é perdido sem decisão explícita.

### Regras de Negócio

| RN | Assunto | Destino no SAA29 |
|---|---|---|
| RN-01 | Descoberta de documentos | ✅ **Mantida** — no indexador offline |
| RN-02 | Título via `.title` → metadado → nome do arquivo | ✅ **Mantida** — `catalog.py`; no piloto FIM não há `.title`, cai no nível 3 + `fim.json` |
| RN-03 | Descrição do manual (`manual_details.xml`) | ✅ **Mantida** — relevante a partir da fase 3 |
| RN-04 | Categoria (`manual_type.xml`, `catid`) | ✅ **Mantida**, em `categorias_manuais.toml` (nunca hardcoded) |
| RN-05 | Ordenação por prefixo numérico | ✅ **Mantida** |
| RN-06 | Revisão (`version/<MANUAL>.txt`) | ✅ **Mantida** — coluna `revisao`/`revisao_data` |
| RN-07 | Encoding UTF-8 → cp1252 | ✅ **Mantida** — `read_text_legacy()`, com teste dedicado |
| RN-08 | Deduplicação no merge | ⏸️ **Adiada** para a fase do acervo completo (não se aplica ao piloto) |
| RN-09 | Indexação incremental, não bloqueante | ♻️ **Reformulada** — incremental sim, mas **offline** (§5.4). "Não bloqueia a UI" passa a ser garantido por construção |
| RN-10 | Sanitização da query FTS | ✅ **Mantida e reforçada** — é também requisito de segurança; teste fuzz obrigatório |

### Casos de borda

| E | Destino |
|---|---|
| E-01 (sem camada de texto) | ✅ mantido — `has_text=0`; **medido como não-risco no piloto** |
| E-02 (PDF corrompido) | ✅ mantido — no indexador offline; nunca aborta o lote |
| E-03 (`.title` ausente) | ✅ mantido |
| E-04 (manual fora dos XMLs) | ✅ mantido — categoria "Outros" |
| E-05 (PDF solto na raiz) | ✅ mantido |
| E-06 (query FTS inválida) | ✅ mantido — jamais 500 |
| E-07 (busca sem resultado) | ✅ mantido |
| E-08 (documento removido) | ✅ mantido — 404 amigável |
| E-09 (reindexação concorrente) | ❌ **eliminado por construção** (§5.4) |
| E-10 (acentos/espaços no caminho) | ✅ mantido — reforçado por `validar_nome_arquivo_seguro` (path traversal) |
| E-11 (PDF > 100 MB no mobile) | ✅ mantido — Range verificado funcionando |
| E-12 (acervo vazio) | ♻️ **substituído** por `PUBLICACOES_ENABLED=false` + estado vazio na UI |

### Critérios de aceite

| CA | Destino |
|---|---|
| CA-01 (busca abre na página exata, p95 < 300 ms) | ✅ **mantido** — é o critério central |
| CA-02 (publicar sem código) | ♻️ **adaptado** — sem código, mas com o procedimento da §5.8 |
| CA-03 (navegação mobile, alvos ≥ 44 px) | ✅ mantido — alinhado ao módulo `/m/` existente |
| CA-04 (diacríticos) | ✅ **mantido e já verificado** — `remove_diacritics 2` funciona no ambiente |
| CA-05 (resiliência da indexação) | ✅ mantido |
| CA-06 (RSS < 200 MB, home < 100 ms) | ♻️ **adaptado** — o alvo agora é *não regredir* o consumo atual do SAA29 no Railway |
| CA-07 (estabilidade de links) | ✅ **mantido** — garantido pelo `document_id` determinístico (§6.2) |

### Decisões em aberto

| D | Status no SAA29 |
|---|---|
| D-01 (rótulos dos `catid` 1–7) | 🟡 **continua aberta** — mas não bloqueia: `categorias_manuais.toml` com provisórios |
| D-02 (acesso restrito?) | ✅ **RESOLVIDA** — JWT + RBAC do SAA29, autenticação obrigatória |
| D-03 (migrar `Comments/` do legado) | 🟡 aberta — fase 2, se houver conteúdo relevante |
| D-04 (domínio/provedor de VPS) | ✅ **ELIMINADA** — não há VPS; o ambiente é o do SAA29 |
| D-05 (manuais exclusivos de um dos sistemas) | 🟡 aberta — só na fase do acervo completo |
| **D-S1 (nova)** | **Onde mora o acervo de 3 GB** — R2 vs. volume Railway vs. servidor interno da OM. *Decisão sua, bloqueia a Fase 3.* |
| **D-S2 (nova)** | **PyMuPDF (AGPL) vs. pypdfium2 (Apache-2.0)** — §5.9. *Decisão sua, antes da Fase 1.* |
| **D-S3 (nova)** | **Autorização para trafegar conteúdo dos manuais por API externa** (RAG) — §5.10. *Bloqueia a Fase 4 inteira.* |
| **D-S4 (nova)** | **Escopo do acervo**: só Eletrônica (8 ATAs seedados) ou frota inteira? Muda a volumetria em uma ordem de grandeza. |
| **D-S5 (nova)** | **Onde roda a estação de publicação** — script no venv da sua máquina (funciona já) ou instância local em Docker com UI (`implementacao_localhost.md`). §8.3. *Não bloqueia nada antes do M4.* |
| **D-S6 (nova)** | **Quem cadastra publicação avulsa** — proposto `EncarregadoInspetorOuAdmin`; confirmar se o mantenedor também deve poder. §9.2. *Decisão de 1 minuto, mas precisa ser sua.* |

---

## 8. Ciclo de publicação anual (o DVD)

Esta seção responde diretamente à pergunta operacional: **chega um DVD por ano com as
publicações novas — como isso entra no sistema?**

### 8.1 A intenção está certa; o mecanismo precisa mudar de lugar

A ideia de "um botão em Configurações onde eu seleciono as pastas do DVD" está **certa no que
importa**: o operador no controle, sem terminal, sem depender de desenvolvedor. O que não
funciona é fazer o navegador e o servidor web carregarem 3 GB / 12.100 arquivos — pelos quatro
limites verificados em §5.11.

A saída é separar duas coisas que a proposta original juntava:

| | **Ingestão** (pesada) | **Ativação** (leve) |
|---|---|---|
| O quê | ler DVD, comparar, extrair texto, construir índice, subir para o R2 | apontar o sistema para a edição nova |
| Onde | **sua máquina**, com o DVD na mão | **botão em `/configuracoes`** |
| Duração | horas (um fim de semana) | **segundos** |
| Risco para o SAA29 | **zero** — nem toca no Railway | mínimo, e reversível |

Isso encaixa exatamente no que você descreveu: *"não é crítico, posso deixar rodando no fim de
semana"*. Rodando **no seu PC** — o Railway não fica ocupado, não há custo de CPU em nuvem, e
se a máquina travar no meio nada acontece com o sistema em produção, porque a edição vigente
continua intacta até você clicar em "Ativar".

### 8.2 O fluxo, ponta a ponta

```
   DVD (anual)
     │
     │  ┌─ SUA MÁQUINA — fim de semana ────────────────────────────────┐
     └─►│  python scripts/publicacoes/publicar.py --dvd E:\ --edicao 2027  │
        │                                                              │
        │   1. inventário + hash SHA-256 de cada arquivo               │
        │   2. DIFF contra a edição vigente                            │
        │        → novos | revisados | removidos | inalterados         │
        │   3. extração de texto só do que mudou   ← economia grande   │
        │   4. constrói catalog.db novo (edição completa)              │
        │   5. gera snapshot.zip do DVD (imutável, com hash)           │
        │   6. sobe para o R2:                                         │
        │        • PDFs novos/revisados  ← SÓ O DELTA                  │
        │        • catalog.db  da edição 2027                          │
        │        • snapshots/2027_EMB314.zip                           │
        │   7. emite relatorio_publicacao_2027.md                      │
        └──────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌─ SAA29 /configuracoes → card "Publicações" ──────────────────┐
        │  Edição 2027  ·  aguardando ativação                         │
        │  128 novos · 342 revisados · 11 removidos · 11.640 inalter.  │
        │  [ Ver relatório ]   [ ATIVAR ]                              │
        │                                                              │
        │  Edição 2026  ·  ● VIGENTE   [ manter como anterior ]        │
        └──────────────────────────────────────────────────────────────┘
```

**A ativação é uma troca de ponteiro** (`manuais_edicoes.status`), não uma cópia de arquivos.
É instantânea, atômica e reversível com um clique — que é justamente a garantia que você pediu
para o caso de algo dar errado.

### 8.3 Onde a estação de publicação roda

Duas formas, ambas previstas por `PUBLICACOES_MODO`:

1. **Script direto** (`PUBLICACOES_MODO` irrelevante) — `python scripts/publicacoes/publicar.py` no
   venv do projeto, na sua máquina. Funciona hoje, sem depender de nada.
2. **Instância local com UI** (`PUBLICACOES_MODO=publicacao`) — se o plano de
   `docs/backlog/Melhorias Futuras/implementacao_localhost.md` (SAA29 em Docker no MacBook,
   sincronizando pelo R2) for adiante, essa instância vira a estação natural: ela tem
   filesystem real, o DVD acessível e nenhum `timeout` de 30 s no caminho. Aí você tem
   **exatamente o botão que imaginou** — só que na instância certa. A instância do Railway
   sobe sempre com `PUBLICACOES_MODO=consulta` e **não expõe** as rotas de ingestão.

### 8.4 Guardar o pacote para reprocessar — sim, com três ajustes

Sua ideia de arquivar o ZIP é boa e vale a pena. Três correções de expectativa:

**a) Compressão.** PDF já é um formato comprimido. Um ZIP de 3 GB de PDFs costuma render
**5–15% de economia**, não 50%. O ganho real **não é tamanho** — é ter **1 objeto imutável com
1 hash** em vez de 12.100 objetos soltos. Isso é o que dá atomicidade ("ou veio tudo, ou não
veio"), verificação de integridade e reprocessamento determinístico. Vale por esses motivos,
não pelo espaço.

**b) Onde.** No **R2**, não no disco do Railway (efêmero — sumiria no próximo deploy) e nunca
dentro do banco. Em `var/publicacoes/pacotes/` só na máquina local, como cache.

**c) Custo.** R2 cobra ~US$ 0,015/GB/mês e **egress zero**. Três edições ≈ 9 GB ≈
**US$ 0,14/mês**. Irrelevante — guarde as 3 últimas com folga.

**Sobre a cópia-mestre:** o DVD físico já é o seu original. O snapshot no R2 protege contra
perda ou degradação da mídia óptica, que é um risco real na faixa de 5–10 anos. O resultado é
a regra 3-2-1 do `Runbook.MD` §6.1 satisfeita de forma natural: **DVD físico + snapshot ZIP no
R2 + acervo expandido no R2**.

**Reprocessar** vira um comando, sem precisar do DVD de novo:

```
python scripts/publicacoes/publicar.py --reprocessar 2027 --forcar-reindexacao
```

### 8.5 Dois ganhos que vêm de graça

**O relatório de diff.** Como o passo 2 já compara hashes, o sistema sabe exatamente o que
mudou. Isso produz, sem custo adicional, o documento que você provavelmente mais quer ter em
mãos depois de uma atualização anual:

> *Edição 2027 — 342 documentos revisados. Por capítulo ATA: 34 (RÁDIO-NAVEGAÇÃO) 41 revisados;
> 42 (AVIÔNICA INTEGRADA) 28 revisados; 24 (ELÉTRICO) 19 revisados; ...*

É material direto para briefar a equipe sobre o que mudou na manutenção naquele ano. Os
arquivos `.title` da Embraer, com a marcação `UNCHANGED`/`REVISED` na 3ª linha (RN-02),
**corroboram** o diff por hash — mas o hash é a fonte de verdade, porque não depende de a
Embraer ter atualizado o sidecar corretamente.

**Só o delta sobe.** Numa revisão anual típica a maior parte do acervo não muda. Se ~90%
ficarem inalterados, o upload anual real é da ordem de **300 MB, não 3 GB** — e o tempo do
passo 3 (extração de texto, a parte cara) cai na mesma proporção.

### 8.6 A edição anterior deve continuar acessível

Um ponto que a formulação "substituir a versão antiga" deixa implícito e que, em manutenção
aeronáutica, é melhor tornar explícito: **pode ser necessário saber qual revisão estava em
vigor quando um serviço foi executado.** Uma pane resolvida em março de 2027 seguiu o
procedimento da edição 2026, não da 2027.

Recomendação proporcional ao porte do sistema (sem virar um sistema de versionamento):

- manter **a edição vigente + a anterior** online, com a anterior sinalizada na UI como
  `REVISÃO ANTERIOR` (`PUBLICACOES_EDICOES_RETIDAS=2`);
- edições mais antigas ficam **apenas como snapshot ZIP** no R2 — recuperáveis se algum dia
  for preciso, sem ocupar índice nem UI;
- `publicacoes_acessos` grava a `edicao_id` consultada, o que fecha a rastreabilidade com custo
  quase zero e é coerente com a §4 do `RBAC.md` ("toda ação crítica deve ser auditável").

---

## 9. Publicações avulsas — BO, BS, NPO e BT

Requisito distinto do acervo do DVD, e a distinção é o ponto de partida do desenho.

### 9.1 Por que é uma entidade separada, não um "manual pequeno"

| | Manuais (DVD) | **Publicações avulsas** |
|---|---|---|
| Chegada | 1× por ano, em lote | ao longo do ano, uma a uma |
| Volume | ~12.100 documentos | dezenas a centenas por ano |
| Metadados | prontos (`.title`, XMLs) | **digitados por quem cadastra** |
| Texto | vetorial, extraível | **scan** — sem camada de texto |
| Busca | full-text no conteúdo | full-text no **cabeçalho digitado** |
| Se perder | reconstrói do DVD | **perda definitiva** |
| Onde mora | `catalog.db` (derivado) | **banco principal**, com backup |

Tratá-las como um tipo de manual seria forçar dados manuais para dentro de um pipeline
desenhado para extração automática. São dois problemas diferentes, com um único ponto de
encontro: a **tela de busca**.

### 9.2 Modelo proposto

O cabeçalho é digitado por quem cadastra — o desenho existe para tornar essa digitação curta e
a recuperação boa depois.

| Campo | Tipo | Observação |
|---|---|---|
| `tipo` | enum | **BO** · **BS** · **NPO** · **BT** · OUTRO — enum novo em `shared/core/enums.py` |
| `numero` | texto | ex.: `BS 314-24-0021` |
| `ano` | inteiro | filtro mais usado depois do tipo |
| `data_emissao` / `data_recebimento` | data | as duas importam: a segunda é a que conta para o esquadrão |
| `emissor` | texto | Embraer · COMGAP · GAP · Esquadrão · outro |
| `titulo` | texto | como consta no documento |
| `ementa` | texto longo | **o campo mais valioso** — 2 a 5 linhas do que o documento determina. É o que a busca vai encontrar, já que o conteúdo é scan. |
| `sistema_ata_id` | FK → `sistemas_ata` | **reusa a tabela que já existe** no módulo `panes` — o mesmo filtro ATA serve manuais e publicações |
| `aplicabilidade` | N:N → `aeronaves` | opcional; vazio = frota inteira |
| `status` | enum | `VIGENTE` · `CANCELADO` · `SUBSTITUIDO` |
| `substituida_por_id` | FK autorreferente | quando um BT substitui outro — a cadeia fica explícita |
| `anexos` | 1:N | o PDF escaneado + arquivos correlatos (planilha, foto, anexo técnico) |
| `cadastrada_por_id`, `criada_em` | auditoria | mesmo padrão dos demais módulos |

**RBAC proposto:** consultar → todos os perfis; cadastrar/editar → `EncarregadoInspetorOuAdmin`
(o atalho já existe em `dependencies.py`); excluir → `AdminRequired`, e **soft delete**, como
no resto do sistema.

### 9.3 Upload dos anexos — aqui **sim** passa pelo app

Diferente do pacote anual: são arquivos individuais e pequenos. Mas dois ajustes são
necessários:

1. **Limite próprio.** `max_upload_size_mb = 0.5` (500 KB) é adequado para foto de pane e
   pequeno demais para um boletim escaneado, que fica tipicamente entre **5 e 50 MB**. Daí
   `PUBLICACOES_AVULSAS_MAX_UPLOAD_MB` separado — sem afrouxar o limite global, que existe por um bom
   motivo.
2. **Não passar pelo pipeline de imagem.** `app/shared/services/image/pipeline.py` (conversão
   HEIC, otimização com `imgdiet`) foi feito para fotos de pane. Um PDF escaneado vai direto
   para o storage, sem reprocessamento.

`.pdf`, `.jpg` e `.png` já estão na allowlist de `file_validators.py` com validação de magic
bytes — **nenhuma mudança na superfície de segurança é necessária** aqui, ao contrário do ZIP
(§5.11).

### 9.4 Busca unificada, dois grupos de resultado

Um único campo de busca na página do módulo, resultados separados:

```
🔍 "gerador"                                          [ Todos ▾ ]

MANUAIS TÉCNICOS  (12)
  SUBJECT 24-31-00 — GERADOR PRINCIPAL
  AMM Parte I › Cap. 24 · pág. 7
  ...substituição do <mark>gerador</mark> principal deve...

PUBLICAÇÕES AVULSAS  (3)
  BS 314-24-0021 · Boletim de Serviço · 2026 · ATA 24 · ● VIGENTE
  Inspeção adicional dos terminais do <mark>gerador</mark> após 500 h
  📎 2 anexos
```

Tecnicamente são duas consultas independentes — FTS5 no `catalog.db` para os manuais, e uma
busca nos metadados no banco principal para as publicações. Como o volume de publicações é de
centenas (não milhares), **não precisa de FTS5**: `LIKE` com índice, ou FTS5 do banco
principal se um dia crescer. Isso mantém as publicações **100% portáveis para PostgreSQL**,
que é um requisito ativo do projeto (§5.3).

### 9.5 Sobre OCR

Uma observação técnica, e a decisão continua sendo sua: **scans são exatamente o caso de uso do
OCR** (`ocrmypdf`/Tesseract). O que costuma inviabilizar na prática é a qualidade da
digitalização — documentos tortos, com carimbo, fotocópia de fotocópia —, e você é quem conhece
o material.

De qualquer forma, **o cadastro manual do cabeçalho é a decisão certa como base**, mesmo que
OCR viesse depois: uma ementa escrita por quem entende do assunto recupera melhor do que texto
OCR ruidoso, e é o único jeito de ter tipo, número, vigência e aplicabilidade — que OCR nenhum
extrai de forma confiável.

E a porta fica aberta: o campo `has_text` já existe no desenho do acervo (E-01), então
adicionar OCR depois é **aditivo**, não uma reforma. Não é escopo agora.

### 9.6 Evolução natural (fora do MVP)

Boletins de Serviço frequentemente **determinam ação** em aeronaves específicas — e o
cumprimento precisa ser comprovado. O modelo acima já tem a aplicabilidade por aeronave, o que
deixa a porta aberta para um **controle de cumprimento de BS por matrícula** (qual aeronave
cumpriu, quando, por quem, com qual ordem de serviço).

Isso é requisito real de conformidade e conversa direto com a **v4.0 — Conformidade e
Formalismo** do `ROADMAP.md`. **Registrado como visão; não fazer agora** — o MVP é consultar,
não controlar cumprimento.

---

## 10. Plano de execução

Cinco marcos. **M1 é entregável sozinho e não depende de nenhuma decisão de infraestrutura.**

---

### M0 — Fundação e decisões (≈ 2 dias)

**Entregáveis**
- ADR-004 em `docs/architecture/adr/` registrando: módulo interno, índice em SQLite separado,
  indexação offline, acervo fora de `data/`.
- Decisão **D-S2** (biblioteca de extração) com benchmark real sobre 20 PDFs do FIM:
  qualidade do texto extraído + tempo.
- Esqueleto `app/modules/publicacoes/` com `__init__.py`, `router.py` vazio registrado e
  `PUBLICACOES_ENABLED` em `config/__init__.py`.
- `.gitignore`: `var/publicacoes/`.

**Gate:** `ruff` + `mypy` + suíte atual (205+ testes) verdes com o módulo registrado e vazio.

---

### M1 — Piloto FIM: busca de falha → procedimento (≈ 1 semana) ⭐

Este é o marco que **entrega valor real com risco quase zero**. Usa os **411 PDFs (14 MB)**
e o `fim.json` **que já estão no repositório**. Nenhuma mudança de infraestrutura.

**Entregáveis**
- `scripts/publicacoes/indexar.py`: varre o acervo, extrai texto por página, grava `catalog.db`
  (`pages` + `pages_fts`) e o catálogo leve no banco principal. Idempotente, `--dry-run`,
  resiliente a arquivo ruim (E-02).
- Migration Alembic: `manuais`, `manuais_documentos`, `manuais_fim_map`. **Sem FTS5.**
- `search.py`: FTS5 com BM25, `snippet()` com `<mark>`, número da página, sanitização (RN-10).
- `router.py`: `/publicacoes/api/busca`, `/publicacoes/api/fim`, `/publicacoes/api/status`,
  `/publicacoes/doc/{id}/pdf`.
- Páginas: lista/busca + viewer PDF.js com `#page=N`; item no `<nav>` do `base.html`;
  atalho em `/m/`.
- Ingestão do `fim.json` → `manuais_fim_map`, ligando 1.377 mensagens a 249 documentos.
- Auditoria de acesso a documento (`publicacoes_acessos`).
- Testes: RN-02/RN-07 com fixtures reais; E-02, E-06, E-08, E-10; CA-01 e CA-04.

**Gate de saída (verificável)**
- Buscar `ADC 001` → procedimento `34-15-00-810-801-A` → PDF abre **na página do trecho**;
- busca full-text `sangria`/`SANGRIA`/`sangría` retorna o mesmo conjunto (CA-04);
- PDF renderiza no viewer **sem violação de CSP no console** (§5.5) — e o delta de CSP
  aplicado está documentado em `docs/methodology/CSP.md` na mesma PR;
- p95 da busca < 300 ms sobre o corpus FIM;
- suíte completa verde nas **duas** pontas da matriz de CI (SQLite **e** Postgres).

---

### M2 — Integração com panes e inspeções (≈ 1 semana)

O momento em que o módulo deixa de ser "um buscador" e vira parte do fluxo de trabalho.

**Entregáveis**
- Na tela de **detalhe da pane**: bloco "Procedimentos FIM do ATA XX" filtrado pelo
  `sistema_ata` da pane (os 8 códigos seedados existem todos no acervo — §2.2).
- No **registro de pane**: campo de busca por mensagem de falha; ao casar com `fim.json`,
  sugere o procedimento e permite anexar a referência à pane.
- Na **execução de inspeção**: link do item de checklist para o documento correspondente.
- Favoritos e histórico por usuário (`publicacoes_favoritos`) — substitui o
  `TechDataFavoritesTouch` do sistema legado com conta real, não `localStorage`.
- Filtros de busca por manual / capítulo / ATA.

**Gate:** um mantenedor consegue, a partir de uma pane aberta, chegar ao procedimento correto
**sem digitar nada**.

---

### M3 — Publicações avulsas: BO, BS, NPO, BT (≈ 1 semana)

**Independente de tudo o que envolve os 3 GB** — não depende de D-S1 nem de D-S4, e pode ser
feito em paralelo com o M2 ou antes dele, conforme a urgência operacional.

**Entregáveis**
- Migration Alembic: `publicacoes_avulsas`, `publicacao_avulsa_anexos`,
  `publicacao_avulsa_aeronaves`; enum `TipoPublicacao` em `shared/core/enums.py`.
- CRUD com RBAC (`EncarregadoInspetorOuAdmin` para cadastro, soft delete por Admin).
- Formulário de cadastro com o cabeçalho completo (§9.2) + upload de anexos com limite próprio
  (`PUBLICACOES_AVULSAS_MAX_UPLOAD_MB`), fora do pipeline de imagem.
- Cadeia de substituição (`substituida_por_id`) e filtro de vigência.
- Busca nos metadados integrada à tela do módulo, em grupo separado (§9.4).
- Testes: cadastro, vigência, substituição, RBAC, limite de upload, soft delete.

**Gate:** cadastrar um BS real com anexo escaneado e encontrá-lo por número, por ATA e por
palavra da ementa — nos três casos.

---

### M4 — Acervo completo e ciclo do DVD (≈ 2 semanas + decisão D-S1) 🔒

**Só começa depois de D-S1 e D-S4 respondidas.** É aqui que entram os 3 GB, o `merge_data.py`
da Fase 0 externa, a migração do storage para R2 e o ciclo anual da §8.

**Entregáveis**
- `scripts/publicacoes/merge_data.py` conforme RN-08 (hash, `_merge_conflicts/`, `merge_report.txt`,
  `--dry-run` por padrão) — o script da Fase 0 externa, aproveitado quase como está.
- `scripts/publicacoes/publicar.py` — a **estação de publicação** da §8.2: inventário, diff por
  hash, extração incremental, `catalog.db` da edição, snapshot ZIP, upload do delta para o R2 e
  `relatorio_publicacao_<ano>.md`. Com `--reprocessar <edicao>`.
- Parsers completos: `manual_details.xml`, `manual_type.xml`, `collections.ini` (cp1252),
  `version/*.txt` → RN-03, RN-04, RN-06.
- Tabela `manuais_edicoes` + card **"Publicações"** em `/configuracoes` com ativar/reverter e
  visualização do relatório de diff (§8.2).
- Storage em R2 com URL pré-assinada; `PUBLICACOES_STORAGE=r2`; retenção de edições e snapshots.
- Runbook interno: `docs/guides/operacao_publicacoes.md`, adaptando a §8 (triagem) do
  `Runbook.MD` externo e substituindo §2/§3/§4/§6.2/§7 pelo procedimento real do Railway.
- Medição de `documentos_sem_texto` no acervo completo → dimensiona a necessidade de OCR.

**Gate:** publicar uma edição de ponta a ponta a partir da mídia, **ativar**, conferir o
relatório de diff, **reverter** para a anterior e reativar — tudo sem downtime e com consumo de
memória do app **sem regressão** frente ao baseline do Railway.

---

### M5 — Fase 3 / RAG 🔒 **fora do plano de execução**

Documentada como visão em `RAG.MD`. **Não entra em roadmap** enquanto **D-S3** não for
formalmente respondida (§5.10). Se for autorizada: as regras R1–R4 do `RAG.MD` §2 são
inegociáveis, o golden set de 30–50 perguntas é pré-requisito de entrada, e a busca híbrida
(degrau 1) deve ser entregue e validada antes de qualquer `/api/ask`.

---

### Resumo de esforço

| Marco | Esforço | Depende de | Entrega valor sozinho? |
|---|---|---|---|
| M0 — fundação | ~2 dias | D-S2 | não (fundação) |
| **M1 — piloto FIM** | **~1 semana** | **nada** | **✅ sim — alto** |
| M2 — integração panes/inspeções | ~1 semana | M1 | ✅ sim |
| **M3 — publicações BO/BS/NPO/BT** | **~1 semana** | **M0** (nem M1) | **✅ sim — alto** |
| M4 — acervo completo + ciclo DVD | ~2 semanas | **D-S1, D-S4** | ✅ sim |
| M5 — RAG | — | **D-S3** | congelado |

**Caminho até valor operacional: ~1 semana e meia (M0+M1), sem tocar em infraestrutura.**

M2 e M3 são independentes entre si — a ordem entre eles é escolha sua, conforme o que dói mais
na operação hoje: ligar a pane ao procedimento (M2) ou parar de perder boletim em pasta de rede
(M3).

---

## 11. Riscos e mitigações

| # | Risco | Prob. | Impacto | Mitigação |
|---|---|:--:|:--:|---|
| R1 | Acervo de 3 GB inviabiliza o deploy atual | **Alta** | **Alto** | Faseamento: M1/M2 com 14 MB; D-S1 decidida com o sistema já provado |
| R2 | PDF.js barrado pela CSP / `X-Frame-Options` | Média | Médio | Item de aceite explícito no M1; PDF.js em canvas (sem iframe) evita o XFO por construção |
| R3 | Índice FTS5 quebra a matriz Postgres do CI | Média | Alto | `catalog.db` separado, fora do Alembic (§5.3) — decisão já tomada |
| R4 | Backup R2 inflado por índice grande | Média | Alto | Índice nunca entra no `DATABASE_URL` (§5.3) |
| R5 | Exposição AGPL do PyMuPDF | Média | Médio | D-S2 antes da Fase 1; `pypdfium2` como alternativa avaliada no piloto |
| R6 | Indexação matando worker (`timeout=30`) | **Alta** se feita in-process | Alto | Indexação **offline** por construção (§5.4) |
| R7 | Módulo vira casca abandonada (precedente `encarregado`) | Média | Médio | M1 fechado e útil por si só; nada é *merged* sem testes e gate verde |
| R8 | Conteúdo controlado trafegando por API externa (RAG) | Baixa (se M4 congelado) | **Muito alto** | M4 fora do roadmap até D-S3 |
| R9 | Divergência de padrão (htmx/Tailwind) criando 2º dialeto de frontend | Média | Médio | Decisão explícita §5.7: Vanilla JS/CSS |
| R10 | Acervo crescendo dentro de `docs/` e inflando a imagem Docker | Média | Médio | Mover para `var/publicacoes/` no M0; `.dockerignore` já cobre `var/` |
| R11 | Habilitar `.zip` na allowlist abre zip-slip / zip-bomb | Média | Alto | **Não habilitar** — o pacote nunca sobe pelo app (§5.11, §8.1) |
| R12 | Publicação anual mal-sucedida derruba o acervo vigente | Baixa | Alto | Edição nova só entra em vigor por **ativação explícita**; reverter é 1 clique; snapshot permite reprocessar (§8.4) |
| R13 | Perda das publicações avulsas (dado insubstituível) | Baixa | **Muito alto** | Ficam no banco principal, dentro do backup R2 já existente; soft delete, nunca hard delete (§6.2) |
| R14 | Degradação da mídia óptica (DVD) ao longo dos anos | Média (5–10 anos) | Alto | Snapshot ZIP no R2 fecha a regra 3-2-1 (§8.4) |
| R15 | Ementa mal preenchida torna a publicação inencontrável | **Alta** | Médio | Ementa como campo obrigatório com mínimo de caracteres; tipo/número/ano/ATA dão caminhos de busca alternativos que não dependem de texto livre |

---

## 12. Anti-escopo (o que **não** fazer)

- ❌ **Não** subir Caddy, `docker-compose` próprio ou segundo processo. O SAA29 já tem
  ingress e TLS pelo Railway; Range funciona no Starlette (verificado).
- ❌ **Não** criar uma segunda aplicação FastAPI dentro do repositório.
- ❌ **Não** colocar `pages`/`pages_fts` no banco principal nem em migration Alembic.
- ❌ **Não** usar a pasta `data/` da raiz (é o volume do banco).
- ❌ **Não** indexar dentro do processo web nem no `lifespan`.
- ❌ **Não** introduzir htmx nem Tailwind.
- ❌ **Não** servir PDFs sem autenticação, em nenhum ambiente.
- ❌ **Não** passar token JWT por query string para o viewer (cookie same-origin resolve).
- ❌ **Não** iniciar qualquer trabalho de RAG antes de D-S3.
- ❌ **Não** portar `Runbook.MD` §2/§3/§4 como está — descreve uma infraestrutura que não existe aqui.
- ❌ **Não** subir o acervo anual (pastas do DVD ou ZIP de GB) pelo navegador (§5.11).
- ❌ **Não** adicionar `.zip` à allowlist de upload sem validador de magic bytes — e, com o
  desenho da §8, não há motivo para adicioná-lo.
- ❌ **Não** descartar a edição anterior do acervo ao publicar uma nova (§8.6).
- ❌ **Não** guardar snapshots ZIP no filesystem do Railway (efêmero) nem dentro do banco.
- ❌ **Não** modelar as publicações avulsas como um tipo de manual — são dado de usuário, com
  criticidade e ciclo de vida diferentes (§9.1).
- ❌ **Não** afrouxar `MAX_UPLOAD_SIZE_MB` global para acomodar boletins escaneados — limite
  próprio do módulo (§9.3).
- ❌ **Não** implementar controle de cumprimento de BS por aeronave no MVP (§9.6).

---

## 13. Conclusão

**Incorporar: sim.** O domínio pede, a stack aceita, e o SAA29 resolve de graça a maior
pendência do projeto externo (autenticação, D-02) além de eliminar outra (VPS/domínio, D-04).

**Do jeito que está escrito: não.** O `Projeto.MD` e o `Runbook.MD` assumem uma VPS dedicada
com disco persistente, Caddy e acervo no filesystem. O SAA29 vive num Railway efêmero com
2 workers, `timeout=30s` e banco que viaja para o R2 a cada 120 segundos. Três decisões
resolvem o descompasso e são a espinha dorsal deste plano:

1. **índice FTS5 em arquivo SQLite dedicado**, fora do Alembic e fora do backup R2;
2. **indexação offline**, nunca dentro do processo web;
3. **acervo fora do repositório e fora de `data/`** — R2 na produção, `var/publicacoes/` em dev.

**E há um atalho que muda a natureza do risco:** o SAA29 **já tem** 411 PDFs do FIM com
camada de texto verificada, 1.377 mensagens de falha mapeadas e 98,4% de cobertura
procedimento→arquivo — tudo somando 14 MB. Isso é uma amostra representativa e um caso de uso
de alto valor operacional que cabe no deploy atual **sem nenhuma mudança de infraestrutura**.

Comece por aí. Em cerca de uma semana e meia o mantenedor lê "ADC 001" no cockpit e abre o
procedimento na página certa, pelo celular, dentro do SAA29. Com isso funcionando e medido,
a conversa sobre os 3 GB deixa de ser uma aposta arquitetural e vira uma decisão de custo de
armazenamento — que é uma decisão muito mais fácil de tomar.

**Sobre o ciclo anual do DVD:** o botão que você imaginou existe, mas ele **ativa** em vez de
receber. A parte pesada roda na sua máquina, com o DVD na mão, no fim de semana — e o SAA29
só recebe o resultado pronto, com um clique reversível. Isso é mais simples de construir,
incomparavelmente mais seguro, e ainda dá dois brindes: **só o delta sobe** (a maior parte do
acervo não muda entre revisões) e todo ano você ganha um **relatório do que mudou, por
capítulo ATA**.

**Sobre BO, BS, NPO e BT:** foi uma adição acertada, e é bom que tenha vindo agora — porque
esses documentos são o oposto dos manuais em quase tudo que importa para o desenho. Não têm
texto extraível, não vêm com metadados, chegam avulsos, e são os únicos dados de todo o módulo
que **não podem ser reconstruídos** se forem perdidos. Por isso vivem no banco principal, com
backup, e não no índice descartável. Melhor ainda: **é o marco que menos depende de decisões
pendentes** — não precisa dos 3 GB, não precisa do R2, não precisa de nada além da fundação.

---

## 14. Próxima ação recomendada

Responder **D-S2** (biblioteca de extração de PDF: PyMuPDF/AGPL vs. pypdfium2/Apache-2.0) e
autorizar o **M0+M1**. Se as publicações avulsas doerem mais no dia a dia do que a busca nos
manuais, **M3 pode vir antes do M2** — ele só depende do M0.

D-S1, D-S3, D-S4 e D-S5 não bloqueiam nada até o M4 e podem ser decididas com o piloto já
rodando. D-S6 é uma linha de código, mas a decisão é sua.
