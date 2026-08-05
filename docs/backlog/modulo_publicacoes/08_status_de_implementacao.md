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
> **Última atualização:** 05/08/2026 · branch `fix/ci-baseline-verde` · 494 testes verdes ·
> `ruff check .` limpo

---

## Painel

| Marco | Escopo | Progresso | Estado |
|---|---|---|---|
| **M0** — Fundação | 8 tarefas | 8/8 | ✅ **Concluído** |
| **M1** — Piloto FIM ⭐ | 15 tarefas | 12/15 | 🔵 **Em execução** — falta a camada visual |
| **M2** — Avulsas (BO/BS/NPO/BT) | 10 tarefas | 0/10 | ⚪ Não iniciado — **não depende do M1** |
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

## M1 — Piloto FIM 🔵 12/15

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | `catalog.py`: parser do índice Lucene | ✅ | `catalog.py:91-184`; 38 testes em `tests/unit/test_publicacoes_catalog.py` |
| 2 | `catalog.py`: ingestão de `fim.json` | ✅ | `catalog.py:362-400`; regressão 1.377/253 contra o arquivo real |
| 3 | Migration `manuais*` | ✅ | `migrations/versions/20260805_1703_067e1a767c1f_*.py` — `upgrade`/`downgrade` testados |
| 4 | `indexar.py` (extração por página, idempotente, `--dry-run`) | ✅ | `scripts/publicacoes/indexar.py`; execução real: 411 PDFs em 2,6 s |
| 5 | `search.py` (sqlite3 puro, BM25, snippet, RN-10) | ✅ | `app/modules/publicacoes/search.py` |
| 6 | Rotas `/api/busca`, `/api/fim`, `/api/status`, `/doc/{id}/pdf` | ✅ | `router.py`; 4 rotas registradas |
| 7 | **PDF.js vendorizado + viewer em canvas** | ⚪ | — |
| 8 | **Páginas (lista/busca), item no `<nav>`, `/m/publicacoes`** | ⚪ | — |
| 9 | Auditoria de acesso (`publicacoes_acessos`) | ✅ | `service.py:registrar_acesso`; teste afirma o snapshot do título |
| 10 | **Medir CSP e documentar o delta** | ⚪ | Bloqueado pela 7 — sem viewer não há o que medir |
| 11 | Verificar o iframe de PDF em `panes_detalhe.js` | ✅ | **Confirmado** — `docs/backlog/revisor/achados_panes_iframe_pdf.md` |
| 12 | Testes: E-02, E-06, E-08, E-10; CA-01 e CA-04 | ⚠️ | 35 testes em `tests/integration/test_publicacoes_busca.py` — ver dívidas abaixo |
| 13 | Tabela `documents` + `rebuild`/`optimize` do FTS5 | ✅ | `indexar.py:finalizar_catalog`; teste prova o modo de falha do B7 |
| 14 | Round-trip de UUID entre os dois bancos | ✅ | `test_round_trip_de_uuid_entre_os_dois_bancos` + o teste que mostra o hex sem hífens |
| 15 | Rate limit na busca (`30/minute`) | ✅ | `router.py` — `@limiter.limit("30/minute")` com `request: Request` |

### Gate de saída do M1

| Critério | Estado | Medido |
|---|:--:|---|
| `ADC 001` → `34-15-00-810-801-A` → PDF **na página do trecho** | ✅ | `viewer_url` termina em `#page=N`; afirmado em teste |
| `sangria`/`SANGRIA`/`sangría` → mesmo conjunto (CA-04) | ✅ | 4 variações parametrizadas, mesmo `total` e mesma ordem |
| PDF renderiza no viewer **sem violação de CSP** | ⚪ | Bloqueado pelas tarefas 7 e 10 |
| p95 da busca < 300 ms sobre o corpus FIM | ✅ | **p95 = 6,7 ms** (200 execuções, 20 termos, 411 docs / 1.186 páginas) |
| `ruff check .` + `pytest` verdes | ✅ | 494 testes, 0 falhas |

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

## M2 — Publicações avulsas ⚪ 0/10

Não iniciado. **Independente do M1** — pode começar a qualquer momento; usa só o banco principal,
sem `catalog.db` e sem `pypdfium2`. Os enums `TipoPublicacao`/`StatusPublicacaoAvulsa` (tarefa 1)
ainda **não** existem em `app/shared/core/enums.py` — só `RevisionStatus` e `StatusEdicao`, que o M1
precisava.

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
| **B8** (segunda metade) | O `escapeHtml` + troca de sentinela por `<mark>` no cliente só existe quando houver cliente. | Chega com a tarefa 8 |
| **`manuais_edicoes`** | A tabela existe e é populada com a linha sintética `piloto-fim`, mas `snapshot_key`, `hash_sha256` e `relatorio_diff` seguem nulos — ganham uso só no M4. | Esperado, não é dívida real |

---

## Próxima tarefa

Duas frentes possíveis, ambas destravadas — a escolha é de prioridade, não de dependência:

1. **Fechar o M1** (tarefas 7, 8 e 10): vendorizar o PDF.js, viewer em canvas, páginas, item de nav
   e atalho mobile, e então medir a CSP no console com o build escolhido. É o que transforma uma API
   que funciona em algo que o mecânico usa. ⚠️ Exige baixar o PDF.js — a CSP não permite CDN.
2. **Começar o M2** (avulsas): entrega valor operacional sozinho, sem depender do M1 e sem tocar em
   frontend novo além de uma tela de lista.

O plano de execução recomenda **M1 antes de M2** por ordem de marco, mas registra explicitamente que
"M1 e M2 dependem só de M0" — inverter não quebra nada.
