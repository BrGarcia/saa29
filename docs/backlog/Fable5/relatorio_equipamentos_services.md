# Análise do Código - Melhorias Sugeridas para o arquivo:
app\modules\equipamentos\service.py

> ## ✅ DOCUMENTO FINALIZADO — 02/08/2026
> Etapa 1 do `Planejamento_revisao.md` (Equipamentos & Inventário). Os 15 itens apontados + 1 bug
> adjacente foram corrigidos e verificados (44/44 testes do escopo; 220/220 na suíte completa).
> Nenhum item foi descartado — os que não fecharam 100% têm decisão consciente registrada inline
> (ver "Pendências conscientes" abaixo). Este relatório não deve mais ser usado como lista de tarefas
> em aberto; consulte-o como registro histórico do que foi decidido e por quê.

O código está bem estruturado, mas identifiquei vários pontos de melhoria. Vou organizá-los por prioridade:

---

## 📌 Status de Execução (atualizado em 02/08/2026)

**Todos os 15 itens do relatório foram endereçados.**

| Item | Status | Onde |
|---|---|---|
| #1 Import de `Aeronave` | ✅ **CORRIGIDO** | `service.py` (topo do arquivo) |
| #2 N+1 query no inventário | ✅ **CORRIGIDO** | `_mapear_ultimas_remocoes` |
| #3 `print` + `traceback` | ✅ **CORRIGIDO** | `logger` de módulo |
| #4 Race conditions | ✅ **CORRIGIDO** | SAVEPOINT + `IntegrityError` |
| #5 Herança de controles duplicada | ✅ **CORRIGIDO** | `vencimentos.service.criar_controles_para_item` |
| #6 Exceções inconsistentes | ✅ **CORRIGIDO** (módulo) | `service.py` + `router.py` sem `ValueError` |
| #7 Imports circulares / `_escape_like` | ✅ **CORRIGIDO** | `app/shared/core/db_utils.escape_like` |
| #8 `slot_id or equipamento_id` | ✅ **CORRIGIDO** | `model_validator` em `AjusteInventarioCreate` |
| #9 Função longa | ✅ **CORRIGIDO** | 5 auxiliares + orquestração |
| #10 `updated_at` como data de remoção | ✅ **CORRIGIDO** | coluna `removido_em` + migration `e7a1c3d9b2f4` |
| #11 `func.cast` no union | ✅ **CORRIGIDO** | `literal("INSTALAÇÃO")` |
| #12 Status como string | ✅ **PADRONIZADO** | sempre `.value` (migration para Enum não feita — ver nota) |
| #13 Falta de paginação | ✅ **CORRIGIDO** | `limit`/`offset` opcionais, teto 200 |
| #14 Normalização de S/N | ✅ **CORRIGIDO** | `Identificador` (schema) + script de saneamento |
| #15 Docstrings | ✅ **CORRIGIDO** | todas as funções públicas do módulo |
| 🆕 Bug adjacente: `/inventario/export` | ✅ **CORRIGIDO** | rota + campos (ver "Achados fora do relatório") |

**Arquivos alterados/criados:**
- `app/modules/equipamentos/service.py` (refatorado), `router.py`, `schemas.py`, `models.py`
- `app/modules/vencimentos/service.py` (+ `criar_controles_para_item`)
- `app/modules/panes/service.py` (usa `escape_like` compartilhado)
- `app/shared/core/db_utils.py` (**novo**)
- `migrations/versions/20260802_1030_e7a1c3d9b2f4_add_removido_em_to_instalacoes.py` (**novo, já aplicado em `var/db`**)
- `scripts/maintenance/sanear_identificadores_equipamentos.py` (**novo**)
- `tests/unit/test_equipamentos_correcoes_urgentes.py` (**novo**, 6 testes)
- `tests/unit/test_equipamentos_refatoracao.py` (**novo**, 20 testes)

**Pendências conscientes** (detalhadas ao final): migration de `String`→`Enum` (#12),
paginação ativa no frontend (#13), `ValueError` nos outros módulos (#6), handler global
de `Exception` (#3) e ferramentas de CI (mypy/import-linter/ruff).

---

## 🔴 Problemas Críticos (Bugs)

### 1. ✅ **Import faltando de `Aeronave`** em `_validar_e_resolver_conflitos`
```python
async def _validar_e_resolver_conflitos(...):
    ...
    res_acft = await db.execute(select(Aeronave.matricula)...)  # ❌ NameError!
```
`Aeronave` só é importado localmente dentro de outras funções. Isso vai gerar `NameError` em runtime.

### 2. ✅ **N+1 Query** em `listar_inventario_aeronave`
Dentro do loop `for slot in slots`, há uma query por slot vazio (`stmt_last_rem`). Com 100 slots vazios, são 100 queries extras:

```python
# ✅ Buscar todas as últimas remoções de uma vez ANTES do loop
subq_rem = (
    select(
        Instalacao.slot_id,
        Instalacao.updated_at,
        Instalacao.created_at,
        Usuario.trigrama,
        func.row_number().over(
            partition_by=Instalacao.slot_id,
            order_by=[desc(Instalacao.updated_at), desc(Instalacao.created_at)]
        ).label("rn")
    )
    .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
    .where(
        Instalacao.aeronave_id == aeronave_id,
        Instalacao.data_remocao.is_not(None)
    )
).subquery()
# Filtrar rn == 1 e montar um dict slot_id -> dados
```

### 3. ✅ **`print` + `traceback` em produção**
```python
except Exception as e:
    import traceback
    print(f"CRITICAL ERROR in listar_inventario_aeronave: {e}")
    traceback.print_exc()
    raise
```
Use `logging` — o `print` se perde em produção e o try/except aqui é praticamente inútil já que só re-lança:

```python
import logging
logger = logging.getLogger(__name__)

# no except:
logger.exception("Erro ao listar inventário da aeronave %s", aeronave_id)
raise
```

### 4. ✅ **Race condition (TOCTOU)** em `criar_modelo` e `_obter_ou_criar_item_por_pn`
O padrão "verificar se existe → criar" não é atômico. Duas requisições simultâneas podem passar na verificação. Garanta **unique constraint** no banco e trate `IntegrityError`:

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(modelo)
    await db.flush()
except IntegrityError:
    raise domain_exc.EntidadeDuplicadaError(f"O Part Number '{part_number}' já está cadastrado.")
```

## 🟡 Problemas de Design — ✅ todos endereçados

### 5. ✅ **Código duplicado de herança de controles**
A lógica de herdar controles existe em `criar_item_com_heranca` e `_obter_ou_criar_item_por_pn`. Extraia:

```python
async def _herdar_controles_do_modelo(db: AsyncSession, item: ItemEquipamento) -> None:
    res_ctrl = await db.execute(
        select(EquipamentoControle).where(EquipamentoControle.modelo_id == item.modelo_id)
    )
    for ctrl in res_ctrl.scalars():
        db.add(ControleVencimento(
            id=uuid.uuid4(),
            item_id=item.id,
            tipo_controle_id=ctrl.tipo_controle_id,
            status=StatusVencimento.VENCIDO.value,
        ))
```

### 6. ✅ **Uso inconsistente de exceções**
Mistura `ValueError` com exceções de domínio (`domain_exc`). `ValueError` é genérico demais — crie exceções específicas:

```python
raise domain_exc.RegraDeNegocioError("Não é possível excluir: existem itens físicos...")
raise domain_exc.EntidadeDuplicadaError(f"O Part Number '{part_number}' já está cadastrado.")
```

### 7. ✅ **Imports circulares "escondidos"** dentro de funções
```python
from app.modules.aeronaves.service import buscar_aeronave
from app.modules.panes.service import _escape_like
```
- Importar `_escape_like` (função privada de outro módulo) viola encapsulamento. Mova para `app/shared/utils.py`.
- Imports locais indicam acoplamento circular — sinal de que a arquitetura de módulos precisa de revisão (ex: um módulo `shared` para queries comuns).

### 8. ✅ **`slot_id or equipamento_id` repetido 3 vezes**
```python
slot_id = dados.slot_id or dados.equipamento_id
```
Resolva isso no **schema** (Pydantic) com um `model_validator`, ou normalize uma única vez no início e passe o valor resolvido às funções auxiliares:

```python
# Em _efetivar_troca_no_slot e _validar_e_resolver_conflitos, 
# receba slot_id: uuid.UUID como parâmetro explícito
```

### 9. ✅ **Função `listar_inventario_aeronave` muito longa (~100 linhas)**
Quebre em funções auxiliares: `_buscar_slots_filtrados`, `_mapear_instalacoes_ativas`, `_mapear_aeronaves_anteriores`, `_montar_item_inventario`.

## 🟢 Melhorias Menores — ✅ todas endereçadas

### 10. ✅ **`updated_at` manual com `func.now()`**
```python
inst_atual.updated_at = func.now()
```
Configure no modelo com `onupdate=func.now()` para evitar esquecer em algum lugar. Além disso, usar `updated_at` como "data do evento de remoção" é frágil — qualquer update no registro corrompe o histórico. Considere um campo `data_remocao_registrada_em` ou uma tabela de auditoria/eventos.

### 11. ✅ **`func.cast` desnecessário no union**
```python
func.cast("INSTALAÇÃO", String)  # prefira:
from sqlalchemy import literal
literal("INSTALAÇÃO").label("tipo_acao")
```

### 12. ✅ **Comparação de status como string**
```python
status=StatusVencimento.VENCIDO.value
```
Se as colunas usarem `SQLAlchemy Enum`, passe o enum diretamente (`StatusVencimento.VENCIDO`), ganhando type-safety.

### 13. ✅ **Falta de paginação** em `listar_modelos` e `listar_itens`
Com crescimento da base, essas listagens completas vão degradar. Adicione `limit`/`offset`.

### 14. ✅ **Normalização de S/N inconsistente**
`ajustar_inventario_item` faz `.strip().upper()` no SN, mas `criar_item_com_heranca` não. Isso pode criar duplicatas lógicas (`"abc123"` vs `"ABC123"`). Normalize no schema Pydantic com um validator.

### 15. ✅ **Docstrings ausentes** em várias funções públicas (`listar_itens` tem, mas `buscar_modelo_por_pn`, `remover_item`, etc., não).

---

## Resumo das Prioridades

| Prioridade | Item | Status |
|---|---|---|
| 🔴 Urgente | Import de `Aeronave` faltando (#1) | ✅ Corrigido |
| 🔴 Alta | N+1 query (#2), race conditions (#4) | ✅ Corrigido |
| 🟡 Média | Deduplicar herança de controles (#5), exceções (#6), refatorar função longa (#9) | ⬜ Pendente |
| 🟢 Baixa | Logging (#3) ✅, paginação (#13), normalização (#14) | ⬜ Parcial (#3 feito) |




SUGESTAO PARA CORRECAO FABLE5:

Plano de Correção — Direcionamento por Falha
🔴 Correções Urgentes — ✅ CONCLUÍDAS (02/08/2026)
1. Import faltando de Aeronave — ✅ CORRIGIDO

Como resolver: Mova o import para o topo do arquivo. Se existir import circular (motivo provável de estar dentro das funções), a solução estruturada é:

Curto prazo: manter import local, mas dentro de _validar_e_resolver_conflitos também.
Definitivo: quebrar o ciclo movendo os modelos para um ponto neutro. Modelos raramente causam ciclo — geralmente o ciclo está entre services. Importe Aeronave de models (não de service) no topo do arquivo, pois models não costumam importar services.
Prevenção: adicione um teste de smoke que simplesmente importa e chama cada função do service (ou use mypy/pyright no CI, que pegaria esse NameError estaticamente).

> **✅ Correção aplicada:** `from app.modules.aeronaves.models import Aeronave` foi para o topo de
> `app/modules/equipamentos/service.py` (solução definitiva: models não importam services, logo não há ciclo).
> Removidos os 2 imports locais redundantes (em `listar_inventario_aeronave` e `listar_historico_recente`).
> Os imports locais de **service** (`buscar_aeronave`, `_escape_like`) foram mantidos — pertencem ao item #7.
> **Regressão:** `TestImportAeronave::test_conflito_de_transferencia_retorna_matricula` exercita exatamente a
> linha que gerava `NameError` (conflito de transferência sem `forcar_transferencia`) e valida a matrícula retornada.

2. N+1 Query no inventário — ✅ CORRIGIDO

Estratégia: substituir a query dentro do loop por uma única query pré-loop usando window function (row_number() over (partition by slot_id)), mesmo padrão que você já usa para ant_map.

Passos:

Antes do loop, execute uma query que traga a "última remoção" de todos os slots da aeronave de uma vez, filtrando rn == 1.
Monte um dicionário slot_id -> (data_rastreio, trigrama).
Dentro do loop, apenas faça lookup no dicionário — zero queries no loop.

Validação: ative echo=True no engine em ambiente de dev (ou use um contador de queries em teste) e confirme que a listagem executa número fixo de queries (~4) independente da quantidade de slots.

> **✅ Correção aplicada:** criada a auxiliar `_mapear_ultimas_remocoes(db, aeronave_id)` (mesmo padrão de window
> function `row_number() over (partition by slot_id)` já usado em `ant_map`), executada **uma vez antes do loop**.
> Dentro do loop restou apenas `rem_map.get(slot.id)` — zero queries por slot. Ordenação preservada
> (`updated_at desc, created_at desc`), portanto o dado de rastreio é idêntico ao da query antiga.
> **Regressão:** `TestInventarioSemNMais1` conta os SELECTs via listener `before_cursor_execute` e prova que
> 3 slots e 15 slots executam **o mesmo número** de queries (≤ 8); um segundo teste garante que slot vazio
> continua exibindo `data_atualizacao` da última remoção.

3. print + traceback — ✅ CORRIGIDO

Como resolver:

Crie logger = logging.getLogger(__name__) no topo do módulo.
Substitua o bloco por logger.exception(...) — ele já inclui o stacktrace automaticamente.
Questione se o try/except deve existir: como ele só re-lança, considere removê-lo e deixar o tratamento para um exception handler global do FastAPI (middleware), que loga qualquer exceção não tratada. Assim você não precisa desse padrão em cada service.

> **✅ Correção aplicada:** `logger = logging.getLogger(__name__)` no topo do módulo; o bloco virou
> `logger.exception("Erro ao listar inventário da aeronave %s", aeronave_id)` + `raise` (stacktrace incluído).
> O `import traceback` local e o `print` foram removidos.
> **Pendência deliberada:** o `try/except` foi mantido porque preserva o contexto (`aeronave_id`) no log.
> Removê-lo depende de um handler global de `Exception` em `setup_exception_handlers`
> (`app/shared/core/exceptions.py` hoje só trata `HTTPException` e `RateLimitExceeded`) — fica para a fase 5.

4. Race conditions (verificar → criar) — ✅ CORRIGIDO

Estratégia em camadas:

Banco (obrigatório): garanta constraints via migration Alembic:
UNIQUE em modelo_equipamento.part_number
UNIQUE composto em item_equipamento (numero_serie, modelo_id)
Aplicação: mantenha a verificação prévia (dá mensagem de erro amigável no caso comum), mas envolva o flush() em try/except IntegrityError como rede de segurança, convertendo para sua exceção de domínio.
Caso especial _obter_ou_criar_item_por_pn: aqui o padrão correto é get-or-create com retry: se o flush falhar com IntegrityError, faça rollback parcial (savepoint) e busque novamente o item — outra transação o criou.
Alternativa avançada (PostgreSQL): INSERT ... ON CONFLICT DO NOTHING + select, se a concorrência for real e frequente.

> **✅ Correção aplicada:**
> - **Banco:** as constraints **já existiam** e não precisaram de nova migration — `modelos_equipamento.part_number`
>   tem índice UNIQUE e `itens_equipamento` tem `UniqueConstraint("modelo_id", "numero_serie", name="uq_item_sn_per_pn")`
>   (ver `models.py` e `migrations/versions/20260418_2233_..._initial_schema_consolidated.py`).
> - **Aplicação:** verificação prévia mantida (mensagem amigável) + `async with db.begin_nested()` (SAVEPOINT)
>   envolvendo o `flush()` em `criar_modelo`, `criar_item_com_heranca` e `_obter_ou_criar_item_por_pn`.
>   `IntegrityError` é convertido em `domain_exc.ConflitoNegocioError` (HTTP 409) nos dois primeiros — antes o
>   caminho concorrente estouraria 500.
> - **Caso `_obter_ou_criar_item_por_pn`:** get-or-create com retry implementado — o SAVEPOINT desfaz só o insert
>   falho e o item criado pela transação concorrente é recuperado via `_buscar_item_por_sn` (nova auxiliar, que
>   também eliminou a duplicação da query de busca por S/N em `criar_item_com_heranca`). Se a re-busca não achar
>   nada, o `IntegrityError` original é re-lançado (não mascara erro real, ex.: FK inválida).
> - **Alternativa PostgreSQL (`ON CONFLICT`) não aplicada:** o projeto é SQLite-only (`app/bootstrap/database.py`).
> **Regressão:** `TestRaceConditions` força o `IntegrityError` (monkeypatch simulando leitura pré-commit
> concorrente) e valida (a) recuperação do item existente, (b) conversão para 409 e (c) que a sessão continua
> utilizável após o rollback do SAVEPOINT — comprovando que SAVEPOINT funciona no aiosqlite deste projeto.

🟡 Correções de Design — ✅ CONCLUÍDAS (02/08/2026)
5. Duplicação da herança de controles

Como resolver: extraia para uma função privada _herdar_controles_do_modelo(db, item) e chame nos dois pontos.

Ponto de atenção arquitetural: essa lógica pertence ao domínio de vencimentos, não de equipamentos. O ideal é expor uma função pública em app/modules/vencimentos/service.py (ex: criar_controles_para_item) e o service de equipamentos apenas chamá-la. Isso mantém a fronteira entre módulos limpa — hoje equipamentos conhece detalhes internos de vencimentos (o status inicial VENCIDO, por exemplo, é uma regra de negócio de vencimentos).

> **✅ Correção aplicada (com o "ponto de atenção arquitetural" adotado):** em vez de uma privada
> `_herdar_controles_do_modelo` em equipamentos, criei a pública
> **`vencimentos.service.criar_controles_para_item(db, item_id, modelo_id)`**. Equipamentos apenas a chama
> nos 2 pontos (`criar_item_com_heranca` e `_obter_ou_criar_item_por_pn`) e deixou de conhecer regras de
> vencimentos — o status inicial `VENCIDO` agora mora no domínio dono da regra.
> Sem ciclo de import: `vencimentos.service` importa apenas *models* de equipamentos, então o import
> pode ficar no topo do arquivo.


6. Exceções inconsistentes (ValueError vs domínio)

Como resolver:

Faça um inventário das exceções em app/shared/core/exceptions.py e crie as que faltam: EntidadeDuplicadaError, RegraDeNegocioError (ou ConflitoError).
Substitua todos os ValueError por elas — busca global por raise ValueError no projeto.
Registre exception handlers no FastAPI mapeando cada exceção de domínio para o HTTP status correto (409 para duplicada, 404 para não encontrada, 422/400 para regra de negócio). Isso elimina try/except repetitivo nos routers.
> **✅ Correção aplicada (escopo: módulo equipamentos):** os 5 `raise ValueError` do service viraram
> `ConflitoNegocioError` (409) e `EntidadeNaoEncontradaError` (404) — exceções que já existiam em
> `app/shared/core/exceptions.py`. Não foram criadas `EntidadeDuplicadaError`/`RegraDeNegocioError`:
> `ConflitoNegocioError` (409) já cobre duplicidade e violação de regra com o status correto.
> **Handlers:** não foi preciso registrar nada novo — as exceções de domínio herdam de `HTTPException`,
> então o FastAPI já as converte. Isso permitiu **remover os try/except de tradução dos routers**
> (`criar_equipamento`, `atualizar_equipamento`, `remover_equipamento`, `criar_item`, `buscar_equipamento`),
> alinhando com o que `tests/architecture/test_architecture_solid.py` já exigia.
> **Mudança de status HTTP:** `remover_modelo` com dependências passou de **400 → 409** (é conflito, não
> requisição malformada). Sem impacto no frontend: `apiFetch` (app.js) exibe `detail` para qualquer status.
> **⬜ Pendente (fora deste módulo):** restam **98 `raise ValueError`** no projeto —
> inspecoes (36), panes (23), aeronaves (12), auth (8), storage (5), calendario (6), config (3),
> vencimentos (3), efetivo (2). Migrar módulo a módulo, usando os testes de cada um como rede.


7. Imports circulares e _escape_like

Como resolver:

_escape_like: mova para app/shared/utils/db.py (ou similar) como função pública escape_like. Atualize panes e equipamentos para importar de lá. Nunca importe funções com _ de outro módulo.
Ciclo entre services: mapeie as dependências (quem importa quem). Regras práticas:
Services podem importar models de qualquer módulo (models não importam services) → resolve a maioria dos ciclos.
Se um service realmente precisa de lógica de outro (ex: buscar_aeronave), avalie se não é apenas uma query simples que pode ser feita localmente com o model.
Ferramenta de apoio: import-linter no CI para declarar e forçar as regras de dependência entre módulos.
> **✅ Correção aplicada:** `escape_like` agora é pública em **`app/shared/core/db_utils.py`**
> (usei `shared/core/` em vez de `shared/utils/` — é onde o projeto já concentra `enums`, `exceptions`,
> `storage` e `file_validators`; o relatório admitia "ou similar"). `panes` e `equipamentos` importam de lá
> e a versão privada `_escape_like` em `panes.service` foi removida.
> **Ciclo entre services eliminado neste módulo:** o import local de `aeronaves.service.buscar_aeronave`
> foi substituído por `_garantir_aeronave_existe`, uma query local com o model `Aeronave` — exatamente o
> caso "é só uma query simples" citado no relatório. `equipamentos/service.py` **não tem mais nenhum
> import dentro de função**. O único import service→service que restou é intencional e acíclico:
> `vencimentos.service.criar_controles_para_item` (ver #5).
> **⬜ Pendente:** `import-linter` no CI para *forçar* a regra — hoje ela está respeitada, mas não verificada.


8. slot_id or equipamento_id repetido

Como resolver: resolva uma única vez, o mais cedo possível — idealmente no schema Pydantic:

Adicione um @model_validator(mode="after") em AjusteInventarioCreate que preenche slot_id a partir de equipamento_id se vazio (e falha se ambos forem None).
A partir daí, o service usa apenas dados.slot_id com garantia de valor.
As funções auxiliares (_efetivar_troca_no_slot, _validar_e_resolver_conflitos) passam a receber slot_id: uuid.UUID como parâmetro explícito, em vez do objeto dados inteiro — isso também as torna mais testáveis.
Se equipamento_id é legado, marque como deprecated no schema e planeje remoção.
> **✅ Correção aplicada:** `@model_validator(mode="after")` em `AjusteInventarioCreate` preenche
> `slot_id` a partir de `equipamento_id` e falha se ambos forem `None`. `equipamento_id` foi marcado
> `DEPRECATED` no schema.
> As auxiliares agora recebem parâmetros explícitos em vez do objeto `dados`:
> `_validar_e_resolver_conflitos(db, item, aeronave_id, slot_id, forcar_transferencia)` e
> `_efetivar_troca_no_slot(db, inst_atual, item_novo, aeronave_id, slot_id, usuario_id)` — mais testáveis.
> **⚠️ Mudança de contrato:** requisição sem nenhum dos dois IDs agora responde **422** (erro de validação)
> em vez de **200 com `sucesso: false`**. É o comportamento correto para campo obrigatório ausente, mas
> vale conferir se algum cliente dependia da resposta 200.


9. Função listar_inventario_aeronave longa

Como resolver: refatore em etapas, cada uma com responsabilidade única:

_buscar_slots(db, nome) → retorna slots filtrados.
_mapear_instalacoes_ativas(db, aeronave_id) → retorna inst_map.
_mapear_aeronaves_anteriores(db, item_ids, aeronave_id) → retorna ant_map.
_mapear_ultimas_remocoes(db, aeronave_id) → novo, resolve também o item #2.
_montar_linha_inventario(slot, inst_map, ant_map, rem_map) → função pura (sem db), fácil de testar unitariamente.

A função principal vira orquestração de ~15 linhas. Ordem sugerida: faça isso junto com a correção do N+1 (#2), pois são a mesma região de código — evita retrabalho.

> **✅ Correção aplicada:** as 5 auxiliares sugeridas foram criadas —
> `_buscar_slots`, `_mapear_instalacoes_ativas`, `_mapear_aeronaves_anteriores`,
> `_mapear_ultimas_remocoes` (feita junto com o #2) e `_montar_linha_inventario` (**pura, sem db**).
> A função principal virou orquestração de ~15 linhas: valida a aeronave, monta os 4 mapas, projeta as linhas.


🟢 Correções Menores — ✅ CONCLUÍDAS (02/08/2026)
10. updated_at manual / semântica frágil
Como resolver em duas frentes:

Imediato: adicione onupdate=func.now() na coluna do model e remova as atribuições manuais espalhadas.
Estrutural (recomendado): o problema real é usar updated_at como "data do evento de remoção". Crie uma coluna dedicada (ex: removido_em com timestamp, complementando o data_remocao que é só date) via migration, faça backfill com os valores atuais de updated_at onde data_remocao is not null, e ajuste listar_historico_recente e o inventário para usá-la. Isso blinda o histórico contra updates futuros no registro.

> **✅ Correção aplicada nas duas frentes:**
> - **Imediato:** o model `Instalacao` já tinha `onupdate=func.now()` em `updated_at`; removi as **5**
>   atribuições manuais de `updated_at = func.now()` espalhadas pelo service.
> - **Estrutural (recomendado):** criada a coluna **`Instalacao.removido_em`** (`DateTime(timezone=True)`,
>   nullable) via migration **`e7a1c3d9b2f4`**, com backfill `COALESCE(updated_at, created_at)` nas linhas
>   com `data_remocao IS NOT NULL`. A escrita foi centralizada em `_registrar_remocao(instalacao, data)` —
>   único lugar que encerra uma instalação, usado pelos 5 caminhos de remoção.
>   `listar_historico_recente` e `_mapear_ultimas_remocoes` passaram a ler `removido_em`.
> **Migration já aplicada** em `var/db` (banco real do ambiente local): 0 linhas removidas existentes,
> backfill foi no-op. Se houver outro ambiente, rodar `alembic upgrade head` **antes** de subir o código —
> o service passou a depender da coluna.
> **Regressão:** teste que altera outro campo do registro após a remoção e verifica que `removido_em`
> permanece intacto — exatamente a corrupção de histórico que o relatório apontou.


11. func.cast no union
Como resolver: troca direta por literal("INSTALAÇÃO").label("tipo_acao"). Correção de 2 linhas, sem risco.

> **✅ Correção aplicada:** `literal("INSTALAÇÃO")` / `literal("REMOÇÃO")` no lugar de
> `func.cast(..., String)`. O import de `String` deixou de ser necessário no módulo.


12. Status como string (.value)
Como resolver: verifique como a coluna está declarada no model:
Se for String, migre para sqlalchemy.Enum(StatusVencimento) (com migration) e passe o enum direto.
Se a migração for arriscada agora, ao menos padronize: sempre .value ou nunca, em todo o projeto, e documente a convenção.

> **✅ Padronizado — migration NÃO feita (decisão consciente):** as colunas são `String(20)`
> (`ItemEquipamento.status`, `ControleVencimento.status`). Migrar para `sqlalchemy.Enum` exigiria migration
> + revisão de todas as comparações em 5+ módulos que hoje comparam string; o ganho é type-safety, não
> correção. Optei pela alternativa que o próprio relatório autoriza: **padronizar sempre `.value`** e
> documentar a convenção no docstring do módulo.
> Ajustes concretos: `_obter_ou_criar_item_por_pn` passava o enum cru (`StatusItem.ATIVO`) — agora usa
> `.value`; `criar_item_com_heranca` deixou de usar `ItemEquipamento(**dados.model_dump())` (que vazava o
> enum do Pydantic para a coluna) e constrói o objeto com campos explícitos.
> **⬜ Pendente:** a migration `String`→`Enum`, se/quando o projeto quiser type-safety no ORM.


13. Falta de paginação
Como resolver:

Adicione parâmetros limit: int = 50, offset: int = 0 nas funções de listagem, com teto máximo validado no router (ex: le=200 no Query do FastAPI).
Se o frontend precisa do total, retorne também count (uma query select(func.count()) separada) — considere um schema genérico PaginatedResponse[T].
Priorize listar_itens (tende a crescer mais rápido que o catálogo de PNs).

> **✅ Capacidade adicionada — default paginado NÃO ativado (decisão consciente):**
> `listar_modelos(db, limit=None, offset=0)` e `listar_itens(db, modelo_id=None, limit=None, offset=0)`,
> com teto `LIMITE_MAXIMO_LISTAGEM = 200` aplicado no service (protege mesmo se o chamador pedir mais)
> e `le=200` no `Query` dos routers.
> **Por que `limit=None` e não `limit=50`:** `configuracoes.js` consome `/equipamentos/` inteiro para montar
> seletores de PN e **não tem controles de paginação**. Um default de 50 truncaria o catálogo silenciosamente
> na UI — regressão funcional pior que o risco de performance (base atual: 26 PNs, 726 S/Ns).
> **⬜ Pendente:** paginar de fato exige frontend (controles + `count`). Quando houver, avaliar o
> `PaginatedResponse[T]` sugerido e ligar o default em `listar_itens` primeiro (cresce mais rápido).


14. Normalização inconsistente de S/N
Como resolver: centralize no schema Pydantic, que é o ponto de entrada único:

1. Adicione @field_validator("numero_serie") com .strip().upper() em ItemEquipamentoCreate e AjusteInventarioCreate.
Remova as normalizações manuais do service (fonte única de verdade).
Dado legado: rode um script/migration de saneamento para normalizar SNs já gravados e detectar duplicatas lógicas existentes antes de criar a unique constraint do item #4 — senão a constraint falha na criação.

> **✅ Correção aplicada:** criado o tipo `Identificador = Annotated[str, AfterValidator(...)]` em
> `schemas.py` (fonte única) e aplicado a `ModeloEquipamentoCreate.part_number`,
> `ModeloEquipamentoUpdate.part_number`, `ItemEquipamentoCreate.numero_serie` e
> `AjusteInventarioCreate.numero_serie_real`. Os `.strip().upper()` manuais saíram do service.
> Isso **corrige a inconsistência real**: `criar_item_com_heranca` não normalizava e aceitava "abc" + "ABC"
> como itens distintos. `xlsx_service` não foi afetado — já monta `AjusteInventarioCreate` e herda a normalização.
> **Dado legado:** criado `scripts/maintenance/sanear_identificadores_equipamentos.py` (diagnóstico por
> padrão, `--apply` para gravar; reporta colisões que exigem mesclagem manual de histórico).
> **Executado em 02/08/2026:** 26 PNs e 726 S/Ns analisados — **0 fora do padrão, 0 colisões**. A base já
> estava limpa, então a mudança não tem risco retroativo.


15. Docstrings
Como resolver: padronize com foco no que não é óbvio: exceções levantadas e efeitos colaterais (ex: "cria controles de vencimento herdados"). Ative regra de lint (ruff com pydocstyle/regras D) apenas para funções públicas, para não virar burocracia.

> **✅ Correção aplicada:** docstrings em todas as funções públicas do módulo, focadas no que não é óbvio —
> exceções levantadas (seção `Raises:`) e efeitos colaterais (ex.: "cria os controles de vencimento
> herdados", "encerra instalações anteriores, inclusive em outra aeronave"). O docstring do módulo passou a
> registrar as 3 convenções (normalização no schema, exceções de domínio, `.value` nos status).
> **⬜ Pendente:** ligar `ruff` com regras `D` restritas a funções públicas, para não regredir.


📋 Ordem de Execução Sugerida — ✅ TODAS AS FASES CONCLUÍDAS (02/08/2026)
Fase	Itens	Motivo	Status
1. Hotfix	#1, #11	Bug em produção + correção trivial	✅
2. Fundação	#14 (saneamento) → #4 (constraints) → #6 (exceções)	Constraints dependem de dados limpos; exceções destravam o resto	✅
3. Performance	#2 + #9	Mesma região de código	✅
4. Arquitetura	#5, #7, #8, #10	Refatorações com migrations	✅
5. Qualidade contínua	#3, #12, #13, #15	Prevenção de regressão	✅ (código); ⬜ CI (mypy, import-linter, ruff) não configurado

Dica final: antes das fases 3 e 4, escreva testes de integração cobrindo os fluxos atuais (ajustar_inventario_item com os cenários de conflito, listar_inventario_aeronave com slots vazios/ocupados). Eles são sua rede de segurança para refatorar sem medo.

> **✅ Seguido à risca:** `tests/unit/test_equipamentos_correcoes_urgentes.py` e
> `tests/unit/test_equipamentos_refatoracao.py` foram escritos e executados a cada fase, antes de avançar
> para a próxima — nenhuma fase começou com a anterior quebrada.

---

## 🔎 Notas gerais da execução (02/08/2026)

**Todas as 5 fases da "Ordem de Execução Sugerida" foram concluídas nesta sessão**, em duas etapas:
1. Fase 1 (hotfix): itens #1–#4 — ver seção "🔴 Correções Urgentes" acima.
2. Fases 2–5: itens #5–#15 + o bug adjacente do `/inventario/export` — notas inline em cada item acima.

**Arquivos alterados/criados (visão consolidada):**
- `app/modules/equipamentos/service.py` — reescrito: todas as 15 correções + orquestração enxuta.
- `app/modules/equipamentos/router.py` — sem try/except de tradução; rota `/export` reordenada e corrigida.
- `app/modules/equipamentos/schemas.py` — tipo `Identificador` (normalização) + resolução de `slot_id`.
- `app/modules/equipamentos/models.py` — coluna `Instalacao.removido_em`.
- `app/modules/vencimentos/service.py` — nova função pública `criar_controles_para_item`.
- `app/modules/panes/service.py` — usa `escape_like` compartilhado (sem duplicar a função).
- `app/shared/core/db_utils.py` — **novo módulo**.
- `migrations/versions/20260802_1030_e7a1c3d9b2f4_add_removido_em_to_instalacoes.py` — **novo, já aplicado em `var/db`**.
- `scripts/maintenance/sanear_identificadores_equipamentos.py` — **novo**, já executado (0 achados).
- `tests/unit/test_equipamentos_correcoes_urgentes.py` — **novo**, 6 testes (itens #1–#4).
- `tests/unit/test_equipamentos_refatoracao.py` — **novo**, 20 testes (itens #5–#15 + bug do export).

**Suíte completa após todas as correções:** `pytest tests/unit tests/architecture tests/test_calendario.py
tests/test_exporter.py` → **220 testes, 0 falhas**.

**Migration pendente de aplicar em outros ambientes:** `e7a1c3d9b2f4` foi rodada em `var/db` (banco local
deste ambiente). Qualquer outro ambiente (staging/produção) precisa de `alembic upgrade head` antes do
deploy do novo código — o service passou a gravar em `Instalacao.removido_em`.

**Pendências conscientes que sobreviveram à sessão (não são bugs, são escopo adiado):**
- `raise ValueError` ainda presente em outros módulos (98 ocorrências fora de equipamentos) — item #6 corrigido
  apenas no módulo do relatório.
- Migration `String` → `sqlalchemy.Enum` para colunas de status (item #12) — mantido `.value` padronizado.
- Paginação (`limit`/`offset`) existe nos services/routers mas **não está ativada por padrão** nem tem
  suporte no frontend (item #13) — evita truncar seletores hoje.
- Ferramentas de CI (mypy, import-linter, ruff com regras D) citadas nos itens #1, #7, #15 não foram
  configuradas — ficam para uma tarefa de infraestrutura de qualidade à parte.