# Status de Implementação — Módulo `publicacoes`

> **Este é o painel que responde "em que ponto estamos".** Muda a cada tarefa concluída, junto com
> [`09_plano_configuracoes.md`](09_plano_configuracoes.md) (**o plano de trabalho corrente** — o
> que fazer agora, em ordem) e
> [`03_especificacao_tecnica.md`](03_especificacao_tecnica.md) (contrato). O resto da pasta é
> registro datado — ver a tabela de status em [`00_indice.md`](00_indice.md).
>
> Espelha as tarefas de [`04_plano_de_execucao.md`](04_plano_de_execucao.md) **na mesma numeração**.
> O plano é a referência do *escopo original*; **onde os dois divergirem, este documento vence** —
> ele descreve o que existe, o plano descreve o que se pretendia.
>
> **Como atualizar:** ao concluir uma tarefa, troque o status e preencha a coluna *Evidência* com o
> arquivo ou teste que prova a conclusão. Status sem evidência verificável não conta como ✅ — foi
> essa disciplina que pegou o B7 (índice que "existe" e não busca nada).
>
> **Última atualização:** 07/08/2026 · branch `feature/modulo-publicacoes` · **650 testes
> verdes** (suíte completa do projeto) · `ruff check app/` limpo · **o explorador do acervo foi
> PROMOVIDO** — `/publicacoes` e `/publicacoes/viewer/{id}` não são mais a home de busca e o viewer
> simples originais, são o explorador de arquivos e o viewer avançado, testados manualmente e
> aprovados pelo desenvolvedor. Ver "Explorador do acervo — PROMOVIDO" abaixo.
>
> **Próximo trabalho:** as Etapas 1 e 2 de [`09_plano_configuracoes.md`](09_plano_configuracoes.md)
> estão concluídas — o módulo está funcionalmente completo para M0–M4, exceto o gate de RSS/disco da
> VPS (🔒 D-04). A verificação visual cobriu `lista.html`, `manual.html`, `capitulo.html`,
> `viewer.html`, `avulsas.html`, `mobile/publicacoes.html` e o explorador promovido (ver seção
> própria abaixo) — falta só o card de `configuracoes.html` (3 modais) e as edições em
> `panes/detalhe.html`/`inspecoes`. Fase 4 (mobile do explorador) segue não iniciada, por decisão de
> escopo. Ver a seção "Próxima tarefa" no fim deste documento.

---

## Painel

| Marco | Escopo | Progresso | Estado |
|---|---|---|---|
| **M0** — Fundação | 8 tarefas | 8/8 | ✅ **Concluído** |
| **M1** — Piloto FIM ⭐ | 15 tarefas | 15/15 | ✅ **Concluído** — as duas rotas de navegação que faltavam (`/publicacoes/manuais/{codigo}` e `.../{capitulo}`) foram fechadas pela Etapa 2 de `09_plano_configuracoes.md`; CSP confirmada limpa em navegador real (Chrome, console sem violações) |
| **M2** — Avulsas (BO/BS/NPO/BT) | 10 tarefas | 10/10 | ✅ **Concluído** |
| **M3** — Integração panes/inspeções | 5 tarefas | 5/5 | ✅ **Concluído** |
| **M4** — Acervo completo + ciclo DVD | 8 tarefas | 8/8 | ✅ **Concluído no código** — tarefas 1 a 8 entregues e testadas (Fases 0–2 de `09_plano_configuracoes.md`); resta a validação visual em navegador real e o gate de infraestrutura (RSS/disco na VPS, preso a D-04) |
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

## M1 — Piloto FIM ✅ 15/15 das tarefas planejadas + a capacidade que faltava, fechada pela Etapa 2

> **Histórico da lacuna, mantido para quem chega agora.** As 15 tarefas abaixo foram entregues, mas
> por quatro marcos o módulo **não cumpria duas rotas que o contrato especifica desde o início**:
>
> | Rota especificada | Observação na spec | Situação |
> |---|---|---|
> | `GET /publicacoes/manuais/{codigo}` | "capítulos" | ✅ implementada — Etapa 2 de `09_plano_configuracoes.md` |
> | `GET /publicacoes/manuais/{codigo}/{capitulo}` | "documentos" | ✅ implementada — Etapa 2 de `09_plano_configuracoes.md` |
>
> A matriz RBAC §7 também listava a ação *"Navegar catálogo / buscar / abrir PDF"* para os quatro
> perfis, e a §1 já previa o template `manual.html`. Ou seja: a navegação estava em **três** lugares
> do contrato — rotas, permissões e layout de arquivos — e não virou tarefa de marco nenhum até a
> Etapa 2 corrigir isso explicitamente (ver a seção dedicada no fim deste documento).
>
> **Lição de processo que continua valendo:** os gates de marco conferem a lista de tarefas, nunca a
> tabela de rotas. Uma rota especificada que ninguém transformou em tarefa não é vista por gate
> nenhum — e assim ficou quatro marcos sem existir. **Ao fechar um marco, rode a auditoria de rotas
> da §0.1 do contrato e cruze com a §3.**

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

## M3 — Integração com panes e inspeções ✅ 5/5

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | Bloco "Procedimentos FIM do ATA XX" no detalhe da pane | ✅ | `panes/detalhe.html#card-fim-pane` + `panes_detalhe.js:carregarProcedimentosFimDaPane`; endpoint novo `GET /publicacoes/api/fim/por-ata/{ata}` |
| 2 | Busca por mensagem de falha no registro de pane → sugere procedimento | ✅ | Mesmo bloco — reaproveita `/publicacoes/api/fim` do M1, sem endpoint novo |
| 3 | Link do item de checklist de inspeção para o documento correspondente | ✅ | `inspecao_detalhe.js:renderizarTarefas` — ícone de busca por item, abre `/publicacoes?q=<título>` |
| 4 | Favoritos (`publicacoes_favoritos`) | ✅ | Migration `7b3acb4928f0`, `service.py` (favoritar/listar/remover), rotas `/api/favoritos`; 12 testes em `tests/unit/test_publicacoes_favoritos.py` |
| 5 | Filtros de busca por manual/capítulo/ATA na tela de busca | ✅ | `catalog.db` ganhou a coluna `documents.ata_codigo`; `search.py`, `router.py` e `publicacoes.js` propagam o filtro `ata` |

**Achado corrigido em relação ao plano original (tarefa 3):** não existe, hoje, nenhum campo
estruturado ligando um item de checklist de inspeção a um documento do acervo — `InspecaoTarefa`
não tem `ata_codigo` nem `procedimento`, só `titulo`/`descricao`/`sistema` em texto livre. Criar
essa coluna exigiria migration no módulo `inspecoes` E dado real para populá-la, nenhum dos dois no
escopo do M3. A solução implementada é a busca full-text (título do item vira a query da tela
unificada de busca) — funciona hoje, sem migration nova, mas é uma correspondência por texto, não
uma referência garantida.

**Tarefa 1, correção de escopo:** o plano falava em "Bloco no detalhe da pane" sem especificar a
fonte; como `manuais_fim_map.procedimento` sempre começa pelos dois dígitos do ATA (convenção do
próprio FIM), a lista vem de um `LIKE 'XX-%'` sobre essa tabela — não precisou de nenhuma coluna
nova.

### Gate do M3

"De uma pane aberta, chegar ao procedimento correto sem digitar nada." ✅ Coberto pela tarefa 1
quando a pane tem `sistema_ata` definido — a lista carrega automaticamente ao abrir a página, sem
qualquer interação. Não coberto automaticamente quando a pane não tem ATA associado (usa a busca
manual da tarefa 2, que exige digitar a mensagem).

---

## M4 — Acervo completo e ciclo do DVD 🔵 7/8

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | Rodar `indexar.py` sobre o acervo completo | ✅ | **Executado de verdade nesta sessão**: 34 manuais, 5.724 documentos, 53.792 páginas, **0 sem camada de texto**, em 152,7s. Edição `2026` criada como `AGUARDANDO_ATIVACAO` no banco local |
| 2 | `publicar.py`: inventário, diff por hash, extração, snapshot ZIP, upload R2, relatório | ✅ | `scripts/publicacoes/publicar.py`; 13 testes em `tests/unit/test_publicacoes_publicar.py`; `--dry-run` e a execução completa (`--pular-upload`) rodados contra o acervo real |
| 3 | `merge_data.py`: merge de remessa nova (RN-08) | ✅ | `scripts/publicacoes/merge_data.py` — hash+mtime, `_merge_conflicts/`, `merge_report.txt`, `--dry-run` por padrão; 13 testes em `tests/unit/test_publicacoes_merge_data.py` |
| 4 | Card "Publicações" em `/configuracoes`: ativar/reverter, ver relatório | ✅ | **Implementado de ponta a ponta** (Fases 0–2 de `09_plano_configuracoes.md`). Fase 0: índice por edição (`catalog.<rotulo>.db`). Fase 1: 5 endpoints `AdminRequired` + migration `c4e7a91d2b58`. Fase 2: card, 3 modais em `configuracoes.html`, `configuracoes_publicacoes.js`, `.btn-publicacao`. 29 testes em `tests/unit/test_publicacoes_edicoes.py`. |
| 5 | Desduplicação por `hash_sha256` entre edição vigente e anterior | ✅ | `service.medir_duplicacao_entre_edicoes` — mede, não deduplica fisicamente (ver nota) |
| 6 | Transferência por rsync/SSH, nunca HTTP | ✅ | `docs/guides/operacao_publicacoes.md` §3 — comandos prontos, com placeholders 🔒 D-04 para host/usuário |
| 7 | Runbook interno | ✅ | `docs/guides/operacao_publicacoes.md`, adaptado de `docs/backlog/manuais/Runbook.MD` §2/§3/§4/§6.2/§7 |
| 8 | Medir `documentos_sem_texto` no acervo completo | ✅ | **0 de 5.724** — acervo bem digitalizado, OCR não é necessidade atual |

### Situação da tarefa 4 — concluída no código, pronta para uso

A **Tarefa 4** está 100% implementada no backend e no frontend conforme especificações das Fases 0, 1 e 2 de [`09_plano_configuracoes.md`](09_plano_configuracoes.md):

1. **Fase 0 (Índice por edição):** Cada edição possui seu próprio `catalog.<rotulo>.db`. A edição `VIGENTE` no banco define qual índice a busca abre (`service.caminho_indice_vigente`). Ativar passou a ser um `UPDATE` instantâneo em transação, sem mover arquivos em disco ou gerar instabilidade. Adendo no [ADR-004](../../architecture/adr/004-modulo-publicacoes.md).
2. **Fase 1 (Endpoints de gerência):** Endpoints `GET /api/edicoes`, `POST /{id}/ativar`, `POST /{id}/arquivar`, `GET /{id}/relatorio` e `GET /duplicacao` criados sob proteção `AdminRequired`, cobrindo o ciclo completo de ativação, reversão, consulta de relatório diff e medição de desduplicação. Migration `c4e7a91d2b58` garante o índice único parcial.
3. **Fase 2 (Card e Modais em `/configuracoes`):** Card "Publicações" integrado ao grid de `/configuracoes` (índigo `#6366f1`), 3 modais (`Gerenciar Edições`, `Relatório de Diff`, `Status do Acervo`) e script `configuracoes_publicacoes.js`.

Toda a suíte com 29 testes unitários em `tests/unit/test_publicacoes_edicoes.py` está **verde**, cobrindo regras de autorização, integridade de edições vigentes, recusa de edições sem índice e a correspondência dos elementos HTML/JS.

### Nota sobre a tarefa 5 (dedup)

`medir_duplicacao_entre_edicoes` **mede**, não **deduplica fisicamente** — hoje as edições
apontam para a mesma árvore em disco (`var/publicacoes/acervo/`), então não há cópia física
duplicada a eliminar ainda. O valor da medição é dimensionar, antes de qualquer reestruturação de
disco, quanto um esquema de dedup física economizaria — dado que falta para o gate "disco da VPS
< 60%". Física de verdade (hardlink entre edições, ou uma segunda árvore por edição) é trabalho de
disco specific a D-04, não algo a decidir sem saber o provedor.

### Gate do M4

"Publicar uma edição ponta a ponta a partir da mídia/remessa nova, ativar, conferir o relatório de
diff, reverter, reativar — sem downtime, RSS por worker < 200 MB, disco da VPS < 60% após duas
edições retidas." — **parcialmente verificável**: publicar/diff/relatório ✅ (medido de verdade);
ativar/reverter ⚠️ (mecanismo, endpoints e tela prontos e testados — Fases 0–2; falta abrir num
navegador real); RSS e disco da VPS 🔒 (não há VPS,
D-04).

---

## Explorador do acervo — PROMOVIDO (substitui a home e o viewer antigos)

`/publicacoes` e `/publicacoes/viewer/{doc_id}` **são hoje** o explorador de arquivos (árvore
Categoria → Manual → Capítulo) e o viewer avançado (zoom, rotação, miniaturas, busca interna) —
não uma prévia em avaliação. O desenvolvedor testou manualmente e decidiu adotar: *"prefiro muito
mais essa versão, quero usar essa nova visualização no projeto"*. Ver
[`melhorias.md`](melhorias.md) (o porquê de cada decisão de design) e
[`10_plano_preview_explorador.md`](10_plano_preview_explorador.md) §8 (o que foi construído e §8.5
o de-para exato da promoção — nomes de arquivo, rotas, o que foi apagado).

| Fase | Escopo | Status |
|---|---|---|
| 0–3 | Explorador navegável, busca por nome/conteúdo, viewer avançado | ✅ **Concluídas e promovidas** — sem flag, é o comportamento padrão de `/publicacoes` |
| 4 | Mobile | ⚪ **Não iniciada — decisão explícita de escopo**, não bloqueio técnico. `mobile/publicacoes.html` continua com a experiência própria (inalterada) |

**O que a promoção mudou de nome/lugar** (detalhe completo em `10_plano_preview_explorador.md`
§8.5): a flag `publicacoes_preview_explorador` foi removida; `publicacoes_preview_router.py` foi
apagado e suas duas rotas viraram os handlers definitivos de `/publicacoes`/`/publicacoes/viewer/{id}`
em `pages/router.py`; `/publicacoes/acervo` e `/publicacoes/acervo/viewer/{id}` não existem mais
(a URL definitiva sempre foi `/publicacoes`/`/publicacoes/viewer/{id}`); os arquivos
`*_preview_*`/`preview/` foram renomeados para seus nomes finais
(`publicacoes_explorador.js`, `publicacoes_viewer.js`, `publicacoes.css`, `lista.html`,
`viewer.html`).

**Duas capacidades da home antiga que o design original do explorador não cobria, fechadas na
promoção** (senão a troca teria sido uma perda funcional, não só uma UI diferente):
1. **Resolução de mensagem do FIM** (CAS/EICAS → procedimento) — virou um `<details>` recolhível na
   sidebar, mesmo endpoint `GET /api/fim` de sempre.
2. **Deep link `?q=`** — contrato com `inspecao_detalhe.js` (checklist de inspeção, M3), que linka
   `/publicacoes?q=<título>`. O explorador lê `?q=` no load e dispara a busca "no conteúdo"
   automaticamente; `inspecao_detalhe.js` não precisou mudar.

`/publicacoes/manuais/{codigo}[/{capitulo}]` (`manual.html`/`capitulo.html`) **não foram tocadas** —
`mobile/publicacoes.html` ainda depende delas para navegar (Fase 4 não existe).

**Verificado em Chrome real (headless via CDP), autenticado, contra o acervo completo** (34
manuais, 5.724 documentos, edição `2026` vigente), **depois** da promoção (sem flag nenhuma):
- `/publicacoes/acervo` devolve 404 (a rota da prévia não existe mais — confirma remoção limpa);
- `/publicacoes` mostra o explorador com o link de avulsas e o resolvedor FIM, sem faixa de prévia;
- `AMM_PART2_1651` (1.148 documentos, 51 capítulos) expande e pagina sem travar;
- as duas modalidades de busca (nome e conteúdo) devolvem resultado e abrem o documento certo;
- abrir um documento pela árvore leva a `/publicacoes/viewer/{id}` (a URL definitiva, não mais
  `/acervo/viewer/`);
- `/publicacoes?q=sangria` dispara a busca "no conteúdo" automaticamente (20 resultados);
- o resolvedor FIM devolve resultados reais (`ADC` → 12 procedimentos);
- `/m/publicacoes` e o link para `/publicacoes/manuais/{codigo}` continuam idênticos, não tocados;
- **console sem nenhuma violação de CSP ou erro em nenhuma tela.**

Efeito colateral da verificação em navegador (ainda na fase de prévia, antes da promoção): dois
bugs pré-existentes da UI **antiga** foram achados e corrigidos — ver "Dívidas conhecidas e
parciais" logo abaixo. Esses bugs não existem mais porque a UI que os continha foi substituída.

**Endpoints novos, permanentes:** `GET /publicacoes/api/catalogo/busca` (busca por nome/caminho) e
o parâmetro `documento_id` em `GET /publicacoes/api/busca` (busca restrita a um documento) — usados
pelo explorador e pelo viewer, respectivamente.

**Testes:** `tests/unit/test_publicacoes_preview.py` foi apagado (testava a flag, que não existe
mais); os testes de id/contrato que valiam a pena manter foram incorporados em
`test_pagina_lista_retorna_200_autenticado`/`test_pagina_viewer_retorna_200_autenticado`
(`tests/integration/test_publicacoes_busca.py`), mais um teste novo do deep link `?q=`. Um teste
obsoleto (`test_home_lista_os_manuais_por_categoria`, que checava HTML renderizado por SSR — a home
agora é client-fetch) foi removido de `test_publicacoes_navegacao.py`; a cobertura equivalente já
existia em `test_listar_manuais_agrupa_contagens` (nível de API). **Suíte completa do projeto: 650
testes, todos verdes** (era 658 com a prévia sob flag). `ruff check app/` limpo.

**Fase 4 (mobile) e o gate de decisão comparativo (§4 do `10_plano_preview_explorador.md`)** seguem
sem trabalho — a decisão de promover veio do uso direto pelo desenvolvedor, não do roteiro formal de
7 tarefas.

---

## Dívidas conhecidas e parciais

| Item | O que falta | Onde |
|---|---|---|
| **E-10** (acentos/espaços no caminho) | Nenhum teste cobre um `file_key` acentuado ponta a ponta, e **não há mais caso real para usar**: o exemplo citado antes (`docs/fim/Código de Panes.PDF`) saiu do repositório junto com o resto de `docs/fim/`, e o acervo normalizado não tem nenhum arquivo com acento ou espaço (medido: 0 de 5.724). Cobrir E-10 agora exige um PDF sintético com nome acentuado na amostra de fixtures — decisão consciente, não mais "basta incluir o que já existe". | `tests/fixtures/fim/`, `tests/integration/test_publicacoes_busca.py:PDFS_AMOSTRA` |
| **CA-01** (p95 < 300 ms) | O número foi **medido** (6,7 ms), mas não é afirmado por teste — regressão de performance passaria despercebida. | idem |
| ~~**Verificação visual do viewer/CSP**~~ | **Resolvido.** Aberto `/publicacoes/viewer/{id}` de um documento real (`AMM_PART2_1651`) em Chrome headless real (via CDP), console sem nenhuma violação de CSP nos dois temas. **Achado no processo:** o viewer não renderizava nenhum PDF — `getDocument(url)` (string) é o atalho removido no `pdfjs-dist` 5.x, e o vendorizado é o 6.2.108; o `catch` traduzia o erro para "documento removido do acervo", apontando para o lugar errado. Corrigido para `getDocument({ url })` em `publicacoes_viewer.js:151`. | `app/web/static/js/publicacoes_viewer.js` |
| **PDF.js sem `cmaps`/`standard_fonts`** | Só o núcleo (`pdf.min.mjs` + `pdf.worker.min.mjs`) foi vendorizado. Um PDF que dependa de fonte padrão não embutida (raro nos manuais, que embutem fonte) pode renderizar com fallback do navegador em vez da fonte exata. | `app/web/static/js/pdfjs/README.md` |
| **Frontend sem verificação visual em navegador — parcialmente resolvido** | **Verificado nesta sessão, em Chrome headless real (via CDP), autenticado, contra o acervo completo (34 manuais/5.724 docs):** `publicacoes/lista.html`, `manual.html` e `capitulo.html` com `AMM_PART2_1651` (o pior caso, 1.148 docs/51 capítulos — não trava), `viewer.html`, `avulsas.html`, `mobile/publicacoes.html`. Dois bugs reais achados e corrigidos: (1) viewer não abria nenhum PDF, ver a linha acima; (2) no mobile, os nomes de manual e os títulos de categoria eram texto quase branco sobre o `.card` branco do desktop — contraste medido em **1,05:1** (WCAG AA exige 4,5:1), porque `.mobile-body` pinta o texto de `--mobile-text` para o shell escuro mas a página herda o `.card` claro; corrigido com `color: var(--text-primary)` explícito em `mobile/publicacoes.html`, contraste agora **14,63:1**. **Ainda não verificado:** o card de Publicações em `configuracoes.html` com seus 3 modais (Fase 2 do M4), as edições em `panes/detalhe.html`/`inspecoes` (M3). | `app/web/templates/mobile/publicacoes.html`, `configuracoes.html`, `panes/detalhe.html`, `inspecao_detalhe.js` |
| **Limite de retenção duplicado entre backend e frontend** | O aviso "N edições têm índice em disco (previsto: 2)" usa `2` fixo em `configuracoes_publicacoes.js`. O valor canônico é `PUBLICACOES_EDICOES_RETIDAS` em `Settings`, que nenhum endpoint expõe — criar um endpoint de configuração só para isso não se pagava agora. Se o limite mudar, muda em dois lugares. | `app/web/static/js/configuracoes_publicacoes.js:atualizarAvisoRetencao` |
| ~~**Nenhum índice por edição existe na máquina local**~~ | **Superado.** Medido nesta sessão: `var/publicacoes/catalog.2026.db` (155 MB) existe, a edição `2026` está `VIGENTE` com 34 manuais/6.135 documentos, e a busca resolve o índice por edição sem aviso de fallback legado. Estado local mudou desde que esta linha foi escrita — não é mais reprodutível como descrito. | `var/publicacoes/` (não versionado) |
| **Link do checklist de inspeção é busca por texto, não referência garantida** | O item de checklist não tem campo estruturado (`ata_codigo`/`procedimento`) para apontar a um documento específico — o link roda uma busca full-text pelo título do item. Funciona bem quando o título é específico (ex: "Verificação da válvula de sangria"), mal quando é genérico (ex: "Inspeção visual geral"). Criar a referência estruturada exige migration em `inspecoes` e dado real para popular — fora do escopo do M3. | `app/web/static/js/inspecao_detalhe.js:renderizarTarefas` |
| **`catalog.db` local precisa reindexação após o M3 e após a Fase 0** | Duas razões acumuladas: (a) a coluna `documents.ata_codigo` só existe em índices gerados depois do M3 — sem ela a busca com filtro `ata` falha com erro de SQL; (b) depois da Fase 0 o arquivo esperado é `catalog.<rotulo>.db`, e um `catalog.db` solto passa a ser servido pela queda de compatibilidade, com aviso no log a cada busca. Nenhuma das duas é migration formal (o índice é descartável, ADR-004) — `python -m scripts.publicacoes.indexar --edicao <rotulo-vigente>` resolve as duas. | `scripts/publicacoes/indexar.py` |
| **Upload ao R2 do `publicar.py` não foi testado contra R2 de verdade** | Sem credenciais R2 nesta sessão — a lógica de upload/poda foi verificada só com `unittest.mock` (`tests/unit/test_publicacoes_publicar.py`), mesmo padrão de `test_r2_manager.py`. O caminho feliz (`boto3.upload_file`) é uma chamada simples e de baixo risco, mas vale um teste manual com credenciais reais antes do primeiro uso em produção. | `scripts/publicacoes/publicar.py:_obter_cliente_s3` |
| **Banco local de desenvolvimento ganhou uma edição real** | Rodar `publicar.py --edicao 2026 --pular-upload` (M4 tarefa 1) contra o acervo real criou a edição `2026` (`AGUARDANDO_ATIVACAO`, 5.724 documentos) no `saa29_local.db` de quem rodou esta sessão, além de sobrescrever `var/publicacoes/catalog.db` com o índice do acervo inteiro (antes só tinha o piloto FIM). Nenhum dos dois é versionado — não afeta outros ambientes, mas quem continuar localmente verá esse estado. | `saa29_local.db` (não versionado), `var/publicacoes/catalog.db` (não versionado) |
| ~~**`catalog.db` por edição não existe (bloqueia a tarefa 4)**~~ | **Resolvido** pela Fase 0 de `09_plano_configuracoes.md`: cada edição tem seu `catalog.<rotulo>.db` e a busca resolve o arquivo pela edição `VIGENTE`. Adendo no ADR-004. | `service.caminho_indice_vigente` |
| ~~**A máquina local ainda usa a queda de compatibilidade**~~ | **Superado** — registro de uma sessão anterior. Estado atual (medido nesta sessão): vigente é `2026`, com `catalog.2026.db` próprio (155 MB); a busca resolve o índice por edição, sem o aviso de fallback legado. | `var/publicacoes/` (não versionado) |
| **`manuais_edicoes`** | A tabela existe e é populada com a linha sintética `piloto-fim`, mas `snapshot_key`, `hash_sha256` e `relatorio_diff` seguem nulos — ganham uso só no M4. | Esperado, não é dívida real |
| ~~**Navegação do acervo não existe (2 rotas do contrato)**~~ | **Resolvido pela Etapa 2 de `09_plano_configuracoes.md`.** `/publicacoes` agora renderiza um índice "Navegar no acervo" (34 manuais agrupados nas 7 categorias, `Ordens Técnicas` recolhido por padrão) e as duas rotas de navegação existem: `/publicacoes/manuais/{codigo}` (capítulos) e `.../{capitulo}` (documentos, paginados por query string). Os filtros "Manual"/"Capítulo" da busca viraram `<select>` populados por `GET /api/manuais` e `GET /api/manuais/{codigo}/capitulos`. 19 testes em `tests/unit/test_publicacoes_navegacao.py`. | `app/web/pages/router.py`, `app/web/templates/publicacoes/{lista,manual,capitulo}.html`, `mobile/publicacoes.html`, `app/modules/publicacoes/{service,router,schemas}.py` |
| **Navegação renderizada direto do `service`, divergindo do padrão client-fetch do resto do app** | `publicacoes_lista_page`, `publicacoes_manual_page` e `publicacoes_capitulo_page` (`app/web/pages/router.py`) montam o HTML no servidor a partir de chamadas diretas ao `service`, com paginação via `?offset=`/`?limit=` na URL — todo o resto do projeto (inclusive o card de busca da mesma página `lista.html`) é 100% client-fetch via `apiFetch`. É decisão deliberada do plano (Etapa 2, §"Índice na home"): evita uma chamada HTTP da página a si mesma e preserva URL compartilhável/paginação server-side. Registrado aqui para que não pareça inconsistência acidental a quem ler o código depois. | `app/web/pages/router.py`, `app/web/templates/publicacoes/manual.html`, `capitulo.html` |
| **`capitulo == ""` na URL usa um sentinela (`_raiz_`)** | Um segmento de path vazio não roteia no FastAPI, então o caso medido do `piloto-fim` (PDFs soltos na raiz do manual) precisa de um valor de URL que não é o `capitulo` real. `CAPITULO_RAIZ_SLUG = "_raiz_"` em `app/web/pages/router.py` faz essa tradução nos dois sentidos. Não é dívida — é a solução —, mas é o tipo de detalhe que confunde quem só olhar a URL sem ler o código. | `app/web/pages/router.py:CAPITULO_RAIZ_SLUG` |
| **O CI exercita 4 PDFs, não o acervo** | Depois que `docs/fim/` saiu do versionamento, a amostra em `tests/fixtures/fim/` (4 arquivos, 172 KB) é tudo que o pipeline tem de PDF real. É deliberado — versionar mais reinstala o peso que a remoção quis eliminar — mas significa que classes de arquivo ausentes da amostra (PDF sem camada de texto, PDF corrompido, nome acentuado) só são exercitadas por fixture sintético ou localmente, com o acervo montado. Os testes que dependem do acervo real já se auto-pulam (`@sem_acervo` em `test_publicacoes_catalog.py`), então a ausência é visível, não silenciosa. | `tests/fixtures/fim/README.md` |
| **`fim.json` duplicado no repositório** | Existem duas cópias idênticas rastreadas: `fim.json` na raiz e `docs/fim.json`. A duplicação **é anterior** ao merge do módulo (já estava na `development`) e não foi tocada aqui para não misturar limpeza com integração. `tests/unit/test_publicacoes_catalog.py` lê a da raiz; o resto do módulo lê `docs/fim.json`. Consolidar numa só é trabalho de uma linha, mas muda o caminho lido por teste — vale fazer isolado. | `fim.json`, `docs/fim.json` |
| ~~**`test_status_aeronave_atualiza_para_indisponivel_ao_abrir_pane` é instável**~~ | **Corrigido.** A primeira análise estimou ~1/256 por execução, contando só as matrículas fixas de `tests/architecture/`; **o número real era ~10%** (2 falhas em 12 execuções, medido). A causa maior estava em `seed.FROTA_PADRAO`: `ensure_default_aeronaves`, chamado por `test_quality_helpers.py`, grava 20 matrículas `59xx` **fora da transação do teste**, então elas persistem pela sessão inteira e ocupam 20 dos 256 valores que `"59" + 2 dígitos hex` pode gerar. Trocado pelo sufixo hex completo nos dois testes afetados; 12 execuções seguidas sem falha. | `tests/unit/test_aeronaves.py` |

---

## Próxima tarefa

O módulo está **funcionalmente completo para M0–M4** (código). O que resta:

1. **RSS por worker / disco da VPS** (parte do gate do M4) — só é verificável depois de D-04 (sem
   VPS não há o que medir).
2. **Verificação visual em navegador do que falta** — a rodada desta sessão cobriu
   `lista.html`/`manual.html`/`capitulo.html`/`viewer.html`/`avulsas.html`/`mobile/publicacoes.html`
   e o explorador do acervo promovido, antes e depois da promoção; falta só **o card de Publicações
   em `configuracoes.html` (3 modais)** e **as edições em `panes/detalhe.html`/`inspecoes` (M3)**.
   Ver a tabela de dívidas acima para o roteiro do que olhar em cada tela.
3. **Fase 4 (mobile) do explorador** — não iniciada por decisão explícita, não bloqueio técnico. Ver
   `10_plano_preview_explorador.md` §8.4.

O item 1 depende de D-04 (VPS real). O item 2 é trabalho de código/navegador autocontido. O item 3
espera decisão de retomada — a promoção do explorador desktop não implica que o mobile precise do
mesmo tratamento agora.

 
NOTA DO DESENVOLVEDOR: M5 (RAG) continua congelado até D-S3 — nenhuma tarefa deste plano depende dele. [NAO TENTAR IMPLEMENTAR O M5 AGORA, POIS ELE SERA IMPLEMENTADO PELO DESENVOLVEDOR DE IA NA D-S3]
