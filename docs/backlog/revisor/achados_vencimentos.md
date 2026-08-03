# Achados de Revisão — Módulo `vencimentos`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão.

---

### [BUG-01] A Matriz de Vencimentos esconde silenciosamente equipamentos que compartilham o mesmo Part Number no mesmo avião

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/vencimentos/service.py:298-442`
- **Eixo:** Contrato
- **Problema:** `montar_matriz_vencimentos` itera `for modelo in modelos` — o conjunto de PNs (`ModeloEquipamento`) que têm regra de periodicidade cadastrada — e monta um mapa de instalações ativas com `inst_map[inst.aeronave_id][slot_modelo_id] = inst` (`service.py:350-358`). Essa chave é `(aeronave_id, modelo_id)`, **não** `(aeronave_id, slot_id)`. Quando uma aeronave tem mais de um slot físico configurado com o mesmo PN, cada `Instalacao` processada nesse loop sobrescreve a anterior no dicionário — a linha da matriz para aquele PN mostra apenas **uma** das instalações, escolhida pela ordem (não determinística, sem `ORDER BY` na query de `service.py:332-347`) em que o banco devolve as linhas.

  Confirmado contra os dados reais de produção em `scripts/seed/seed_slots.py:10-51`:
  - `MDP1`/`MDP2` compartilham o PN `MA902B-01` (linhas 18-19)
  - `CMFD1`/`CMFD2`/`CMFD3`/`CMFD4` — **4 slots** — compartilham o PN `MB387B-01` (linhas 30-31, 42-43)
  - `AMPMIC-1P`/`AMPMIC-2P` compartilham `263-000` (linhas 26, 40)
  - `ASP-1P`/`ASP-2P` compartilham `343-001` (linhas 32, 44)
  - `STICKGRIP-1P`/`STICKGRIP-2P` compartilham `733-0402` (linhas 36, 45)

  Ou seja, 5 dos ~31 slots definidos na frota real compartilham PN com pelo menos um outro slot — não é um caso extremo hipotético, é o desenho normal da aeronave (múltiplos displays/microfones idênticos em posições diferentes). O caso mais grave é o dos 4 `CMFD`: a matriz perde 3 de 4 displays.

  O schema de resposta `SlotMatrizOut` (`schemas.py:92-99`) tem campos `slot_id`/`nome_posicao` — sugerindo que a intenção original era identificar o slot físico — mas o dicionário de resposta (`service.py:422-427`) nunca os preenche; o frontend (`app/web/static/js/vencimentos.js:199,252,344,390,433`) também nunca lê `slot_id`, agrupando tudo por `sistema` (o nome genérico do PN). Confirma-se assim que não existe, hoje, nenhum caminho — nem no backend, nem no frontend — para o usuário ver o segundo, terceiro ou quarto equipamento do mesmo tipo instalado na mesma aeronave.

  **Nenhum teste** no repositório cria dois slots com o mesmo `modelo_id` na mesma aeronave e verifica o conteúdo da matriz (confirmado em `tests/unit/test_vencimentos_criticos.py` e nos testes de matriz em `tests/unit/test_equipamentos.py:388-410`) — o cenário nunca foi exercitado, apesar de ser o mais comum da frota real.
- **Consequência:** o dashboard central de conformidade de manutenção da frota — a própria razão de existir deste módulo — omite, de forma sistemática e silenciosa, o status de vencimento de equipamentos reais instalados, incluindo se estão `VENCIDO`. Um controle vencido em `CMFD2`, `CMFD3` ou `CMFD4` pode nunca aparecer na matriz enquanto `CMFD1` estiver `OK`, dependendo apenas da ordem de retorno da query.
- **Correção proposta:** decidir a granularidade correta com o desenvolvedor (ver seção de perguntas) — provavelmente expandir a matriz para uma linha por slot físico (`slot_id`) em vez de por PN, já que o schema de resposta já tem os campos para isso; alternativamente, se o agrupamento por PN for intencional, agregar explicitamente o pior status entre todos os slots do mesmo PN, em vez de escolher um arbitrariamente.
- **Risco de regressão:** ALTO — muda a estrutura da resposta consumida pelo frontend; qualquer mudança de granularidade exige atualizar `vencimentos.js` também.
- **Precisa de teste antes?** SIM

---

### [BUG-02] `PUT /vencimentos/tipos-controle/{tipo_id}` devolve 409 em vez de 404 quando o ID não existe

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/vencimentos/service.py:73-77`, `app/modules/vencimentos/router.py:54-58`
- **Eixo:** Contrato
- **Problema:** `atualizar_tipo_controle` levanta `ValueError("Tipo de controle não encontrado.")` quando o `tipo_id` não existe (`service.py:76-77`), mas o router captura **todo** `ValueError` da função e mapeia uniformemente para `HTTP_409_CONFLICT` (`router.py:54-58`), sem distinguir "não encontrado" (404) de "nome duplicado" (409, o outro `ValueError` possível na mesma função, `service.py:83-84`).
- **Consequência:** o cliente recebe 409 Conflict para um recurso que simplesmente não existe. Vale notar que o próprio módulo já corrigiu exatamente essa classe de bug em `prorrogar_vencimento` — existe um teste de regressão dedicado, `test_prorrogar_vencimento_inexistente_levanta_404_nao_500` (`tests/unit/test_vencimentos_criticos.py:80-93`), cujo docstring documenta que a versão anterior levantava um `domain_exc.NotFoundError` inexistente (`AttributeError` → 500) e foi corrigida para `EntidadeNaoEncontradaError` (404) — mas a mesma limpeza não foi replicada em `atualizar_tipo_controle`, que continua no dialeto antigo (`ValueError` cru, sem distinção de status).
- **Correção proposta:** migrar `atualizar_tipo_controle` (e `criar_tipo_controle`, por consistência) para `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError`, no mesmo padrão já usado em `registrar_execucao` e `prorrogar_vencimento`.
- **Risco de regressão:** BAIXO — corrige o status HTTP para o caso correto; nenhum cliente legítimo depende do 409 incorreto.
- **Precisa de teste antes?** SIM

---

### [RISCO-03] Nenhuma proteção contra duas prorrogações simultaneamente ativas para o mesmo controle

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/vencimentos/service.py:444-485`, `app/modules/vencimentos/models.py:88-108`
- **Eixo:** Concorrência / Banco
- **Problema:** `prorrogar_vencimento` desativa prorrogações ativas do controle com um `UPDATE` cru (`service.py:454-463`) e, em seguida, insere uma nova `ProrrogacaoVencimento` com `ativo=True` (`service.py:470-483`) — sem nenhuma transação/lock cobrindo as duas operações como uma unidade atômica, e sem nenhuma `UniqueConstraint`/índice parcial no banco garantindo "no máximo uma prorrogação ativa por `controle_id`" (`models.py:88-108` não declara nenhuma). Contraste com o restante do módulo: `TipoControle.nome` e `EquipamentoControle` (`uq_equip_controle`) têm `UniqueConstraint` + `SAVEPOINT`/`except IntegrityError` como rede de segurança contra corrida — este é o único ponto do módulo sem essa proteção.
- **Consequência:** duas chamadas concorrentes de `POST /{vencimento_id}/prorrogar` para o mesmo vencimento (dois usuários, ou um clique duplo) podem ambas ler "nenhuma prorrogação ativa a desativar" antes de qualquer commit, e ambas inserir uma nova prorrogação `ativo=True` — deixando duas prorrogações simultaneamente ativas para o mesmo controle. `montar_matriz_vencimentos` então escolhe uma arbitrariamente com `next(p for p in venc.prorrogacoes if p.ativo)` (`service.py:395`), exibindo uma data de vencimento/documento de prorrogação que pode não ser a mais recente. É a mesma classe de lacuna já registrada para `Instalacao` (uma instalação ativa por slot) em `docs/backlog/revisor/achados_equipamentos.md` (RISCO-05).
- **Correção proposta:** adicionar um índice único parcial (`CREATE UNIQUE INDEX ... ON prorrogacoes_vencimento(controle_id) WHERE ativo = 1`) e envolver a criação da nova prorrogação em `SAVEPOINT`/`except IntegrityError`, no mesmo padrão do resto do módulo.
- **Risco de regressão:** MÉDIO — requer migration; validar que nenhum dado existente já viola a invariante antes de aplicar a constraint.
- **Precisa de teste antes?** SIM

---

### [MELHORIA-04] `except IntegrityError` de `associar_controle_a_equipamento` sempre reporta "já associado", mesmo quando a causa real é outra

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/vencimentos/service.py:130-145`
- **Eixo:** Tratamento de erros
- **Problema:** ao criar uma nova associação `EquipamentoControle`, o bloco `except IntegrityError` (`service.py:140-145`) captura qualquer violação de integridade no insert — incluindo uma violação de `ForeignKey` se `modelo_id` ou `tipo_controle_id` não existirem (nenhum dos dois é validado antes do insert) — e sempre devolve a mesma mensagem "Este tipo de controle já está associado a este equipamento.", que corresponde apenas à violação da `UniqueConstraint` `uq_equip_controle`.
- **Consequência:** um cliente que envie um `modelo_id` ou `tipo_controle_id` inexistente recebe 409 "já associado" (mensagem enganosa) em vez de 404 "PN ou tipo de controle não encontrado" — o erro real fica mascarado.
- **Correção proposta:** validar a existência de `modelo_id` e `tipo_controle_id` antes do insert, levantando `domain_exc.EntidadeNaoEncontradaError` especificamente para esses casos, deixando o `except IntegrityError` apenas para a violação de unicidade genuína.
- **Risco de regressão:** BAIXO — restrito a endpoint ADMIN.
- **Precisa de teste antes?** NÃO

---

### [MELHORIA-05] Duas rotas de "remoção" retornam sucesso silencioso para recurso inexistente

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/vencimentos/service.py:220-232,487-503`
- **Eixo:** Contrato
- **Problema:** `remover_controle_de_equipamento` (`service.py:220-232`) e `cancelar_prorrogacao` (`service.py:487-503`) não levantam nenhuma exceção quando o registro-alvo não existe — a primeira simplesmente não faz nada (`if assoc: ...`, sem `else`), a segunda retorna `False` (via `rowcount > 0`). Os respectivos handlers (`router.py:97-108,163-173`) devolvem 200 (`{"success": True, "message": "Regra removida"}` incondicionalmente na primeira; `{"success": sucesso}` na segunda) mesmo quando nada foi de fato alterado.
- **Consequência:** inconsistente com o padrão 404 usado no restante do módulo (`registrar_execucao`, `prorrogar_vencimento`, e — depois do BUG-02 corrigido — `atualizar_tipo_controle`) para operações sobre um ID inexistente. Um `modelo_id`/`tipo_controle_id` ou `vencimento_id` errado (typo, dado obsoleto na UI) passa despercebido como "sucesso".
- **Correção proposta:** decidir se o comportamento idempotente (200/204 mesmo sem alteração real) é intencional; se não for, levantar `domain_exc.EntidadeNaoEncontradaError` nos dois casos, alinhando com o restante do módulo.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO

---

### [MELHORIA-06] `registrar_execucao` não valida que a data de execução não está no futuro

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/vencimentos/service.py:234-288`, `app/modules/vencimentos/schemas.py:59-61`
- **Eixo:** Validação
- **Problema:** `ControleVencimentoUpdate.data_ultima_exec` (`schemas.py:60`) é um `date` sem nenhuma restrição de intervalo, e `registrar_execucao` grava esse valor diretamente (`service.py:260`) sem checar se está no futuro.
- **Consequência:** um erro de digitação na data de execução (ex.: ano trocado) empurra `data_vencimento` para o futuro sem nenhuma checagem, fazendo um controle que deveria estar `VENCIDO`/`VENCENDO` aparecer como `OK` na matriz até alguém notar manualmente a inconsistência.
- **Correção proposta:** adicionar validação (no schema, via `field_validator`, ou no service) rejeitando `data_ultima_exec > date.today()`.
- **Risco de regressão:** BAIXO — hoje nada depende de aceitar datas futuras.
- **Precisa de teste antes?** NÃO

---

### [MELHORIA-07] Lógica de "desativar prorrogações ativas" duplicada três vezes

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/vencimentos/service.py:264-275,454-465,488-501`
- **Eixo:** Arquitetura (anti-padrão §7.5 do `revisor.md`, "reimplementação de algo que já existe")
- **Problema:** o par `UPDATE ProrrogacaoVencimento SET ativo=False WHERE controle_id=X AND ativo=True` seguido de `db.expire(vencimento, ["prorrogacoes"])` (com o mesmo comentário "Bug 147: Sincronizar cache da sessão") aparece de forma quase idêntica em `registrar_execucao`, `prorrogar_vencimento` e `cancelar_prorrogacao`.
- **Consequência:** nenhuma funcional hoje; três cópias da mesma lógica aumentam o custo de manutenção — uma correção futura (ex.: junto com RISCO-03, ao adicionar SAVEPOINT) precisaria ser replicada nos três lugares.
- **Correção proposta:** extrair um helper único (ex. `_desativar_prorrogacoes_ativas(db, controle_id)`) usado pelos três pontos.
- **Risco de regressão:** BAIXO — refatoração mecânica.
- **Precisa de teste antes?** NÃO

---

## Resumo

- Total de achados: 7
- BUG: 2 (CRÍTICA: 0, ALTA: 1, MÉDIA: 1, BAIXA: 0)
- RISCO: 1 (MÉDIA: 1)
- MELHORIA: 4 (todas BAIXA)
- DÚVIDA: 0

## Arquivos revisados

- `app/modules/vencimentos/router.py` (integral, 180 linhas)
- `app/modules/vencimentos/service.py` (integral, 503 linhas)
- `app/modules/vencimentos/models.py` (integral, 108 linhas)
- `app/modules/vencimentos/schemas.py` (integral, 139 linhas)
- `scripts/seed/seed_slots.py` (integral — decisivo para confirmar o BUG-01 contra dados reais)
- `app/web/static/js/vencimentos.js` (trechos — para confirmar como o frontend consome a matriz)
- `app/modules/equipamentos/models.py` (trecho — para confirmar `SlotInventario`/`Instalacao`)
- `tests/unit/test_vencimentos_criticos.py` (integral, 150+ linhas lidas)
- `tests/unit/test_equipamentos.py` (trecho — testes de `/vencimentos/matriz`)
- Nomes de teste em `tests/unit/test_vencimentos_inspecoes_media_prioridade.py`

## Não revisado / limitações

- **Ausência de `__init__.py`**: já documentado no `00_mapa_arquitetural.md` §5 e §7 (item 8) como o único módulo de domínio sem esse arquivo. Não é um achado novo desta sessão — apenas confirmado como ainda presente.
- **`calcular_status_vencimento` / status derivado em tempo de leitura**: implementado corretamente e testado (`test_calcular_status_vencimento_puro`, `test_matriz_vencimentos_nao_fica_stale_com_status_persistido_desatualizado`, ambos em `tests/unit/test_vencimentos_criticos.py`). Verificado, não é achado.
- **SAVEPOINT + `IntegrityError`** em `criar_tipo_controle`, `atualizar_tipo_controle` (flush) e no caminho de criação de `associar_controle_a_equipamento`: implementado e coerente com o padrão do resto do projeto (exceto o ponto específico do RISCO-03).
- **RBAC entre os 9 endpoints**: consistente — `AdminRequired` para catálogo/regras de periodicidade, `ExecucaoPermitida` (MANTENEDOR/ENCARREGADO/ADMINISTRADOR) para registrar execução, `EncarregadoInspetorOuAdmin` para prorrogação (decisão de "Engenharia", corretamente mais restrita). Sem achado.
- **`criar_controles_para_item`**: ponto de entrada usado por `equipamentos.service` (já visto na revisão anterior) — revisado aqui apenas para confirmar que todo controle nasce `VENCIDO` sem `data_vencimento`, comportamento coerente com `calcular_status_vencimento`.
- **Cobertura de testes**: boa para o recálculo de periodicidade, status derivado em tempo de leitura, e o bug já corrigido de `prorrogar_vencimento` inexistente. **Lacuna central identificada**: nenhum teste cria dois slots com o mesmo `modelo_id` na mesma aeronave para verificar o comportamento da matriz — por isso o BUG-01 nunca foi detectado, apesar de ser o cenário mais comum da frota real segundo o próprio script de seed de produção.
- **Dependência com `equipamentos.models` (`ModeloEquipamento`, `ItemEquipamento`, `Instalacao`)**: lida apenas o suficiente para entender o fluxo da matriz; a revisão de fundo de `equipamentos` já foi feita em sessão anterior (`achados_equipamentos.md`).

## Perguntas para o desenvolvedor

- A granularidade da Matriz de Vencimentos (BUG-01) deveria ser por slot físico (`slot_id`) em vez de por PN (`modelo_id`) — cada `CMFD1`..`CMFD4` como uma linha própria — ou o agrupamento por PN é intencional, e a correção correta é agregar o pior status entre todos os slots do mesmo PN em vez de escolher um arbitrariamente?
- A base semeada por `scripts/seed/seed_slots.py` reflete a configuração real da frota em produção hoje (ou seja, o BUG-01 já está afetando dados reais agora), ou é apenas um script de desenvolvimento/demonstração?
- O comportamento "sucesso silencioso" de `remover_controle_de_equipamento`/`cancelar_prorrogacao` para IDs inexistentes (MELHORIA-05) é uma escolha deliberada de idempotência, ou deveria retornar 404 como o restante do módulo?
