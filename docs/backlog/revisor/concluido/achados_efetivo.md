# Achados de Revisão — Módulo `efetivo`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 04/08/2026
> 5/7 corrigidos, 1 parcial (RISCO-03: comentário explícito adicionado ao atalho de seed,
> sem mudança estrutural — o próprio achado já classificava (1) como sem ação urgente), 1 não
> corrigido por decisão consciente (MELHORIA-06, que o próprio achado já classificava como não
> urgente no volume atual). Commit `c5e9ff3`. Suite completa: 406 testes, 0 falhas (9 novos em
> `tests/unit/test_efetivo.py`). Status por item marcado inline em cada achado abaixo (campo
> `**Status:**`).

---

### [RISCO-01] Leitura de indisponibilidades aberta a qualquer usuário autenticado — expõe motivo e observação de terceiros

- **Classificação:** RISCO
- **Severidade:** ALTA
- **Arquivo:** `app/modules/efetivo/router.py:22-28`
- **Eixo:** Segurança
- **Problema:** `GET /efetivo/ativas` e `GET /efetivo/usuario/{usuario_id}` exigem apenas `CurrentUser` (qualquer usuário autenticado, qualquer papel). Ambos retornam `IndisponibilidadeOut`, que inclui `tipo` (`FERIAS`, `DISPENSA`, `FOLGA`, `SERVIÇO`, `OUTRO`) e `observacao` (texto livre, até 500 caracteres) — de **qualquer** militar do sistema, sem checagem de que o solicitante seja o próprio dono do registro ou tenha papel privilegiado. Escrita (`POST /`) e remoção (`DELETE /{id}`) já são restritas a `EncarregadoOuAdmin` (`router.py:16,31`) — só a leitura ficou aberta.
- **Consequência:** um `MANTENEDOR` comum consegue consultar `GET /efetivo/usuario/{qualquer_id}` e ler, por exemplo, que outro militar está de `DISPENSA` (afastamento médico) com a `observacao` associada — dado de saúde/pessoal exposto sem necessidade operacional de quem consulta. Contrasta com o módulo `calendario`, que trata dado equivalente (evento marcado `private`) com censura ativa de identidade, título e notas para quem não é dono nem privilegiado (`calendario/service.py:35-38,47-63`) — o mesmo tipo de informação (indisponibilidade de pessoal) tem dois níveis de proteção diferentes dependendo de qual dos dois módulos a expõe.
- **Consequência (dado agravante):** `TipoIndisponibilidade` inclui `DISPENSA`, que no contexto de gestão de efetivo tipicamente denota afastamento médico/administrativo — categoria sensível o suficiente para justificar controle de acesso, não apenas de escrita.
- **Correção proposta:** restringir a leitura de indisponibilidades de terceiros a `EncarregadoOuAdmin` ou ao próprio dono (`usuario_id == current_user.id`), no mesmo padrão de "dono ou privilegiado" já usado em `calendario.service.is_owner`/`has_privilege`. Se a leitura ampla for necessária para alguma tela (ex. calendário de disponibilidade da equipe), considerar um endpoint agregado que exponha só "disponível/indisponível" sem o motivo.
- **Risco de regressão:** MÉDIO — se alguma tela hoje depende de listar indisponibilidades de terceiros para usuários não privilegiados, a restrição quebra esse fluxo; precisa checar consumidores no front antes de aplicar.
- **Precisa de teste antes?** SIM.
- **Status:** ✅ CORRIGIDO, com desenho diferente do proposto — implementado conforme a resposta do desenvolvedor (ver seção de perguntas), não a correção originalmente sugerida. A leitura permanece aberta a qualquer `CurrentUser` (decisão consciente: a indisponibilidade em si é pública). Adicionado `TipoIndisponibilidade.PARTICULAR` (`app/shared/core/enums.py`); nova função `efetivo.service._to_out` serializa toda saída da API e força `observacao=None` sempre que `tipo == PARTICULAR`, para **qualquer** solicitante (dono ou não), em vez de restringir por papel/dono. Aplicado em `registrar_indisponibilidade`, `listar_indisponibilidades_ativas` e `listar_indisponibilidades_por_usuario`. Testes: `test_tipo_particular_oculta_observacao_em_todas_as_saidas`, `test_tipo_nao_particular_preserva_observacao`, `test_leitura_de_indisponibilidade_de_terceiro_permanece_publica`, `test_leitura_publica_de_tipo_particular_nao_expoe_observacao_via_api`.

---

### [BUG-02] Registrar indisponibilidade para `usuario_id` inexistente derruba a request com 500 em vez de erro tratado

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/efetivo/service.py:15-36`; `app/modules/efetivo/router.py:15-20`
- **Eixo:** Banco / Tratamento de erros
- **Problema:** `registrar_indisponibilidade` valida datas e sobreposição, mas nunca confere se `dados.usuario_id` corresponde a um `Usuario` existente antes de `db.add(indisp)` / `await db.flush()`. Como o projeto roda com `PRAGMA foreign_keys=ON` (`00_mapa_arquitetural.md` §6) e `Indisponibilidade.usuario_id` tem `ForeignKey("usuarios.id", ondelete="CASCADE")` (`models.py:24`), um `usuario_id` inexistente faz o `flush()` levantar `IntegrityError` do SQLite. O router só captura `except ValueError as e` (`router.py:19-20`) — `IntegrityError` escapa e vira 500 genérico.
- **Consequência:** `POST /efetivo/` com um `usuario_id` que não existe (UUID válido mas não cadastrado, ou de um usuário já removido) retorna 500 com traceback de SQL, em vez de 404/400 com mensagem clara — expõe detalhe de implementação ao cliente e é o padrão exato que o checklist **D** do `revisor.md` pede para evitar ("mensagem de exceção interna devolvida ao cliente").
- **Correção proposta:** validar a existência do usuário antes do `db.add` (padrão já usado em `calendario.service._ensure_user_exists`) e levantar `ValueError`/404 apropriado — reaproveitando, se fizer sentido, a mesma função auxiliar de outro módulo em vez de reimplementar.
- **Risco de regressão:** BAIXO — adiciona uma validação, não altera o caminho feliz.
- **Precisa de teste antes?** SIM.
- **Status:** ✅ CORRIGIDO. `registrar_indisponibilidade` agora faz `db.get(Usuario, dados.usuario_id)` antes de montar `Indisponibilidade`/`db.add`, levantando `ValueError("Usuário não encontrado.")` — capturado pelo `except ValueError` já existente em `router.py`, retornando 400 em vez de 500. Testes: `test_usuario_id_inexistente_levanta_valueerror_nao_integrityerror`, `test_post_efetivo_usuario_id_inexistente_retorna_400_nao_500`.

---

### [RISCO-03] Checagem de sobreposição de período é TOCTOU e sem constraint de banco equivalente; seed contorna o service por completo

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/efetivo/service.py:20-31`; `app/modules/auth/service.py:401-412`; `migrations/versions/20260426_2005_390dd051edd3_add_indisponibilidades.py`
- **Eixo:** Concorrência / Banco
- **Problema:** dois achados relacionados. (1) A checagem de sobreposição de datas para o mesmo usuário (`service.py:21-31`) é um `SELECT` seguido de decisão de inserir — clássico TOCTOU: duas requisições concorrentes registrando períodos sobrepostos para o mesmo `usuario_id` podem ambas passar pela checagem, já que não existe nenhuma constraint de exclusão de intervalo no banco (a migração `390dd051edd3` que cria a tabela é auto-gerada, só com `ForeignKeyConstraint` e índice em `usuario_id`, sem constraint de não-sobreposição). (2) O seed de desenvolvimento em `app/modules/auth/service.py:404-410` instancia `Indisponibilidade(...)` diretamente via ORM (`db.add(indisp)`), contornando por completo `registrar_indisponibilidade` — inclusive a validação de sobreposição e de `data_fim >= data_inicio` que o service garante.
- **Consequência:** sob concorrência real (dois `POST /efetivo/` simultâneos para o mesmo militar), o sistema pode acabar com dois períodos de indisponibilidade sobrepostos no banco, que é exatamente o que a validação do service existe para impedir. O caminho do seed (2) é honesto sobre ser um atalho de desenvolvimento, mas normaliza a prática de escrever na tabela sem passar pela regra de negócio — um padrão que, se replicado, deixa a validação do service decorativa.
- **Correção proposta:** para (1), nada estrutural é urgente sem evidência de concorrência real neste fluxo — registrar o risco (severidade MÉDIA, não ALTA, porque o cenário exige dois cadastros simultâneos do mesmo militar). Para (2), é código de seed isolado por um `if user == "mantenedor":` de inicialização — sem ação necessária, mas vale um comentário explícito de que é um atalho consciente que ignora a validação do service (hoje já implícito, mas não declarado).
- **Risco de regressão:** BAIXO — não propõe mudança de código, apenas registro do risco.
- **Precisa de teste antes?** NÃO (registro de risco, sem correção proposta nesta sessão).
- **Status:** 🔶 PARCIAL, conforme a própria correção proposta. (1) sem mudança estrutural — mantido como risco registrado, sem constraint de exclusão de intervalo no banco, por não haver evidência de concorrência real neste fluxo. (2) comentário explícito adicionado em `app/modules/auth/service.py` acima do `Indisponibilidade(...)` do seed, declarando que é um atalho consciente que contorna `registrar_indisponibilidade` (e suas validações de sobreposição/data) — aceitável por ser dado de seed fixo, não input de usuário.

---

### [MELHORIA-04] Docstring do model promete integração com alocação de panes que não existe em nenhum lugar do código

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/efetivo/models.py:20`
- **Eixo:** Arquitetura
- **Problema:** o docstring de `Indisponibilidade` declara: *"Registro de período onde um usuário não pode ser alocado para panes."* Um `grep` por `Indisponibilidade`/`efetivo` em todo `app/` fora do próprio módulo só encontra: o registro no `bootstrap/main.py` (import de model + router), referências textuais em `auth/router.py`/`auth/service.py` (rótulos de UI, "efetivo" como sinônimo de "usuários do sistema", sem relação com indisponibilidade) e o seed de desenvolvimento já citado no RISCO-03. Nenhum ponto do módulo `panes` (responsável por atribuir `pane_responsaveis`) consulta a tabela `indisponibilidades` para impedir a atribuição de um militar indisponível.
- **Consequência:** a regra de negócio descrita no comentário do model não é aplicada — um militar registrado como `FERIAS`/`DISPENSA` pode ser normalmente atribuído como responsável por uma pane, contradizendo o propósito declarado da tabela (anti-padrão #2 do `revisor.md`, "comentário que descreve algo que o código não faz").
- **Correção proposta:** decidir conscientemente entre (a) implementar a checagem em `panes.service` ao atribuir responsável, consultando `efetivo.service.listar_indisponibilidades_ativas` ou equivalente, ou (b) corrigir o docstring para não prometer uma integração que não existe, deixando explícito que hoje é só um registro informativo.
- **Risco de regressão:** MÉDIO se a opção for (a) — passa a bloquear atribuições hoje permitidas, com impacto direto no fluxo operacional de panes.
- **Precisa de teste antes?** SIM, se a decisão for (a).
- **Resposta do desenvolvedor:** opção (b) — não prometer nem implementar a integração; atribuição de responsável por pane deve continuar independente da indisponibilidade.
- **Status:** ✅ CORRIGIDO (opção b). Docstring de `Indisponibilidade` (`app/modules/efetivo/models.py`) reescrito para não prometer a integração com `panes`, com nota explícita de que é "apenas informativo — não bloqueia atribuição de responsável por pane". Nenhuma mudança de comportamento; sem teste novo necessário (correção de comentário).

---

### [MELHORIA-05] `selectinload(Indisponibilidade.usuario)` carrega dado que o schema de saída nunca expõe

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/efetivo/service.py:38-48`; `app/modules/efetivo/schemas.py:18-26`
- **Eixo:** Banco
- **Problema:** `listar_indisponibilidades_ativas` faz `.options(selectinload(Indisponibilidade.usuario))` (linha 46), mas `IndisponibilidadeOut` (o `response_model` do endpoint `GET /ativas`) só expõe `id`, `usuario_id`, `tipo`, `data_inicio`, `data_fim`, `observacao`, `created_at` — nenhum campo do relacionamento `usuario`. É uma query adicional (join/`IN` para carregar `Usuario`) executada em toda chamada do endpoint sem que o resultado seja usado.
- **Consequência:** custo de uma query extra por chamada sem benefício observável — pequeno, mas seguindo o padrão de "eager-load descartado" também encontrado no módulo `dashboard` (achados_dashboard.md, MELHORIA-03).
- **Correção proposta:** remover o `selectinload` se o relacionamento realmente não for necessário, ou expor os campos relevantes de `usuario` (ex. nome/trigrama) em `IndisponibilidadeOut` se a intenção original era exibir isso na UI.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO. `selectinload(Indisponibilidade.usuario)` removido de `listar_indisponibilidades_ativas` — nenhum campo do relacionamento é usado (a serialização passou a ser feita por `_to_out`, que só lê colunas escalares da própria `Indisponibilidade`, ver RISCO-01). Coberto indiretamente pelos testes de listagem já existentes (nenhuma regressão de dados retornados).

---

### [MELHORIA-06] Sem paginação nas listagens; `tipo` sem CHECK no banco; sem índice em `(data_inicio, data_fim)`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/efetivo/models.py:25-27`; `app/modules/efetivo/router.py:22-28`; `app/modules/efetivo/service.py:38-55`
- **Eixo:** Contrato / Banco
- **Problema:** três achados menores relacionados a robustez de longo prazo. (1) `GET /efetivo/ativas` e `GET /efetivo/usuario/{usuario_id}` não têm paginação (checklist **C** do `revisor.md`) — hoje inofensivo pelo volume baixo de dados de uma unidade, mas sem teto. (2) `tipo` é `String(50)` sem `CheckConstraint`, então só a borda Pydantic (`TipoIndisponibilidade`) impede valores fora do enum — qualquer escrita direta no ORM (como o seed do RISCO-03) grava `.value` corretamente hoje, mas nada no banco impede um valor arbitrário se esse hábito se espalhar. (3) o filtro de "ativas" (`data_inicio <= data_ref AND data_fim >= data_ref`, usado tanto na query quanto na checagem de sobreposição do RISCO-03) roda sem nenhum índice composto em `(data_inicio, data_fim)` — hoje sem impacto de performance mensurável, mas é o padrão de filtro mais frequente do módulo.
- **Consequência:** nenhuma imediata — riscos de escala/robustez, não bugs presentes.
- **Correção proposta:** avaliar paginação se o efetivo crescer; considerar `CheckConstraint` em `tipo` alinhado ao enum; considerar índice composto em `(data_inicio, data_fim)` se o volume justificar (checklist **B** do `revisor.md` pede medição antes de otimizar sem necessidade, conforme `revisor.md` §9).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO.
- **Status:** 🚫 NÃO CORRIGIDO — o próprio achado já classifica como "sem impacto imediato... considerar se o volume justificar". Mantido como está nesta sessão (inclusive porque `tipo` ganhou um valor novo, `PARTICULAR`, no RISCO-01 desta mesma sessão — qualquer `CheckConstraint`/migração ficaria mais estável decidida depois, junto de uma eventual paginação); revisitar se o efetivo crescer.

---

### [MELHORIA-07] Módulo sem nenhum teste — nenhum dos achados acima seria pego pela suíte atual

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** módulo `app/modules/efetivo/` inteiro
- **Eixo:** Testes
- **Problema:** `grep -rl "efetivo\|Indisponibilidade" tests/ --include=*.py` não retorna nenhum arquivo — os 4 endpoints do módulo (`POST /`, `GET /ativas`, `GET /usuario/{id}`, `DELETE /{id}`) não têm nenhum teste, unitário ou de integração, na suíte atual (checklist **G** do `revisor.md`: "Módulo sem nenhum teste").
- **Consequência:** RISCO-01 (leitura sem controle de acesso), BUG-02 (500 em vez de erro tratado) e RISCO-03 (TOCTOU de sobreposição) já existiam no código sem que nenhum teste os detectasse — a ausência de testes não é apenas uma lacuna de cobertura, é a razão concreta pela qual os outros achados desta sessão sobreviveram até agora.
- **Correção proposta:** criar `tests/unit/test_efetivo.py` cobrindo, no mínimo: caminho feliz de registro/listagem/remoção, rejeição de `data_fim < data_inicio`, rejeição de sobreposição, e — após decisão sobre RISCO-01 — o controle de acesso correto na leitura.
- **Risco de regressão:** BAIXO — é adição pura de testes.
- **Precisa de teste antes?** — (é o próprio item).
- **Status:** ✅ CORRIGIDO. Criado `tests/unit/test_efetivo.py` (9 testes): caminho feliz de registro/listagem/remoção, rejeição de `data_fim < data_inicio`, rejeição de sobreposição, `usuario_id` inexistente (BUG-02, via service e via `client_autenticado`), censura de `observacao` para `PARTICULAR` (RISCO-01, via service e via `client` autenticado com token de MANTENEDOR) e confirmação de que a leitura de terceiros permanece pública.

---

## Resumo

- Total de achados: 7
- BUG: 1 (CRÍTICA: 0, ALTA: 0, MÉDIA: 1, BAIXA: 0)
- RISCO: 2
- MELHORIA: 4
- DÚVIDA: 0
- **Corrigidos: 5/7** — 1 parcial (RISCO-03: comentário adicionado ao seed, sem mudança
  estrutural, conforme a própria correção proposta) e 1 não corrigido por decisão consciente
  (MELHORIA-06, que o próprio achado já classifica como sem impacto imediato)

## Arquivos revisados

- `app/modules/efetivo/models.py`
- `app/modules/efetivo/schemas.py`
- `app/modules/efetivo/service.py`
- `app/modules/efetivo/router.py`
- `app/modules/auth/service.py` (trecho do seed de desenvolvimento que grava `Indisponibilidade` diretamente)
- `migrations/versions/20260426_2005_390dd051edd3_add_indisponibilidades.py`
- `app/bootstrap/dependencies.py` (para confirmar `EncarregadoOuAdmin`/`CurrentUser`)
- `app/shared/core/enums.py` (`TipoIndisponibilidade`)
- `app/modules/encarregado/__init__.py` — ver nota abaixo

## Não revisado / limitações

- **`app/modules/encarregado`**: registrado aqui por não ter documento próprio (decisão de escopo desta sessão). É uma casca vazia — só `__init__.py` com docstring de intenção ("Ciência e Acompanhamento de Alterações Pendentes"), sem `router.py`, `models.py`, `service.py` ou `schemas.py`, e não é importado nem registrado em `app/bootstrap/main.py`. Já documentado como fato no mapa arquitetural (`00_mapa_arquitetural.md` §7.10, "módulo fantasma"). Não há código a revisar; sinalizado aqui apenas para não ficar invisível no backlog de revisão. Não é um `BUG`/`RISCO` deste módulo `efetivo` — é uma nota de cobertura do ciclo de revisão como um todo.
- Rate limiting: nenhum dos 4 endpoints tem `@limiter.limit(...)` — padrão de 116 dos 117 endpoints do sistema (mapa §5/§7.5), não é achado isolado deste módulo.
- Ausência de camada `repositories/`: idem, padrão de 100% dos módulos (mapa §1).
- O consumo do módulo pelo front-end (`app/web/templates/efetivo.html`, se existir tela dedicada) não foi lido — a extensão do impacto do RISCO-01 na UI (quais telas hoje exibem indisponibilidade de terceiros a usuários não privilegiados) não foi confirmada.

## Perguntas para o desenvolvedor (respondidas)

- **RISCO-01:** a leitura aberta de indisponibilidades a qualquer autenticado é intencional (ex. para uma tela de "disponibilidade da equipe" visível a todos) ou deveria ser restrita a dono/privilegiado como o restante do sistema trata dado sensível equivalente? **Resposta: a indisponibilidade da pessoa deve ser pública; indisponibilidades do tipo "Particular" têm um tipo próprio e aparecerão como particular, sem a descrição.** Implementado como `TipoIndisponibilidade.PARTICULAR` + censura de `observacao` na saída, sem restrição de acesso por papel/dono.
- **MELHORIA-04:** a integração "indisponibilidade bloqueia atribuição de responsável por pane" descrita no docstring do model é uma funcionalidade pendente de implementação ou o docstring deveria ser corrigido para não prometê-la? **Resposta: não prometer nem integrar — atribuição de responsável deve continuar independente da indisponibilidade.** Docstring corrigido.
