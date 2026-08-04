# Projeto: Sistema Web de Consulta de Manuais Técnicos — EMB-314 Super Tucano

> Documento de direcionamento técnico. Substituição da solução Java/Lucene atual por um
> sistema web leve, otimizado para VPS de baixo custo, preparado para futura integração com IA.

**Data:** 03/08/2026
**Status:** Proposta aprovada — aguardando início da Fase 0

---

## 1. Visão Geral

### Objetivo
Sistema web único para consulta dos manuais técnicos da aeronave EMB-314 Super Tucano,
unificando as aplicações atuais (`Program` — manutenção; `Program_Operational` — operação)
em um só sistema com diretório central `data/`.

### Regra de ouro
**Adicionar um manual = copiar a pasta para `data/`.** Nenhuma alteração de código,
nenhum cadastro manual. O indexador detecta e absorve automaticamente.

### Diagnóstico do acervo atual (inspecionado em 03/08/2026)
| Item | Valor |
|---|---|
| PDFs totais | ~12.100 |
| Volume | ~3 GB (`Program/Data` 2,0 GB + `Program_Operational/Data` 1,1 GB) |
| Manuais | 53 em `Program`, 51 em `Program_Operational` — **51 sobrepostos** |
| Estrutura | Pasta por manual → pasta por capítulo → PDFs |
| Metadados existentes | `manual_details.xml` (descrições PT), `manual_type.xml` (categorias), `ALXapplicability_control.xml` (efetividade), arquivos `.title` ao lado de cada PDF |
| Sistema antigo | Java + Lucene (pastas `Index/` com segmentos `.tis/.frq/...`) — será descartado |

Exemplo de `.title` (fonte primária de títulos, gerada pela Embraer TechPubs):
```
SDS1651_75-30-00.PDF AMM PART I-1651 - SUBJECT 75-30-00 - SANGRIA DO COMPRESSOR
UNCHANGED
```
A segunda linha traz o status de revisão (`UNCHANGED`/`REVISED`).

---

## 2. Arquitetura

Monólito modular com índice embutido — **um processo, um arquivo de banco, zero serviços externos**
(sem Elasticsearch, sem Postgres, sem Redis, sem JVM).

```
┌─────────────────────────── VPS (1 GB RAM) ───────────────────────────┐
│                                                                       │
│  Caddy (reverse proxy + TLS automático + gzip)                        │
│     │                                                                 │
│     ├── /data/*  ──► arquivos PDF estáticos (com Range requests)      │
│     │                                                                 │
│     └── /*  ──► App Python (FastAPI + Uvicorn, 1 worker)              │
│                    ├── UI (Jinja2 + htmx + PDF.js)                    │
│                    ├── API de busca ──► SQLite FTS5 (catalog.db)      │
│                    └── Indexador (scan de data/ no boot + sob demanda)│
│                                                                       │
│  data/            ◄── manuais (só copiar arquivos, zero código)       │
│  index/catalog.db ◄── catálogo + texto extraído + índice FTS          │
└───────────────────────────────────────────────────────────────────────┘
```

Princípios:
- **Consumo de RAM alvo: 80–150 MB.** SQLite lê sob demanda do disco (não carrega índice
  em memória como o Lucene/JVM).
- **PDFs nunca passam pela aplicação Python.** O Caddy os serve direto do disco com
  `Range` requests — essencial para o PDF.js abrir a página N sem baixar o arquivo inteiro.
- **Zero orquestração.** Deploy = `docker compose up -d` (ou systemd puro).

---

## 3. Stack Tecnológica

| Camada | Escolha | Justificativa |
|---|---|---|
| Linguagem | **Python 3.12** | Melhor ecossistema para extração de PDF; caminho mais curto para RAG/embeddings futuros (critério que desempata contra Go) |
| Web framework | **FastAPI + Uvicorn** | Leve (~50 MB RSS), async, docs de API automáticas, maduro |
| Extração de texto | **PyMuPDF (fitz)** | Núcleo em C, ~10–50 páginas/s; ordens de magnitude mais rápido que pdfminer/PyPDF2 |
| Busca | **SQLite FTS5** | Full-text nativo com BM25, `snippet()` e `highlight()`; zero serviço extra; substitui o Lucene diretamente |
| Frontend | **Jinja2 + htmx + Tailwind** | Server-rendered = leve no servidor e no celular; sem build de SPA; htmx (~14 KB) dá a interatividade necessária |
| Viewer de PDF | **PDF.js** (fallback: viewer nativo do navegador) | Deep-link `#page=N` — a busca leva direto à página do resultado |
| Proxy | **Caddy** | TLS automático, config de ~10 linhas, estáticos com range/gzip |
| Deploy | **Docker Compose** (alternativa: systemd) | `git pull && docker compose up -d` |

Restrições respeitadas: sem Java, tudo open source, ~6 dependências Python no total.

---

## 4. Estrutura de Diretórios

```
supertucano-docs/
├── data/                        # ÚNICA pasta de conteúdo (merge dos dois Data/)
│   ├── AMM_PART1_1651/
│   │   ├── CHAPTER_75/
│   │   │   ├── SDS1651_75-30-00.PDF
│   │   │   └── SDS1651_75-30-00.title   # já existente — vira metadado
│   │   └── ...
│   ├── manual_details.xml       # já existente — descrições dos manuais
│   ├── manual_type.xml          # já existente — categorias
│   └── ...
├── index/
│   └── catalog.db               # SQLite (gerado; nunca versionado no git)
├── app/
│   ├── main.py                  # FastAPI, rotas HTML e API
│   ├── indexer.py               # scan de data/, extração PyMuPDF, escrita FTS
│   ├── catalog.py               # parse dos XML e .title, modelo de metadados
│   ├── search.py                # consultas FTS5, snippets, ranking, filtros
│   ├── templates/               # Jinja2: base, home, manual, capítulo, busca, viewer
│   └── static/                  # htmx, pdf.js, css
├── scripts/
│   └── merge_data.py            # Fase 0: unificação dos dois Data/
├── Caddyfile
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 5. Fluxo de Funcionamento

1. **Boot** — app sobe em <1 s; indexador dispara em background (não bloqueia o serviço).
2. **Indexação** — varre `data/`, compara `(caminho, mtime, tamanho)` com o catálogo;
   processa só PDFs novos/alterados; lê `.title` e XMLs para título, manual e categoria.
3. **Navegação** — home lista manuais por categoria (Manutenção / Operação / Boletins,
   derivado de `manual_type.xml`) → capítulos → documentos, tudo espelhando a estrutura de pastas.
4. **Busca** — usuário digita → htmx consulta `/api/search?q=...` → FTS5 retorna resultados
   ranqueados por BM25 com snippet destacado e **número da página** → clique abre o PDF.js
   já na página certa (`/viewer?file=...#page=12`).
5. **Leitura** — PDF servido estático pelo Caddy; PDF.js renderiza progressivamente
   (importante para AMMs grandes e para mobile).

---

## 6. Indexação Automática

- **Granularidade por página**: cada página do PDF vira uma linha no índice FTS.
  É o que permite responder "resultado na página 12 do capítulo 75" em vez de
  "está em algum lugar neste PDF de 300 páginas".
- **Incremental e idempotente**: chave barata `(path, mtime, size)`; remoções detectadas
  (arquivo some de `data/` → sai do índice).
- **Disparo**: no boot + endpoint `POST /admin/reindex` + (Fase 2) watcher com `watchdog`.
- **Estimativa**: indexação completa inicial dos ~12 mil PDFs na ordem de 15–40 min
  (uma única vez); incrementais em segundos.
- **PDFs escaneados sem camada de texto**: marcados com `has_text = 0` — continuam
  navegáveis e visualizáveis; OCR fica para a Fase 3 (ocrmypdf), não bloqueia o MVP.

---

## 7. Modelo de Dados / Metadados

Aproveitar o que a Embraer já entrega — não inventar formato novo.

```sql
-- catálogo (SQLite, WAL mode)
CREATE TABLE manuals (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,            -- ex.: AMM_PART1
    part_number TEXT,              -- ex.: 1651
    description_pt TEXT,           -- de manual_details.xml
    category TEXT,                 -- de manual_type.xml (catid)
    path TEXT NOT NULL UNIQUE      -- ex.: AMM_PART1_1651
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    manual_id INTEGER REFERENCES manuals(id),
    chapter TEXT,                  -- ex.: CHAPTER_75
    file_path TEXT NOT NULL UNIQUE,
    title TEXT,                    -- do .title; fallback: metadado do PDF ou nome do arquivo
    sort_order INTEGER,            -- do prefixo numérico (010_, 020_, ...)
    pages INTEGER,
    mtime REAL, size INTEGER,      -- chave de indexação incremental
    has_text INTEGER DEFAULT 1,
    revision_status TEXT           -- UNCHANGED / REVISED (2ª linha do .title)
);

CREATE TABLE pages (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    page_number INTEGER,
    text TEXT
);

CREATE VIRTUAL TABLE pages_fts USING fts5(
    text,
    content='pages', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
```

Fallbacks: um PDF avulso jogado em `data/` sem `.title` e sem XML também funciona
(título = metadado interno do PDF ou nome do arquivo tratado).

---

## 8. Busca (substituição do Lucene)

SQLite FTS5 cobre tudo o que o Lucene fazia no sistema antigo:

- **BM25** para ranking; `snippet()` / `highlight()` nativos para trechos destacados.
- Prefix queries (`sangri*`), frases (`"sangria do compressor"`), AND/OR/NOT.
- Filtros combinados com SQL normal: por manual, capítulo, categoria.
- `remove_diacritics 2` → "aviao" encontra "avião"; adequado a conteúdo PT/EN misto.
- Desempenho: ~500 mil–1 M de linhas-página → consultas de poucos ms a dezenas de ms
  em NVMe de VPS, sem nada residente em RAM.

**Limitação conhecida (aceita):** FTS5 não faz stemming em português nativamente.
Para manuais técnicos (termos exatos, códigos ATA, part numbers) o impacto é mínimo;
se necessário, adiciona-se tokenizer customizado depois, sem mudar a arquitetura.

---

## 9. Preparação para IA / RAG

O desenho acima já entrega ~80% de um pipeline RAG:

1. A tabela `pages` **é** o corpus extraído e normalizado — a etapa mais cara de
   qualquer RAG (parsing de PDF) já estará pronta.
2. Evolução, tudo dentro do mesmo SQLite:
   - Tabela `chunks(document_id, page_start, page_end, text)` derivada de `pages`;
   - **sqlite-vec** (extensão leve em C) para embeddings e busca vetorial no próprio `catalog.db`;
   - Busca híbrida = `pages_fts` (BM25) + sqlite-vec (semântica) com fusão RRF;
   - Endpoint `/api/ask`: monta contexto e chama API de LLM externa (ex.: Claude) —
     a VPS só orquestra, não roda modelo.
3. Nenhum passo exige trocar banco, linguagem ou infraestrutura.

---

## 10. Escalabilidade

- O acervo atual (~12 mil PDFs) já é "milhares de documentos" — a arquitetura nasce dimensionada.
- `catalog.db` estimado em ~1–2 GB com texto por página; muito abaixo dos limites práticos do FTS5.
- WAL mode: leitores nunca bloqueiam; escrita só existe durante indexação.
- PDFs estáticos escalam com filesystem + cache do Caddy — a app não é gargalo.
- **Fronteira de troca limpa**: se um dia extrapolar (100k+ manuais, múltiplos operadores),
  `search.py` é o único módulo que passaria a conhecer um Meilisearch/Typesense.
  Não pagar esse custo agora.

---

## 11. Roadmap

### Fase 0 — Preparação (1–2 dias)
- [ ] Script `scripts/merge_data.py`: mesclar `Program/Data` + `Program_Operational/Data`
      em `data/`, com deduplicação por hash (51 manuais repetidos viram um só) e relatório
      de conflitos (arquivos de mesmo nome com conteúdo diferente → manter o mais recente e logar).
- [ ] Descartar `java/`, `lib/`, `Index/` (Lucene antigo) — manter backup até a v1.0 validada.
- [ ] Repositório git novo com a estrutura da seção 4.

### Fase 1 — MVP (1–2 semanas)
- [ ] `catalog.py`: parse de `manual_details.xml`, `manual_type.xml`, `.title`.
- [ ] `indexer.py`: scan incremental + PyMuPDF + escrita em `pages`/`pages_fts`.
- [ ] `search.py`: consulta FTS5 com BM25, snippets, página do hit.
- [ ] `main.py` + templates: home por categoria → manual → capítulo → documento;
      busca global; viewer PDF.js com deep-link de página.
- [ ] `Dockerfile`, `docker-compose.yml`, `Caddyfile`; deploy na VPS.
- **Critério de pronto:** qualquer manual pesquisável e legível no celular.

### Fase 2 — Versão 1.0 (2–3 semanas)
- [ ] Filtros de busca (manual, capítulo, categoria); sugestões por prefixo.
- [ ] Favoritos e histórico (substitui `TechDataFavoritesTouch` e `Comments` do sistema
      antigo — localStorage no início; conta simples se necessário).
- [ ] Reindexação automática (`watchdog`) + página de status do índice.
- [ ] Autenticação básica, se o acesso for restrito.
- [ ] Polimento mobile; opcional: cache de PDFs recentes via service worker.

### Fase 3 — Evoluções futuras
- [ ] OCR para PDFs sem camada de texto (ocrmypdf, job noturno).
- [ ] Chunks + sqlite-vec + busca híbrida (semântica).
- [ ] `/api/ask` com LLM — perguntas em linguagem natural com citação de página.
- [ ] Controle de revisões/efetividade por aeronave (base: `ALXapplicability_control.xml`).

---

## 12. Requisitos de Infraestrutura

| Item | Especificação mínima |
|---|---|
| VPS | 1 vCPU, 1 GB RAM, 20 GB disco (ideal NVMe) — faixa US$ 5–6/mês |
| SO | Linux (Debian/Ubuntu LTS) |
| Disco | ~3 GB (PDFs) + ~2 GB (índice) + sistema |
| Portas | 80/443 (Caddy cuida do TLS via Let's Encrypt) |

---

## 13. Critérios de Sucesso

- Busca em milissegundos com resultado apontando a página exata do PDF.
- RAM total do sistema < 200 MB em regime.
- Publicar manual novo = copiar pasta para `data/` (zero código, zero cadastro).
- Deploy reproduzível em um comando.
- Nenhuma dependência de Java em qualquer etapa.
- Corpus de texto pronto para RAG sem retrabalho.
