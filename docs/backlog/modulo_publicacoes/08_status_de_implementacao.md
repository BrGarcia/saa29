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
> **Última atualização:** 06/08/2026 · branch `feature/modulo-publicacoes` · **622 testes
> verdes** · `ruff check .` limpo
>
> **Próximo trabalho:** Etapa 2 de [`09_plano_configuracoes.md`](09_plano_configuracoes.md) —
> navegação do acervo. A Etapa 1 (gerência em `/configuracoes`) está concluída.

---

## Painel

| Marco | Escopo | Progresso | Estado |
|---|---|---|---|
| **M0** — Fundação | 8 tarefas | 8/8 | ✅ **Concluído** |
| **M1** — Piloto FIM ⭐ | 15 tarefas | 15/15 | ⚠️ **Tarefas entregues, duas rotas do contrato faltando** — `/publicacoes/manuais/{codigo}` e `.../{capitulo}` estão na §3 desde o começo e nunca viraram tarefa; ver a nota no M1 e a Etapa 2 do `09`. CSP verificada por leitura de código, não por navegador real |
| **M2** — Avulsas (BO/BS/NPO/BT) | 10 tarefas | 10/10 | ✅ **Concluído** |
| **M3** — Integração panes/inspeções | 5 tarefas | 5/5 | ✅ **Concluído** |
| **M4** — Acervo completo + ciclo DVD | 8 tarefas | 7/8 | 🔵 **Em execução** — a tarefa 4 está implementada de ponta a ponta (Fases 0–2 de `09_plano_configuracoes.md`), pendente só de verificação visual em navegador; resta a tarefa do gate de RSS/disco, presa a D-04 |
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

## M1 — Piloto FIM ⚠️ 15/15 das tarefas planejadas, mas com uma capacidade faltando

> **Leia isto antes de considerar o M1 fechado.** As 15 tarefas abaixo foram entregues, e mesmo
> assim o marco **não cumpre duas rotas que o contrato especifica**. A tabela de rotas de
> `03_especificacao_tecnica.md` §3 lista, desde a primeira versão:
>
> | Rota especificada | Observação na spec | Situação |
> |---|---|---|
> | `GET /publicacoes/manuais/{codigo}` | "capítulos" | ❌ não existe |
> | `GET /publicacoes/manuais/{codigo}/{capitulo}` | "documentos" | ❌ não existe |
>
> A matriz RBAC §7 também lista a ação *"Navegar catálogo / buscar / abrir PDF"* para os quatro
> perfis, e a §1 já previa o template `manual.html`. Ou seja: a navegação estava em **três** lugares
> do contrato — rotas, permissões e layout de arquivos — e **não virou tarefa de marco nenhum**.
>
> Consequência: `/publicacoes` é só busca. Sem digitar um termo não há nada na tela, e os filtros de
> refino são texto livre — para filtrar por manual é preciso já saber que o código é `FIM_1741`.
> Num acervo de 34 manuais e 5.724 documentos, quem não sabe o que procurar não tem entrada.
>
> Corrigido pela **Etapa 2 de [`09_plano_configuracoes.md`](09_plano_configuracoes.md)** (⚪ não
> iniciada), que tem o plano detalhado e os dados do acervo medidos.
>
> **Lição de processo, e o motivo de esta nota existir:** os gates de marco conferem a lista de
> tarefas, nunca a tabela de rotas. Uma rota especificada que ninguém transformou em tarefa não é
> vista por gate nenhum — e assim ficou quatro marcos sem existir. **Ao fechar um marco, rode a
> auditoria de rotas da §0.1 do contrato e cruze com a §3.**

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
| 4 | Card "Publicações" em `/configuracoes`: ativar/reverter, ver relatório | ⚠️ | **Implementado nas Fases 0–2 de `09_plano_configuracoes.md`; sem verificação visual.** Fase 0: índice por edição — trocar a `VIGENTE` muda o que a busca devolve (`test_trocar_edicao_vigente_muda_o_que_a_busca_devolve`, verificado por mutação). Fase 1: 5 endpoints `AdminRequired` + migration `c4e7a91d2b58` (índice único parcial). Fase 2: card, 3 modais, `configuracoes_publicacoes.js`, `.btn-publicacao`. 29 testes em `tests/unit/test_publicacoes_edicoes.py`. ⚠️ **não aberto em navegador** — ver dívidas |
| 5 | Desduplicação por `hash_sha256` entre edição vigente e anterior | ✅ | `service.medir_duplicacao_entre_edicoes` — mede, não deduplica fisicamente (ver nota) |
| 6 | Transferência por rsync/SSH, nunca HTTP | ✅ | `docs/guides/operacao_publicacoes.md` §3 — comandos prontos, com placeholders 🔒 D-04 para host/usuário |
| 7 | Runbook interno | ✅ | `docs/guides/operacao_publicacoes.md`, adaptado de `docs/backlog/manuais/Runbook.MD` §2/§3/§4/§6.2/§7 |
| 8 | Medir `documentos_sem_texto` no acervo completo | ✅ | **0 de 5.724** — acervo bem digitalizado, OCR não é necessidade atual |

### Situação da tarefa 4 — bloqueador removido, tela pendente

**O bloqueador arquitetural foi resolvido.** Era este: "ativar" pressupõe um `catalog.db` por
edição, e existia **um único** `var/publicacoes/catalog.db`, sobrescrito a cada
`indexar.py`/`publicar.py` — mudar `manuais_edicoes.status` não mudaria o que a busca devolve.

A **Fase 0** de [`09_plano_configuracoes.md`](09_plano_configuracoes.md) construiu o que faltava:
cada edição tem seu `catalog.<rotulo>.db`, e a edição `VIGENTE` no banco é que decide qual arquivo a
busca abre (`service.caminho_indice_vigente`). Ativar passou a ser um `UPDATE` — sem mover arquivo,
sem janela em que banco e disco discordem. Decisão registrada no adendo do
[ADR-004](../../architecture/adr/004-modulo-publicacoes.md); a revisão do `os.replace()` previsto
originalmente está justificada ali.

Efeito colateral relevante: **publicar uma edição nova deixou de destruir o índice da edição em
vigor** — era um bug real, não só um impedimento para a tarefa 4.

Falta a tarefa 4 propriamente dita — endpoints de ativar/arquivar/relatório (Fase 1) e o card em
`/configuracoes` (Fase 2), ambos especificados no plano.

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

## Dívidas conhecidas e parciais

| Item | O que falta | Onde |
|---|---|---|
| **E-10** (acentos/espaços no caminho) | Nenhum teste cobre um `file_key` acentuado ponta a ponta, e **não há mais caso real para usar**: o exemplo citado antes (`docs/fim/Código de Panes.PDF`) saiu do repositório junto com o resto de `docs/fim/`, e o acervo normalizado não tem nenhum arquivo com acento ou espaço (medido: 0 de 5.724). Cobrir E-10 agora exige um PDF sintético com nome acentuado na amostra de fixtures — decisão consciente, não mais "basta incluir o que já existe". | `tests/fixtures/fim/`, `tests/integration/test_publicacoes_busca.py:PDFS_AMOSTRA` |
| **CA-01** (p95 < 300 ms) | O número foi **medido** (6,7 ms), mas não é afirmado por teste — regressão de performance passaria despercebida. | idem |
| **Verificação visual do viewer/CSP** | O delta de CSP (`worker-src 'self'`) foi justificado por leitura do código-fonte do PDF.js, não por abrir o console de um navegador real contra a aplicação rodando — esta sessão não teve acesso a um navegador. Antes de dar o item por definitivamente fechado, alguém precisa abrir `/publicacoes/viewer/{id}` de um documento real e checar o console por violações de CSP. Passo a passo em `docs/methodology/CSP.md` §5. | `docs/methodology/CSP.md` §5 |
| **PDF.js sem `cmaps`/`standard_fonts`** | Só o núcleo (`pdf.min.mjs` + `pdf.worker.min.mjs`) foi vendorizado. Um PDF que dependa de fonte padrão não embutida (raro nos manuais, que embutem fonte) pode renderizar com fallback do navegador em vez da fonte exata. | `app/web/static/js/pdfjs/README.md` |
| **Frontend sem verificação visual em navegador** | `publicacoes/lista.html`, `viewer.html`, `mobile/publicacoes.html`, `avulsas.html`, as edições em `panes/detalhe.html`/`inspecoes` (M3) e **o card de Publicações em `configuracoes.html` com seus 3 modais** (Fase 2) foram implementados e passam em testes de fumaça, mas nenhum foi aberto num navegador real — não há confirmação visual de layout, dos modais, do bloco FIM na pane, nem da experiência mobile. Para o card novo, o que os testes cobrem é o modo de falha silencioso (ids do template batendo com os alvos do JS); o que falta é aparência, o `auto-fit` do grid em telas estreitas, e o console limpo de CSP. | Templates de `app/web/templates/publicacoes/`, `configuracoes.html`, `mobile/publicacoes.html`, `panes/detalhe.html`, `inspecao_detalhe.js` |
| **Limite de retenção duplicado entre backend e frontend** | O aviso "N edições têm índice em disco (previsto: 2)" usa `2` fixo em `configuracoes_publicacoes.js`. O valor canônico é `PUBLICACOES_EDICOES_RETIDAS` em `Settings`, que nenhum endpoint expõe — criar um endpoint de configuração só para isso não se pagava agora. Se o limite mudar, muda em dois lugares. | `app/web/static/js/configuracoes_publicacoes.js:atualizarAvisoRetencao` |
| **Nenhum índice por edição existe na máquina local** | Consequência esperada de `catalog.db` legado (ver linha acima sobre reindexação): na tela, **as duas edições aparecem com "Índice: ausente"** e o botão "Ativar" é substituído por "reindexe para poder ativar". É o comportamento correto — mas significa que o fluxo de ativação só pode ser exercitado de verdade depois de `python -m scripts.publicacoes.indexar --edicao <rotulo>`. | `var/publicacoes/` (não versionado) |
| **Link do checklist de inspeção é busca por texto, não referência garantida** | O item de checklist não tem campo estruturado (`ata_codigo`/`procedimento`) para apontar a um documento específico — o link roda uma busca full-text pelo título do item. Funciona bem quando o título é específico (ex: "Verificação da válvula de sangria"), mal quando é genérico (ex: "Inspeção visual geral"). Criar a referência estruturada exige migration em `inspecoes` e dado real para popular — fora do escopo do M3. | `app/web/static/js/inspecao_detalhe.js:renderizarTarefas` |
| **`catalog.db` local precisa reindexação após o M3 e após a Fase 0** | Duas razões acumuladas: (a) a coluna `documents.ata_codigo` só existe em índices gerados depois do M3 — sem ela a busca com filtro `ata` falha com erro de SQL; (b) depois da Fase 0 o arquivo esperado é `catalog.<rotulo>.db`, e um `catalog.db` solto passa a ser servido pela queda de compatibilidade, com aviso no log a cada busca. Nenhuma das duas é migration formal (o índice é descartável, ADR-004) — `python -m scripts.publicacoes.indexar --edicao <rotulo-vigente>` resolve as duas. | `scripts/publicacoes/indexar.py` |
| **Upload ao R2 do `publicar.py` não foi testado contra R2 de verdade** | Sem credenciais R2 nesta sessão — a lógica de upload/poda foi verificada só com `unittest.mock` (`tests/unit/test_publicacoes_publicar.py`), mesmo padrão de `test_r2_manager.py`. O caminho feliz (`boto3.upload_file`) é uma chamada simples e de baixo risco, mas vale um teste manual com credenciais reais antes do primeiro uso em produção. | `scripts/publicacoes/publicar.py:_obter_cliente_s3` |
| **Banco local de desenvolvimento ganhou uma edição real** | Rodar `publicar.py --edicao 2026 --pular-upload` (M4 tarefa 1) contra o acervo real criou a edição `2026` (`AGUARDANDO_ATIVACAO`, 5.724 documentos) no `saa29_local.db` de quem rodou esta sessão, além de sobrescrever `var/publicacoes/catalog.db` com o índice do acervo inteiro (antes só tinha o piloto FIM). Nenhum dos dois é versionado — não afeta outros ambientes, mas quem continuar localmente verá esse estado. | `saa29_local.db` (não versionado), `var/publicacoes/catalog.db` (não versionado) |
| ~~**`catalog.db` por edição não existe (bloqueia a tarefa 4)**~~ | **Resolvido** pela Fase 0 de `09_plano_configuracoes.md`: cada edição tem seu `catalog.<rotulo>.db` e a busca resolve o arquivo pela edição `VIGENTE`. Adendo no ADR-004. | `service.caminho_indice_vigente` |
| **A máquina local ainda usa a queda de compatibilidade** | Verificado nesta sessão contra o estado real: vigente é `piloto-fim`, mas o único índice em disco é o `catalog.db` legado (155 MB, conteúdo da edição `2026`, gravado antes da Fase 0). A busca funciona (351 resultados para "sangria") e loga o aviso a cada consulta. Some com uma reindexação — não foi feita aqui para não gastar ~150s e sobrescrever mais estado local sem necessidade. | `var/publicacoes/` (não versionado) |
| **`manuais_edicoes`** | A tabela existe e é populada com a linha sintética `piloto-fim`, mas `snapshot_key`, `hash_sha256` e `relatorio_diff` seguem nulos — ganham uso só no M4. | Esperado, não é dívida real |
| **Navegação do acervo não existe (2 rotas do contrato)** | `/publicacoes` é só busca: sem digitar um termo não há nada na tela, e os filtros "Manual"/"Capítulo" são texto livre — exigem saber de antemão que o código é `FIM_1741` e o capítulo `CHAPTER_36`. Com 34 manuais e 5.724 documentos, quem não sabe o que procurar não entra. As rotas `/publicacoes/manuais/{codigo}` e `.../{capitulo}` estão na §3 do contrato desde a primeira versão e nunca viraram tarefa (ver a nota no M1). **Plano pronto para execução: Etapa 2 do `09`** — 2 páginas HTML + 3 endpoints, sem migration, testes especificados. | `app/web/pages/router.py`, `app/web/templates/publicacoes/`, `mobile/publicacoes.html` |
| **O CI exercita 4 PDFs, não o acervo** | Depois que `docs/fim/` saiu do versionamento, a amostra em `tests/fixtures/fim/` (4 arquivos, 172 KB) é tudo que o pipeline tem de PDF real. É deliberado — versionar mais reinstala o peso que a remoção quis eliminar — mas significa que classes de arquivo ausentes da amostra (PDF sem camada de texto, PDF corrompido, nome acentuado) só são exercitadas por fixture sintético ou localmente, com o acervo montado. Os testes que dependem do acervo real já se auto-pulam (`@sem_acervo` em `test_publicacoes_catalog.py`), então a ausência é visível, não silenciosa. | `tests/fixtures/fim/README.md` |
| **`fim.json` duplicado no repositório** | Existem duas cópias idênticas rastreadas: `fim.json` na raiz e `docs/fim.json`. A duplicação **é anterior** ao merge do módulo (já estava na `development`) e não foi tocada aqui para não misturar limpeza com integração. `tests/unit/test_publicacoes_catalog.py` lê a da raiz; o resto do módulo lê `docs/fim.json`. Consolidar numa só é trabalho de uma linha, mas muda o caminho lido por teste — vale fazer isolado. | `fim.json`, `docs/fim.json` |
| ~~**`test_status_aeronave_atualiza_para_indisponivel_ao_abrir_pane` é instável**~~ | **Corrigido.** A primeira análise estimou ~1/256 por execução, contando só as matrículas fixas de `tests/architecture/`; **o número real era ~10%** (2 falhas em 12 execuções, medido). A causa maior estava em `seed.FROTA_PADRAO`: `ensure_default_aeronaves`, chamado por `test_quality_helpers.py`, grava 20 matrículas `59xx` **fora da transação do teste**, então elas persistem pela sessão inteira e ocupam 20 dos 256 valores que `"59" + 2 dígitos hex` pode gerar. Trocado pelo sufixo hex completo nos dois testes afetados; 12 execuções seguidas sem falha. | `tests/unit/test_aeronaves.py` |

---

## Próxima tarefa

O módulo está **funcionalmente completo para M0–M3** e o M4 está em 6/8. O pré-requisito
arquitetural da tarefa 4 — índice por edição — **está construído e testado** (Fase 0 de
[`09_plano_configuracoes.md`](09_plano_configuracoes.md), adendo no ADR-004). Restam:

1. **Etapa 2 de [`09_plano_configuracoes.md`](09_plano_configuracoes.md) — navegação do acervo.**
   É o próximo trabalho, e o plano está detalhado o suficiente para alguém começar sem contexto
   prévio: fatos do acervo medidos, contrato das 3 rotas, lista dos 11 testes, armadilhas do
   harness. Fecha a capacidade que o M1 prometeu e não entregou.
2. **RSS por worker / disco da VPS** (parte do gate do M4) — só é verificável depois de D-04.
3. **Verificação visual em navegador** de tudo que foi construído — dívida acumulada desde o M1.

A Etapa 2 não tem bloqueador: é leitura de catálogo sobre colunas que já existem, sem migration.

 
NOTA DO DESENVOLVEDOR: M5 (RAG) continua congelado até D-S3 — nenhuma tarefa deste plano depende dele. [NAO TENTAR IMPLEMENTAR O M5 AGORA, POIS ELE SERA IMPLEMENTADO PELO DESENVOLVEDOR DE IA NA D-S3]
