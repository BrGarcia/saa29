# Índice — Documentação de Apoio do Módulo `publicacoes`

> Mapa de leitura desta pasta. `docs/backlog/manuais/` permanece **apenas como referência** do
> projeto externo que originou a ideia — não editar aquela pasta; toda decisão vigente mora aqui.

## Ordem de leitura recomendada

| # | Documento | O que é | Leia se... |
|---|---|---|---|
| — | [`opus_plano_de_incorporacao.md`](opus_plano_de_incorporacao.md) | O parecer original (Revisões 1–5), veredito e análise de fricção completa | Quer o histórico do raciocínio e o "porquê" por trás de cada decisão |
| 1 | [`01_achados_do_acervo.md`](01_achados_do_acervo.md) | **Base factual.** Tudo que foi medido no acervo real: censo, cobertura, achados operacionais | Quer saber o que existe de fato no disco, com evidência |
| 2 | [`02_formato_indice_lucene.md`](02_formato_indice_lucene.md) | Engenharia reversa do índice legado `index_2.0/`: formato binário, parser de referência, armadilhas | Vai escrever `catalog.py` ou precisa entender de onde vêm título/revisão/capítulo |
| 3 | [`03_especificacao_tecnica.md`](03_especificacao_tecnica.md) | **Especificação executável.** Modelo de dados, rotas, schemas, RBAC, env vars, layout de arquivos | Vai implementar qualquer parte do módulo |
| 4 | [`04_plano_de_execucao.md`](04_plano_de_execucao.md) | Marcos M0–M5 quebrados em tarefas, com gates verificáveis | Quer saber a ordem e o que fazer em cada marco |
| 5 | [`05_rastreabilidade_externa.md`](05_rastreabilidade_externa.md) | Destino de cada RN/E/CA/D da `Especificacao.MD` externa, à luz dos achados | Quer conferir que nenhuma regra do projeto externo foi perdida |
| 6 | [`06_addendum_revisao_5.md`](06_addendum_revisao_5.md) | O que a Revisão 5 muda no parecer, seção por seção | Já leu o parecer e quer só o diff |
| — | [`../../architecture/adr/004-modulo-publicacoes.md`](../../architecture/adr/004-modulo-publicacoes.md) | ADR formal das 4 decisões de arquitetura que sobrevivem a todas as revisões | Quer a decisão registrada no lugar canônico do projeto |

## Status de cada documento

| Documento | Status | Decisão ou referência? |
|---|---|---|
| `opus_plano_de_incorporacao.md` | Histórico — Revisão 5 registrada só como bloco de cabeçalho, corpo não reescrito | Referência (o addendum é que carrega a decisão vigente) |
| `01_achados_do_acervo.md` | Fechado nesta etapa | Referência factual |
| `02_formato_indice_lucene.md` | Fechado nesta etapa, parser verificado por execução | Referência técnica |
| `03_especificacao_tecnica.md` | Fechado nesta etapa | **Decisão** — é o contrato de execução |
| `04_plano_de_execucao.md` | Fechado nesta etapa | **Decisão** — ordem e escopo de marcos |
| `05_rastreabilidade_externa.md` | Fechado nesta etapa | Referência de rastreabilidade |
| `06_addendum_revisao_5.md` | Fechado nesta etapa | **Decisão** — o que muda a partir de agora |
| `004-modulo-publicacoes.md` (ADR) | Proposto | **Decisão formal** |

## O que ainda está em aberto (não travado nesta etapa)

Ver `05_rastreabilidade_externa.md` (seção Decisões em Aberto) para a lista completa com status
individual. As que não bloqueiam nenhum marco até o M4: D-01 (rótulos de categoria), D-03
(migrar `Comments/` do legado — provavelmente não se aplica), D-04 (provedor de VPS), D-05
(manuais exclusivos de um sistema legado), D-S3 (autorização RAG), D-S4 (escopo final do acervo,
parcialmente respondida), D-S7 (backup testado).

## Resumo de uma frase por decisão travada

- **Piloto FIM primeiro** (`docs/fim/`, 411 PDFs), não o acervo completo, no M1.
- **`pypdfium2`** para extração por página — resolve D-S2, encerra a questão AGPL.
- **Publicações avulsas (M2) antes da integração com panes/inspeções (M3)**.
- **Acervo normalizado** para `var/publicacoes/acervo/` — sem acento, sem espaço.
- **`catalog.db` só com `sqlite3` puro**, nunca SQLAlchemy.
- **`API_PREFIXES` recebe `/publicacoes/api/`**, nunca `/publicacoes/`.
