# Análise do `inspecoes/service.py`

Vou dividir em: **(1) bugs reais**, **(2) otimizações**, **(3) refatoração estrutural**, com código para os pontos críticos.

---

## 1. Bugs identificados (por severidade)

### 🔴 Bug 1 — `atualizar_tarefa_inspecao` sobrescreve dados de execução em edições repetidas

Se a tarefa já está `CONCLUIDA` e alguém só edita a observação (reenviando status `CONCLUIDA`), o código **sobrescreve `data_execucao` e `executado_por_id`**, perdendo o registro original — grave num contexto de rastreabilidade aeronáutica:

```python
if status_novo in {StatusTarefaInspecao.CONCLUIDA, StatusTarefaInspecao.NA}:
    ...
    tarefa.data_execucao = datetime.now(timezone.utc)  # sempre reatribui!
```

**Correção** — só carimbar na *transição* de status:

```python
transicionou = tarefa.status != status_novo.value

if status_novo in {StatusTarefaInspecao.CONCLUIDA, StatusTarefaInspecao.NA}:
    if not executor_id:
        raise domain_exc.ConflitoNegocioError("Executor obrigatorio para atualizar tarefa.")
    executor = await _buscar_usuario(db, executor_id)
    if not executor:
        raise domain_exc.EntidadeNaoEncontradaError("Executor nao encontrado ou inativo.")
    if transicionou or dados.executado_por_id is not None:
        tarefa.executado_por_id = executor_id
    if transicionou:
        tarefa.data_execucao = datetime.now(timezone.utc)
elif status_novo == StatusTarefaInspecao.PENDENTE:
    tarefa.executado_por_id = None
    tarefa.data_execucao = None
```

### 🔴 Bug 2 — Semântica de PATCH quebrada em `atualizar_tarefa_inspecao` e `atualizar_inspecao`

```python
tarefa.observacao_execucao = dados.observacao_execucao  # apaga se o cliente não enviou
if dados.pane_id:                                       # impossível LIMPAR o pane_id
    tarefa.pane_id = dados.pane_id
```

E em `atualizar_inspecao`:

```python
inspecao.observacoes = dados.observacoes  # None implícito apaga observações
```

**Correção** — usar `exclude_unset` como você já faz nos outros updates:

```python
changes = dados.model_dump(exclude_unset=True)
if "observacao_execucao" in changes:
    tarefa.observacao_execucao = changes["observacao_execucao"]
if "pane_id" in changes:          # agora permite setar E limpar (None)
    tarefa.pane_id = changes["pane_id"]
```

### 🔴 Bug 3 — `abrir_inspecao` aceita IDs de tipo duplicados → linhas duplicadas em `InspecaoEventoTipo`

```python
tipos = [tipos_por_id[tid] for tid in dados.tipos_inspecao_ids]  # duplica se o cliente repetir o ID
...
for tipo in tipos:
    db.add(InspecaoEventoTipo(...))  # insert duplicado → IntegrityError não tratado ou lixo no banco
```

**Correção** — deduplicar preservando ordem (idealmente também via validator no schema):

```python
ids_unicos = list(dict.fromkeys(dados.tipos_inspecao_ids))
```

### 🟠 Bug 4 — `abrir_inspecao` valida templates *depois* de mutar estado

A validação "tipos sem tarefas template" acontece **após** `db.add(inspecao)`, `flush()` e `aeronave.status = INSPECAO`. Você fica dependente do rollback do handler global. Se qualquer caminho commitar (background task, handler que não faz rollback), sobra uma inspeção órfã e aeronave com status errado. **Correção**: mover toda validação (aeronave, usuário, tipos, inspeção ativa, templates) para *antes* de qualquer escrita.

### 🟠 Bug 5 — Deduplicação de tarefas por `titulo` em vez de `tarefa_catalogo_id`

```python
chave = t.tarefa_catalogo.titulo.strip().lower()
```

Duas tarefas de catálogo **distintas** com títulos iguais (ex.: "Inspeção visual" em sistemas diferentes) serão fundidas, e o `tarefa_catalogo_id` gravado será o de uma delas arbitrariamente. Como o vínculo template→catálogo é por FK, o dedupe correto entre tipos é por ID:

```python
chave = t.tarefa_catalogo_id
```

Se o dedupe por título for regra de negócio intencional, ao menos combine: `(t.tarefa_catalogo_id,)` como chave primária de dedupe e título só como fallback documentado.

### 🟡 Bug 6 — Regressão de status da inspeção não tratada

Se a única tarefa executada volta a `PENDENTE`, a inspeção permanece `EM_ANDAMENTO` para sempre. Decisão de negócio, mas vale explicitar:

```python
if status_novo == StatusTarefaInspecao.PENDENTE:
    # opcional: reverter para ABERTA se nenhuma outra tarefa foi executada
    ...
```

### 🟡 Bug 7 — `pane_id` não é validado

`tarefa.pane_id = dados.pane_id` aceita UUID inexistente. Se não houver FK com enforcement no SQLite (`PRAGMA foreign_keys` precisa estar ON na conexão), isso grava lixo silenciosamente.

### 🟡 Bug 8 — Race em `atualizar_tipo_inspecao` (código)

Você protegeu o `criar_tipo_inspecao` com `begin_nested` + `IntegrityError`, mas o update de código usa só check-then-set. Aplique o mesmo padrão.

---

## 2. Otimizações

### `listar_inspecoes` — o maior custo do módulo

`selectinload(Inspecao.tarefas)` numa listagem carrega **todas as tarefas de até 200 inspeções** (potencialmente milhares de linhas) provavelmente só para calcular progresso. Substitua por agregação no banco:

```python
async def listar_inspecoes_com_progresso(
    db: AsyncSession,
    filtros: schemas.FiltroInspecao | None = None,
) -> list[tuple[Inspecao, int, int]]:
    total_sq = (
        select(func.count(InspecaoTarefa.id))
        .where(InspecaoTarefa.inspecao_id == Inspecao.id)
        .correlate(Inspecao)
        .scalar_subquery()
    )
    concluidas_sq = (
        select(func.count(InspecaoTarefa.id))
        .where(
            InspecaoTarefa.inspecao_id == Inspecao.id,
            InspecaoTarefa.status.in_(_STATUS_TAREFA_CONCLUIDA),
        )
        .correlate(Inspecao)
        .scalar_subquery()
    )
    query = (
        select(Inspecao, total_sq.label("total"), concluidas_sq.label("concluidas"))
        .options(selectinload(Inspecao.aeronave), selectinload(Inspecao.tipos_aplicados))
        .order_by(Inspecao.data_abertura.desc())
    )
    # ... filtros como antes ...
    result = await db.execute(query)
    return [(insp, total, concl) for insp, total, concl in result.all()]
```

Outros pontos na mesma função:

- Com o filtro `tipo_inspecao_id` via `join`, adicione **`.distinct()`** por segurança (many-to-many).
- Adicione **desempate na ordenação**: `order_by(Inspecao.data_abertura.desc(), Inspecao.id)` — sem isso a paginação pode pular/repetir itens com o mesmo timestamp.
- Considere retornar `(itens, total)` para o frontend paginar corretamente.

### Recargas completas desnecessárias

O padrão "flush → `buscar_inspecao` completo de novo" aparece 5×. Após `atualizar_inspecao` (que só muda `observacoes`), refazer 6 `selectinload`s é desperdício — o objeto já está carregado e atualizado na sessão. Só recarregue quando a mutação cria/afeta relações (caso de `abrir_inspecao`). Para os demais, retorne o próprio objeto.

E extraia o padrão repetido:

```python
async def _recarregar_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar inspecao.")
    return inspecao

async def _obter_inspecao_editavel(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)
    return inspecao
```

### Updates repetitivos → helper genérico

O padrão `if "campo" in changes and changes["campo"] is not None:` se repete em 4 funções:

```python
def _aplicar_alteracoes(entidade, changes: dict, *, strip: set[str] = frozenset(), anulaveis: set[str] = frozenset()) -> None:
    for campo, valor in changes.items():
        if valor is None and campo not in anulaveis:
            continue
        if isinstance(valor, str) and campo in strip:
            valor = valor.strip()
        setattr(entidade, campo, valor)
```

### `concluir_inspecao` — validação de pendências no banco

Em vez de depender de `inspecao.tarefas` carregado em memória:

```python
pendentes = await db.scalar(
    select(func.count(InspecaoTarefa.id)).where(
        InspecaoTarefa.inspecao_id == inspecao_id,
        InspecaoTarefa.obrigatoria.is_(True),
        InspecaoTarefa.status == StatusTarefaInspecao.PENDENTE.value,
    )
)
if pendentes:
    raise domain_exc.ConflitoNegocioError("Inspecao possui tarefas obrigatorias pendentes.")
```

Mais barato (não carrega as tarefas) e reflete o estado real do banco, não o snapshot da sessão.

---

## 3. Refatoração estrutural

O arquivo mistura **4 agregados diferentes**: tipos de inspeção, catálogo de tarefas, templates e inspeções/execução. Como o módulo é um dos maiores, sugiro promover `service.py` a pacote, mantendo compatibilidade total de imports:

```
app/modules/inspecoes/
├── router.py
├── models.py
├── schemas.py
└── service/
    ├── __init__.py        # re-exporta tudo → nenhum import externo quebra
    ├── _shared.py         # _normalizar_codigo, _buscar_usuario, helpers, constantes
    ├── tipos.py           # CRUD TipoInspecao
    ├── catalogo.py        # CRUD TarefaCatalogo
    ├── templates.py       # CRUD/reordenação TarefaTemplate
    └── inspecoes.py       # abertura, execução, conclusão, cancelamento, progresso
```

```python
# service/__init__.py
from app.modules.inspecoes.service.tipos import *        # noqa: F401,F403
from app.modules.inspecoes.service.catalogo import *     # noqa: F401,F403
from app.modules.inspecoes.service.templates import *    # noqa: F401,F403
from app.modules.inspecoes.service.inspecoes import *    # noqa: F401,F403
```

E o `abrir_inspecao` reescrito com a ordem correta (validar tudo → mutar tudo):

```python
async def abrir_inspecao(db, dados, aberto_por_id) -> Inspecao:
    # ---------- FASE 1: validações (nenhuma escrita) ----------
    ids_tipos = list(dict.fromkeys(dados.tipos_inspecao_ids))          # Bug 3

    aeronave = await _buscar_aeronave(db, dados.aeronave_id)
    if not aeronave:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave nao encontrada.")
    if aeronave.status == StatusAeronave.INATIVA.value:
        raise domain_exc.ConflitoNegocioError("Aeronave inativa. Reative antes de registrar inspecao.")

    tipos = await _resolver_tipos_ativos(db, ids_tipos)
    usuario = await _buscar_usuario_ou_falhar(db, aberto_por_id)
    await _garantir_sem_inspecao_ativa(db, dados.aeronave_id, ids_tipos)

    templates = await _carregar_templates_ordenados(db, tipos)
    if not templates:                                                   # Bug 4: antes de escrever
        raise domain_exc.ConflitoNegocioError("Os tipos de inspecao nao possuem tarefas template cadastradas.")

    # ---------- FASE 2: escrita ----------
    inspecao = Inspecao(..., data_fim_prevista=_calcular_dpe(dados, tipos))
    db.add(inspecao)
    await db.flush()

    db.add_all(InspecaoEventoTipo(inspecao_id=inspecao.id, tipo_inspecao_id=t.id) for t in tipos)
    aeronave.status = StatusAeronave.INSPECAO.value

    for i, (template, obrigatoria) in enumerate(_deduplicar_templates(templates), start=1):  # Bug 5: por catalogo_id
        db.add(InspecaoTarefa(inspecao_id=inspecao.id, ordem=i, obrigatoria=obrigatoria, ...))

    await db.flush()
    return await _recarregar_inspecao(db, inspecao.id)
```

---

## Resumo de prioridades

| # | Item | Tipo | Prioridade |
|---|------|------|-----------|
| 1 | `data_execucao`/executor sobrescritos em re-edição | Bug | Alta |
| 2 | PATCH apaga `observacoes`/`observacao_execucao`; `pane_id` não limpável | Bug | Alta |
| 3 | IDs de tipo duplicados em `abrir_inspecao` | Bug | Alta |
| 4 | Validação de templates após mutação de estado | Bug | Alta |
| 5 | Dedupe por título em vez de `tarefa_catalogo_id` | Bug | Média |
| 6 | Listagem carregando todas as tarefas → agregação SQL | Perf | Alta |
| 7 | Recargas completas desnecessárias após flush | Perf | Média |
| 8 | Ordenação sem desempate na paginação | Bug sutil | Média |
| 9 | Split do service em subpacote | Estrutura | Média |
