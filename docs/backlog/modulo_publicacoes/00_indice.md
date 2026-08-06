# Índice — Documentação de Apoio do Módulo `publicacoes`

> Mapa de leitura desta pasta. `docs/backlog/manuais/` permanece **apenas como referência** do
> projeto externo que originou a ideia — não editar aquela pasta; toda decisão vigente mora aqui.

## Chegou agora? Três documentos bastam

1. **[`08_status_de_implementacao.md`](08_status_de_implementacao.md)** — o que já existe, tarefa a
   tarefa, com evidência verificável, e as dívidas conhecidas.
2. **[`03_especificacao_tecnica.md`](03_especificacao_tecnica.md)** — o contrato: modelo de dados,
   rotas, RBAC. Comece pela **§0.1**, que lista o que mudou desde o planejamento original.
3. **[`09_plano_configuracoes.md`](09_plano_configuracoes.md)** — o plano de trabalho da gerência de
   edições e da navegação do acervo, com as duas etapas concluídas. Fica como referência de contrato
   e de "o que a execução mudou em relação ao planejado"; o que resta no módulo (RSS/disco da VPS,
   verificação visual) não é mais trabalho de código descrito aqui — ver o `08`.

Os demais documentos da pasta são registro datado (medições, pareceres, revisões) — úteis para
entender *por que* algo é como é, desnecessários para trabalhar.

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
| 7 | [`07_revisao_pre_implementacao.md`](07_revisao_pre_implementacao.md) | **8 bugs antecipados + 2 simplificações + 5 lacunas de convenção**, cada um medido por execução real | Vai implementar — é o documento que evita perder um dia depurando no lugar errado |
| 8 | [`08_status_de_implementacao.md`](08_status_de_implementacao.md) | **Painel de progresso.** Tarefa a tarefa, com evidência verificável, gates medidos e a próxima tarefa | Quer saber **em que ponto a implementação está** — é o único documento desta pasta que muda com o código |
| 9 | [`09_plano_configuracoes.md`](09_plano_configuracoes.md) | Plano de trabalho da gerência de edições e da navegação do acervo — Etapa 1 (gerência em `/configuracoes`) ✅ e Etapa 2 (navegação do acervo) ✅, ambas concluídas | Quer o contrato de cada endpoint/página e o registro de "o que a execução mudou em relação ao planejado" |
| — | [`../../architecture/adr/004-modulo-publicacoes.md`](../../architecture/adr/004-modulo-publicacoes.md) | ADR formal das 4 decisões de arquitetura que sobrevivem a todas as revisões | Quer a decisão registrada no lugar canônico do projeto |

## Status de cada documento

| Documento | Status | Decisão ou referência? |
|---|---|---|
| `opus_plano_de_incorporacao.md` | Histórico — corpo não reescrito; nota de vigência no topo | Referência (o addendum e o `08` carregam o que vale hoje) |
| `01_achados_do_acervo.md` | **Datado** — registro de medição de 04–05/08, com nota de vigência no topo | Referência factual (não reescrito quando a realidade muda) |
| `02_formato_indice_lucene.md` | Fechado, parser verificado por execução | Referência técnica |
| `03_especificacao_tecnica.md` | **Vivo** — §0.1 lista o que mudou desde o planejamento | **Decisão** — é o contrato de execução |
| `04_plano_de_execucao.md` | Histórico — plano como escrito antes da execução; o `08` é a fonte da verdade | **Decisão** original de ordem e escopo de marcos |
| `05_rastreabilidade_externa.md` | Fechado | Referência de rastreabilidade |
| `06_addendum_revisao_5.md` | Fechado | **Decisão** — o que mudou na Revisão 5 |
| `07_revisao_pre_implementacao.md` | Datado — os 8 bugs antecipados foram confirmados e tratados | **Decisão** — rastreio de cada um no `08` |
| `08_status_de_implementacao.md` | **Vivo** — atualizado a cada tarefa concluída | Rastreamento de progresso |
| `09_plano_configuracoes.md` | **Vivo, mas sem trabalho de código pendente** — Etapas 1 e 2 concluídas | **Decisão** — reverte o `os.replace()` previsto em `search.py` por resolução do índice pelo banco (adendo no ADR-004); registra as 3 rotas de navegação que a §3 do contrato especificava e nunca tinham virado tarefa |
| `004-modulo-publicacoes.md` (ADR) | Aceito, com adendo de 06/08 sobre o índice por edição | **Decisão formal** |

> Atenção à assimetria: a tabela acima é o status **dos documentos**, não o da implementação. Quem
> quer saber o que já foi codificado abre o `08`.

**Três documentos mudam; o resto é registro.** `08` (progresso), `09` (o que falta do M4) e `03`
(contrato) são atualizados conforme o código anda. Os demais são datados: quando uma premissa deles
cai, a correção entra como nota de vigência no topo — o corpo não é reescrito, para que o histórico
do raciocínio continue legível.

## O que ainda está em aberto (não travado nesta etapa)

Ver `05_rastreabilidade_externa.md` (seção Decisões em Aberto) para a lista completa com status
individual. As que não bloqueiam nenhum marco até o M4: D-01 (rótulos de categoria), D-03
(migrar `Comments/` do legado — provavelmente não se aplica), D-04 (provedor de VPS), D-05
(manuais exclusivos de um sistema legado), D-S3 (autorização RAG), D-S4 (escopo final do acervo,
parcialmente respondida), D-S7 (backup testado).

## Resumo de uma frase por decisão travada

- **Piloto FIM primeiro** (411 PDFs do `FIM_1741`), não o acervo completo, no M1.
- **`pypdfium2`** para extração por página — resolve D-S2, encerra a questão AGPL.
- **Publicações avulsas (M2) antes da integração com panes/inspeções (M3)**.
- **Acervo normalizado** para `var/publicacoes/acervo/` — sem acento, sem espaço.
- **`catalog.db` só com `sqlite3` puro**, nunca SQLAlchemy.
- **Um índice por edição** (`catalog.<rotulo>.db`); a edição `VIGENTE` no banco decide qual a busca
  abre. Revisa o `os.replace()` previsto originalmente — adendo do ADR-004.
- **O acervo não é versionado.** Nem `docs/fim/` (removido) nem `var/publicacoes/acervo/`. O
  repositório guarda só `tests/fixtures/fim/` (4 PDFs, 172 KB, para o CI) e `docs/fim.json`.
- **`API_PREFIXES` recebe `/publicacoes/api/`**, nunca `/publicacoes/`.
- **`rebuild` obrigatório no FTS5** após a carga — contagem não prova que a busca funciona.
- **`snippet` com sentinela `\x02`/`\x03`**, escapado no cliente — nunca `<mark>` cru do SQLite.
- **`document_id` inclui a edição** e trafega entre bancos sempre via `uuid.UUID()`.
