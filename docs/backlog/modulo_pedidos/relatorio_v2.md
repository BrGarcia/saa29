# Relatório v2 — Auditoria da Feature Central de Pedidos

> **Finalidade:** documento de **consulta** (changelog conceitual da auditoria). Substitui `relatorio.md`.
> **Planejamento vive em:** `feature_controle_pedidos.md` (v1.3) — fonte única.
> **Artefatos:** `feature_controle_pedidos.md` (spec) · `mockup_pedidos.html` (visual, nesta pasta).
> **Data:** 2026-08-02 · **Status:** ✅ correções aplicadas no feature v1.2; verificação contra o código na v1.3 (2026-08-03, §7).

---

## 1. Veredito

Spec madura e alinhada ao SAA29. A auditoria v1 estava majoritariamente correta, mas continha **1 erro factual** e **omitia validações de segurança**. Tudo consolidado no feature v1.2. Pronto para implementação.

---

## 2. Correções conceituais aplicadas (v1.2)

| Tema | Antes (v1.1) | Agora (v1.2) |
|---|---|---|
| **Pedido × Inventário** | Atender "instalava" o item (§2.1 conflava os dois) | **Desacoplados.** Atender é administrativo (RN-12); não instala e não baixa pendência (RN-14). Instalação segue no inventário. |
| **Semântica "Atendido"** | Ambígua | Fechada como **atendimento administrativo**. Item pode ir a outra ANV → novo pedido p/ a original. |
| **RBAC** | Ausente; rascunho incluía MANTENEDOR criando e omitia INSPETOR | Gestão = **ENCARREGADO/INSPETOR/ADMIN** (`EncarregadoInspetorOuAdmin`, já existe). MANTENEDOR só visualiza. |
| **Rotas** | `/api/pedidos/...` | `/pedidos/...` (padrão do projeto). Ações por verbo: `/atender`, `/cancelar`, `/restaurar`. |
| **Rota web** | `app/web/pages/pedidos.py` | Registrar em `app/web/pages/router.py`. |
| **Modelo p/ vencimento** | Só `slot_id` | + `origem`, `controle_vencimento_id`, `item_id`. |
| **Pedido genérico** | Sem identificação do PN | + `modelo_id`, `part_number_snapshot`, `nome_equipamento_snapshot`. |
| **Auditoria** | `solicitante_id` nullable; sem quem atendeu/cancelou | `solicitante_id` **NOT NULL**; + `atendido_por_id`, `cancelado_por_id`, `data_cancelamento`, `motivo_cancelamento`. |
| **Duplicidade** | Sem regra | RN-09: 1 pedido `PENDENTE` por pendência → 409 (+ índice parcial). |
| **Local do mockup** | Doc citava `docs/backlog/` | Corrigido p/ raiz `mockup_pedidos.html`. |

---

## 3. Vulnerabilidades técnicas incorporadas

| ID | Risco | Correção no feature v1.2 |
|---|---|---|
| V1 | RN-03/04 só no JS (burlável via API) | `@model_validator` server-side (§7.2). |
| V2 | Backdating de `data_pedido` | RN-15: data definida no servidor. |
| V3 | Máquina de estados não imposta | RN-11: transições só de `PENDENTE`, validadas no service → 409. |
| V4 | `<script>`/CSS inline violam CSP `script-src 'self'` | §8.2: externalizar JS/CSS. |
| V5 | `innerHTML` com dado dinâmico (XSS) | §8.2: `textContent`/`escapeHtml`, sem `innerHTML`. |
| V6 | Colisão de `numero_pedido` | RN-02: geração server-side + 409. |
| V7 | Sem soft delete (quebra convenção) | `ativo` + `/restaurar` (RN-16). |
| V8 | Tipagem ORM não-opcional vs FK nullable | `Mapped[... | None]` (§3.3). |
| V9 | `quantidade` sem limite | `ge=1, le=999`. |

---

## 4. Erro factual corrigido (v1)

- Auditoria v1 afirmava arquivo salvo como `feature_controle_pedidos.md.txt`. **Falso** — já era `.md`. Removido.

---

## 5. Já em conformidade (mantido)

PK `UUID`/`uuid4` · enums `str,Enum` como `String(20)` · `created_at`/`updated_at` tz-aware · enums em `app/shared/core/enums.py` · estrutura `app/modules/pedidos/` · exportação CSV/XLSX segue padrão `/inspecoes/export`.

---

## 6. Pendências fora do escopo (higiene de docs)

- **Doc drift do inventário (não bloqueia pedidos):** `RBAC.md:55` diz instalar = MAN/ENC/ADM, mas `referencia-api.md:598` diz ENC/ADM. Reconciliar na doc do módulo de equipamentos.
- **Drift de enums em docs:** `Database.md`/`referencia-api.md` listam papéis sem INSPETOR em alguns trechos; `TipoPapel` correto tem 4 papéis.

---

## 7. Verificação contra o código (v1.3 — 2026-08-03)

Spec v1.2 auditada arquivo a arquivo contra o codebase. Confirmados como corretos: enums padrão `str, enum.Enum`, `EncarregadoInspetorOuAdmin` (existe em `app/bootstrap/dependencies.py`), todos os nomes de tabelas/campos citados (`slots_inventario`, `instalacoes.data_remocao`, `controle_vencimentos`, `aeronaves.matricula`, `usuarios.trigrama`, etc.), rotas sem `/api`, padrão `ativo` + `/restaurar`, cookie `saa29_token`, CSP `script-src 'self'`.

Divergências corrigidas na v1.3:

| Tema | v1.2 dizia | Fato no código (v1.3) |
|---|---|---|
| **Local do mockup** | Raiz do repo (a "correção" do §2 estava errada) | `docs/backlog/modulo_pedidos/mockup_pedidos.html` — único no repo |
| **Registro do router** | "Registrar no bootstrap" (vago) | `include_router(prefix="/pedidos")` **+** lista `API_PREFIXES` em `app/bootstrap/main.py` (decide redirect vs JSON em 401/403) |
| **Export** | `?formato=csv\|xlsx` | Param real é `format` (`Query(alias="format")`, padrão `/inspecoes/export`) |
| **Ordenação de rotas** | Não mencionada | Literais antes de `/{id}`; `{id}` tipado `uuid.UUID` (precedente: `equipamentos/router.py:199`) |
| **Ícone na nav** | Emoji 📦 | Nav usa ícones SVG inline com `title` + highlight por `request.url.path` |
| **`solicitante_trigrama`** | `str` obrigatório | `Usuario.trigrama` é nullable → `str \| None` |
| **Docs centrais (Fase 4)** | Nomes soltos | Caminhos reais: `docs/core/{SRS,SPECS}.md`, `docs/architecture/{Database,referencia-api,overview,RBAC}.md` |
| **Async** | Não mencionado | Engine async (aiosqlite); services são `async def` com `AsyncSession` |
| **RBAC (uso)** | Só o nome da dependência | Usada como parâmetro anotado; papéis são constantes string de `app/modules/auth/roles.py`, não enum |
| **Índice parcial** | "Validar compatibilidade" | Sem precedente no projeto; service é a garantia primária, índice opcional |
| **CSRF no front** | "Enviar token CSRF" | Usar `apiFetch` global de `app.js` (injeta `X-CSRF-Token` da meta tag automaticamente); `escapeHtml` também é global de `app.js` |
