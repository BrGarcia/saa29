# Backlog — Melhorias na página `/configuracoes`

> Status: 🟢 Levantamento concluído (nenhuma alteração de código aplicada ainda)
> Data: 2026-08-13
> Escopo: análise da página `/configuracoes` buscando melhorias que reaproveitem ao máximo o código/padrões já existentes (mínima alteração nos módulos).

## 1. Onde a página vive

Stack: FastAPI + Jinja2, server-rendered, JS vanilla por página (sem framework front-end).

| Peça | Arquivo |
|---|---|
| Rota | `app/web/pages/router.py:213-216` — `GET /configuracoes`, protegida por `AdminRequired` (`app/bootstrap/dependencies.py:147`) |
| Template | `app/web/templates/configuracoes.html` (1164 linhas) |
| JS principal | `app/web/static/js/configuracoes.js` (1937 linhas) |
| JS de Publicações | `app/web/static/js/configuracoes_publicacoes.js` (645 linhas — extraído à parte por tamanho) |
| CSS das cores por seção | `app/web/static/css/index.css:256-392` |

**Padrão consolidado do módulo** (documentado também em `docs/backlog/modulo_publicacoes/09_plano_configuracoes.md:239-278`):
- Card no grid: ícone + título + descrição + botões empilhados.
- Botão abre um **modal `glass-panel`** (`position:fixed; inset:0` + `backdrop-filter`) com header (ícone de fechar em SVG) e footer ("Fechar").
- Handlers registrados em `DOMContentLoaded`, **nunca `onclick` inline** (CSP).
- Visibilidade condicional via atributo `data-role="ADMINISTRADOR|ENCARREGADO|INSPETOR"` lido por `window.hasPermission` (`auth_check.js:35-53`).

Esse padrão já está validado 7 vezes na página — é a base de reaproveitamento para qualquer item novo abaixo.

## 2. Mapa dos atalhos existentes hoje

7 cards, lista plana (sem agrupamento por categoria), `grid-template-columns: repeat(auto-fit, minmax(300px,1fr))`:

| Card | HTML | `data-role` | Botões (ação) |
|---|---|---|---|
| Aeronaves | `configuracoes.html:11-44` | — | `#btn-nova-aeronave` → modal `#modal-aeronave` (242); `#btn-alterar-status-aeronave` (`ENCARREGADO`) → modal `#modal-alterar-status-aeronave` (282) |
| Equipamentos e PNs | `configuracoes.html:46-88` | `ENCARREGADO` (card todo) | `#btn-novo-pn` → modal (426); `#btn-gerenciar-catalogo` → modal (388); `#btn-upload-xlsx` → modal (1112) |
| Controles de Vencimento | `configuracoes.html:90-131` | `ADMINISTRADOR` | `#btn-tipos-controle` (320); `#btn-editar-tipo-controle` (351); `#btn-equipamento-controle` (497) |
| Administração de Efetivo | `configuracoes.html:133-152` | `ADMINISTRADOR` | `#btn-config-efetivo` → **navega** para `/efetivo` (sem modal) |
| Inspeções | `configuracoes.html:154-177` | `ENCARREGADO` | `#btn-config-inspecoes` → modal (562); `#btn-gerenciar-catalogo-tarefas` → modal (730) |
| Publicações | `configuracoes.html:179-210` | `INSPETOR` | `#btn-gerenciar-edicoes` → modal (944, inclui zip do disco bruto + upload agendado); `#btn-status-acervo` → modal (1087); `#btn-ir-avulsas` → **navega** para `/publicacoes/avulsas` |
| Calendário | `configuracoes.html:212-235` | `ADMINISTRADOR` | `#btn-config-calendario-tipos` → modal (826) |

19 modais no total, todos com o mesmo esqueleto reutilizável.

**Módulos sem card, e por que isso está correto hoje:** Panes, Pedidos e Encarregado (Ciência) têm ícone no nav principal (`base.html:51,59,67`) mas nenhum conceito de "tipo/categoria" configurável — são só operacionais. A ausência de card não é uma lacuna por si só, é consistente com o padrão observado.

## 3. Oportunidades de melhoria (ordenadas por esforço, vitórias rápidas primeiro)

### 3.1 Remover handler órfão `btn-criar-inspecao` — Esforço: baixo
`configuracoes.js:111-113` registra um listener para `#btn-criar-inspecao` (navegaria para `/inspecoes`), mas **esse elemento não existe** em `configuracoes.html` (confirmado por busca no template inteiro). É inofensivo (`?.` evita erro), mas é código morto.
- **Reaproveitamento:** nenhum código novo — decisão binária: apagar as 3 linhas, ou adicionar o botão que falta no card "Inspeções" reaproveitando o handler já pronto (ele já aponta para o lugar certo).

### 3.2 Completar dark mode do botão de Publicações — Esforço: baixo
Das 7 cores de seção, 6 têm override para tema escuro em `index.css:387-392` (`[data-theme="dark"] .btn-outline-X`). Falta apenas `.btn-outline-publicacao` (definida em `index.css:359-366`), que é o card mais recente — foi esquecida na hora de adicionar.
- **Reaproveitamento:** copiar literalmente o padrão das outras 6 linhas, só trocando a cor.
```css
[data-theme="dark"] .btn-outline-publicacao { color: #818cf8 !important; border-color: #818cf8 !important; }
```

### 3.3 Diferenciar cor de `.btn-calendario` de `.btn-aeronave` — Esforço: baixo
`.btn-aeronave` usa `var(--primary-color)` (`index.css:258`), que resolve para `#3b82f6` no tema claro. `.btn-calendario` usa `#3b82f6` **hardcoded** (`index.css:369`). No tema claro os dois cards ficam com o mesmo azul; no tema escuro `--primary-color` vira `#60a5fa` mas o hardcode não acompanha, então as cores também não pareiam entre os temas.
- **Reaproveitamento:** trocar o hex fixo de `.btn-calendario`/`.btn-outline-calendario` por um tom livre — nenhuma das 7 cores atuais usa, por exemplo, tons de vermelho/rosa.

### 3.4 Resolver divergência de acesso (Admin vs. Encarregado) na página — Esforço: baixo (após decisão de produto)
Três lugares do código hoje discordam sobre quem pode acessar `/configuracoes`:
- Backend: rota exige só `ADMINISTRADOR` puro (`router.py:214`, `AdminRequired`).
- Nav: o link do menu só aparece para `ADMINISTRADOR` (`auth_check.js:62-65`).
- Cliente: `configuracoes.js:19-25` checa `funcao !== 'ADMINISTRADOR' && funcao !== 'ENCARREGADO'` e mostra um toast dizendo *"Apenas administradores e encarregados podem acessar esta área"* — mas um ENCARREGADO nunca chega a executar esse JS, porque o servidor já barra com 403 antes do render.
- HTML: 3 cards/botões usam `data-role="ENCARREGADO"` e 1 usa `data-role="INSPETOR"`, mas como `hasPermission` sempre retorna `true` para `ADMINISTRADOR` (`auth_check.js:92`), esses atributos hoje não escondem nada na prática — são decorativos, porque só admin chega na página.

Isso é uma decisão de produto pendente, não um bug per se: **é preciso confirmar** se a intenção é (a) liberar a página parcialmente para ENCARREGADO/INSPETOR, ou (b) manter só ADMINISTRADOR e limpar os `data-role` vestigiais.
- **Reaproveitamento:** já existe pronto o dependency `EncarregadoOuAdmin` (`app/bootstrap/dependencies.py:151-153`, já usado em Panes/Pedidos/Equipamentos) — trocar `AdminRequired` → `EncarregadoOuAdmin` em `router.py:214` mais o ajuste equivalente em `auth_check.js:62` é a via (a), sem criar nenhum mecanismo novo (o `data-role` no HTML já está pronto para essa granularidade). A via (b) é só remover o branch de ENCARREGADO em `configuracoes.js:19-25` e os atributos `data-role="ENCARREGADO"/"INSPETOR"` que sobraram.
- Nota: existe também uma ideia relacionada, de escopo maior e complementar a este achado — RBAC granular por checkbox por usuário, na tela de Efetivo — desenvolvida na seção **7** deste documento.

### 3.5 Card "Sistemas ATA" (catálogo do módulo Panes) — Esforço: médio
Diferente de "Tipos de Controle" (Vencimentos), "Tipos de Inspeção" e "Tipos de Evento" (Calendário) — que têm CRUD completo com card+modal em `/configuracoes` — o catálogo de **Sistemas ATA**, usado para classificar Panes, só tem leitura: `app/modules/panes/router.py:24-35` expõe apenas `GET /sistemas`, sem POST/PUT/DELETE em nenhum router. Hoje só é editável via seed/SQL direto.
- **Por quê:** é o único catálogo de "tipo" do sistema sem tela administrativa, ao lado de 3 exemplos já resolvidos do mesmo padrão.
- **Reaproveitamento:** a UI é praticamente uma cópia do modal `#modal-tipo-controle` (`configuracoes.html:320-348`) e da função `salvarTipoControle` em `configuracoes.js` — só trocar os campos/endpoint. O esforço real está no backend (endpoints novos em `panes/router.py` e `panes/service.py`), não na parte de configurações.

### 3.6 Reagrupar os cards por categoria — Esforço: baixo/médio, fazer junto com um próximo card novo
Hoje os 7 cards são uma lista plana sem headers de seção. Funciona bem em 7; ao acrescentar um 8º ou 9º card (itens 3.5 ou o de Inventário, ver docs relacionados), a varredura visual começa a pesar sem agrupamento (ex.: "Frota & Manutenção", "Publicações & Documentação", "Efetivo & Acesso").
- **Reaproveitamento:** é reestruturação do HTML existente (agrupar os `<div class="card">` já prontos sob `<h3>` de seção), nenhum componente novo.
- Recomendação: não fazer isoladamente — combinar com a entrada do próximo card (3.5 ou o card de Inventário já especificado em `docs/backlog/modulo_inventario/enhange_gerenciar_inventario.md`, que já prevê explicitamente um botão em `/configuracoes` no RF-01 daquele documento).

### 3.7 Retomada de polling do upload agendado ao recarregar a página — Esforço: médio
Já documentado como débito conhecido em `docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md` (item B-06, linhas 72 e 287-291): se o usuário reabre `/configuracoes` no meio de um upload agendado em status `PROCESSANDO`, a barra de progresso não retoma sozinha.
- **Reaproveitamento:** o loop de acompanhamento do envio já existe em `configuracoes_publicacoes.js:462-518` — falta só reconectar/consultar o status ao carregar a página, sem criar nada novo. Não é um item de atalho/botão, mas está no mesmo card (Publicações) e vale registrar aqui por proximidade.

## 4. Padrões reutilizáveis a seguir em qualquer item novo (referência rápida)

1. **Estrutura de card:** `configuracoes.html:11-44` (Aeronaves) é o exemplo mais simples de copiar.
2. **Cores por seção:** pares `.btn-X` / `.btn-outline-X` + dark mode em `index.css:256-392`; comentário em `index.css:347-349` já documenta o raciocínio de escolha de cor nova.
3. **Modal `glass-panel`:** copiar o esqueleto de qualquer um dos 19 modais existentes (header com SVG "X" de fechar + footer "Fechar").
4. **Ícones:** módulos que já têm ícone no nav principal (Panes, Pedidos, Encarregado, Inventário) já têm SVG pronto em `base.html:51-121` para copiar 1:1 — é o que já foi feito para Publicações (`configuracoes.html:184-191`, com comentário explícito registrando a decisão).
5. **Botão que só navega (sem modal):** `#btn-config-efetivo` (`configuracoes.js:76-81`) e `#btn-ir-avulsas` (`configuracoes_publicacoes.js:54-56`) são o modelo pronto para qualquer atalho que só precise de `window.location.href = '/...'`.
6. **Visibilidade condicional:** atributo `data-role="X"` (mecanismo já existente, `auth_check.js:35-53`) — nenhum novo mecanismo de permissão de UI deve ser criado.
7. **Utilitários globais:** `apiFetch`, `showToast`, `escapeHtml` (de `app.js`) já cobrem chamada de API e feedback visual para qualquer card novo.

## 5. O que foi verificado e está OK (sem ação necessária)

- **Não há configuração "espalhada"** fora de `/configuracoes`: busca em `aeronaves.html`, `inventario.html`, `inspecoes/lista.html`, `calendario.html` e `vencimentos.html` não encontrou controles administrativos duplicados. O único controle fora da página é `#btn-add-membro` em `efetivo.html:16`, que é a própria tela de destino do card "Administração de Efetivo" — não é duplicata.
- Os únicos "settings" fora da UI são de nível de deployment (hora UTC do processamento noturno, `app/bootstrap/config/__init__.py:143-144`, e `PUBLICACOES_EDICOES_RETIDAS`, já registrado como dívida em `09_plano_configuracoes.md:351-353`) — baixo valor trazer para a UI, pois exigem restart do processo de qualquer forma.
- **Encarregado, Panes e Pedidos** não precisam de card hoje: são módulos puramente operacionais, sem conceito de tipo/categoria configurável.
- O card de Publicações já é a evidência de que o time vem seguindo a prática recomendada aqui: os recursos recentes de disco bruto agendado e PDF.js (commits `339d13b`, `315da0f`) foram **encaixados no card existente**, não viraram cards novos.

## 6. Priorização sugerida

| Ordem | Item | Esforço | Tipo |
|---|---|---|---|
| 1 | 3.1 Remover handler órfão | Baixo | Limpeza |
| 2 | 3.2 Dark mode do botão Publicações | Baixo | Consistência visual |
| 3 | 3.3 Cor exclusiva do Calendário | Baixo | Consistência visual |
| 4 | 3.4 Decidir acesso Admin/Encarregado | Baixo (após decisão) | Decisão de produto + limpeza |
| 5 | 3.7 Retomada de polling do upload | Médio | Robustez |
| 6 | 3.5 Card "Sistemas ATA" | Médio | Novo card (backend + UI) |
| 7 | 3.6 Reagrupamento por categoria | Baixo/Médio | Reorganização visual (fazer junto com #6 ou o card de Inventário) |

Itens 1-3 são triviais e sem risco, recomendados como primeiro lote. Item 4 depende de alinhamento com o dono do produto antes de qualquer código. Itens 5-7 são de médio porte e fazem mais sentido como um lote conjunto futuro, já que todos mexem na mesma área (grid de cards).

A ideia da seção 7 (permissões individuais por checkbox) fica fora desta tabela por ser um projeto de outro porte — depende do item 3.4 estar decidido antes e envolve mudanças de backend fora do escopo de `/configuracoes` (também mexe na tela de Efetivo).

## 7. Ideia maior (rascunho desenvolvido): Permissões individuais por usuário via checkbox

> **Origem:** rascunho do usuário em `docs/backlog/permissoes_pelo_pagina_confg.md` (5 linhas, não desenvolvido): *"desenvolver futuramente a ideia de definir as permissões RBAC de maneira individual através de checkbox em cada usuário na página de configurações / página Administração de Efetivo Militar — um botão 'definir permissões' que abre um modal e lista todas as permissões e roles em formato de checkbox."*

Diferente dos itens 3.1-3.7 (ajustes pontuais dentro do padrão já existente da página), esta é uma mudança que toca o sistema de autorização — por isso ganha uma seção própria, com análise de viabilidade antes de qualquer estimativa de esforço.

### 7.1 Como o RBAC funciona hoje (por que a ideia, como escrita, não é trivial)

O sistema usa **RBAC por papel único e fechado, não por permissões**: 1 usuário → 1 campo `funcao` (string) → conjunto fixo de capacidades definido em código.

- Papéis definidos em `app/modules/auth/roles.py:10-25` (`MANTENEDOR`, `ENCARREGADO`, `INSPETOR`, `ADMINISTRADOR`) e replicados no enum Pydantic `TipoPapel` (`app/shared/core/enums.py:43-55`) — dois lugares que precisam ficar sincronizados manualmente.
- A coluna `funcao` no banco é `String(50)` livre, sem CHECK/FK (`app/modules/auth/models.py:50-54`; criada em `migrations/versions/20260418_2233_6ff995143283_initial_schema_consolidated.py:74-79`) — a validação do valor é só na camada Pydantic.
- Backend checa via `ensure_role`/`require_role` (`app/bootstrap/dependencies.py:115-165`) e 7 dependencies-atalho (`AdminRequired`, `EncarregadoOuAdmin`, `InspetorOuAdmin`, etc.), usadas em **~126 pontos** espalhados por 14 módulos (`aeronaves`, `auth`, `calendario`, `efetivo`, `encarregado`, `equipamentos`, `inspecoes`, `panes`, `pedidos`, `publicacoes`, `vencimentos`, `web/pages`), mais ~5 usos diretos de `ensure_role` e 8 comparações ad-hoc de `funcao` (2 delas já fora do padrão, com listas hardcoded em vez das constantes de `roles.py` — `app/modules/panes/router.py:428`, `app/modules/panes/service.py:223`).
- Frontend checa via `window.hasPermission` (`app/web/static/js/auth_check.js:76-107`), que **não é uma hierarquia totalmente ordenada**: um `INSPETOR` chamando `hasPermission('ENCARREGADO')` retorna `false` — ENCARREGADO e INSPETOR são paralelos, não comparáveis, apesar do comentário do arquivo sugerir "papel mínimo exigido". O dado `funcao` vem de `/auth/me` uma vez por carregamento de página e fica em `localStorage.saa29_user` (`auth_check.js:1-26`) — não é revalidado a cada checagem.
- Visibilidade de UI é controlada pelo atributo `data-role="X"` em qualquer elemento (`auth_check.js:34-53`), já usado ~19-23 vezes em 7 templates — é o mesmo mecanismo usado nos 7 cards desta página (seção 2).

**Não existe hoje o conceito de "permissão" como entidade** — nem tabela, nem enum — apenas papéis. A ideia do rascunho ("checkbox por permissão por usuário") pressupõe essa camada, que precisaria ser criada do zero.

### 7.2 Duas leituras possíveis do rascunho

**(A) Sistema completo de permissões granulares** — reescrever toda a autorização para checar permissões individuais em vez de papel:
- Exigiria revisar os ~170-180 pontos de checagem listados acima (backend + frontend + templates) — não é uma feature isolada, é uma reescrita da camada de autorização inteira.
- Precisaria decidir a semântica dos overrides: só **aditivos** (dão mais que o papel base) ou também **subtrativos** (revogam o que o papel daria)? Isso muda o modelo de dados por completo.
- Afeta a regra de "último admin" já existente e comentada como ponto sensível no código (`app/modules/auth/service.py:189-198,286-297`, marcada como BUG-03/RISCO-07) — precisaria ser redefinida, já que "última pessoa com a permissão X" complica a regra atual de "último `ADMINISTRADOR`".
- **Esforço: alto.** Autorização é código sensível a segurança — o próprio comentário de `roles.py:5-7` já é enfático sobre isso ("evita aliases indevidos... facilita auditoria de segurança"). **Não recomendado como próximo passo**; é um projeto à parte, não um item pontual de backlog.

**(B) MVP restrito aos atalhos de `/configuracoes` (recomendado)** — em vez de um sistema genérico de permissão por feature, aplicar overrides individuais só sobre o conjunto já enumerado e fechado de `data-role` usados nos 7 cards desta página (relaciona-se diretamente com o item 3.4). É plausível porque esse conjunto já é pequeno, fechado e centralizado num único lugar (o HTML), ao contrário do RBAC de backend que está espalhado em ~126 pontos.

### 7.3 Desenho do MVP (opção B) — reaproveitamento máximo do que já existe

- **Botão "Definir permissões"**: reaproveita o padrão de ação por linha já usado na tabela de `efetivo.html:24-38` (ícone lápis "Editar", `efetivo.js:87-93`) — adicionar um segundo ícone ao lado, no mesmo padrão visual, sem inventar um novo layout de linha.
- **Modal**: segue o mesmo esqueleto `glass-panel` já padronizado (header com SVG "X" de fechar + footer "Fechar") — o molde usado nos 19 modais de `/configuracoes` e nos 3 modais de `efetivo.html` (`#modal-membro`, `#modal-editar-membro`, `#modal-resetar-senha`), não é um componente novo.
- **Lista de checkboxes dentro do modal**: não existe hoje um componente pronto para isso — o mais próximo é o filtro estático de `app/web/templates/calendario.html:10-12` (classe `.calendar-check`), que serve de referência visual, mas a lista precisaria ser gerada dinamicamente em JS a partir de um array fixo de permissões, no mesmo estilo de geração de linhas já usado em `efetivo.js:61-127` (linhas de tabela) ou nas listas dos modais de catálogo em `configuracoes.js`.
- **Permissões candidatas ao MVP** (mapeadas 1:1 aos `data-role` já existentes nos cards de `/configuracoes`, sem inventar taxonomia nova): `EFETIVO_ADMIN`, `INSPECOES_CONFIG`, `PUBLICACOES_CONFIG`, `VENCIMENTOS_CONFIG`, `CALENDARIO_CONFIG`, `AERONAVES_STATUS`, `EQUIPAMENTOS_CONFIG`.

O que precisa ser criado — e este é o ponto de atenção mais importante do MVP, porque não é "só front-end":
1. Tabela nova pequena, ex. `usuario_permissoes_extra(usuario_id, permissao)` + migration Alembic — enum fechado de ~7 valores, **aditivo apenas** (dá acesso extra além do papel base; não revoga nada do papel base).
2. Endpoint novo `PUT /auth/usuarios/{id}/permissoes` (`AdminRequired`), ao lado dos já existentes em `app/modules/auth/router.py:381-494`.
3. Incluir essas permissões no payload de `/auth/me` (`UsuarioOut`, `app/modules/auth/schemas.py:55-68`) e no `localStorage.saa29_user` (hoje só guarda `id, nome, funcao, username, posto` — `auth_check.js:13-19`).
4. `hasPermission` (`auth_check.js:76-107`) passa a checar também essa lista de overrides, além da `funcao` — mudança localizada numa única função (~30 linhas), sem tocar no restante do frontend.
5. **Os endpoints por trás dos ~7 botões-alvo precisam aprender sobre o override**, senão o MVP vira só decoração — não os ~126 pontos todos, só os poucos que atendem os cards afetados. Caminho: uma dependency nova, ex. `EncarregadoOuAdminOuOverride`, que aceita papel OU override, sem tocar nos outros ~120 pontos do sistema que ficam fora do escopo do MVP.

### 7.4 Risco a evitar

Se os passos 1, 2, 3 e 5 acima não forem feitos e só a parte visual (checkbox no modal + `data-role` no client) for implementada, o resultado é **controle de acesso decorativo**: o botão aparece para o usuário por causa do override, mas a chamada de API por trás continua checando só `funcao` e retorna 403. Qualquer implementação deste item precisa cobrir o ciclo completo (front + back) — do contrário é pior que não ter a feature, porque cria uma falsa expectativa de acesso.

### 7.5 Estimativa e recomendação

| Abordagem | Esforço | Recomendação |
|---|---|---|
| (A) Sistema completo de permissões granulares | Alto (reescreve ~170-180 pontos de autorização em todo o sistema) | Não fazer agora — projeto à parte, exigiria revisão de segurança dedicada |
| (B) MVP restrito às ~7 permissões de `/configuracoes` | Médio/Alto (nova tabela + migration + endpoint + ajuste em `hasPermission` + dependency nova nos endpoints dos botões-alvo) | Viável como próximo passo, mas só depois do item **3.4** estar decidido |

O item 3.4 (quem acessa `/configuracoes` — Admin puro ou Admin+Encarregado) e esta ideia mexem na mesma pergunta de fundo de RBAC desta página; resolver 3.4 primeiro evita retrabalho ao desenhar o MVP de permissões individuais.
