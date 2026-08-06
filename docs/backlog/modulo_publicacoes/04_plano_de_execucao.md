# Plano de Execução — Módulo `publicacoes`

> Marcos herdados do `opus_plano_de_incorporacao.md` §10, **reordenados conforme a decisão desta
> sessão** (avulsas antes da integração com panes/inspeções) e **quebrados em tarefas**, com os
> gates reescritos para o CI real (`01_achados_do_acervo.md` §7.4 — sem matriz Postgres, sem
> mypy).

**Ordem:** M0 (fundação) → **M1 (piloto FIM)** → **M2 (avulsas)** → M3 (integração) → M4 (acervo
completo). M1 e M2 dependem só de M0; a ordem entre elas é a única coisa que mudou em relação ao
parecer original. M3 depende de M1. M4 depende de M0+M1 e da decisão D-04 (provedor de VPS).

---

## M0 — Fundação (≈ 2 dias)

| # | Tarefa | Arquivo(s) |
|---|---|---|
| 1 | ADR-004 registrando as 4 decisões da espinha dorsal + `pypdfium2` | `docs/architecture/adr/004-modulo-publicacoes.md` |
| 2 | Normalizar `var/Publicações/` → `var/publicacoes/acervo/` (rename, sem reprocessar nada) | `var/publicacoes/acervo/` |
| 3 | `.gitignore`: **substituir** a entrada atual `var/publicações/` (linha 57) por `var/publicacoes/` — a atual tem acento e só protege hoje porque o Windows casa sem diferenciar maiúsculas; **no Linux (CI/VPS) não casaria**, e depois do rename da tarefa 2 não casa em sistema nenhum. Fazer **junto** com o rename, no mesmo commit, senão abre uma janela com 1 GB rastreável (R22) | `.gitignore` |
| 4 | Esqueleto do módulo: `__init__.py`, `router.py` vazio (`APIRouter()`, zero rotas) | `app/modules/publicacoes/` |
| 5 | Registro nos 5 pontos (import de models — mesmo vazio por ora, import do router, `API_PREFIXES` com `/publicacoes/api/`, `include_router`, `migrations/env.py`) | `app/bootstrap/main.py`, `migrations/env.py` |
| 6 | `PUBLICACOES_*` em `Settings` + `.env.example` (`03_especificacao_tecnica.md` §6) | `app/bootstrap/config/__init__.py`, `.env.example` |
| 7 | `pypdfium2` em `requirements.txt`, pinado (`==` explícito, como o resto do arquivo) | `requirements.txt` |
| 8 | `config/categorias_manuais.toml` com os 34 manuais medidos (`01_achados_do_acervo.md` §1.1) | `config/categorias_manuais.toml` |

**Gate:** `ruff check .` limpo + suíte atual (verificar contagem de testes em `pytest --collect-only`
antes de começar, para ter o número real de referência) verde, com o módulo registrado e vazio.
`git status` sem `var/Publicações` nem `var/publicacoes` rastreados.

---

## M1 — Piloto FIM: busca de falha → procedimento (≈ 1 semana) ⭐

Usa os 411 PDFs de `docs/fim/` (já versionados) **enriquecidos pelo Lucene do `FIM_1741`** quando
`var/publicacoes/acervo/Manuais/FIM_1741/index_2.0/` estiver presente (opcional — 409/411 têm
correspondência, `01_achados_do_acervo.md` §6).

| # | Tarefa | Detalhe |
|---|---|---|
| 1 | `catalog.py`: parser do índice Lucene (copiar de `02_formato_indice_lucene.md` §5, com testes de regressão contra os números do §7 daquele documento) | `app/modules/publicacoes/catalog.py` |
| 2 | `catalog.py`: ingestão de `fim.json` → estrutura intermediária mensagem→procedimento | idem |
| 3 | Migration Alembic: `manuais`, `manuais_documentos`, `manuais_fim_map` (**sem `manuais_edicoes`/`pages`/FTS5** — ver nota abaixo) | `migrations/versions/` |
| 4 | `scripts/publicacoes/indexar.py`: varre um diretório de entrada (parametrizado — `docs/fim/` neste marco), extrai texto **por página** com `pypdfium2`, grava `catalog.db` (`pages`+`pages_fts`), grava o catálogo leve no banco principal via `service.py`. Idempotente, `--dry-run`, resiliente a PDF corrompido (E-02, nunca aborta o lote) | `scripts/publicacoes/indexar.py` |
| 5 | `search.py`: abertura read-only do `catalog.db` (`sqlite3` puro, nunca SQLAlchemy — `01_achados_do_acervo.md` §7.3), BM25, `snippet()` com `<mark>`, sanitização de query (RN-10) | `app/modules/publicacoes/search.py` |
| 6 | `router.py`: `/publicacoes/api/busca`, `/publicacoes/api/fim`, `/publicacoes/api/status`, `/publicacoes/doc/{id}/pdf` | `app/modules/publicacoes/router.py` |
| 7 | PDF.js vendorizado em `app/web/static/js/pdfjs/`; viewer em canvas (D-F — nunca iframe, `X-Frame-Options: DENY` é global) | `app/web/static/js/pdfjs/`, `app/web/templates/publicacoes/viewer.html` |
| 8 | Páginas: lista/busca (`app/web/pages/router.py`) + item no `<nav>` de `base.html` + atalho `/m/publicacoes` (`mobile_router.py` + drawer de `base_mobile.html`) | `app/web/templates/publicacoes/`, `app/web/static/js/publicacoes.js` |
| 9 | Auditoria de acesso (`publicacoes_acessos`) a cada abertura de documento | `service.py` |
| 10 | Medir CSP no console com o build de PDF.js escolhido; aplicar o delta mínimo (`worker-src 'self' blob:` provável) e documentar em `docs/methodology/CSP.md` na mesma PR | `app/shared/middleware/security.py`, `docs/methodology/CSP.md` |
| 11 | Verificar se `X-Frame-Options: DENY` já quebra o iframe de PDF em `panes_detalhe.js:580-606` (achado correlato, `03_especificacao_tecnica.md` §4.4) — registrar como bug preexistente separado se confirmado, não corrigir aqui | — |
| 12 | Testes: `catalog.py` com fixtures reais do Lucene (números fixos do `02_formato_indice_lucene.md` §7 como regressão); E-02, E-06, E-08, E-10; CA-01 e CA-04 | `tests/unit/test_publicacoes_catalog.py`, `tests/integration/test_publicacoes_busca.py` |
| 13 | **Tabela `documents` no `catalog.db`** + `rebuild`/`optimize` do FTS5 ao final da carga — sem isso os filtros da API são inimplementáveis e a busca devolve zero silenciosamente (`07_revisao_pre_implementacao.md` B6/B7) | `scripts/publicacoes/indexar.py` |
| 14 | **Teste de round-trip de UUID** entre `catalog.db` e banco principal — o formato difere (hex sem hífens vs. canônico) e a divergência falha sem erro (B5) | `tests/integration/test_publicacoes_busca.py` |
| 15 | **Rate limit** na busca (`30/minute`) — com `request: Request` na assinatura, exigido pelo decorator | `router.py` |

**Sequência recomendada dentro do M1** (ordena para que os bugs *silenciosos* apareçam cedo, em
vez de depois da UI pronta):

1. `catalog.py` — tem gabarito de verificação pronto (`02_formato_indice_lucene.md` §7);
2. `indexar.py` gerando `catalog.db` **com rebuild**, validado por **busca real, nunca por
   contagem** (B7);
3. teste de round-trip de UUID (B5) — antes de qualquer UI, porque é o contrato que ela assume;
4. `search.py` + rota de busca;
5. viewer PDF.js + tratamento de snippet (B8) + medição de CSP;
6. resto da UI.

**Nota sobre `manuais_edicoes`:** a tabela pode nascer na migration do M1 (evita uma segunda
migration alterando a FK de `manuais.edicao_id` depois), mas populada com uma única linha
sintética (`rotulo="piloto-fim"`, `status=VIGENTE`) — o fluxo de ativação/reversão só ganha UI e
significado real no M4.

**Gate de saída (verificável, reescrito para o CI real):**
- Buscar `ADC 001` → procedimento `34-15-00-810-801-A` → PDF abre **na página do trecho** (não
  mais só "na página 1" — `pypdfium2` por página entrega isso, diferente do que o Lucene sozinho
  permitiria, `01_achados_do_acervo.md` §5);
- busca full-text `sangria`/`SANGRIA`/`sangría` retorna o mesmo conjunto (CA-04);
- PDF renderiza no viewer **sem violação de CSP no console** — delta documentado em
  `docs/methodology/CSP.md` na mesma PR;
- p95 da busca < 300 ms sobre o corpus FIM (411 documentos, ~4.150 páginas estimadas);
- `ruff check .` + `pytest --cov` verdes (o CI real roda só isso — `01_achados_do_acervo.md` §7.4,
  não "as duas pontas da matriz SQLite/Postgres" como o parecer original previa).

---

## M2 — Publicações avulsas: BO, BS, NPO, BT (≈ 1 semana)

Independente do M1 — não usa `catalog.db` nem `pypdfium2`, só o banco principal.

| # | Tarefa | Detalhe |
|---|---|---|
| 1 | Enum `TipoPublicacao`, `StatusPublicacaoAvulsa` em `shared/core/enums.py` | |
| 2 | Migration: `publicacoes_avulsas`, `publicacao_avulsa_anexos`, `publicacao_avulsa_aeronaves` | `migrations/versions/` |
| 3 | `avulsas.py` + `service.py`: CRUD, cadeia `substituida_por_id`, filtro de vigência | `app/modules/publicacoes/avulsas.py` |
| 4 | RBAC: `EncarregadoInspetorOuAdmin` para cadastro/edição, `AdminRequired` + soft delete para exclusão (D-S6) | `router.py` |
| 5 | Upload de anexo: `PUBLICACOES_AVULSAS_MAX_UPLOAD_MB`, **fora** do pipeline de imagem (`shared/services/image/pipeline.py` não se aplica — PDF escaneado vai direto ao storage) | `router.py`, `service.py` |
| 6 | Busca por metadados: `LIKE` com `escape_like` (`shared/core/db_utils.py:10`), portável para Postgres | `service.py` |
| 7 | Páginas: `avulsas.html`, `publicacoes_avulsas.js` | `app/web/templates/publicacoes/avulsas.html` |
| 8 | Testes: cadastro, vigência, substituição, RBAC, limite de upload, soft delete | `tests/unit/test_publicacoes_avulsas.py` |
| 9 | **Teste de XSS**: ementa com `<img src=x onerror=...>`, buscar por termo dela e afirmar que a resposta não contém `<img` — a ementa é entrada de usuário e vai para o `snippet` (`07_revisao_pre_implementacao.md` B8) | `tests/security/test_publicacoes_xss.py` |
| 10 | Rate limit no upload de anexo (`10/minute`, mesmo valor do upload de panes) | `router.py` |

**Gate:** cadastrar um BS real com anexo escaneado e encontrá-lo por número, por ATA e por palavra
da ementa — nos três casos.

---

## M3 — Integração com panes e inspeções (≈ 1 semana)

| # | Tarefa | Detalhe |
|---|---|---|
| 1 | Bloco "Procedimentos FIM do ATA XX" no detalhe da pane, filtrado por `sistema_ata` | `app/web/templates/panes/detalhe.html`, `panes_detalhe.js` |
| 2 | Busca por mensagem de falha no registro de pane → sugere procedimento via `manuais_fim_map` | `app/modules/panes/` (consumindo `publicacoes.service`) |
| 3 | Link do item de checklist de inspeção para o documento correspondente | `app/modules/inspecoes/` |
| 4 | Favoritos (`publicacoes_favoritos`) | `service.py`, `router.py` |
| 5 | Filtros de busca por manual/capítulo/ATA na tela de busca | `publicacoes.js` |

**Gate:** de uma pane aberta, chegar ao procedimento correto sem digitar nada.

---

## M4 — Acervo completo e ciclo do DVD (≈ 2 semanas + D-04) 🔒

**Escopo corrigido pela Revisão 5:** deixa de ser "trazer os 3 GB para dentro do sistema" — já
estão em `var/publicacoes/acervo/` desde o M0, e são 1 GB, não 3. Passa a ser **o ciclo de
republicação anual** e a decisão de hospedagem.

| # | Tarefa | Detalhe |
|---|---|---|
| 1 | Rodar `indexar.py` (já existe desde o M1) apontado para `var/publicacoes/acervo/Manuais/` inteiro — **não é trabalho novo de código**, é uma execução em escala maior. Pode acontecer a qualquer momento depois do M1, **sem esperar D-04** | `scripts/publicacoes/indexar.py` |
| 2 | `publicar.py`: inventário, diff por hash, extração incremental do delta, snapshot ZIP, upload ao R2, `relatorio_publicacao_<ano>.md` | `scripts/publicacoes/publicar.py` |
| 3 | `merge_data.py`: merge de remessa nova no acervo existente (RN-08) | `scripts/publicacoes/merge_data.py` |
| 4 | Card "Publicações" em `/configuracoes`: ativar/reverter edição, ver relatório de diff | `app/web/templates/configuracoes.html` (existente) |
| 5 | Desduplicação por `hash_sha256` entre edição vigente e anterior | `service.py` |
| 6 | Transferência por `rsync`/SSH da estação de publicação para a VPS, com verificação de hash — nunca por HTTP | `docs/guides/operacao_publicacoes.md` |
| 7 | Runbook interno, adaptando `docs/backlog/manuais/Runbook.MD` §2/§3/§4/§6.2/§7 (tabela de reavaliação no parecer §5.8) | `docs/guides/operacao_publicacoes.md` |
| 8 | Medir `documentos_sem_texto` no acervo completo → dimensiona necessidade de OCR | `service.py` |

**Gate:** publicar uma edição ponta a ponta a partir da mídia/remessa nova, ativar, conferir o
relatório de diff, reverter, reativar — sem downtime, RSS por worker < 200 MB, disco da VPS < 60%
após duas edições retidas.

---

## M5 — Fase 3 / RAG 🔒 fora do plano de execução

Inalterado em relação ao parecer §10 (M5): congelado até D-S3 (autorização formal para trafegar
conteúdo técnico-militar por API de LLM externa). Nenhuma tarefa deste plano depende dele.

---

## Resumo de esforço

| Marco | Esforço | Depende de | Entrega valor sozinho? |
|---|---|---|---|
| M0 — fundação | ~2 dias | — | não (fundação) |
| **M1 — piloto FIM** | **~1 semana** | M0 | **✅ sim — alto** |
| **M2 — avulsas** | **~1 semana** | M0 (não M1) | **✅ sim — alto** |
| M3 — integração | ~1 semana | M1 | ✅ sim |
| M4 — acervo completo + ciclo DVD | ~2 semanas | M0+M1, D-04 | ✅ sim |
| M5 — RAG | — | D-S3 | congelado |

**Caminho até valor operacional: ~1 semana e meia (M0+M1 ou M0+M2), sem tocar em infraestrutura,
sem depender de VPS.**

---

## Riscos deste plano — apenas os que mudaram em relação ao parecer

O parecer §11 lista R1–R19; a maioria sobrevive sem alteração. Os que mudam com a Revisão 5:

| # | Risco | Mudança |
|---|---|---|
| R1 | Acervo satura o disco | Reclassificado **duas vezes**: orçamento cai para 1/3 (1 GB medido vs. 3 GB assumido) |
| R3 | Índice FTS5 quebra a matriz Postgres do CI | Motivo original **não existe** (CI real não tem matriz Postgres) — decisão de manter `catalog.db` separado do Alembic continua certa, mas por portabilidade declarada, não por proteção de CI |
| R5 | Exposição AGPL do PyMuPDF | **Encerrado** — D-S2 decidida por `pypdfium2` (Apache-2.0/BSD-3) |
| **R20** 🆕 | Registrar `/publicacoes/` (em vez de `/publicacoes/api/`) em `API_PREFIXES` quebra o redirect de login das páginas HTML | Baixa prob. (documentado explicitamente em três lugares agora), alto impacto se acontecer — mesmo bug já visto com o calendário |
| **R21** 🆕 | Abrir `catalog.db` com SQLAlchemy dispara backup R2 espúrio do banco principal | Baixa prob. (regra explícita em D-D), médio impacto — poluição de log e upload desnecessário, não perda de dado |
| **R22** 🆕 | `var/Publicações/` (1 GB) entra no histórico do git antes do M0 rodar | **Média prob. até a correção do `.gitignore` ser commitada** — mitigação é a tarefa M0 #3, primeira do marco |
