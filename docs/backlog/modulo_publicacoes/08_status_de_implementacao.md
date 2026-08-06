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
> **Última atualização:** 05/08/2026 · branch `fix/ci-baseline-verde` · 575 testes verdes ·
> `ruff check .` limpo

---

## Painel

| Marco | Escopo | Progresso | Estado |
|---|---|---|---|
| **M0** — Fundação | 8 tarefas | 8/8 | ✅ **Concluído** |
| **M1** — Piloto FIM ⭐ | 15 tarefas | 15/15 | ✅ **Concluído** — CSP verificada por leitura de código, não por navegador real (ver dívidas) |
| **M2** — Avulsas (BO/BS/NPO/BT) | 10 tarefas | 10/10 | ✅ **Concluído** |
| **M3** — Integração panes/inspeções | 5 tarefas | 5/5 | ✅ **Concluído** |
| **M4** — Acervo completo + ciclo DVD | 8 tarefas | 6/8 | 🔵 **Em execução** — faltam as 2 tarefas que dependem de infraestrutura por decidir (D-04) ou de arquitetura ainda não fechada (catalog.db por edição) |
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

## M4 — Acervo completo e ciclo do DVD 🔵 6/8

| # | Tarefa | Status | Evidência |
|---|---|:--:|---|
| 1 | Rodar `indexar.py` sobre o acervo completo | ✅ | **Executado de verdade nesta sessão**: 34 manuais, 5.724 documentos, 53.792 páginas, **0 sem camada de texto**, em 152,7s. Edição `2026` criada como `AGUARDANDO_ATIVACAO` no banco local |
| 2 | `publicar.py`: inventário, diff por hash, extração, snapshot ZIP, upload R2, relatório | ✅ | `scripts/publicacoes/publicar.py`; 13 testes em `tests/unit/test_publicacoes_publicar.py`; `--dry-run` e a execução completa (`--pular-upload`) rodados contra o acervo real |
| 3 | `merge_data.py`: merge de remessa nova (RN-08) | ✅ | `scripts/publicacoes/merge_data.py` — hash+mtime, `_merge_conflicts/`, `merge_report.txt`, `--dry-run` por padrão; 13 testes em `tests/unit/test_publicacoes_merge_data.py` |
| 4 | Card "Publicações" em `/configuracoes`: ativar/reverter, ver relatório | ⚪ | **Não implementado** — motivo técnico concreto abaixo, não falta de tempo |
| 5 | Desduplicação por `hash_sha256` entre edição vigente e anterior | ✅ | `service.medir_duplicacao_entre_edicoes` — mede, não deduplica fisicamente (ver nota) |
| 6 | Transferência por rsync/SSH, nunca HTTP | ✅ | `docs/guides/operacao_publicacoes.md` §3 — comandos prontos, com placeholders 🔒 D-04 para host/usuário |
| 7 | Runbook interno | ✅ | `docs/guides/operacao_publicacoes.md`, adaptado de `docs/backlog/manuais/Runbook.MD` §2/§3/§4/§6.2/§7 |
| 8 | Medir `documentos_sem_texto` no acervo completo | ✅ | **0 de 5.724** — acervo bem digitalizado, OCR não é necessidade atual |

### Por que a tarefa 4 não foi implementada (não é falta de tempo)

"Ativar" uma edição, tal como o M4 foi desenhado (`search.py`, docstring de `_abrir_catalog_ro`),
pressupõe um `catalog.db` **por edição**, trocado atomicamente com `os.replace()` no momento da
ativação — é assim que a busca nunca fica com um índice pela metade. **Isso não está construído.**
Hoje existe **um único** `var/publicacoes/catalog.db`, sobrescrito a cada `indexar.py`/`publicar.py`
— não há "catalog.db da edição 2026" e "catalog.db da edição piloto-fim" coexistindo em arquivos
separados prontos para a troca atômica.

Implementar só a metade visível (endpoints que mudam `manuais_edicoes.status` no banco, mais um
card na tela) **sem** o mecanismo de arquivo por edição criaria uma func "ativar" que muda o status
no banco mas não muda o que a busca realmente devolve — pior que não ter o botão, porque
pareceria funcionar. A correção correta é arquitetural (nomear o `catalog.db` por edição, ex.
`catalog.<rotulo>.db`, e apontar `PUBLICACOES_INDEX_PATH` para o vigente via symlink ou registro em
`Settings`), maior que o que cabe nesta sessão sem virar meia-solução. Registrado como pendência
real em vez de código que passa em teste mas mente sobre o que faz.

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
ativar/reverter ⚪ (bloqueado pela lacuna arquitetural acima); RSS e disco da VPS 🔒 (não há VPS,
D-04).

---

## Dívidas conhecidas e parciais

| Item | O que falta | Onde |
|---|---|---|
| **E-10** (acentos/espaços no caminho) | Nenhum teste cobre um `file_key` acentuado ponta a ponta. O caso real existe e está versionado: `docs/fim/Código de Panes.PDF`. Basta incluí-lo na amostra do teste de integração. | `tests/integration/test_publicacoes_busca.py:PDFS_AMOSTRA` |
| **CA-01** (p95 < 300 ms) | O número foi **medido** (6,7 ms), mas não é afirmado por teste — regressão de performance passaria despercebida. | idem |
| **Verificação visual do viewer/CSP** | O delta de CSP (`worker-src 'self'`) foi justificado por leitura do código-fonte do PDF.js, não por abrir o console de um navegador real contra a aplicação rodando — esta sessão não teve acesso a um navegador. Antes de dar o item por definitivamente fechado, alguém precisa abrir `/publicacoes/viewer/{id}` de um documento real e checar o console por violações de CSP. Passo a passo em `docs/methodology/CSP.md` §5. | `docs/methodology/CSP.md` §5 |
| **PDF.js sem `cmaps`/`standard_fonts`** | Só o núcleo (`pdf.min.mjs` + `pdf.worker.min.mjs`) foi vendorizado. Um PDF que dependa de fonte padrão não embutida (raro nos manuais, que embutem fonte) pode renderizar com fallback do navegador em vez da fonte exata. | `app/web/static/js/pdfjs/README.md` |
| **Frontend sem verificação visual em navegador** | `publicacoes/lista.html`, `viewer.html`, `mobile/publicacoes.html`, `avulsas.html`, e as edições em `panes/detalhe.html`/`inspecoes` (M3) foram implementados e passam em testes de fumaça (200 + `text/html` quando aplicável), mas nenhum foi aberto num navegador real nesta sessão — não há confirmação visual de layout, dos modais de cadastro/anexo/favorito, do bloco FIM na pane, nem da experiência mobile. | Todos os templates de `app/web/templates/publicacoes/`, `mobile/publicacoes.html`, `panes/detalhe.html`, `inspecao_detalhe.js` |
| **Link do checklist de inspeção é busca por texto, não referência garantida** | O item de checklist não tem campo estruturado (`ata_codigo`/`procedimento`) para apontar a um documento específico — o link roda uma busca full-text pelo título do item. Funciona bem quando o título é específico (ex: "Verificação da válvula de sangria"), mal quando é genérico (ex: "Inspeção visual geral"). Criar a referência estruturada exige migration em `inspecoes` e dado real para popular — fora do escopo do M3. | `app/web/static/js/inspecao_detalhe.js:renderizarTarefas` |
| **`catalog.db` local precisa reindexação após o M3** | A coluna `documents.ata_codigo` só existe em índices gerados depois desta mudança em `indexar.py`. Um `catalog.db` gerado antes do M3 (por outro desenvolvedor, ou em outra máquina) não tem a coluna — a busca com filtro `ata` falharia com erro de SQL. Não é uma migration formal (o índice é descartável, ADR-004) — basta rodar `python -m scripts.publicacoes.indexar` de novo. | `scripts/publicacoes/indexar.py` |
| **Upload ao R2 do `publicar.py` não foi testado contra R2 de verdade** | Sem credenciais R2 nesta sessão — a lógica de upload/poda foi verificada só com `unittest.mock` (`tests/unit/test_publicacoes_publicar.py`), mesmo padrão de `test_r2_manager.py`. O caminho feliz (`boto3.upload_file`) é uma chamada simples e de baixo risco, mas vale um teste manual com credenciais reais antes do primeiro uso em produção. | `scripts/publicacoes/publicar.py:_obter_cliente_s3` |
| **Banco local de desenvolvimento ganhou uma edição real** | Rodar `publicar.py --edicao 2026 --pular-upload` (M4 tarefa 1) contra o acervo real criou a edição `2026` (`AGUARDANDO_ATIVACAO`, 5.724 documentos) no `saa29_local.db` de quem rodou esta sessão, além de sobrescrever `var/publicacoes/catalog.db` com o índice do acervo inteiro (antes só tinha o piloto FIM). Nenhum dos dois é versionado — não afeta outros ambientes, mas quem continuar localmente verá esse estado. | `saa29_local.db` (não versionado), `var/publicacoes/catalog.db` (não versionado) |
| **`catalog.db` por edição não existe (bloqueia a tarefa 4)** | Ver a seção dedicada em M4 acima — é a lacuna arquitetural que impede "ativar edição" de fazer sentido hoje. | `app/modules/publicacoes/search.py` |
| **`manuais_edicoes`** | A tabela existe e é populada com a linha sintética `piloto-fim`, mas `snapshot_key`, `hash_sha256` e `relatorio_diff` seguem nulos — ganham uso só no M4. | Esperado, não é dívida real |

---

## Próxima tarefa

O módulo está **funcionalmente completo para M0–M3** e o M4 está em 6/8, com as duas tarefas
restantes bloqueadas por motivos concretos (não por falta de tempo):

1. **Tarefa 4 (ativar/reverter edição)** — exige primeiro resolver o `catalog.db` por edição
   (nomear por rótulo + apontar `Settings` para o vigente), que é trabalho de arquitetura, não de
   tela. Ver a seção "Por que a tarefa 4 não foi implementada" acima antes de começar.
2. **RSS por worker / disco da VPS** (parte do gate do M4) — só é verificável depois de D-04.

Sugestão de ordem daqui para frente: (a) resolver o `catalog.db` por edição — é pré-requisito real
da tarefa 4, não um nice-to-have; (b) construir a tarefa 4 (endpoints de ativar/reverter + card em
`/configuracoes`) sobre essa base; (c) D-04 resolvida → validar o gate completo do M4 na VPS real.

M5 (RAG) continua congelado até D-S3 — nenhuma tarefa deste plano depende dele.
