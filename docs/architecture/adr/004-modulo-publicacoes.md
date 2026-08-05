# ADR-004: Módulo `publicacoes` — Índice Separado, Indexação Offline, Extração Permissiva

**Data:** 2026-08-05
**Status:** Proposto
**Decisores:** Bruno Garcia

---

## Contexto

O SAA29 vai incorporar um sistema de consulta de manuais técnicos e publicações avulsas
(BO/BS/NPO/BT) como módulo interno (`app/modules/publicacoes/`), substituindo/absorvendo um
projeto externo autônomo já especificado em `docs/backlog/manuais/` (Projeto.MD, Especificacao.MD,
Runbook.MD, RAG.MD).

O parecer de viabilidade (`docs/backlog/modulo_publicacoes/opus_plano_de_incorporacao.md`, 5
revisões) analisou a incorporação sem acesso ao acervo real. Uma investigação de planejamento
subsequente (`docs/backlog/modulo_publicacoes/01_achados_do_acervo.md`) mediu o acervo diretamente
em `var/publicacoes/acervo/` (antes `var/Publicações/`) e encontrou:

- **1,0 GB / 5.724 PDFs / 34 manuais já presentes no disco**, não 3 GB/12.100 PDFs em DVD como o
  parecer assumia;
- **nenhum sidecar de metadados** (`.title`, XMLs) — mas cada manual traz um **índice Lucene
  legado** (`index_2.0/`) com título, revisão e capítulo para 5.719/5.724 documentos, sem número
  de página;
- o CI real (`.github/workflows/ci.yml`) roda um único job SQLite, sem matriz Postgres e sem
  mypy — diferente do que os documentos de planejamento anteriores citavam.

Este ADR registra as decisões de arquitetura que **sobrevivem** a essa correção de premissa —
eram a espinha dorsal do parecer desde a Revisão 1 e continuam sendo depois da Revisão 5 — mais
uma decisão nova, específica do formato de dados encontrado.

## Decisão

1. **O índice de busca full-text (`catalog.db`) vive em um arquivo SQLite dedicado**, gerado
   offline, fora do `DATABASE_URL` e fora do controle do Alembic. É aberto em runtime
   **exclusivamente com `sqlite3` da biblioteca padrão**, em modo somente-leitura
   (`?mode=ro&uri=true`), nunca com SQLAlchemy — porque `app/bootstrap/events.py:34-41` registra o
   listener de backup R2 na classe `Session` inteira, e uma engine SQLAlchemy sobre o `catalog.db`
   dispararia backups espúrios do banco principal a cada reindexação.

2. **A indexação (extração de texto por página) roda offline**, em `scripts/publicacoes/indexar.py`,
   nunca dentro do processo web nem no `lifespan`. O Gunicorn tem `timeout=30` fixo
   (`gunicorn_conf.py`) e o ambiente de produção-alvo tem CPU limitada — indexar in-process
   derrubaria o sistema para os usuários, não apenas degradaria.

3. **O acervo de PDFs vive fora do repositório e fora de `data/`** — em `var/publicacoes/acervo/`
   (path normalizado, sem acento/espaço; `data/` já é o ponto de montagem do banco principal via
   `docker-compose.yml`). Adicionado ao `.gitignore` no primeiro commit deste módulo.

4. **A extração de texto usa `pypdfium2` (Apache-2.0 / BSD-3-Clause), não PyMuPDF (AGPL-3.0).**
   A cláusula de rede da AGPL alcança software acessado por rede, e o SAA29 é um sistema web
   interno acessado por usuários da FAB — decisão consciente para não herdar exposição jurídica de
   uma escolha feita para outro projeto. O texto já extraído pelo índice Lucene legado (82,6 MB,
   UTF-8 válido em 100% dos documentos testados) serve como gabarito de qualidade para validar a
   extração do `pypdfium2`, sem depender de PyMuPDF em nenhum ponto do pipeline.

## Alternativas Consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| FTS5 dentro do banco principal (`saa29_local.db`) | Uma única fonte de dados, sem camada extra | Quebra portabilidade Postgres declarada (`docs/methodology/NEXT.md`); infla o ciclo de backup R2 com um índice potencialmente de dezenas de MB |
| Indexação disparada no boot ou via `POST /admin/reindex` | Espelha o desenho do projeto externo, "publicar = copiar pasta" | Mata o worker no `timeout=30`; em CPU limitada, para o sistema inteiro durante a indexação, não apenas degrada |
| Acervo dentro de `docs/fim/` ou outro diretório versionado do repositório | Zero infraestrutura nova | 1 GB no histórico do git é permanente mesmo que os arquivos sejam depois removidos; infla toda clonagem futura |
| PyMuPDF para extração | Melhor qualidade e desempenho documentados na literatura | Licença AGPL-3.0 com cláusula de rede aplicável a sistema web; exposição jurídica desnecessária quando há alternativa permissiva equivalente para o caso de uso |

## Consequências

**Positivas:**
- O módulo pode evoluir a camada de busca (trocar FTS5 por outro motor, ou até por
  `tsvector`/`pg_trgm` do Postgres) sem tocar em router, service ou UI — a fronteira é
  `search.py`.
- Nenhuma dependência AGPL entra no projeto.
- A indexação pode rodar em qualquer máquina com o acervo montado (não precisa ser o servidor de
  produção) — inclusive antes de qualquer decisão de hospedagem estar tomada.
- O acervo de 1 GB nunca precisa ser clonado por quem só quer trabalhar no código do módulo.

**Negativas / Trade-offs:**
- Dois "bancos" (principal + `catalog.db`) para manter mentalmente coerentes via `document_id`
  determinístico (`03_especificacao_tecnica.md` §2.2) — mais disciplina de código do que um único
  banco relacional resolveria de graça.
- A indexação offline exige um passo manual (ou script agendado) para publicar atualizações —
  não há "salvar e já aparece", como haveria com indexação em request.
- `pypdfium2` é menos testado em produção que PyMuPDF para extração de texto — mitigado pelo
  gabarito de qualidade do texto Lucene já existente e por benchmark real sobre os PDFs do piloto
  antes de comprometer o acervo inteiro (`04_plano_de_execucao.md`, M0).

## Referências

- [`docs/backlog/modulo_publicacoes/01_achados_do_acervo.md`](../../backlog/modulo_publicacoes/01_achados_do_acervo.md)
- [`docs/backlog/modulo_publicacoes/02_formato_indice_lucene.md`](../../backlog/modulo_publicacoes/02_formato_indice_lucene.md)
- [`docs/backlog/modulo_publicacoes/03_especificacao_tecnica.md`](../../backlog/modulo_publicacoes/03_especificacao_tecnica.md)
- [`docs/backlog/modulo_publicacoes/opus_plano_de_incorporacao.md`](../../backlog/modulo_publicacoes/opus_plano_de_incorporacao.md)
- [`app/bootstrap/events.py`](../../../app/bootstrap/events.py)
- [`gunicorn_conf.py`](../../../gunicorn_conf.py)
