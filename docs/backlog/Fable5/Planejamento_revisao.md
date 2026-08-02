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

### 🔹 ETAPA 3: Módulo de Vencimentos & Inspeções
* **Arquivos Alvo:**
  - `app/modules/vencimentos/service.py` & `models.py`
  - `app/modules/inspecoes/service.py` & `models.py`
  - `app/modules/inspecoes/pdf_service.py`
* **Relatório a Gerar:** `docs/backlog/Fable5/relatorio_vencimentos_inspecoes.md`
* **Foco Técnico:**
  - Otimização de cálculos de prazos e periodicidades (evitar consultas desnecessárias ao banco).
  - Cascata de atualização de status do inventário quando uma inspeção é concluída ou aberta.
  - Performance da geração de PDFs via ReportLab (alocação de memória e tratamento de imagens).
  - RBAC e segregação de funções (validação de inspetor vs mantenedor).

---

### 🔹 ETAPA 4: Autenticação, Usuários & Segurança Central
* **Arquivos Alvo:**
  - `app/modules/auth/service.py`, `security.py`, `router.py`
  - `app/shared/middleware/csrf.py` & `dependencies.py`
* **Relatório a Gerar:** `docs/backlog/Fable5/relatorio_auth_seguranca.md`
* **Foco Técnico:**
  - Validação rigorosa de rotação de Refresh Tokens e invalidação de família em tentativa de reuso.
  - Mitigação de ataques de Timing em comparações de tokens e senhas (bcrypt/sha256).
  - Verificação de headers CSRF e tratamento de Cookies `HttpOnly` / `SameSite`.
  - Prevenção de vazamento de informações técnicas em respostas de erro da API.

---

### 🔹 ETAPA 5: Shared Core, Database Bootstrap & Exportadores
* **Arquivos Alvo:**
  - `app/bootstrap/database.py` & `main.py`
  - `app/shared/exporter.py`
  - `app/shared/core/file_validators.py` & `storage.py`
* **Relatório a Gerar:** `docs/backlog/Fable5/relatorio_core_bootstrap.md`
* **Foco Técnico:**
  - Garantia de PRAGMAs de performance no SQLite (`WAL mode`, `synchronous=NORMAL`).
  - Otimização da geração de relatórios CSV/XLSX em lote para evitar picos de memória.
  - Tratamento de exceções e resiliência em uploads/rollbacks com o storage Cloudflare R2.
  - Centralização dos Exception Handlers globais no FastAPI.

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
| **Etapa 3** | Vencimentos & Inspeções | ⚪ Pendente | `relatorio_vencimentos_inspecoes.md` | — |
| **Etapa 4** | Auth & Segurança | ⚪ Pendente | `relatorio_auth_seguranca.md` | — |
| **Etapa 5** | Core & Infraestrutura | ⚪ Pendente | `relatorio_core_bootstrap.md` | — |

---
*Plano de Otimização e Refatoração FABLE 5 — Sistema SAA29.*
