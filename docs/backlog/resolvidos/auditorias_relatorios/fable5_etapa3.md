# 🔧 Plano de Execução — ETAPA 3: Vencimentos & Inspeções

> **Escopo:** `app/modules/vencimentos/` + `app/modules/inspecoes/`
> **Relatório a gerar:** `docs/backlog/Fable5/relatorio_vencimentos_inspecoes.md`
> **Referência de processo:** `docs/backlog/Fable5/Planejamento_revisao.md` (Protocolo de Execução por Etapa)
> **Template de auditoria:** `docs/backlog/Fable5/prompt.md`
>
> **Status de execução:** 🔴 Críticos ✅ · 🟡 Média ✅ · 🟢 Baixa ✅ — Etapa 3 concluída em 02/08/2026

---

## 📁 Arquivos-Alvo (3.150 linhas)

| Arquivo | Linhas | Prioridade |
|---|---:|:---:|
| `app/modules/vencimentos/service.py` | 472 | 🔴 Alta |
| `app/modules/vencimentos/models.py` | 108 | 🟡 Média |
| `app/modules/vencimentos/router.py` | 170 | 🟡 Média |
| `app/modules/inspecoes/service.py` | 643 | 🔴 Alta |
| `app/modules/inspecoes/models.py` | 189 | 🟡 Média |
| `app/modules/inspecoes/router.py` | 520 | 🔴 Alta |
| `app/modules/inspecoes/pdf_service.py` | 909 | 🟢 Baixa |

> ⚠️ **Ajuste de escopo vs. plano original:** o `Planejamento_revisao.md` prevê para esta etapa *"performance da
> geração de PDFs via ReportLab (alocação de memória e **tratamento de imagens**)"*. Uma varredura em
> `pdf_service.py` não encontrou **nenhuma** manipulação de imagem (`ImageReader`, `drawImage`, `PIL`): o
> arquivo só usa `Paragraph`/`Table`/`Spacer`. A premissa está desatualizada — o foco real de PDF é
> **duplicação estrutural** (ver item #12), não imagens.

---

## 🔎 Achados Pré-Verificados

Levantamento feito na preparação deste plano. **CONFIRMADO** = reproduzido/verificado nesta sessão;
**A VERIFICAR** = forte indício, exige confirmação com teste durante a execução.

### 🔴 Críticos — ✅ CONCLUÍDO (02/08/2026)

---

#### 1. `AttributeError` em runtime: `domain_exc.NotFoundError` não existe — **CONFIRMADO** → ✅ CORRIGIDO
- **Tipo:** Bug
- **Evidência (`app/modules/vencimentos/service.py:424`):**
  ```python
  vencimento = await db.get(ControleVencimento, vencimento_id)
  if not vencimento:
      raise domain_exc.NotFoundError(detail="Vencimento não encontrado.")
  ```
- **Verificação executada:**
  ```
  >>> hasattr(exceptions, 'NotFoundError')  →  False
  Disponíveis: ConflitoNegocioError, EntidadeNaoEncontradaError, PermissaoNegadaError, SAA29BaseException
  ```
  É a **única** ocorrência de `NotFoundError` em `app/` (as demais são `FileNotFoundError`, builtin).
- **Risco & Impacto:** chamar `prorrogar_vencimento` com um `vencimento_id` inexistente levanta
  `AttributeError: module 'app.shared.core.exceptions' has no attribute 'NotFoundError'` →
  **HTTP 500** em vez de 404. Mesma classe do bug crítico corrigido na Etapa 1 (`NameError` de `Aeronave`).
  Nenhum teste cobre o caminho de "não encontrado" — por isso passou despercebido.
- **Correção:** trocar por `domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")`,
  alinhando com `registrar_execucao:215`. Teste de regressão obrigatório.

---

#### 2. Código morto: `stmt_update` construído e nunca executado — **CONFIRMADO** → ✅ CORRIGIDO
- **Tipo:** Arquitetura / Dívida técnica
- **Evidência (`app/modules/vencimentos/service.py:73-109`):** dentro de
  `associar_controle_a_equipamento`, um `update()` completo é montado em `stmt_update` (L77-92) e
  **jamais passado a `db.execute()`**. Logo abaixo (L95-107) a mesma operação é refeita via ORM.
- **Agravantes no mesmo bloco:**
  - `from sqlalchemy import update` (L75) — import local usado só pelo código morto.
  - L90: `func.date(..., f'+{periodicidade} months')` — interpolação de valor em fragmento SQL.
    Inócua hoje (é `int` e é código morto), mas é o padrão que não deve existir no repositório.
  - Comentários de proveniência de IA que devem sair: *"seguiremos a sugestão do auditor Claude"* (L89),
    *"conforme sugestão de segurança 152"* (L94).
- **Correção:** remover L75-92 integralmente e manter apenas o loop ORM.

---

#### 3. Status de vencimento nunca é recalculado pela passagem do tempo — **A VERIFICAR** → ✅ CORRIGIDO (opção A)
- **Tipo:** Bug de domínio
- **Evidência:** `ControleVencimento.status` é uma coluna **persistida** (`models.py:76`), gravada só em
  dois momentos: na criação (sempre `VENCIDO`) e em `registrar_execucao` (`service.py:250-258`).
  `montar_matriz_vencimentos` apenas **lê** o valor gravado (`service.py:359`: `status_final = venc.status`).
  Nenhum job/recálculo periódico existe (`app/bootstrap/tasks.py` tem apenas limpeza de token e de anexos).
- **Risco & Impacto:** um controle gravado como `OK` com vencimento para daqui a 40 dias continua
  exibido como **OK** depois de vencido. A matriz de vencimentos — artefato central do módulo — mostra
  status desatualizado indefinidamente até alguém registrar uma nova execução. Em manutenção
  aeronáutica isso é uma falha de segurança operacional, não só cosmética.
- **Agravante ligado ao item #4:** ao alterar a periodicidade (`service.py:106-108`), `data_vencimento`
  é recalculada mas `status` **não** — o comentário no código admite *"O status será recalculado na
  próxima visualização"*, o que **não acontece**.
- **Correção (decidir na execução — recomendo a opção A):**
  - **A. Derivar no ponto de leitura.** Extrair helper puro `calcular_status(data_vencimento, hoje)` e
    aplicá-lo em `montar_matriz_vencimentos`/`listar_vencimentos_por_item`. Elimina a classe inteira de
    bug (não há estado para dessincronizar) e é testável sem banco. Coluna vira cache/histórico.
  - **B. Job periódico** em `bootstrap/tasks.py` recalculando em lote. Mantém o bug entre execuções.
- **Verificar antes de corrigir:** se o frontend ou o dashboard filtram por `status` em SQL
  (`WHERE status = 'VENCIDO'`); nesse caso a opção A exige ajustar essas queries.

---

#### 4. Recálculo de periodicidade não atualiza `status` — **CONFIRMADO** (subitem de #3) → ✅ CORRIGIDO
- **Evidência (`app/modules/vencimentos/service.py:106-108`).**
- **Correção aplicada:** resolvido junto com #3 (opção A) — o status passou a ser derivado em tempo de
  leitura a partir de `data_vencimento`, que já era recalculada corretamente aqui; não há mais coluna
  de status para ficar dessincronizada.

---

#### 5. Duplicação integral de bloco de sincronização de status da aeronave — **CONFIRMADO** → ✅ CORRIGIDO
- **Tipo:** Arquitetura
- **Evidência:** `app/modules/inspecoes/service.py:574-593` (`concluir_inspecao`) e
  `app/modules/inspecoes/service.py:610-629` (`cancelar_inspecao`) são **byte a byte idênticos**:
  contagem de inspeções ativas + contagem de panes abertas + decisão `INDISPONIVEL`/`DISPONIVEL`.
- **Agravante:** ambos fazem `from app.modules.panes.models import Pane` **dentro da função**
  (L582-583 e L618-619) — acoplamento cross-módulo escondido do import-linter.
- **Risco:** regra de disponibilidade de aeronave divergindo entre os dois caminhos na próxima alteração.
  É exatamente o defeito de sincronização de status corrigido na Etapa 2 (`editar_pane`).
- **Correção:** extrair `_sincronizar_status_aeronave(db, inspecao)` e mover a consulta de panes para uma
  função pública em `panes.service` (mesmo padrão de `vencimentos.service.criar_controles_para_item`
  criado na Etapa 1), eliminando o import local.
- **Correção aplicada (mais econômica do que o previsto):** o módulo `panes.service` já continha, desde a
  Etapa 2, uma função equivalente e **mais completa** —
  `_sincronizar_status_aeronave_pane(db, aeronave_id)` — que já decidia entre `INSPECAO`/`INDISPONIVEL`/
  `DISPONIVEL` considerando tanto panes quanto inspeções ativas (via import tardio de
  `inspecoes.service.STATUS_ATIVOS`). Em vez de criar uma função nova, essa função foi **tornada pública**
  (renomeada para `panes.service.sincronizar_status_aeronave`) e os dois blocos duplicados em
  `inspecoes/service.py` foram substituídos por uma chamada a ela através do wrapper privado
  `inspecoes.service._sincronizar_status_aeronave` (import tardio, espelhando o padrão já usado no
  sentido inverso — evita ciclo de import em tempo de carregamento do módulo).
- **🔴 Bug adicional descoberto durante a correção (fora do escopo original do achado #5, mas causado por
  ele) — CORRIGIDO:** a função reaproveitada tinha um guard defeituoso —
  `if status_str not in [StatusAeronave.INSPECAO.value, "INSPEÇÃO", ...]` antes de aplicar `INDISPONIVEL`
  — escrito partindo do princípio de que só `panes.service` a chamaria, e que o status "INSPECAO" só
  poderia ter sido setado por *outro* ator (o módulo de inspeções) em paralelo, então não deveria ser
  sobrescrito. Ao passar a ser chamada **pelo próprio módulo de inspeções no momento de concluir/cancelar
  a inspeção**, esse guard vira uma armadilha: o `status` gravado na aeronave nesse instante *ainda* é
  `INSPECAO` (foi a própria inspeção que está terminando quem o colocou lá), então o guard bloqueava
  indevidamente a transição para `INDISPONIVEL` mesmo com uma pane aberta — a aeronave ficava presa em
  `INSPECAO` para sempre. Corrigido em `app/modules/panes/service.py:129-136`: a checagem de inspeção
  ativa (`tem_inspecao_ativa`, consulta ao vivo na tabela `inspecoes`) já é a fonte de verdade — o guard
  redundante sobre o `status` persistido foi removido, mantendo apenas a proteção contra sobrescrever
  `INATIVA`/`ESTOCADA`. **Capturado por teste de regressão antes de ir para produção** — ver
  `test_concluir_inspecao_com_pane_aberta_mantem_aeronave_indisponivel` e o par de cancelamento.
- **Efeito colateral em teste pré-existente:** `tests/unit/test_aeronaves.py::TestEndpointsAdicionais::
  test_status_aeronave_permanece_inspecao_quando_pane_aberta` setava `aeronave.status = INSPECAO`
  manualmente, **sem** criar o registro `Inspecao` correspondente — ou seja, testava exatamente o guard
  defeituoso removido acima. Corrigido para criar um registro real de `Inspecao` (ABERTA), alinhando o
  teste ao invariante de domínio real (status `INSPECAO` sempre corresponde a uma inspeção ativa).

---

### 🟡 Média — ✅ CONCLUÍDO (02/08/2026)

#### 6. N+1 queries em `associar_controle_a_equipamento` — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/modules/vencimentos/service.py:122-140`):** carrega todos os itens do modelo e emite
  **1 SELECT por item** para checar se o `ControleVencimento` já existe.
- **Correção aplicada:** um único `SELECT item_id FROM controle_vencimentos WHERE tipo_controle_id = :t
  AND item_id IN (...)`, subtração de `set` em Python e criação apenas do que falta. Mesmo padrão da
  Etapa 1. Teste: `test_associar_controle_a_equipamento_nao_gera_n_mais_1` (conta SELECTs via listener
  `before_cursor_execute`).

#### 7. N+1 em `abrir_inspecao` — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/modules/inspecoes/service.py:353-357`):** `buscar_tipo_inspecao` em loop (1 query por tipo).
  **`service.py:401-402`:** `listar_tarefas_template` em loop (1 query por tipo).
- **Correção aplicada:** `WHERE TipoInspecao.id.in_(dados.tipos_inspecao_ids)` num único SELECT (com
  validação dos IDs ausentes por diferença de conjuntos) e um único `WHERE TarefaTemplate.tipo_inspecao_id
  .in_(...)` com `selectinload`, reagrupado em Python por tipo para preservar a ordem original de
  iteração (cliente → `ordem` dentro do tipo) que a lógica de deduplicação por título depende.
  Testes: `test_abrir_inspecao_com_multiplos_tipos_nao_gera_n_mais_1` (test_inspecoes_refatoracao.py) e
  `test_abrir_inspecao_multiplos_tipos_usa_queries_batched`.

#### 8. TOCTOU (check-then-act) em criações com UNIQUE — **CONFIRMADO** → ✅ CORRIGIDO (parcial, ver nota)
- **Evidência:**
  - `vencimentos/service.py:33-38` — `criar_tipo_controle` (UNIQUE em `TipoControle.nome`, `models.py:29`). ✅
  - `vencimentos/service.py:48-53` — `atualizar_tipo_controle`. ✅
  - `vencimentos/service.py:62-119` — `associar_controle_a_equipamento` (UNIQUE `uq_equip_controle`, `models.py:45`). ✅
  - `inspecoes/service.py:52-63` — `criar_tipo_inspecao`. ✅
  - `inspecoes/service.py:208-235` — `criar_tarefa_template` (dois checks sequenciais). ✅
  - `inspecoes/service.py:363-374` — inspeção ativa duplicada. **Não corrigido nesta etapa**: não há
    UNIQUE constraint possível (a regra é "não pode haver duas inspeções *ativas* com o mesmo tipo",
    condicional ao status, não um par de colunas fixo) — precisaria de índice único parcial
    (`WHERE status IN ('ABERTA','EM_ANDAMENTO')`), que o SQLite atual do projeto não usa neste padrão em
    nenhum outro lugar. Fica como pendência consciente.
- **Correção aplicada:** reaplicado o padrão SAVEPOINT (`async with db.begin_nested()`) + captura de
  `IntegrityError` → exceção de domínio, já consolidado nas Etapas 1 e 2, nas 5 funções marcadas ✅ acima.
- **🔴 Achado sistêmico descoberto durante a implementação (fora do escopo desta etapa — documentado para
  investigação futura):** ao escrever o teste de regressão para `criar_tipo_inspecao`, uma combinação
  específica de testes revelou que uma inserção feita dentro de `async with db.begin_nested()` **sobrevive
  ao `await session.rollback()`** de teardown do fixture `db` de teste (`tests/conftest.py:71-73`),
  vazando para o teste seguinte dentro da mesma sessão de `pytest`. Isolado experimentalmente: com o
  SAVEPOINT, `IF-50H` criado em um teste ainda aparecia numa consulta sem filtro em outro teste rodado
  logo depois; sem o SAVEPOINT (voltando a `db.add()` + `flush()` simples), o vazamento desaparecia.
  Isso é consistente com uma lacuna de configuração conhecida e documentada do SQLAlchemy para SQLite
  (ver "Serializable isolation / Savepoints" na documentação do dialeto SQLite): o driver `aiosqlite`
  precisa de um par de listeners (`connect` + `begin`) desabilitando o `BEGIN` implícito do `pysqlite`
  para que `SAVEPOINT`/`RELEASE SAVEPOINT` fiquem corretamente aninhados dentro de uma transação externa
  revertível — `tests/conftest.py` (engine de testes) e `app/bootstrap/database.py` (produção) **não têm
  esse listener**. **Implicação potencialmente séria:** se o mesmo problema ocorrer em produção, todo o
  padrão de proteção via `db.begin_nested()` introduzido desde a Etapa 1 (TOCTOU) pode não estar isolando
  corretamente uma escrita malsucedida do restante da transação da requisição. **Não investigado nem
  corrigido aqui** — exige mudança na configuração do engine (arquivo compartilhado por toda a aplicação),
  fora do escopo de um módulo específico; recomendo tratar como item dedicado na Etapa 5 (bootstrap/
  database) ou como hotfix isolado, com um teste de regressão específico para o comportamento do SAVEPOINT
  antes de mexer. **Mitigação aplicada nesta etapa:** o teste frágil que expôs o sintoma
  (`test_router_isolado_encarregado_pode_criar_tipo`, que fazia `SELECT` sem filtro assumindo tabela
  vazia) foi corrigido para filtrar pelo `codigo` esperado — o teste em si tinha uma premissa de isolamento
  incorreta independentemente deste achado.

#### 9. `atualizar_inspecao` apaga observações num PATCH parcial — **VERIFICADO: FALSO-POSITIVO**
- **Evidência (`app/modules/inspecoes/service.py:449`):** `inspecao.observacoes = dados.observacoes`
  sem `exclude_unset`.
- **Verificação feita:** a rota é `@router.put("/{inspecao_id}", ...)` (`inspecoes/router.py:436-439`,
  "Atualizar observacoes da inspecao") e `InspecaoUpdate` tem **um único campo**, `observacoes`
  (`schemas.py:126-127`). Não há PATCH para este endpoint. Como é PUT com um único campo editável, a
  semântica de "substituição total" está correta por definição — não há campo parcial para preservar.
- **Conclusão:** não é bug. Nenhuma correção aplicada; mantido como estava.

#### 10. 36 `raise ValueError` em inspeções + 16 `except ValueError` genéricos no router — **CONFIRMADO** → ✅ CORRIGIDO
- **Contagem verificada:** `inspecoes` = 36 `raise ValueError` (não 18 `except` como estimado na
  preparação do plano — a contagem real de blocos `except ValueError` no router era **16**),
  `vencimentos` = 3 (não tocados neste item; mantidos como `ValueError` simples, pois o módulo já é
  internamente consistente — ver nota do item #8 sobre reaproveitar o mesmo padrão de exceção).
- **Evidência do efeito colateral (`app/modules/inspecoes/router.py`):** o router mapeava `ValueError` por
  posição, não por significado — `"Tipo de inspecao nao encontrado"` saía como **409 CONFLICT**, e
  `"Inspecao nao encontrada"` ora era 404 ora 409 dependendo do endpoint.
- **Correção aplicada:** os 36 `raise ValueError` foram classificados automaticamente por conteúdo da
  mensagem (`"nao encontrad"` → `EntidadeNaoEncontradaError`/404; qualquer outro caso →
  `ConflitoNegocioError`/409) e convertidos via script — 18 viraram `EntidadeNaoEncontradaError`, 18
  viraram `ConflitoNegocioError`. 14 dos 16 blocos `try/except ValueError` do router foram removidos (as
  exceções de domínio já carregam o status HTTP correto e propagam sozinhas via FastAPI). Os **2 blocos
  restantes** (`gerar_pdf_inspecao`, `gerar_checklist_inspecao`) foram mantidos — capturam
  `(ValueError, domain_exc.EntidadeNaoEncontradaError)` porque `pdf_service.py` (escopo da Fase 5/item
  #12) ainda não foi revisado e pode legitimamente levantar `ValueError` de bibliotecas internas.
- **Mudança de status HTTP em `reordenar_tarefas_template`:** o endpoint mapeava seus `ValueError` para
  **400 BAD_REQUEST** (único caso divergente dos demais, que usavam 409). Migrado para
  `ConflitoNegocioError` (409), alinhando com o resto do módulo — nenhum teste ou uso no frontend
  dependia do 400 especificamente (verificado antes de migrar).
- **Ajuste em 4 testes pré-existentes** (`test_inspecoes.py`): trocado `pytest.raises(ValueError, ...)`
  por `pytest.raises(domain_exc.ConflitoNegocioError, ...)`, já que a exceção de domínio não herda de
  `ValueError`.
- **Testes novos:** `test_atualizar_tipo_inspecao_inexistente_retorna_404_via_router`,
  `test_abrir_inspecao_duplicada_retorna_409_via_router`,
  `test_criar_tipo_inspecao_duplicado_retorna_conflito_de_dominio`.

#### 11. Sem teto de paginação em `listar_inspecoes` — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/modules/inspecoes/service.py:318-320`):** `limit` vem direto do filtro, sem clamp
  (o `else` sem filtro usa 100). A Etapa 1 padronizou **teto 200** em `listar_modelos`/`listar_itens`.
- **Correção aplicada:** `LIMITE_MAXIMO_LISTAGEM = 200` (mesmo padrão/valor de
  `equipamentos.service.LIMITE_MAXIMO_LISTAGEM`), aplicado via `min(filtros.limit,
  LIMITE_MAXIMO_LISTAGEM)` e no `else` sem filtro. Teste:
  `test_listar_inspecoes_respeita_teto_de_seguranca` (reduz o teto via `monkeypatch` para não precisar
  criar 200+ inspeções).

### 🟢 Baixa — ✅ CONCLUÍDO (02/08/2026)

#### 12. `pdf_service.py`: duas funções monolíticas com forte duplicação — **CONFIRMADO** → ✅ CORRIGIDO (parcial, ver nota)
- **Evidência:** o arquivo tem exatamente 3 funções — `_format_date` (L29) +
  `gerar_pdf_ordem_inspecao` (L39-459, **~420 linhas**) + `gerar_pdf_checklist_inspecao` (L461-906, **~445 linhas**).
  Ambas repetem a query com `selectinload`, a criação do `SimpleDocTemplate` e toda a definição de
  `ParagraphStyle` (`title_style`, `subtitle_style`, `section_heading`, ...).
- **Correção aplicada:** extraídas `_carregar_inspecao_para_pdf(db, inspecao_id)` (query + 404) e
  `_carregar_instalacoes_aeronave(db, aeronave_id)` (query de instalações + filtro de itens controlados),
  eliminando as duas queries duplicadas. **Não extraído:** `_construir_estilos()`/`_montar_documento()` —
  os ~20 `ParagraphStyle` diferem sutilmente entre as duas funções (tamanhos de fonte distintos:
  `section_heading` é `fontSize=10` na ordem e `9.5` no checklist; o checklist tem estilos exclusivos como
  `subsection_heading`/`manual_box_style`) e o checklist tem uma função interna
  (`build_checklist_table`) sem equivalente na ordem. Unificar exigiria parametrizar cada estilo
  individualmente — risco desproporcional ao ganho para um item 🟢, decisão de escopo consciente.
- **Verificação de equivalência binária:** gerados os dois PDFs de uma inspeção-fixture **antes** e
  **depois** da extração (script ad-hoc, fora do repo) e comparado o **texto extraído via `pypdf`**
  (mais robusto que hash de bytes, que muda a cada geração por causa do timestamp "Emitido em"/
  metadados internos do ReportLab). Resultado: texto **idêntico**, exceto os 4 timestamps esperados
  (`data_abertura`/"Emitido em" — variam porque os dois PDFs foram gerados em momentos diferentes, não
  por causa do código). Estrutura de páginas (2+2) e contagem de caracteres também idênticas.

#### 13. Strings mágicas no cálculo de progresso — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/modules/inspecoes/service.py:641`):** `if tarefa.status in {"CONCLUIDA", "N/A"}`
  em vez de `StatusTarefaInspecao`.
- **Correção aplicada:** confirmado que `StatusTarefaInspecao.NA.value == "N/A"` (`enums.py:95`); extraída
  constante de módulo `_STATUS_TAREFA_CONCLUIDA = {StatusTarefaInspecao.CONCLUIDA.value,
  StatusTarefaInspecao.NA.value}`. Testes:
  `test_calcular_progresso_considera_concluida_e_na_como_progresso`,
  `test_calcular_progresso_sem_tarefas_nao_divide_por_zero` (função não tinha nenhum teste antes).

#### 14. Limpezas menores — **CONFIRMADO** → ✅ CORRIGIDO (parcial, ver nota)
- `== True` com `# noqa: E712` em `inspecoes/service.py` (6 ocorrências, não 5 como estimado
  originalmente) → `.is_(True)`, comentários `noqa` removidos (deixaram de ser necessários). ✅
- `prorrogar_vencimento` (`vencimentos/service.py`): ternário aninhado numa linha de ~200 colunas
  quebrado em `data_base = vencimento.data_vencimento or dados_prorrogacao.data_concessao` +
  `data_nova_vencimento = data_base + timedelta(days=...)`. ✅
- `ProrrogacaoVencimento`: `relativedelta(days=...)` → `timedelta(days=...)` (import de `timedelta`
  adicionado; `relativedelta` continua em uso em `registrar_execucao`/`associar_controle_a_equipamento`
  para soma de **meses**, onde `timedelta` não serve). ✅
- `montar_matriz_vencimentos`: `date.today()` içado para fora do laço duplo (calculado 1x em `hoje =
  date.today()`) — já resolvido na Fase 2 junto com o item #3, registrado aqui por completude. ✅
- **Não corrigido nesta etapa (decisão consciente):** índice único parcial para "uma só prorrogação ativa
  por controle" (`ProrrogacaoVencimento`, `models.py:88-108`). O plano pedia apenas **avaliar**, não
  corrigir; e como a Fase 3 revelou uma lacuna não investigada na configuração de SAVEPOINT/transação do
  SQLite (ver item #8), adicionar uma nova migration com constraint neste momento — sem entender primeiro
  se `IntegrityError`/rollback estão se comportando corretamente no engine atual — foi considerado
  arriscado demais para um item de prioridade 🟢. Mantido como pendência consciente.
- `== True` em `vencimentos/service.py` (3 ocorrências: L269, L459, L493) — **não corrigido**: não fazia
  parte da evidência original do item #14 (que citava apenas `inspecoes/service.py`); fica registrado
  aqui como achado adicional de baixíssima prioridade para uma eventual varredura futura.

---

## 🗺️ Plano de Ação em Fases

Ordem escolhida para que cada fase feche com a suíte verde e possa ser revertida isoladamente.

### Fase 0 — Baseline (obrigatória, antes de tocar em código)
1. `.venv\Scripts\pytest` → confirmar **261/261** (baseline atual desta branch).
2. Inventariar a cobertura existente: `tests/unit/test_inspecoes.py` (18), `test_inspecao_pdf.py` (9).
   Nenhum arquivo de teste dedicado a `vencimentos` — **confirmar essa lacuna** e tratá-la como risco:
   as mudanças em vencimentos partem de cobertura ~zero.
3. Gerar e arquivar o hash dos 2 PDFs de uma inspeção-fixture (baseline do item #12).

### Fase 1 — Bugs críticos de runtime (menor risco, maior retorno) — ✅ CONCLUÍDA
- Item **#1** (`NotFoundError` → `EntidadeNaoEncontradaError`). ✅
- Item **#2** (remoção do código morto + comentários de IA). ✅
- **Testes:** `test_prorrogar_vencimento_inexistente_levanta_404_nao_500` (`test_vencimentos_criticos.py`).
- ✅ *Checkpoint: suíte verde (271/271 após Fase 1+2 combinadas).*

### Fase 2 — Correção do modelo de status (maior impacto de domínio) — ✅ CONCLUÍDA
- Item **#3** + **#4**: opção **A** escolhida — `calcular_status_vencimento(data_vencimento, hoje)`
  extraída em `vencimentos/service.py`, aplicada em `montar_matriz_vencimentos` e em
  `listar_controles_item` (router, sem mutar o objeto ORM — ver nota abaixo). ✅
- **Pré-requisito verificado:** frontend (`vencimentos.js`) lê `status` do JSON de resposta, não filtra
  via SQL — a derivação em tempo de leitura é segura.
- **Nota de design importante:** o status derivado **não é persistido de volta** no `ControleVencimento`
  durante uma leitura — só é calculado no momento de montar a resposta HTTP. Persistir seria um efeito
  colateral de escrita numa rota GET (a sessão do `get_db` faz commit automático ao fim da requisição),
  o que é surpreendente e arriscado em concorrência. Coberto por
  `test_matriz_nao_persiste_status_derivado_como_efeito_colateral`.
- **Testes:** `test_calcular_status_vencimento_puro`,
  `test_matriz_vencimentos_nao_fica_stale_com_status_persistido_desatualizado`,
  `test_matriz_nao_persiste_status_derivado_como_efeito_colateral`,
  `test_status_derivado_reflete_mudanca_de_periodicidade`.
- ✅ *Checkpoint.*
- **Também executada nesta fase (achado #5, adiantado por eficiência — mesma área de código/testes):**
  ver detalhamento completo na seção do achado #5 acima, incluindo o bug adicional descoberto em
  `panes.service.sincronizar_status_aeronave` e o ajuste em `test_aeronaves.py`.

### Fase 3 — Concorrência e performance — ✅ CONCLUÍDA
- Itens **#6**, **#7** (N+1) e **#8** (TOCTOU/SAVEPOINT). ✅
- **Testes:** contagem de queries nos caminhos otimizados (`_ContadorDeQueries`, listener
  `before_cursor_execute`); criação concorrente de `TipoControle`/`TipoInspecao` levantando conflito de
  domínio em vez de `IntegrityError` cru; sessão permanece utilizável após o `IntegrityError` ser
  absorvido pelo SAVEPOINT.
- **Achado sistêmico não corrigido nesta fase:** ver nota completa no item #8 acima — o SAVEPOINT
  (`db.begin_nested()`) parece não estar isolado corretamente do rollback externo no engine SQLite atual
  (testes e possivelmente produção). Registrado como pendência para a Etapa 5.
- ✅ *Checkpoint (279/279).*

### Fase 4 — Padronização de exceções e contrato HTTP — ✅ CONCLUÍDA
- Item **#10** (36 `ValueError` → `domain_exc`, 14 blocos `try/except` removidos do router). ✅
- Item **#9** verificado como **falso-positivo** (PUT de campo único, semântica de substituição correta) —
  nenhuma correção necessária. ✅
- Item **#11** (teto de paginação). ✅
- ⚠️ **Fase de maior risco de regressão, conforme previsto:** mudou os status codes de várias rotas de
  inspeções (`reordenar_tarefas_template`: 400→409; diversos "não encontrado" que eram 409 viraram 404
  corretamente). 4 testes pré-existentes precisaram ser ajustados de `pytest.raises(ValueError)` para
  `pytest.raises(domain_exc.ConflitoNegocioError)` — verificado que nada no frontend dependia dos códigos
  antigos antes de migrar.
- (Item **#5**, originalmente planejado para esta fase, já havia sido resolvido na Fase 2 por eficiência —
  ver nota lá.)
- ✅ *Checkpoint (279/279).*

### Fase 5 — Limpeza e PDF — ✅ CONCLUÍDA
- Itens **#12** (parcial — queries extraídas, estilos mantidos por decisão consciente), **#13**, **#14**
  (parcial — índice único parcial de prorrogação adiado). ✅
- Baseline de PDF gerado **nesta fase** (não na Fase 0, como o plano original previa) e comparado via
  texto extraído (`pypdf`), não hash de bytes — ver nota completa no item #12.
- ✅ *Checkpoint (281/281).*

### Fase 6 — Consolidação — ✅ CONCLUÍDA
- `docs/backlog/Fable5/relatorio_vencimentos_inspecoes.md` gerado no formato do `prompt.md`.
- `Planejamento_revisao.md` atualizado: linha da Etapa 3 na matriz + seção detalhada + pendências
  conscientes.
- Commit seguindo o padrão das Etapas 1-2.

---

## 🧪 Estratégia de Testes

Seguindo a convenção estabelecida na Etapa 2 (arquivos por faixa de prioridade):

| Arquivo | Cobre |
|---|---|
| `tests/unit/test_vencimentos_criticos.py` (6 testes) | Itens #1, #3, #4 — 404 correto, status derivado, recálculo de periodicidade |
| `tests/unit/test_inspecoes_refatoracao.py` (4 testes) | Item #5 — status da aeronave em concluir/cancelar, inclusive com pane aberta remanescente |
| `tests/unit/test_vencimentos_inspecoes_media_prioridade.py` (8 testes) | Itens #6, #7, #8, #10, #11 — N+1, SAVEPOINT/TOCTOU, contrato HTTP, paginação |
| `tests/unit/test_aeronaves.py` (ajustado) | Corrigido para criar registro real de `Inspecao` em vez de setar `status` manualmente (invariante de domínio) |
| `tests/unit/test_inspecoes.py` (ajustado) | 4 asserts migrados de `ValueError` para `domain_exc.ConflitoNegocioError`; 1 assert de contagem irrestrita trocado por filtro explícito |

| `tests/unit/test_inspecoes_refatoracao.py` (+2, item #13) | `calcular_progresso` com status CONCLUIDA/N/A/PENDENTE e lista vazia |

**Resultado final:** suíte completa **261 (baseline) → 281**, sem regressão. Item #9 verificado como
falso-positivo. Item #12 (PDF) validado por equivalência de texto extraído, não por novo teste automatizado
(os testes existentes de `test_inspecao_pdf.py` já cobrem o contrato de bytes/404 das duas funções).

---

## ⚠️ Riscos Conhecidos desta Etapa

1. **Cobertura quase nula em `vencimentos`** — não há `test_vencimentos.py`. Escrever teste de
   caracterização **antes** de refatorar `montar_matriz_vencimentos`.
2. **Mudança de contrato HTTP** (Fase 4) — o frontend pode tratar 409 explicitamente. Verificar
   `app/web/static/js/` antes de trocar os status codes.
3. **Item #3 é decisão de arquitetura, não só correção** — se houver dúvida entre as opções A e B,
   **parar e consultar** antes de implementar.
4. **`pdf_service.py` sem baseline binário** — não refatorar sem o hash da Fase 0.
5. **Lição da Etapa 2 (não repetir):** não tentar otimizar `db.refresh` populando relações ORM
   manualmente — causou `MissingGreenlet` e foi revertido.
6. **Novo (descoberto na Fase 3):** o padrão SAVEPOINT (`db.begin_nested()`) usado desde a Etapa 1 para
   proteção TOCTOU pode não estar sendo revertido corretamente pelo `rollback()` externo no engine SQLite
   atual (falta a configuração de `isolation_level`/listener de `begin` recomendada pelo SQLAlchemy para
   savepoints funcionarem com `pysqlite`/`aiosqlite`). Não corrigido nesta etapa — ver detalhes no item #8.
   Tratar com prioridade na Etapa 5 antes de assumir que o isolamento de SAVEPOINT é confiável em produção.

---

## ✅ Definition of Done

- [x] Todos os achados 🔴 corrigidos ou explicitamente adiados **com justificativa no relatório**.
- [x] `.venv\Scripts\pytest` = 100% verde, sem testes desabilitados/marcados como skip (281/281).
- [x] `relatorio_vencimentos_inspecoes.md` gerado no formato do `prompt.md`.
- [x] `Planejamento_revisao.md` atualizado (matriz + seção da Etapa 3 + pendências conscientes).
- [x] Zero `print()`/`traceback` novos; logging via `logging.getLogger(__name__)`.
- [x] Zero comentários de proveniência de IA remanescentes no escopo (nenhum foi introduzido nesta etapa).
- [x] Commit com mensagem no padrão das Etapas 1-2.

---
*Plano de execução da Etapa 3 — FABLE 5 / SAA29. Achados levantados em 02/08/2026.*
