# Achados de Revisão — Módulo `inspecoes`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 03/08/2026
> 11/14 corrigidos, 0 parciais, 3 não corrigidos por decisão consciente (as duas DÚVIDAs,
> respondidas pelo desenvolvedor, e MELHORIA-14, que o próprio achado já classificava como não
> urgente). Suite completa: 390 testes, 0 falhas. Status por item marcado inline em cada achado
> abaixo (campo `**Status:**`).

---

### [BUG-01] `GET /inspecoes/export` retorna 500 em toda chamada — atributos inexistentes

- **Classificação:** BUG
- **Severidade:** CRÍTICA
- **Arquivo:** `app/modules/inspecoes/router.py:301,304,306`
- **Eixo:** Contrato
- **Problema:** `exportar_inspecoes` monta cada linha do relatório acessando `insp.tipo_inspecao.nome` (`router.py:304`) e `insp.dpe` (`router.py:306`). Nenhum dos dois atributos existe no modelo `Inspecao` (`models.py:119-153`): o relacionamento real se chama `tipos_aplicados` (lista, não singular) e a data prevista se chama `data_fim_prevista`. `grep -rn "\.tipo_inspecao\b\|\.dpe\b" app/modules/inspecoes/` confirma que só `router.py` usa esses dois nomes — `pdf_service.py`, que gera os PDFs a partir do mesmo objeto `Inspecao`, usa corretamente `tipos_aplicados` e `data_fim_prevista` (`pdf_service.py:225,229`).
- **Consequência:** toda chamada a `GET /inspecoes/export` (CSV ou XLSX), mesmo com zero ou uma inspeção retornada por `listar_inspecoes`, levanta `AttributeError` dentro do laço de montagem das linhas. Isso é capturado pelo handler genérico de exceções e devolvido como 500 "Erro interno do servidor" — o endpoint de exportação está inteiramente quebrado, sem exceção. Nenhum teste cobre isso: nem `tests/unit/test_inspecoes.py`, nem `tests/unit/test_inspecoes_refatoracao.py`, nem `tests/unit/test_inspecao_pdf.py` chamam `/export` (confirmado por busca em todos os três arquivos).
- **Correção proposta:** trocar `insp.tipo_inspecao.nome` por algo como `", ".join(t.nome for t in insp.tipos_aplicados)` (já usado como padrão em `pdf_service.py:225`) e `insp.dpe` por `insp.data_fim_prevista`.
- **Risco de regressão:** BAIXO — troca mecânica de nomes de atributo, sem mudança de comportamento pretendido.
- **Precisa de teste antes?** SIM (o bug só passou despercebido porque não existe nenhum teste de integração para este endpoint)
- **Status:** ✅ CORRIGIDO. `tipo_inspecao.nome` → `", ".join(t.nome for t in insp.tipos_aplicados)`; `insp.dpe` → `insp.data_fim_prevista`. Teste: `test_exportar_inspecoes_nao_levanta_attributeerror` (tests/unit/test_inspecoes_achados_revisor.py).

---

### [BUG-02] `atualizar_tarefa_inspecao` sobrescreve `data_execucao`/`executado_por_id` em toda reedição de tarefa já concluída

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/inspecoes/service.py:560-567`
- **Eixo:** Contrato / Banco
- **Problema:** sempre que `status_novo` é `CONCLUIDA` ou `NA`, o código regrava `tarefa.executado_por_id` e `tarefa.data_execucao = datetime.now(timezone.utc)` incondicionalmente (`service.py:566-567`), mesmo quando a tarefa já estava nesse status e a chamada é apenas para editar `observacao_execucao` (reenviando o mesmo `status=CONCLUIDA`). Não há checagem de transição (`tarefa.status != status_novo.value`) antes de regravar esses dois campos.
- **Consequência:** num contexto de rastreabilidade aeronáutica, cada edição de observação de uma tarefa já concluída apaga o registro original de quem executou e quando — o campo passa a refletir a data/hora da última edição, não da execução real. `tests/unit/test_inspecoes.py:200-233` cobre apenas a primeira transição (PENDENTE → CONCLUIDA), não uma segunda chamada sobre uma tarefa já concluída.
- **Correção proposta:** só regravar `executado_por_id`/`data_execucao` quando `tarefa.status != status_novo.value` (transição real), preservando os valores originais em reedições que mantêm o mesmo status.
- **Risco de regressão:** BAIXO — restringe a regravação a um caso mais específico; nenhum teste depende do comportamento atual de sobrescrita.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `executado_por_id`/`data_execucao` só são regravados quando `tarefa.status != status_novo.value` (transição real) ou quando o cliente envia `executado_por_id` explicitamente. Testes: `test_reeditar_tarefa_concluida_preserva_executor_e_data_original`, `test_transicao_real_para_concluida_atualiza_executor_e_data`.

---

### [BUG-03] Semântica de PATCH quebrada — `observacao_execucao`, `observacoes` e `pane_id` não seguem `exclude_unset`

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/inspecoes/service.py:499,573,575-576`
- **Eixo:** Contrato
- **Problema:** três pontos do módulo gravam campos opcionais sem usar `dados.model_dump(exclude_unset=True)`, padrão já adotado em `atualizar_tipo_inspecao` (`service.py:122`) e `atualizar_tarefa_catalogo` (`service.py:187`) para o restante do arquivo. Em `atualizar_tarefa_inspecao`: `tarefa.observacao_execucao = dados.observacao_execucao` (`service.py:573`) apaga a observação sempre que o cliente não a reenviar; `if dados.pane_id: tarefa.pane_id = dados.pane_id` (`service.py:575-576`) usa checagem de truthy, então é impossível **limpar** um `pane_id` já setado (enviar `null` não tem efeito). Em `atualizar_inspecao`: `inspecao.observacoes = dados.observacoes` (`service.py:499`) apaga as observações sempre que o campo vier `None` — e como `InspecaoUpdate` só tem esse único campo (`schemas.py:126-127`), toda chamada ao endpoint zera as observações a menos que o cliente reenvie o texto completo de volta.
- **Consequência:** um cliente que atualize uma tarefa só para trocar o `status` (sem reenviar `observacao_execucao`) apaga silenciosamente qualquer observação já registrada; o mesmo vale para `PUT /inspecoes/{id}` e `observacoes`. E não existe nenhum caminho para desvincular uma tarefa de uma pane (`pane_id`) uma vez associada.
- **Correção proposta:** usar `dados.model_dump(exclude_unset=True)` nos três pontos, seguindo o padrão já usado no restante do arquivo — isso também resolve a limitação de nunca poder limpar `pane_id`.
- **Risco de regressão:** MÉDIO — muda o contrato do PATCH para não apagar mais campos omitidos; qualquer cliente que hoje dependa (mesmo sem perceber) de "enviar `status` sempre limpa a observação" precisa ser revisto.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. Os três pontos usam `dados.model_dump(exclude_unset=True)`; `pane_id` agora aceita `null` explícito para desvincular. Testes: `test_atualizar_tarefa_sem_observacao_no_payload_preserva_a_existente`, `test_atualizar_inspecao_sem_observacoes_no_payload_preserva_a_existente`, `test_pane_id_null_explicito_desvincula_tarefa_de_pane`.

---

### [BUG-04] `abrir_inspecao` não deduplica `tipos_inspecao_ids` repetidos — linhas duplicadas em `InspecaoEventoTipo`

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:387-398,436-437`
- **Eixo:** Banco / Contrato
- **Problema:** `tipos_por_id` (`service.py:393`) já deduplica por ID a partir do resultado da query, mas a linha seguinte reconstrói a lista a partir do payload original do cliente: `tipos = [tipos_por_id[tid] for tid in dados.tipos_inspecao_ids]` (`service.py:398`). Se o cliente enviar `[A, A, B]`, `tipos` vira `[A, A, B]` — e o laço `for tipo in tipos: db.add(InspecaoEventoTipo(...))` (`service.py:436-437`) insere duas linhas para o mesmo par `(inspecao, A)`. Não há `UniqueConstraint` na tabela `inspecao_evento_tipos` (`models.py:101-116`) que impeça isso.
- **Consequência:** a inspeção fica com duas linhas de vínculo para o mesmo tipo. Como o relacionamento `Inspecao.tipos_aplicados` é uma lista simples (não deduplicada) sobre essa tabela de associação, `GET /inspecoes/{id}` e a listagem passam a exibir o mesmo tipo de inspeção duas vezes em `tipos_aplicados`. As tarefas instanciadas não duplicam (a deduplicação por título em `service.py:457-466` absorve o efeito colateral nesse ponto), mas o dado de vínculo fica incorreto.
- **Correção proposta:** deduplicar `dados.tipos_inspecao_ids` preservando ordem (ex.: `list(dict.fromkeys(...))`) antes de montar `tipos` em `service.py:398`.
- **Risco de regressão:** BAIXO — fecha uma lacuna, não recorta nenhum comportamento hoje intencional.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `tipos_inspecao_ids` deduplicado via `list(dict.fromkeys(...))` preservando ordem, logo no início de `abrir_inspecao`. Teste: `test_abrir_inspecao_deduplica_tipos_inspecao_ids_repetidos`.

---

### [BUG-05] `pane_id` inválido em `atualizar_tarefa_inspecao` derruba a requisição com 500 em vez de erro de negócio

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:575-576,581`
- **Eixo:** Contrato / Banco
- **Problema:** `tarefa.pane_id = dados.pane_id` (`service.py:576`) grava o UUID recebido do cliente sem verificar se existe uma `Pane` com esse ID. A FK existe no modelo (`InspecaoTarefa.pane_id`, `models.py:180`, `ondelete="SET NULL"`) e é de fato aplicada em runtime (`PRAGMA foreign_keys=ON` em `app/bootstrap/database.py:52`), mas o `await db.flush()` em `service.py:581` não está envolvido em `try/except IntegrityError` — diferente do padrão já usado em `criar_tipo_inspecao` (`service.py:80-88`) para o mesmo tipo de violação.
- **Consequência:** um `pane_id` inexistente (UUID malformado do ponto de vista de negócio, mas válido como UUID) faz o `flush()` estourar `IntegrityError` sem tratamento, que sobe até o handler genérico de exceções e vira 500 "Erro interno do servidor" — em vez de um 404/422 informando que a pane não existe.
- **Correção proposta:** validar a existência da `Pane` antes de atribuir (ex.: um `select(exists())` simples), levantando `domain_exc.EntidadeNaoEncontradaError` como já é feito para `executor_id` (`service.py:563-565`).
- **Risco de regressão:** BAIXO — apenas adiciona uma validação antes de um caminho que hoje já falha, só que com o status HTTP errado.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. Valida `Pane` existente via `select(Pane.id)` antes de gravar `pane_id`, levantando `EntidadeNaoEncontradaError`. Teste: `test_atualizar_tarefa_com_pane_id_inexistente_levanta_404_nao_500`. O teste pré-existente `test_rn04_tarefa_com_anomalia_deve_gerar_pane_vinculada` usava um `pane_id` forjado (`uuid.uuid4()` sem `Pane` real) — atualizado para criar uma `Pane` real primeiro.

---

### [RISCO-06] `atualizar_tipo_inspecao` sem proteção contra corrida de UNIQUE no código

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:122-140`
- **Eixo:** Concorrência / Banco
- **Problema:** ao trocar o `codigo` de um tipo de inspeção, o método verifica unicidade com uma consulta prévia (`service.py:126-128`) e só depois atribui `tipo.codigo = codigo` (`service.py:129`), sem `async with db.begin_nested(): ... except IntegrityError` em volta do `await db.flush()` (`service.py:140`) — diferente do padrão já aplicado em `criar_tipo_inspecao` (`service.py:80-88`, com o comentário explícito "SAVEPOINT: em caso de criação concorrente com o mesmo código...") e em `criar_tarefa_template` (`service.py:257-268`) no mesmo arquivo.
- **Consequência:** duas requisições concorrentes trocando o código de dois tipos diferentes para o mesmo valor passam ambas na checagem prévia; a segunda a fazer `flush()` recebe um `IntegrityError` cru, não capturado, que sobe até o handler genérico e retorna 500 em vez do 409 que o usuário veria no caso não concorrente (mesma mensagem já usada em `criar_tipo_inspecao`).
- **Correção proposta:** envolver a atribuição de `tipo.codigo` e o `flush()` seguinte no mesmo padrão SAVEPOINT + `except IntegrityError` já usado em `criar_tipo_inspecao`.
- **Risco de regressão:** BAIXO — replica um padrão já validado no mesmo arquivo, para o mesmo tipo de conflito.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `tipo.codigo = codigo` + `flush()` envolvidos em `async with db.begin_nested(): ... except IntegrityError`, mesmo padrão de `criar_tipo_inspecao`. Teste: `test_atualizar_tipo_inspecao_savepoint_absorve_integrity_error_sem_derrubar_sessao` (força a colisão no flush do SAVEPOINT, não no pre-check, e confirma que a sessão continua utilizável depois).

---

### [RISCO-07] `listar_inspecoes` carrega todas as tarefas de cada inspeção só para calcular progresso

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:341-345`, `app/modules/inspecoes/router.py:268-277`
- **Eixo:** Banco
- **Problema:** `listar_inspecoes` usa `selectinload(Inspecao.tarefas)` (`service.py:344`) para popular até `LIMITE_MAXIMO_LISTAGEM=200` inspeções (`service.py:36,353,355`); o único consumidor dessas tarefas no router é `service.calcular_progresso(inspecao)` (`router.py:271`), que só precisa de `len(inspecao.tarefas)` e uma contagem por status (`service.py:654-658`) — não dos dados completos de cada tarefa (título, descrição, observação, executor).
- **Consequência:** cada chamada a `GET /inspecoes/` (tela de listagem) paga o custo de carregar potencialmente milhares de linhas de `InspecaoTarefa` (até 200 inspeções × N tarefas cada) inteiras, só para extrair dois números por inspeção. O mesmo padrão se repete em `exportar_inspecoes` (`router.py:298,302`), que reusa `listar_inspecoes` sem paginação real (limite fixo de 1000).
- **Correção proposta:** substituir o `selectinload(Inspecao.tarefas)` por uma agregação no banco (contagem total e contagem de concluídas via subquery correlacionada, no mesmo espírito do `calcular_progresso` atual), carregando apenas os dois números por inspeção em vez das linhas completas.
- **Risco de regressão:** MÉDIO — muda a forma de retorno de `listar_inspecoes`; qualquer código que hoje dependa de `inspecao.tarefas` estar populado após essa chamada específica precisa ser ajustado.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `listar_inspecoes` não faz mais `selectinload(Inspecao.tarefas)`; nova função `contar_tarefas_por_inspecao` traz só (total, concluídas) por inspeção via agregação (`func.count`/`func.sum(case(...))` agrupado por `inspecao_id`). Router (`listar_inspecoes`/`exportar_inspecoes`) usa essa contagem em vez de `calcular_progresso(inspecao)` (que dependia de `.tarefas` carregado — `calcular_progresso` continua existindo e testada isoladamente, só não é mais chamada nesses dois pontos). Testes: `test_contar_tarefas_por_inspecao_retorna_contagens_corretas`, `test_endpoint_listar_inspecoes_usa_queries_constantes_independente_do_num_tarefas`.

---

### [DÚVIDA-08] Deduplicação de tarefas por título ao montar o checklist de `abrir_inspecao`

- **Classificação:** DÚVIDA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:457-466`
- **Eixo:** Contrato
- **Problema:** ao combinar templates de múltiplos tipos de inspeção, a chave de deduplicação é `t.tarefa_catalogo.titulo.strip().lower()` (`service.py:459`), não `t.tarefa_catalogo_id`. `tests/unit/test_inspecoes.py:414-438` (`test_rn01_abrir_inspecao_com_multiplos_tipos_e_deduplicar_tarefas`) confirma que isso é comportamento **intencional e testado**: o teste cria duas `TarefaCatalogo` **distintas** (IDs diferentes) chamadas "Tarefa obrigatoria 1"/"Tarefa obrigatoria 2" para dois tipos diferentes e afirma explicitamente que o resultado deve ter só 2 tarefas (dedupe por título entre catálogos distintos, não só dentro do mesmo catálogo reaproveitado).
- **Consequência:** quando dois tipos de inspeção têm tarefas de catálogo **diferentes** que por coincidência compartilham o título, a tarefa instanciada na inspeção grava um `tarefa_catalogo_id` arbitrário — o do template "visto primeiro" (`service.py:461-464`), não necessariamente uma escolha determinística ou documentada para quem for investigar o vínculo depois. Se essa coincidência de título não for garantida pelo cadastro (nada no schema impede dois itens de catálogo com o mesmo `titulo`), o vínculo `tarefa_catalogo_id` da tarefa final pode não refletir o catálogo que o operador esperava.
- **Correção proposta:** confirmar com o desenvolvedor se a intenção de RN-01 é realmente "mesmo título = mesma tarefa" entre catálogos distintos (caso em que vale documentar isso explicitamente no código, já que hoje só existe no teste) ou se o dedupe deveria ocorrer apenas por `tarefa_catalogo_id` (permitindo tarefas de título igual, mas catálogo diferente, coexistirem na mesma inspeção).
- **Risco de regressão:** ALTO se o comportamento for trocado — o teste RN-01 citado quebraria e a contagem de tarefas por inspeção mudaria para quem já usa múltiplos tipos combinados.
- **Precisa de teste antes?** SIM, se e quando a resposta à dúvida implicar mudança de comportamento.
- **Resposta do desenvolvedor:** manter dedupe por título — é o comportamento intencional e já testado (RN-01).
- **Status:** 🚫 NÃO CORRIGIDO (decisão consciente — nada a corrigir). Documentado explicitamente no código em `abrir_inspecao` (comentário acima do laço de deduplicação), como sugerido na correção proposta, para não ficar só implícito no teste.

---

### [DÚVIDA-09] Regressão de status da inspeção não é revertida quando a última tarefa executada volta a `PENDENTE`

- **Classificação:** DÚVIDA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/inspecoes/service.py:568-570,578-579`
- **Eixo:** Contrato
- **Problema:** `atualizar_tarefa_inspecao` promove a inspeção de `ABERTA` para `EM_ANDAMENTO` na primeira tarefa que sai de `PENDENTE` (`service.py:578-579`), mas não existe o caminho inverso: se essa mesma tarefa (ou a única que havia sido tocada) voltar para `PENDENTE` (`service.py:568-570`), a inspeção permanece `EM_ANDAMENTO` indefinidamente, mesmo que nenhuma tarefa tenha sido de fato executada.
- **Consequência:** a tela de acompanhamento mostra uma inspeção "em andamento" sem nenhum trabalho registrado, caso o único progresso feito seja desfeito. Não há teste cobrindo esse cenário de regressão.
- **Correção proposta:** confirmar se é intencional que `EM_ANDAMENTO` seja um status "só de ida" (uma vez iniciado, nunca volta a `ABERTA`) ou se a inspeção deveria reverter para `ABERTA` quando nenhuma tarefa restar com status diferente de `PENDENTE`.
- **Risco de regressão:** BAIXO — reverter o status é aditivo e não afeta o caminho de progresso normal.
- **Precisa de teste antes?** SIM, se for decidido implementar a reversão.
- **Resposta do desenvolvedor:** não implementar — manter `EM_ANDAMENTO` como status "só de ida".
- **Status:** 🚫 NÃO CORRIGIDO (decisão consciente de produto — nenhuma mudança de código).

---

### [MELHORIA-10] `abrir_inspecao` valida disponibilidade de templates depois de já ter mutado estado

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/inspecoes/service.py:417-455`
- **Eixo:** Arquitetura
- **Problema:** a checagem "os tipos selecionados têm tarefas template cadastradas" (`service.py:454-455`) só acontece depois de `db.add(inspecao)` + `await db.flush()` (`service.py:433-434`) e de já ter setado `aeronave.status = StatusAeronave.INSPECAO.value` (`service.py:439`) em memória. Hoje isso é seguro porque a dependência `get_db` (`app/bootstrap/dependencies.py:31-39`) faz `rollback()` de qualquer exceção não tratada antes que a sessão seja reusada, e não há nenhum `commit()` intermediário dentro de `abrir_inspecao` — mas a ordem inverte a prática mais robusta de "validar tudo, depois escrever tudo", ficando dependente desse comportamento da camada de infraestrutura para permanecer seguro.
- **Consequência:** nenhuma hoje, dado o `rollback` garantido em `get_db`. O risco é de manutenção futura: qualquer mudança que introduza um `commit()` parcial dentro da função (ex.: uma tarefa em background, ou um refactor que quebre a função em duas transações) deixaria a aeronave presa em `INSPECAO` com uma inspeção órfã sem templates.
- **Correção proposta:** reordenar para validar aeronave, usuário, tipos, inspeção ativa e templates **antes** de qualquer `db.add`/mutação de `aeronave.status`.
- **Risco de regressão:** BAIXO — reordenação de validações sem mudança de resultado final nos casos de sucesso.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO. Validações de aeronave, tipos, usuário, inspeção ativa e templates agora acontecem antes de qualquer `db.add`/mutação de `aeronave.status`. Teste: `test_abrir_inspecao_sem_templates_nao_move_aeronave_para_inspecao` (adicionado apesar do "NÃO" original, para travar o comportamento agora que a ordem mudou).

---

### [MELHORIA-11] Filtro por tipo em `listar_inspecoes` sem `.distinct()` e ordenação sem desempate

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/inspecoes/service.py:349-350,357`
- **Eixo:** Banco
- **Problema:** o filtro `filtros.tipo_inspecao_id` faz `query.join(Inspecao.tipos_aplicados).where(TipoInspecao.id == filtros.tipo_inspecao_id)` (`service.py:349-350`) sem `.distinct()` — se uma inspeção tiver duas linhas de vínculo para o mesmo tipo (cenário do BUG-04), ela apareceria duas vezes na listagem filtrada por esse tipo. Separadamente, `order_by(Inspecao.data_abertura.desc())` (`service.py:357`) não tem critério de desempate (ex.: `Inspecao.id`), então duas inspeções abertas no mesmo instante podem ter ordem instável entre páginas.
- **Consequência:** hoje o efeito prático do primeiro ponto depende do BUG-04 já estar presente nos dados; o segundo é uma fragilidade latente de paginação (itens podem ser pulados ou repetidos ao navegar entre páginas) que só se manifesta com volume e timestamps colididos.
- **Correção proposta:** adicionar `.distinct()` à query quando o filtro por tipo for usado, e um segundo critério de ordenação (`Inspecao.id`) como desempate.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO. `.distinct()` aplicado quando `filtros.tipo_inspecao_id` é usado; `order_by(Inspecao.data_abertura.desc(), Inspecao.id)` para desempate. Teste: `test_listar_inspecoes_filtro_por_tipo_nao_duplica_com_vinculo_repetido`.

---

### [MELHORIA-12] Recarregamento completo da inspeção após mudanças que não afetam relações

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/inspecoes/service.py:499-505,619-631,639-648`
- **Eixo:** Banco
- **Problema:** `atualizar_inspecao` (só muda `observacoes`), `concluir_inspecao` e `cancelar_inspecao` fazem `await db.flush()` e em seguida chamam `buscar_inspecao(db, inspecao_id)` de novo (`service.py:502,628,645`), refazendo os 5 `selectinload` da função (`service.py:361-373`) sobre um objeto que já está carregado e atualizado na mesma sessão — nenhuma dessas três operações cria ou altera as relações (`aeronave`, `tipos_aplicados`, `aberto_por`, `concluido_por`, `tarefas`) que justificariam um recarregamento.
- **Consequência:** três consultas com eager-loading completo desnecessárias por chamada a esses três endpoints. Diferente de `abrir_inspecao`, onde o recarregamento é necessário porque as tarefas/tipos acabaram de ser inseridos e precisam ser materializados na coleção do objeto.
- **Correção proposta:** para essas três funções, retornar o próprio objeto `inspecao` já em memória (após `flush`/`refresh` pontual dos campos alterados) em vez de chamar `buscar_inspecao` de novo.
- **Risco de regressão:** BAIXO — o objeto já reflete o estado pós-`flush` dentro da mesma sessão; a troca não muda o conteúdo retornado, só evita as consultas redundantes.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO, com um ajuste sobre a proposta original. Implementado como descrito (sem re-chamar `buscar_inspecao`), mas com uma pegadinha real encontrada ao testar: `Inspecao.updated_at` (`onupdate=func.now()`) fica **expirado** no objeto após `db.flush()` — acessá-lo depois (ex.: ao serializar `InspecaoOut`) sem um `db.refresh()` explícito estoura `MissingGreenlet` (lazy-load implícito não suportado em contexto async). Adicionado `await db.refresh(inspecao, attribute_names=["updated_at"])` nas três funções — refresh pontual só da coluna, sem re-disparar os `selectinload`. Em `concluir_inspecao`, `inspecao.concluido_por_id = concluido_por_id` foi trocado por `inspecao.concluido_por = usuario` (atribuir o objeto, não só o FK cru) para manter a relação já carregada em memória em vez de ficar dessincronizada. Pego pelo teste pré-existente `test_rbac_inspetor_pode_validar_inspecao`, que falhou na primeira tentativa da correção.

---

### [MELHORIA-13] Padrão `if "campo" in changes and changes["campo"] is not None` repetido sem helper

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/inspecoes/service.py:122-140,187-199,283-300`
- **Eixo:** Arquitetura
- **Problema:** `atualizar_tipo_inspecao`, `atualizar_tarefa_catalogo` e `atualizar_tarefa_template` repetem a mesma estrutura de checagem campo a campo (`"x" in changes and changes["x"] is not None: entidade.x = changes["x"]`), incluindo a variação com `.strip()` para campos de texto.
- **Consequência:** nenhuma em runtime; qualquer novo campo atualizável precisa replicar manualmente o mesmo bloco em cada função, com risco de esquecer o `.strip()` ou a checagem de `None` em algum ponto novo.
- **Correção proposta:** extrair um helper pequeno e local ao módulo (ex.: aplica um dicionário de mudanças a uma entidade, com conjunto opcional de campos a normalizar com `.strip()`), reduzindo a duplicação sem alterar o comportamento de nenhuma das três funções.
- **Risco de regressão:** BAIXO — refatoração mecânica, mesma lógica por campo.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO. Helper `_aplicar_mudancas(entidade, changes, campos, campos_nulaveis, campos_strip)` extraído e usado nas três funções — distingue campos que ignoram `None` (`campos`) dos que aceitam `None` explicitamente para limpar (`campos_nulaveis`, ex. `descricao`). Refatoração mecânica, coberta pelos testes de CRUD já existentes (`test_crud_tipo_inspecao_completo`, `test_crud_tarefa_catalogo`, `test_fluxo_tarefas_template`).

---

### [MELHORIA-14] `service.py` mistura quatro agregados diferentes em um único arquivo de 658 linhas

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/inspecoes/service.py` (arquivo inteiro)
- **Eixo:** Arquitetura
- **Problema:** o arquivo concentra CRUD de `TipoInspecao` (`service.py:68-150`), CRUD de `TarefaCatalogo` (`service.py:153-207`), CRUD/reordenação de `TarefaTemplate` (`service.py:210-334`) e todo o ciclo de vida de `Inspecao`/`InspecaoTarefa` (`service.py:337-658`) — quatro responsabilidades relativamente independentes, cada uma com seu próprio conjunto de regras de negócio.
- **Consequência:** nenhuma em runtime; dificulta localizar código relevante e aumenta a chance de alterações em uma área colidirem (no diff) com alterações em outra, sem relação de negócio entre elas.
- **Correção proposta:** se o módulo continuar crescendo, avaliar promover `service.py` a pacote (`service/tipos.py`, `service/catalogo.py`, `service/templates.py`, `service/inspecoes.py`, reexportados por um `__init__.py` para não quebrar imports existentes). Não é urgente no tamanho atual — registrar como sinal a observar, não como ação imediata.
- **Risco de regressão:** BAIXO, se feito como reexport puro sem mudar assinaturas.
- **Precisa de teste antes?** NÃO
- **Status:** 🚫 NÃO CORRIGIDO — o próprio achado já classifica como "não urgente no tamanho atual... sinal a observar, não ação imediata". Mantido como está nesta sessão; revisitar se o arquivo continuar crescendo.

---

## Resumo

- Total de achados: 14
- BUG: 5 (CRÍTICA: 1, ALTA: 2, MÉDIA: 2, BAIXA: 0)
- RISCO: 2 (MÉDIA: 2)
- MELHORIA: 5 (MÉDIA: 1, BAIXA: 4)
- DÚVIDA: 2
- **Corrigidos: 11/14** — 3 não corrigidos por decisão consciente: as duas DÚVIDAs (respondidas pelo desenvolvedor, sem mudança de código) e MELHORIA-14 (o próprio achado já classifica como "não urgente... sinal a observar")

## Arquivos revisados

- `app/modules/inspecoes/router.py` (integral, 472 linhas)
- `app/modules/inspecoes/service.py` (integral, 658 linhas)
- `app/modules/inspecoes/models.py` (integral, 189 linhas)
- `app/modules/inspecoes/schemas.py` (integral, 215 linhas)
- `app/modules/inspecoes/pdf_service.py` (integral, 893 linhas — para confirmar que não repete os erros de atributo do BUG-01)
- `app/modules/inspecoes/__init__.py`
- `app/bootstrap/dependencies.py` (para confirmar o comportamento de `rollback` de `get_db`, citado no MELHORIA-10, e os atalhos de RBAC usados no router)
- `app/bootstrap/database.py` (para confirmar `PRAGMA foreign_keys=ON`, citado no BUG-05)
- `app/shared/core/exceptions.py` (para confirmar o handler genérico que devolve 500)
- `tests/unit/test_inspecoes.py`, `tests/unit/test_inspecoes_refatoracao.py`, `tests/unit/test_inspecao_pdf.py` (nomes e corpo dos testes, para mapear cobertura e confirmar o comportamento intencional do DÚVIDA-08)

## Não revisado / limitações

- **RBAC do módulo**: `atualizar_tarefa_inspecao` e `adicionar_tarefa_avulsa` exigem apenas `CurrentUser` (qualquer um dos 4 papéis do sistema), enquanto `abrir_inspecao`/`atualizar_inspecao`/`concluir_inspecao`/`cancelar_inspecao` exigem `EncarregadoInspetorOuAdmin` (exclui `MANTENEDOR`). Verificado contra a descrição de papéis em `app/shared/core/enums.py:43-55` ("MANTENEDOR: execução de manutenção") — parece design intencional (quem executa a manutenção pode marcar tarefas, mas não abrir/fechar a inspeção), não é achado.
- **Geração de PDF (`pdf_service.py`)**: lido por completo para confirmar que não repete os erros de atributo do BUG-01, mas a lógica de layout/conteúdo do PDF em si (mais de 800 linhas de montagem de tabelas ReportLab) não foi revisada linha a linha em busca de bugs de formatação — fora do escopo de uma revisão de regras de negócio e concorrência.
- **Dependência cruzada com `panes`**: `_sincronizar_status_aeronave` (`service.py:58-65`) delega para `panes.service.sincronizar_status_aeronave` via import local — a lógica de fato já foi revisada na sessão do módulo `panes` (`docs/backlog/revisor/concluido/achados_panes.md`, RISCO-08 e RISCO-09); não repetida aqui.
- **Cobertura de testes**: boa para os caminhos de CRUD e para a regra RN-01/RN-02/RN-04/RN-05 de negócio (1.060 linhas em 3 arquivos). **Lacunas identificadas**: nenhum teste chama `GET /inspecoes/export` (por isso o BUG-01 nunca foi pego); nenhum teste reedita uma tarefa já `CONCLUIDA` (BUG-02); nenhum teste verifica que `observacoes`/`observacao_execucao`/`pane_id` sobrevivem a um PATCH parcial (BUG-03); nenhum teste envia `tipos_inspecao_ids` duplicados (BUG-04); nenhum teste envia `pane_id` inexistente (BUG-05); nenhum teste exercita atualização concorrente de `codigo` em `atualizar_tipo_inspecao` (RISCO-06).

## Perguntas para o desenvolvedor (respondidas)

- A deduplicação de tarefas por título entre catálogos distintos (DÚVIDA-08, testada em RN-01) é a regra de negócio pretendida, ou o dedupe deveria considerar apenas `tarefa_catalogo_id`, permitindo tarefas de título igual mas catálogo diferente coexistirem na mesma inspeção? **Resposta: manter por título — é o comportamento intencional.**
- Uma inspeção que atinge `EM_ANDAMENTO` deveria poder reverter para `ABERTA` se a última tarefa tocada voltar a `PENDENTE` (DÚVIDA-09), ou `EM_ANDAMENTO` é intencionalmente um status "só de ida"? **Resposta: não implementar a reversão — status "só de ida" intencional.**
