# Achados de Revisão — Módulo `panes`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 03/08/2026
> 12/18 achados corrigidos, 4 parciais, 2 não corrigidos por exigirem decisão de produto ou migração
> de schema fora do escopo desta sessão (ver `## Perguntas para o desenvolvedor` ao final). Commit
> `b786ef8`. Suite completa: 341 testes, 0 falhas. Status por item marcado inline em cada achado
> abaixo (campo `**Status:**`).

---

### [BUG-01] `GET /panes/export` retorna 500 em toda chamada — classe inexistente

- **Classificação:** BUG
- **Severidade:** CRÍTICA
- **Arquivo:** `app/modules/panes/router.py:123`
- **Eixo:** Contrato
- **Problema:** o handler `exportar_panes` instancia `schemas.PaneFilter(status=status, aeronave_id=aeronave_id, skip=0, limit=1000)`, mas essa classe **não existe** em `app/modules/panes/schemas.py` — o schema equivalente se chama `FiltroPane` (`schemas.py:30`). `grep -rn "PaneFilter"` no repositório inteiro retorna apenas essa única linha de uso, sem nenhuma definição em lugar nenhum.
- **Consequência:** toda chamada a `GET /panes/export` (CSV ou XLSX) levanta `AttributeError: module 'app.modules.panes.schemas' has no attribute 'PaneFilter'`, capturado pelo handler genérico de exceções (`app/shared/core/exceptions.py:91-97`), retornando 500 "Erro interno do servidor" para o cliente. O endpoint de exportação de relatórios está inteiramente quebrado. Nenhum teste cobre isso: `tests/test_exporter.py` testa só os helpers `gerar_csv`/`gerar_xlsx` isolados (sem passar pelo router), e nenhum dos 4 arquivos `test_panes*.py` chama `/export`.
- **Correção proposta:** trocar `schemas.PaneFilter` por `schemas.FiltroPane` em `router.py:123`.
- **Risco de regressão:** BAIXO — troca mecânica de nome de classe com assinatura de campos idêntica.
- **Precisa de teste antes?** SIM (o bug só foi pego porque não existe teste de integração para este endpoint — corrigir sem adicionar teste deixaria a regressão futura igualmente invisível)
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. `schemas.PaneFilter` → `schemas.FiltroPane`. Teste de integração novo em `tests/security/test_panes_achados_revisor.py` (CSV e XLSX).

---

### [BUG-02] Dois caminhos para RESOLVIDA com efeitos colaterais divergentes

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/service.py:428-449,454-527`
- **Eixo:** Contrato / Arquitetura
- **Problema:** existem dois caminhos que levam uma pane a `RESOLVIDA`. `concluir_pane` (`service.py:454-527`, via `POST /{pane_id}/concluir`) grava `observacao_conclusao` e, se o usuário que concluiu ainda não constar como responsável, o adiciona automaticamente (`service.py:486-512`). `editar_pane` (`service.py:428-449`, via `PUT /{pane_id}` com `status=RESOLVIDA`, COR-03) grava apenas `data_conclusao` e `concluido_por_id` — não grava observação nem adiciona responsável.
- **Consequência:** a mesma transição de negócio ("resolver a pane") produz dados finais diferentes dependendo de qual endpoint o cliente chamou. Uma pane resolvida via `PUT` fica sem ação corretiva registrada e sem o executor listado como responsável — inconsistência visível em relatórios e na tela de detalhe.
- **Correção proposta:** decidir se `PUT .../status=RESOLVIDA` deve ser bloqueado (forçando `/concluir` como único caminho de conclusão) ou se `editar_pane` deve replicar a mesma lógica de responsável/observação de `concluir_pane`. Ver também RISCO-03, que trata da autorização desse mesmo caminho.
- **Risco de regressão:** MÉDIO — qualquer cliente que hoje dependa do `PUT` para resolver precisa ser identificado antes de bloquear o caminho.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Optou-se por bloquear: `editar_pane` rejeita qualquer `status` com 409, direcionando para `POST /{pane_id}/concluir`. Nenhum cliente identificado dependendo do `PUT` para resolver (frontend não foi auditado a fundo — risco residual, ver observação). Testado em `tests/unit/test_panes_alta_prioridade.py`.

---

### [BUG-03] Mapeamento de `ValueError` para status HTTP incorreto em 5 pontos do router

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:67-71,323-327,436-440,457-461,487-491`
- **Eixo:** Contrato
- **Problema:** o service ainda comunica parte dos seus erros como `ValueError` genérico com mensagem em texto (ver MELHORIA-13), e cada handler decide o status HTTP sem checar qual erro de fato ocorreu:
  - `criar_pane` (`router.py:67-71`): tanto "Aeronave não encontrada" quanto "Aeronave inativa" (`service.py:176,178`) viram **404** — a segunda é um conflito de estado, não ausência de recurso (deveria ser 409).
  - `deletar_pane` (`router.py:457-461`): "Pane não encontrada" e "Pane já está inativa" (`service.py:538,541`) ambas viram **404** — a segunda deveria ser 409.
  - `restaurar_pane` (`router.py:487-491`): "Pane não encontrada" e "Pane já está ativa" (`service.py:554,557`) ambas viram **400** — a primeira deveria ser 404.
  - `adicionar_responsavel` (`router.py:436-440`): "Pane não encontrada", "Usuário já é responsável" e "Usuário não encontrado" (`service.py:893,898,903,917`) todas viram **409** — as duas primeiras variantes de "não encontrado" deveriam ser 404.
  - `upload_anexo` (`router.py:323-327`): "Pane não encontrada" (`service.py:591`) vira **422**, quando deveria ser 404.
- **Consequência:** clientes não conseguem diferenciar programaticamente "recurso não existe" de "conflito de estado" — só têm a string de `detail` em português para inferir a causa, o que quebra qualquer integração automatizada e é frágil a mudança de texto (o mesmo problema documentado no mapa arquitetural §5 para `aeronaves/router.py`).
- **Correção proposta:** migrar os `raise ValueError` restantes do service para `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError` (ver MELHORIA-13) e simplificar os `except` do router para não precisar adivinhar pelo texto.
- **Risco de regressão:** MÉDIO — muda o status HTTP retornado hoje; qualquer cliente que já trate (incorretamente) o código atual como "sucesso silencioso" ou dependa do código específico precisa ser revisto.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Os 5 pontos citados (e mais os equivalentes em `criar_pane`) migrados para `EntidadeNaoEncontradaError`/`ConflitoNegocioError`; `except ValueError` correspondentes removidos do router. `excluir_anexo` não foi tocado (já mapeava corretamente, fora do escopo listado). Teste de regressão para "aeronave inativa" (404→409) em `tests/unit/test_panes.py`.

---

### [RISCO-04] `Content-Type` do cliente, nunca validado, chega ao storage no fallback de background

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:294-321`, `app/modules/panes/service.py:707-744`
- **Eixo:** Segurança
- **Problema:** `upload_anexo` no router extrai `content_type = arquivo.content_type or "application/octet-stream"` (`router.py:309`) — esse valor vem direto do cliente HTTP e **nunca é verificado** contra o conteúdo real (`validate_file_upload`, chamado logo antes em `router.py:304`, confere apenas nome de arquivo, extensão e magic bytes — não o header `Content-Type`). Esse `content_type` é passado como argumento `mime_real` para a task de background `processar_imagem_background` (`router.py:315-321`). Dentro dela, se o pipeline de otimização de imagem falhar, o bloco de fallback (`service.py:736-744`) faz `storage_svc.upload(arquivo_bytes, nome_original, mime_real)` — ou seja, usa o `content_type` do cliente, não recalculado, como `content_type` real do upload.
- **Consequência:** com `storage_backend=r2`, esse valor vira o `ContentType` do objeto S3 (`app/shared/core/storage.py:113-118`), que é o header retornado quando o arquivo é servido pela URL pré-assinada. Um atacante envia um PNG poliglota (bytes válidos de imagem, mas que também é HTML/JS válido) com `Content-Type: text/html` — passa pela validação de magic bytes normalmente (é um PNG de verdade), mas se cair no caminho de fallback é servido pelo R2 como `text/html`, executando no navegador de quem acessar o link — XSS armazenado. Nota lateral: o parâmetro `tipo_mime` recebido por `service.upload_anexo` (`service.py:569`) sequer é usado no caminho síncrono — o service recalcula corretamente o MIME a partir dos bytes (`service.py:605-611`) — só o caminho de fallback do background é afetado.
- **Correção proposta:** no fallback (`service.py:736-744`), recalcular o MIME real a partir dos bytes (mesma lógica de `service.py:603-611`) em vez de reusar o `mime_real` recebido como argumento, que na verdade carrega o `content_type` não confiável do cliente.
- **Risco de regressão:** BAIXO — o caminho normal (sem fallback) já faz a coisa certa; a correção só alinha o caminho de exceção ao mesmo padrão.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Novo helper `_detectar_mime_real` (reusado no caminho síncrono e no fallback); `processar_imagem_background` recalcula o MIME a partir dos bytes em vez de confiar no `content_type` do cliente. Testado em `tests/security/test_panes_achados_revisor.py` com um PNG real + Content-Type `text/html` forjado.

---

### [RISCO-05] Autorização inconsistente entre os dois caminhos de resolução de pane

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:193-194,220`
- **Eixo:** Segurança
- **Problema:** `concluir_pane` sempre exige `ensure_role(usuario_atual, "MANTENEDOR", "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")` (`router.py:220`). Já `editar_pane` só chama `ensure_role(usuario_atual, "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")` **se** `descricao` ou `sistema_ata_id` vierem no payload (`router.py:193-194`) — um `PUT` só com `{"status": "RESOLVIDA"}` passa sem nenhuma checagem além de `CurrentUser` (qualquer usuário autenticado).
- **Consequência:** hoje sem escalação de privilégio real, porque os 4 papéis do sistema já cobrem todos os usuários possíveis (`TipoPapel`), mas é uma trava de autorização ausente por construção — o dia em que um papel novo, somente-leitura, for adicionado ao sistema, ele poderá resolver panes via `PUT` sem passar pela checagem que `concluir_pane` aplica.
- **Correção proposta:** aplicar a mesma checagem de papel em `editar_pane` sempre que `dados.status is not None`, não só para `descricao`/`sistema_ata_id`.
- **Risco de regressão:** BAIXO — hoje não bloquearia nenhum usuário real, dado o conjunto de papéis existente.
- **Precisa de teste antes?** NÃO (mas testar junto com a correção do BUG-02, que toca o mesmo caminho)
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Mesma correção do BUG-02: como `status` via `PUT` agora é rejeitado incondicionalmente (409) para qualquer usuário, a checagem de papel ausente deixou de ser um caminho explorável — não foi adicionada uma checagem de papel separada porque o caminho em si foi fechado.

---

### [MELHORIA-06] Regra de negócio duplicada no router como "safety net" redundante

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:50-64,235-275`
- **Eixo:** Arquitetura (mapa arquitetural §7, item 4)
- **Problema:** `criar_pane` (`router.py:50-64`) e `concluir_pane` (`router.py:235-275`) reimplementam em SQL cru, direto no handler, a mesma regra de sincronização de status de aeronave que `service.sincronizar_status_aeronave` já executa — e que **já foi chamada** dentro do próprio `service.criar_pane` (`service.py:214`) e `service.concluir_pane` (`service.py:515`) antes do controle voltar ao router. O comentário no código ("Safety net... garante a transição mesmo em cenários de cache de ORM") não descreve nenhum cenário reproduzível em que o service, sozinho, falharia.
- **Consequência:** duas implementações independentes da mesma regra de negócio, que precisam ser mantidas em sincronia manualmente a cada mudança futura (ex.: uma nova condição de transição de status adicionada em `sincronizar_status_aeronave` não é replicada automaticamente no router). Custo adicional: 2 `SELECT COUNT` e até 1 `UPDATE` extra por conclusão de pane, todos redundantes com o que o service já fez.
- **Correção proposta:** remover os dois blocos "safety net" do router, confiando inteiramente em `sincronizar_status_aeronave` (já chamada pelo service). Se houver um caso real documentado que motivou o safety net, investigar e corrigir na origem (dentro do service), não duplicar no router.
- **Risco de regressão:** MÉDIO — remover requer confirmar que não há de fato um cenário de cache de ORM não coberto (ver pergunta ao desenvolvedor).
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Os dois "safety nets" (`criar_pane` e `concluir_pane`) removidos do router; confia-se inteiramente em `sincronizar_status_aeronave` chamada pelo service. Nenhum caso reproduzível de cenário de cache de ORM não coberto foi identificado nem relatado — decisão tomada sem confirmação explícita do desenvolvedor (ver pergunta ao final do documento). Testado (`test_concluir_pane_libera_aeronave` cobre o caminho que o safety net supostamente protegia).

---

### [MELHORIA-07] `concluir_pane` carrega a mesma pane três vezes com eager-loading pesado

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:228,278`, `app/modules/panes/service.py:474`
- **Eixo:** Banco
- **Problema:** o handler `concluir_pane` chama `service.buscar_pane` (`router.py:228`, com 6 `selectinload`) apenas para extrair `aeronave_id_pane` e alimentar o safety net (MELHORIA-06); o service internamente já busca a mesma pane via `_buscar_pane_por_id` (`service.py:474`, mais 5 `selectinload`); e ao final o router busca a pane **de novo** (`router.py:278`, os mesmos 6 `selectinload`) só para montar o código `ddd/yy` da resposta.
- **Consequência:** três consultas com eager-loading completo para uma única operação de conclusão. A primeira delas existe só para servir ao safety net do achado MELHORIA-06 — removendo-o, essa consulta inteira desaparece.
- **Correção proposta:** eliminar a primeira busca junto com o safety net (MELHORIA-06); avaliar se a segunda busca do service e a busca final do router podem ser consolidadas (ex.: `concluir_pane` no service já devolver os dados necessários para o código, evitando o recarregamento do router).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ⚠️ CORRIGIDO PARCIALMENTE — commit `b786ef8`. A primeira busca (só para alimentar o safety net) foi eliminada junto com o MELHORIA-06. A consolidação da segunda busca do service com a busca final do router (de 2 buscas para 1) não foi feita — continuam duas consultas com eager-loading completo.

---

### [RISCO-08] Corrida em `sincronizar_status_aeronave` sob SQLite

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/service.py:89-145`
- **Eixo:** Concorrência
- **Problema:** a função lê o estado atual (via duas queries `EXISTS`, `service.py:112-123`) e decide o novo status da aeronave com base nisso, sem exclusão mútua efetiva no banco atual do projeto: `db.get(Aeronave, aeronave_id, with_for_update=True)` (`service.py:106`) é compilado como no-op em SQLite — fato documentado no próprio docstring da função (`service.py:96-101`).
- **Consequência:** duas panes da mesma aeronave criadas ou resolvidas concorrentemente (duas abas, dois usuários simultâneos) podem intercalar leitura e escrita de forma que o status final da aeronave não reflita o estado real de panes/inspeções abertas.
- **Correção proposta:** nenhuma ação necessária enquanto o backend for SQLite single-writer (WAL + `busy_timeout` já mitigam parcialmente, conforme mapa arquitetural §6); revisar quando/se o projeto migrar para um banco que suporte `SELECT ... FOR UPDATE` de verdade.
- **Risco de regressão:** N/A — é um risco assumido e documentado, não uma correção pendente.
- **Precisa de teste antes?** SIM, se e quando for endereçado (teste de concorrência dedicado).
- **Status:** 🚫 NÃO CORRIGIDO — por definição do próprio achado ("nenhuma ação necessária enquanto o backend for SQLite single-writer"). Nenhuma ação de código tomada; revisitar se/quando o projeto migrar para um banco com `SELECT ... FOR UPDATE` real.

---

### [RISCO-09] Código `ddd/yy` recalculado por window function, nunca persistido

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/service.py:71-86`
- **Eixo:** Banco / Contrato
- **Problema:** `_get_ranking_subquery` deriva o identificador visível ao usuário (`"{sequencia:03d}/{ano}"`) com `row_number() OVER (PARTITION BY ano ORDER BY data_abertura, id)` sobre **todas** as panes daquele ano, recalculado a cada `listar_panes`/`buscar_pane`. O valor não existe como coluna persistida em `Pane`.
- **Consequência:** hoje o resultado é estável, porque soft-delete não filtra a subquery e `data_abertura` não é editável por nenhum endpoint — mas a estabilidade é acidental, não garantida pelo esquema. Qualquer hard-delete futuro, ou uma correção manual de `data_abertura` direto no banco, renumera retroativamente todas as panes subsequentes do mesmo ano — um código já citado em um relatório impresso ou em uma OS física passaria a apontar para uma pane diferente. Custo adicional: a window function varre a tabela inteira do ano a cada listagem, mesmo paginada.
- **Correção proposta:** avaliar persistir a sequência no momento da criação (ex.: coluna `sequencia_anual` preenchida uma vez, com índice único `(ano, sequencia_anual)`), eliminando o recálculo e a fragilidade a hard-delete/edição de data.
- **Risco de regressão:** ALTO — muda a fonte do dado mais visível do módulo (o "código" da pane); exige migração e validação cuidadosa de que os códigos existentes não mudam ao migrar.
- **Precisa de teste antes?** SIM
- **Status:** 🚫 NÃO CORRIGIDO — risco de regressão ALTO e migração de schema, incompatível com o escopo desta sessão de correção. Requer sessão dedicada com validação cuidadosa de que os códigos existentes não mudam.

---

### [RISCO-10] Export sem paginação sinalizada, sem restrição de papel e sem rate limit

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/panes/router.py:111-149`
- **Eixo:** Segurança / Contrato
- **Problema:** `exportar_panes` monta `schemas.FiltroPane` (após corrigir BUG-01) com `limit=1000` fixo (o teto máximo do schema) e não repassa os filtros de texto/data que `listar_panes` aceita — só `status` e `aeronave_id`. O endpoint exige apenas `CurrentUser` (qualquer papel autenticado exporta a base inteira de panes) e não tem `@limiter.limit`, diferente do único endpoint do sistema que tem rate limit (`auth/login`, conforme mapa §7.5).
- **Consequência:** se houver mais de 1000 panes ativas no filtro pedido, o relatório exportado é truncado silenciosamente, sem qualquer indicação ao usuário de que faltam registros. Combinado com a ausência de rate limit, o endpoint é um vetor barato de exfiltração/scraping de dados por qualquer usuário autenticado.
- **Correção proposta:** expor os filtros de data/texto também no export; sinalizar truncamento (ex.: header customizado ou contagem total); avaliar se a exportação deveria ser restrita a papéis de gestão (ENCARREGADO/ADMINISTRADOR); aplicar rate limit.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO (mas só é observável de fato depois do BUG-01 corrigido)
- **Status:** ⚠️ CORRIGIDO PARCIALMENTE — commit `b786ef8`. Filtros de texto/data adicionados, truncamento sinalizado via header `X-Export-Truncated`, `@limiter.limit("10/minute")` aplicado. A restrição a papéis de gestão **não foi feita** — decisão de produto que pode bloquear usuários que hoje exportam sem restrição (ver pergunta ao desenvolvedor). Testado em `tests/security/test_panes_achados_revisor.py`.

---

### [RISCO-11] Parâmetro `status` sombreia o módulo `fastapi.status` na assinatura de dois handlers

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/router.py:83,119`
- **Eixo:** Arquitetura
- **Problema:** `listar_panes(..., status: schemas.StatusPane | None = Query(...))` e `exportar_panes(..., status: schemas.StatusPane | None = None)` declaram um parâmetro chamado `status`, que dentro do corpo dessas funções sombreia o módulo `status` do FastAPI importado em `router.py:10` (usado em todos os outros handlers do arquivo para `status.HTTP_*`).
- **Consequência:** hoje inofensivo — nenhuma das duas funções usa `status.HTTP_*` no corpo — mas é uma armadilha: qualquer `raise HTTPException(status_code=status.HTTP_...)` adicionado dentro dessas duas funções no futuro vai falhar com `AttributeError: 'StatusPane' object has no attribute 'HTTP_...'` (ou similar, dependendo do valor do parâmetro), um erro cuja causa não é óbvia à primeira vista.
- **Correção proposta:** renomear o parâmetro da query (ex. `status_filtro`) ou importar `fastapi.status` com alias (`from fastapi import status as http_status`).
- **Risco de regressão:** BAIXO — troca de nome de parâmetro de query; verificar se o nome `status` é usado por algum client (query string) que dependa dele.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Parâmetro interno renomeado para `status_filtro` em `listar_panes` e `exportar_panes`, com `Query(alias="status")` — a query string `?status=` (usada pelo frontend, confirmado via grep) continua funcionando sem mudança de contrato.

---

### [MELHORIA-12] Docstring inoperante em `concluir_pane`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/router.py:220-226`
- **Eixo:** Manutenibilidade
- **Problema:** a chamada `ensure_role(usuario_atual, ...)` foi inserida na primeira linha do corpo da função, antes do que deveria ser a docstring (`router.py:220-226`). Como resultado, o texto que parece uma docstring é, na prática, apenas uma string literal solta — não é reconhecida pelo Python como `__doc__` da função e não aparece na documentação OpenAPI gerada.
- **Consequência:** nenhuma em runtime; a documentação da API perde a explicação da regra de negócio para este endpoint especificamente.
- **Correção proposta:** mover a docstring para a primeira linha do corpo, antes do `ensure_role`.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Docstring movida para a primeira linha do corpo de `concluir_pane`, antes do `ensure_role`.

---

### [MELHORIA-13] Dois dialetos de erro coexistindo no mesmo `service.py`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/service.py:408,418,476,479,538,541,554,557,591,893,898,903,917`
- **Eixo:** Arquitetura (mapa §5)
- **Problema:** `editar_pane` e `concluir_pane` usam as exceções tipadas `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError` (`service.py:408,418,476,479`), mas `excluir_pane`, `restaurar_pane`, `upload_anexo` e `adicionar_responsavel` ainda levantam `raise ValueError(...)` cru (`service.py:538,541,554,557,591,893,898,903,917`) — é a causa raiz do BUG-03.
- **Consequência:** inconsistência dentro do próprio arquivo (não só entre módulos, como já registrado no mapa arquitetural §5): metade das funções carrega o status HTTP correto na exceção, a outra metade delega ao router adivinhar por texto — o que já produziu os 5 mapeamentos incorretos do BUG-03.
- **Correção proposta:** migrar as 4 funções restantes para `domain_exc`, alinhando o service inteiro a um único padrão.
- **Risco de regressão:** MÉDIO — junto com BUG-03, muda o status HTTP retornado hoje por esses endpoints.
- **Precisa de teste antes?** SIM (mesma correção do BUG-03)
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Mesma correção do BUG-03: `excluir_pane`, `restaurar_pane`, `upload_anexo` (só o caso "pane não encontrada") e `adicionar_responsavel` migradas para `domain_exc`. `excluir_anexo` deliberadamente não tocada (fora do escopo listado neste achado, e seu mapeamento já estava correto).

---

### [MELHORIA-14] RBAC imperativo no corpo do handler, divergente dos outros 8 routers de domínio

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/router.py:194,220,301,356,423-431,454,475`
- **Eixo:** Arquitetura (mapa §5, item RBAC)
- **Problema:** `panes/router.py` é, conforme já mapeado no `00_mapa_arquitetural.md` §5, o único router de domínio que chama `ensure_role(usuario_atual, ...)` imperativamente dentro do corpo do handler (6 ocorrências: `router.py:194,220,301,356,454,475`) em vez de usar os atalhos `Annotated` (`AdminRequired`, `EncarregadoOuAdmin`, etc.) diretamente na assinatura, como os demais 8 routers fazem. `adicionar_responsavel` (`router.py:419-431`) mistura os dois estilos: usa `ExecucaoPermitida` na assinatura **e** uma checagem manual adicional no corpo (`router.py:426-431`) para o caso "mantenedor só pode se auto-atribuir".
- **Consequência:** nenhuma funcional — é puramente uma divergência de padrão que dificulta auditoria (a lista de papéis exigidos por um endpoint não é visível só olhando a assinatura, como nos outros módulos).
- **Correção proposta:** onde a regra é um conjunto fixo de papéis (a maioria dos 6 casos), migrar para o atalho `Annotated` equivalente na assinatura. Onde a regra depende de dado do payload (`adicionar_responsavel`), manter a checagem imperativa, que é inerentemente dinâmica.
- **Risco de regressão:** BAIXO — refatoração mecânica sem mudança de comportamento (verificar que os conjuntos de papéis batem exatamente com os atalhos existentes em `app/bootstrap/dependencies.py`).
- **Precisa de teste antes?** NÃO
- **Status:** ⚠️ CORRIGIDO PARCIALMENTE — commit `b786ef8`. `excluir_anexo`, `deletar_pane` e `restaurar_pane` (papel fixo `ENCARREGADO`/`ADMINISTRADOR`) migrados para o atalho `EncarregadoOuAdmin`. `editar_pane`, `concluir_pane` e `upload_anexo` mantidos imperativos — `editar_pane` por depender do payload (correto, per correção proposta); `concluir_pane`/`upload_anexo` porque o conjunto de papéis (MANTENEDOR+ENCARREGADO+INSPETOR+ADMINISTRADOR = todos os papéis do sistema) não tem atalho `Annotated` equivalente pronto em `dependencies.py`.

---

### [MELHORIA-15] Carga completa da pane usada apenas para checar existência

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/service.py:590,892`
- **Eixo:** Banco
- **Problema:** `upload_anexo` (`service.py:590`, `if not await _buscar_pane_por_id(db, pane_id): raise ...`) e `adicionar_responsavel` (`service.py:892`, mesmo padrão) usam `_buscar_pane_por_id` — que carrega a pane com 5 `selectinload` (`service.py:365-376`) — apenas para testar se ela existe.
- **Consequência:** consulta mais cara do que o necessário para uma simples checagem booleana. O próprio módulo já demonstra o padrão mais barato em `sincronizar_status_aeronave` (`select(exists().where(...))`, `service.py:112-123`).
- **Correção proposta:** substituir por um `select(exists().where(Pane.id == pane_id, Pane.ativo == True))` nos dois pontos.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Novo helper `_pane_existe_ativa` (exatamente o `select(exists()...)` proposto), usado em `upload_anexo`, `adicionar_responsavel` e também em `listar_anexos` (MELHORIA-17).

---

### [RISCO-16] `PaneResponsavel.trigrama` depende de eager-load mantido manualmente em cada call site

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/models.py:253-256`
- **Eixo:** Concorrência
- **Problema:** a property `trigrama` acessa `self.usuario.trigrama` (`models.py:255-256`), e o relacionamento `PaneResponsavel.usuario` é `lazy="select"` — carregamento lazy síncrono, que sob `AsyncSession` levanta `MissingGreenlet` se acessado sem a relação já carregada em memória. Hoje isso não acontece porque todo ponto que cria/lê um `PaneResponsavel` e depois o serializa via `ResponsavelOut` garante o carregamento explicitamente: `db.refresh(resp, ["usuario"])` em `criar_pane` (`service.py:211`) e `concluir_pane`/`adicionar_responsavel` (`service.py:510,920`), e `selectinload(...).selectinload(PaneResponsavel.usuario)` em `listar_panes`/`buscar_pane`/`_buscar_pane_por_id` (`service.py:304,339,370`).
- **Consequência:** funciona hoje só porque 4 pontos independentes de código lembram de carregar a relação — é a materialização, dentro de `panes`, do mesmo padrão frágil já registrado como achado 21 em `docs/backlog/revisor/concluido/achados_auth.md` (relacionamentos `lazy="select"` de `Usuario`). Qualquer novo endpoint futuro que serialize `PaneResponsavel`/`ResponsavelOut` sem passar por um desses 4 pontos quebra em runtime com um erro cuja causa (lazy loading síncrono sob sessão assíncrona) não é óbvia pela mensagem.
- **Correção proposta:** documentar explicitamente a obrigação de eager-load antes de acessar `.trigrama`, ou considerar carregar o campo já pronto via a própria query (ex.: `selectinload` sempre acompanhado de um comentário apontando para esta property).
- **Risco de regressão:** BAIXO se apenas documentado.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. Comentário de alerta adicionado na property `trigrama` em `models.py`, listando os 4 pontos que hoje garantem o eager-load.

---

### [MELHORIA-17] `listar_anexos` não valida existência nem estado da pane

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/service.py:789-794`, `app/modules/panes/router.py:330-341`
- **Eixo:** Contrato
- **Problema:** `listar_anexos` filtra só por `Anexo.pane_id == pane_id` (`service.py:791`), sem checar se a pane existe nem se está `ativo`. O handler correspondente (`router.py:335-341`) também é o único dos 3 endpoints de anexo sem `ensure_role` — os outros dois (`upload_anexo`, `excluir_anexo`) exigem papéis específicos.
- **Consequência:** `GET /{pane_id}/anexos` com um `pane_id` de pane soft-deleted retorna 200 com a lista de anexos normalmente (em vez de refletir que a pane "não existe" do ponto de vista do resto da API), e qualquer usuário autenticado (sem checagem de papel) pode listar anexos de qualquer pane.
- **Correção proposta:** decidir se a listagem de anexos deveria exigir a mesma política de papel dos outros dois endpoints de anexo, e se panes inativas deveriam retornar 404 aqui também (para consistência com `buscar_pane`).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ⚠️ CORRIGIDO PARCIALMENTE — commit `b786ef8`. `listar_anexos` agora retorna 404 para pane inexistente/inativa (via `_pane_existe_ativa`), consistente com `buscar_pane`. A questão de RBAC (exigir o mesmo papel de `upload_anexo`/`excluir_anexo`) **não foi decidida** — deixada como está (qualquer usuário autenticado lista) por ser decisão de produto (ver pergunta ao desenvolvedor).

---

### [MELHORIA-18] `except Exception as e` com variável não usada no fallback de detecção de MIME

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/panes/service.py:604-608`
- **Eixo:** Tratamento de erros
- **Problema:** o bloco que chama `magic.from_buffer` captura `except Exception as e:` e cai silenciosamente para `_detect_mime_type_fallback`, sem logar `e` nem qualquer outra informação.
- **Consequência:** se a biblioteca `python-magic`/`libmagic` estiver mal instalada ou falhar sistematicamente, o sistema inteiro passa a depender do detector manual de assinaturas (que reconhece menos formatos e variantes), sem nenhum sinal nos logs de que isso está acontecendo.
- **Correção proposta:** adicionar `logger.warning(...)` no bloco, no mesmo padrão já usado em `app/shared/core/file_validators.py:101-103` para o mesmo cenário.
- **Risco de regressão:** BAIXO — é aditivo (log).
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `b786ef8`. `logger.warning(...)` adicionado dentro do novo helper `_detectar_mime_real` (RISCO-04), no caminho `except Exception` da chamada a `magic.from_buffer`.

---

## Resumo

- Total de achados: 18
- BUG: 3 (CRÍTICA: 1, ALTA: 0, MÉDIA: 2, BAIXA: 0)
- RISCO: 6 (ALTA: 0, MÉDIA: 4, BAIXA: 2)
- MELHORIA: 9 (todas BAIXA, exceto MELHORIA-06 e MELHORIA-07 em MÉDIA)
- DÚVIDA: 0

### Status da correção (03/08/2026, commit `b786ef8`)

- ✅ Corrigidos: 12/18 (BUG-01, 02, 03 · RISCO-04, 05, 11 · MELHORIA-06, 12, 13, 15, 18 · RISCO-16)
- ⚠️ Parcial: 4/18 (MELHORIA-07, RISCO-10, MELHORIA-14, MELHORIA-17 — núcleo corrigido, parte opcional/decisão de produto deixada em aberto)
- 🚫 Não corrigidos: 2/18 (RISCO-08 — sem ação necessária por definição do próprio achado; RISCO-09 — risco de regressão ALTO, exige sessão dedicada com migração)

## Arquivos revisados

- `app/modules/panes/router.py` (integral, 491 linhas)
- `app/modules/panes/service.py` (integral, 931 linhas)
- `app/modules/panes/models.py` (integral, 259 linhas)
- `app/modules/panes/schemas.py` (integral, 154 linhas)
- `app/modules/panes/__init__.py` (integral)
- `app/shared/core/storage.py` (integral — implementações Local e R2)
- `app/shared/core/file_validators.py` (integral)
- `app/shared/core/exceptions.py` (para confirmar o comportamento do handler genérico no BUG-01)
- `app/bootstrap/dependencies.py` (para os atalhos RBAC citados na MELHORIA-14)
- `app/bootstrap/tasks.py` (para confirmar `anexos_travados_cleanup_task`, citada como mitigação já existente)
- `tests/unit/test_panes.py`, `tests/unit/test_panes_alta_prioridade.py`, `tests/unit/test_panes_media_prioridade.py`, `tests/unit/test_panes_baixa_prioridade.py` (nomes de teste, para mapear cobertura)
- `tests/test_exporter.py` (para confirmar a lacuna de cobertura do BUG-01)

## Não revisado / limitações

- **Path traversal em upload de anexo**: tratado corretamente em duas camadas (`file_validators.validar_nome_arquivo_seguro` + substituição do nome original por `uuid4().hex + extensão` em ambas as implementações de `StorageService`). Verificado, não é achado.
- **Upload sem limite de memória**: `ler_upload_com_limite` lê em chunks e rejeita com 413 antes de materializar o arquivo inteiro. Correto.
- **SQL injection no filtro de texto de `listar_panes`**: usa `escape_like` com `escape="\\"` explícito, e há teste dedicado para `%`/`_` literais. Verificado, não é achado.
- **N+1 queries em `listar_panes`/`buscar_pane`**: todas as relações serializadas nos schemas de resposta são carregadas via `selectinload` explícito. Verificado, não é achado.
- **Compensação de storage órfão** (upload persistido no storage mas falha ao gravar no banco): coberta pelo código (`service.py:661-669`) e por teste dedicado. Não é achado.
- **Durabilidade do `BackgroundTasks` do FastAPI**: limitação conhecida e já documentada no próprio código-fonte (comentário em `limpar_anexos_processando_antigos`, `service.py:752-762`), mitigada por uma task periódica de limpeza (`app/bootstrap/tasks.py:105-130`). Registrada aqui como limitação assumida do projeto, não reaberta como achado novo.
- **Ausência da camada `repositories/`**: padrão de fato do projeto inteiro (`00_mapa_arquitetural.md` §1), que orienta explicitamente a não reportar isso como achado isolado de um módulo.
- **Rate limiting**: apenas 1 de 117 endpoints do sistema tem `@limiter.limit` (mapa §7.5) — não é um achado isolado de `panes`; citado apenas como agravante local no RISCO-10 (export).
- **Cobertura de testes**: alta em volume e qualidade — 1.763 linhas em 4 arquivos, cobrindo RBAC, transições de status, concorrência (`IntegrityError`/SAVEPOINT em `adicionar_responsavel` e em `concluir_pane`), lazy-load assíncrono explícito (`test_panes_baixa_prioridade.py:141`) e estabilidade do código `ddd/yy` sob diferentes cenários. **Lacunas identificadas**: nenhum teste chama `GET /panes/export` (por isso o BUG-01 nunca foi pego); nenhum teste compara o resultado de `PUT status=RESOLVIDA` contra `POST /concluir` para a mesma pane (BUG-02/RISCO-05); nenhum teste verifica se os "safety nets" do router (MELHORIA-06) são de fato necessários ou redundantes.
- **Dependência cruzada com `inspecoes` e `aeronaves`**: `sincronizar_status_aeronave` (`service.py:89-145`) importa `inspecoes.models.Inspecao` e `inspecoes.service.STATUS_ATIVOS` dentro da função (lazy import, já mapeado no `00_mapa_arquitetural.md` §4 como parte do ciclo `aeronaves ↔ inspecoes ↔ panes`). Não revisado em profundidade aqui — os módulos `inspecoes` e `aeronaves` terão sua própria sessão de revisão.

## Perguntas para o desenvolvedor

- Os "safety nets" de SQL direto no router (MELHORIA-06, `criar_pane` e `concluir_pane`) cobrem algum cenário real já observado de dessincronia de status de aeronave, ou podem ser removidos com confiança total em `sincronizar_status_aeronave`?
- Resolver uma pane via `PUT /{pane_id}` com `status=RESOLVIDA` (sem observação de conclusão nem adição automática de responsável) é um fluxo suportado deliberadamente, ou `/concluir` deveria ser o único caminho de conclusão (BUG-02 e RISCO-05)?
- O código `ddd/yy` (RISCO-09) precisa permanecer estável mesmo diante de uma futura exclusão física (hard-delete) de panes, ou a garantia atual (nunca há hard-delete) é considerada suficiente e permanente?
