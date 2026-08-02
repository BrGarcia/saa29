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

### 🔹 ETAPA 1: Módulo de Equipamentos & Inventário
* **Arquivos Alvo:**
  - `app/modules/equipamentos/service.py`
  - `app/modules/equipamentos/models.py`
  - `app/modules/equipamentos/router.py`
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_equipamentos_services.md`
* **Foco Técnico:**
  - 🔴 **Bug Crítico:** Import faltante de `Aeronave` em `_validar_e_resolver_conflitos` (`NameError`).
  - 🔴 **N+1 Query:** Busca sequencial de remoções no loop `listar_inventario_aeronave` (otimizar com window function `row_number()`).
  - 🔴 **Concorrência (TOCTOU):** Falta de tratamento de `IntegrityError` em `criar_modelo` e `_obter_ou_criar_item_por_pn`.
  - 🟡 **Dívida Técnica:** Duplicação da herança de vencimentos (`_herdar_controles_do_modelo`).
  - 🟢 **Limpeza & Logging:** Substituir `print`/`traceback` por `logging` e padronizar exceções de domínio (`domain_exc`).

---

### 🔹 ETAPA 2: Módulo de Panes & Anexos
* **Arquivos Alvo:**
  - `app/modules/panes/service.py`
  - `app/modules/panes/models.py`
  - `app/modules/panes/router.py`
* **Relatório de Referência:** `docs/backlog/Fable5/relatorio_panes_service.md`
* **Foco Técnico:**
  - 🔴 **Sincronização de Status:** `editar_pane` não sincroniza status da aeronave ao marcar `RESOLVIDA`.
  - 🔴 **Bug de Busca SQL:** `_escape_like` sem declaração `escape="\\"` em queries `.like()` / `.ilike()`.
  - 🔴 **Durabilidade em Background:** Risco de anexos presos em "processando" caso o processo reinicie.
  - 🔴 **Race Conditions:** Duplicidade de responsáveis (`TOCTOU`) e concorrência na exclusão de anexos.
  - 🟡 **Gerenciamento de Memory Stream:** Validação de tamanho de upload antes de carregar o payload inteiro na RAM.

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
| **Etapa 1** | Equipamentos & Inventário | 🟡 Prontidão para Execução | `relatorio_equipamentos_services.md` | — |
| **Etapa 2** | Panes & Anexos | 🟡 Relatório Criado | `relatorio_panes_service.md` | — |
| **Etapa 3** | Vencimentos & Inspeções | ⚪ Pendente | `relatorio_vencimentos_inspecoes.md` | — |
| **Etapa 4** | Auth & Segurança | ⚪ Pendente | `relatorio_auth_seguranca.md` | — |
| **Etapa 5** | Core & Infraestrutura | ⚪ Pendente | `relatorio_core_bootstrap.md` | — |

---
*Plano de Otimização e Refatoração FABLE 5 — Sistema SAA29.*
