# Revisão de Pré-Implementação — Módulo `publicacoes`

> Revisão do planejamento **antes da primeira linha de código**, cruzando
> `03_especificacao_tecnica.md` com `docs/backlog/00_mapa_arquitetural.md` e com o código real do
> SAA29. Objetivo: antecipar bugs que só apareceriam na implementação (ou, pior, em produção) e
> simplificar o que estava sobre-projetado.
>
> **Data:** 2026-08-05 · **Método:** leitura cruzada + **execução real** de SQLite/SQLAlchemy para
> cada hipótese testável. Nenhum achado abaixo é opinião de leitura: os marcados 🔬 foram medidos.

**Resultado:** 8 bugs que teriam ido para o código, 2 simplificações, 5 lacunas de convenção.
Todas as correções já foram **aplicadas** em `03_especificacao_tecnica.md`.

---

## Bugs antecipados

### 🔴 B1 — PK composta com colunas nullable em `publicacoes_favoritos` (inválida em SQL)

O desenho anterior declarava `documento_id` e `avulsa_id` como `primary_key=True, nullable=True`,
para modelar "favorito de manual OU de avulsa". **Coluna de PRIMARY KEY não pode ser nullable**:
no PostgreSQL a criação da tabela falha; no SQLite "funciona" por um quirk histórico de
compatibilidade e passa a **aceitar duplicatas silenciosamente**, porque `NULL != NULL` na
comparação de chave. Ou seja: quebraria a portabilidade que o projeto paga para ter, e no
ambiente de desenvolvimento o bug ficaria invisível.

**Correção aplicada:** PK surrogate (`id` UUID) + `CheckConstraint` XOR garantindo exatamente um
alvo preenchido + duas `UniqueConstraint` separadas (`usuario_id, documento_id` e
`usuario_id, avulsa_id`). NULLs são distintos em UNIQUE nos dois bancos, então as duplicatas
reais são bloqueadas e os NULLs não conflitam entre si.

### 🔴 B2 — `document_id` determinístico colidiria na primeira publicação anual

O UUID v5 era derivado de `(manual_codigo, file_key)`. Mas a §8.6 do parecer mantém **duas
edições online simultaneamente** (vigente + anterior). O mesmo arquivo existe nas duas → mesma
entrada → mesmo UUID → **violação de PK em `manuais_documentos`** no exato momento da primeira
publicação de edição nova, que é a operação mais crítica e menos testada do sistema.

**Correção aplicada:** `edicao_rotulo` entra no input do UUID v5. Isso exigiu reinterpretar o
CA-07 — feito explicitamente em `03_especificacao_tecnica.md` §2.2: o critério externo fala em
estabilidade "após reindexação **sem mudança no arquivo**" (mesma edição → mesmo ID ✅); links
antigos continuarem apontando para a edição antiga é a rastreabilidade que manutenção
aeronáutica exige, não uma violação.

### 🔴 B3 — FK de `ata_codigo` para `sistemas_ata` quebraria a indexação 🔬

O desenho previa `ata_codigo` como FK opcional para `sistemas_ata.codigo`.

**Medido:** `docs/fim/` sozinho tem **28 capítulos ATA** (21, 22, 23, 24, 26, 27, 28, 29, 30, 31,
32, 33, 34, 35, 36, 42, 52, 61, 71, 73, 74, 76, 77, 79, 93, 94, 95, 97), e
`scripts/seed/seed_sistemas_ata.py` seeda **8** (22, 23, 27, 31, 34, 42, 94, 97). Com PRAGMA
`foreign_keys=ON` (ativo, `database.py:47-65`), a inserção de documento de qualquer um dos 20
capítulos não seedados falharia — mais de 70% dos capítulos do piloto.

**Correção aplicada:** `ata_codigo` vira `String(4)` indexado **sem FK**; o join com
`sistemas_ata` acontece em query, quando o código existir lá. Modela a realidade: o acervo cobre
mais ATAs do que o SAA29 cataloga hoje.

### 🔴 B4 — auditoria de acesso se autodestruía com `ondelete="CASCADE"`

`publicacoes_acessos` tinha CASCADE em `documento_id`. Como o indexador **remove documentos que
sumiram do acervo** (RN-09), cada reindexação apagaria silenciosamente o histórico de quem
consultou aqueles documentos. Auditoria que some quando o objeto auditado some não é auditoria —
e o `RBAC.md` §4 exige que "toda ação crítica seja auditável".

**Correção aplicada:** `ondelete="SET NULL"` + coluna `documento_titulo` com **snapshot do título
no momento do acesso**, para o registro continuar legível após a remoção. Favoritos mantêm
CASCADE de propósito (favorito de documento removido *deve* sumir). Regra complementar
registrada: edições nunca sofrem hard delete — `ARQUIVADA` descarta artefatos de disco/R2, nunca
as linhas de catálogo que sustentam as FKs da auditoria.

### 🔴 B5 — formato de UUID divergente entre os dois bancos 🔬

**Medido:** o tipo `Uuid` do SQLAlchemy grava no SQLite como **hex de 32 caracteres sem hífens**
(`9a6a262f6c5948bca07dee6ff17b8b10`), enquanto `str(uuid.UUID(...))` — a forma natural de gravar
no `catalog.db` — produz a **forma canônica com hífens**.

Como os dois bancos são engines separadas, o `document_id` viaja entre eles **como string**. Uma
comparação crua devolve zero resultados **sem lançar erro**: a busca simplesmente não acha nada,
e o sintoma ("índice vazio?") aponta para o lugar errado.

**Correção aplicada:** §2.2.1 nova em `03_especificacao_tecnica.md`, com contrato explícito
(`catalog.db` sempre canônico; conversão obrigatória por `uuid.UUID()` antes de qualquer query
ORM) e **teste de integração obrigatório** do round-trip busca → `catalog.db` → banco principal.

### 🔴 B6 — os filtros `manual`/`chapter` do contrato de API eram inimplementáveis

O contrato de `GET /publicacoes/api/busca` (herdado da `Especificacao.MD` §4 e preservado
deliberadamente) aceita `manual`, `chapter` e `category`. Mas o `catalog.db` continha **apenas**
`pages(document_id, page_number, text)` — nenhum dado de manual ou capítulo. E não há JOIN
possível com o banco principal: são engines distintas, uma delas `sqlite3` puro e read-only. Os
filtros só poderiam ser aplicados **depois** de trazer todos os resultados para a aplicação, o
que quebra `LIMIT`/`OFFSET` e o campo `total`.

**Correção aplicada:** tabela `documents` desnormalizada dentro do `catalog.db`
(`document_id, manual_codigo, capitulo, titulo, categoria`) + índices. Filtro, ordenação e
paginação passam a acontecer inteiramente dentro do `catalog.db`, em uma query só. É dado
derivado dentro do índice descartável — perfeitamente coerente com a arquitetura, e ainda elimina
um N+1 no banco principal para montar cada resultado.

### 🔴 B7 — FTS5 de conteúdo externo não se popula sozinho, e a contagem engana 🔬

O esquema usa `content='pages'` (external content). **Medido:**

| Momento | `count(*) FROM pages_fts` | `MATCH 'sangria'` |
|---|---:|---:|
| Após inserir 2 páginas em `pages` | **2** ✅ (engana) | **0** 🔴 |
| Após `INSERT INTO pages_fts(pages_fts) VALUES('rebuild')` | 2 | **2** ✅ |

A contagem lê *através* da tabela de conteúdo e devolve o número certo, então um teste de fumaça
por contagem passa enquanto **toda busca retorna vazio**. É o tipo de bug que consome um dia de
depuração no lugar errado (query? sanitização? tokenizer?).

**Correção aplicada:** `rebuild` + `optimize` obrigatórios ao final da carga, documentados com a
tabela de comportamento medido, e **regra explícita de que o aceite do índice se dá por busca
real, nunca por contagem**.

### 🔴 B8 — o `snippet` com `<mark>` é XSS 🔬

Todo o frontend passa dados por `escapeHtml` (`app.js:223`), mas o snippet **precisa** renderizar
`<mark>` como HTML. As duas saídas óbvias estão erradas: `escapeHtml` mostra `&lt;mark&gt;`
literal; `innerHTML` direto executa script vindo do conteúdo. E não é ameaça hipotética — a
**ementa das publicações avulsas é entrada de usuário** e vai para a busca.

**Medido** com `snippet(pages_fts, 0, '<mark>', '</mark>', …)` sobre um texto contendo
`<img src=x onerror=alert(1)>`: o payload volta íntegro e executável.

**Correção aplicada:** delimitadores sentinela (`char(2)`/`char(3)`) no SQL, `escapeHtml` no
cliente e só então a troca dos sentinelas por `<mark>`. Resultado medido: `procedimento
&lt;img src=x onerror=alert(1)&gt; <mark>sangria</mark> do compressor` — tag neutralizada,
realce preservado. Mais teste obrigatório em `tests/security/`.

---

## Simplificações

### 🟢 S1 — `PUBLICACOES_ENABLED` removida

A motivação (subir com o módulo desligado até o acervo existir) **morreu com a Revisão 5**: o
acervo já está no disco e o desenvolvimento é local. O custo era real: registro condicional de
rotas complica boot e testes (`app` é instância de módulo criada no import) e o item de menu
viraria link morto quando desligada. O que a flag protegeria já é coberto por construção —
`catalog.db` ausente → `/api/status` reporta índice ausente e a UI mostra estado vazio (E-12).

### 🟢 S2 — `PUBLICACOES_MODO` removida

A flag guardava "rotas de ingestão" que **não existem em nenhum marco do plano**: a estação de
publicação é um script (`publicar.py`) e ativar/reverter são rotas admin que *devem* existir no
servidor. Uma flag que não guarda nada é configuração morta que ainda assim precisa ser
documentada, testada e explicada. Reintroduzir apenas se algum dia existirem rotas de ingestão
de verdade.

---

## Lacunas de convenção (contra `00_mapa_arquitetural.md`)

| # | Lacuna | Correção aplicada |
|---|---|---|
| C1 | Sem rate limit em nenhum endpoint — o mapa (§5, §7.5) registra "1 de 117 endpoints" como risco estrutural | `@limiter.limit("30/minute")` na busca e `"10/minute")` no upload de anexo. Nota de que o decorator **exige `request: Request`** na assinatura (precedente `panes/router.py:107`) |
| C2 | `total`/`limit`/`offset` sem limites declarados | `ge`/`le` nos `Query` **e** guarda no service (que também é chamado por scripts, fora do FastAPI) |
| C3 | Risco de sombrear `fastapi.status` com filtro `status` | `status_filtro: ... = Query(alias="status")` — trap real já documentado em `panes/router.py:71-75` |
| C4 | Enum `RevisionStatus` usado na tabela mas nunca declarado; imports de `CheckConstraint`/`UniqueConstraint` ausentes no bloco de `models.py` | Ambos adicionados |
| C5 | `scripts/publicacoes/` sem `__init__.py`, embora o script importe de `app.*` e rode como `python -m` | `__init__.py` explicitado no layout, com o precedente (`scripts/__init__.py`, `scripts/seed/__init__.py`) |

Também registrado: `ruff.toml` já dá `per-file-ignores` a `scripts/**`, mas `app/modules/publicacoes/`
fica sob as regras plenas — com destaque para **`ASYNC`** (I/O bloqueante em `async def` reprova o
gate, daí `asyncio.to_thread` em toda leitura de `catalog.db` e de arquivo) e **`S608`** (SQL por
f-string reprova, daí `MATCH ?` por bind parameter).

---

## Verificações que passaram (nenhuma ação necessária)

| Hipótese testada | Resultado |
|---|---|
| `fim.json` teria mensagens duplicadas, quebrando `UniqueConstraint("mensagem")` 🔬 | **1.377 entradas, 1.377 mensagens únicas, zero duplicatas** — constraint segura contra o dado real |
| `ORDER BY bm25()` poderia estar invertido 🔬 | `ASC` está correto (bm25 do SQLite é negativo; mais negativo = mais relevante). Corpus de 52 docs: termo 4× em texto curto `-5.5080`, termo 1× em texto longo `-0.3785`. Documentado na query de referência, porque `DESC` inverteria o ranking e passaria em qualquer teste que só verifique "veio resultado" |
| PK composta em `pages` impediria o `content_rowid='rowid'` do FTS5 🔬 | Funciona — a tabela mantém rowid implícito e o join `p.rowid = pages_fts.rowid` resolve |
| `remove_diacritics 2` casaria `sangría`/`SANGRIA`/`sangria` (CA-04) 🔬 | Confirmado: os três retornam o mesmo conjunto |
| `snippet()` aceitaria delimitadores arbitrários 🔬 | Aceita — viabiliza a solução de sentinela do B8 |

---

## Efeito no plano de execução

Nenhum marco muda de ordem ou de escopo. O que muda é **densidade de tarefa**: M1 ganha o
`rebuild` do FTS, a tabela `documents` no `catalog.db`, o contrato de UUID e o tratamento de
snippet; M2 ganha o teste de XSS. Nada disso é trabalho novo de arquitetura — é detalhe que
teria sido descoberto na implementação, cada um custando entre horas e um dia de depuração,
sendo que B5, B7 e B8 falham **silenciosamente** (sem exceção, sem log), que é a categoria mais
cara.

**Recomendação de sequência dentro do M1**, para que os bugs silenciosos apareçam cedo:

1. `catalog.py` (parser Lucene, com os números de `02_formato_indice_lucene.md` §7 como
   regressão) — é a base de tudo e já tem gabarito de verificação;
2. `indexar.py` gerando `catalog.db` **com o rebuild**, validado por **busca real** (B7);
3. teste de round-trip de UUID entre os dois bancos (B5) — antes de qualquer UI, porque é o
   contrato que a UI vai assumir como dado;
4. `search.py` + rota de busca;
5. viewer PDF.js + tratamento de snippet (B8) + medição de CSP;
6. resto da UI.
