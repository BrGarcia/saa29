# Especificação Funcional e Técnica — Sistema de Consulta de Manuais EMB-314

> Documento complementar ao [Projeto.MD](Projeto.MD). O Projeto.MD define **o quê e por quê**
> (arquitetura, stack, roadmap); este documento define **exatamente como cada funcionalidade
> se comporta**: telas, rotas, contrato de API, regras de negócio, casos de borda e critérios
> de aceite. É o documento de trabalho da equipe de desenvolvimento.

**Data:** 03/08/2026 · **Versão:** 1.0 · **Escopo:** Fases 0–2 do roadmap (MVP → v1.0)

---

## 1. Perfis de Usuário e Casos de Uso

| Perfil | Necessidade principal | Cenário típico |
|---|---|---|
| **Mecânico de manutenção** | Achar um procedimento/subject rapidamente | Busca "sangria do compressor" no hangar, pelo celular, abre a página exata |
| **Piloto** | Consultar manuais operacionais (checklists, boletins) | Navega por categoria → manual → capítulo, no tablet |
| **Gestor de publicações** | Publicar/atualizar manuais | Copia a pasta nova para `data/`, confere na página de status que foi indexada |

Casos de uso do MVP:
- **UC-01** Navegar: categoria → manual → capítulo → documento → visualizar PDF.
- **UC-02** Buscar por palavra-chave em todo o acervo e abrir o resultado na página exata.
- **UC-03** Buscar dentro de um manual específico (filtro).
- **UC-04** Publicar manual novo copiando pasta para `data/` (sem código).
- **UC-05** (v1.0) Favoritar documentos e rever histórico de consulta.

---

## 2. Mapa de Navegação e URLs

Todas as rotas HTML são server-rendered (Jinja2); as rotas `/api/*` retornam JSON.

| Rota | Conteúdo |
|---|---|
| `GET /` | Home: manuais agrupados por categoria + campo de busca global |
| `GET /manual/{manual_path}` | Capítulos/seções do manual (ex.: `/manual/AMM_PART1_1651`) |
| `GET /manual/{manual_path}/{chapter}` | Documentos do capítulo, em `sort_order` |
| `GET /viewer?doc={id}#page={n}` | PDF.js carregando `/data/...` na página `n` |
| `GET /search?q=...&manual=...&chapter=...` | Página de resultados (usa `/api/search` via htmx) |
| `GET /data/{path}` | PDF estático (servido pelo Caddy, não pela app) |
| `GET /api/search` | Busca JSON (contrato na seção 4) |
| `GET /api/status` | Estado do índice (contrato na seção 4) |
| `POST /admin/reindex` | Dispara reindexação incremental (protegido) |

Regra: URLs de documento são **estáveis e derivadas do caminho em `data/`** — podem ser
compartilhadas por link e continuam válidas entre reindexações.

---

## 3. Especificação de Telas

### 3.1 Home (`/`)
```
┌──────────────────────────────────────────────────────┐
│  🛩  Manuais EMB-314 Super Tucano                     │
│  ┌────────────────────────────────────────────┐      │
│  │ 🔍 Buscar em todos os manuais...           │      │
│  └────────────────────────────────────────────┘      │
│                                                       │
│  MANUTENÇÃO                                           │
│   ▸ AMM Parte I — Manual de Manutenção (SDS)  Rev.10  │
│   ▸ AMM Parte II — Manual de Manutenção (MPP) Rev.10  │
│   ▸ FIM — Manual de Pesquisa de Panes         Rev.7   │
│  OPERAÇÃO                                             │
│   ▸ ...                                               │
│  BOLETINS E INFORMATIVOS                              │
│   ▸ BS — Boletim de Serviço                           │
└──────────────────────────────────────────────────────┘
```
- Agrupamento por categoria (RN-04). Cada manual mostra **descrição em PT** (RN-03)
  e **revisão/data** (RN-06).
- Busca com sugestões a partir de 3 caracteres (v1.0; no MVP, submit simples).

### 3.2 Manual (`/manual/{path}`)
- Breadcrumb `Home › AMM Parte I`.
- Lista de capítulos na ordem natural (`010_FRONTMATTER` antes de `CHAPTER_21`; RN-05).
- Campo "buscar somente neste manual" (preenche `manual=` na busca).

### 3.3 Capítulo (`/manual/{path}/{chapter}`)
- Documentos em `sort_order`, exibindo o **título humano** do `.title` (RN-02).
- Badge `REVISADO` quando `revision_status = REVISED`.
- Clique → viewer.

### 3.4 Resultados de busca (`/search`)
```
│ 🔍 "sangria do compressor"          [Filtrar: Manual ▾] │
│ 142 resultados (12 ms)                                  │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ SUBJECT 75-30-00 — SANGRIA DO COMPRESSOR            │ │
│ │ AMM Parte I › Capítulo 75 · pág. 3                  │ │
│ │ ...a válvula de **sangria do compressor** deve...   │ │
│ └─────────────────────────────────────────────────────┘ │
```
- Cada resultado: título do documento, trilha (manual › capítulo), **página**, snippet
  com termos destacados. Clique abre o viewer já na página.
- Paginação de 20 em 20 (htmx "carregar mais").

### 3.5 Viewer (`/viewer`)
- PDF.js em tela cheia com barra mínima: voltar, título, página atual/total, download,
  busca interna do PDF.js.
- Deep-link `#page=N` obrigatório (é o coração do UC-02).
- Fallback: se PDF.js falhar, `<iframe>`/objeto nativo do navegador com o mesmo `#page=N`.
- Mobile: pinch-zoom e swipe de página funcionais.

---

## 4. Contrato de API

### `GET /api/search`
Parâmetros: `q` (obrigatório), `manual`, `chapter`, `category`, `limit` (default 20), `offset`.

```json
{
  "query": "sangria do compressor",
  "total": 142,
  "took_ms": 12,
  "results": [
    {
      "doc_id": 4821,
      "title": "SUBJECT 75-30-00 - SANGRIA DO COMPRESSOR",
      "manual": {"path": "AMM_PART1_1651", "description": "SDS - Manual de Manutenção da Aeronave"},
      "chapter": "CHAPTER_75",
      "page": 3,
      "snippet": "...a válvula de <mark>sangria</mark> do <mark>compressor</mark> deve...",
      "pdf_url": "/data/AMM_PART1_1651/CHAPTER_75/SDS1651_75-30-00.PDF",
      "viewer_url": "/viewer?doc=4821#page=3"
    }
  ]
}
```
Erros: `400` se `q` vazio ou sintaxe FTS inválida (a app **sanitiza** a query antes —
aspas desbalanceadas etc. não podem virar 500; ver E-06).

### `GET /api/status`
```json
{
  "manuals": 53, "documents": 12117, "pages_indexed": 486210,
  "documents_without_text": 84,
  "last_index_run": "2026-08-03T14:22:05Z",
  "index_state": "idle | running",
  "db_size_bytes": 1873215488
}
```

### `POST /admin/reindex`
- Protegido (token via header ou auth básica — decisão D-02).
- Responde `202 Accepted` imediatamente; progresso acompanhado por `/api/status`.
- Se já houver indexação em curso: `409 Conflict`.

---

## 5. Regras de Negócio (RN)

Fontes de dados verificadas no acervo real em 03/08/2026.

**RN-01 — Descoberta de documentos.** Documento = qualquer arquivo `*.pdf`/`*.PDF` sob
`data/` (case-insensitive). Estrutura esperada `data/<MANUAL>/<CAPÍTULO>/arquivo.pdf`, mas
PDFs em qualquer profundidade devem ser indexados (nível extra vira parte da trilha).
Ignorar: `.title`, `.xml`, `.ini`, `.bak`, `.DS_Store` e demais não-PDF.

**RN-02 — Título do documento.** Ordem de precedência:
1. Arquivo `.title` homônimo (formato: linha 1 = aviso fixo; **linha 2** = `NOME.PDF <título>`;
   **linha 3** = status de revisão `UNCHANGED`/`REVISED`). Extrair o título removendo o
   prefixo do nome de arquivo. Guardar a linha 3 em `revision_status`.
2. Metadado `title` interno do PDF (via PyMuPDF), se não vazio/genérico.
3. Nome do arquivo tratado (sem extensão, `_`→espaço).

**RN-03 — Descrição do manual.** De `data/manual_details.xml`
(`<manual partnumber type><custom-description>`), casando `type` + `partnumber` com o nome
da pasta (`AMM_PART1_1651` → type `AMM_PART1`, PN `1651`). Complemento: `collections.ini`
traz nomes amigáveis por coleção. Fallback: nome da pasta.

**RN-04 — Categoria.** De `manual_type.xml` (`catid` por `typeid`). Os `catid` numéricos
(1–7) **não têm rótulo nos arquivos** — mapeamento nome↔número é a decisão em aberto D-01;
até lá, usar provisoriamente: 1=Manutenção, 3=Operação, 4=Boletins, demais="Outros".
O mapeamento fica em config (`categories.toml`), nunca hardcoded.

**RN-05 — Ordenação.** Prefixo numérico `NNN_` do nome de arquivo/pasta define
`sort_order` (`010_FRONTMATTER` < `020_...`). Sem prefixo: ordem alfabética após os
prefixados. Capítulos: `010_FRONTMATTER` primeiro, depois `CHAPTER_NN` por número.

**RN-06 — Revisão do manual.** De `data/version/<MANUAL>.txt` (linhas `Rev. N`,
`Date: MM/DD/YYYY`, `TR:`). A pasta `version/` dos sistemas antigos deve ser levada para
`data/version/` no merge da Fase 0. Exibir "Rev. 10 · 19/06/2015" no card do manual.

**RN-07 — Encoding.** `.ini` e alguns legados estão em **Latin-1 (cp1252)**; XMLs declaram
UTF-8; `.title` tratar como UTF-8 com fallback cp1252. Toda leitura de metadado passa por
uma função única `read_text_legacy()` que tenta UTF-8 → cp1252. Nunca deixar exception de
decode derrubar a indexação.

**RN-08 — Deduplicação (merge Fase 0).** Mesmo caminho relativo nos dois `Data/`:
- hash igual → manter um;
- hash diferente → manter o de **mtime mais recente** e registrar no relatório de merge
  (`merge_report.txt`) para revisão humana. Nenhum arquivo é descartado silenciosamente:
  os preteridos vão para `_merge_conflicts/`.

**RN-09 — Indexação incremental.** Chave `(file_path, mtime, size)`. Mudou → re-extrai.
Sumiu do disco → remove de `documents`/`pages`/`pages_fts` na mesma transação.
Novo → indexa. A indexação roda em processo/thread de background e **nunca bloqueia** a UI.

**RN-10 — Busca.** FTS5 com `unicode61 remove_diacritics 2`. A query do usuário é
convertida em sintaxe FTS segura: termos viram `termo*` (prefixo) unidos por `AND`;
aspas do usuário viram busca de frase; caracteres de controle FTS (`^ : ( ) -`) são
escapados. Ranking BM25; snippet de ~30 tokens com `<mark>`.

---

## 6. Casos de Borda — comportamento definido (E)

| # | Situação | Comportamento |
|---|---|---|
| E-01 | PDF sem camada de texto (escaneado) | Indexa metadados, `has_text=0`; aparece na navegação e no viewer; excluído da busca full-text; contabilizado em `/api/status` |
| E-02 | PDF corrompido / PyMuPDF lança exceção | Loga com caminho, marca `has_text=0`, segue a indexação (nunca aborta o lote) |
| E-03 | `.title` ausente ou malformado | Cai para RN-02 níveis 2 e 3 |
| E-04 | Pasta de manual sem entrada nos XMLs | Manual aparece com nome da pasta, categoria "Outros" |
| E-05 | PDF solto na raiz de `data/` | Indexado sob manual sintético "Documentos avulsos" |
| E-06 | Query FTS inválida (aspas desbalanceadas etc.) | Sanitização da RN-10; jamais retornar 500 |
| E-07 | Busca sem resultados | Página com "nenhum resultado", sugestão de remover filtros/verificar grafia |
| E-08 | Arquivo removido de `data/` com link/favorito apontando para ele | Viewer responde 404 com página amigável "documento removido do acervo" |
| E-09 | Reindexação disparada durante indexação em curso | `409`; nunca duas indexações simultâneas (lock) |
| E-10 | Nomes com espaços/acentos no caminho | URLs sempre percent-encoded; testes cobrem caso real |
| E-11 | PDF > 100 MB no mobile | PDF.js com range requests carrega por página; nunca bloquear por tamanho |
| E-12 | `data/` vazio no primeiro boot | Home exibe estado vazio com instrução de publicação (UC-04); app sobe normalmente |

---

## 7. Critérios de Aceite (formato Dado/Quando/Então)

**CA-01 (UC-02 — busca com página exata)**
Dado o acervo indexado, quando busco `sangria do compressor`,
então recebo resultados em <300 ms (p95) com o SUBJECT 75-30-00 entre os 3 primeiros,
e ao clicar o PDF abre **na página do trecho**, não na página 1.

**CA-02 (UC-04 — publicação sem código)**
Dado um manual novo copiado para `data/`, quando a reindexação roda (boot ou `/admin/reindex`),
então o manual aparece na home com título/categoria corretos **sem nenhuma alteração de código
ou banco manual**.

**CA-03 (UC-01 — navegação mobile)**
Dado um celular (viewport 375 px), quando navego home → manual → capítulo → documento,
então todos os toques têm alvo ≥ 44 px, nada exige scroll horizontal e o PDF é legível
com zoom por gesto.

**CA-04 (busca com diacríticos)**
Quando busco `sangria` ou `SANGRIA` ou `sangría`,
então os três retornam o mesmo conjunto de resultados.

**CA-05 (resiliência da indexação)**
Dado um lote com 1 PDF corrompido entre 100, quando a indexação roda,
então os 99 são indexados, o corrompido é logado e `/api/status` reflete a contagem.

**CA-06 (consumo de recursos)**
Dado o sistema em regime com o acervo completo (~12 mil PDFs),
então RSS do processo < 200 MB e a home responde em < 100 ms (p95) na VPS-alvo.

**CA-07 (estabilidade de links)**
Dado um link `/viewer?doc=...#page=12` compartilhado, quando o acervo é reindexado
(sem mudança no arquivo), então o link continua abrindo o mesmo documento na mesma página.

---

## 8. Metas Não Funcionais (mensuráveis)

| Métrica | Alvo | Como medir |
|---|---|---|
| Busca p95 | < 300 ms | log de `took_ms` |
| Home/navegação p95 | < 100 ms | access log do Caddy |
| RSS do processo | < 200 MB | `systemd`/`docker stats` |
| Boot da app | < 2 s (índice existente) | log de startup |
| Indexação completa inicial | < 60 min na VPS-alvo | log do indexador |
| Indexação incremental (1 manual novo) | < 2 min | idem |
| Lighthouse mobile (home e busca) | ≥ 90 performance / ≥ 90 acessibilidade | CI ou manual |

---

## 9. Fora de Escopo do MVP (explícito)

- OCR de PDFs escaneados (Fase 3).
- Busca semântica / RAG / LLM (Fase 3).
- Contas de usuário e permissões por perfil (favoritos do MVP usam `localStorage`).
- Edição/anotação de PDFs (o legado `Comments` será apenas arquivado; migração é decisão D-03).
- Impressão controlada e watermarking.
- Sincronização offline completa (apenas cache básico do navegador).

## 10. Decisões em Aberto (resolver antes/durante a Fase 1)

| # | Decisão | Opções | Responsável | Prazo |
|---|---|---|---|---|
| D-01 | Rótulos oficiais dos `catid` 1–7 | Confirmar com usuários do sistema antigo (telas do TechData) | Bruno | Fase 1 |
| D-02 | Acesso restrito? | Aberto na rede interna · auth básica · login individual | Bruno | Fase 1 |
| D-03 | Migrar comentários do legado (`Comments/`)? | Arquivar · migrar para v1.0 | Bruno | Fase 2 |
| D-04 | Domínio/host e provedor da VPS | — | Bruno | antes do deploy |
| D-05 | Manuais presentes só em um dos dois sistemas antigos (2 casos) | Verificar no relatório de merge se são de acesso restrito a pilotos | Bruno | Fase 0 |

## 11. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| PDFs vetoriais com texto em curvas (sem camada extraível) | Busca não os encontra | Contagem em `/api/status` já no MVP dimensiona o problema; OCR na Fase 3 |
| Encoding legado (cp1252) corromper títulos | Acentuação quebrada na UI | RN-07 + teste automatizado com amostras reais |
| Query FTS maliciosa/malformada | 500 na busca | RN-10 (sanitização) + teste fuzz simples |
| VPS com disco lento (não NVMe) | Busca acima da meta | Validar com benchmark na Fase 1 antes de fechar provedor (D-04) |
| Acervo crescer além do previsto | Índice > disco | `/api/status` expõe `db_size_bytes`; fronteira de troca descrita no Projeto.MD §10 |

---

## 12. Sequência de Trabalho Sugerida para a Equipe

1. **Fase 0** — rodar `merge_data.py`, revisar `merge_report.txt`, resolver D-05.
2. Resolver D-01/D-02 (bloqueiam rótulos da home e o `/admin/reindex`).
3. **Fase 1** — ordem de implementação com dependências mínimas:
   `catalog.py` (parsers + testes com dados reais) → `indexer.py` → `search.py` →
   rotas/templates → viewer → deploy.
4. Validar CA-01..CA-07 na VPS-alvo com o acervo completo antes de declarar MVP pronto.

> Testes: cada RN e cada E da seção 6 vira ao menos um teste automatizado (pytest),
> usando uma amostra pequena e real do acervo versionada em `tests/fixtures/`.
