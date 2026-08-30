# 📋 Plano de Implementação — Gestão de Slots, Itens e Auditoria de Dados Mestres do Inventário

> **Versão:** 1.6
> **Data:** 2026-08-30 (v1.0 em 2026-08-19)
> **Referência:** `docs/BACKLOG/modulo_inventario/enhange_gerenciar_inventario.md` (SPEC-CONF-001 v2.1)
> **Status:** 🟢 Pronto para execução
> **Escopo deste documento:** passo a passo técnico para fechar os buracos de CRUD em `slots_inventario` e `itens_equipamento`, corrigir o bug de integração do `posicao_xlsx`, e introduzir a tabela de auditoria de dados mestres `auditoria_dados_mestres`. Tudo dentro do módulo `app/modules/equipamentos/` já existente — não é criado um módulo novo.

> ✅ **Nota de revisão (v1.5 — 2026-08-30):** acrescentado o **PR-0** (Seção 0.2). A medição da linha de base mostrou que `development` já estava vermelho antes desta feature: `ruff check .` com 11 erros (CI reprovando desde 21/08) e 4 falhas de `pytest` por contaminação entre testes. Sem isso corrigido, o critério "a suíte continua verde" da Etapa 11 era immensurável e o portão de CI não distinguia quebra nova de quebra preexistente. **PR-0 já executado e verde** — ver Seção 0.2.

> ✅ **Nota de revisão (v1.4 — 2026-08-30):** **portão 1 do PR-3 satisfeito** — o pré-check foi executado no banco de produção da VPS: 33 slots, **0 duplicidades**, **0 nulos**, e `alembic_version = 2676d7fdd987` (produção já está no head do repositório). O risco R14 cai de Alta para Baixa. Os dois portões permanecem, com uma ressalva nova: o pré-check é um retrato de um instante e `POST /equipamentos/slots/` continua aberto para ADMIN — **reexecutar imediatamente antes do merge do PR-3**.

> ⚠️ **Nota de revisão (v1.3 — 2026-08-30):** as exclusões deixam de usar `DELETE` com corpo JSON e passam a `POST /{id}/remover` com corpo. Motivo: a v1.1/v1.2 afirmava que `pedidos` era precedente de `DELETE`-com-body — **é falso**. Nenhum dos 10 endpoints `@router.delete` do projeto recebe body, e `pedidos` faz justamente o contrário (`POST /{id}/cancelar` com corpo em `router.py:208`, `DELETE /{id}` sem corpo em `:223`). Efeito colateral bem-vindo: `DELETE /equipamentos/{id}` não precisa mais mudar de assinatura, e a quebra de contrato que estava em aberto para decisão deixa de existir.

> ⚠️ **Nota de revisão (v1.2 — 2026-08-30):** a entrega foi **fatiada em 3 PRs** (Seção 0.1) depois que a inspeção do pipeline mostrou que a migration chega a produção sem porteiro manual. A alteração destrutiva de schema (`NOT NULL` + `UNIQUE`) foi isolada no PR-3 para poder ser revertida sozinha, e a correção do bug do XLSX foi antecipada para o PR-1 sem depender dela.

> ⚠️ **Nota de revisão (v1.1 — 2026-08-30):** a v1.0 foi re-verificada contra o código e corrigida em sete pontos: `down_revision` (Etapa 3), tipos `sa.Uuid()` na migration (Etapa 3), serialização JSON da auditoria (Etapa 5), bloqueio de exclusão de item por `ControleVencimento` (Etapa 6), filtro de inativos em `listar_slots` — não só em `_buscar_slots` (Etapa 6), efeito real de `ordem_exibicao` sobre o `sort` em Python (Etapa 6), e reativação de slot (Etapas 4/6/7). Acrescentada a Etapa 11 (adequação das suítes existentes), que a v1.0 tratava erradamente como "sem alteração".

> ⚠️ **Nota de coordenação:** este plano edita arquivos **compartilhados**: `app/shared/core/enums.py`, `app/web/templates/configuracoes.html`. A tabela nova (`AuditoriaDadosMestres`) fica dentro de `app/modules/equipamentos/models.py`, que já é importado em `migrations/env.py:27` e `app/bootstrap/main.py:18` — por isso **não é preciso editar nenhum dos dois**. Se outra frente estiver mexendo em `enums.py` ou no template de Configurações em paralelo, reconferir antes de abrir PR.

---

## 0. Visão do que será construído

Ao final deste plano:

- `slots_inventario` terá CRUD completo (hoje só tem `POST`): `PATCH`, remoção via `POST /{id}/remover`, inativar, **reativar**, consultar ocupação.
- `itens_equipamento` terá CRUD completo (hoje só tem `POST`): `PATCH`, remoção via `POST /{id}/remover`.
- O bug de integração do XLSX é corrigido: `posicao_xlsx` passa a ser obrigatório na criação de slot, então todo slot cadastrado pela API casa corretamente com a planilha de importação.
- Toda escrita em `modelos_equipamento`, `slots_inventario` e `itens_equipamento` grava um registro em `auditoria_dados_mestres` (nova tabela, append-only).
- A UI de Configurações ganha um modal "Gerenciar Slots" no card já existente "Equipamentos e PNs", mais um botão "Histórico" nas linhas do catálogo de PNs.
- Nada muda no comportamento de `/inventario`, no fluxo de "Sincronizar" (`ajustar_inventario_item`) nem na importação XLSX além do que está listado acima — RNF-08 da spec.

**Explicitamente fora deste plano** (ver Seção 15 da spec): persistir `sn_siloms`/`sn_real` como colunas separadas; refatorar os seeds para upsert idempotente; *optimistic locking*; *maker-checker*.

---

## 0.1 Estratégia de entrega — 3 PRs

### Por que fatiar

O pipeline **migra produção sozinho, sem porteiro manual**:

```
.github/workflows/deploy.yml:44   docker-compose exec -T web python -m alembic upgrade head
scripts/start.sh:28               python -m alembic upgrade head      # sob `set -e`
```

A migration roda no deploy **e de novo a cada start do container**. Com `set -e`, uma migration que falha não degrada — **o container não sobe**. Se a `UNIQUE (nome_posicao, sistema)` encontrar uma duplicata na VPS, ou houver `sistema`/`posicao_xlsx` nulo lá, o merge em `main` derruba a aplicação.

Daí a regra que organiza os três PRs: **o que é aditivo pode ir junto; o que é destrutivo vai sozinho, para poder ser revertido sozinho.**

### O insight que barateia o PR-1

A correção do bug do XLSX **não depende da coluna `NOT NULL`**. O bug é "slot criado pela API nasce com `posicao_xlsx = NULL` e nunca casa com a planilha". Tornar o campo obrigatório no **schema Pydantic** já fecha isso por completo: a API deixa de aceitar a criação sem o campo. O `NOT NULL` no banco é cinto-e-suspensório — e é ele, sozinho, que arrasta o backfill, a UNIQUE, a reescrita de 18 testes e todo o risco em produção.

Por isso o PR-1 entrega o valor do bug fix com risco de migration quase zero.

### Os três PRs

*(precedidos pelo PR-0 — Seção 0.2)*

| PR | Etapas | Conteúdo | Migration | Risco |
|---|---|---|---|---|
| **PR-1** — *base aditiva* | 1, 2, 3a, 4, 5, 8 | Enums; `AuditoriaDadosMestres`; colunas novas de slot (`descricao`, `ordem_exibicao`, `ativo`, `created_at`, `updated_at`) **todas nullable ou com default**; `posicao_xlsx`/`sistema` obrigatórios **só no schema Pydantic**; `auditoria_service`; filtro `ativo` no XLSX; **+ ajuste dos 2 testes de API** que criam slot sem `posicao_xlsx` (`test_equipamentos.py:239`, `:266`) | `create_table` + `add_column` — nenhuma alteração destrutiva | **Baixo** |
| **PR-2** — *funcionalidade* | 6, 7, 9, 10 | CRUD de slots e itens, reativação, auditoria nas escritas, endpoints novos, UI, testes novos | nenhuma | **Baixo** — rotas novas, aditivas |
| **PR-3** — *aperto de schema* | 3b, 11 | `sistema`/`posicao_xlsx` → `NOT NULL`; `UNIQUE uq_slot_nome_sistema`; `created_at` → `NOT NULL`; adequação das 20 construções de slot nas suítes e seeds | **destrutiva — isolada** | **Alto** |

**Ordem dentro de cada PR:** PR-1 `1 → 2 → 3a → 4 → 5 → 8`; PR-2 `6 → 7 → 9 → 10`; PR-3 `3b → 11`.

> **Nota sobre a Etapa 2 (models):** as colunas de `SlotInventario` são declaradas com o tipo final já no PR-1, **exceto** `sistema`, `posicao_xlsx` e `created_at`, que permanecem `nullable=True` no ORM até o PR-3. Manter o ORM à frente do banco faria o `--autogenerate` do PR-2 tentar gerar a alteração destrutiva por conta própria.

### Portões obrigatórios do PR-3

Só o PR-3 precisa disto — e precisa dos dois, não de um:

1. ✅ **Pré-check no banco de PRODUÇÃO** — **executado em 2026-08-30**:

   | Métrica | Produção (VPS) | Local |
   |---|---|---|
   | Slots | 33 | 33 |
   | Duplicidades `(nome_posicao, sistema)` | **0** | 0 |
   | Nulos em `sistema`/`posicao_xlsx` | **0** | 0 |
   | `alembic_version` | **`2676d7fdd987`** (head do repo) | `b63e385e3395` (uma atrás) |

   O caminho está livre: a UNIQUE não encontra obstáculo e o backfill da 3b será um no-op. Produção estar no head do repositório também confirma que não há migrations acumuladas a aplicar antes da nova, e que `down_revision = "2676d7fdd987"` está correto.

   ⚠️ **Reexecutar imediatamente antes do merge do PR-3.** O resultado acima é um retrato de um instante, e `POST /equipamentos/slots/` segue aberto para ADMIN — um slot criado entre hoje e o merge pode introduzir a duplicata que hoje não existe. O comando:
   ```sql
   SELECT nome_posicao, sistema, COUNT(*) FROM slots_inventario GROUP BY 1,2 HAVING COUNT(*) > 1;
   SELECT COUNT(*) FROM slots_inventario WHERE sistema IS NULL OR posicao_xlsx IS NULL;
   ```
   Se qualquer uma retornar linha, **sanear antes** — o backfill do `upgrade()` resolve nulo, **não** resolve duplicata.

2. **Snapshot manual antes do deploy.** Ver Seção 16 (Rollback): o backup automático para o R2 é *debounced por escrita* e sobrescreve o estado pré-migration segundos depois. Ele não serve como ponto de retorno.

**A favor:** o CI roda `pytest` antes de fazer deploy (`deploy.yml:28-30`). Se a Etapa 11 ficar incompleta, o deploy é **bloqueado**, não quebrado — a suíte é um portão real, não apenas uma formalidade.

---

## 0.2 PR-0 — linha de base verde *(pré-requisito, já executado)*

Antes de medir "a suíte continua verde", era preciso que ela estivesse verde. Não estava.

### Diagnóstico (2026-08-30)

| Sintoma | Medição |
|---|---|
| `ruff check .` | **11 erros** — CI (`ci.yml`) reprovando em 5 de 5 execuções desde 2026-08-21, morrendo no lint **antes** de chegar ao pytest |
| `pytest -q` (suíte completa) | **1 failed + 3 errors**, determinístico em duas execuções |
| `pytest` dos mesmos arquivos isolados | **57 passed** — ou seja, contaminação entre testes, não comportamento quebrado |
| `pytest -q --ignore=tests/security/test_login_csrf.py` | **767 passed** — arquivo isolado como causa única das 4 falhas |

**Causa raiz da contaminação:** o endpoint de login faz `db.commit()` explícito (`app/modules/auth/router.py:59`, e também nos caminhos de tentativa falha do rate limiting em `:198`/`:224`). Commit não é desfeito pelo `rollback` da fixture `db` (`tests/conftest.py:122-127`), então o usuário criado por `tests/security/test_login_csrf.py` — que reusava o `joao.silva` de `dados_usuario_valido` — **sobrevivia ao teste** e quebrava `tests/unit/test_auth.py::TestLogin::test_login_sucesso` com `UNIQUE constraint failed: usuarios.username`. Só na suíte completa; nunca com o arquivo rodando sozinho. O arquivo veio dos commits de CSRF/rate-limiting de 2026-08-23, ainda não mesclados em `main`.

**Por que importava para esta feature:** `deploy.yml` roda `pytest` antes de publicar na VPS. Com `development` vermelho, o merge em `main` faria o deploy falhar — e, pior, ninguém conseguiria distinguir uma regressão nova da quebra preexistente. O "portão de CI" que a Seção 0.1 credita como rede de segurança existia, mas estava travado.

### Correções aplicadas

| Arquivo | Correção |
|---|---|
| `tests/security/test_login_csrf.py` | Fixture `usuario_csrf` com **username único** (evita a colisão) e **DELETE no teardown** (evita o acúmulo). `TokenRefresh.usuario_id` tem `ondelete=CASCADE`, então os tokens do login saem junto |
| 5 erros F401/E401 | `ruff check . --fix` — imports não usados e import múltiplo em uma linha |
| `publicacoes/router.py:883`, `zipar_disco.py:130` | B904 — `raise ... from exc`, preservando a causa na cadeia |
| `publicacoes/router.py:944` | S110 — `try/except/pass` na limpeza de multipart passa a **logar**: engolir em silêncio escondia multipart órfão ocupando espaço no R2 |
| `publicacoes/service.py:1375` | F821 — import de `PublicacoesUploadJob` sob `TYPE_CHECKING` (o módulo já tem `from __future__ import annotations`; faltava o nome existir para o checker) |
| `scripts/publicacoes/publicar.py:382` | F821 — `import uuid` no topo; existia só dentro da função, como `uuid_mod` |
| `tests/unit/test_publicacoes_upload_job.py:77` | B017 — `pytest.raises(Exception)` → `pytest.raises(IntegrityError)`; o genérico passaria até com um erro de teste mal escrito |

### Resultado verificado

```
ruff check .   → All checks passed!          (ruff==0.16.1, a versão fixada em requirements-dev.txt)
pytest -q      → 770 passed, 3 skipped       (era: 1 failed, 3 errors)
```

**Confirmado no CI** (run 33329608657): `All checks passed!` no lint e `770 passed, 3 skipped in 139.03s` — os mesmos números do local.

### O que o PR-0 desentocou — e resolveu: travamento no encerramento do processo

Com o lint corrigido, o job passou a **chegar** ao pytest pela primeira vez em 9 dias — e revelou um bug pré-existente: a suíte termina, imprime o resultado, e **o processo não sai**. O job morria no teto de 15min (`ci.yml`); antes desse teto existir, morreu duas vezes no limite de 6h do Actions.

Não era regressão desta feature: o comentário do `ci.yml:12-18` já registrava as duas ocorrências anteriores. Ficou invisível desde 21/08 porque o job morria no ruff aos 36s, antes de chegar ao pytest.

#### Como foi diagnosticado

O `conftest.py` já tinha um diagnóstico plantado, mas ele rodava cedo demais (logo após fechar a engine de teste) e nunca imprimia nada. Foi substituído por um **watchdog** no hook `pytest_sessionfinish`: um timer daemon que, se o processo não encerrar em `SAA29_TIMEOUT_ENCERRAMENTO` segundos (padrão 120), despeja o stack de **todas** as threads e encerra com o **status real da suíte**.

O watchdog foi validado em quatro cenários antes de ser usado — sendo o último o que realmente importava, porque um watchdog que saísse sempre `0` tornaria o CI incapaz de reprovar:

| Prova | Cenário | Resultado |
|---|---|---|
| 1 | Suíte verde, watchdog disparando | Despeja stacks, sai com **0** |
| 2 | Nenhum teste coletado | `exit 5` do próprio pytest, watchdog não interfere |
| 3 | Suíte completa, timeout padrão | 770 passed, `exit 0`, watchdog **não dispara** |
| 4b | Suíte **vermelha** + encerramento travado | Despeja stacks, sai com **1** — não mascara a falha |

Na primeira execução real (run `33332855429`) o despejo nomeou o culpado:

```
Thread principal:  threading.py:1624 in _shutdown
Outra thread viva: aiosqlite/core.py:59 in _connection_worker_thread
```

#### Causa raiz

`aiosqlite/core.py:90` cria a thread da conexão **sem** `daemon=True`. Thread não-daemon faz `threading._shutdown()` esperar por ela indefinidamente. Bastava uma conexão SQLite não fechada para o processo nunca sair.

E havia **duas** engines na suíte, não uma:

| Engine | Onde | Era fechada? |
|---|---|---|
| De teste | `tests/conftest.py:44` | Sim, em `:148` |
| Da aplicação | `app/bootstrap/database.py:35` | **Não** — por ninguém |

A função `dispose_engine()` já existia em `app/bootstrap/database.py:94`; só nunca era chamada pela suíte. Confirmado por instrumentação temporária que a engine da aplicação **é** instanciada na suíte completa (embora não em subconjuntos pequenos), então a chamada não é inócua.

#### Correção e prova

```python
# tests/conftest.py — teardown da sessão
await test_engine.dispose()   # já existia
await dispose_engine()        # novo
```

| Run | Duração | Resultado |
|---|---|---|
| `33329608657` | 15m19s | ❌ cancelado no teto — processo pendurado |
| `33332855429` | 5m01s | ✅ verde, mas travou e o watchdog encerrou aos 120s |
| `33333644525` | **2m45s** | ✅ verde, **zero disparos do watchdog** — processo encerra sozinho |

Resolvido na causa, não contornado. O watchdog permanece instalado e inativo, como rede de segurança para vazamentos futuros.

> **Nota para quem for rodar o lint local:** `requirements-dev.txt:20` fixa `ruff==0.16.1` deliberadamente — o comentário no arquivo registra que o CI antes instalava sem pin e "o resultado do lint mudava sem ninguém tocar em código". Usar outra versão reintroduz esse problema.

---

## 1. Mapa de arquivos

| PR | Arquivo | Ação | Observação |
|---|---|---|---|
| 1 | `app/shared/core/enums.py` | **editar** | + `EntidadeAuditada`, `AcaoAuditoria` |
| 1 / 3 | `app/modules/equipamentos/models.py` | **editar** | PR-1: colunas novas de `SlotInventario` + classe `AuditoriaDadosMestres`. PR-3: aperto de nulabilidade + `UniqueConstraint` |
| 1 | `migrations/versions/..._auditoria_dados_mestres_e_campos_slot.py` | criar | migration **3a** — aditiva |
| 3 | `migrations/versions/..._slot_not_null_e_unique.py` | criar | migration **3b** — destrutiva, isolada |
| 1 | `app/modules/equipamentos/schemas.py` | **editar** | `SlotInventarioCreate` estendido (é isto que corrige o bug do XLSX); `SlotInventarioUpdate`, `ItemEquipamentoUpdate`, `RemocaoJustificada`, `AuditoriaOut` novos |
| 1 | `app/modules/equipamentos/auditoria_service.py` | criar | `registrar`, `snapshot`, `diff_campos`, `listar` |
| 1 | `app/modules/equipamentos/xlsx_service.py` | **editar** | filtrar `ativo=True` ao carregar slots |
| 2 | `app/modules/equipamentos/service.py` | **editar** | `atualizar_slot`, `remover_slot`, `inativar_slot`, `reativar_slot`, `atualizar_item`, `excluir_item` + auditoria nas funções de PN/slot/item existentes |
| 2 | `app/modules/equipamentos/router.py` | **editar** | 7 endpoints novos (todos aditivos) + **5 endpoints existentes** ganham `request`/`current_user` para repassar `usuario_id`/`ip_origem` à auditoria — **nenhum muda contrato de entrada** |
| 2 | `app/web/templates/configuracoes.html` | **editar** | botão + 2 modais novos + botão "Histórico" no catálogo de PN |
| 2 | `app/web/static/js/configuracoes_inventario.js` | criar | JS dos modais novos |
| 2 | `tests/unit/test_gestao_inventario.py` | criar | cobertura das US-01 a US-03 da spec |
| 3 | `tests/` (8 arquivos) + `scripts/seed/seed_slots.py` | **editar** | 18 das 20 construções de `SlotInventario(...)` não passam `posicao_xlsx` (algumas nem `sistema`) e quebram com as colunas `NOT NULL` — ver Etapa 11 |

**Ordem de execução:** ver Seção 0.1 — `PR-1: 1→2→3a→4→5→8` · `PR-2: 6→7→9→10` · `PR-3: 3b→11`. Dentro do PR-3, a Etapa 11 vem **junto** da migration 3b: no instante em que `sistema`/`posicao_xlsx` viram `NOT NULL`, a suíte fica vermelha e deixa de servir como rede de segurança.

---

## 2. Etapa 1 — Enums (`app/shared/core/enums.py`)

Acrescentar ao final do arquivo, seguindo o estilo já usado por `StatusItem`/`OrigemControle` (herança de `str, enum.Enum`, docstring curta):

```python
class EntidadeAuditada(str, enum.Enum):
    """Entidades de dados mestres do inventário cobertas por auditoria."""
    MODELO_EQUIPAMENTO = "MODELO_EQUIPAMENTO"
    SLOT = "SLOT"
    ITEM = "ITEM"


class AcaoAuditoria(str, enum.Enum):
    """Ação registrada em auditoria_dados_mestres. Append-only — RN-09."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
```

Não remover nem reordenar nenhum enum existente — apenas apensar.

---

## 3. Etapa 2 — Modelos ORM (`app/modules/equipamentos/models.py`)

### 3.1 Estender `SlotInventario`

```python
class SlotInventario(Base):
    """
    Representa uma posição física pré-definida na aeronave (LCN/Slot).
    Slot é GLOBAL da frota (compartilhado por todas as aeronaves) — o vínculo
    por aeronave só existe em Instalacao (ver comentário em Instalacao abaixo).
    """
    __tablename__ = "slots_inventario"
    # __table_args__ com a UniqueConstraint entra apenas no PR-3, junto da
    # migration 3b — pelo mesmo motivo da nulabilidade faseada abaixo.
    # __table_args__ = (
    #     UniqueConstraint("nome_posicao", "sistema", name="uq_slot_nome_sistema"),
    # )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome_posicao: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # ⚠️ NULABILIDADE FASEADA — ver Seção 0.1.
    # PR-1/PR-2: estas três permanecem nullable=True no ORM, espelhando o banco
    # após a migration 3a. Declarar nullable=False antes da 3b faria o
    # --autogenerate do PR-2 emitir a alteração destrutiva por conta própria,
    # contrabandeando para um PR de baixo risco exatamente o que foi isolado.
    # PR-3: junto com a migration 3b, trocar para nullable=False e remover o
    # `| None` de sistema, posicao_xlsx e created_at.
    sistema: Mapped[str | None] = mapped_column(String(50), nullable=True)
    posicao_xlsx: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="RESTRICT"), nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ordem_exibicao: Mapped[int | None] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, server_default="1", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # --- Relacionamentos (sem alteração) ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="slots")
    instalacoes: Mapped[list["Instalacao"]] = relationship(back_populates="slot")

    def __repr__(self) -> str:
        return f"<SlotInventario nome={self.nome_posicao!r} pn={self.modelo_id}>"
```

**Pontos críticos (não pular):**
- **A Etapa 2 acontece em duas rodadas.** PR-1 adiciona as colunas novas e deixa `sistema`/`posicao_xlsx`/`created_at` como estão (nullable). PR-3 aperta as três e acrescenta a `UniqueConstraint`. Manter o ORM à frente do banco entre um PR e outro faz o `--autogenerate` gerar a alteração destrutiva sozinho.
- `sistema` e `posicao_xlsx` só passam a `nullable=False` no PR-3 — com backfill antes do `ALTER` (migration 3b).
- A obrigatoriedade que **de fato corrige o bug do XLSX** é a do schema Pydantic (Etapa 4), que entra já no PR-1 e não depende de nada disto.
- `server_default="1"` em `ativo` garante que as 33 linhas já existentes no banco não fiquem com `NULL` após o `ALTER TABLE`.
- `UniqueConstraint` nova formaliza a chave natural que `seed_slots.py:64-69` já usa de fato, mas que hoje **não é garantida pelo banco** — rodar o pré-check de duplicidade (Etapa 3) antes de aplicar.

### 3.2 Nova classe `AuditoriaDadosMestres`

Acrescentar ao final do arquivo, importando os dois enums novos:

```python
from app.shared.core.enums import StatusItem, EntidadeAuditada, AcaoAuditoria

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario
    from app.modules.vencimentos.models import EquipamentoControle, ControleVencimento


class AuditoriaDadosMestres(Base):
    """
    Trilha append-only de escritas em dados mestres do inventário
    (ModeloEquipamento, SlotInventario, ItemEquipamento).

    Sem UPDATE/DELETE pela aplicação — mesmo padrão de
    ExecucaoVencimentoHistorico (app/modules/vencimentos/models.py).
    """
    __tablename__ = "auditoria_dados_mestres"
    __table_args__ = (
        Index("ix_auditoria_entidade", "entidade", "entidade_id"),
        Index("ix_auditoria_criado_em", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entidade: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    acao: Mapped[str] = mapped_column(String(10), nullable=False)
    valores_anteriores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valores_novos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    justificativa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    usuario: Mapped["Usuario | None"] = relationship()

    def __repr__(self) -> str:
        return f"<AuditoriaDadosMestres {self.entidade}:{self.acao} id={self.entidade_id}>"
```

**Pontos críticos (não pular):**
- Import `JSON` de `sqlalchemy` no topo do arquivo (não existe hoje em `models.py`) — SQLite não tem `JSONB`, e `JSON` do SQLAlchemy já serializa/desserializa automaticamente.
- `entidade`/`acao` como `String` (não `Enum` nativo) — mesmo padrão de `ItemEquipamento.status` (`models.py:89`), que trata o enum como aplicacional, não como constraint de banco.
- `usuario_id` nullable — segue o precedente de `Instalacao.usuario_id` (`models.py:125`), para não quebrar se um usuário for removido.

---

## 4. Etapa 3 — Migrations (3a aditiva no PR-1, 3b destrutiva no PR-3)

São **duas** migrations, em dois PRs. Juntá-las anula o motivo de ter fatiado a entrega: a 3a poderia ir a produção hoje; a 3b é a que pode derrubar o container.

```bash
# PR-1
alembic revision --autogenerate -m "auditoria_dados_mestres_e_campos_slot"
# PR-3 (depois que a 3a estiver em produção)
alembic revision --autogenerate -m "slot_not_null_e_unique"
```

Gerar a partir do head atual do **repositório**: **`2676d7fdd987`** (`migrations/versions/20260820_1400_2676d7fdd987_publicacoes_manuais_origem.py`). A v1.0 deste plano dizia `b63e385e3395` — esse é o head do **banco local** (`saa29_local.db`), que está uma migration atrás do repositório. Rodar `alembic upgrade head` **antes** do autogenerate, senão o `down_revision` nasce errado e a migration entra fora de ordem.

**Pré-check — o da 3b é o que importa.** A 3a não pode falhar por dado preexistente e dispensa portão. Para a 3b, rodar a consulta abaixo **no banco de produção da VPS**, não no local:

```sql
SELECT nome_posicao, sistema, COUNT(*) FROM slots_inventario GROUP BY 1, 2 HAVING COUNT(*) > 1;
SELECT nome_posicao, sistema FROM slots_inventario WHERE sistema IS NULL OR posicao_xlsx IS NULL;
```

*Executado em 2026-08-30 nos **dois** ambientes: `saa29_local.db` e o banco de produção da VPS (`/app/data/saa29.db`). Ambos com 33 slots, 0 duplicidades e 0 nulos. Produção está em `alembic_version = 2676d7fdd987`, o head do repositório. Ver Seção 0.1, portão 1 — inclusive a ressalva de reexecutar antes do merge do PR-3.*

### 4.1 Migration 3a — aditiva (PR-1)

Só adiciona. Não altera nulabilidade, não cria UNIQUE, não toca em dado existente além de preencher `created_at`. Pode ir a produção sem portão manual.

```python
def upgrade() -> None:
    # 1. Colunas novas — todas nullable ou com server_default
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.add_column(sa.Column("descricao", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("ordem_exibicao", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Backfill de created_at (a promoção a NOT NULL fica para a 3b)
    op.execute("UPDATE slots_inventario SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    # 3. Nova tabela
    op.create_table(
        "auditoria_dados_mestres",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entidade", sa.String(30), nullable=False),
        sa.Column("entidade_id", sa.Uuid(), nullable=False),
        sa.Column("acao", sa.String(10), nullable=False),
        sa.Column("valores_anteriores", sa.JSON(), nullable=True),
        sa.Column("valores_novos", sa.JSON(), nullable=True),
        sa.Column("justificativa", sa.String(500), nullable=True),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auditoria_entidade", "auditoria_dados_mestres", ["entidade", "entidade_id"])
    op.create_index("ix_auditoria_criado_em", "auditoria_dados_mestres", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_criado_em", table_name="auditoria_dados_mestres")
    op.drop_index("ix_auditoria_entidade", table_name="auditoria_dados_mestres")
    op.drop_table("auditoria_dados_mestres")
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("ativo")
        batch_op.drop_column("ordem_exibicao")
        batch_op.drop_column("descricao")
```

### 4.2 Migration 3b — destrutiva (PR-3)

**Não mergear sem os dois portões da Seção 0.1** (pré-check em produção + snapshot manual).

```python
def upgrade() -> None:
    # 1. Backfill ANTES de tornar as colunas NOT NULL.
    #    Resolve NULO — NÃO resolve duplicata: se o pré-check em produção
    #    acusar duplicidade em (nome_posicao, sistema), sanear antes, ou a
    #    UNIQUE do passo 3 falha e o container não sobe (start.sh, set -e).
    op.execute("UPDATE slots_inventario SET sistema = '' WHERE sistema IS NULL")
    op.execute("UPDATE slots_inventario SET posicao_xlsx = '' WHERE posicao_xlsx IS NULL")
    op.execute("UPDATE slots_inventario SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    # 2. Promoção a NOT NULL — batch mode obrigatório em SQLite
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.alter_column("sistema", existing_type=sa.String(50), nullable=False)
        batch_op.alter_column("posicao_xlsx", existing_type=sa.String(20), nullable=False)
        batch_op.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)

        # 3. Chave natural que seed_slots.py:64-69 já usa de fato
        batch_op.create_unique_constraint("uq_slot_nome_sistema", ["nome_posicao", "sistema"])


def downgrade() -> None:
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.drop_constraint("uq_slot_nome_sistema", type_="unique")
        batch_op.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch_op.alter_column("posicao_xlsx", existing_type=sa.String(20), nullable=True)
        batch_op.alter_column("sistema", existing_type=sa.String(50), nullable=True)
```

**Pontos críticos (não pular):**
- **3a e 3b não podem virar uma migration só.** A 3a é reversível sem perda e não pode falhar por dado preexistente; a 3b pode. Fundi-las devolve todo o risco ao PR-1.
- A ordem "backfill → batch_alter_table" é obrigatória: alterar `sistema` para `NOT NULL` com linhas `NULL` existentes falha o `ALTER TABLE` mesmo em modo batch.
- O backfill **não** substitui o pré-check: `UPDATE ... SET sistema = ''` transforma nulos em string vazia, e duas linhas com `('MDP1', '')` continuam violando a UNIQUE.
- `env.py:53` já liga `render_as_batch=True` quando a URL contém `sqlite` — não é preciso configurar isso na migration, só usar `op.batch_alter_table`.
- **Tipos UUID:** usar `sa.Uuid()`, nunca `sa.CHAR(32)`. É a convenção do projeto (`20260810_0932_a6ebf9f13490_add_pedidos_module.py:34`), é o que o ORM emite para `Mapped[uuid.UUID]`, e é o tipo de `usuarios.id` — misturar os dois quebra a FK e deixa o `--autogenerate` acusando drift para sempre.
- **`created_at` termina `NOT NULL` só na 3b:** o modelo declara `Mapped[datetime]` sem `| None`, mas adicionar a coluna já como `NOT NULL` falharia nas 33 linhas existentes. Daí a sequência entre os dois PRs: *3a adiciona nullable e faz o backfill → 3b promove*. Até lá, o ORM mantém `created_at` como `Mapped[datetime | None]` para não gerar drift no `--autogenerate` do PR-2.
- Nunca editar manualmente uma migration sem revisar o autogenerate primeiro — o Alembic pode detectar mudanças adicionais não intencionais em outros modelos (`docs/guides/CONTRIBUTING.md §7`).

---

## 5. Etapa 4 — Schemas (`app/modules/equipamentos/schemas.py`) *(PR-1)*

> **Esta etapa é a que corrige o bug do XLSX.** Tornar `posicao_xlsx` obrigatório aqui faz a API parar de criar slots com `NULL` — que é a causa descrita na Seção 1 da spec. A coluna `NOT NULL` (PR-3) não acrescenta comportamento; só formaliza no banco o que o schema já garante. Por isso o valor chega no PR-1, sem depender da migration destrutiva.

```python
class SlotInventarioCreate(BaseModel):
    nome_posicao: str = Field(..., max_length=100)
    sistema: str = Field(..., max_length=50)
    posicao_xlsx: Identificador = Field(..., max_length=20)
    modelo_id: uuid.UUID
    descricao: str | None = Field(default=None, max_length=200)
    ordem_exibicao: int | None = None


class SlotInventarioUpdate(BaseModel):
    nome_posicao: str | None = Field(None, max_length=100)
    sistema: str | None = Field(None, max_length=50)
    posicao_xlsx: Identificador | None = Field(None, max_length=20)
    modelo_id: uuid.UUID | None = None
    descricao: str | None = Field(None, max_length=200)
    ordem_exibicao: int | None = None


class SlotInventarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome_posicao: str
    sistema: str
    posicao_xlsx: str
    modelo_id: uuid.UUID
    # PN esperado — a tela de gestão (Etapa 9) exibe a coluna "PN esperado";
    # sem isto o JS teria de cruzar modelo_id contra o catálogo no cliente.
    part_number: str | None = None
    descricao: str | None
    ordem_exibicao: int | None
    ativo: bool


class ItemEquipamentoUpdate(BaseModel):
    numero_serie: Identificador | None = Field(None, max_length=100)
    status: StatusItem | None = None


class RemocaoJustificada(BaseModel):
    justificativa: str = Field(..., min_length=5, max_length=500)


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entidade: str
    entidade_id: uuid.UUID
    acao: str
    valores_anteriores: dict | None
    valores_novos: dict | None
    justificativa: str | None
    usuario_id: uuid.UUID | None
    criado_em: datetime
```

**Pontos críticos (não pular):**
- `SlotInventarioCreate.sistema` e `.posicao_xlsx` passam de opcionais para obrigatórios — isso é uma **mudança de contrato**. Qualquer chamador existente de `POST /equipamentos/slots/` que hoje omite esses campos vai passar a receber `422`. Conferir `configuracoes.js` (hoje não tem formulário de criação de slot pela UI, só a API é usada em testes) antes de mesclar.
- Reaproveitar o tipo `Identificador` já existente (`schemas.py:20`) para `posicao_xlsx` mantém a normalização (maiúsculas/trim) consistente com PN e S/N.
- **`SlotInventarioUpdate` não expõe `ativo` de propósito** — ativar/inativar são endpoints dedicados (`/inativar`, `/reativar`), para que cada transição gere um registro de auditoria explícito em vez de se esconder num `PATCH` genérico.
- `SlotInventarioOut.part_number` é preenchido a partir de `slot.modelo.part_number`; toda listagem de slots já carrega o relacionamento via `selectinload` em `_buscar_slots` — `listar_slots` (`service.py:285`) precisa passar a fazer o mesmo (Etapa 6).

---

## 6. Etapa 5 — Serviço de auditoria (`app/modules/equipamentos/auditoria_service.py`)

```python
"""
app/modules/equipamentos/auditoria_service.py
Trilha append-only de escritas em dados mestres do inventário
(ModeloEquipamento, SlotInventario, ItemEquipamento).

Nenhuma função aqui faz UPDATE ou DELETE sobre AuditoriaDadosMestres —
mesmo padrão de app/modules/vencimentos/service.py para
ExecucaoVencimentoHistorico.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipamentos.models import AuditoriaDadosMestres
from app.shared.core.enums import EntidadeAuditada, AcaoAuditoria

CAMPOS_IGNORADOS = {"created_at", "updated_at", "id"}


def _serializavel(valor):
    """Converte um valor de coluna em algo que `json.dumps` aceite.

    Sem isto, gravar um snapshot vindo de `slot.__table__.columns` estoura
    `TypeError: Object of type UUID is not JSON serializable` na coluna JSON —
    `modelo_id` é uuid.UUID e `created_at` é datetime.
    """
    if isinstance(valor, (uuid.UUID, datetime, date)):
        return str(valor)
    return valor


def snapshot(obj, campos: list[str] | None = None) -> dict:
    """Snapshot serializável de uma instância ORM.

    Uso obrigatório em vez de montar o dict à mão: garante que todo valor
    passe por `_serializavel` antes de chegar à coluna JSON.
    """
    nomes = campos or [c.name for c in obj.__table__.columns]
    return {n: _serializavel(getattr(obj, n)) for n in nomes}


def diff_campos(antes: dict | None, depois: dict | None) -> tuple[dict, dict]:
    """Retorna (anteriores, novos) apenas com os campos que mudaram.

    `antes=None` (CREATE) devolve depois inteiro em `novos`, `anteriores={}`.
    `depois=None` (DELETE) devolve antes inteiro em `anteriores`, `novos={}`.
    """
    antes = antes or {}
    depois = depois or {}
    chaves = (set(antes) | set(depois)) - CAMPOS_IGNORADOS

    anteriores, novos = {}, {}
    for chave in chaves:
        v_antes, v_depois = antes.get(chave), depois.get(chave)
        if v_antes != v_depois:
            anteriores[chave] = v_antes
            novos[chave] = v_depois
    return anteriores, novos


async def registrar(
    db: AsyncSession,
    *,
    entidade: EntidadeAuditada,
    entidade_id: uuid.UUID,
    acao: AcaoAuditoria,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
    anteriores: dict | None = None,
    novos: dict | None = None,
    justificativa: str | None = None,
) -> None:
    """Grava um registro de auditoria. `usuario_id` deve vir sempre da sessão
    autenticada (RN-05) — nunca de payload do cliente."""
    db.add(AuditoriaDadosMestres(
        id=uuid.uuid4(),
        entidade=entidade.value,
        entidade_id=entidade_id,
        acao=acao.value,
        # Rede de segurança: mesmo que um chamador esqueça de usar snapshot(),
        # nada não-serializável chega à coluna JSON.
        valores_anteriores={k: _serializavel(v) for k, v in (anteriores or {}).items()} or None,
        valores_novos={k: _serializavel(v) for k, v in (novos or {}).items()} or None,
        justificativa=justificativa,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        criado_em=datetime.now(),
    ))
    await db.flush()


async def listar(
    db: AsyncSession,
    entidade: EntidadeAuditada | None = None,
    entidade_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditoriaDadosMestres]:
    stmt = select(AuditoriaDadosMestres).order_by(desc(AuditoriaDadosMestres.criado_em))
    if entidade:
        stmt = stmt.where(AuditoriaDadosMestres.entidade == entidade.value)
    if entidade_id:
        stmt = stmt.where(AuditoriaDadosMestres.entidade_id == entidade_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

**Pontos críticos (não pular):**
- `diff_campos` grava só o que mudou — evita blob gigante em `UPDATE` de um único campo, no espírito do comentário original da spec ("Somente campos alterados").
- **Todo snapshot passa por `snapshot()`/`_serializavel`.** Este era o defeito mais silencioso da v1.0 deste plano: `{c.name: getattr(slot, c.name) for c in slot.__table__.columns}` devolve `uuid.UUID` e `datetime` crus, que a coluna `JSON` do SQLAlchemy não consegue serializar. O erro só apareceria no primeiro `PATCH`/`DELETE` real, não na criação da tabela.
- Em `DELETE` o snapshot é gravado **inteiro** (não passa por `diff_campos`), então é justamente o caminho onde `id` e `created_at` chegam à coluna JSON — mais um motivo para a normalização ser obrigatória, não opcional.
- Todo chamador de `registrar()` precisa passar `usuario_id=current_user.id` vindo da dependência FastAPI, nunca de um campo do schema — é a mesma disciplina já aplicada em `ajustar_inventario_item` (`service.py:474-487`) para o BUG-01.

---

## 7. Etapa 6 — Service (`app/modules/equipamentos/service.py`)

Adicionar ao final do arquivo (após a seção de Slots existente, `service.py:270-288`):

```python
# ============================================================
# Slots — CRUD completo
# ============================================================

async def atualizar_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    dados: SlotInventarioUpdate,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> SlotInventario:
    """Atualiza um slot. Troca de modelo_id (PN esperado) é bloqueada
    enquanto houver instalação ativa nesse slot em qualquer aeronave —
    RN-04: slot é global da frota, então a troca afeta todas as aeronaves.

    Raises:
        EntidadeNaoEncontradaError: slot ou novo modelo_id inexistente.
        ConflitoNegocioError: (nome_posicao, sistema) já em uso; ou troca de
            modelo_id com instalação ativa.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    antes = auditoria_service.snapshot(slot)  # serializável — nunca dict cru

    if dados.modelo_id is not None and dados.modelo_id != slot.modelo_id:
        res = await db.execute(
            select(Instalacao.id).where(Instalacao.slot_id == slot_id, Instalacao.data_remocao.is_(None))
        )
        if res.first():
            raise domain_exc.ConflitoNegocioError(
                "Não é possível trocar o PN esperado: este slot tem instalação ativa em ao menos uma aeronave."
            )
        if not await db.get(ModeloEquipamento, dados.modelo_id):
            raise domain_exc.EntidadeNaoEncontradaError(f"Equipamento {dados.modelo_id} não encontrado.")
        slot.modelo_id = dados.modelo_id

    novo_nome = dados.nome_posicao if dados.nome_posicao is not None else slot.nome_posicao
    novo_sistema = dados.sistema if dados.sistema is not None else slot.sistema
    if (novo_nome, novo_sistema) != (slot.nome_posicao, slot.sistema):
        res = await db.execute(
            select(SlotInventario.id).where(
                SlotInventario.nome_posicao == novo_nome,
                SlotInventario.sistema == novo_sistema,
                SlotInventario.id != slot_id,
            )
        )
        if res.first():
            raise domain_exc.ConflitoNegocioError("Já existe um slot com este nome nesta localização.")

    for campo in ("nome_posicao", "sistema", "posicao_xlsx", "descricao", "ordem_exibicao"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(slot, campo, valor)

    await db.flush()

    depois = auditoria_service.snapshot(slot)
    anteriores, novos = auditoria_service.diff_campos(antes, depois)
    if novos:
        await auditoria_service.registrar(
            db, entidade=EntidadeAuditada.SLOT, entidade_id=slot.id, acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id, ip_origem=ip_origem, anteriores=anteriores, novos=novos,
        )
    return slot


async def _contar_instalacoes_slot(db: AsyncSession, slot_id: uuid.UUID) -> list[dict]:
    """Lista aeronaves/instalações vinculadas a um slot (ativas e históricas)."""
    res = await db.execute(
        select(Aeronave.matricula, Instalacao.data_remocao)
        .join(Instalacao, Instalacao.aeronave_id == Aeronave.id)
        .where(Instalacao.slot_id == slot_id)
    )
    return [{"aeronave": m, "ativa": rem is None} for m, rem in res.all()]


async def remover_slot(
    db: AsyncSession, slot_id: uuid.UUID, justificativa: str,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um slot sem nenhuma instalação vinculada.

    Raises:
        EntidadeNaoEncontradaError: slot inexistente.
        ConflitoNegocioError: existe instalação (ativa ou histórica) vinculada.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    ocupacao = await _contar_instalacoes_slot(db, slot_id)
    if ocupacao:
        raise domain_exc.ConflitoNegocioError(
            f"Não é possível excluir: {len(ocupacao)} instalação(ões) vinculada(s) a este slot. "
            "Considere inativar o slot."
        )

    antes = auditoria_service.snapshot(slot)
    await db.delete(slot)
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.SLOT, entidade_id=slot_id, acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id, ip_origem=ip_origem, anteriores=antes, justificativa=justificativa,
    )


async def _alternar_ativo_slot(
    db: AsyncSession, slot_id: uuid.UUID, ativo: bool,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> SlotInventario:
    """Liga/desliga um slot. Não exige ausência de instalações (RF-05/RF-13)."""
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")
    if slot.ativo == ativo:
        return slot  # idempotente — sem auditoria de não-mudança
    anterior = slot.ativo
    slot.ativo = ativo
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.SLOT, entidade_id=slot_id, acao=AcaoAuditoria.UPDATE,
        usuario_id=usuario_id, ip_origem=ip_origem,
        anteriores={"ativo": anterior}, novos={"ativo": ativo},
    )
    return slot


async def inativar_slot(db, slot_id, usuario_id, ip_origem=None):
    """RF-05 — inativa sem apagar histórico."""
    return await _alternar_ativo_slot(db, slot_id, False, usuario_id, ip_origem)


async def reativar_slot(db, slot_id, usuario_id, ip_origem=None):
    """RF-13 — sem isto, um slot inativado some da listagem (RF-12) e fica
    permanentemente inacessível pela aplicação."""
    return await _alternar_ativo_slot(db, slot_id, True, usuario_id, ip_origem)


# ============================================================
# Itens de Equipamento — CRUD completo
# ============================================================

async def atualizar_item(
    db: AsyncSession, item_id: uuid.UUID, dados: ItemEquipamentoUpdate,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> ItemEquipamento:
    """Corrige S/N ou status de um item físico.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: novo S/N já usado por outro item do mesmo PN.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    antes = auditoria_service.snapshot(item, ["numero_serie", "status"])

    if dados.numero_serie is not None and dados.numero_serie != item.numero_serie:
        if await _buscar_item_por_sn(db, item.modelo_id, dados.numero_serie):
            raise domain_exc.ConflitoNegocioError(f"S/N '{dados.numero_serie}' já cadastrado para este P/N.")
        item.numero_serie = dados.numero_serie
    if dados.status is not None:
        item.status = dados.status.value

    await db.flush()
    depois = auditoria_service.snapshot(item, ["numero_serie", "status"])
    anteriores, novos = auditoria_service.diff_campos(antes, depois)
    if novos:
        await auditoria_service.registrar(
            db, entidade=EntidadeAuditada.ITEM, entidade_id=item.id, acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id, ip_origem=ip_origem, anteriores=anteriores, novos=novos,
        )
    return item


async def excluir_item(
    db: AsyncSession, item_id: uuid.UUID, justificativa: str,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um item sem instalação vinculada.

    Nome deliberadamente distinto de `remover_item` (service.py:714), que já
    significa "encerrar a instalação ativa de um item" — não confundir.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: existe instalação vinculada a este item.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    res = await db.execute(select(Instalacao.id).where(Instalacao.item_id == item_id))
    if res.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este item tem instalação vinculada. Considere status=REMOVIDO."
        )

    # ControleVencimento.item_id (vencimentos/models.py:77) é FK SEM ondelete —
    # sem esta checagem o db.delete() estoura IntegrityError (500) em vez de 409.
    # E como criar_item_com_heranca cria controles herdados para TODO item novo
    # (service.py:232), este é o caminho comum, não a exceção.
    res_controles = await db.execute(
        select(ControleVencimento.id).where(ControleVencimento.item_id == item_id)
    )
    if res_controles.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este item tem controles de vencimento (TBV/RBA) vinculados. "
            "Considere status=REMOVIDO."
        )

    antes = auditoria_service.snapshot(item, ["numero_serie", "modelo_id", "status"])
    await db.delete(item)
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.ITEM, entidade_id=item_id, acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id, ip_origem=ip_origem, anteriores=antes, justificativa=justificativa,
    )
```

### 7.1 Filtro de inativos — **duas** funções, não uma

Existem **duas** funções distintas que listam slots, e RF-12 exige alterar as duas. A v1.0 deste plano só citava `_buscar_slots`, o que deixaria o teste #9 da Etapa 10 ("slot inativo some de `GET /equipamentos/slots/`") impossível de passar.

```python
# (a) service.py:341 — alimenta a grade de /inventario
async def _buscar_slots(db: AsyncSession, nome: str | None = None, apenas_ativos: bool = True) -> list[SlotInventario]:
    stmt = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if apenas_ativos:
        stmt = stmt.where(SlotInventario.ativo.is_(True))
    if nome:
        ...  # sem alteração no resto da função
    res = await db.execute(stmt)
    return list(res.scalars().all())


# (b) service.py:285 — alimenta GET /equipamentos/slots/ (tela de gestão)
async def listar_slots(db: AsyncSession, incluir_inativos: bool = False) -> list[SlotInventario]:
    """Lista os slots configurados.

    `incluir_inativos=True` é o que permite à tela de gestão exibir — e
    reativar (RF-13) — um slot desligado. Sem esse parâmetro, RF-05 + RF-12
    tornariam a inativação irreversível pela aplicação.
    """
    stmt = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if not incluir_inativos:
        stmt = stmt.where(SlotInventario.ativo.is_(True))
    stmt = stmt.order_by(
        SlotInventario.ordem_exibicao.nulls_last(),
        SlotInventario.sistema,
        SlotInventario.nome_posicao,
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
```

> `listar_slots` ganha `selectinload(SlotInventario.modelo)` porque `SlotInventarioOut` passa a expor `part_number` (Etapa 4). Sem isso, cada linha dispararia um lazy-load — e em contexto async isso levanta `MissingGreenlet`, não só N+1.

### 7.2 `ordem_exibicao` só funciona se o `sort` em Python mudar

`listar_inventario_aeronave` **reordena o resultado em memória** depois de chamar `_buscar_slots`:

```python
# service.py:322 — ANTES
inventario.sort(key=lambda x: (x.sistema or "ZZZ", x.nome_posicao))

# DEPOIS — sem esta linha, ordem_exibicao é campo morto na tela de Inventário
inventario.sort(key=lambda x: (
    x.ordem_exibicao if x.ordem_exibicao is not None else 10**6,
    x.sistema or "ZZZ",
    x.nome_posicao,
))
```

Isso exige acrescentar `ordem_exibicao` a `InventarioItemOut` (`schemas.py:103`) e propagá-lo em `_montar_linha_inventario` (`service.py:438`). Um `ORDER BY` na query **não** resolve: o `sort` em Python vem depois e sobrescreve.

### 7.3 Auditoria das criações e instrumentação dos serviços existentes

RF-09 diz *toda* escrita — o que inclui as três criações, não só as edições:

| Função | Arquivo | O que muda |
|---|---|---|
| `criar_modelo` | `service.py:57` | + `usuario_id`/`ip_origem`; auditoria `CREATE` |
| `atualizar_modelo` | `service.py:122` | + `usuario_id`/`ip_origem`; auditoria `UPDATE` com diff |
| `remover_modelo` | `service.py:151` | + `usuario_id`/`ip_origem`/`justificativa`; auditoria `DELETE` |
| `criar_slot` | `service.py:270` | + `usuario_id`/`ip_origem`; auditoria `CREATE`; **tratar `IntegrityError`** da nova UNIQUE |
| `criar_item_com_heranca` | `service.py:197` | + `usuario_id`/`ip_origem`; auditoria `CREATE` — **omitido na v1.0 deste plano** |

`criar_slot` precisa do mesmo tratamento de corrida que `criar_item_com_heranca` já faz (`service.py:220-231`), senão a UNIQUE nova devolve 500 em vez de 409:

```python
    try:
        async with db.begin_nested():
            db.add(slot)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar slot %s/%s: %s",
                       dados.nome_posicao, dados.sistema, exc.orig)
        raise domain_exc.ConflitoNegocioError(
            "Já existe um slot com este nome nesta localização."
        ) from exc
```

**Pontos críticos (não pular):**
- **Colisão de nome deliberadamente evitada:** `service.remover_item` (linha 714) já existe e significa "encerrar instalação". A função nova **precisa** se chamar `excluir_item` — reaproveitar o nome `remover_item` sobrescreveria o fluxo operacional de desinstalação usado por `PATCH /instalacoes/{id}/remover`.
- `_contar_instalacoes_slot` inclui instalações **históricas** (não só ativas) — RN-03 da spec é mais rígida que a de item (RN-06), porque um slot removido apaga rastreabilidade de toda a frota, não de uma linha isolada.
- `atualizar_slot`/`atualizar_item` só chamam `auditoria_service.registrar` quando `diff_campos` encontra mudança real — evita registro de auditoria vazio em um PATCH que não alterou nada.
- Imports novos no topo de `service.py`: `auditoria_service`, `EntidadeAuditada`, `AcaoAuditoria`, `SlotInventarioUpdate`, `ItemEquipamentoUpdate` e **`ControleVencimento`** (`app.modules.vencimentos.models`) — este último é o que viabiliza a checagem de RN-06 ampliada em `excluir_item`. `EquipamentoControle` já é importado por `remover_modelo`, então o precedente de import cruzado entre os módulos já existe.
- **Nenhum snapshot montado à mão.** Usar sempre `auditoria_service.snapshot(obj, campos?)`: dicts crus vindos de `__table__.columns` carregam `uuid.UUID`/`datetime` e quebram a serialização da coluna `JSON`.
- **`excluir_item` bloqueia por dois vínculos**, não um: `Instalacao` **e** `ControleVencimento`. Sem o segundo, o endpoint devolve 500 no caso mais comum.

---

## 8. Etapa 7 — Router (`app/modules/equipamentos/router.py`)

Inserir nas seções já existentes de Slots (após linha 107) e Itens (após linha 137), e uma seção nova de Auditoria ao final.

**Primeiro, o endpoint de listagem existente** (`router.py:84-91`) ganha o parâmetro que torna a tela de gestão possível:

```python
@router.get("/slots/", response_model=list[schemas.SlotInventarioOut], summary="Listar todos os slots configurados")
async def listar_slots(db: DBSession, _: CurrentUser, incluir_inativos: bool = Query(False)):
    slots = await service.listar_slots(db, incluir_inativos=incluir_inativos)
    return [schemas.SlotInventarioOut.model_validate(s) for s in slots]
```

**Endpoints novos:**

```python
@router.patch("/slots/{slot_id}", response_model=schemas.SlotInventarioOut, summary="Atualizar slot")
async def atualizar_slot(
    slot_id: uuid.UUID, dados: schemas.SlotInventarioUpdate,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    slot = await service.atualizar_slot(
        db, slot_id, dados, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.SlotInventarioOut.model_validate(slot)


@router.post("/slots/{slot_id}/remover", summary="Excluir slot (exige justificativa)")
async def remover_slot(
    slot_id: uuid.UUID, dados: schemas.RemocaoJustificada,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    await service.remover_slot(
        db, slot_id, dados.justificativa, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return {"success": True, "message": "Slot removido com sucesso."}


@router.post("/slots/{slot_id}/inativar", response_model=schemas.SlotInventarioOut, summary="Inativar slot")
async def inativar_slot(slot_id: uuid.UUID, db: DBSession, request: Request, current_user: AdminRequired):
    slot = await service.inativar_slot(
        db, slot_id, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.SlotInventarioOut.model_validate(slot)


@router.post("/slots/{slot_id}/reativar", response_model=schemas.SlotInventarioOut, summary="Reativar slot")
async def reativar_slot(slot_id: uuid.UUID, db: DBSession, request: Request, current_user: AdminRequired):
    """RF-13 — contrapartida obrigatória de /inativar."""
    slot = await service.reativar_slot(
        db, slot_id, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.SlotInventarioOut.model_validate(slot)


@router.get("/slots/{slot_id}/ocupacao", summary="Listar aeronaves que ocupam o slot")
async def ocupacao_slot(slot_id: uuid.UUID, db: DBSession, _: AdminRequired):
    return await service._contar_instalacoes_slot(db, slot_id)


@router.patch("/itens/{item_id}", response_model=schemas.ItemEquipamentoOut, summary="Atualizar item")
async def atualizar_item(
    item_id: uuid.UUID, dados: schemas.ItemEquipamentoUpdate,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    item = await service.atualizar_item(
        db, item_id, dados, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.ItemEquipamentoOut.model_validate(item)


@router.post("/itens/{item_id}/remover", summary="Excluir item (exige justificativa)")
async def excluir_item(
    item_id: uuid.UUID, dados: schemas.RemocaoJustificada,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    await service.excluir_item(
        db, item_id, dados.justificativa, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return {"success": True, "message": "Item removido com sucesso."}


# ---- Auditoria de Dados Mestres ----

@router.get("/auditoria", response_model=list[schemas.AuditoriaOut], summary="Consultar auditoria de dados mestres")
async def listar_auditoria(
    db: DBSession, _: AdminRequired,
    entidade: EntidadeAuditada | None = None,
    entidade_id: uuid.UUID | None = None,
    limit: int = 50, offset: int = 0,
):
    registros = await auditoria_service.listar(db, entidade, entidade_id, limit, offset)
    return [schemas.AuditoriaOut.model_validate(r) for r in registros]
```

Imports novos no topo: `from fastapi import Request`, `from app.modules.equipamentos import auditoria_service`, `from app.shared.core.enums import EntidadeAuditada`.

**Pontos críticos (não pular):**
- `_contar_instalacoes_slot` é "privada" por convenção (`_` no nome) mas reaproveitada direto no endpoint de ocupação — mesmo padrão de `router.py:89` que já expõe `service.listar_slots` sem passar por uma função pública dedicada. Se preferir manter a convenção estrita, renomear para `contar_instalacoes_slot` (pública) na Etapa 6.
- **Exclusão é `POST /{id}/remover`, não `DELETE` com corpo.** RF-10 exige justificativa nas operações destrutivas, e justificativa precisa de corpo — mas `DELETE` com corpo não tem precedente algum neste projeto: dos 10 endpoints `@router.delete` existentes, **nenhum** recebe body. O padrão real do repositório para "ação destrutiva que exige motivo" está em `pedidos`:

  ```
  app/modules/pedidos/router.py:208   @router.post("/{pedido_id}/cancelar")   # dados: PedidoCancelar
  app/modules/pedidos/router.py:223   @router.delete("/{pedido_id}")          # sem corpo
  ```

  Além da consistência, isso evita um risco operacional concreto: a aplicação roda atrás do nginx da VPS, e corpo em `DELETE` é descartado silenciosamente por vários proxies e clientes HTTP. *(Versões anteriores deste plano citavam `pedidos` como precedente de `DELETE`-com-body — a afirmação era falsa.)*
- Nenhum endpoint `DELETE` existente muda de assinatura. Em particular, **`DELETE /equipamentos/{equipamento_id}` fica intocado**: ganha auditoria com `justificativa=None`, e o botão "Remover PN" do `configuracoes.js:763` continua funcionando sem alteração. Se a Q4 (Qualidade) exigir justificativa também para PN, acrescenta-se `POST /equipamentos/{id}/remover` ao lado do `DELETE` — aditivo, sem quebrar consumidor nenhum.
- Nenhuma destas rotas colide com `/{equipamento_id}` (`router.py:51`) porque todas têm 2+ segmentos de path.
- **Cinco endpoints já existentes mudam junto** (a v1.0 falava só em "6 endpoints novos"): `POST /`, `PATCH /{equipamento_id}`, `DELETE /{equipamento_id}` (`router.py:36-81`), `POST /slots/` (`:94`) e `POST /itens/` (`:125`) passam a receber `request: Request` e a trocar `_: AdminRequired` por `current_user: AdminRequired`, repassando `usuario_id`/`ip_origem` ao service. Sem isso, RF-09 fica cumprido só para as edições e as criações ficam sem trilha.
- `ip_origem` vem de `request.client.host`. Atrás do nginx da VPS isso registra o IP do proxy; tratar como limitação conhecida (Seção 6.6 da spec), não como rastreabilidade de rede.

---

## 9. Etapa 8 — Consumidor de slots (`app/modules/equipamentos/xlsx_service.py`)

```python
# xlsx_service.py:138-142 — filtrar apenas slots ativos
res_slots = await db.execute(
    select(SlotInventario, ModeloEquipamento)
    .join(ModeloEquipamento, SlotInventario.modelo_id == ModeloEquipamento.id)
    .where(SlotInventario.ativo.is_(True))
)
slots_ativos = res_slots.all()
```

**Pontos críticos (não pular):** sem este filtro, um slot inativado continua entrando no preview de importação XLSX e recebendo o serial sintético `XXXXXXX-{nome_posicao}` (mesmo bug descrito na Seção 1 da spec, só que para slots inativos em vez de slots sem `posicao_xlsx`).

---

## 10. Etapa 9 — UI (`app/web/templates/configuracoes.html` + `app/web/static/js/configuracoes_inventario.js`)

### 10.1 Template

No card "Equipamentos e PNs" (`configuracoes.html:77-93`), adicionar um botão após `#btn-gerenciar-catalogo`:

```html
<button class="btn btn-equipamento" id="btn-gerenciar-slots" style="width: 100%;">
    <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"
        style="vertical-align: middle; margin-right: 5px;">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
    Gerenciar Slots
</button>
```

Dois modais novos, clonando o esqueleto `glass-panel` de `#modal-catalogo` (`configuracoes.html:405-440`):
- `#modal-slots` — tabela (Loc, Slot, PN esperado, `posicao_xlsx`, Ativo, ações Editar / **Inativar ou Reativar** / Remover / Histórico) + botão "Novo Slot". Carrega com `?incluir_inativos=true`, senão as linhas inativas nunca apareceriam e o botão "Reativar" ficaria inalcançável.
- `#modal-form-slot` — formulário de criar/editar slot (campos: `nome_posicao`, `sistema`, `posicao_xlsx`, `modelo_id` como `<select>` populado do catálogo, `descricao`, `ordem_exibicao`).
- Reaproveitar `#modal-catalogo` existente: adicionar botão "Histórico" (ícone de relógio) em cada linha, ao lado de Editar/Remover (`configuracoes.js:759-766`).

### 10.2 JavaScript (`configuracoes_inventario.js`)

Novo arquivo (precedente: `configuracoes_publicacoes.js`, extraído do principal por tamanho — `configuracoes.js` já tem 1937 linhas). Carregar em `configuracoes.html` junto da linha 1186:

```html
<script src="/static/js/configuracoes_inventario.js"></script>
```

Estrutura seguindo `configuracoes.js:690-840` (abrir modal → `carregarLista*` via `apiFetch` → renderizar linhas com `escapeHtml` → `addEventListener` nos botões, nunca `onclick` inline):

```javascript
// app/web/static/js/configuracoes_inventario.js
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-gerenciar-slots')?.addEventListener('click', openModalSlots);
    document.getElementById('btn-close-modal-slots')?.addEventListener('click', closeModalSlots);
    document.getElementById('btn-novo-slot')?.addEventListener('click', () => openModalFormSlot());
    document.getElementById('formSlot')?.addEventListener('submit', salvarSlot);
});

let slotsCache = [];

async function carregarListaSlots() {
    const tbody = document.getElementById('lista-slots-body');
    if (!tbody) return;
    try {
        // incluir_inativos=true: a tela de gestão é o único lugar onde um slot
        // desligado precisa continuar visível (para reativar — RF-13).
        slotsCache = await apiFetch('/equipamentos/slots/?incluir_inativos=true');
        tbody.innerHTML = '';
        slotsCache.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${escapeHtml(s.sistema)}</td>
                <td>${escapeHtml(s.nome_posicao)}</td>
                <td>${escapeHtml(s.part_number || '---')}</td>
                <td>${escapeHtml(s.posicao_xlsx)}</td>
                <td>${s.ativo ? 'Ativo' : 'Inativo'}</td>
                <td class="acoes"></td>
            `;
            const acoes = tr.querySelector('.acoes');
            const btnEdit = document.createElement('button');
            btnEdit.className = 'btn-icon';
            btnEdit.addEventListener('click', () => openModalFormSlot(s.id));
            acoes.appendChild(btnEdit);

            // Inativar/Reativar é o MESMO botão, alternando pelo estado.
            const btnToggle = document.createElement('button');
            btnToggle.className = 'btn-icon';
            btnToggle.title = s.ativo ? 'Inativar' : 'Reativar';
            btnToggle.addEventListener('click', () => alternarAtivoSlot(s.id, !s.ativo));
            acoes.appendChild(btnToggle);
            // botões de remover/histórico seguem o mesmo padrão
            tbody.appendChild(tr);
        });
    } catch (e) {
        showToast(e.message || 'Erro ao carregar slots.', 'error');
    }
}
```

(Código completo a implementar seguindo fielmente o molde já citado — este trecho fixa a estrutura mínima obrigatória: `apiFetch`, `escapeHtml`, `addEventListener`, `showToast`.)

**Pontos críticos (não pular):**
- CSP do projeto é `script-src 'self'` sem `'unsafe-inline'` — qualquer `onclick=` inline simplesmente não executa (RN-16, `docs/ia/rules.ctx`).
- `#modal-slots` usa `data-role="ADMINISTRADOR"` no botão do card, coerente com a decisão de escopo (admin-only) e com `/configuracoes` já ser `AdminRequired` no backend.

---

## 11. Etapa 10 — Testes (`tests/unit/test_gestao_inventario.py`)

Usar as fixtures já existentes em `tests/conftest.py` — não criar fixtures novas: `client`, `db`, `usuario_e_token` (ADMINISTRADOR), `usuario_encarregado_e_token`, `dados_aeronave_valida`, `dados_equipamento_valido`. Seguir o padrão de helpers privados de `tests/unit/test_inventario.py` (`_criar_modelo`, `_criar_slot`, `_criar_aeronave`).

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | Criar slot sem `posicao_xlsx` | 422 |
| 2 | Criar slot com `(nome_posicao, sistema)` duplicado | 409 |
| 3 | Criar slot via API e depois rodar preview XLSX com PN/posição correspondentes | slot é encontrado (regressão do bug da Seção 1) |
| 4 | Editar `nome_posicao`/`descricao` de slot | 200, auditoria UPDATE com diff correto |
| 5 | Editar `modelo_id` de slot com instalação ativa | 409 |
| 6 | Editar `modelo_id` de slot sem instalação | 200 |
| 7 | `POST /slots/{id}/remover` com instalação (ativa ou histórica) | 409, sugestão "inativar" |
| 8 | `POST /slots/{id}/remover` sem instalação | 200, auditoria `DELETE`, exige `justificativa` (ausente → 422) |
| 9 | Inativar slot | `ativo=false`; some de `GET /equipamentos/slots/` (lista padrão), **aparece** em `?incluir_inativos=true`, e some do preview XLSX e da grade de `/inventario` |
| 9b | Reativar slot inativado (RF-13) | `ativo=true`; volta à lista padrão e ao preview XLSX; auditoria UPDATE |
| 10 | Editar S/N de item para valor já usado no mesmo PN | 409 |
| 11 | Editar S/N de item para valor livre | 200, auditoria UPDATE |
| 12 | `POST /itens/{id}/remover` com instalação vinculada | 409, sugestão `status=REMOVIDO` |
| 13 | `POST /itens/{id}/remover` sem instalação **e sem controles de vencimento** | 200, auditoria `DELETE` |
| 13b | `POST /itens/{id}/remover` em item criado por `POST /equipamentos/itens/` (que herda controles) | **409** com menção a controles de vencimento — nunca 500. Caso mais provável na prática (RN-06 ampliada) |
| 13c | Auditoria de `UPDATE`/`DELETE` de slot é lida de volta via `GET /equipamentos/auditoria` | `valores_anteriores`/`valores_novos` desserializam sem erro (regressão do defeito de serialização JSON de UUID/datetime) |
| 13d | `ordem_exibicao` definido em dois slots do mesmo `sistema` | `/inventario` respeita a ordem; slots com `ordem_exibicao=NULL` vão para o fim |
| 14 | ENCARREGADO tenta qualquer escrita de slot/item, incluindo os `/remover` | 403 |
| 15 | `GET /equipamentos/auditoria?entidade=SLOT&entidade_id=...` | retorna os registros na ordem certa |
| 16 | Suíte de regressão `test_inventario.py`, `test_equipamentos.py`, `test_equipamentos_xlsx.py` | continua verde **após a adequação da Etapa 11** — o comportamento de `/inventario` e do XLSX não muda, mas as construções de slot precisam ser atualizadas (não é "sem alteração") |

---

## 12. Etapa 11 — Adequação das suítes e seeds existentes *(PR-3)*

**Executar no mesmo PR da migration 3b — nunca antes dela, nunca depois.**

> **Duas quebras diferentes, em dois PRs diferentes** — confundi-las faz o PR-1 nascer vermelho:
>
> | O que quebra | Por causa de | Quantos | PR |
> |---|---|---|---|
> | Testes que fazem `POST /equipamentos/slots/` | O **schema Pydantic** exigir `posicao_xlsx` (Etapa 4) → 422 | 2 | **PR-1** |
> | Testes que constroem `SlotInventario(...)` direto pelo ORM | A **coluna** virar `NOT NULL` (migration 3b) | 18 | **PR-3** |
>
> O schema barra na entrada da API; o `NOT NULL` barra no banco. Quem cria o objeto pelo ORM nunca passa pelo schema — por isso os 18 sobrevivem ao PR-1 e só caem no PR-3. Tornar `sistema` e `posicao_xlsx` `NOT NULL` invalida a maioria das construções de slot já existentes no repositório: das 20 ocorrências de `SlotInventario(...)` em `tests/` e `scripts/`, apenas 2 passam `posicao_xlsx`.

| Arquivo | Linhas | Falta |
|---|---|---|
| `tests/unit/test_dashboard.py` | 97, 185 | `sistema` **e** `posicao_xlsx` |
| `tests/unit/test_encarregado.py` | 121, 154 | `sistema` **e** `posicao_xlsx` |
| `tests/architecture/test_performance_audit.py` | 24, 85 | `sistema` **e** `posicao_xlsx` |
| `tests/unit/test_vencimentos_criticos.py` | 160, 217, 295, 296, 356, 399 | `posicao_xlsx` |
| `tests/unit/test_equipamentos_achados_revisor.py` | 91, 118, 144 | `posicao_xlsx` |
| `tests/unit/test_equipamentos_refatoracao.py` | 72 | `posicao_xlsx` |
| `tests/unit/test_equipamentos_correcoes_urgentes.py` | 76 | `posicao_xlsx` |
| `tests/unit/test_inventario.py` | 35 | conferir |
| `tests/unit/test_equipamentos_xlsx.py` | 67 | conferir |
| `scripts/seed/seed_slots.py` | 73 | conferir (o seed já casa por `(part_number, posicao_xlsx)`) |

> ⚠️ **Correção (v1.6):** os dois testes de API **não pertencem a esta etapa** — pertencem ao PR-1. `tests/unit/test_equipamentos.py:239` e `:266` fazem `POST /equipamentos/slots/` com apenas `nome_posicao`/`sistema`/`modelo_id`, então quebram no instante em que `SlotInventarioCreate` passa a exigir `posicao_xlsx` (Etapa 4, **PR-1**) — muito antes de a coluna virar `NOT NULL`.

**Como fazer sem espalhar a mudança:** os arquivos com mais de uma ocorrência já usam helpers privados (`_criar_slot`, `_slot`); onde o helper existe, basta preenchê-lo com um `posicao_xlsx` derivado do nome (ex.: `posicao_xlsx=nome[:20]`). Onde a construção está inline, preferir extrair um helper local a repetir o campo.

**Critério de saída da etapa:** `pytest -q` verde no mesmo commit que aplica a 3b. Como o CI roda `pytest` antes do deploy (`deploy.yml:28-30`), um PR-3 com esta etapa incompleta é **barrado no CI** e não chega a produção — o portão existe, mas não substitui rodar a suíte localmente antes de abrir o PR.

---

## 13. Verificação end-to-end

**PR-1 e PR-2:**

```bash
alembic upgrade head                                              # PRIMEIRO: põe o banco local no head do repo (2676d7fdd987)
alembic revision --autogenerate -m "auditoria_dados_mestres_e_campos_slot"   # só então gerar a nova
alembic upgrade head                                              # aplica a migration 3a
alembic downgrade -1 && alembic upgrade head                      # confirma downgrade/upgrade limpos
pytest tests/unit/test_gestao_inventario.py -v                    # testes do plano
pytest tests/unit/test_inventario.py tests/unit/test_equipamentos.py tests/unit/test_equipamentos_xlsx.py -v  # regressão (RNF-08)
pytest -q                                                          # suíte completa
ruff check app/modules/equipamentos/ app/shared/core/enums.py
python scripts/run_app.py                                         # smoke manual
```

**PR-3 — sequência adicional, nesta ordem:**

```bash
# 1. PORTÃO: pré-check no banco de PRODUÇÃO (via SSH na VPS), não no local.
#    Se retornar qualquer linha, sanear antes de prosseguir.
# 2. PORTÃO: snapshot manual do banco de produção (Seção 16).
# 3. Só então:
alembic upgrade head            # aplica a 3b
alembic downgrade -1            # o downgrade da 3b devolve nulabilidade e derruba a UNIQUE
alembic upgrade head
pytest -q                       # tem de estar verde COM a Etapa 11 aplicada
alembic heads                   # deve retornar exatamente 1
```

> Testar o `downgrade` da 3b não é formalidade: é o caminho de retorno se a UNIQUE estourar em produção. Um `downgrade` que só foi lido, nunca executado, não é um plano de rollback.

**Smoke manual** (navegador, usuário ADMINISTRADOR):
1. Acessar `/configuracoes` → card "Equipamentos e PNs" → "Gerenciar Slots".
2. Criar um slot novo com `posicao_xlsx` preenchido.
3. Abrir `/inventario`, escolher uma aeronave, confirmar que o slot novo aparece na Loc certa (vazio).
4. Subir um XLSX de teste com PN/posição batendo com o slot novo → preview mostra o S/N encontrado (não `XXXXXXX-...`).
5. Editar o slot (descrição, ordem) e salvar — toast de sucesso.
6. Inativar o slot — confirmar que ele some de `/inventario` e do preview XLSX, mas continua visível na tela de gestão (marcado "Inativo").
6b. Reativar o mesmo slot — confirmar que ele volta a `/inventario` e ao preview XLSX.
7. Tentar remover um slot ocupado — modal mostra a lista de aeronaves impedientes.
8. No catálogo de PNs, clicar "Histórico" de um item — ver os registros CREATE/UPDATE com autor e data.
9. Corrigir um S/N de item errado pelo CRUD de itens.
9b. Tentar excluir um item criado pela tela (que herdou controles de vencimento) — deve vir 409 com mensagem sobre controles, **nunca** um erro 500.
9c. Abrir a auditoria de um slot editado — os valores anterior/novo precisam renderizar (prova de que a serialização JSON está correta).
10. Abrir DevTools → Console: nenhuma violação de CSP durante todo o fluxo.
11. Logar como ENCARREGADO: botões de escrita ocultos; tentativa direta via API retorna 403.

---

## 14. Riscos e armadilhas conhecidas

| # | Risco | Mitigação |
|---|---|---|
| R1 | `ALTER TABLE ... NOT NULL` falha se houver `sistema`/`posicao_xlsx` nulos no banco local | Backfill (`UPDATE ... SET x = ''`) **antes** do `batch_alter_table`, dentro da própria migration (Etapa 3) |
| R2 (reescrito) | `SlotInventarioCreate` com campos agora obrigatórios quebra os chamadores existentes. **Levantamento feito:** não é a UI o problema (de fato não há formulário de criação de slot hoje) — são as **suítes**: 18 das 20 construções de `SlotInventario(...)` em `tests/`/`scripts/` não passam `posicao_xlsx`, e 2 testes de API passariam a receber 422 | Etapa 11, executada logo após a migration, com `pytest -q` verde como critério de saída |
| R3 | Confundir `excluir_item` (novo, exclusão física do item) com `remover_item` (existente, encerra instalação) | Nomes deliberadamente diferentes (Etapa 7); revisar imports no router para não chamar a função errada |
| R4 | Slot inativado continua aparecendo no preview XLSX se o filtro da Etapa 8 for esquecido | Teste #3 e #9 da Etapa 10 cobrem isso explicitamente |
| R5 | `usuario_id` de auditoria vindo do payload em vez da sessão, reintroduzindo o BUG-01 | Toda assinatura de service novo recebe `usuario_id` como parâmetro explícito setado pelo router a partir de `current_user.id` — nunca de um campo do schema |
| R6 | `EntidadeAuditada`/`AcaoAuditoria` merge simultâneo em `enums.py` com outra feature em paralelo | Commits pequenos; conferir `git diff` de `enums.py` antes de abrir PR |
| R7 | Migration em conflito de `down_revision` com outra branch que também gera migration a partir do mesmo head `2676d7fdd987` | Reconferir `alembic heads` (deve haver 1 só) antes de abrir PR; rebase se necessário |
| R8 | Duas fontes de PN por slot já divergentes (`seed_slots.py` vs `scripts/maintenance/force_sync_slots.py` — MDP, DVR, UFCP, PIC/NAV) podem gerar confusão ao editar slot pela UI nova | Fora de escopo corrigir aqui; documentar no PR como débito técnico pré-existente, não introduzido por este plano |
| R9 | `POST /equipamentos/itens/{id}/remover` devolve 500 (`IntegrityError` da FK `ControleVencimento.item_id`) em vez de 409 — e esse é o caso **comum**, já que todo item criado pela API herda controles | Checagem explícita de `ControleVencimento` em `excluir_item` (Etapa 6) + teste #13b |
| R10 | Auditoria estoura `TypeError` ao serializar `uuid.UUID`/`datetime` na coluna `JSON`; o erro só aparece no primeiro `PATCH`/`DELETE` real, não na criação da tabela | `auditoria_service.snapshot()` obrigatório + normalização defensiva dentro de `registrar()` (Etapa 5) + teste #13c |
| R11 | Slot inativado fica permanentemente inacessível pela aplicação (some da listagem por RF-12 e não havia como reativar) | RF-13: `POST /slots/{id}/reativar` + `?incluir_inativos=true` (Etapas 6 e 7) + teste #9b |
| R12 | `ordem_exibicao` vira campo morto: o `sort` em Python de `listar_inventario_aeronave` (`service.py:322`) sobrescreve qualquer `ORDER BY` da query | Alterar a chave do `sort` e propagar `ordem_exibicao` até `InventarioItemOut` (Etapa 6, §7.2) + teste #13d |
| R13 | Migration gerada a partir do head errado (`b63e385e3395`, que é o do banco local) entra fora de ordem em relação a `2676d7fdd987` | `alembic upgrade head` **antes** do autogenerate; conferir `alembic heads` == 1 antes do PR |
| R14 (recalibrado: Alta → **Baixa**) | **Migration destrutiva chega a produção sem porteiro.** `deploy.yml:44` e `start.sh:28` rodam `alembic upgrade head` no deploy e a cada start, sob `set -e`: uma duplicata em `(nome_posicao, sistema)` na VPS faria o container **não subir** — outage, não degradação. **Pré-check de 2026-08-30: 0 duplicidades, 0 nulos em produção** — a condição de falha não existe hoje | Fatiar em 3 PRs (Seção 0.1); snapshot manual mantido; `downgrade` da 3b executado, não só lido; **reexecutar o pré-check antes do merge** — a janela entre hoje e o PR-3 permite criação de slots |
| R15 | Backup automático do R2 é *debounced por escrita* (`tasks.py:50-60`) e sobrescreve o estado pré-migration segundos depois — quem contar com ele como rollback encontra o banco já migrado | Snapshot manual antes do deploy do PR-3 (Seção 16) |
| R16 | ORM declarando `nullable=False` antes da migration 3b faz o `--autogenerate` do PR-2 emitir a alteração destrutiva sozinho, contrabandeando-a para um PR de baixo risco | Nulabilidade faseada na Etapa 2: `sistema`/`posicao_xlsx`/`created_at` só apertam no PR-3, junto da 3b |

---

## 15. Checklist de aceite (espelha a spec v2.2 §11 e §18)

- [ ] `PATCH /equipamentos/slots/{id}` edita slot; bloqueia troca de PN esperado com instalação ativa (409).
- [ ] `POST /equipamentos/slots/{id}/remover` exige justificativa; bloqueia se houver qualquer instalação vinculada (409).
- [ ] `POST /equipamentos/slots/{id}/inativar` marca `ativo=false` sem apagar histórico.
- [ ] `POST /equipamentos/slots/{id}/reativar` devolve o slot à operação (RF-13); `GET /equipamentos/slots/?incluir_inativos=true` lista os desligados.
- [ ] `GET /equipamentos/slots/{id}/ocupacao` lista as aeronaves impedientes.
- [ ] Criar slot sem `posicao_xlsx` retorna 422.
- [ ] Slot duplicado `(nome_posicao, sistema)` retorna 409.
- [ ] `PATCH /equipamentos/itens/{id}` corrige S/N/status; S/N duplicado no mesmo PN retorna 409.
- [ ] `POST /equipamentos/itens/{id}/remover` exige justificativa; bloqueia com 409 (nunca 500) se houver instalação **ou controle de vencimento** vinculado.
- [ ] Nenhum endpoint `DELETE` existente mudou de assinatura; "Remover PN" segue funcionando sem alteração no `configuracoes.js`.
- [ ] Toda escrita em PN/Slot/Item — **inclusive as três criações** — grava 1 registro em `auditoria_dados_mestres` com `usuario_id` da sessão (nunca do payload).
- [ ] `valores_anteriores`/`valores_novos` gravam e leem sem `TypeError` (UUID/datetime normalizados).
- [ ] `ordem_exibicao` altera de fato a ordem da grade de `/inventario`.
- [ ] `GET /equipamentos/auditoria` consulta a trilha, filtrável por entidade.
- [ ] Slot inativo não aparece em `/inventario` nem no preview XLSX.
- [ ] Slot novo criado pela API casa corretamente no preview XLSX (regressão do bug da Seção 1 da spec).
- [ ] ENCARREGADO/MANTENEDOR/INSPETOR recebem 403 em toda escrita nova.
- [ ] UI: modal "Gerenciar Slots" funcional em `/configuracoes`; zero violação de CSP.
- [ ] Etapa 11 concluída: as 20 construções de `SlotInventario(...)` e os 2 `POST /slots/` das suítes atualizados.
- [ ] `pytest -q` verde (suíte completa, sem regressão de comportamento em `/inventario` ou XLSX).
- [ ] `ruff check .` limpo.
- [ ] `alembic upgrade head` e `alembic downgrade -1` funcionam sem erro, com `down_revision = "2676d7fdd987"` e tipos `sa.Uuid()`.
- [ ] `alembic heads` retorna exatamente 1 head.

**Portões exclusivos do PR-3:**

- [x] Pré-check de duplicidade/nulos rodado no banco de **produção** (VPS) em 2026-08-30: 33 slots, 0 duplicidades, 0 nulos, `alembic_version=2676d7fdd987`.
- [ ] Pré-check **reexecutado** imediatamente antes do merge do PR-3 (a janela desde 2026-08-30 permite criação de novos slots) — resultado anexado ao PR.
- [ ] Snapshot manual do banco de produção tirado imediatamente antes do deploy (Seção 16).
- [ ] `alembic downgrade -1` da 3b **executado**, não apenas lido.
- [ ] Etapa 11 no mesmo commit da 3b, com `pytest -q` verde localmente antes de abrir o PR.

---

## 16. Rollback

> ⚠️ A Seção 19 da spec v2.0 dizia "restauração do arquivo `saa29_local.db` a partir de backup". Isso descreve o ambiente de desenvolvimento, **não** o de produção. O que segue é o mecanismo real.

### Como o banco de produção é preservado hoje

| Passo | Onde | Efeito |
|---|---|---|
| Restore na subida | `scripts/start.sh:23` | `r2_manager.py restore` — o container **restaura o banco do R2 ao iniciar** |
| Migração automática | `scripts/start.sh:28` e `deploy.yml:44` | `alembic upgrade head`, sem porteiro, sob `set -e` |
| Backup | `app/bootstrap/tasks.py:50-60` | *debounced por escrita*: após uma escrita, agenda `r2_manager.py backup` |

### A consequência que obriga ao snapshot manual

O backup é disparado **por escrita**, não por deploy. Assim que a primeira escrita acontece depois da migration, o snapshot no R2 **já é o banco migrado** — o estado pré-migration é sobrescrito em segundos. **Não existe snapshot pré-migration automático.** Confiar no backup automático como ponto de retorno é confiar em algo que já foi substituído.

### Procedimento

**Antes do deploy do PR-3:**

O banco de produção fica em `/app/data/saa29.db`, no volume `sqlite_data` do serviço `web` (`docker-compose.yml:8-13`).

```bash
# Na VPS (~/saa29), com a aplicação ainda no estado pré-migration.
# Snapshot consistente via API nativa do SQLite — não copiar o arquivo a quente:
docker-compose exec -T web python -c \
  "import sqlite3; s=sqlite3.connect('/app/data/saa29.db'); d=sqlite3.connect('/tmp/pre_3b.db'); s.backup(d); d.close(); s.close()"

# Tirar a cópia de dentro do container, para fora do fluxo do R2 (que será sobrescrito):
docker cp "$(docker-compose ps -q web)":/tmp/pre_3b.db ./pre_3b_$(date +%F).db
```

> `cp` direto do arquivo `.db` com a aplicação no ar pode capturar um estado inconsistente (WAL em andamento). `sqlite3.backup()` é o mesmo mecanismo que o `r2_manager.py:70-77` já usa por esse motivo.

**Se a 3b falhar (container não sobe):**

1. `git revert` do merge do PR-3 em `main` e redeploy — a 3b não terá sido aplicada, já que a falha aborta o `upgrade`.
2. Se a 3b foi aplicada parcialmente: restaurar `pre_3b_<data>.db` sobre o volume e subir com o `main` revertido.
3. `alembic downgrade -1` só é utilizável se o container subir — daí o passo 1 vir primeiro.

**PR-1 e PR-2** não precisam deste procedimento: a 3a é reversível por `downgrade` sem perda de dado, e o PR-2 não tem migration. Um `git revert` + redeploy basta.

### Por que não há feature flag

Não existe infraestrutura de flags no projeto. As rotas novas são **aditivas** — não alteram o comportamento de `/inventario` nem do "Sincronizar" — então reverter o merge é suficiente para PR-1 e PR-2. Só o PR-3 muda dado existente, e é por isso que ele viaja sozinho.
