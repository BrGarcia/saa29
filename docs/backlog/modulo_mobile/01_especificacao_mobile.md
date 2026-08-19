# 📱 Feature: Versão Mobile do SAA29 — Linha de Voo

## 1. Visão Geral

### 1.1 Problema

O SAA29 hoje é operado majoritariamente em desktop, dentro do esquadrão. Mas boa parte do trabalho de manutenção acontece **debaixo da asa**, no pátio, onde não há estação de trabalho: registrar uma pane, marcar um item de checklist, dar baixa num vencimento, trocar uma caixa-preta. Essas ações continuam sendo feitas no papel e depois transcritas, ou o militar precisa voltar ao esquadrão para digitar — perdendo tempo e introduzindo erro de transcrição.

O sistema já tem uma tentativa de resposta a isso: a interface `/m/` ("Módulo Mobile da Linha de Voo", entregue na v1.4.0), com três telas (Frota, Tarefas da Aeronave, Publicações), PWA declarado e um fluxo de "concluir pane em 1 toque". Um levantamento do estado atual, porém, encontrou que **essa interface não funciona de fato**:

| # | Achado | Evidência | Consequência |
|---|---|---|---|
| 1 | `mobile/base_mobile.html` não renderiza `<meta name="csrf-token">` (o `base.html` desktop renderiza, linha 12) | `app/web/templates/mobile/base_mobile.html` | `apiFetch` não envia `X-CSRF-Token` → **todo POST/PATCH do mobile responde 403**. O botão "CONCLUIR PANE (1 TOQUE)" nunca funcionou de fato |
| 2 | Service Worker registrado em `/sw.js`, mas o arquivo só é servido em `/static/sw.js` | `app/web/static/js/mobile/app_mobile.js:7` | O SW nunca instala (404 no registro). Mesmo se corrigido, o escopo padrão de um SW em `/static/` não cobriria `/m/` |
| 3 | `manifest.json` aponta para `/static/img/icon-192.png` e `icon-512.png`; o diretório `app/web/static/img/` não existe | `app/web/static/manifest.json` | A instalação do PWA na tela inicial falha por falta de ícone — **o PWA nunca foi instalável** |
| 4 | `/m/` e `/m/aeronave/{id}` estão definidos duas vezes, em `mobile_router.py` e em `pages/router.py:219-235` | ambos os arquivos | Código morto: como `mobile_router` é incluído primeiro (`main.py:172`), as rotas de `pages/router.py` nunca executam |
| 5 | `tarefas_aeronave.html` referencia 7 classes CSS que não existem em `mobile.css` | `.mobile-tabs`, `.mobile-tab-btn`, `.mobile-task-card`, `.mobile-task-list`, `.mobile-aeronave-header`, `.mobile-nav-back`, `.badge-status` | As abas "Todas/Panes/Checklists" renderizam sem estilo e sem handler de clique; o JS compensa parcialmente com `style.cssText` inline nos cards |
| 6 | `frota_mobile.js` faz 1 requisição de panes **por aeronave** exibida | `app/web/static/js/mobile/frota_mobile.js:22-37` | N+1 de rede logo na tela de abertura, justo no cenário de 4G do pátio que a interface deveria proteger |
| 7 | `tarefas_mobile.js` lê `pane.aberto_por_trigrama` | `app/web/static/js/mobile/tarefas_mobile.js:66` | Esse campo não existe em `PaneListItem` (o schema expõe `criador`) — sempre cai no fallback `"MANT"` |
| 8 | O access token expira em 15 min e nenhum JS do sistema chama `POST /auth/refresh` | `app/web/static/js/app.js:151` (`apiFetch`) vs. `auth/router.py:119` (`/auth/refresh` existe e nunca é chamado) | O militar é expulso para `/login` no meio de uma manutenção, no desktop e no mobile igualmente |

O objetivo desta feature não é reescrever o mobile do zero, mas **consertar essa base e estendê-la** para cobrir o ciclo real de trabalho do mantenedor em campo — sem tentar replicar o desktop inteiro no celular.

### 1.2 Solução Proposta

Evoluir `/m/` como uma segunda superfície do mesmo backend — mesmas APIs REST, mesmo RBAC no servidor, mesma CSP estrita — cobrindo cinco áreas de negócio recortadas apenas às ações de **execução** de campo:

- **PANES** — relatar, anexar foto, assumir, concluir.
- **INSPEÇÕES** — executar checklist, adicionar tarefa avulsa.
- **VENCIMENTOS** — registrar execução, ver histórico.
- **INVENTÁRIO** — instalar/remover item já cadastrado (troca de componente).
- **PUBLICAÇÕES** — já existe; só normalização visual e de contraste.

Tudo ancorado numa aeronave por vez (a Frota como tela inicial), sem duplicar telas de gestão, catálogo ou configuração — essas continuam exclusivas do desktop.

**Fora de escopo desta entrega**, por decisão explícita:
- **Modo offline / fila de gravação.** O roadmap (`docs/ROADMAP.md`, v2.0) menciona "Modo Offline", mas decidiu-se entregar primeiro uma versão **somente online**, com PWA instalável e shell (HTML/CSS/JS) cacheado para abertura rápida — sem cache de dados de negócio e sem fila de ações pendentes. Fila offline exige idempotência nos endpoints, resolução de conflito e auditoria de quem/quando fez o quê num sistema com rastreabilidade obrigatória por trigrama; é trabalho de uma entrega futura, não deste recorte.
- **Scanner de QR Code**, **anotação sobre foto**, **paridade total com o desktop** — mantidos no roadmap, fora deste recorte.

---

## 2. Persona e Recorte de Ações

**Persona principal: MANTENEDOR** (`TipoPapel.MANTENEDOR`, `app/shared/core/enums.py:52`) — "EXECUTA" na taxonomia de `docs/architecture/RBAC.md` §5. É o alvo direto da dependência `ExecucaoPermitida` (`app/bootstrap/dependencies.py:163-165`, que reúne MANTENEDOR + ENCARREGADO + ADMINISTRADOR) e do próprio docstring de `mobile_router.py:27` ("Lista de Tarefas e Panes da Aeronave para Mantenedor em 1 Toque"). ENCARREGADO e ADMINISTRADOR também usam o mobile — herdam as mesmas ações de execução — mas nenhuma ação de gestão exclusiva deles é exposta aqui.

**Regra de recorte:** o mobile v1 expõe **apenas ações que já são permitidas ao MANTENEDOR no backend**. Nenhuma tela mobile introduz um caminho de escrita que hoje não exista na API desktop, e nenhuma tela mobile faz checagem de papel no cliente — a página é servida a qualquer autenticado e o backend decide o que aceitar, exatamente como o resto do sistema já opera (ver `docs/architecture/RBAC.md` §3.2: "Backend é a fonte de verdade para autorização").

### 2.1 Escopo por módulo

| Módulo | Dentro do mobile (RF) | Fora — permanece exclusivo do desktop |
|---|---|---|
| **FROTA** (espinha de navegação) | Lista de aeronaves ordenada por criticidade, com contadores agregados de pendência | Cadastro de aeronave, alternar status manualmente |
| **PANES** | Ver panes abertas da aeronave · Relato rápido (nova pane) · Anexar foto pela câmera · Assumir responsabilidade (a si mesmo) · Concluir com observação | Editar descrição/sistema ATA · Delegar a terceiros · Excluir/restaurar (lixeira) · Exportar relatório |
| **INSPEÇÕES** | Ver inspeções ativas da aeronave com progresso e DPE · Executar item de checklist (`PENDENTE`↔`CONCLUIDA`↔`N/A` + observação) · Adicionar tarefa avulsa | Abrir inspeção · Concluir inspeção · Cancelar inspeção · Catálogo de tipos/tarefas · Emitir PDF/OS |
| **VENCIMENTOS** | Ver controles da aeronave por slot, com status derivado por data · Registrar execução · Ver histórico de execuções | Prorrogar vencimento · Cancelar prorrogação · Regras de periodicidade · Tipos de controle |
| **INVENTÁRIO** | Ver inventário por slot (PN / nome / S/N / status) · Remover item de um slot · Instalar item **já cadastrado** em um slot | Ajuste/sincronismo de S/N em conflito · Cadastro de novo PN/slot/item físico · Import XLSX em massa |
| **PUBLICAÇÕES** | Navegar acervo por categoria/manual/capítulo · Busca full-text · Resolver mensagem CAS/EICAS (FIM) · Viewer de PDF | Cadastro/edição de publicações avulsas · Gestão de edições do acervo · Upload de acervo |

**Limitação conhecida a documentar na UI, não a contornar:** `POST /equipamentos/itens/` (cadastrar novo S/N) é `AdminRequired`, e `POST /equipamentos/inventario/ajuste` (sincronismo/conflito) é `EncarregadoOuAdmin`. Isso significa que **o mantenedor não pode, pelo celular, dar entrada em um componente cujo número de série nunca foi cadastrado no sistema** — só instalar um item que já exista no catálogo de itens físicos. Se a caixa-preta que chegou é nova, ele depende de um Administrador lançar o S/N primeiro. Esta feature **não relaxa** esse RBAC; a tela mobile deve informar isso claramente quando a lista de S/N disponíveis vier vazia, em vez de travar sem explicação.

---

## 3. Arquitetura de Navegação

O mantenedor está sempre **em uma aeronave**. Toda a informação de execução se ancora na matrícula, exceto Publicações (consulta global, sem contexto de ANV):

```
/m/                          Frota (home) — cards por ANV com contadores
 └─ /m/aeronave/{id}         Hub da aeronave — 4 abas
      ├─ Panes         → /m/pane/nova?aeronave_id=…   (relato rápido)
      │                → /m/pane/{pane_id}            (detalhe: foto, assumir, concluir)
      ├─ Inspeções     → /m/inspecao/{inspecao_id}    (checklist)
      ├─ Vencimentos     (in-place na aba, modal de execução)
      └─ Inventário      (in-place na aba, modais remover/instalar)
/m/publicacoes                Global (única tela fora do contexto de ANV) — já existe
```

3 rotas de página novas (`/m/pane/nova`, `/m/pane/{id}`, `/m/inspecao/{id}`); Vencimentos e Inventário vivem como abas in-place no hub, sem rota própria — menos navegação, menos peso.

---

## 4. Requisitos Funcionais

### Frota (RF-M0x)
- **RF-M01**: A tela inicial (`/m/`) deve listar todas as aeronaves ativas, ordenadas por criticidade operacional: INDISPONÍVEL/com pendência primeiro, depois INSPEÇÃO, depois DISPONÍVEL — regra já implementada em `calcularPrioridadeOperacional` (`frota_mobile.js`), a preservar.
- **RF-M02**: Cada card de aeronave deve exibir contadores agregados: panes abertas, tarefas de inspeção pendentes, vencimentos vencidos/vencendo — obtidos em **uma única requisição** (não uma por aeronave).
- **RF-M03**: Tocar no card leva ao Hub da Aeronave (`/m/aeronave/{id}`).

### Hub da Aeronave (RF-M1x)
- **RF-M10**: O hub exibe 4 abas — Panes, Inspeções, Vencimentos, Inventário — com carregamento sob demanda (a aba só busca dados quando é aberta pela primeira vez).
- **RF-M11**: O cabeçalho do hub mostra matrícula e status atual da aeronave.

### Panes (RF-M2x)
- **RF-M20**: A aba Panes lista as panes `ABERTA` da aeronave.
- **RF-M21**: "Relato Rápido" cria uma pane (`POST /panes/`) com aeronave pré-preenchida, sistema ATA opcional (`GET /panes/sistemas`) e descrição; permite anexar uma foto no mesmo fluxo.
- **RF-M22**: O detalhe da pane permite: anexar foto adicional pela câmera do aparelho (`POST /panes/{id}/anexos`, campo já suporta `capture="environment"`), assumir responsabilidade sobre si mesmo (`POST /panes/{id}/responsaveis`, MANTENEDOR só pode indicar a si mesmo — regra já aplicada no router), registrar comentário, e concluir com observação (`POST /panes/{id}/concluir`).
- **RF-M23**: Galeria de anexos já enviados, com abertura em tela cheia.

### Inspeções (RF-M3x)
- **RF-M30**: A aba Inspeções lista inspeções `ABERTA`/`EM_ANDAMENTO` da aeronave, com barra de progresso (`progresso_percentual`, já calculado por `InspecaoListItem`) e DPE destacada (vermelho se vencida, âmbar se ≤ 7 dias — mesma regra visual do desktop).
- **RF-M31**: Tocar numa inspeção abre o checklist (`/m/inspecao/{id}`): lista de tarefas, filtro Pendentes/Todas.
- **RF-M32**: Tocar numa tarefa abre uma folha de ação para marcar `PENDENTE` / `CONCLUIDA` / `N/A`, com observação opcional (`PUT /inspecoes/tarefas/{id}`).
- **RF-M33**: Botão "Adicionar tarefa extra" para tarefa avulsa fora do template (`POST /inspecoes/{id}/tarefas`) — liberado a qualquer autenticado por ser requisito de Segurança de Voo (já é assim no desktop).

### Vencimentos (RF-M4x)
- **RF-M40**: A aba Vencimentos lista os controles da aeronave agrupados por slot, com status derivado por data (`OK`/`VENCENDO`/`VENCIDO`/`PRORROGADO`/`DESINSTALADO`), ordenados por urgência.
- **RF-M41**: Modal de execução registra `data_ultima_exec` e observação (`PATCH /vencimentos/{id}/executar`); erros de validação (data futura, data anterior à última execução) devem aparecer como mensagem clara, não como erro genérico.
- **RF-M42**: Acesso ao histórico de execuções de um controle (`GET /vencimentos/{id}/historico`).

### Inventário (RF-M5x)
- **RF-M50**: A aba Inventário lista os slots da aeronave com PN, nome, S/N instalado (se houver) e status (`GET /equipamentos/inventario/{aeronave_id}`).
- **RF-M51**: Remover o item de um slot, com confirmação e data (`PATCH /equipamentos/instalacoes/{id}/remover`).
- **RF-M52**: Instalar um item já cadastrado naquele PN num slot vazio (`GET /equipamentos/itens/?equipamento_id=` para listar S/N disponíveis, depois `POST /equipamentos/itens/{id}/instalar`); se a lista vier vazia, exibir mensagem explicando a limitação de RBAC (item 2.1 acima), não um erro.

### Publicações (RF-M6x)
- **RF-M60**: Manter a navegação/busca/FIM/viewer já existentes em `/m/publicacoes`, normalizando o visual para os componentes de `mobile.css` (hoje usa `.card`/`.form-input`/`.btn` do desktop com estilo inline compensando contraste).

### Transversal (RF-M9x)
- **RF-M90**: PWA instalável (ícones presentes, manifest correto, Service Worker registrado e servido no escopo certo).
- **RF-M91**: Sessão não deve expirar durante o uso — renovação silenciosa via `POST /auth/refresh` antes de forçar logout.
- **RF-M92**: Drawer de navegação sem itens "placeholder/desabilitado" — cada item existe de fato.

---

## 5. Requisitos Não-Funcionais

- **RNF-01 — Alvo de toque.** Todo elemento interativo ≥ `56px` (token `--mobile-touch-target` já definido em `mobile.css:17`), para uso com luva/mão suada no pátio.
- **RNF-02 — Contraste sob sol.** Dark-only por design (o mobile não segue o toggle de tema do desktop); manter os tokens de alto contraste já validados em `mobile.css:5-18`.
- **RNF-03 — Custo de rede.** Nenhuma tela de abertura deve gerar requisições N+1; ver RF-M02.
- **RNF-04 — CSP estrita (RN-16).** Zero scripts inline, zero atributos `on*=`. Passagem de dado Jinja→JS exclusivamente via `data-*` em elemento oculto, como já é o padrão em `#mobile-global-context` (`base_mobile.html:81-84`).
- **RNF-05 — Sem regressão de CSRF.** Toda mutação (`POST`/`PUT`/`PATCH`/`DELETE`) feita a partir do mobile deve ter o header `X-CSRF-Token` sincronizado (achado #1 corrigido na Etapa 1).
- **RNF-06 — Sem novas dependências de front-end.** Continua Jinja2 + JavaScript vanilla; nenhum bundler, framework ou pacote npm é introduzido.
- **RNF-07 — Compatibilidade de viewport.** Testado em 393×852 (iPhone 14/15/16 Pro) e 375×667 (iPhone SE), como referência de menor tela suportada.

---

## 6. RBAC do Escopo Mobile

Nenhuma regra nova — o mobile herda exatamente as dependências já usadas pelos mesmos endpoints no desktop (`app/bootstrap/dependencies.py`):

| Ação mobile | Dependency no endpoint consumido |
|---|---|
| Ver frota, aeronave, panes, inspeções, vencimentos, inventário, publicações | `CurrentUser` |
| Criar pane, comentar, anexar foto | `CurrentUser` / `ExecucaoPermitida` conforme endpoint |
| Concluir pane | `ExecucaoPermitida` (MANTENEDOR, ENCARREGADO, ADMINISTRADOR) |
| Assumir responsabilidade em pane | `ExecucaoPermitida`, e MANTENEDOR só a si mesmo (regra já no router) |
| Executar tarefa de inspeção / adicionar tarefa avulsa | `CurrentUser` (qualquer autenticado — decisão de Segurança de Voo já vigente) |
| Registrar execução de vencimento | `ExecucaoPermitida` (**INSPETOR não executa**, por design) |
| Instalar/remover item de inventário | `ExecucaoPermitida` |
| Cadastrar novo S/N / ajuste de sincronismo | **Não exposto no mobile** (`AdminRequired` / `EncarregadoOuAdmin`) |

---

## 7. Contratos dos Endpoints Novos

### `GET /dashboard/frota`
Agregação por aeronave para a tela inicial, eliminando o N+1 atual. Vive em `app/modules/dashboard/` — módulo já dedicado a agregação read-only cross-módulo, sem tabela própria.

```jsonc
// Response 200
[
  {
    "aeronave_id": "uuid",
    "matricula": "FAB-2854",
    "status": "INDISPONIVEL",
    "panes_abertas": 2,
    "inspecoes_ativas": 1,
    "tarefas_pendentes": 5,
    "vencimentos_vencidos": 1,
    "vencimentos_vencendo": 3,
    "slots_vazios": 0
  }
]
```
Autorização: `CurrentUser`. Sem paginação (frota é pequena — um esquadrão local, RN-14).

### `GET /vencimentos/matriz?aeronave_id=<uuid>`
Filtro opcional acrescentado ao endpoint existente (`app/modules/vencimentos/router.py:179-183`). Sem o parâmetro, comportamento idêntico ao atual (frota inteira, consumido por `vencimentos.js` no desktop). Com o parâmetro, a query em `montar_matriz_vencimentos` (`vencimentos/service.py:408-413`) ganha um `.where(Aeronave.id == aeronave_id)` a mais.

---

## 8. Fluxo de Uso Principal (exemplo)

1. Mantenedor abre o app (ícone na tela inicial, instalado como PWA) → `/m/` carrega a Frota em uma requisição.
2. Aeronave FAB-2854 está com badge "INDISPONÍVEL — 2 pendências" no topo da lista (ordenação por criticidade). Toca no card.
3. Hub da aeronave abre na aba Panes por padrão (o que motivou a indisponibilidade). Vê 2 panes abertas.
4. Toca em uma pane → tela de detalhe → tira foto do componente com defeito pela câmera → anexo sobe e aparece na galeria.
5. Registra a solução no campo de observação → "Concluir e Assinar".
6. Volta ao hub, abre a aba Inspeções → vê o checklist da IF-50H em andamento → marca 3 itens como concluídos.
7. Abre a aba Vencimentos → um controle está VENCENDO → registra a execução feita naquele item.
8. Sessão passa dos 15 minutos durante o trabalho → renovação silenciosa acontece em segundo plano, sem expulsar o usuário.

---

## 9. Critérios de Aceite

- [ ] Login mobile e toda mutação (concluir pane, executar tarefa, registrar vencimento, instalar/remover item) funcionam sem 403 de CSRF.
- [ ] `/m/` faz **uma** requisição para montar a lista de aeronaves com contadores.
- [ ] PWA instala de fato na tela inicial (Android e iOS), com ícone correto e sem barra de endereço em modo `standalone`.
- [ ] Nenhuma tela mobile expõe uma ação de escrita que o MANTENEDOR não tenha no desktop.
- [ ] Nenhum script inline / atributo `on*=` em nenhum template mobile novo ou alterado (RN-16, auditável pelos testes de `test_mobile.py`).
- [ ] Sessão de uso contínuo > 15 min não força logout.
- [ ] Suíte de testes (`pytest tests -q`) e `ruff check .` passam sem regressão.
- [ ] Mockup aprovado pelo usuário antes do início da Etapa 3 (ver `mockup_mobile.html`).
