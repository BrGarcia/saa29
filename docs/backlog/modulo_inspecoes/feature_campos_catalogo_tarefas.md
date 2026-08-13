# Melhoria — Padronização dos campos Manual e Tarefa no cadastro de tarefas

> Status: ✅ Fase 1 implementada na branch `feature/catalogo-tarefas-manual-tarefa` (migração aplicada e testada localmente; ainda não commitada/mergeada). Fase 2 (seção 7) segue pendente, não implementada.
> Data: 2026-08-13 (revisado em 2026-08-13: escopo ampliado para incluir "Adicionar Tarefa Extra"; implementado em 2026-08-13)
> Escopo: duas janelas de cadastro de tarefa passam a usar o mesmo vocabulário (Manual/Tarefa em vez de Sistema/Grupo):
> 1. Modal **"Nova Tarefa no Catálogo"** — `Configurações → Gerenciar Tarefas → Catálogo Global de Tarefas → + Nova Tarefa`.
> 2. Modal **"Adicionar Tarefa Extra"** — `/inspecoes/{id} → Adicionar Tarefa` (tarefa avulsa, fora do catálogo).

## 1. Pedido original

Ajustar o formulário de cadastro de tarefa no catálogo global para permitir registrar a identificação estruturada da tarefa e sua referência documental.

| Campo atual | Campo proposto | Exemplo |
|---|---|---|
| Título da Tarefa (Ação) * | Título da Tarefa * | Teste Funcional do FDR |
| Sistema / Grupo | **Manual** | MPP1651_31-31-00-05-1 |
| — | **Tarefa** | 31-31-00-720-801-A |
| Descrição / Referência | Descrição | Realizar teste funcional do FDR, verificar validade das baterias, etiquetar equipamento. |

Restrições dadas: mexer só nos campos da janela "Nova Tarefa", não adicionar funcionalidade não pedida, preservar o comportamento de cadastro existente, manter o padrão visual da aplicação, manter a janela "Catálogo Global de Tarefas" e o fluxo de acesso atual.

> **Atualização (2026-08-13):** por decisão do dono do produto, a melhoria passou a cobrir também o modal **"Adicionar Tarefa Extra"** (`/inspecoes/{id}`), que usa hoje o mesmo padrão de campo "Sistema" — objetivo explícito é **padronizar as duas janelas de cadastro de tarefa** com o mesmo vocabulário (Manual/Tarefa). A decisão de manter a coluna `sistema` no banco, já recomendada na seção 4, foi confirmada e agora vale para as duas tabelas afetadas (`tarefas_catalogo` e `inspecao_tarefas`).

## 2. Onde isso vive hoje (mapeamento técnico)

| Peça | Arquivo |
|---|---|
| Modelo ORM `TarefaCatalogo` | `app/modules/inspecoes/models.py:47-67` (`titulo`, `descricao`, `sistema`, `ativa`) |
| Schemas `TarefaCatalogoCreate/Update/Out` | `app/modules/inspecoes/schemas.py:60-84` |
| Service `criar_tarefa_catalogo` / `atualizar_tarefa_catalogo` | `app/modules/inspecoes/service.py:188-232` |
| Router `POST/PUT /inspecoes/tarefas-catalogo` | `app/modules/inspecoes/router.py:88-129` (dependency `EncarregadoOuAdmin`; na prática só Admin chega lá, pois `/configuracoes` é admin-only desde `melhorias_pagina_configuracoes.md` item 3.4) |
| Modal + form no template | `app/web/templates/configuracoes.html:796-841` (`#modal-form-tarefa-catalogo`, `#formTarefaCatalogo`) |
| JS do form (abrir/preencher/salvar) | `app/web/static/js/configuracoes.js:1345-1439` (`openModalFormTarefaCatalogo`, `salvarTarefaCatalogo`) |
| Migration que criou a tabela | `migrations/versions/20260430_1259_728522300c7e_desacoplamento_tarefas.py` |
| Seed de desenvolvimento | `scripts/seed/seed_tarefas.py` |
| Cabeça atual do Alembic | `20260813_1500_e1a2b3c4d5f6` (`publicacoes upload modo_processamento...`) — é a `down_revision` de qualquer migração nova |

O fluxo de acesso e o modal "Catálogo Global de Tarefas" (`#modal-catalogo-tarefas`, listagem + botão "Nova Tarefa") não precisam de nenhuma alteração — só o modal de formulário (`#modal-form-tarefa-catalogo`) que abre a partir dele.

**Segunda janela agora em escopo — "Adicionar Tarefa Extra" (`/inspecoes/{id}`):**

| Peça | Arquivo |
|---|---|
| Modelo ORM `InspecaoTarefa` | `app/modules/inspecoes/models.py:156-189` (já tem `sistema: String(100)`, nulável) |
| Schemas `InspecaoTarefaCreate` / `InspecaoTarefaOut` | `app/modules/inspecoes/schemas.py:138-171` |
| Service `adicionar_tarefa_avulsa` (cria a tarefa avulsa) | `app/modules/inspecoes/service.py:606-635` |
| Service `abrir_inspecao` (denormaliza `TarefaCatalogo` → `InspecaoTarefa` ao instanciar tarefas de template) | `app/modules/inspecoes/service.py:556-569` |
| Router `POST /inspecoes/{inspecao_id}/tarefas` | `app/modules/inspecoes/router.py:468-481` |
| Modal + form no template | `app/web/templates/inspecoes/detalhe.html:88-123` (`#modal-add-tarefa`, `#formAddTarefa`) |
| Coluna "Sistema" da checklist de execução | `app/web/templates/inspecoes/detalhe.html:34` |
| JS do form (abrir/salvar) | `app/web/static/js/inspecao_detalhe.js:351-394` (`openModalAddTarefa`, `salvarAddTarefa`) |
| JS da checklist (coluna "Sistema" + fallback de descrição) | `app/web/static/js/inspecao_detalhe.js:219,283` |

## 3. Achado central: `sistema` está em uso em 7 pontos além do formulário

O pedido lista os campos alvo sem mencionar "Sistema", o que sugere substituição total. Antes de decidir, é preciso registrar que `TarefaCatalogo.sistema` **não é exclusivo deste formulário** — é lido e escrito em outros 7 lugares:

| # | Onde | O que faz |
|---|---|---|
| 1 | `configuracoes.js:1310` | Coluna "Sistema" na listagem do Catálogo Global de Tarefas |
| 2 | `configuracoes.js:1372` | Pré-preenche o input ao abrir o form em modo edição |
| 3 | `configuracoes.js:1709` | Rótulo `[sistema] título` no `<select>` usado para vincular uma tarefa do catálogo a um Tipo de Inspeção (`#tarefaCatalogoSelect`, modal "Tarefas da Inspeção") |
| 4 | `configuracoes.html:728` + `configuracoes.js:1173` | Coluna "Sistema" na tabela de tarefas já vinculadas a um Tipo de Inspeção |
| 5 | `service.py:565` (dentro de `abrir_inspecao`) | Ao abrir uma inspeção, `sistema` do catálogo é **copiado (denormalizado)** para `InspecaoTarefa.sistema` |
| 6 | `inspecao_detalhe.js:219` | Coluna "Sistema" na checklist de execução da inspeção (`/inspecoes/{id}`) |
| 7 | `inspecao_detalhe.js:283` | Fallback de descrição no modal de atualização de status da tarefa (`t.descricao \|\| t.sistema`) |

Além disso, existe uma **tela irmã**, que usa o mesmo padrão de campo "Sistema": o modal "Adicionar Tarefa Extra" em `/inspecoes/{id}` (`app/web/templates/inspecoes/detalhe.html:96-121`, input `#addTarefaSistemaInput`). Esse formulário cria uma `InspecaoTarefa` avulsa, sem `tarefa_catalogo_id` — **não é a janela "Nova Tarefa no Catálogo"**, é um fluxo tecnicamente independente (modelo, schema, service e router próprios). Na primeira versão desta análise ela tinha sido deixada de fora do escopo; por decisão do dono do produto (seção 1), ela **entrou no escopo** para que as duas janelas de cadastro de tarefa fiquem padronizadas com o mesmo vocabulário.

`sistema` já é opcional em 100% desses pontos (`t.sistema || 'Geral'`, `t.sistema || '---'` etc.) — nenhum deles quebra se o valor vier nulo.

## 4. Decisão de viabilidade

**Recomendação (confirmada pelo dono do produto): manter a coluna `sistema` no banco em ambas as tabelas (`tarefas_catalogo` e `inspecao_tarefas`) — não remover — e adicionar duas colunas novas e independentes — `manual` e `codigo_tarefa` — nas duas. Os dois formulários (Catálogo e Tarefa Extra) passam a capturar Manual/Tarefa em vez de Sistema; `sistema` para de ser escrito por qualquer um dos dois, mas nada que já o lê quebra.**

Por quê:

- **Custo de remover `sistema` de verdade é maior que o pedido cobre.** Apagar a coluna exigiria também tratar os 7 pontos de consumo listados acima — nada disso está nos critérios de aceite, e a restrição explícita é *"alterar somente os campos necessários na janela Nova Tarefa"*. Isso vale igualmente para `InspecaoTarefa.sistema`: é a mesma coluna, com o mesmo padrão de fallback gracioso, só que na tabela de tarefas já instanciadas numa inspeção em vez do catálogo.
- **Trocar o formulário sem tocar no banco já satisfaz o pedido.** Como todo consumidor de `sistema` já degrada graciosamente para nulo, bastar não gravar mais esse campo por este form já produz o efeito pedido (o usuário não vê mais "Sistema / Grupo" na tela) sem quebrar nada.
- **Reaproveitar `sistema` como um dos dois campos novos foi considerado e descartado.** Os valores atuais de `sistema` (ex.: "Elétrica", "Motor", "Trem de Pouso", ver `seed_tarefas.py`) são categorias curtas, não referências de manual — misturar os dois sentidos na mesma coluna criaria dado ambíguo. Duas colunas novas, nuláveis, são mais simples e não migram/reinterpretam nada que já existe.
- **Nome da coluna:** usar `tarefa` como nome de campo dentro da classe `TarefaCatalogo` gera a redundância `TarefaCatalogo.tarefa` (e, no JSON de saída, uma chave `tarefa` ambígua com o próprio recurso). Proposto **`codigo_tarefa`** como nome interno — mesmo padrão já usado em `TipoInspecao.codigo` — mantendo o rótulo da UI como "Tarefa", que é o que o pedido especifica. O mesmo nome de coluna (`manual`, `codigo_tarefa`) é usado em `InspecaoTarefa`, para manter os dois modelos com vocabulário idêntico — é literalmente o mesmo par de campos, só que numa tarefa já instanciada dentro de uma inspeção em vez de no catálogo reutilizável.
- **Consistência entre os dois caminhos de criação de `InspecaoTarefa`:** hoje uma `InspecaoTarefa` nasce de duas formas — (a) instanciada a partir de um `TarefaTemplate`/`TarefaCatalogo` quando uma inspeção é aberta (`abrir_inspecao`, denormaliza `sistema` do catálogo), ou (b) avulsa, via "Adicionar Tarefa Extra". Para as duas janelas ficarem realmente padronizadas, a denormalização de `abrir_inspecao` passa a copiar `manual`/`codigo_tarefa` do catálogo também (além de `sistema`, que continua sendo copiado por compatibilidade) — sem isso, uma tarefa vinda do catálogo com Manual/Tarefa preenchidos apareceria "muda" dentro da inspeção, enquanto uma tarefa avulsa cadastrada à mão mostraria a referência. Ver seção 6.
- **Baixo risco de migração:** conforme registrado em memória do projeto, a aplicação ainda não está hospedada (dev local, VPS planejada) — não há dado real de produção em jogo, então uma migração puramente aditiva (duas colunas nuláveis) tem risco mínimo mesmo sem plano de backfill.

Alternativa descartada: renomear `sistema` → `manual` em vez de criar coluna nova. Rejeitada pelo mesmo motivo do ponto acima (dado semanticamente diferente) e porque ainda deixaria faltando um campo próprio para "Tarefa" (código).

## 5. Modelagem de dados proposta

```python
# app/modules/inspecoes/models.py — TarefaCatalogo
manual: Mapped[str | None] = mapped_column(String(100), nullable=True)
codigo_tarefa: Mapped[str | None] = mapped_column(String(60), nullable=True)

# app/modules/inspecoes/models.py — InspecaoTarefa (mesmo par, mesmos tamanhos)
manual: Mapped[str | None] = mapped_column(String(100), nullable=True)
codigo_tarefa: Mapped[str | None] = mapped_column(String(60), nullable=True)
```

Tamanhos folgados em relação aos exemplos dados (`MPP1651_31-31-00-05-1` = 22 caracteres; `31-31-00-720-801-A` = 18 caracteres), seguindo o padrão de `sistema` (`String(100)`) para não introduzir um limite artificialmente apertado. Usar o mesmo par de colunas/tamanhos nas duas tabelas evita qualquer conversão ou truncamento ao denormalizar de `TarefaCatalogo` para `InspecaoTarefa`.

## 6. Plano de implementação — Fase 1 (obrigatória, cobre o ACEITE + padronização pedida)

### 6.1 Catálogo Global de Tarefas

| Arquivo | Mudança |
|---|---|
| `migrations/versions/` (nova revisão, `down_revision = "e1a2b3c4d5f6"`) | `ALTER TABLE tarefas_catalogo ADD COLUMN manual VARCHAR(100)` e `ADD COLUMN codigo_tarefa VARCHAR(60)`, ambas nuláveis. Ver 6.3 — mesma revisão também altera `inspecao_tarefas`. |
| `app/modules/inspecoes/models.py:47-67` | Adicionar `manual` e `codigo_tarefa` na classe `TarefaCatalogo`, ao lado de `sistema` (que permanece intocado). |
| `app/modules/inspecoes/schemas.py:60-84` | `TarefaCatalogoCreate`: `manual: str \| None = Field(default=None, max_length=100)`, `codigo_tarefa: str \| None = Field(default=None, max_length=60)`. Mesmos dois campos em `TarefaCatalogoUpdate` (opcionais) e em `TarefaCatalogoOut` (retorno). `sistema` continua declarado nos três schemas — só deixa de ser preenchido por este formulário. |
| `app/modules/inspecoes/service.py:188-198` (`criar_tarefa_catalogo`) | Passar `manual=dados.manual, codigo_tarefa=dados.codigo_tarefa` no construtor de `TarefaCatalogo`. |
| `app/modules/inspecoes/service.py:217-232` (`atualizar_tarefa_catalogo`) | Adicionar `"manual"` e `"codigo_tarefa"` ao conjunto `campos_nulaveis` passado a `_aplicar_mudancas` (hoje é `{"descricao", "sistema"}`). |
| `app/web/templates/configuracoes.html:816-820` | Trocar o `form-group` de "Sistema / Grupo" (`#sistemaTarefaCatalogoInput`) por dois `form-group` novos: "Manual" (`#manualTarefaCatalogoInput`, placeholder `Ex: MPP1651_31-31-00-05-1`) e "Tarefa" (`#codigoTarefaCatalogoInput`, placeholder `Ex: 31-31-00-720-801-A`). Mesma classe `form-input`, mesmo padrão visual dos demais campos do modal. |
| `app/web/templates/configuracoes.html:822` | Label "Descrição / Referência" → "Descrição" (a referência documental passou a ter campos próprios). |
| `app/web/static/js/configuracoes.js:1345-1382` (`openModalFormTarefaCatalogo`) | Trocar a referência a `inputSistema`/`sistemaTarefaCatalogoInput` por leitura de `manualTarefaCatalogoInput` e `codigoTarefaCatalogoInput` ao pré-preencher o form em modo edição. |
| `app/web/static/js/configuracoes.js:1400-1439` (`salvarTarefaCatalogo`) | Corpo do `POST`/`PUT` passa a enviar `manual` e `codigo_tarefa` em vez de `sistema`. |

Nenhum componente visual novo: os dois campos novos reaproveitam literalmente o mesmo `form-group`/`form-input` já usado por "Título" e "Sistema/Grupo" hoje — é troca de rótulo, id e placeholder, no mesmo esqueleto de modal `glass-panel`.

`scripts/seed/seed_tarefas.py` não precisa mudar para o ACEITE ser satisfeito (o catálogo semeado em dev continua válido com `sistema` preenchido e `manual`/`codigo_tarefa` nulos); pode opcionalmente ganhar 2-3 exemplos com os campos novos preenchidos só para dar sinal visual em ambiente de desenvolvimento.

### 6.2 Adicionar Tarefa Extra (padronização, escopo ampliado)

| Arquivo | Mudança |
|---|---|
| `app/modules/inspecoes/models.py:156-189` | Adicionar `manual` e `codigo_tarefa` na classe `InspecaoTarefa`, ao lado de `sistema` (intocado). |
| `app/modules/inspecoes/schemas.py:138-171` | `InspecaoTarefaCreate`: adicionar `manual: str \| None = Field(default=None, max_length=100)` e `codigo_tarefa: str \| None = Field(default=None, max_length=60)`. `InspecaoTarefaOut`: mesmos dois campos, para a checklist conseguir exibi-los. `sistema` continua nos dois schemas. |
| `app/modules/inspecoes/service.py:606-635` (`adicionar_tarefa_avulsa`) | Passar `manual=dados.manual, codigo_tarefa=dados.codigo_tarefa` no construtor de `InspecaoTarefa` (`sistema=dados.sistema` continua no código, só que o formulário não vai mais enviá-lo). |
| `app/web/templates/inspecoes/detalhe.html:102-105` | Trocar o `form-group` de "Sistema" (`#addTarefaSistemaInput`) por dois `form-group`: "Manual" (`#addTarefaManualInput`, mesmo placeholder do catálogo) e "Tarefa" (`#addTarefaCodigoInput`), reaproveitando o mesmo par de campos do modal do catálogo (6.1). |
| `app/web/static/js/inspecao_detalhe.js:361-394` (`salvarAddTarefa`) | Ler `addTarefaManualInput`/`addTarefaCodigoInput` em vez de `addTarefaSistemaInput`; corpo do `POST /inspecoes/{id}/tarefas` passa a enviar `manual` e `codigo_tarefa` em vez de `sistema`. |

### 6.3 Consistência da checklist de execução (necessária para a padronização ter efeito prático)

Sem isto, uma tarefa avulsa cadastrada com Manual/Tarefa preenchidos ficaria **sem nenhum lugar na aplicação onde esse dado aparece** — diferente do catálogo (seção 7), a tarefa avulsa não tem uma tela de edição posterior para consultar o valor salvo. Por isso este bloco entra na Fase 1, não fica como Fase 2 opcional:

| Arquivo | Mudança |
|---|---|
| `migrations/versions/` (mesma revisão de 6.1) | `ALTER TABLE inspecao_tarefas ADD COLUMN manual VARCHAR(100)` e `ADD COLUMN codigo_tarefa VARCHAR(60)`, nuláveis. |
| `app/modules/inspecoes/service.py:556-569` (denormalização em `abrir_inspecao`) | Ao instanciar `InspecaoTarefa` a partir de `TarefaTemplate`/`TarefaCatalogo`, copiar também `manual=template.tarefa_catalogo.manual, codigo_tarefa=template.tarefa_catalogo.codigo_tarefa` (além de `sistema`, que continua sendo copiado). Sem isso, tarefas vindas do catálogo ficariam inconsistentes com tarefas avulsas dentro da mesma checklist. |
| `app/web/templates/inspecoes/detalhe.html:34` | Cabeçalho de coluna "Sistema" → "Tarefa" (mostra `codigo_tarefa`). |
| `app/web/static/js/inspecao_detalhe.js:219` | Célula da coluna passa a exibir `t.codigo_tarefa || '—'` em vez de `t.sistema || 'Geral'`. |
| `app/web/static/js/inspecao_detalhe.js:283` | Fallback de descrição no modal de status: `t.descricao \|\| t.codigo_tarefa \|\| t.manual \|\| ''` em vez de `t.descricao \|\| t.sistema \|\| ''`. |

Com isso, os dois caminhos que alimentam `InspecaoTarefa` (instanciada do catálogo, ou avulsa) resultam no mesmo vocabulário visível na checklist — é o que fecha o pedido de "padronizar a janela de tarefa" de ponta a ponta, não só nos dois formulários de entrada.

## 7. Plano de implementação — Fase 2 (ainda recomendada, fora do ACEITE literal)

A checklist de execução da inspeção já é coberta pela Fase 1 (seção 6.3), porque sem isso a padronização pedida ficaria incompleta. O que sobra como Fase 2 são só as telas de **gestão do catálogo** (não de execução) que também exibem "Sistema" hoje — têm menor urgência porque o catálogo tem tela de edição própria, então o dado nunca fica de fato inacessível, só não aparece de relance nessas listagens:

| Onde | Mudança sugerida |
|---|---|
| Listagem do Catálogo (`configuracoes.js:1310`) | Coluna "Sistema" → "Tarefa" (exibindo `codigo_tarefa`), por ser a referência mais útil para localizar o item depois. |
| Select de vínculo tarefa↔tipo (`configuracoes.js:1709`) | Rótulo `[sistema] título` → `[codigo_tarefa] título` (mesmo fallback `'Geral'`). |
| Tabela de tarefas vinculadas a um Tipo (`configuracoes.html:728`, `configuracoes.js:1173`) | Mesma troca de coluna. |

Essas trocas são só de exibição — não envolvem migração de dado nem mudança de schema além do que a Fase 1 já introduz. Tarefas antigas do catálogo (com `sistema` preenchido e `manual`/`codigo_tarefa` nulos) simplesmente mostrariam essas colunas vazias até serem reeditadas manualmente; nenhuma mudança automática de dado é proposta.

## 8. Riscos e observações

- **Nenhuma migração de dado histórico.** Tarefas e inspeções já cadastradas mantêm `sistema` preenchido e ganham `manual`/`codigo_tarefa` nulos até serem editadas (catálogo) ou reabertas (inspeção) — comportamento esperado de colunas aditivas, sem heurística automática razoável para preencher os novos campos a partir do antigo.
- **Baixo risco de migração:** ambiente ainda não hospedado (dev local, VPS planejada — sem dado real de produção hoje), o que reduz a preocupação usual com `ALTER TABLE` em produção. As duas tabelas (`tarefas_catalogo`, `inspecao_tarefas`) recebem colunas nuláveis, sem `NOT NULL`/default a recalcular.
- **Testes existentes não quebram.** `tests/unit/test_inspecoes.py` (linhas 84, 105, 451, 498, 541-542) e `tests/unit/test_inspecoes_refatoracao.py` (linha 71) constroem `TarefaCatalogoCreate(..., sistema=...)` — como `sistema` permanece no schema (só deixa de ser exposto nos formulários), nenhum desses testes precisa mudar. Testes novos devem cobrir `manual`/`codigo_tarefa` em `criar_tarefa_catalogo`/`atualizar_tarefa_catalogo`, em `adicionar_tarefa_avulsa`, e a propagação em `abrir_inspecao` (uma tarefa instanciada de um `TarefaCatalogo` com `manual`/`codigo_tarefa` preenchidos deve chegar com os mesmos valores em `InspecaoTarefa`).
- **Vocabulário agora consistente entre as duas janelas** — era um risco na primeira versão desta análise (catálogo falando Manual/Tarefa, tarefa avulsa ainda falando Sistema); resolvido ao trazer "Adicionar Tarefa Extra" para o mesmo escopo (seção 6.2).

## 9. Critérios de aceite — rastreabilidade

| Critério do pedido | Satisfeito por |
|---|---|
| Janela "Nova Tarefa no Catálogo" apresenta Título, Manual, Tarefa e Descrição | Fase 1 (6.1), item `configuracoes.html:816-822` |
| Usuário informa o manual de referência | Fase 1, campo `manual` |
| Usuário informa o código/número da tarefa | Fase 1, campo `codigo_tarefa` (rótulo "Tarefa") |
| Usuário informa a descrição detalhada | Já existe (`descricao`), só muda o rótulo |
| Título continua disponível | Inalterado |
| Dados persistidos corretamente | Fase 1, `models.py` + `schemas.py` + `service.py` + migração |
| *(ampliação 2026-08-13)* "Adicionar Tarefa Extra" usa o mesmo vocabulário Manual/Tarefa | Fase 1 (6.2), `inspecoes/detalhe.html:102-105` + `inspecao_detalhe.js:361-394` |
| *(ampliação 2026-08-13)* Coluna `sistema` mantida nas duas tabelas, sem degradação de telas existentes | Fase 1 (todas), seção 4 e 8 |

## 10. Estimativa de esforço

- **Fase 1:** médio — 1 migração aditiva (2 tabelas) + 12 arquivos tocados (2 models, 4 schemas, 3 funções de service, 2 templates, 2 arquivos JS), todos seguindo padrões já existentes no módulo; nenhum componente ou padrão visual novo, e os dois formulários reaproveitam literalmente o mesmo par de campos.
- **Fase 2:** baixo — troca pontual de coluna/rótulo em 3 telas de gestão do catálogo já existentes.

## 11. Registro de implementação (Fase 1, 2026-08-13)

Implementado na íntegra conforme seções 6.1, 6.2 e 6.3, na branch `feature/catalogo-tarefas-manual-tarefa`. Ainda não commitado nem aberto PR — fica para o dono do produto decidir quando revisar/commitar.

- **Migração:** `migrations/versions/20260813_1239_b63e385e3395_manual_e_codigo_tarefa_em_tarefas_.py` (`down_revision = e1a2b3c4d5f6`), aplicada ao banco local (`saa29_local.db`) e conferida via `PRAGMA table_info` nas duas tabelas.
- **Testes:** `tests/unit/test_inspecoes.py`, `test_inspecoes_refatoracao.py` e `test_inspecao_pdf.py` — 33/33 passando sem alteração, confirmando a previsão da seção 8. Suíte completa de `tests/unit` rodada por cima: 541 passando; as 3 falhas encontradas (`test_publicacoes_catalog.py::test_regressao_acervo_real_*`) são pré-existentes e não relacionadas — dependem de um acervo real de PDFs em disco que não está presente neste ambiente, confirmado por `git diff development` não tocar em nada daquele módulo.
- **Achado colateral (não corrigido, fora de escopo):** `alembic revision --autogenerate` só pegou o diff das duas colunas novas depois de eu remover manualmente do arquivo gerado um lote de mudanças sem relação — `DROP TABLE encarregado_ciencias` (o módulo `encarregado` não está importado em `migrations/env.py:24-33`, então o Alembic acha que a tabela deveria ser removida), troca de tipo em `publicacoes_upload_jobs.status`/`modo_processamento` (falso positivo já documentado em `20260813_1500_e1a2b3c4d5f6...py`, comparação VARCHAR-refletido vs. `sa.Enum(create_constraint=False)`) e drop de `uq_pedidos_numero_pedido`. Vale abrir um item de backlog separado para adicionar `import app.modules.encarregado.models` em `env.py` — sem isso, a próxima pessoa que rodar `--autogenerate` corre o risco de aceitar um `DROP TABLE encarregado_ciencias` sem perceber.
- **Achado colateral (ambiente, não corrigido):** `tests/unit/test_publicacoes_favoritos.py`, `test_publicacoes_publicar.py` e `test_zip_validator.py` não coletam nesta máquina por `ModuleNotFoundError: No module named 'pypdfium2'` — dependência ausente no `venv` local, sem relação com esta melhoria.
