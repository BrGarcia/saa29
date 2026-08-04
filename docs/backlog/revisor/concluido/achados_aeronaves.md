# Achados de Revisão — Módulo `aeronaves`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 03/08/2026
> 7/7 achados corrigidos, 0 parciais, 0 não corrigidos. As 2 perguntas ao desenvolvedor
> (RISCO-05, RISCO-03) foram respondidas antes da implementação — ver decisões inline em cada
> achado. Commit `671082e`. Suite completa: 397 testes, 0 falhas. Status por item marcado inline
> em cada achado abaixo (campo `**Status:**`).

---

### [BUG-01] Aeronave pode ficar travada em status INSPECAO sem nenhuma inspeção real por trás

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/aeronaves/service.py:105-122,125-157`
- **Eixo:** Contrato / Arquitetura
- **Problema:** `atualizar_aeronave` bloqueia explicitamente qualquer mudança de status **saindo** de `INSPECAO` a menos que o novo status também seja `INSPECAO` (`service.py:142-143`, "Aeronave em inspeção ativa. Conclua a inspeção para alterar o status.") e bloqueia mudanças **entrando** em `INSPECAO` manualmente (`service.py:139-140`, "Use o módulo de Inspeções"). Essas duas guardas pressupõem que `status == INSPECAO` só pode ter sido gravado por uma inspeção real. Mas `criar_aeronave` (`service.py:105-122`) monta `Aeronave(**dados.model_dump())` direto do payload do cliente **sem nenhuma validação de status** — `AeronaveCreate.status` (`schemas.py:20`) aceita qualquer valor do enum, incluindo `INSPECAO`, na criação.
- **Consequência:** um `POST /aeronaves/` com `{"status": "INSPEÇÃO", ...}` cria uma aeronave presa em `INSPECAO` sem que exista nenhum registro em `Inspecao` por trás. A partir daí, tanto `PUT /aeronaves/{id}` quanto `POST /{id}/toggle-status` (`router.py:110-128`, que chama `alternar_status_aeronave`, `service.py:82-83`) recusam qualquer transição, porque ambos tratam `status==INSPECAO` como prova de inspeção ativa sem consultar a tabela `inspecoes`. O único caminho de recuperação é indireto: abrir uma pane para essa aeronave (o que aciona `panes.service.sincronizar_status_aeronave`, que consulta a tabela real e corrige para `INDISPONIVEL`/`DISPONIVEL`) — nenhum endpoint do próprio módulo `aeronaves` resolve o problema que o próprio módulo criou.
- **Correção proposta:** aplicar em `criar_aeronave` a mesma guarda já existente em `atualizar_aeronave` — rejeitar `status == INSPECAO` na criação, já que a única fonte legítima desse status é o módulo de inspeções.
- **Risco de regressão:** BAIXO — fecha uma lacuna, não recorta comportamento hoje intencional (nenhum teste depende de criar aeronave já em `INSPECAO`).
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `criar_aeronave` rejeita `status == INSPECAO` com `ConflitoNegocioError` (409), mesma guarda de `atualizar_aeronave`. Teste: `test_criar_aeronave_com_status_inspecao_e_rejeitada` (tests/unit/test_aeronaves_achados_revisor.py).

---

### [BUG-02] `listar_aeronaves` reimplementa a sincronização de status de forma incompleta — não corrige status INSPECAO órfão

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/aeronaves/service.py:38-68`
- **Eixo:** Arquitetura / Contrato
- **Problema:** este é o **terceiro** lugar do código que reimplementa a regra "sincronizar status da aeronave com base em panes/inspeções ativas" (os outros dois — `panes.service.sincronizar_status_aeronave`, canônico, e os "safety nets" em SQL cru de `panes/router.py` — já estão documentados em `docs/backlog/revisor/concluido/achados_panes.md`, MELHORIA-06 — corrigido). A versão aqui, embutida em `listar_aeronaves`, tem uma lacuna que as outras duas não têm: seu `else` final só reseta para `DISPONIVEL` quando `status_base == StatusAeronave.INDISPONIVEL.value` (`service.py:59`) — comparado à versão canônica em `panes/service.py:141`, que reseta a partir de `[INDISPONIVEL, INSPECAO, "INSPEÇÃO"]`. Uma aeronave com `status=INSPECAO` (ou `"INSPEÇÃO"`) sem inspeção ativa nem pane aberta cai no `else` (`novo_status = None`, `service.py:61-62`) e **nunca é corrigida** por esta função.
- **Consequência:** ao listar a frota (`GET /aeronaves/`, a tela de "Controle de Frota"), uma aeronave que ficou com `INSPECAO` órfão (cenário do BUG-01, ou qualquer outra causa futura) continua exibida como "em inspeção" indefinidamente — a própria função que existe para corrigir isso na listagem falha silenciosamente nesse caso específico. Nenhum teste cobre esse cenário (os testes existentes de sincronização — `test_status_aeronave_permanece_inspecao_quando_pane_aberta` — cobrem o caso com pane aberta, não o caso sem pane nem inspeção).
- **Correção proposta:** alinhar a condição do `else` de `listar_aeronaves` à mesma lista de status de origem usada em `panes.service.sincronizar_status_aeronave` — ou, melhor, eliminar a duplicação chamando a função canônica para cada aeronave listada (ver também RISCO-03 sobre o efeito colateral de mutação dentro de um GET).
- **Risco de regressão:** BAIXO — torna a correção mais abrangente, não mais restritiva.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO como efeito da correção do RISCO-03 (decisão do desenvolvedor: mover a correção para os pontos de mutação real, não reimplementar a regra de novo em `listar_aeronaves`). A lógica duplicada e incompleta foi removida por inteiro — `listar_aeronaves` passou a ser leitura pura, eliminando a superfície onde o BUG-02 vivia.

---

### [RISCO-03] `listar_aeronaves` grava no banco dentro de um endpoint de listagem (GET)

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/aeronaves/service.py:38-68`, `app/modules/aeronaves/router.py:22-35`
- **Eixo:** Concorrência / Arquitetura
- **Problema:** `GET /aeronaves/` (verbo semanticamente seguro/idempotente) executa, a cada chamada, duas queries adicionais e potencialmente `db.add()`/`await db.flush()` sobre uma ou mais aeronaves (`service.py:64-68`) para "corrigir" o status em memória antes de devolver a lista.
- **Consequência:** viola a expectativa de que um `GET` não tem efeito colateral — um proxy, cache de navegador, ou qualquer prefetch de tela pode disparar escritas não intencionais no banco. Sob uso concorrente (duas abas abrindo a tela de frota ao mesmo tempo), múltiplas requisições `GET` podem competir para escrever a mesma correção de status na mesma aeronave, sem necessidade real de fazer isso numa rota de leitura. Também não há rate limit nesse endpoint (consistente com o achado transversal do mapa §7.5), então cada refresh da tela de frota paga o custo de escrita.
- **Correção proposta:** mover a responsabilidade de correção de status para os pontos de mutação real (abertura/conclusão de pane e inspeção, que já chamam `sincronizar_status_aeronave`), e fazer `listar_aeronaves` apenas **ler** o estado — se for necessário exibir o status "correto" independente do que está persistido, calcular isso apenas para a resposta, sem `db.add`/`flush`.
- **Risco de regressão:** MÉDIO — depende de garantir que todos os pontos de mutação reais (panes, inspeções) já cobrem os casos que hoje são "corrigidos" apenas na listagem.
- **Precisa de teste antes?** SIM
- **Resposta do desenvolvedor:** mover para os pontos de mutação real — confirmado por leitura de código que `criar_pane`/`concluir_pane`/`cancelar_pane` e `concluir_inspecao`/`cancelar_inspecao` já chamam `sincronizar_status_aeronave` em todos os pontos reais de mutação; o BUG-01 (única forma de criar um status órfão sem passar por esses pontos) também foi fechado nesta mesma sessão.
- **Status:** ✅ CORRIGIDO. `listar_aeronaves` não faz mais `db.add`/`await db.flush()` — apenas lê. Testes: `test_listar_aeronaves_nao_grava_no_banco` (conta INSERT/UPDATE emitidos durante a chamada — zero esperado), `test_listar_aeronaves_nao_corrige_status_orfao_silenciosamente`. Os dois testes pré-existentes que verificavam sincronização via listagem (`test_status_aeronave_atualiza_para_indisponivel_ao_abrir_pane`, `test_status_aeronave_permanece_inspecao_quando_pane_aberta`) continuam passando sem alteração — a sincronização já havia acontecido no `POST /panes/`, antes do `GET`.

---

### [RISCO-04] `criar_aeronave`/`atualizar_aeronave` sem tratamento de `IntegrityError` na corrida de unicidade

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/aeronaves/service.py:105-122,145-157`
- **Eixo:** Concorrência / Banco
- **Problema:** tanto `criar_aeronave` quanto `atualizar_aeronave` verificam unicidade de `matricula`/`serial_number` com uma consulta prévia (`service.py:111,115-117,145-152`) e só depois inserem/atualizam — clássico TOCTOU. A constraint `unique=True` no banco (`models.py:46-59`) é a rede de segurança real contra a corrida, mas, diferente do padrão já adotado em `auth.service.criar_usuario` (SAVEPOINT + `except IntegrityError`) e `panes.service.criar_pane`/`adicionar_responsavel` (mesmo padrão), aqui **não existe nenhum `try/except IntegrityError`** ao redor do `await db.flush()`.
- **Consequência:** duas requisições concorrentes cadastrando a mesma matrícula/serial passam ambas na checagem prévia; a segunda a fazer `flush()` recebe um `IntegrityError` cru, não capturado, que sobe até o handler genérico de exceções (`app/shared/core/exceptions.py:91-97`) e retorna **500 Erro interno do servidor** — em vez do 409 Conflict que o usuário veria no caso não concorrente.
- **Correção proposta:** envolver o `db.add(aeronave)` + `flush()` (e o `flush()` de `atualizar_aeronave` quando `matricula`/`serial_number` mudam) em `async with db.begin_nested(): ...` com `except IntegrityError`, convertendo para a mesma exceção de negócio (`ValueError`, ou migrando para `domain_exc.ConflitoNegocioError`, ver MELHORIA-07) já usada no caminho não concorrente.
- **Risco de regressão:** BAIXO — replica um padrão já validado em outros dois módulos do mesmo projeto.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. `db.add(aeronave)`/`flush()` em `criar_aeronave` e o `flush()` de `atualizar_aeronave` envolvidos em `async with db.begin_nested(): ... except IntegrityError`, convertendo para `domain_exc.ConflitoNegocioError` (já migrado direto para a exceção tipada, ver MELHORIA-07). Testes: `test_criar_aeronave_savepoint_absorve_integrity_error_sem_derrubar_sessao`, `test_atualizar_aeronave_savepoint_absorve_integrity_error_sem_derrubar_sessao`.

---

### [RISCO-05] `alternar_status_aeronave` (toggle) perde o subtipo original de status ao reativar

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/aeronaves/service.py:73-102`
- **Eixo:** Contrato
- **Problema:** a docstring diz "Alterna entre OPERACIONAL e INATIVA" (`service.py:77`), mas a implementação real (`service.py:85-99`) trata qualquer status diferente de `INATIVA`/`INSPECAO` (isto é, `DISPONIVEL`, `OPERACIONAL` **e** `ESTOCADA`) como "ativo" e o move para `INATIVA`; ao reverter, sempre grava `DISPONIVEL` (`service.py:86`), nunca o status original. Confirmado por `tests/unit/test_aeronaves.py:257-268` (`test_reativar_aeronave`): uma aeronave recém-criada com status `DISPONIVEL` (default), ao ser desativada e reativada via toggle duas vezes, retorna a `DISPONIVEL` — o teste não exercita o caso de uma aeronave `ESTOCADA` ou `OPERACIONAL` sendo desativada e reativada.
- **Consequência:** uma aeronave marcada como `ESTOCADA` (guardada, fora de operação por outro motivo) que seja desativada e depois reativada pelo mesmo endpoint perde essa informação permanentemente e passa a aparecer como `DISPONIVEL` — sem nenhum teste cobrindo (ou documentando como intencional) essa perda.
- **Correção proposta:** decidir se o comportamento é intencional (documentar e corrigir a docstring) ou se o toggle deveria preservar/registrar o status anterior antes de inativar, para restaurá-lo corretamente ao reativar.
- **Risco de regressão:** MÉDIO — mudar o comportamento de reativação pode afetar expectativas já em uso na tela de frota.
- **Precisa de teste antes?** SIM
- **Resposta do desenvolvedor:** preservar o status anterior.
- **Status:** ✅ CORRIGIDO. Nova coluna `aeronaves.status_anterior_inativacao` (migration `a6b7c8d9e0f1`, nullable) guarda o status no momento da inativação; `alternar_status_aeronave` restaura esse valor ao reativar (ou `DISPONIVEL` se não houver nada salvo — ex.: dados pré-existentes à migration). Docstring do serviço atualizada para descrever o comportamento real. Testes: `test_toggle_status_preserva_estocada_ao_reativar`, `test_toggle_status_disponivel_permanece_disponivel_ao_reativar`.

---

### [MELHORIA-06] Código morto: `desativar_aeronave`/`reativar_aeronave` e import não usado

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/aeronaves/service.py:160-181`, `app/modules/aeronaves/router.py:11`
- **Eixo:** Manutenibilidade
- **Problema:** `desativar_aeronave` e `reativar_aeronave` (`service.py:160-181`) não são chamados por nenhum router, teste ou outro módulo (`grep` confirma zero chamadas fora da própria definição) — a funcionalidade equivalente é exposta via `POST /{id}/toggle-status` → `alternar_status_aeronave`. Em `router.py:11`, o import `EncarregadoInspetorOuAdmin` também não é usado em nenhuma assinatura do arquivo.
- **Consequência:** nenhuma em runtime; custo de manutenção — as duas funções soft-delete/restore parecem ser a API pública do módulo, mas na prática nenhum cliente as alcança, o que pode confundir quem for dar manutenção ao módulo.
- **Correção proposta:** remover as duas funções e o import não utilizado, ou — se fizerem parte de uma API planejada mas ainda não exposta — expor as rotas correspondentes ou adicionar um comentário explicando por que existem sem uso.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO. `desativar_aeronave`/`reativar_aeronave` removidas (`service.py` foi reescrito por completo nesta sessão); import `EncarregadoInspetorOuAdmin` removido de `router.py`.

---

### [MELHORIA-07] `service.py` só usa `ValueError` cru — nenhuma exceção de domínio tipada

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/aeronaves/service.py` (todo o arquivo)
- **Eixo:** Arquitetura (mapa §5)
- **Problema:** as 12 ocorrências de erro do módulo são todas `raise ValueError(...)`; nenhuma usa `app.shared.core.exceptions` (`domain_exc`). Em compensação, o router faz *string-matching* em português para decidir o status HTTP — `"não encontrada" in detail.lower()` (`router.py:94-98,118-124`) — exatamente o padrão já registrado como achado transversal no mapa arquitetural (§5, "Tradução de erro no router").
- **Consequência:** hoje o *string-matching* felizmente acerta o status correto para todas as mensagens atuais (confirmado lendo cada uma), mas quebra silenciosamente assim que qualquer mensagem de erro for reescrita (ex.: trocar "não encontrada" por "não localizada" faz um 404 virar 409 sem nenhum teste de tipo pegar isso em tempo de build).
- **Correção proposta:** migrar `service.py` para `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError`, eliminando o *string-matching* do router — mesma direção já recomendada para `panes` em `docs/backlog/revisor/concluido/achados_panes.md` (MELHORIA-13 — corrigido).
- **Risco de regressão:** MÉDIO — muda o tipo de exceção propagada; os `except ValueError` do router (`router.py:52,89,115`) precisam ser ajustados junto.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO. As 12 ocorrências de `ValueError` migradas para `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError`; os três blocos `except ValueError` com *string-matching* removidos do router (as exceções de domínio já carregam o status HTTP e propagam direto para o handler global, mesmo padrão dos demais módulos revisados nesta rodada). Coberto pelos testes existentes de 404/409 (`test_criar_aeronave_matricula_duplicada`, `test_alternar_status_aeronave_sob_inspecao_ativa_rejeitado`) e pelos novos testes desta sessão.

---

## Resumo

- Total de achados: 7
- BUG: 2 (CRÍTICA: 0, ALTA: 1, MÉDIA: 1, BAIXA: 0)
- RISCO: 3 (MÉDIA: 2, BAIXA: 1)
- MELHORIA: 2 (todas BAIXA)
- DÚVIDA: 0
- **Corrigidos: 7/7**

## Arquivos revisados

- `app/modules/aeronaves/router.py` (integral, 128 linhas)
- `app/modules/aeronaves/service.py` (integral, 181 linhas)
- `app/modules/aeronaves/models.py` (integral, 124 linhas)
- `app/modules/aeronaves/schemas.py` (integral, 62 linhas)
- `app/modules/aeronaves/__init__.py`
- `app/shared/core/enums.py` (para confirmar os 6 valores de `StatusAeronave`)
- `tests/unit/test_aeronaves.py` (integral, 411 linhas)
- Trecho de `app/modules/dashboard/service.py` (só para confirmar acoplamento cross-module já mapeado)

## Não revisado / limitações

- **`panes.service.sincronizar_status_aeronave`** e a lógica de inspeções (`inspecoes.service.STATUS_ATIVOS`) foram lidos apenas o suficiente para comparar com a reimplementação local em `listar_aeronaves` (BUG-02) — a revisão de fundo desses dois módulos fica para suas próprias sessões (`inspecoes` ainda não revisado).
- **RBAC do módulo** (`AdminRequired` para criar/atualizar, `EncarregadoOuAdmin` para toggle, `CurrentUser` para listar/buscar): verificado como internamente consistente, sem achado.
- **Paginação em `GET /aeronaves/`**: já implementada (`skip`/`limit`), diferente de `auth.listar_usuarios` (achado 22 em `docs/backlog/revisor/concluido/achados_auth.md` — corrigido) — não é achado aqui.
- **Cobertura de testes**: boa para o caminho feliz e para os cenários de sincronização com pane/inspeção real (411 linhas, ~17 testes). **Lacunas identificadas**: nenhum teste cria aeronave já com `status=INSPECAO` (BUG-01); nenhum teste verifica a listagem quando o status fica órfão sem pane nem inspeção (BUG-02); nenhum teste cobre concorrência na criação/atualização (RISCO-04); nenhum teste desativa/reativa uma aeronave que não estava em `DISPONIVEL` originalmente (RISCO-05).

## Perguntas para o desenvolvedor (respondidas)

- O toggle de status (RISCO-05) deveria preservar o status anterior à desativação (ex.: uma aeronave `ESTOCADA` volta a `ESTOCADA`, não a `DISPONIVEL`), ou `DISPONIVEL` é sempre o destino correto de reativação por design? **Resposta: preservar o status anterior.**
- A mutação de status dentro de `GET /aeronaves/` (RISCO-03) é uma escolha deliberada para simplificar a UI (a tela de frota sempre reflete o estado "corrigido" sem precisar de um job separado), ou pode ser movida para os pontos de mutação real sem perda de funcionalidade? **Resposta: mover para os pontos de mutação real.**
