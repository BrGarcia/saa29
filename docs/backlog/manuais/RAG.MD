# RAG.MD — Plano de Implementação Futura: Busca Semântica e Perguntas em Linguagem Natural

> Documento de planejamento da **Fase 3** do roadmap ([Projeto.MD](Projeto.MD) §11).
> Não é escopo do MVP nem da v1.0 — mas o sistema base foi desenhado para que esta fase
> seja **incremental**: nenhum passo aqui exige trocar banco, linguagem ou infraestrutura.

**Data:** 03/08/2026 · **Versão:** 1.0 · **Pré-requisito:** v1.0 em produção e estável

---

## 1. Objetivo

Evoluir o sistema em dois degraus independentes:

1. **Busca semântica (híbrida)** — encontrar conteúdo por *significado*, não só por
   palavra exata: "superaquecimento na partida" encontra a seção sobre *hot start*
   mesmo sem essas palavras no texto.
2. **Perguntas em linguagem natural (`/api/ask`)** — "qual o torque dos parafusos do
   painel de acesso da seção 71?" → resposta em texto **com citação obrigatória de
   manual, capítulo e página**, montada por um LLM a partir de trechos recuperados
   do acervo (RAG — Retrieval-Augmented Generation).

Os degraus são independentes: a busca híbrida tem valor sozinha e pode ser entregue
sem o degrau 2.

## 2. Princípio de segurança operacional (inegociável)

Este sistema serve documentação aeronáutica. Regras fixas para qualquer resposta gerada:

- **R1 — Citação obrigatória.** Toda afirmação da resposta aponta manual + capítulo +
  página, com link direto para o viewer (`/viewer?doc=...#page=N`). Resposta sem fonte
  recuperada = "não encontrei no acervo", nunca conhecimento do modelo.
- **R2 — O documento oficial prevalece.** Disclaimer permanente na UI: a resposta é
  auxílio à *localização* da informação; o procedimento válido é o do manual exibido.
- **R3 — Sem geração de procedimento.** O prompt do sistema proíbe o LLM de completar,
  resumir criticamente ou "corrigir" procedimentos; ele localiza, transcreve e aponta.
- **R4 — Temperatura zero e trechos íntegros.** Snippets citados vêm do banco
  (tabela `chunks`), não da memória do modelo.

## 3. O que a arquitetura base já entrega (por que isto é incremental)

| Pré-requisito de RAG | Situação após v1.0 |
|---|---|
| Corpus extraído e limpo | ✅ tabela `pages` (texto por página, ~500 mil linhas) |
| Metadados por documento | ✅ `documents`/`manuals` (título, capítulo, revisão, categoria) |
| Busca lexical de qualidade | ✅ `pages_fts` (BM25) — vira a "perna lexical" da busca híbrida |
| Deep-link para a fonte | ✅ viewer com `#page=N` — vira o link de citação |
| Indexação incremental | ✅ RN-09 — embeddings entram no mesmo ciclo |

O trabalho novo se resume a: **chunking → embeddings → busca vetorial → fusão → (depois) geração**.

## 4. Arquitetura da evolução

```
                         ┌────────────────────────── mesma VPS ──────────────────────────┐
consulta ──► /api/search │  FTS5 (BM25)  ──┐                                             │
                         │                 ├─► fusão RRF ─► resultados híbridos          │
                         │  sqlite-vec ────┘        │                                    │
                         │  (embeddings)            │                                    │
pergunta ──► /api/ask ───┼──────────────────────────┴─► top-K chunks ─► LLM (API externa)│
                         │                                               │               │
                         │                              resposta + citações página a página
                         └───────────────────────────────────────────────────────────────┘
```

- **Nada de infra nova**: embeddings ficam no próprio `catalog.db` via extensão
  **sqlite-vec** (C puro, ~kb de dependência).
- **Nenhum modelo roda na VPS**: embeddings e geração são chamadas a APIs externas
  (a VPS de 1 GB só orquestra). Decisão de fornecedor em D-R1 (§10).

## 5. Modelo de dados (extensão do esquema existente)

```sql
-- Chunks: unidade de recuperação (derivada de pages, não substitui)
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    page_start INTEGER,          -- para citar "pág. 3–4"
    page_end INTEGER,
    text TEXT,                   -- 300–800 tokens, com overlap de ~15%
    embedding_model TEXT,        -- versão do modelo (permite migração gradual)
    embedded_at TEXT
);

-- Vetores (sqlite-vec)
CREATE VIRTUAL TABLE chunks_vec USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[1024]        -- dimensão conforme modelo escolhido (D-R1)
);

-- FTS sobre chunks (perna lexical da fusão, com a MESMA granularidade da vetorial)
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text, content='chunks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
```

### Estratégia de chunking (específica para manuais técnicos)
- **Respeitar fronteiras do documento**: nunca misturar documentos/subjects num chunk —
  o acervo já é naturalmente fragmentado em PDFs pequenos por subject (ex.:
  `SDS1651_75-30-00.PDF`), o que facilita muito.
- Alvo de 300–800 tokens por chunk com overlap de ~15%; documentos curtos (< 800 tokens)
  viram chunk único.
- **Prefixar cada chunk com seu contexto**: `"[AMM Parte I › Cap. 75 › SANGRIA DO
  COMPRESSOR] <texto>"` — melhora sensivelmente a recuperação em manuais, onde o texto
  da página sozinho ("remova os 4 parafusos") é ambíguo sem o título do subject.
- Tabelas de torque/limites: manter a linha inteira no mesmo chunk (não quebrar no meio).

## 6. Pipeline de embeddings

1. Job `embedder.py` (mesmo padrão do indexador): seleciona chunks sem embedding do
   modelo vigente → chama API de embeddings em lotes → grava em `chunks_vec`.
2. **Incremental por revisão**: quando um PDF muda (RN-09), seus chunks são recriados e
   re-embeddados; o resto do acervo não é tocado.
3. Executável como job noturno ou pós-reindexação; interrompível e retomável
   (estado = "chunk sem vetor").

### Ordem de grandeza de custo (estimativa a validar em D-R1)
- Corpus: ~500 mil páginas × ~200–400 tokens ≈ **100–200 M tokens**.
- Embedding via API (faixa típica de US$ 0,02–0,13 / M tokens): **~US$ 2–25, custo único**
  (re-embeddings posteriores são marginais — só o que mudou).
- Armazenamento: 1024 floats × ~700 mil chunks ≈ **~3 GB** no `catalog.db` →
  **exige upgrade do disco da VPS** (20 → 40 GB) — único impacto real de infra.

## 7. Busca híbrida (degrau 1)

- Duas buscas em paralelo: `chunks_fts` (BM25, top-50) e `chunks_vec` (kNN, top-50).
- **Fusão RRF** (Reciprocal Rank Fusion): `score = Σ 1/(60 + rank)` — simples, sem
  necessidade de normalizar scores heterogêneos, padrão da indústria.
- Resultado final mantém o formato do `/api/search` atual (compatibilidade com a UI),
  com um campo novo `match_type: "lexical" | "semantic" | "both"`.
- UI: toggle "busca inteligente" (padrão ligado; desligado = FTS puro, útil para
  part numbers e códigos exatos, onde lexical é imbatível).
- **Fallback estrutural**: se a API de embeddings estiver fora, a busca degrada para
  FTS puro automaticamente — o sistema nunca fica sem busca.

## 8. Perguntas em linguagem natural (degrau 2)

Fluxo do `/api/ask`:
1. Pergunta → embedding da pergunta → busca híbrida → top-K chunks (K≈8–12).
2. Reranking leve opcional (D-R2): reordenar os K por relevância antes de montar contexto.
3. Prompt: instruções R1–R4 (§2) + chunks com seus metadados + pergunta.
4. LLM via API (ex.: Claude — modelo pequeno/rápido resolve; a tarefa é extrativa).
5. Resposta estruturada: texto + lista de citações `{manual, capítulo, página, viewer_url}`.
6. UI de chat simples (uma pergunta → uma resposta com fontes; histórico é v2).

Custo operacional estimado: perguntas são eventos raros (equipe pequena) — dezenas de
US$/mês no pior caso; medir no piloto (D-R3).

## 9. Avaliação de qualidade (antes de liberar para a equipe)

- **Golden set**: 30–50 perguntas reais coletadas com mecânicos/pilotos, com a resposta
  correta anotada (manual + página). É o pré-requisito de entrada do degrau 2.
- Métricas: *recall@10* da recuperação (a página certa está entre os 10 chunks?) —
  meta ≥ 90%; para o degrau 2, taxa de resposta com citação correta — meta ≥ 95%,
  e **zero** respostas sem fonte.
- Rodar o golden set a cada mudança de modelo/chunking (script `eval_rag.py`), comparando
  antes/depois. Sem golden set não se mexe em produção.

## 10. Decisões em aberto (D-R)

| # | Decisão | Opções / critério |
|---|---|---|
| D-R1 | Fornecedor e modelo de embeddings | API multilíngue com bom desempenho PT/EN técnico (ex.: Voyage, OpenAI, Cohere; avaliar com o golden set); dimensão do vetor define o schema |
| D-R2 | Reranker no degrau 2 | Sem reranker (mais simples) vs. reranker via API (melhor precisão) — decidir pelo recall@10 medido |
| D-R3 | Orçamento mensal de API | Definir teto e alerta de consumo antes do piloto |
| D-R4 | Quem acessa o `/api/ask` | Todos vs. piloto restrito inicial (recomendado: piloto com 3–5 usuários e coleta de feedback) |
| D-R5 | Dados sensíveis | Confirmar se o teor dos manuais pode transitar por API externa; caso não, alternativa local exige VPS maior (≥ 8 GB) e modelo open-source — reavaliar custo/benefício |

## 11. Roadmap da Fase 3

| Etapa | Entrega | Esforço estimado | Gate de saída |
|---|---|---|---|
| R0 | Golden set + resolução de D-R1/D-R5 | 1 semana (maior parte é coleta com usuários) | 30+ perguntas anotadas |
| R1 | Chunking + `chunks`/`chunks_fts` | 3–5 dias | chunks íntegros amostrados manualmente |
| R2 | Embeddings + sqlite-vec + busca híbrida | 1 semana | recall@10 ≥ 90% no golden set |
| R3 | `/api/ask` + UI de pergunta (piloto restrito, D-R4) | 1–2 semanas | ≥ 95% de citações corretas; zero sem fonte |
| R4 | Abertura geral + monitoramento de custo (D-R3) | 2–3 dias | teto de custo configurado |

**Ordem importa**: R2 (busca híbrida) já entrega valor sozinha; R3 só começa com R2 validada.

## 12. O que NÃO fazer (anti-escopo)

- ❌ Rodar LLM ou modelo de embedding **na VPS de 1 GB** — matematicamente inviável.
- ❌ Trocar SQLite por banco vetorial dedicado (Qdrant, Pinecone...) — para < 1 M chunks,
  sqlite-vec resolve e mantém a operação em um único arquivo.
- ❌ Fine-tuning de modelos — RAG com bom chunking cobre o caso de uso; fine-tuning é
  custo alto e manutenção contínua sem ganho demonstrado aqui.
- ❌ Chat multi-turno com memória na primeira versão — complexidade de estado sem
  necessidade comprovada; o padrão de uso é pergunta pontual.
- ❌ Deixar o LLM responder sem recuperação ("modo assistente geral") — viola R1/R3.
