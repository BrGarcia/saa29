arquivo:
app/modules/vencimentos/service.py, app/modules/vencimentos/models.py, app/modules/vencimentos/router.py,
app/modules/inspecoes/service.py, app/modules/inspecoes/models.py, app/modules/inspecoes/router.py,
app/modules/inspecoes/pdf_service.py

> ## ✅ DOCUMENTO FINALIZADO — 02/08/2026
> Todos os itens priorizados (Crítica 5/5, Média 6/6 — sendo #9 falso-positivo verificado, Baixa 3/3 —
> parcial em #12 e #14 por decisão consciente) foram corrigidos e verificados. Suíte completa final:
> **281 testes, 0 falhas** (baseline da etapa: 261). Este relatório é o registro histórico das decisões
> tomadas. O plano de execução detalhado, com o passo a passo de cada fase e as evidências completas de
> verificação, está em `docs/backlog/Fable5/Etapa3.md` — este documento é o resumo no formato de auditoria
> padrão do projeto (`prompt.md`).
>
> **Achado extra descoberto durante a execução (fora do escopo original, registrado como pendência):** o
> padrão SAVEPOINT (`db.begin_nested()`) usado desde a Etapa 1 para proteção TOCTOU parece não estar
> isolado corretamente do `rollback()` externo no engine SQLite atual — uma inserção feita dentro de um
> SAVEPOINT sobreviveu ao rollback de um teste, vazando para o teste seguinte. Consistente com uma lacuna
> de configuração conhecida do SQLAlchemy para savepoints em SQLite (falta desabilitar o `BEGIN` implícito
> do `pysqlite`/`aiosqlite`). Não investigado nem corrigido aqui — recomendado como item dedicado da
> Etapa 5 (bootstrap/database), com um teste de regressão específico antes de qualquer mudança.

---

## 📌 Status de Execução (02/08/2026)

**Todos os itens do relatório foram corrigidos ou verificados: Crítica 5/5, Média 6/6, Baixa 3/3.**

| Item | Prioridade | Status | Onde |
|---|---|---|---|
| #1 `NotFoundError` inexistente (`AttributeError` em runtime) | 🔴 Crítica | ✅ CORRIGIDO | `vencimentos/service.py:prorrogar_vencimento` → `EntidadeNaoEncontradaError` |
| #2 Código morto (`stmt_update` nunca executado) | 🔴 Crítica | ✅ CORRIGIDO | `associar_controle_a_equipamento`, bloco removido |
| #3 Status de vencimento nunca recalculado pelo tempo | 🔴 Crítica | ✅ CORRIGIDO | `calcular_status_vencimento()` derivado em tempo de leitura |
| #4 Recálculo de periodicidade não atualiza status | 🔴 Crítica | ✅ CORRIGIDO | resolvido junto com #3 (status deixou de ser persistido como fonte de verdade) |
| #5 Duplicação de sincronização de status da aeronave | 🔴 Crítica | ✅ CORRIGIDO | `inspecoes.service` delega a `panes.service.sincronizar_status_aeronave` (+ bug de guard corrigido) |
| #6 N+1 em `associar_controle_a_equipamento` | 🟡 Média | ✅ CORRIGIDO | SELECT único com `IN`, subtração de `set` |
| #7 N+1 em `abrir_inspecao` | 🟡 Média | ✅ CORRIGIDO | 2 SELECTs batched (tipos + templates) no lugar de 2N |
| #8 TOCTOU em criações com UNIQUE | 🟡 Média | ✅ CORRIGIDO (5/6; inspeção ativa fica como pendência — sem UNIQUE possível) | SAVEPOINT + `IntegrityError` → exceção de domínio |
| #9 `atualizar_inspecao` apagaria observações em PATCH parcial | 🟡 Média | ✅ VERIFICADO: FALSO-POSITIVO | rota é PUT de campo único; sem correção necessária |
| #10 36 `ValueError` sem tipo + contrato HTTP inconsistente | 🟡 Média | ✅ CORRIGIDO | migrados para `domain_exc`; 14 blocos `try/except` removidos do router |
| #11 Sem teto de paginação em `listar_inspecoes` | 🟡 Média | ✅ CORRIGIDO | `LIMITE_MAXIMO_LISTAGEM = 200`, mesmo padrão da Etapa 1 |
| #12 `pdf_service.py` com queries duplicadas | 🟢 Baixa | ✅ CORRIGIDO (parcial — estilos ReportLab mantidos por decisão consciente) | `_carregar_inspecao_para_pdf` / `_carregar_instalacoes_aeronave` |
| #13 Strings mágicas em `calcular_progresso` | 🟢 Baixa | ✅ CORRIGIDO | `StatusTarefaInspecao` |
| #14 Limpezas menores (`== True`, ternário, `relativedelta`) | 🟢 Baixa | ✅ CORRIGIDO (parcial — índice único de prorrogação adiado) | `.is_(True)`, `timedelta`, `date.today()` içado |

**Arquivos alterados (consolidado — todas as prioridades):**
- `app/modules/vencimentos/service.py`, `router.py`
- `app/modules/inspecoes/service.py`, `router.py`, `pdf_service.py`
- `app/modules/panes/service.py` (função `sincronizar_status_aeronave` tornada pública + bug de guard corrigido, item #5)
- `tests/unit/test_vencimentos_criticos.py` (6 testes — novo)
- `tests/unit/test_inspecoes_refatoracao.py` (6 testes — novo)
- `tests/unit/test_vencimentos_inspecoes_media_prioridade.py` (8 testes — novo)
- `tests/unit/test_aeronaves.py`, `tests/unit/test_inspecoes.py`, `tests/unit/test_panes_alta_prioridade.py`,
  `tests/unit/test_panes_baixa_prioridade.py` (ajustados — ver `Etapa3.md` para detalhes de cada ajuste)

**Suíte completa final:** `.venv\Scripts\pytest` → **281 testes, 0 falhas** (baseline: 261).

**Pendências conscientes que saem do escopo desta etapa** (documentadas, não bloqueiam o fechamento):
- Inspeção ativa duplicada (`abrir_inspecao`) permanece com janela de corrida — não há UNIQUE constraint
  possível para essa regra condicional; exigiria índice único parcial.
- Índice único parcial para "uma só prorrogação ativa por controle" (`ProrrogacaoVencimento`) — avaliado,
  não implementado; adiado por prudência dado o achado sobre SAVEPOINT (ver acima).
- Unificação de estilos `ParagraphStyle` entre `gerar_pdf_ordem_inspecao`/`gerar_pdf_checklist_inspecao` —
  os estilos divergem sutilmente entre as duas funções; risco desproporcional ao ganho para um item 🟢.
- Achado sistêmico do SAVEPOINT/rollback no engine SQLite (ver aviso no topo) — recomendado para Etapa 5.
- `== True` em `vencimentos/service.py` (3 ocorrências) não migradas para `.is_(True)` — fora da evidência
  original do item #14.

---

Relatorio:
Revisão de Código: app/modules/vencimentos/service.py, app/modules/inspecoes/service.py (+ router.py e
pdf_service.py de inspeções)

🔴 Bugs e Problemas Críticos

### [1] AttributeError em runtime: domain_exc.NotFoundError não existe
- **Severidade:** 🔴 Crítica
- **Tipo:** Bug
- **Evidência (`app/modules/vencimentos/service.py:424`, antes da correção):**
  ```python
  vencimento = await db.get(ControleVencimento, vencimento_id)
  if not vencimento:
      raise domain_exc.NotFoundError(detail="Vencimento não encontrado.")
  ```
  `NotFoundError` não existe em `app/shared/core/exceptions.py` (as classes disponíveis são
  `EntidadeNaoEncontradaError`, `ConflitoNegocioError`, `PermissaoNegadaError`).
- **Risco & Impacto:** chamar `prorrogar_vencimento` com um `vencimento_id` inexistente levantava
  `AttributeError` → **HTTP 500** em vez de 404. Nenhum teste cobria esse caminho.
- **Correção Recomendada:** trocar por `domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")`,
  alinhando com `registrar_execucao`. **Aplicada.** Teste: `test_prorrogar_vencimento_inexistente_levanta_404_nao_500`.

### [2] Código morto: update SQL construído e nunca executado
- **Severidade:** 🔴 Crítica
- **Tipo:** Arquitetura / Dívida técnica
- **Evidência (`app/modules/vencimentos/service.py`, `associar_controle_a_equipamento`, antes da correção):**
  um `sqlalchemy.update()` completo era montado em `stmt_update` e **jamais passado a `db.execute()`**;
  logo abaixo a mesma operação era refeita via ORM (única que de fato executava).
- **Risco & Impacto:** ~20 linhas de código morto, incluindo um import local supérfluo e interpolação de
  valor em fragmento SQL (`func.date(..., f'+{periodicidade} months')`) — inócua por ser código morto, mas
  um padrão perigoso de se replicar. Continha também comentários de proveniência de IA no código
  (`"seguiremos a sugestão do auditor Claude"`).
- **Correção Recomendada:** remover o bloco morto por completo, mantendo só o loop ORM funcional.
  **Aplicada.**

### [3] Status de vencimento nunca é recalculado pela passagem do tempo
- **Severidade:** 🔴 Crítica
- **Tipo:** Bug de domínio
- **Evidência:** `ControleVencimento.status` era uma coluna persistida, gravada apenas na criação (sempre
  `VENCIDO`) e em `registrar_execucao`. `montar_matriz_vencimentos` apenas lia o valor gravado
  (`status_final = venc.status`). Nenhum job de recálculo periódico existia.
- **Risco & Impacto:** um controle gravado como `OK` continuava exibido como `OK` mesmo depois de vencido —
  a matriz de vencimentos, artefato central do módulo, ficava desatualizada indefinidamente até alguém
  registrar uma nova execução. Falha de segurança operacional em manutenção aeronáutica, não só cosmética.
- **Correção Recomendada:** derivar o status em tempo de leitura. **Aplicada** — helper puro
  `calcular_status_vencimento(data_vencimento, hoje)` aplicado em `montar_matriz_vencimentos` e
  `listar_controles_item` (router, sem mutar o objeto ORM — mutar deixaria uma leitura GET com efeito
  colateral de escrita). A coluna persistida vira histórico/cache do momento da última execução, não fonte
  de verdade para exibição. Testes: `test_calcular_status_vencimento_puro`,
  `test_matriz_vencimentos_nao_fica_stale_com_status_persistido_desatualizado`,
  `test_matriz_nao_persiste_status_derivado_como_efeito_colateral`.

### [4] Recálculo de periodicidade não atualizava o status
- **Severidade:** 🔴 Crítica (subitem do #3)
- **Tipo:** Bug de domínio
- **Evidência:** ao mudar a periodicidade de um `EquipamentoControle`, `data_vencimento` era recalculada
  mas `status` não — o próprio comentário do código admitia que "seria recalculado na próxima
  visualização", o que não acontecia.
- **Correção Recomendada:** resolvido junto com o #3 — como o status passou a ser derivado a partir de
  `data_vencimento` (que já era recalculada corretamente), o problema desaparece estruturalmente.
  **Aplicada.** Teste: `test_status_derivado_reflete_mudanca_de_periodicidade`.

### [5] Duplicação integral de bloco de sincronização de status da aeronave
- **Severidade:** 🔴 Crítica
- **Tipo:** Arquitetura
- **Evidência:** `concluir_inspecao` e `cancelar_inspecao` (`app/modules/inspecoes/service.py`) continham
  blocos **byte a byte idênticos** para contar inspeções ativas + panes abertas e decidir
  `INDISPONIVEL`/`DISPONIVEL`, com `import` local de `app.modules.panes.models.Pane` dentro da função.
- **Risco & Impacto:** regra de disponibilidade de aeronave divergindo entre os dois caminhos na próxima
  alteração — a mesma classe de bug já corrigida na Etapa 2 (`editar_pane`).
- **Correção Recomendada:** extrair a lógica para uma função compartilhada. **Aplicada** de forma mais
  econômica do que planejado: `panes.service` já continha, desde a Etapa 2, uma função equivalente e mais
  completa (`_sincronizar_status_aeronave_pane`, considerando panes **e** inspeções ativas). Ela foi
  tornada pública (`sincronizar_status_aeronave`) e reutilizada pelos dois pontos de `inspecoes/service.py`
  via um wrapper privado com import tardio (evita ciclo de import).
  **Bug adicional descoberto e corrigido durante essa reutilização:** o guard de `status_str` na função
  reaproveitada impedia a transição para `INDISPONIVEL` quando o status atual já era `INSPECAO` — correto
  quando chamado só por `panes.service` (nunca via essa condição naturalmente), mas incorreto quando
  chamado pelo próprio módulo de inspeções no momento de **concluir/cancelar** a inspeção, pois o status
  gravado nesse instante *ainda* é `INSPECAO` (foi a própria inspeção que o colocou lá). A aeronave ficava
  presa em `INSPECAO` para sempre mesmo com uma pane aberta. Corrigido removendo o guard redundante — a
  checagem de inspeção ativa (consulta ao vivo) já é a fonte de verdade. Capturado por teste de regressão
  **antes** de ir para produção. Testes:
  `test_concluir_inspecao_com_pane_aberta_mantem_aeronave_indisponivel`,
  `test_cancelar_inspecao_com_pane_aberta_mantem_indisponivel`,
  `test_cancelar_inspecao_sem_pendencias_retorna_aeronave_disponivel`,
  `test_concluir_inspecao_mantem_status_inspecao_se_outra_ativa`.

🟡 Problemas de Média Prioridade

### [6] N+1 queries em associar_controle_a_equipamento
- **Severidade:** 🟡 Média
- **Tipo:** Performance
- **Evidência:** carregava todos os itens do modelo e emitia 1 SELECT por item para checar se o
  `ControleVencimento` já existia.
- **Correção Recomendada:** um único `SELECT item_id ... WHERE tipo_controle_id = :t AND item_id IN (...)`,
  subtração de `set` em Python, criação apenas do que falta. **Aplicada.** Teste:
  `test_associar_controle_a_equipamento_nao_gera_n_mais_1`.

### [7] N+1 em abrir_inspecao
- **Severidade:** 🟡 Média
- **Tipo:** Performance
- **Evidência:** `buscar_tipo_inspecao` e `listar_tarefas_template` chamados em loop, 1 query por tipo de
  inspeção selecionado.
- **Correção Recomendada:** 2 SELECTs batched com `IN`, reagrupados em Python preservando a ordem original
  de iteração (necessária para a deduplicação de tarefas por título). **Aplicada.** Testes:
  `test_abrir_inspecao_com_multiplos_tipos_nao_gera_n_mais_1`,
  `test_abrir_inspecao_multiplos_tipos_usa_queries_batched`.

### [8] TOCTOU (check-then-act) em criações com UNIQUE
- **Severidade:** 🟡 Média
- **Tipo:** Concorrência
- **Evidência:** `criar_tipo_controle`, `atualizar_tipo_controle`, `associar_controle_a_equipamento`
  (vencimentos), `criar_tipo_inspecao`, `criar_tarefa_template` (inspeções) faziam SELECT de checagem
  seguido de INSERT sem proteção transacional.
- **Correção Recomendada:** SAVEPOINT (`async with db.begin_nested()`) + captura de `IntegrityError` →
  exceção de domínio, padrão já consolidado nas Etapas 1 e 2. **Aplicada** nas 5 funções citadas.
  **Não corrigido:** duplicidade de inspeção ativa em `abrir_inspecao` — não há UNIQUE constraint possível
  (regra condicional ao status, não par de colunas fixo); precisaria de índice único parcial, fora do
  escopo desta etapa.

### [9] atualizar_inspecao apagaria observações num PATCH parcial
- **Severidade:** 🟡 Média (verificado como falso-positivo)
- **Tipo:** Bug (suspeita não confirmada)
- **Evidência:** `inspecao.observacoes = dados.observacoes` sem `exclude_unset`.
- **Verificação:** a rota é `PUT /{inspecao_id}` com `InspecaoUpdate` tendo **um único campo**
  (`observacoes`). Não existe PATCH para este endpoint. PUT com campo único é semântica de substituição
  total por definição — não há "campo parcial" a preservar.
- **Correção Recomendada:** nenhuma. Falso-positivo confirmado e documentado.

### [10] 36 raise ValueError sem tipo + contrato HTTP inconsistente
- **Severidade:** 🟡 Média
- **Tipo:** Arquitetura
- **Evidência:** o router de inspeções mapeava `ValueError` por posição do bloco `try/except`, não por
  significado — `"Tipo de inspecao nao encontrado"` saía como 409 CONFLICT, e `"Inspecao nao encontrada"`
  ora era 404 ora 409, dependendo do endpoint.
- **Correção Recomendada:** migrar para exceções de domínio tipadas. **Aplicada** — os 36 `raise
  ValueError` foram classificados por conteúdo da mensagem (padrão "não encontrad" → 404; demais → 409) e
  convertidos: 18 viraram `EntidadeNaoEncontradaError`, 18 viraram `ConflitoNegocioError`. 14 dos 16 blocos
  `try/except ValueError` do router foram removidos (as exceções já propagam com o status correto sozinhas).
  Os 2 blocos remanescentes (nos endpoints de PDF) foram mantidos por prudência, já que `pdf_service.py`
  ainda pode legitimamente levantar `ValueError` de bibliotecas internas (fora do escopo revisado).
  `reordenar_tarefas_template` teve seu status mudado de 400 para 409, alinhando com o resto do módulo —
  verificado que nada dependia do código antigo antes de migrar.

### [11] Sem teto de paginação em listar_inspecoes
- **Severidade:** 🟡 Média
- **Tipo:** Performance / Segurança
- **Evidência:** `limit` vinha direto do filtro do cliente, sem clamp no service (o schema tinha
  `le=1000`, mas o service não aplicava teto adicional).
- **Correção Recomendada:** `LIMITE_MAXIMO_LISTAGEM = 200`, mesmo padrão já estabelecido na Etapa 1
  (`equipamentos.service`). **Aplicada.** Teste: `test_listar_inspecoes_respeita_teto_de_seguranca`.

🟢 Problemas de Baixa Prioridade

### [12] pdf_service.py: duas funções monolíticas com forte duplicação
- **Severidade:** 🟢 Baixa
- **Tipo:** Arquitetura
- **Evidência:** `gerar_pdf_ordem_inspecao` (~420 linhas) e `gerar_pdf_checklist_inspecao` (~445 linhas)
  repetiam a query de carregamento da inspeção e a query de instalações da aeronave.
- **Correção Recomendada:** extrair as partes duplicadas. **Aplicada parcialmente** —
  `_carregar_inspecao_para_pdf` e `_carregar_instalacoes_aeronave` extraídas, eliminando as duas queries
  duplicadas. **Não extraída:** a definição de `ParagraphStyle` (~20 estilos) — os tamanhos de fonte
  divergem sutilmente entre as duas funções e o checklist tem estilos/helpers exclusivos; unificar exigiria
  parametrizar cada estilo, risco desproporcional para um item 🟢. Verificada equivalência de saída via
  comparação do texto extraído com `pypdf` antes/depois da extração — idêntico, exceto os timestamps
  esperados de geração.

### [13] Strings mágicas no cálculo de progresso
- **Severidade:** 🟢 Baixa
- **Tipo:** Dívida técnica
- **Evidência:** `if tarefa.status in {"CONCLUIDA", "N/A"}` em vez de usar `StatusTarefaInspecao`.
- **Correção Recomendada:** usar o enum. **Aplicada** — confirmado que `StatusTarefaInspecao.NA.value ==
  "N/A"`; extraída constante de módulo `_STATUS_TAREFA_CONCLUIDA`. Função não tinha nenhum teste antes;
  2 testes novos adicionados.

### [14] Limpezas menores
- **Severidade:** 🟢 Baixa
- **Tipo:** Dívida técnica
- **Evidência e correção:**
  - `== True` com `# noqa: E712` (6 ocorrências em `inspecoes/service.py`) → `.is_(True)`, comentários
    `noqa` removidos. **Aplicada.**
  - Ternário aninhado de ~200 colunas em `prorrogar_vencimento` → quebrado em duas linhas nomeadas.
    **Aplicada.**
  - `relativedelta(days=...)` → `timedelta(days=...)` em `prorrogar_vencimento` (mantido `relativedelta`
    onde a soma é de **meses**, que `timedelta` não cobre). **Aplicada.**
  - `date.today()` recalculado dentro do laço duplo de `montar_matriz_vencimentos` → içado para fora
    (resolvido junto com o item #3). **Aplicada.**
  - Índice único parcial para "uma só prorrogação ativa por controle" — **não corrigido**: o plano pedia
    apenas avaliar; adiado por prudência dado o achado sobre SAVEPOINT/rollback (ver aviso no topo deste
    relatório).
  - `== True` em `vencimentos/service.py` (3 ocorrências) — **não corrigido**: fora da evidência original
    do item, registrado para uma varredura futura.

---

## 📋 Plano de Ação (já executado nesta etapa)

| Fase | Prioridade | Itens |
|---|---|---|
| 1-2 | 🔴 Crítica | #1-#5 |
| 3-4 | 🟡 Média | #6-#11 |
| 5 | 🟢 Baixa | #12-#14 |
| 6 | Consolidação | Este relatório + `Planejamento_revisao.md` |

Detalhamento completo de cada fase, incluindo as evidências de verificação, os testes escritos e as
decisões de escopo tomadas durante a execução, está em `docs/backlog/Fable5/Etapa3.md`.
