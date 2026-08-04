# Sistema de Consulta de Manuais Técnicos — EMB-314 Super Tucano

Sistema web leve para consulta dos manuais técnicos da aeronave EMB-314 Super Tucano,
substituindo a solução legada em Java/Lucene (`Program` e `Program_Operational`) por uma
aplicação única, moderna e otimizada para VPS de baixo custo.

**Status:** 📋 Planejamento concluído — pronto para iniciar a Fase 0 (merge do acervo).

## A ideia em três linhas

- Todos os manuais vivem em uma única pasta **`data/`** — publicar um manual = copiar a pasta, zero código.
- Busca full-text por palavra-chave que abre o PDF **na página exata** do resultado, em desktop e mobile.
- Um processo Python + SQLite: roda em VPS de 1 GB de RAM, sem Java, sem serviços externos.

## Stack (resumo)

FastAPI + Uvicorn · SQLite FTS5 · PyMuPDF · Jinja2 + htmx · PDF.js · Caddy · Docker Compose
— justificativas completas em [Projeto.MD](Projeto.MD) §3.

## Documentação — ordem de leitura

| # | Documento | O que responde | Leia se você é... |
|---|---|---|---|
| 1 | [Projeto.MD](Projeto.MD) | **O quê e por quê** — visão, arquitetura, stack, modelo de dados, roadmap em fases | todos (começar aqui) |
| 2 | [Especificacao.MD](Especificacao.MD) | **Como se comporta** — telas, rotas, contrato de API, regras de negócio (RN), casos de borda (E), critérios de aceite (CA) | dev implementando |
| 3 | [Runbook.MD](Runbook.MD) | **Como operar** — provisionamento da VPS, deploy, publicação de manuais, backup, triagem de problemas | quem faz deploy/operação |
| 4 | [RAG.MD](RAG.MD) | **Evolução futura com IA** — busca semântica e perguntas em linguagem natural (Fase 3) | arquitetura/planejamento |

## Acervo (diagnóstico de 03/08/2026)

- ~12.100 PDFs, ~3 GB, 53 manuais (AMM, AIPC, FIM, CMM, boletins...)
- Metadados já fornecidos pela Embraer TechPubs e aproveitados pelo sistema:
  arquivos `.title` (títulos + status de revisão), `manual_details.xml`,
  `manual_type.xml`, `collections.ini`, `version/*.txt`

## Roadmap (resumo — detalhes em Projeto.MD §11)

- **Fase 0** (1–2 dias): merge dos dois `Data/` legados em `data/`, com deduplicação e relatório.
- **Fase 1 — MVP** (1–2 semanas): indexação, navegação, busca com página exata, viewer, deploy.
- **Fase 2 — v1.0** (2–3 semanas): filtros, favoritos, reindexação automática, autenticação.
- **Fase 3 — futuro**: OCR, busca semântica e perguntas em linguagem natural ([RAG.MD](RAG.MD)).

## Pendências de decisão (bloqueiam partes da Fase 1)

Ver Especificacao.MD §10 — em especial **D-01** (rótulos das categorias) e
**D-05** (manuais exclusivos de um dos sistemas legados).

## Convenções do repositório

- Documentação de planejamento na raiz (estes `.MD`); código em `app/`; scripts utilitários em `scripts/`.
- `index/catalog.db` e `data/` **não são versionados** no git (gerado e acervo, respectivamente).
- Toda mudança de procedimento operacional atualiza o Runbook **na mesma PR**.
