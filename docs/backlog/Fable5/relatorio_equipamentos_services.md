# Análise do Código - Melhorias Sugeridas para o arquivo:
app\modules\equipamentos\service.py


O código está bem estruturado, mas identifiquei vários pontos de melhoria. Vou organizá-los por prioridade:

## 🔴 Problemas Críticos (Bugs)

### 1. **Import faltando de `Aeronave`** em `_validar_e_resolver_conflitos`
```python
async def _validar_e_resolver_conflitos(...):
    ...
    res_acft = await db.execute(select(Aeronave.matricula)...)  # ❌ NameError!
```
`Aeronave` só é importado localmente dentro de outras funções. Isso vai gerar `NameError` em runtime.

### 2. **N+1 Query** em `listar_inventario_aeronave`
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

### 3. **`print` + `traceback` em produção**
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

### 4. **Race condition (TOCTOU)** em `criar_modelo` e `_obter_ou_criar_item_por_pn`
O padrão "verificar se existe → criar" não é atômico. Duas requisições simultâneas podem passar na verificação. Garanta **unique constraint** no banco e trate `IntegrityError`:

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(modelo)
    await db.flush()
except IntegrityError:
    raise domain_exc.EntidadeDuplicadaError(f"O Part Number '{part_number}' já está cadastrado.")
```

## 🟡 Problemas de Design

### 5. **Código duplicado de herança de controles**
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

### 6. **Uso inconsistente de exceções**
Mistura `ValueError` com exceções de domínio (`domain_exc`). `ValueError` é genérico demais — crie exceções específicas:

```python
raise domain_exc.RegraDeNegocioError("Não é possível excluir: existem itens físicos...")
raise domain_exc.EntidadeDuplicadaError(f"O Part Number '{part_number}' já está cadastrado.")
```

### 7. **Imports circulares "escondidos"** dentro de funções
```python
from app.modules.aeronaves.service import buscar_aeronave
from app.modules.panes.service import _escape_like
```
- Importar `_escape_like` (função privada de outro módulo) viola encapsulamento. Mova para `app/shared/utils.py`.
- Imports locais indicam acoplamento circular — sinal de que a arquitetura de módulos precisa de revisão (ex: um módulo `shared` para queries comuns).

### 8. **`slot_id or equipamento_id` repetido 3 vezes**
```python
slot_id = dados.slot_id or dados.equipamento_id
```
Resolva isso no **schema** (Pydantic) com um `model_validator`, ou normalize uma única vez no início e passe o valor resolvido às funções auxiliares:

```python
# Em _efetivar_troca_no_slot e _validar_e_resolver_conflitos, 
# receba slot_id: uuid.UUID como parâmetro explícito
```

### 9. **Função `listar_inventario_aeronave` muito longa (~100 linhas)**
Quebre em funções auxiliares: `_buscar_slots_filtrados`, `_mapear_instalacoes_ativas`, `_mapear_aeronaves_anteriores`, `_montar_item_inventario`.

## 🟢 Melhorias Menores

### 10. **`updated_at` manual com `func.now()`**
```python
inst_atual.updated_at = func.now()
```
Configure no modelo com `onupdate=func.now()` para evitar esquecer em algum lugar. Além disso, usar `updated_at` como "data do evento de remoção" é frágil — qualquer update no registro corrompe o histórico. Considere um campo `data_remocao_registrada_em` ou uma tabela de auditoria/eventos.

### 11. **`func.cast` desnecessário no union**
```python
func.cast("INSTALAÇÃO", String)  # prefira:
from sqlalchemy import literal
literal("INSTALAÇÃO").label("tipo_acao")
```

### 12. **Comparação de status como string**
```python
status=StatusVencimento.VENCIDO.value
```
Se as colunas usarem `SQLAlchemy Enum`, passe o enum diretamente (`StatusVencimento.VENCIDO`), ganhando type-safety.

### 13. **Falta de paginação** em `listar_modelos` e `listar_itens`
Com crescimento da base, essas listagens completas vão degradar. Adicione `limit`/`offset`.

### 14. **Normalização de S/N inconsistente**
`ajustar_inventario_item` faz `.strip().upper()` no SN, mas `criar_item_com_heranca` não. Isso pode criar duplicatas lógicas (`"abc123"` vs `"ABC123"`). Normalize no schema Pydantic com um validator.

### 15. **Docstrings ausentes** em várias funções públicas (`listar_itens` tem, mas `buscar_modelo_por_pn`, `remover_item`, etc., não).

---

## Resumo das Prioridades

| Prioridade | Item |
|---|---|
| 🔴 Urgente | Import de `Aeronave` faltando (#1) |
| 🔴 Alta | N+1 query (#2), race conditions (#4) |
| 🟡 Média | Deduplicar herança de controles (#5), exceções (#6), refatorar função longa (#9) |
| 🟢 Baixa | Logging (#3), paginação (#13), normalização (#14) |




SUGESTAO PARA CORRECAO FABLE5:

Plano de Correção — Direcionamento por Falha
🔴 Correções Urgentes
1. Import faltando de Aeronave

Como resolver: Mova o import para o topo do arquivo. Se existir import circular (motivo provável de estar dentro das funções), a solução estruturada é:

Curto prazo: manter import local, mas dentro de _validar_e_resolver_conflitos também.
Definitivo: quebrar o ciclo movendo os modelos para um ponto neutro. Modelos raramente causam ciclo — geralmente o ciclo está entre services. Importe Aeronave de models (não de service) no topo do arquivo, pois models não costumam importar services.
Prevenção: adicione um teste de smoke que simplesmente importa e chama cada função do service (ou use mypy/pyright no CI, que pegaria esse NameError estaticamente).
2. N+1 Query no inventário

Estratégia: substituir a query dentro do loop por uma única query pré-loop usando window function (row_number() over (partition by slot_id)), mesmo padrão que você já usa para ant_map.

Passos:

Antes do loop, execute uma query que traga a "última remoção" de todos os slots da aeronave de uma vez, filtrando rn == 1.
Monte um dicionário slot_id -> (data_rastreio, trigrama).
Dentro do loop, apenas faça lookup no dicionário — zero queries no loop.

Validação: ative echo=True no engine em ambiente de dev (ou use um contador de queries em teste) e confirme que a listagem executa número fixo de queries (~4) independente da quantidade de slots.

3. print + traceback

Como resolver:

Crie logger = logging.getLogger(__name__) no topo do módulo.
Substitua o bloco por logger.exception(...) — ele já inclui o stacktrace automaticamente.
Questione se o try/except deve existir: como ele só re-lança, considere removê-lo e deixar o tratamento para um exception handler global do FastAPI (middleware), que loga qualquer exceção não tratada. Assim você não precisa desse padrão em cada service.
4. Race conditions (verificar → criar)

Estratégia em camadas:

Banco (obrigatório): garanta constraints via migration Alembic:
UNIQUE em modelo_equipamento.part_number
UNIQUE composto em item_equipamento (numero_serie, modelo_id)
Aplicação: mantenha a verificação prévia (dá mensagem de erro amigável no caso comum), mas envolva o flush() em try/except IntegrityError como rede de segurança, convertendo para sua exceção de domínio.
Caso especial _obter_ou_criar_item_por_pn: aqui o padrão correto é get-or-create com retry: se o flush falhar com IntegrityError, faça rollback parcial (savepoint) e busque novamente o item — outra transação o criou.
Alternativa avançada (PostgreSQL): INSERT ... ON CONFLICT DO NOTHING + select, se a concorrência for real e frequente.
🟡 Correções de Design
5. Duplicação da herança de controles

Como resolver: extraia para uma função privada _herdar_controles_do_modelo(db, item) e chame nos dois pontos.

Ponto de atenção arquitetural: essa lógica pertence ao domínio de vencimentos, não de equipamentos. O ideal é expor uma função pública em app/modules/vencimentos/service.py (ex: criar_controles_para_item) e o service de equipamentos apenas chamá-la. Isso mantém a fronteira entre módulos limpa — hoje equipamentos conhece detalhes internos de vencimentos (o status inicial VENCIDO, por exemplo, é uma regra de negócio de vencimentos).

6. Exceções inconsistentes (ValueError vs domínio)

Como resolver:

Faça um inventário das exceções em app/shared/core/exceptions.py e crie as que faltam: EntidadeDuplicadaError, RegraDeNegocioError (ou ConflitoError).
Substitua todos os ValueError por elas — busca global por raise ValueError no projeto.
Registre exception handlers no FastAPI mapeando cada exceção de domínio para o HTTP status correto (409 para duplicada, 404 para não encontrada, 422/400 para regra de negócio). Isso elimina try/except repetitivo nos routers.
7. Imports circulares e _escape_like

Como resolver:

_escape_like: mova para app/shared/utils/db.py (ou similar) como função pública escape_like. Atualize panes e equipamentos para importar de lá. Nunca importe funções com _ de outro módulo.
Ciclo entre services: mapeie as dependências (quem importa quem). Regras práticas:
Services podem importar models de qualquer módulo (models não importam services) → resolve a maioria dos ciclos.
Se um service realmente precisa de lógica de outro (ex: buscar_aeronave), avalie se não é apenas uma query simples que pode ser feita localmente com o model.
Ferramenta de apoio: import-linter no CI para declarar e forçar as regras de dependência entre módulos.
8. slot_id or equipamento_id repetido

Como resolver: resolva uma única vez, o mais cedo possível — idealmente no schema Pydantic:

Adicione um @model_validator(mode="after") em AjusteInventarioCreate que preenche slot_id a partir de equipamento_id se vazio (e falha se ambos forem None).
A partir daí, o service usa apenas dados.slot_id com garantia de valor.
As funções auxiliares (_efetivar_troca_no_slot, _validar_e_resolver_conflitos) passam a receber slot_id: uuid.UUID como parâmetro explícito, em vez do objeto dados inteiro — isso também as torna mais testáveis.
Se equipamento_id é legado, marque como deprecated no schema e planeje remoção.
9. Função listar_inventario_aeronave longa

Como resolver: refatore em etapas, cada uma com responsabilidade única:

_buscar_slots(db, nome) → retorna slots filtrados.
_mapear_instalacoes_ativas(db, aeronave_id) → retorna inst_map.
_mapear_aeronaves_anteriores(db, item_ids, aeronave_id) → retorna ant_map.
_mapear_ultimas_remocoes(db, aeronave_id) → novo, resolve também o item #2.
_montar_linha_inventario(slot, inst_map, ant_map, rem_map) → função pura (sem db), fácil de testar unitariamente.

A função principal vira orquestração de ~15 linhas. Ordem sugerida: faça isso junto com a correção do N+1 (#2), pois são a mesma região de código — evita retrabalho.

🟢 Correções Menores
10. updated_at manual / semântica frágil
Como resolver em duas frentes:

Imediato: adicione onupdate=func.now() na coluna do model e remova as atribuições manuais espalhadas.
Estrutural (recomendado): o problema real é usar updated_at como "data do evento de remoção". Crie uma coluna dedicada (ex: removido_em com timestamp, complementando o data_remocao que é só date) via migration, faça backfill com os valores atuais de updated_at onde data_remocao is not null, e ajuste listar_historico_recente e o inventário para usá-la. Isso blinda o histórico contra updates futuros no registro.

11. func.cast no union
Como resolver: troca direta por literal("INSTALAÇÃO").label("tipo_acao"). Correção de 2 linhas, sem risco.

12. Status como string (.value)
Como resolver: verifique como a coluna está declarada no model:
Se for String, migre para sqlalchemy.Enum(StatusVencimento) (com migration) e passe o enum direto.
Se a migração for arriscada agora, ao menos padronize: sempre .value ou nunca, em todo o projeto, e documente a convenção.

13. Falta de paginação
Como resolver:

Adicione parâmetros limit: int = 50, offset: int = 0 nas funções de listagem, com teto máximo validado no router (ex: le=200 no Query do FastAPI).
Se o frontend precisa do total, retorne também count (uma query select(func.count()) separada) — considere um schema genérico PaginatedResponse[T].
Priorize listar_itens (tende a crescer mais rápido que o catálogo de PNs).

14. Normalização inconsistente de S/N
Como resolver: centralize no schema Pydantic, que é o ponto de entrada único:

1. Adicione @field_validator("numero_serie") com .strip().upper() em ItemEquipamentoCreate e AjusteInventarioCreate.
Remova as normalizações manuais do service (fonte única de verdade).
Dado legado: rode um script/migration de saneamento para normalizar SNs já gravados e detectar duplicatas lógicas existentes antes de criar a unique constraint do item #4 — senão a constraint falha na criação.

15. Docstrings
Como resolver: padronize com foco no que não é óbvio: exceções levantadas e efeitos colaterais (ex: "cria controles de vencimento herdados"). Ative regra de lint (ruff com pydocstyle/regras D) apenas para funções públicas, para não virar burocracia.

📋 Ordem de Execução Sugerida
Fase	Itens	Motivo
1. Hotfix	#1, #11	Bug em produção + correção trivial
2. Fundação	#14 (saneamento) → #4 (constraints) → #6 (exceções)	Constraints dependem de dados limpos; exceções destravam o resto
3. Performance	#2 + #9 juntos	Mesma região de código
4. Arquitetura	#5, #7, #8, #10	Refatorações com migrations
5. Qualidade contínua	#3, #12, #13, #15 + CI (mypy, import-linter, ruff)	Prevenção de regressão

Dica final: antes das fases 3 e 4, escreva testes de integração cobrindo os fluxos atuais (ajustar_inventario_item com os cenários de conflito, listar_inventario_aeronave com slots vazios/ocupados). Eles são sua rede de segurança para refatorar sem medo.