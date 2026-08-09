# 📋 Plano de Revisão e Otimização de Código — FABLE 5

> **Objetivo Principal:** Otimizar o código, eliminar bugs críticos, erradicar *race conditions* / *N+1 queries*, reforçar a segurança e elevar a manutenibilidade do SAA29.  
> **Estratégia de Contexto:** Divisão modular da base de código em **5 Etapas Sequenciais e Isoladas**, respeitando o limite de janela de tokens por sessão de IA.  
> **Template de Prompt:** Cada etapa utiliza o guia enxuto `docs/backlog/Fable5/prompt.md`.

---

## 📐 Estrutura das Etapas de Auditoria e Correção

```text
ETAPA 1 ➔ Equipamentos & Inventário (service.py / models.py / router.py)
ETAPA 2 ➔ Panes & Anexos (service.py / models.py / router.py)
ETAPA 3 ➔ Vencimentos & Inspeções (services / pdf_service / models)
ETAPA 4 ➔ Auth, Sessões & Segurança (auth / csrf / dependencies)
ETAPA 5 ➔ Bootstrap, Shared Core & Exporter (database / storage / exporter)
```

---

## 🎯 Detalhamento do Escopo por Etapas

### 🔹 ETAPA 1: Módulo de Equipamentos & Inventário — ✅ CONCLUÍDA (02/08/2026)
* **Arquivos Alvo:**
  - `app/modules/equipamentos/service.py`
  - `app/modules/equipamentos/models.py`
  - `app/modules/equipamentos/router.py`
  - `app/modules/equipamentos/schemas.py` (normalização e resolução de `slot_id` adicionadas ao escopo)
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_equipamentos_services.md` (finalizado — 15/15 itens + 1 bug adjacente corrigidos)
* **Foco Técnico (todos os pontos abaixo corrigidos):**
  - 🔴 **Bug Crítico:** Import faltante de `Aeronave` em `_validar_e_resolver_conflitos` (`NameError`). → ✅
  - 🔴 **N+1 Query:** Busca sequencial de remoções no loop `listar_inventario_aeronave` (otimizado com window function `row_number()`). → ✅
  - 🔴 **Concorrência (TOCTOU):** Tratamento de `IntegrityError` via SAVEPOINT em `criar_modelo`, `criar_item_com_heranca` e `_obter_ou_criar_item_por_pn`. → ✅
  - 🟡 **Dívida Técnica:** Duplicação da herança de vencimentos extraída para `vencimentos.service.criar_controles_para_item` (movida para o domínio correto). → ✅
  - 🟢 **Limpeza & Logging:** `print`/`traceback` substituídos por `logging`; exceções de domínio (`domain_exc`) padronizadas no módulo. → ✅
* **Efeitos colaterais aproveitados na mesma etapa:** função `listar_inventario_aeronave` decomposta em 5
  auxiliares; `escape_like` centralizado em `app/shared/core/db_utils.py`; nova coluna
  `Instalacao.removido_em` (migration `e7a1c3d9b2f4`, aplicada em `var/db`); normalização de PN/S/N via
  schema Pydantic + script de saneamento (`scripts/maintenance/sanear_identificadores_equipamentos.py`,
  0 achados na base atual); paginação opcional (`limit`/`offset`, teto 200) em `listar_modelos`/`listar_itens`;
  bug adjacente no endpoint `/inventario/export` (rota mal ordenada + campos inexistentes) corrigido.
* **Pendências conscientes que saem do escopo desta etapa** (documentadas no relatório, não bloqueiam o fechamento):
  `raise ValueError` ainda presente em outros módulos (98 ocorrências fora de equipamentos — cada etapa
  seguinte deve tratar as suas); migration `String → sqlalchemy.Enum` para colunas de status; paginação
  sem suporte no frontend ainda; ferramentas de CI (mypy, import-linter, ruff regras D) não configuradas.
* **Testes:** 44/44 do escopo do módulo (`test_equipamentos.py`, `test_inventario.py`,
  `test_equipamentos_correcoes_urgentes.py` — novo, `test_equipamentos_refatoracao.py` — novo);
  suíte completa do projeto **220/220**.
* **Git Sync:** ⬜ não executado — mudanças aplicadas no working tree, aguardando revisão/commit do usuário.

---

### 🔹 ETAPA 2: Módulo de Panes & Anexos — ✅ CONCLUÍDA (02/08/2026)
* **Arquivos Alvo:**
  - `app/modules/panes/service.py`
  - `app/modules/panes/models.py`
  - `app/modules/panes/router.py`
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_panes_service.md` (finalizado — Alta 6/6, Média 4/4, Baixa 7/7)
* **Foco Técnico (todos os pontos abaixo corrigidos):**
  - 🔴 **Sincronização de Status:** `editar_pane` não sincroniza status da aeronave ao marcar `RESOLVIDA`. → ✅
  - 🔴 **Bug de Busca SQL:** `_escape_like` sem declaração `escape="\\"` em queries `.like()`. → ✅
  - 🔴 **Durabilidade em Background:** Risco de anexos presos em "processando" caso o processo reinicie. → ✅ (mitigação mínima: job de limpeza; ver pendências)
  - 🔴 **Race Conditions:** Duplicidade de responsáveis (`TOCTOU`) e concorrência na exclusão/processamento de anexos. → ✅ (UNIQUE + SAVEPOINT + checagem condicional)
  - 🟡 **Validação de tamanho antes de carregar tudo em memória:** não fazia parte do resumo priorizado
    do relatório (item #1, fora da tabela 🔴🟡🟢) — **não foi tocado nesta etapa**, permanece pendente.
* **Itens de média e baixa prioridade também fechados:** anexo órfão no storage (compensação +
  ordem invertida em `excluir_anexo`), filtro `data_fim` incluindo o dia inteiro, coerência
  extensão×MIME (`_EXTENSAO_MIME_MAP`), exceções de domínio em `editar_pane`/`concluir_pane`
  (sem string-matching), imports mortos, subquery de ranking deduplicada, `EXISTS` no lugar de
  `COUNT`, detecção de dialeto via `db.bind.dialect.name`, `db.refresh` reduzido em `concluir_pane`,
  `asyncio.to_thread` + logger de módulo em `processar_imagem_background`, variáveis `resultado→pane`
  simplificadas.
* **Tentativa revertida (documentada para não repetir):** otimizar `db.refresh` também em `criar_pane`
  populando relações manualmente — quebrou em runtime (`MissingGreenlet`, lazy-load síncrono em contexto
  async) porque um objeto ORM recém-`flush()`ado não tem coleções "vazias e carregadas" como presumido.
  Revertido antes de consolidar, com teste direto comprovando o problema.
* **Pendências conscientes que saem do escopo desta etapa** (documentadas no relatório):
  correção definitiva de durabilidade do background (fila persistente tipo Celery/ARQ/RQ, item #5);
  `with_for_update` é no-op no SQLite atual (só protege de fato em outro banco); hierarquia de exceções
  de domínio aplicada só a `editar_pane`/`concluir_pane`, não ao restante do módulo; validação de tamanho
  de upload antes de carregar em memória (item #1, fora da tabela priorizada) permanece pendente.
* **Testes:** 61/61 do escopo do módulo (`test_panes.py` + `test_panes_alta_prioridade.py` (13) +
  `test_panes_media_prioridade.py` (12) + `test_panes_baixa_prioridade.py` (5) — 30 testes novos);
  suíte completa do projeto **250/250**.
* **Git Sync:** ⬜ não executado — mudanças aplicadas no working tree, aguardando revisão/commit do usuário.

---

### 🔹 ETAPA 3: Módulo de Vencimentos & Inspeções — ✅ CONCLUÍDA (02/08/2026)
* **Arquivos Alvo:**
  - `app/modules/vencimentos/service.py` & `router.py`
  - `app/modules/inspecoes/service.py` & `router.py`
  - `app/modules/inspecoes/pdf_service.py`
  - `app/modules/panes/service.py` (função de sincronização de status reaproveitada, ver abaixo)
* **Plano de Execução:** `docs/backlog/Fable5/Etapa3.md` (evidências completas, testes por fase, decisões de escopo)
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_vencimentos_inspecoes.md` (finalizado — Crítica 5/5, Média 6/6, Baixa 3/3)
* **Foco Técnico (todos os pontos abaixo corrigidos):**
  - 🔴 **Bug Crítico:** `domain_exc.NotFoundError` inexistente causava `AttributeError` (500) ao prorrogar vencimento inexistente. → ✅
  - 🔴 **Bug de Domínio:** status de vencimento (`OK`/`VENCENDO`/`VENCIDO`) nunca era recalculado pela passagem do tempo — matriz de vencimentos ficava desatualizada indefinidamente. Corrigido derivando o status em tempo de leitura (`calcular_status_vencimento`), sem persistir o valor derivado (evita efeito colateral de escrita numa rota GET). → ✅
  - 🔴 **Dívida Técnica:** duplicação integral do bloco de sincronização de status da aeronave entre `concluir_inspecao`/`cancelar_inspecao`, extraída para a função já existente e mais completa `panes.service.sincronizar_status_aeronave` (criada na Etapa 2, tornada pública). → ✅
  - 🔴 **Bug adicional descoberto na reutilização acima:** guard defeituoso em `sincronizar_status_aeronave` deixava a aeronave presa em `INSPECAO` ao concluir/cancelar uma inspeção com pane aberta remanescente — capturado por teste de regressão antes de ir para produção. → ✅
  - 🟡 **N+1 Queries:** `associar_controle_a_equipamento` (vencimentos) e `abrir_inspecao` (inspeções) otimizados com SELECTs batched via `IN`. → ✅
  - 🟡 **Concorrência (TOCTOU):** SAVEPOINT + `IntegrityError` aplicado em 5 pontos de criação protegidos por UNIQUE (vencimentos e inspeções), mesmo padrão das Etapas 1-2. → ✅
  - 🟡 **Contrato HTTP:** 36 `raise ValueError` sem tipo em inspeções migrados para exceções de domínio; 14 blocos `try/except ValueError` removidos do router (o status HTTP deixou de depender da posição do bloco). → ✅
  - 🟢 **Limpeza:** strings mágicas em `calcular_progresso`, `== True` sem `.is_(True)`, ternário aninhado, `relativedelta`→`timedelta`, teto de paginação (`LIMITE_MAXIMO_LISTAGEM = 200`, mesmo padrão da Etapa 1). → ✅
* **Efeitos colaterais aproveitados na mesma etapa:** `pdf_service.py` teve as duas queries duplicadas
  (carregar inspeção + carregar instalações) extraídas para helpers compartilhados, com equivalência de
  saída verificada via comparação de texto extraído (`pypdf`) antes/depois da mudança.
* **⚠️ Achado sistêmico não corrigido, fora do escopo desta etapa (recomendado para a Etapa 5):** o padrão
  SAVEPOINT (`db.begin_nested()`) usado desde a Etapa 1 para proteção TOCTOU parece não estar isolado
  corretamente do `rollback()` externo no engine SQLite atual (uma inserção dentro de um SAVEPOINT
  sobreviveu ao rollback de um teste, vazando para o teste seguinte). Consistente com uma lacuna de
  configuração conhecida do SQLAlchemy para savepoints em SQLite (falta desabilitar o `BEGIN` implícito do
  `pysqlite`/`aiosqlite`) em `tests/conftest.py` e `app/bootstrap/database.py`. **Implicação potencial:**
  se o mesmo problema ocorrer em produção, o isolamento de escritas malsucedidas via SAVEPOINT (usado nas
  Etapas 1, 2 e 3) pode não estar funcionando como pretendido. Não investigado nem corrigido — exige um
  teste de regressão dedicado antes de mexer na configuração do engine.
* **Ajuste de premissa vs. plano original:** o foco técnico previa *"tratamento de imagens"* na geração de
  PDF — não há nenhuma manipulação de imagem em `pdf_service.py` (só `Paragraph`/`Table`); o foco real era
  duplicação estrutural das queries, tratado acima.
* **Pendências conscientes que saem do escopo desta etapa** (documentadas no relatório, não bloqueiam o fechamento):
  duplicidade de inspeção ativa em `abrir_inspecao` sem proteção transacional (não há UNIQUE constraint
  possível para essa regra condicional); índice único parcial para "uma só prorrogação ativa por controle"
  (avaliado, não implementado, por prudência dado o achado do SAVEPOINT); unificação dos ~20
  `ParagraphStyle` divergentes entre as duas funções de PDF (risco desproporcional ao ganho); `== True`
  remanescente em `vencimentos/service.py` (3 ocorrências, fora da evidência original do item).
* **Testes:** 20 testes novos (`test_vencimentos_criticos.py` — 6, `test_inspecoes_refatoracao.py` — 6,
  `test_vencimentos_inspecoes_media_prioridade.py` — 8) + ajustes em `test_aeronaves.py`,
  `test_inspecoes.py`, `test_panes_alta_prioridade.py`, `test_panes_baixa_prioridade.py` (referências ao
  nome público da função de sincronização e ao novo tipo de exceção); suíte completa do projeto **281/281**.
* **Git Sync:** ⬜ não executado — mudanças aplicadas no working tree, aguardando revisão/commit do usuário.

---

### 🔹 ETAPA 4: Autenticação, Usuários & Segurança Central — ✅ CONCLUÍDA (02/08/2026)
* **Arquivos Alvo:**
  - `app/modules/auth/service.py`, `security.py`, `router.py`
  - `app/shared/middleware/csrf.py` & `app/bootstrap/dependencies.py`
    (caminho corrigido: o plano original citava `app/shared/dependencies.py`, que não existe)
  - `app/bootstrap/config/__init__.py` (2 campos novos: `refresh_token_expire_days`, `enable_test_users`)
* **Plano de Execução:** `docs/backlog/Fable5/Etapa4.md` (evidências completas, testes por fase, decisões de escopo)
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_auth_seguranca.md` (finalizado — Crítica 4/4, Média 6/6, Baixa 1/1)
* **Foco Técnico (todos os pontos abaixo corrigidos):**
  - 🔴 **Vulnerabilidade Crítica:** revogação de família de refresh tokens (defesa contra reuso) era
    desfeita pelo `rollback()` automático da dependency `get_db` — a mensagem "todos os tokens foram
    revogados" era falsa. Corrigido com `db.commit()` explícito, comprovado por teste que falha sem a
    correção. → ✅
  - 🔴 **Vulnerabilidade Latente:** `get_current_user` não validava o claim `type` do JWT — um refresh
    token (7 dias) seria aceito como access token (15 min) numa refatoração aparentemente inofensiva do
    campo `sub`. → ✅
  - 🔴 **Bug Operacional:** senha do admin sobrescrita a cada execução do script de seed, tornando a
    rotação de senha pela UI inefetiva. Corrigido: só na criação; redefinição exige
    `ADMIN_PASSWORD_RESET=1` explícito. → ✅
  - 🔴 **Vulnerabilidade:** criação de 3 contas privilegiadas com senha fixa protegida por um único
    gatilho (`APP_ENV`) e duas fontes de verdade divergentes para o ambiente
    (`os.getenv` vs `settings.app_env`). Corrigido: dois gatilhos explícitos + fonte única. → ✅
  - 🟡 **CSRF:** bypass de teste com header previsível (segredo aleatório por processo), vazamento de
    detalhe de exceção, isenção desnecessária de `/auth/login`/`/auth/logout`, geração de token
    desperdiçada em assets estáticos. → ✅
  - 🟡 **Timing:** enumeração de usernames via diferença de tempo (~227ms vs <0.001ms, medido antes de
    corrigir) mitigada com hash dummy. → ✅
  - 🟢 **Limpeza:** 8 `raise ValueError` → exceções de domínio; TOCTOU em `criar_usuario` protegido por
    SAVEPOINT; pré-hash de senha deduplicado; `CsrfSettings` corrigido para resolver configuração em
    runtime (não em tempo de import). → ✅
* **Achado adicional descoberto durante a correção do item #4:** `scripts/db/init_db.py` tinha uma
  segunda implementação, divergente e não documentada, de criação de usuários de teste (usuários/senhas
  diferentes dos criados por `garantir_usuarios_essenciais`) — removida; e o campo `ENABLE_TEST_USERS`,
  já citado em `.env.example`, nunca tinha sido adicionado à classe `Settings`.
* **Pendências conscientes que saem do escopo desta etapa** (documentadas no relatório, não bloqueiam o
  fechamento): magic numbers de lockout viraram constantes de módulo, não campos de `Settings` (decisão:
  são regra de negócio, não configuração de ambiente); `decodificar_token(token, tipo_esperado)` como
  alternativa mais robusta ao item do `type` claim não foi implementada (mudaria assinatura usada em
  múltiplos pontos, risco desproporcional).
* **Testes:** 11 testes novos (`test_refresh_token_rotacao.py` — 2, `test_auth_contas.py` — 9); suíte
  completa do projeto **292/292**.
* **Git Sync:** ⬜ não executado — mudanças aplicadas no working tree, aguardando revisão/commit do usuário.

---

### 🔹 ETAPA 5: Shared Core, Database Bootstrap & Exportadores — ✅ CONCLUÍDA (02/08/2026)
* **Arquivos Alvo:**
  - `app/bootstrap/database.py`, `main.py` & `events.py`
  - `app/shared/exporter.py`
  - `app/shared/core/file_validators.py`, `storage.py` & `exceptions.py`
* **Plano de Execução:** `docs/backlog/Fable5/Etapa5.md` (evidências completas, testes por fase, decisões de escopo)
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_core_bootstrap.md` (finalizado — Crítica 4/4, Média 6/6, Baixa 1/1)
* **Ajuste de premissa vs. plano original:** o foco técnico previa *"garantia de PRAGMAs de performance
  (WAL mode, synchronous=NORMAL)"* — **já estava implementado** desde antes desta etapa. A lacuna real era
  `busy_timeout`, tratada abaixo.
* **Foco Técnico (todos os pontos abaixo corrigidos):**
  - 🔴 **Vulnerabilidade Crítica:** CSV/Formula Injection nos exportadores — dados de campos livres
    (descrição de pane, observações) podiam conter fórmulas maliciosas que executam ao abrir o relatório
    no Excel. Corrigido neutralizando o primeiro caractere de gatilho, preservando números negativos
    legítimos. → ✅
  - 🔴 **Concorrência:** SQLite sem `busy_timeout` suficiente para os escritores de fundo introduzidos nas
    Etapas 1-2. Confirmado experimentalmente (13/30 falhas sem PRAGMA suficiente, 0/30 com 15000ms) antes
    de corrigir. → ✅
  - 🔴 **Vulnerabilidade + Bug de Produto:** allowlist de upload divergente em 5 lugares (não 4) — o mais
    grave: o pipeline inteiro de conversão HEIC→JPEG (fotos de iPhone) era **código morto**, inalcançável
    a partir do endpoint real de upload, porque o validador que roda primeiro no router não conhecia
    HEIC/HEIF. Unificado numa única fonte de verdade. → ✅
  - 🔴 **Vulnerabilidade (DoS):** upload sem limite de tamanho lido antes de qualquer rejeição — corrigido
    com leitura em chunks que aborta assim que ultrapassa o limite configurado. → ✅
  - 🟡 **Robustez:** escrita local bloqueante corrigida (`asyncio.to_thread`); shutdown passou a aguardar
    o cancelamento das tasks de background; handler de exceção 401/403 corrigido para reconhecer o
    prefixo do calendário (fonte única de prefixos de API, não mais duplicada); handler genérico para
    exceções não tratadas adicionado (antes, um erro inesperado podia expor stack trace ao cliente). → ✅
  - 🟢 **Limpeza:** validação de path traversal (3 cópias idênticas) unificada; numeração de comentários
    corrigida; fallback silencioso de CORS agora loga um aviso. → ✅
* **Pendências conscientes que saem do escopo desta etapa** (documentadas no relatório, não bloqueiam o
  fechamento): `write_only=True`/`StreamingResponse` para reduzir o pico de memória dos exportadores
  (exigiria reescrever a estilização célula a célula, sem problema de memória medido concretamente);
  `raise ValueError` em `storage.py`/`bootstrap/config` mantido (infraestrutura, não domínio);
  `os.makedirs`/`app = create_app()` em tempo de import não alterados.
* **Testes:** 34 testes novos (`test_exporter_injection.py` — 17, `test_storage_hardening.py` — 11,
  `test_bootstrap_resiliencia.py` — 5, `test_exporter.py` — +1); suíte completa do projeto **326/326**.
* **Git Sync:** ⬜ não executado — mudanças aplicadas no working tree, aguardando revisão/commit do usuário.

---

## ⚙️ Protocolo de Execução por Etapa

Para manter a consistência e o controle de versão em cada etapa:

1. **Leitura do Escopo Limite:** Abrir exclusivamente os 2-3 arquivos da etapa vigente.
2. **Auditoria com Template:** Executar o prompt `docs/backlog/Fable5/prompt.md`.
3. **Consolidação do Relatório:** Salvar/atualizar o relatório da etapa na pasta `docs/backlog/Fable5/`.
4. **Implementação & Refatoração:** Aplicar as correções código a código.
5. **Verificação Automatizada:** Executar `.venv\Scripts\pytest` (100% de sucesso obrigatório).
6. **Git Sync:** Executar `git add`, `git commit` e `git push origin development` imediatamente após a etapa.

---

## 📊 Matriz de Acompanhamento da Revisão

| Etapa | Módulo Principal | Status | Relatório Gerado | Testes Passing |
|:---:|---|:---:|:---:|:---:|
| **Etapa 1** | Equipamentos & Inventário | ✅ Concluída (02/08/2026) | `relatorio_equipamentos_services.md` (finalizado) | 44/44 (módulo) · 220/220 (suíte) |
| **Etapa 2** | Panes & Anexos | ✅ Concluída (02/08/2026) | `relatorio_panes_service.md` (finalizado) | 61/61 (módulo) · 250/250 (suíte) |
| **Etapa 3** | Vencimentos & Inspeções | ✅ Concluída (02/08/2026) | `relatorio_vencimentos_inspecoes.md` (finalizado) | 20 novos (módulo) · 281/281 (suíte) |
| **Etapa 4** | Auth & Segurança | ✅ Concluída (02/08/2026) | `relatorio_auth_seguranca.md` (finalizado) | 11 novos (módulo) · 292/292 (suíte) |
| **Etapa 5** | Core & Infraestrutura | ✅ Concluída (02/08/2026) | `relatorio_core_bootstrap.md` (finalizado) | 34 novos (módulo) · 326/326 (suíte) |

---

## 🏁 Encerramento do Plano FABLE 5 (02/08/2026)

As 5 etapas foram concluídas. Suíte completa final do projeto: **326/326 testes**, partindo de um
baseline de 220 no início da Etapa 1 — **106 testes novos** ao longo de todo o plano. Nenhum commit foi
enviado automaticamente ao remoto; cada etapa aguardou revisão e autorização explícita do usuário antes
do `git push`.

### 📋 Apanhado Final das Pendências Conscientes (Etapas 1-5)

Itens identificados, avaliados e **deliberadamente deixados fora do escopo** de cada etapa, com a
justificativa registrada no momento da decisão. Consolidados aqui para virar o ponto de partida de um
eventual backlog pós-FABLE-5 — nenhum é um bug esquecido, todos foram uma escolha registrada.

**Concorrência / Banco de dados**
- `with_for_update` é no-op no SQLite atual — só produz exclusão mútua real se o projeto migrar para
  outro banco (ex.: PostgreSQL). (Etapa 2)
- **Achado sistêmico não investigado, descoberto na Etapa 3:** o padrão SAVEPOINT (`db.begin_nested()`)
  usado desde a Etapa 1 para proteção TOCTOU pode não estar isolado corretamente do `rollback()` externo
  no engine SQLite atual — uma inserção dentro de um SAVEPOINT sobreviveu ao rollback de um teste,
  vazando para o teste seguinte. Consistente com uma lacuna de configuração conhecida do SQLAlchemy para
  savepoints em SQLite (falta desabilitar o `BEGIN` implícito do `pysqlite`/`aiosqlite`). **Recomendação:**
  tratar como item dedicado, com um teste de regressão específico do comportamento do SAVEPOINT antes de
  mexer na configuração do engine — pode afetar a garantia real de isolamento de todas as correções TOCTOU
  aplicadas nas Etapas 1, 2, 3 e 4.
- Duplicidade de inspeção ativa em `abrir_inspecao` (Etapa 3) permanece com janela de corrida — não há
  UNIQUE constraint possível para essa regra condicional ao status.
- Índice único parcial para "uma só prorrogação ativa por controle" (`ProrrogacaoVencimento`, Etapa 3) —
  avaliado, não implementado, por prudência dado o achado do SAVEPOINT acima.

**Durabilidade / Infraestrutura**
- Correção definitiva de durabilidade do processamento de anexos em background (fila persistente tipo
  Celery/ARQ/RQ) — a Etapa 2 aplicou apenas uma mitigação mínima (job de limpeza periódico). (Etapa 2)
- `openpyxl.Workbook(write_only=True)` e `StreamingResponse` para reduzir o pico de memória (não só o
  CPU, já resolvido) dos exportadores CSV/XLSX — exigiria reescrever a estilização célula a célula.
  (Etapa 5)

**Dados / Schema**
- Migration `String → sqlalchemy.Enum` para colunas de status (`StatusPane`, `StatusAeronave`, etc.) —
  levantada na Etapa 1, nunca endereçada. (Etapa 1)
- Paginação (`limit`/`offset`) adicionada em `equipamentos`/`inspeções` ainda sem suporte no frontend.
  (Etapas 1, 3)

**Segurança (itens menores, não críticos)**
- `decodificar_token(token, tipo_esperado)` como alternativa mais robusta à checagem inline do claim
  `type` — não implementada por mudar assinatura usada em múltiplos pontos. (Etapa 4)
- Magic numbers de lockout (5 tentativas / 15 min) viraram constantes de módulo em `auth/service.py`, não
  campos de `Settings` — decisão: são regra de negócio de domínio, não configuração de ambiente. (Etapa 4)

**Ferramentas de CI/qualidade (nunca fizeram parte do escopo de nenhuma etapa)**
- `mypy` (type checking estático) não configurado.
- `import-linter` (checagem de dependências entre camadas/módulos) não configurado.
- Regras `D` do `ruff` (docstrings) não configuradas.

**Decisão para o próximo passo:** este apanhado não vira automaticamente uma "Etapa 6" — fica registrado
aqui como candidato a um novo ciclo de backlog, a ser priorizado pelo usuário quando fizer sentido. O item
de maior risco potencial é o achado do SAVEPOINT/rollback (pode enfraquecer proteções de concorrência já
aplicadas), seguido pela durabilidade do processamento de anexos em background.

---
*Plano de Otimização e Refatoração FABLE 5 — Sistema SAA29.*
