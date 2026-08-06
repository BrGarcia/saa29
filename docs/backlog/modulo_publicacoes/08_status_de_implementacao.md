# Status de Implementação — Módulo `publicacoes`

> **Este é o único documento desta pasta que muda com o código.** Os outros sete são decisões
> fechadas; este é o painel que responde "em que ponto estamos".
>
> Espelha as tarefas de [`04_plano_de_execucao.md`](04_plano_de_execucao.md) **na mesma numeração** —
> se as duas listas divergirem, o plano é a referência do *escopo* e este documento é a referência
> do *progresso*.
>
> **Como atualizar:** ao concluir uma tarefa, troque o status e preencha a coluna *Evidência* com o
> arquivo ou teste que prova a conclusão. Status sem evidência verificável não conta como ✅ — foi
> essa disciplina que pegou o B7 (índice que "existe" e não busca nada).
>
> **Última atualização:** 05/08/2026 · branch `fix/ci-baseline-verde` · 533 testes verdes ·
> `ruff check .` limpo

---

## Painel

| Marco | Escopo | Progresso | Estado |
|---|---|---|---|
| **M0** — Fundação | 8 tarefas | 8/8 | ✅ **Concluído** |
| **M1** — Piloto FIM ⭐ | 15 tarefas | 15/15 | ✅ **Concluído** — CSP verificada por leitura de código, não por navegador real (ver dívidas) |
| **M2** — Avulsas (BO/BS/NPO/BT) | 10 tarefas | 10/10 | ✅ **Concluído** |
| **M3** — Integração panes/inspeções | 5 tarefas | 0/5 | ⚪ Não iniciado — depende do M1 |
| **M4** — Acervo completo + ciclo DVD | 8 tarefas | 0/8 | 🔒 Bloqueado por D-04 (VPS), exceto a tarefa 1 |
| **M5** — RAG | — | — | 🔒 Congelado até D-S3 |

Legenda: ✅ concluído · 🔵 em execução · ⚪ não iniciado · 🔒 bloqueado · ⚠️ parcial

---

## M0 — Fundação ✅

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | ADR-004 com as 4 decisões + `pypdfium2` | ✅ | `docs/architecture/adr/004-modulo-publicacoes.md` |
| 2 | Normalizar `var/Publicações/` → `var/publicacoes/acervo/` | ✅ | Diretório no disco; 34 manuais em `acervo/Manuais/` |
| 3 | `.gitignore` sem acento (`var/publicacoes/`) | ✅ | `.gitignore:60` — `git check-ignore` confirma |
| 4 | Esqueleto do módulo | ✅ | `app/modules/publicacoes/__init__.py`, `router.py` |
| 5 | Registro nos 5 pontos | ✅ | `main.py:23,40,63,157` + `migrations/env.py:32` |
| 6 | `PUBLICACOES_*` em `Settings` + `.env.example` | ✅ | `app/bootstrap/config/__init__.py:88-123` |
| 7 | `pypdfium2` pinado | ✅ | `requirements.txt` — `pypdfium2==5.12.1` |
| 8 | `categorias_manuais.toml` com os 34 manuais | ✅ | `config/categorias_manuais.toml`; teste afirma os 34 |

**Gate:** ✅ `ruff` limpo · suíte verde · `git status` sem `var/publicacoes` rastreado ·
`API_PREFIXES` recebeu `/publicacoes/api/` (não `/publicacoes/` — risco R20 evitado).

---

## M1 — Piloto FIM ✅ 15/15

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | `catalog.py`: parser do índice Lucene | ✅ | `catalog.py:91-184`; 38 testes em `tests/unit/test_publicacoes_catalog.py` |
| 2 | `catalog.py`: ingestão de `fim.json` | ✅ | `catalog.py:362-400`; regressão 1.377/253 contra o arquivo real |
| 3 | Migration `manuais*` | ✅ | `migrations/versions/20260805_1703_067e1a767c1f_*.py` — `upgrade`/`downgrade` testados |
| 4 | `indexar.py` (extração por página, idempotente, `--dry-run`) | ✅ | `scripts/publicacoes/indexar.py`; execução real: 411 PDFs em 2,6 s |
| 5 | `search.py` (sqlite3 puro, BM25, snippet, RN-10) | ✅ | `app/modules/publicacoes/search.py` |
| 6 | Rotas `/api/busca`, `/api/fim`, `/api/status`, `/doc/{id}/pdf` | ✅ | `router.py`; 4 rotas registradas |
| 7 | PDF.js vendorizado + viewer em canvas | ✅ | `app/web/static/js/pdfjs/` (pdfjs-dist 6.2.108, Apache-2.0); `publicacoes/viewer.html` + `publicacoes_viewer.js` — nunca iframe (D-F) |
| 8 | Páginas (lista/busca), item no `<nav>`, `/m/publicacoes` | ✅ | `publicacoes/lista.html`, `mobile/publicacoes.html`, item em `base.html` e `base_mobile.html`, rotas em `pages/router.py`/`mobile_router.py` |
| 9 | Auditoria de acesso (`publicacoes_acessos`) | ✅ | `service.py:registrar_acesso`; teste afirma o snapshot do título |
| 10 | Medir CSP e documentar o delta | ⚠️ | `worker-src 'self'` aplicado e documentado em `docs/methodology/CSP.md` §5 — **por leitura do código-fonte do PDF.js, não por console de navegador real** (ver dívidas) |
| 11 | Verificar o iframe de PDF em `panes_detalhe.js` | ✅ | **Confirmado** — `docs/backlog/revisor/achados_panes_iframe_pdf.md` |
| 12 | Testes: E-02, E-06, E-08, E-10; CA-01 e CA-04 | ⚠️ | 43 testes em `tests/integration/test_publicacoes_busca.py` — ver dívidas abaixo |
| 13 | Tabela `documents` + `rebuild`/`optimize` do FTS5 | ✅ | `indexar.py:finalizar_catalog`; teste prova o modo de falha do B7 |
| 14 | Round-trip de UUID entre os dois bancos | ✅ | `test_round_trip_de_uuid_entre_os_dois_bancos` + o teste que mostra o hex sem hífens |
| 15 | Rate limit na busca (`30/minute`) | ✅ | `router.py` — `@limiter.limit("30/minute")` com `request: Request` |

Endpoint adicional não previsto no plano original, necessário para o cabeçalho do viewer:
`GET /publicacoes/api/documentos/{doc_id}` (título, manual, capítulo, e o banner de
"REVISÃO ANTERIOR" com link para o equivalente vigente — `service.obter_equivalente_vigente`,
testado em `test_equivalente_vigente_aponta_da_edicao_antiga_para_a_nova`).

### Gate de saída do M1

| Critério | Estado | Medido |
|---|:--:|---|
| `ADC 001` → `34-15-00-810-801-A` → PDF **na página do trecho** | ✅ | `viewer_url` termina em `#page=N`; afirmado em teste |
| `sangria`/`SANGRIA`/`sangría` → mesmo conjunto (CA-04) | ✅ | 4 variações parametrizadas, mesmo `total` e mesma ordem |
| PDF renderiza no viewer **sem violação de CSP** | ⚠️ | Delta aplicado e justificado por leitura de código; **não confirmado em console de navegador real** — ver dívidas |
| p95 da busca < 300 ms sobre o corpus FIM | ✅ | **p95 = 6,7 ms** (200 execuções, 20 termos, 411 docs / 1.186 páginas) |
| `ruff check .` + `pytest` verdes | ✅ | 502 testes, 0 falhas |

### Bugs antecipados (`07_revisao_pre_implementacao.md`) — situação real

| # | Bug | Situação |
|---|---|---|
| B1 | PK composta nullable em favoritos | ⏭️ N/A no M1 — a tabela é do M3 |
| B2 | `document_id` colidiria entre edições | ✅ Edição no input do UUID v5; teste afirma IDs distintos por edição |
| B3 | FK de `ata_codigo` quebraria a indexação | ✅ `String(4)` indexado sem FK; 411 documentos indexados sem falha |
| B4 | Auditoria se autodestruía com CASCADE | ✅ `SET NULL` + snapshot do título |
| B5 | Formato de UUID divergente entre bancos | ✅ **Confirmado por teste** — o hex sem hífens não bate com a forma canônica |
| B6 | Filtros `manual`/`chapter` inimplementáveis | ✅ Tabela `documents` no `catalog.db`; filtro testado |
| B7 | FTS5 não se popula e a contagem engana | ✅ **Reproduzido em teste** — sem `rebuild`, `count(*)` acerta e `MATCH` dá 0 |
| B8 | `snippet` com `<mark>` é XSS | ⚠️ Metade feita — a API já emite `\x02`/`\x03` e teste afirma que não há HTML; **a outra metade (troca por `<mark>` no JS) chega com a tarefa 8** |

---

## M2 — Publicações avulsas ✅ 10/10

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | Enum `TipoPublicacao`, `StatusPublicacaoAvulsa` | ✅ | `app/shared/core/enums.py` |
| 2 | Migration: `publicacoes_avulsas`, anexos, aeronaves N:N | ✅ | `migrations/versions/20260805_2141_7daf099e56ed_*.py` — `upgrade`/`downgrade` testados |
| 3 | `avulsas.py` + `service.py`: CRUD, cadeia `substituida_por_id`, filtro de vigência | ✅ | `app/modules/publicacoes/avulsas.py` |
| 4 | RBAC: `EncarregadoInspetorOuAdmin` cadastro/edição, `AdminRequired` + soft delete exclusão (D-S6) | ✅ | `router.py`; testado nos dois sentidos da fronteira (Mantenedor fora, Encarregado dentro) |
| 5 | Upload de anexo fora do pipeline de imagem | ✅ | `router.py:upload_anexo_avulsa` — `validate_file_upload` + `ler_upload_com_limite`, sem `shared/services/image/pipeline.py` |
| 6 | Busca por metadados: `LIKE`/`ILIKE` com `escape_like` | ✅ | `avulsas.py:buscar_avulsas` |
| 7 | Páginas: `avulsas.html`, `publicacoes_avulsas.js` | ✅ | `app/web/templates/publicacoes/avulsas.html` |
| 8 | Testes: cadastro, vigência, substituição, RBAC, limite de upload, soft delete | ✅ | 27 testes em `tests/unit/test_publicacoes_avulsas.py` |
| 9 | Teste de XSS (ementa com `<img onerror>`) | ✅ | 4 testes em `tests/security/test_publicacoes_xss.py` — servidor nunca emite `<mark>`, e a renderização do cliente é simulada em Python para provar que o payload não sobrevive como tag |
| 10 | Rate limit no upload de anexo (`10/minute`) | ✅ | `router.py` — `@limiter.limit("10/minute")` |

**Achado não previsto no plano:** o filtro `texto` da busca precisava de algum destaque para ser
útil (mostrar por que o resultado casou), mas o plano original não detalhava isso para avulsas —
só para o acervo A. Implementado um `snippet` com a MESMA receita de sentinela `\x02`/`\x03` do
`catalog.db` (`avulsas.construir_snippet`), reaproveitando a função `snippetSeguro` do cliente
para os dois acervos.

### Gate do M2

Cadastrar um BS real com anexo escaneado e encontrá-lo por número, por ATA e por palavra da
ementa — nos três casos. ✅ Verificado por teste único que cadastra uma publicação, anexa um PDF,
vincula a um `sistema_ata`, e confirma os três caminhos de busca no mesmo cadastro
(`test_gate_m2_encontrar_por_numero_ata_e_ementa`).

---

## M3 — Integração com panes e inspeções ⚪ 0/5

Não iniciado. Depende do M1 concluído.

---

## M4 — Acervo completo e ciclo do DVD 🔒 0/8

Bloqueado por **D-04** (provedor de VPS), com uma exceção registrada no plano: a **tarefa 1**
(rodar `indexar.py` sobre `var/publicacoes/acervo/Manuais/` inteiro) **não é trabalho novo de
código** e pode acontecer a qualquer momento — o script já aceita o diretório do acervo como
entrada e reconhece o layout de um diretório por manual.

Ordem de grandeza do que isso indexaria, medida no acervo em disco: **34 manuais, 5.724 PDFs**
(contra 411 do piloto).

---

## Dívidas conhecidas e parciais

| Item | O que falta | Onde |
|---|---|---|
| **E-10** (acentos/espaços no caminho) | Nenhum teste cobre um `file_key` acentuado ponta a ponta. O caso real existe e está versionado: `docs/fim/Código de Panes.PDF`. Basta incluí-lo na amostra do teste de integração. | `tests/integration/test_publicacoes_busca.py:PDFS_AMOSTRA` |
| **CA-01** (p95 < 300 ms) | O número foi **medido** (6,7 ms), mas não é afirmado por teste — regressão de performance passaria despercebida. | idem |
| **Verificação visual do viewer/CSP** | O delta de CSP (`worker-src 'self'`) foi justificado por leitura do código-fonte do PDF.js, não por abrir o console de um navegador real contra a aplicação rodando — esta sessão não teve acesso a um navegador. Antes de dar o item por definitivamente fechado, alguém precisa abrir `/publicacoes/viewer/{id}` de um documento real e checar o console por violações de CSP. Passo a passo em `docs/methodology/CSP.md` §5. | `docs/methodology/CSP.md` §5 |
| **PDF.js sem `cmaps`/`standard_fonts`** | Só o núcleo (`pdf.min.mjs` + `pdf.worker.min.mjs`) foi vendorizado. Um PDF que dependa de fonte padrão não embutida (raro nos manuais, que embutem fonte) pode renderizar com fallback do navegador em vez da fonte exata. | `app/web/static/js/pdfjs/README.md` |
| **Frontend sem verificação visual em navegador** | `publicacoes/lista.html`, `viewer.html`, `mobile/publicacoes.html` e `avulsas.html` foram implementados e passam em testes de fumaça (200 + `text/html`), mas nenhum foi aberto num navegador real nesta sessão — não há confirmação visual de layout, dos modais de cadastro/anexo de avulsas, nem da experiência mobile. | Todos os templates de `app/web/templates/publicacoes/` e `mobile/publicacoes.html` |
| **`manuais_edicoes`** | A tabela existe e é populada com a linha sintética `piloto-fim`, mas `snapshot_key`, `hash_sha256` e `relatorio_diff` seguem nulos — ganham uso só no M4. | Esperado, não é dívida real |

---

## Próxima tarefa

**M3 — Integração com panes e inspeções.** Depende do M1 (já concluído): o bloco "Procedimentos FIM
do ATA XX" e a sugestão por mensagem de falha precisam do viewer existir de verdade para fazer
sentido (link que abre em algum lugar). Cinco tarefas: bloco no detalhe da pane, busca por mensagem
de falha sugerindo procedimento, link do checklist de inspeção, favoritos (`publicacoes_favoritos`,
achado B1 — PK surrogate + CheckConstraint XOR), e filtros de busca por manual/capítulo/ATA na tela
de busca (exige levar `ata_codigo` para o `catalog.db`, que hoje só tem `manual_codigo`/`capitulo`).

Depois do M3, **M4** (o que não depende de D-04): rodar `indexar.py` sobre o acervo completo
(34 manuais, 5.724 PDFs — tarefa 1, não é trabalho novo de código), e os scripts `publicar.py`/
`merge_data.py`, que podem ser escritos e testados localmente mesmo sem a decisão de VPS fechada.
