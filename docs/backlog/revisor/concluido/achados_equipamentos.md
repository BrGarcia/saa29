# Achados de Revisão — Módulo `equipamentos`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 03/08/2026
> 9/9 achados corrigidos, 0 parciais, 0 não corrigidos. As 3 perguntas ao desenvolvedor
> (MELHORIA-08, RISCO-02, MELHORIA-06) foram respondidas antes da implementação — ver decisões
> inline em cada achado. Commit `55eda8b`. Suite completa: 377 testes, 0 falhas. `xlsx_service.py`
> não tinha nenhum teste no repositório antes desta sessão — cobertura nova em
> `tests/unit/test_equipamentos_xlsx.py`. Status por item marcado inline em cada achado abaixo
> (campo `**Status:**`).

---

### [BUG-01] `POST /inventario/ajuste` confia no `usuario_id` enviado pelo cliente — trilha de auditoria falsificável

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/equipamentos/router.py:258-281`, `app/modules/equipamentos/schemas.py:126-148`
- **Eixo:** Segurança
- **Problema:** o handler `ajustar_inventario` recebe `dados: schemas.AjusteInventarioCreate` e passa direto para o service, sem nunca capturar o usuário autenticado — a dependência de RBAC é vinculada a `_: EncarregadoOuAdmin` (descartada, `router.py:266`), então não há nenhuma variável com o usuário logado disponível no handler. `AjusteInventarioCreate.usuario_id` (`schemas.py:132`) é um campo comum do payload, preenchível livremente pelo cliente. Esse valor é gravado como `Instalacao.usuario_id` (`service.py:609-618`, via `_efetivar_troca_no_slot`) — o campo que a tela de histórico usa para mostrar "quem fez a alteração" (`usuario_trigrama` em `listar_historico_recente` e `listar_inventario_aeronave`). Compare com os outros dois endpoints que gravam o mesmo tipo de evento — `instalar_item` (`router.py:153-162`) e `remover_item` (`router.py:170-179`) — que corretamente usam `current_user.id`, nunca um valor vindo do payload.
- **Consequência:** qualquer usuário com papel ENCARREGADO ou ADMINISTRADOR pode, através de `POST /inventario/ajuste`, atribuir uma alteração de inventário a **qualquer outro usuário do sistema** (ou deixar `usuario_id=null`), bastando informar um UUID diferente do seu próprio no corpo da requisição. A trilha de auditoria do módulo (a única razão de existir do campo `usuario_id`/`usuario_trigrama` no histórico) é forjável por design, não por um bug de digitação.
- **Correção proposta:** trocar `_: EncarregadoOuAdmin` por `current_user: EncarregadoOuAdmin` e usar `current_user.id` ao construir a instalação em `ajustar_inventario_item`, ignorando (ou removendo do schema) o `usuario_id` vindo do cliente — no mesmo padrão já usado por `instalar_item`/`remover_item` e pelos dois fluxos de XLSX (que corretamente passam `current_user.id` do router para o service, `router.py:322-323,364-366`).
- **Risco de regressão:** BAIXO — remove uma capacidade que nunca deveria ter existido; nenhum cliente legítimo depende de forjar o autor da alteração.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. `ajustar_inventario_item` passa a receber `usuario_id` como parâmetro do service (sempre `current_user.id` do router), e o campo `usuario_id` foi removido de `AjusteInventarioCreate`. Teste: `test_ajuste_ignora_usuario_id_forjado_no_payload` (tests/unit/test_inventario.py) — cria um "atacante" autenticado que tenta forjar a autoria em nome de outro usuário e confirma que o histórico registra sempre quem autenticou a requisição.

---

### [RISCO-02] Upload de XLSX identifica a aeronave pelo nome do arquivo, sem vínculo verificado entre prévia e confirmação

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/equipamentos/xlsx_service.py:52-77,205-239`, `app/modules/equipamentos/router.py:309-333`
- **Eixo:** Contrato / Segurança
- **Problema:** `obter_previa_xlsx_inventario` deriva a aeronave-alvo inteiramente do **nome do arquivo enviado pelo cliente** (`nome_base = os.path.splitext(filename)[0]`, `xlsx_service.py:63-70`) — não há nenhum outro parâmetro no fluxo de prévia que informe qual aeronave o usuário pretende atualizar. O passo seguinte, `POST /inventario/upload-xlsx/process` (`router.py:309-333`), recebe `XlsxProcessRequest.aeronave_id` (`schemas.py:192-194`) **diretamente do corpo da requisição de confirmação**, sem nenhuma verificação de que esse `aeronave_id` é o mesmo que a prévia anterior calculou a partir do nome do arquivo, nem de que os `slot_id`s confirmados pertencem de fato aos itens que foram exibidos na prévia daquela aeronave.
- **Consequência:** os dois passos (prévia e confirmação) não têm nenhum vínculo do lado do servidor — apenas a suposição de que o frontend vai reenviar fielmente o `aeronave_id` que a prévia retornou. Um cliente que envie `aeronave_id` diferente do previsto (por bug do frontend, uma aba com estado antigo, ou uma chamada manual à API) aplica as atribuições de S/N pensadas para uma aeronave em outra, sem qualquer aviso — `slots_inventario` não pertence a uma aeronave específica (é um catálogo global de posições), então nada no service rejeita a combinação. Sem nenhum teste no repositório cobrindo os endpoints de XLSX (ver seção de limitações), esse cenário nunca foi exercitado.
- **Correção proposta:** incluir na resposta da prévia um identificador de sessão (ou reenviar e validar o `aeronave_id` já resolvido pela prévia) e validar, no passo de confirmação, que o `aeronave_id` recebido é exatamente o que a prévia calculou para aquele arquivo — rejeitando a confirmação caso divirja.
- **Risco de regressão:** MÉDIO — muda o contrato entre prévia e confirmação; exige que o frontend realmente reenvie o valor correto.
- **Precisa de teste antes?** SIM
- **Resposta do desenvolvedor:** fechar a lacuna — não foi simplificação deliberada.
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. `obter_previa_xlsx_inventario` gera um `preview_token` JWT assinado (mesma chave/algoritmo já usados para tokens de auth, `app_secret_key`/`jwt_algorithm`, TTL de 15 min) contendo `aeronave_id` + os `slot_ids` que a prévia efetivamente incluiu. `processar_confirmacao_xlsx` exige e valida o token antes de aplicar qualquer alteração — rejeita (`ConflitoNegocioError`) se o token estiver ausente/expirado/adulterado, se a `aeronave_id` divergir, ou se algum slot confirmado não fizer parte da prévia original. `XlsxProcessRequest.preview_token` agora é campo obrigatório; frontend (`configuracoes.js`) atualizado para reenviar `previewData.preview_token`. Testes: `test_confirmacao_com_token_valido_sucede`, `test_confirmacao_com_aeronave_diferente_da_previa_e_rejeitada`, `test_confirmacao_com_slot_fora_da_previa_e_rejeitada`, `test_confirmacao_com_token_invalido_e_rejeitada`, `test_confirmacao_com_token_expirado_e_rejeitada`, `test_endpoint_process_sem_preview_token_retorna_422` (tests/unit/test_equipamentos_xlsx.py).

---

### [RISCO-03] Upload de XLSX sem limite de tamanho no endpoint de prévia; legado carrega o arquivo inteiro antes de checar tamanho

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/equipamentos/router.py:284-306,335-361`
- **Eixo:** Segurança
- **Problema:** `upload_inventario_xlsx_preview` (`router.py:284-306`) faz `content = await file.read()` sem **nenhum** limite de tamanho — diferente de todo upload em `panes`, que usa `ler_upload_com_limite` para rejeitar antes de materializar o arquivo inteiro em memória. O endpoint legado `upload_inventario_xlsx` (`router.py:335-361`) tem uma checagem (`len(content) > 5*1024*1024`), mas ela roda **depois** de `content = await file.read()` já ter carregado o arquivo inteiro — o mesmo anti-padrão que já foi corrigido em `panes` (item #4 documentado em `docs/backlog/revisor/concluido/achados_panes.md`, RISCO herdado do relatório anterior de panes).
- **Consequência:** qualquer usuário com papel ENCARREGADO/ADMINISTRADOR pode enviar um arquivo arbitrariamente grande para `/preview` sem nenhuma rejeição por tamanho, consumindo memória do processo antes mesmo de `openpyxl.load_workbook` processar o conteúdo (que também é intensivo em memória para planilhas grandes/malformadas). O endpoint legado mitiga parcialmente, mas ainda paga o custo de materializar o arquivo inteiro antes de rejeitar.
- **Correção proposta:** aplicar `ler_upload_com_limite` (já existente em `app/shared/core/file_validators.py`) nos dois endpoints, com um teto de tamanho apropriado para planilhas de inventário.
- **Risco de regressão:** BAIXO — mesmo padrão já validado em produção no módulo `panes`.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. Aplicado `ler_upload_com_limite` (teto de 5 MB) no endpoint de prévia. O endpoint legado que tinha a checagem tardia foi removido (ver MELHORIA-08), então o risco desaparece por completo — sobra um único caminho de upload, já protegido. Teste: `test_endpoint_preview_arquivo_grande_e_rejeitado` (tests/unit/test_equipamentos_xlsx.py).

---

### [MELHORIA-04] `criar_slot` deixa vazar erro de banco cru ao cliente

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/equipamentos/router.py:96-113`
- **Eixo:** Tratamento de erros
- **Problema:** o handler envolve a chamada ao service num `try/except Exception as e: raise HTTPException(400, detail=str(e))`. `service.criar_slot` (`service.py:257-262`) não valida se `modelo_id` existe nem se `nome_posicao` já está em uso antes de inserir — a única defesa é a `ForeignKey` do banco. Se `modelo_id` não existir, o `flush()` levanta `IntegrityError`, capturada pelo `except Exception` genérico do router, e `str(e)` — que para SQLAlchemy inclui a instrução SQL e os parâmetros da query, já que a engine não configura `hide_parameters` (`app/bootstrap/database.py:35-39`) — é devolvido como `detail` da resposta 400.
- **Consequência:** qualquer erro inesperado nesse endpoint (não só o de FK) devolve ao cliente uma mensagem potencialmente contendo SQL interno e valores de parâmetros — exposição de detalhe técnico interno (checklist D). O comentário no topo de `router.py:17-19` afirma que "os endpoints... não têm try/except de tradução de erro" porque os services levantariam exceções de domínio — mas `criar_slot` não segue esse padrão, nem no service (nenhuma validação/exceção de domínio) nem no router (`except Exception` genérico, não um `except domain_exc.*`).
- **Correção proposta:** validar em `service.criar_slot` que `modelo_id` existe (levantando `domain_exc.EntidadeNaoEncontradaError`) antes do insert, e trocar o `except Exception` do router por um bloco que não vaze a mensagem crua de exceções não previstas — deixando-as propagar para o handler genérico (`app/shared/core/exceptions.py:91-97`), que já responde com uma mensagem genérica seguindo o padrão do resto do arquivo.
- **Risco de regressão:** BAIXO — restrito a um endpoint só acessível por ADMIN.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. `criar_slot` valida `modelo_id` via `db.get` antes do insert; `except Exception` genérico removido do router (a exceção de domínio propaga para o handler global). Testes: `test_criar_slot_modelo_inexistente_levanta_404_nao_400_cru`, `test_criar_slot_modelo_existente_sucede` (tests/unit/test_equipamentos_achados_revisor.py).

---

### [RISCO-05] Nenhuma restrição de unicidade concorrente para "uma instalação ativa por slot"

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/equipamentos/models.py:102-131`, `app/modules/equipamentos/service.py:469,514-521,621-642`
- **Eixo:** Concorrência / Banco
- **Problema:** a invariante "no máximo uma `Instalacao` ativa (`data_remocao IS NULL`) por slot" é garantida apenas por lógica de aplicação — `_obter_instalacao_ativa_no_slot` lê o estado atual antes de decidir se encerra e recria (`service.py:469,514-521`), e `instalar_item` faz o mesmo (`service.py:621-642`). Diferente de todas as outras invariantes de unicidade do módulo (PN em `ModeloEquipamento`, SN por PN em `ItemEquipamento` via `uq_item_sn_per_pn`) — que têm uma `UniqueConstraint` no banco como rede de segurança contra corrida, com `SAVEPOINT`/`except IntegrityError` no service (`service.py:74-85,206-217,546-558`) —, `Instalacao` não tem nenhuma constraint (nem um índice único parcial `WHERE data_remocao IS NULL`) impedindo duas instalações ativas simultâneas no mesmo slot.
- **Consequência:** duas chamadas concorrentes de `ajustar_inventario`/`instalar_item` no mesmo slot (dois usuários fazendo ajuste de inventário ao mesmo tempo, ou um clique duplo no frontend) podem ambas ler "nenhuma instalação ativa" (ou a mesma instalação ativa) e ambas inserir uma nova `Instalacao` sem remoção — deixando duas instalações "ativas" apontando para o mesmo slot físico, que é exatamente o tipo de corrupção de estado que o resto do módulo tem o cuidado de prevenir com constraint + SAVEPOINT.
- **Correção proposta:** adicionar um índice único parcial em SQLite (`CREATE UNIQUE INDEX ... ON instalacoes(slot_id) WHERE data_remocao IS NULL`) e envolver a criação da nova `Instalacao` em `SAVEPOINT`/`except IntegrityError`, no mesmo padrão já usado no restante do módulo.
- **Risco de regressão:** MÉDIO — requer migration; validar que nenhum dado existente já viola a invariante antes de aplicar a constraint.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `55eda8b`, com uma correção sobre o achado original. A constraint proposta (`UNIQUE` só em `slot_id`) estava **errada**: `SlotInventario` é uma posição compartilhada por toda a frota (ex.: "MDP1" existe uma vez no catálogo, mas cada aeronave tem sua própria `Instalacao` ativa apontando para o mesmo `slot_id`). Aplicar a constraint como escrita no achado bloquearia o funcionamento normal do sistema — confirmado contra `var/db`: agrupar só por `slot_id` reportava 33 "duplicatas" de até 22 instalações ativas cada, que eram simplesmente aeronaves diferentes com uma instalação ativa no mesmo slot (comportamento correto). A invariante real, confirmada em `_obter_instalacao_ativa_no_slot` (que sempre filtra por `slot_id` **e** `aeronave_id`), é por par — 0 violações agrupando dessa forma. Implementado: índice único parcial `uq_instalacao_ativa_por_slot_aeronave` em `(slot_id, aeronave_id)` + SAVEPOINT/`IntegrityError` em `ajustar_inventario_item` e `instalar_item`. Testes: `test_indice_unico_barra_duas_instalacoes_ativas_no_mesmo_slot_e_aeronave`, `test_mesmo_slot_aceita_instalacoes_ativas_em_aeronaves_diferentes`, `test_instalar_item_concorrente_no_mesmo_slot_levanta_conflito_de_dominio` (tests/unit/test_equipamentos_achados_revisor.py).

---

### [MELHORIA-06] `remover_modelo` não avisa sobre exclusão em cascata dos controles de vencimento vinculados ao PN

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/equipamentos/service.py:150-177`
- **Eixo:** Banco / Contrato
- **Problema:** `remover_modelo` verifica explicitamente se existem `ItemEquipamento` ou `SlotInventario` dependentes do PN antes de excluir, devolvendo uma mensagem amigável de conflito em cada caso (`service.py:162-174`). Não existe checagem equivalente para `EquipamentoControle` (o template de controles de vencimento vinculado ao PN, `vencimentos/models.py:38-58`) — cuja FK usa `ondelete="CASCADE"` (`vencimentos/models.py:50`). Como resultado, remover um PN que ainda não tem itens físicos mas já tem controles de vencimento configurados **não falha** — o banco silenciosamente apaga os registros de `EquipamentoControle` junto.
- **Consequência:** um administrador que configurou os controles de vencimento exigidos por um PN (mas ainda não cadastrou nenhum item físico) e depois exclui o PN por engano perde essa configuração sem nenhum aviso — diferente do padrão consistente usado para as outras duas dependências do mesmo PN.
- **Correção proposta:** adicionar a mesma checagem amigável para `EquipamentoControle` antes da exclusão (ou, se a intenção for permitir a exclusão em cascata deliberadamente, ao menos informar na resposta quantos templates de controle foram removidos junto).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Resposta do desenvolvedor:** bloquear a exclusão, no mesmo padrão já usado para itens físicos e slots.
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. `remover_modelo` agora verifica `EquipamentoControle` dependente e recusa (409) antes de excluir, na mesma sequência de checagens já usada para itens/slots. Testes: `test_remover_modelo_com_equipamento_controle_dependente_levanta_409`, `test_remover_modelo_sem_dependentes_sucede` (tests/unit/test_equipamentos_achados_revisor.py).

---

### [MELHORIA-07] `router.py:92` acessa o ORM diretamente, pulando o service (já mapeado no mapa arquitetural)

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/equipamentos/router.py:89-93`
- **Eixo:** Arquitetura (mapa §5 e §7, item "Acesso a banco fora do service")
- **Problema:** `listar_slots` faz `from sqlalchemy import select` e `db.execute(select(SlotInventario))` diretamente no handler, sem passar pelo service — já citado no `00_mapa_arquitetural.md` §5 como o único ponto de `equipamentos/router.py` que acessa o banco fora da camada de serviço. Confirmado nesta revisão: continua presente e é o único desvio desse tipo neste arquivo (todos os outros 17 endpoints do router chamam `service.*`).
- **Consequência:** nenhuma funcional; inconsistência de camadas que dificulta testar/mockar esse endpoint isoladamente do ORM.
- **Correção proposta:** mover a query para uma função em `service.py` (ex. `listar_slots`), seguindo o padrão do resto do arquivo.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. Query movida para `service.listar_slots(db)`; o router agora chama o service, como os outros 17 endpoints. Coberto indiretamente pelos testes existentes de `GET /equipamentos/slots/`.

---

### [MELHORIA-08] Dois caminhos paralelos para a mesma operação de upload de inventário

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/equipamentos/router.py:284-333,335-378`
- **Eixo:** Arquitetura
- **Problema:** o módulo mantém dois fluxos completos para a mesma funcionalidade (atualizar inventário via XLSX): o par prévia+confirmação (`/upload-xlsx/preview` + `/upload-xlsx/process`) e o endpoint legado de aplicação direta (`/upload-xlsx`, explicitamente rotulado "Legado/Direto" no summary, `router.py:337`). O legado reimplementa sua própria checagem de tamanho (RISCO-03) em vez de reusar qualquer validação centralizada, e é o único dos dois fluxos sem etapa de confirmação — herdando também o problema do RISCO-02 sem nenhuma chance de o usuário conferir a prévia antes de aplicar.
- **Consequência:** manutenção dobrada — uma correção (ex. limite de tamanho, RISCO-03) aplicada a um fluxo pode não ser replicada ao outro, como já aconteceu (o legado tem checagem de tamanho, a prévia não tem nenhuma).
- **Correção proposta:** confirmar com o desenvolvedor se o endpoint legado ainda é necessário (algum cliente/integração depende dele) ou se pode ser removido em favor do fluxo prévia+confirmação, reduzindo a superfície de manutenção.
- **Risco de regressão:** ALTO se removido sem confirmar dependência ativa — por isso é registrado como pergunta ao desenvolvedor, não como correção a aplicar diretamente.
- **Precisa de teste antes?** NÃO (decisão primeiro)
- **Resposta do desenvolvedor:** remover o legado — sem cliente/integração ativa dependente.
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. Confirmado por grep que o frontend (`configuracoes.js`) só chama `/preview` e `/process`; nenhuma referência a `/inventario/upload-xlsx` (legado) em nenhum lugar do código. Endpoint e a função `processar_xlsx_inventario` (única usuária) removidos. Teste: `test_endpoint_legado_upload_xlsx_removido` (tests/unit/test_equipamentos_xlsx.py) confirma que não há mais handler POST para o path.

---

### [MELHORIA-09] `except Exception` sem log nos três pontos de processamento de XLSX

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/equipamentos/xlsx_service.py:100-102,198-201,234-237`
- **Eixo:** Tratamento de erros
- **Problema:** os três blocos que processam o conteúdo do XLSX (`obter_previa_xlsx_inventario`, `processar_xlsx_inventario`, `processar_confirmacao_xlsx`) capturam `except Exception as e` e apenas anexam `str(e)` a uma lista de erros/detalhes retornada ao cliente com **status 200** — nenhum dos três loga a exceção (`logger.exception`/`logger.warning`).
- **Consequência:** falhas inesperadas de processamento (não só arquivo malformado, mas também bugs de código ou erros de banco durante `ajustar_inventario_item`) ficam visíveis apenas na resposta ao usuário, sem nenhum rastro nos logs do servidor para diagnóstico — e, como o handler devolve 200 mesmo quando `erros` não está vazio, um monitoramento de erros baseado em status HTTP não detectaria essas falhas.
- **Correção proposta:** adicionar `logger.exception(...)` em cada um dos três blocos antes de anexar a mensagem à resposta.
- **Risco de regressão:** BAIXO — é aditivo (log).
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `55eda8b`. `logger.exception(...)` adicionado nos dois blocos que restaram após a remoção do legado (MELHORIA-08): leitura do XLSX na prévia e aplicação de cada item na confirmação.

---

## Resumo

- Total de achados: 9
- BUG: 1 (CRÍTICA: 0, ALTA: 1, MÉDIA: 0, BAIXA: 0)
- RISCO: 3 (MÉDIA: 3)
- MELHORIA: 5 (MÉDIA: 1, BAIXA: 4)
- DÚVIDA: 0
- **Corrigidos: 9/9** (commit `55eda8b`)

## Arquivos revisados

- `app/modules/equipamentos/router.py` (integral, 378 linhas)
- `app/modules/equipamentos/service.py` (integral, 726 linhas)
- `app/modules/equipamentos/models.py` (integral, 131 linhas)
- `app/modules/equipamentos/schemas.py` (integral, 194 linhas)
- `app/modules/equipamentos/xlsx_service.py` (integral, 239 linhas)
- `app/modules/equipamentos/__init__.py`
- `app/modules/vencimentos/models.py` (trecho de `EquipamentoControle`, para confirmar o `ondelete=CASCADE` do MELHORIA-06)
- `app/bootstrap/database.py` (para confirmar ausência de `hide_parameters` no MELHORIA-04)
- `tests/unit/test_equipamentos.py`, `test_equipamentos_correcoes_urgentes.py`, `test_equipamentos_refatoracao.py`, `test_inventario.py` (nomes de teste, para mapear cobertura)

## Não revisado / limitações

- **Uso consistente de `domain_exc`**: diferente de `auth`, `panes` e `aeronaves`, este módulo usa quase inteiramente as exceções tipadas de `app.shared.core.exceptions` no service (única exceção: `criar_slot`, coberta no MELHORIA-04). Verificado como o padrão mais maduro entre os módulos revisados até agora — citado positivamente, não é achado.
- **N+1 queries em `listar_inventario_aeronave`**: a função é explicitamente desenhada (com comentário) para executar um número fixo de queries independente da quantidade de slots, usando window functions (`_mapear_aeronaves_anteriores`, `_mapear_ultimas_remocoes`) em vez de uma consulta por slot. Verificado e testado (`test_numero_de_queries_independe_da_quantidade_de_slots`). Correto, não é achado.
- **SAVEPOINT + `IntegrityError` para corridas de unicidade** em `criar_modelo`, `criar_item_com_heranca` e `_obter_ou_criar_item_por_pn`: implementado e testado (`test_criar_modelo_converte_integrity_error_em_conflito`, `test_get_or_create_recupera_item_criado_em_paralelo`). Correto — é o padrão que falta apenas em `Instalacao` (RISCO-05).
- **RBAC entre os 17 endpoints do router**: verificado como internamente consistente (ADMIN para mudanças de catálogo, ENCARREGADO/ADMIN para ajustes de inventário e XLSX, papéis operacionais para instalar/remover item físico) — sem o tipo de divergência já registrado para `panes` (RBAC imperativo) neste módulo.
- **`AjusteInventarioCreate._resolver_slot_id`** (compatibilidade com o campo legado `equipamento_id`): lido e compreendido, comportamento coberto por teste dedicado (`test_equipamento_id_legado_preenche_slot_id`, `test_slot_id_tem_precedencia_sobre_equipamento_id`). Não é achado.
- **Dependência com `vencimentos.service.criar_controles_para_item`**: lida apenas o suficiente para confirmar o efeito colateral em `criar_item_com_heranca`/`_obter_ou_criar_item_por_pn` — a revisão de fundo do módulo `vencimentos` fica para sua própria sessão.
- **Cobertura de testes**: forte para o catálogo (PN/SN), instalação/remoção manual e o fluxo de ajuste de inventário via `POST /inventario/ajuste` (concorrência de criação de item, conflito de transferência, contagem de queries). **Lacuna total identificada**: `xlsx_service.py` (239 linhas — prévia, processamento direto e confirmação de upload) não tem **nenhum** teste no repositório — nem de caminho feliz, nem de erro. Isso inclui os três endpoints de upload do router. Essa é a razão pela qual RISCO-02 e RISCO-03 nunca foram exercitados.

## Perguntas para o desenvolvedor (respondidas)

- O endpoint legado `POST /inventario/upload-xlsx` (MELHORIA-08) ainda tem algum cliente/integração ativa, ou pode ser removido em favor do fluxo prévia+confirmação? **Resposta: removido — sem dependência ativa.**
- O vínculo entre a prévia de XLSX e a confirmação (RISCO-02) — hoje inexistente do lado do servidor — foi uma simplificação deliberada (confiando no frontend controlado pelo próprio time) ou é uma lacuna a fechar? **Resposta: fechar a lacuna.**
- `EquipamentoControle` sendo apagado em cascata ao remover um PN (MELHORIA-06) é o comportamento desejado, ou deveria bloquear a exclusão como as outras duas dependências do PN? **Resposta: bloquear, no mesmo padrão das outras duas.**
