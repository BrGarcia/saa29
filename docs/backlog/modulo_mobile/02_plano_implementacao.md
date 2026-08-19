# 📋 Plano de Implementação — Versão Mobile do SAA29

Companion de `01_especificacao_mobile.md`. Segue o padrão de `docs/backlog/modulo_pedidos/plano_implementacao.md`: cada etapa é entregável e testável isoladamente, na ordem em que deve ser codificada.

## 0. Visão do que será construído

Não é um módulo novo — é conserto + extensão de `/m/`, consumindo APIs que já existem em `panes`, `inspecoes`, `vencimentos`, `equipamentos` e `publicacoes`. Só dois endpoints novos (`GET /dashboard/frota` e o filtro `?aeronave_id=` em `GET /vencimentos/matriz`); o resto é frontend (templates Jinja2 + JS vanilla) e correção de bugs já mapeados.

## 1. Mapa de arquivos

**Novos:**
```
app/web/templates/mobile/aeronave.html          (renomeia tarefas_aeronave.html)
app/web/templates/mobile/pane_nova.html
app/web/templates/mobile/pane_detalhe.html
app/web/templates/mobile/inspecao_checklist.html
app/web/static/js/mobile/aeronave_mobile.js      (renomeia tarefas_mobile.js)
app/web/static/js/mobile/panes_mobile.js
app/web/static/js/mobile/inspecoes_mobile.js
app/web/static/js/mobile/vencimentos_mobile.js
app/web/static/js/mobile/inventario_mobile.js
app/web/static/img/icon-192.png
app/web/static/img/icon-512.png
app/web/static/img/apple-touch-icon.png
```

**Alterados:**
```
app/web/templates/mobile/base_mobile.html        (meta CSRF, apple-touch-icon, drawer)
app/web/templates/mobile/frota.html               (sem mudança estrutural)
app/web/templates/mobile/publicacoes.html          (classes mobile.css)
app/web/static/js/mobile/frota_mobile.js           (1 fetch em vez de N+1)
app/web/static/js/mobile/app_mobile.js             (nenhuma mudança — o registro já aponta certo após a Etapa 1.2)
app/web/static/js/app.js                           (apiFetch: renovação silenciosa)
app/web/static/css/mobile.css                      (7 classes + tokens de status)
app/web/pages/mobile_router.py                     (3 rotas novas de página, +GET /sw.js)
app/web/pages/router.py                             (remove /m/ duplicado)
app/web/static/manifest.json                       (id, scope, description)
app/modules/dashboard/schemas.py                    (FrotaAgregadaItem)
app/modules/dashboard/service.py                    (get_frota_agregada)
app/modules/dashboard/router.py                      (GET /frota)
app/modules/vencimentos/service.py                   (montar_matriz_vencimentos: filtro opcional)
app/modules/vencimentos/router.py                     (query param aeronave_id)
tests/unit/test_mobile.py                             (novos casos)
tests/unit/test_dashboard.py                           (GET /dashboard/frota)
docs/ROADMAP.md, docs/methodology/NEXT.md               (fechamento)
```

---

## 2. Etapa 1 — Fundação (conserta o que está quebrado)

### 2.1 CSRF no shell mobile
`app/web/templates/mobile/base_mobile.html`, dentro de `<head>`, logo após a linha do `<meta name="theme-color">`:
```html
<meta name="csrf-token" content="{{ request.state.csrf_token }}">
```
Idêntico ao que `base.html:12` já faz. Sem isso `apiFetch` (`app.js:161-164`) não tem token para colocar em `X-CSRF-Token` e todo POST/PATCH mobile recebe 403 do `CSRFMiddleware`.

### 2.2 Service Worker no escopo certo
Hoje `app_mobile.js:7` registra `navigator.serviceWorker.register('/sw.js')`, mas o único arquivo existente é `app/web/static/sw.js`, servido só sob `/static/sw.js` pelo `StaticFiles` mount (`main.py:190`).

Adicionar em `app/web/pages/mobile_router.py`:
```python
from fastapi.responses import FileResponse

@router.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        "app/web/static/sw.js",
        media_type="text/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )
```
Sem `Depends(get_current_user)` — o SW precisa registrar mesmo antes do login. O header `Service-Worker-Allowed: /` é o que permite um SW registrado fora de `/static/` controlar `/m/`.

### 2.3 Ícones do PWA
Gerar `app/web/static/img/icon-192.png`, `icon-512.png` (fundo `#0F172A`, mesma identidade do favicon SVG existente) e `apple-touch-icon.png` (180×180, sem transparência — iOS não aceita alfa no touch icon). Adicionar em `base_mobile.html`:
```html
<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png">
```

### 2.4 Remover rotas duplicadas
Apagar de `app/web/pages/router.py` o bloco `# --- ROTAS MOBILE (/m/) ---` (linhas 219-235) — código morto, `mobile_router` já cobre as mesmas rotas e é incluído primeiro em `main.py:172`.

### 2.5 Renovação silenciosa de token
Em `app/web/static/js/app.js`, função `apiFetch` (linha 151): ao receber `401`, em vez de chamar `clearAuth()` direto, tentar `POST /auth/refresh` uma única vez (o endpoint já roda rotação de refresh token e regrava os cookies `saa29_token`/`saa29_refresh_token` via `Response.set_cookie`, `auth/router.py:83-105`) e repetir a requisição original. Só chama `clearAuth()` se o refresh também falhar.

```javascript
let refreshPromise = null;

async function tentarRefresh() {
    if (!refreshPromise) {
        refreshPromise = fetch("/auth/refresh", { method: "POST", credentials: "same-origin" })
            .then(res => res.ok)
            .finally(() => { refreshPromise = null; });
    }
    return refreshPromise;
}

// dentro de apiFetch, no bloco `if (response.status === 401)`:
if (response.status === 401 && !options._retried) {
    const renovou = await tentarRefresh();
    if (renovou) {
        return apiFetch(endpoint, { ...options, _retried: true });
    }
    clearAuth();
    throw new Error("Sessão expirada.");
}
```
O `refreshPromise` compartilhado evita disparar N chamadas de refresh em paralelo quando várias requisições recebem 401 ao mesmo tempo (ex.: as 4 abas do hub buscando dados juntas). `_retried` evita loop infinito se o refresh "funcionar" mas o novo token ainda for rejeitado.

Afeta desktop e mobile igualmente — validar manualmente 2-3 telas desktop (Panes, Dashboard) antes de fechar a etapa.

### 2.6 CSS mobile — classes faltantes
Adicionar a `app/web/static/css/mobile.css` (a partir da linha 339, fim do arquivo atual):
- `.mobile-tabs` (flex row, scroll horizontal se necessário), `.mobile-tab-btn` (+ `.active`)
- `.mobile-task-list`, `.mobile-task-card` (substituindo o `style.cssText` inline hoje em `tarefas_mobile.js:58`)
- `.mobile-aeronave-header`, `.mobile-nav-back`
- `.badge-status` + variantes por status (`--mobile-status-ok`, `--mobile-status-vencendo`, `--mobile-status-vencido`, `--mobile-status-prorrogado`, `--mobile-status-desinstalado` como novos tokens no `:root`)

Depois, remover os `style.cssText` inline de `tarefas_mobile.js` (que vira `aeronave_mobile.js` na Etapa 2) e do card de pane.

### 2.7 Corrigir campo de trigrama
`app/web/static/js/mobile/tarefas_mobile.js:66` lê `pane.aberto_por_trigrama`, que não existe em `PaneListItem` (`app/modules/panes/schemas.py:125-144` expõe `criador: UsuarioOut | None`). Trocar para `pane.criador?.trigrama || 'MANT'`. Remover a função morta `getCsrfTokenFromCookie` (linhas 115-118) — nunca é chamada, e com o item 2.1 o token já vem da meta tag.

### 2.8 Testes desta etapa (`tests/unit/test_mobile.py`)
- `test_mobile_base_template_contem_meta_csrf` — `'name="csrf-token"' in response.text`.
- `test_sw_js_servido_na_raiz_com_scope_correto` — `GET /sw.js` → 200, header `Service-Worker-Allowed: /`.
- `test_manifest_icones_existem_em_disco` — `Path("app/web/static/img/icon-192.png").exists()` etc.
- `test_rotas_m_nao_duplicadas` — inspeciona `app.routes` e garante um único handler para `/m/`.

---

## 3. Etapa 2 — Espinha: Frota + Hub da Aeronave

### 3.1 `GET /dashboard/frota`

`app/modules/dashboard/schemas.py`, acrescentar:
```python
class FrotaAgregadaItem(BaseModel):
    aeronave_id: str
    matricula: str
    status: str
    panes_abertas: int = 0
    inspecoes_ativas: int = 0
    tarefas_pendentes: int = 0
    vencimentos_vencidos: int = 0
    vencimentos_vencendo: int = 0
    slots_vazios: int = 0
```

`app/modules/dashboard/service.py`, nova função `get_frota_agregada(db) -> list[FrotaAgregadaItem]`, seguindo o padrão de `get_frota_summary` (linhas 232-296: 3 queries agregadas por `aeronave_id`, casadas em memória por `str(id)`, não N+1 por aeronave):

1. `SELECT aeronave_id, COUNT(*) FROM panes WHERE status='ABERTA' AND ativo=1 GROUP BY aeronave_id` — mapa `panes_abertas`.
2. `SELECT aeronave_id, COUNT(*) FROM inspecoes WHERE status IN ('ABERTA','EM_ANDAMENTO') GROUP BY aeronave_id` — mapa `inspecoes_ativas`; join com `InspecaoTarefa.status='PENDENTE'` (via `inspecao_id IN (...)`, mesma técnica de `contar_tarefas_por_inspecao`, `inspecoes/service.py:402`) para `tarefas_pendentes`.
3. Vencimentos vencidos/vencendo: reaproveitar a mesma lógica de status derivado (`calcular_status_vencimento`) já usada em `montar_matriz_vencimentos`, mas agregando só a contagem — **não** reimplementar a derivação de status; extrair um helper compartilhado se o corpo começar a divergir (avaliar em code review; não é obrigatório se a query aqui for suficientemente mais simples que a matriz completa).
4. `slots_vazios`: `COUNT(slots) - COUNT(instalacoes ativas)` por aeronave, mesma base de `listar_inventario_aeronave`.
5. `SELECT * FROM aeronaves WHERE status != 'INATIVA' ORDER BY matricula` como espinha da lista; casar os mapas acima por `str(aeronave.id)`.

`app/modules/dashboard/router.py`, novo endpoint:
```python
@router.get("/frota", response_model=list[FrotaAgregadaItem], summary="Frota agregada para o mobile")
async def get_frota_agregada_endpoint(db: DBSession, _: CurrentUser) -> list[FrotaAgregadaItem]:
    return await service.get_frota_agregada(db)
```
`/dashboard/` já está em `API_PREFIXES` (`main.py:61`) — nenhuma mudança de roteamento global necessária.

### 3.2 `frota_mobile.js` — 1 fetch
Trocar `apiFetch('/aeronaves/')` + N×`apiFetch('/panes/?aeronave_id=...')` por uma única chamada a `apiFetch('/dashboard/frota')`. Preservar `calcularPrioridadeOperacional`, adaptando a assinatura para receber os campos agregados (`panes_abertas`, `inspecoes_ativas`, `vencimentos_vencidos`) em vez de só `pendenciasCount`. Badges por tipo: vermelho para pendência de pane/vencimento vencido, âmbar para vencendo, azul para inspeção ativa.

### 3.3 Hub de 4 abas
Renomear `app/web/templates/mobile/tarefas_aeronave.html` → `aeronave.html` e `app/web/static/js/mobile/tarefas_mobile.js` → `aeronave_mobile.js`. Estrutura do template:
```html
<div class="mobile-tabs">
  <button class="mobile-tab-btn active" data-tab="panes">Panes</button>
  <button class="mobile-tab-btn" data-tab="inspecoes">Inspeções</button>
  <button class="mobile-tab-btn" data-tab="vencimentos">Vencimentos</button>
  <button class="mobile-tab-btn" data-tab="inventario">Inventário</button>
</div>
<div id="tab-panes" class="mobile-tab-panel"></div>
<div id="tab-inspecoes" class="mobile-tab-panel" hidden></div>
<div id="tab-vencimentos" class="mobile-tab-panel" hidden></div>
<div id="tab-inventario" class="mobile-tab-panel" hidden></div>
```
`aeronave_mobile.js` controla troca de aba (toggle `hidden` + `active`, sem framework) e delega a busca de cada aba para `panes_mobile.js`, `inspecoes_mobile.js`, `vencimentos_mobile.js`, `inventario_mobile.js` — cada um exporta uma função `carregarAba<X>(aeronaveId, container)` chamada só na primeira vez que a aba abre (flag `dataset.loaded`).

`app/web/pages/mobile_router.py`, atualizar a rota existente:
```python
@router.get("/aeronave/{aeronave_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_aeronave_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    return templates.TemplateResponse("mobile/aeronave.html", {
        "request": request, "aeronave_id": aeronave_id, "user": user
    })
```

### 3.4 Drawer sem placeholders
Em `base_mobile.html`, remover o bloco `<div class="mobile-drawer-placeholder">` (linhas 61-71: "Relato Rápido de Pane" e "Sincronização Offline" desabilitados) — o primeiro passa a existir de verdade (Etapa 3), o segundo está fora de escopo por decisão explícita (ver spec §1.2) e não deve continuar prometido na UI.

### 3.5 Testes
- `GET /dashboard/frota` sem auth → 401; autenticado → 200 e formato da lista.
- Contadores corretos com fixtures de pane aberta + inspeção ativa + vencimento vencido numa mesma aeronave.
- Estrutura das 4 abas presente em `/m/aeronave/{id}`.

---

## 4. Etapa 3 — PANES

### 4.1 Relato rápido — `/m/pane/nova`
`app/web/pages/mobile_router.py`:
```python
@router.get("/pane/nova", response_class=HTMLResponse, include_in_schema=False)
async def mobile_pane_nova_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    return templates.TemplateResponse("mobile/pane_nova.html", {
        "request": request, "aeronave_id": aeronave_id, "user": user
    })
```
`pane_nova.html`: aeronave fixa (vinda da query string, exibida como texto — não editável, evita seleção errada em campo), `<select>` de sistema ATA carregado de `GET /panes/sistemas`, `<textarea>` de descrição, `<input type="file" capture="environment">` para foto opcional. Submit dispara, em sequência: `POST /panes/` (`schemas.PaneCreate`: `aeronave_id`, `sistema_ata_id?`, `descricao?`) e, se houver foto, `POST /panes/{id}/anexos` (multipart). Sucesso redireciona para `/m/pane/{id}`.

### 4.2 Detalhe — `/m/pane/{pane_id}`
```python
@router.get("/pane/{pane_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_pane_detalhe_page(request: Request, pane_id: str, user=Depends(get_current_user)):
    return templates.TemplateResponse("mobile/pane_detalhe.html", {
        "request": request, "pane_id": pane_id, "user": user
    })
```
`pane_detalhe.html` + `panes_mobile.js`, buscando `GET /panes/{id}` (schema `PaneOut`, já traz `anexos` e `responsaveis`):
- Cabeçalho: aeronave, código (`codigo`), status.
- Card de descrição + sistema ATA.
- Galeria de anexos (`<img>` para `TipoAnexo.IMAGEM`, link para `TipoAnexo.DOCUMENTO`), cada um resolvido via `GET /panes/{id}/anexos/{anexo_id}/download`.
- Botão "Tirar Foto" → `<input type="file" accept="image/*" capture="environment">` oculto (reaproveita o padrão já presente em `tarefas_aeronave.html:28`) → `POST /panes/{id}/anexos`.
- Botão "Assumir" → `POST /panes/{id}/responsaveis` com `{ usuario_id: <próprio usuário, do contexto oculto>, papel: "MANTENEDOR" }` — o router já restringe MANTENEDOR a só poder indicar a si mesmo (`app/modules/panes/router.py:428-433`), então não precisa de validação extra no cliente além de preencher com o próprio id.
- Campo de observação + botão "Concluir e Assinar" → `POST /panes/{id}/concluir` (`PaneConcluir.observacao_conclusao`).
- Card de comentários (editável mesmo com pane já concluída, igual ao desktop) → `PUT /panes/{id}` só com `{ comentarios }`.

### 4.3 Aba Panes do hub
`panes_mobile.js` também expõe `carregarAbaPanes(aeronaveId, container)`: `GET /panes/?aeronave_id=&status=ABERTA`, cards com link para `/m/pane/{id}` e botão flutuante "+ Relatar Pane" → `/m/pane/nova?aeronave_id=`.

### 4.4 Testes
- Criar pane com foto → 2 chamadas encadeadas, anexo aparece em `GET /panes/{id}/anexos`.
- Assumir responsabilidade grava o próprio usuário.
- Concluir muda status e a aeronave sincroniza (reaproveita a asserção já existente em `test_fluxo_concluir_pane_mobile_1_toque`, hoje quebrada pelo bug de CSRF — deve voltar a passar de ponta a ponta via HTTP, não só via override de dependency).

---

## 5. Etapa 4 — INSPEÇÕES

### 5.1 Aba Inspeções do hub
`inspecoes_mobile.js`, `carregarAbaInspecoes(aeronaveId, container)`: `GET /inspecoes/?aeronave_id=&status=ABERTA` e outra chamada com `status=EM_ANDAMENTO` (ou, mais simples, sem filtro de status e descartando no cliente os `STATUS_FINAIS` — decidir pelo menor número de requisições; o endpoint aceita um único `status` por vez, então **duas chamadas em paralelo com `Promise.all`** é preferível a filtrar client-side uma listagem sem filtro). Cada card mostra `progresso_percentual`, tipos aplicados, e DPE com cor (vermelho se `data_fim_prevista < hoje`, âmbar se `<= hoje + 7 dias`).

### 5.2 Checklist — `/m/inspecao/{id}`
```python
@router.get("/inspecao/{inspecao_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_inspecao_checklist_page(request: Request, inspecao_id: str, user=Depends(get_current_user)):
    return templates.TemplateResponse("mobile/inspecao_checklist.html", {
        "request": request, "inspecao_id": inspecao_id, "user": user
    })
```
`inspecao_checklist.html` + `inspecoes_mobile.js`: `GET /inspecoes/{id}` (cabeçalho) + `GET /inspecoes/{id}/tarefas` (lista). Toggle "Pendentes / Todas" filtra client-side (lista já é pequena — dezenas, não milhares). Toque na tarefa abre uma folha de ação (bottom sheet, `<dialog>` ou div fixa) com 3 botões grandes (`PENDENTE`/`CONCLUIDA`/`N/A`) + campo de observação → `PUT /inspecoes/tarefas/{id}` (`schemas.InspecaoTarefaUpdate` — conferir campos exatos no schema ao implementar; a essência é `status` + `observacao_execucao?`). Botão fixo "Adicionar tarefa extra" abre formulário (título, manual, código da tarefa, descrição, checkbox obrigatória) → `POST /inspecoes/{id}/tarefas`.

### 5.3 Testes
- Marcar 1ª tarefa como `CONCLUIDA` move a inspeção de `ABERTA` para `EM_ANDAMENTO` (mesma asserção do desktop, via rota mobile).
- Tarefa avulsa aparece na listagem com `ordem` = max+1.

---

## 6. Etapa 5 — VENCIMENTOS

### 6.1 Filtro no backend
`app/modules/vencimentos/service.py`, função `montar_matriz_vencimentos` (linha 366), acrescentar parâmetro opcional:
```python
async def montar_matriz_vencimentos(db: AsyncSession, aeronave_id: uuid.UUID | None = None) -> dict:
    ...
    q_acft = select(Aeronave).where(Aeronave.status != StatusAeronave.INATIVA)
    if aeronave_id is not None:
        q_acft = q_acft.where(Aeronave.id == aeronave_id)
    q_acft = q_acft.order_by(Aeronave.matricula)
    res_acft = await db.execute(q_acft)
    ...
```
(ajuste equivalente na query de slots, se ela também partir do `modelo_map` — conferir se algum filtro por aeronave precisa refletir nos slots antes; na versão atual os slots vêm de `modelo_map.keys()`, independente de aeronave, então só a query de `aeronaves` muda).

`app/modules/vencimentos/router.py`, endpoint `/matriz` (linha 179):
```python
@router.get("/matriz", summary="Visão matricial de vencimentos (Frota x Slot x Controle)")
async def matriz_vencimentos(
    db: DBSession,
    _: CurrentUser,
    aeronave_id: uuid.UUID | None = Query(default=None),
):
    return await service.montar_matriz_vencimentos(db, aeronave_id=aeronave_id)
```
Sem quebra: `vencimentos.js` do desktop continua chamando sem o parâmetro.

### 6.2 Aba Vencimentos
`vencimentos_mobile.js`, `carregarAbaVencimentos(aeronaveId, container)`: `GET /vencimentos/matriz?aeronave_id=` devolve `{ cabecalho, aeronaves: [{ slots: [{ controles: [...] }] }] }` — como é 1 aeronave só, renderizar direto `aeronaves[0].slots`. Cada controle vira uma linha com badge de status (usando os tokens de cor da Etapa 1.6) e botão "Registrar Execução".

Modal de execução → `PATCH /vencimentos/{vencimento_id}/executar` (`{ data_ultima_exec, observacao? }`). Tratar 409 (data anterior à última execução) e 422 (data futura, validado no schema) com mensagem legível, não o JSON cru.

Link "Ver histórico" → `GET /vencimentos/{vencimento_id}/historico`, lista simples em modal.

### 6.3 Testes
- `GET /vencimentos/matriz?aeronave_id=` devolve só a aeronave pedida.
- Execução via mobile grava e desativa prorrogação ativa (mesma regra do desktop).

---

## 7. Etapa 6 — INVENTÁRIO

### 7.1 Aba Inventário
`inventario_mobile.js`, `carregarAbaInventario(aeronaveId, container)`: `GET /equipamentos/inventario/{aeronaveId}` → `schemas.InventarioItemOut[]` (já traz `nome_posicao`, `part_number`, `nome_generico`, `numero_serie`, `status_item`, `usuario_trigrama`). Uma linha por slot; slots vazios (`item_id is None`) em destaque visual distinto.

### 7.2 Remover
Botão "Remover" (só quando `item_id` presente) → confirmação nativa (`confirm()` é aceitável aqui — ação destrutiva pontual, mesmo padrão já usado em `configuracoes_publicacoes.js:excluirEdicao()`) → `PATCH /equipamentos/instalacoes/{instalacao_id}/remover` com `{ data_remocao: hoje }`.

### 7.3 Instalar
Botão "Instalar" (só quando slot vazio) → `GET /equipamentos/itens/?equipamento_id={modelo_id}` (o `modelo_id` do slot precisa vir do `InventarioItemOut`; conferir se `equipamento_id`/`modelo_id` está no schema — se não estiver, é o único ajuste de schema desta etapa: adicionar `modelo_id: uuid.UUID` a `InventarioItemOut` para o mobile poder buscar os itens daquele PN). Filtrar no cliente os itens com `status == "ESTOQUE"` (não instalados). Se a lista vier vazia, exibir: *"Nenhum item de estoque cadastrado para este PN. Solicite ao Administrador o cadastro do número de série antes de instalar."* — não um erro genérico. Seleção → `POST /equipamentos/itens/{item_id}/instalar` (`{ aeronave_id, slot_id, data_instalacao: hoje }`).

### 7.4 Testes
- Remover→instalar no mesmo slot reflete em `GET /equipamentos/inventario/{id}` (troca completa).
- Lista de itens de estoque vazia → mensagem específica, não erro 500/genérico.

> Nota de performance: `listar_inventario_aeronave` tem N+1 conhecido (item 2 da "Refatoração FABLE 5" em `docs/ROADMAP.md`). Esta etapa **consome** o endpoint como está; só otimizar aqui se a resposta em rede móvel real (Etapa de verificação) ficar perceptivelmente lenta — senão deixar para o item já planejado no roadmap, para não misturar refactor de performance com feature.

---

## 8. Etapa 7 — PUBLICAÇÕES + acabamento PWA

### 8.1 Normalizar `mobile/publicacoes.html`
Trocar `.card`, `.form-input`, `.btn` (classes do desktop, hoje com `style="color: var(--text-primary)"` inline para compensar contraste — comentário explicativo já no próprio arquivo, linhas 15-19) pelas classes de `mobile.css`. Criar `.mobile-card`, `.mobile-input`, `.mobile-btn` se ainda não existirem com o contraste certo sobre fundo escuro, evitando o CSS inline atual.

### 8.2 Viewer de PDF em tela pequena
Testar `/publicacoes/viewer/{doc_id}` em 393×852: gestos de pinça/zoom do PDF.js em canvas, barra de ferramentas não deve cobrir mais que ~15% da altura útil. Ajustar CSS pontual em `publicacoes.css` se necessário (sem tocar na lógica do `publicacoes_viewer.js`).

### 8.3 `manifest.json`
```json
{
  "id": "/m/",
  "scope": "/m/",
  "description": "SAA29 — Linha de Voo: panes, inspeções, vencimentos e inventário no pátio.",
  ...
}
```
(mantendo `start_url`, `theme_color`, `icons` já corretos após a Etapa 1).

### 8.4 Fechamento
- `ruff check .`
- `pytest tests -q`
- Atualizar `docs/ROADMAP.md` (mover os itens de v2.0 "PWA" para concluído, com nota do que ficou fora — offline de gravação) e `docs/methodology/NEXT.md`.

---

## 9. Verificação end-to-end

```bash
ruff check .
pytest tests -q
pytest tests/unit/test_mobile.py tests/integration/test_mobile_integration.py tests/unit/test_dashboard.py -v
python scripts/run_app.py     # http://127.0.0.1:8000
```

Manual, DevTools emulando iPhone 14 Pro (393×852), throttling "Fast 4G":

1. Login `mantenedor` / `123456` (semeado com `APP_ENV=development` + `ENABLE_TEST_USERS=True`, `auth/service.py:320-421`).
2. `/m/` — conferir na aba Network: **uma** requisição a `/dashboard/frota`.
3. Abrir uma aeronave → percorrer as 4 abas; cada aba deve disparar sua busca só na primeira abertura (Network mostra a chamada só uma vez ao trocar de aba e voltar).
4. **Regressão-alvo:** concluir uma pane pelo mobile deve retornar 200, não 403.
5. Relato rápido com foto da câmera do aparelho; anexo sai de `"processando"` e aparece na galeria.
6. Marcar tarefa de inspeção como `CONCLUIDA`; inspeção muda para `EM_ANDAMENTO`, progresso sobe.
7. Registrar execução de vencimento; status muda e aparece no histórico.
8. Remover e depois instalar um item no mesmo slot; conferir reflexo em `/inventario` no desktop.
9. Deixar sessão parada > 15 min e agir — não pode cair para `/login`.
10. "Adicionar à Tela de Início" no Android e no iOS: ícone correto, abre em `standalone`.

---

## 10. Riscos e armadilhas conhecidas

| Risco | Mitigação |
|---|---|
| `Permissions-Policy: camera=()` em `shared/middleware/security.py:55` pode bloquear `<input capture>` em algum navegador | Testar em aparelho real na Etapa 3; se bloquear, relaxar para `camera=(self)` — mudança mínima e isolada, justificar no commit |
| Renovação silenciosa em `app.js` é compartilhada com **todo** o desktop | Cobrir com teste dedicado; validar manualmente 2-3 telas desktop antes de fechar a Etapa 1; usar a promise única para não multiplicar chamadas de refresh |
| `ControleVencimento.status` persistido diverge do derivado por data (dashboard usa um, matriz usa outro — achado já documentado em `docs/backlog/00_mapa_arquitetural.md`) | O mobile usa **sempre** o derivado, como a matriz. Não tentar unificar essa divergência aqui — fora de escopo |
| `InventarioItemOut` pode não expor `modelo_id` hoje | Conferir no início da Etapa 6; se faltar, é um campo a mais no schema, sem migração (não é coluna nova, é dado já carregado pela query) |
| Rate limit de `/auth/refresh` é 20/min (`@limiter.limit`) | Suficiente para 1 refresh por token expirado; não chamar em loop (o `_retried` do item 2.5 garante isso) |
| Excesso de telas novas inflando a manutenção futura | Só 3 rotas de página novas; Vencimentos e Inventário ficam como abas in-place, sem rota própria |

---

## 11. Checklist de aceite (espelha `01_especificacao_mobile.md` §9)

- [ ] Etapa 1 — CSRF, SW, ícones, rota duplicada removida, refresh silencioso, CSS completo, trigrama corrigido.
- [ ] Etapa 2 — `/dashboard/frota` em produção, hub com 4 abas, drawer sem placeholder.
- [ ] Etapa 3 — Relato rápido + detalhe de pane com foto, assumir, concluir.
- [ ] Etapa 4 — Checklist de inspeção com execução de tarefa e tarefa avulsa.
- [ ] Etapa 5 — Vencimentos por aeronave com execução e histórico.
- [ ] Etapa 6 — Inventário com remover/instalar e mensagem clara de limitação de RBAC.
- [ ] Etapa 7 — Publicações normalizada, PWA instalável de fato, docs atualizados.
- [ ] `pytest tests -q` e `ruff check .` limpos em cada etapa.
