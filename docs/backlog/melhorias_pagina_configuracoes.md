# Backlog — Melhorias na página `/configuracoes`

> Status: 🟢 Levantamento concluído — **3.1, 3.2, 3.3 aplicados; 3.4 decidido e aplicado (admin-only)**. Pendentes: 3.5, 3.6, 3.7.
> Data: 2026-08-13 — revisado contra o código em 2026-08-13 (correções em 3.2, 3.3, 3.4, 3.7)
> Escopo: análise da página `/configuracoes` buscando melhorias que reaproveitem ao máximo o código/padrões já existentes (mínima alteração nos módulos).

## 1. Onde a página vive

Stack: FastAPI + Jinja2, server-rendered, JS vanilla por página (sem framework front-end).

| Peça | Arquivo |
|---|---|
| Rota | `app/web/pages/router.py:213-216` — `GET /configuracoes`, protegida por `AdminRequired` (`app/bootstrap/dependencies.py:147`) |
| Template | `app/web/templates/configuracoes.html` (1163 linhas) |
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
| Aeronaves | `configuracoes.html:11-44` | — (só nos botões) | `#btn-nova-aeronave` (`ADMINISTRADOR`, linha 27) → modal `#modal-aeronave` (242); `#btn-alterar-status-aeronave` (`ENCARREGADO`, linha 35) → modal `#modal-alterar-status-aeronave` (282) |
| Equipamentos e PNs | `configuracoes.html:46-88` | `ENCARREGADO` (card todo) | `#btn-novo-pn` → modal (426); `#btn-gerenciar-catalogo` → modal (388); `#btn-upload-xlsx` → modal (1112) |
| Controles de Vencimento | `configuracoes.html:90-131` | `ADMINISTRADOR` | `#btn-tipos-controle` (320); `#btn-editar-tipo-controle` (351); `#btn-equipamento-controle` (497) |
| Administração de Efetivo | `configuracoes.html:133-152` | `ADMINISTRADOR` | `#btn-config-efetivo` → **navega** para `/efetivo` (sem modal) |
| Inspeções | `configuracoes.html:154-177` | `ENCARREGADO` | `#btn-config-inspecoes` → modal (562); `#btn-gerenciar-catalogo-tarefas` → modal (730) |
| Publicações | `configuracoes.html:179-210` | `INSPETOR` | `#btn-gerenciar-edicoes` → modal (944, inclui zip do disco bruto + upload agendado); `#btn-status-acervo` → modal (1087); `#btn-ir-avulsas` → **navega** para `/publicacoes/avulsas` |
| Calendário | `configuracoes.html:212-235` | `ADMINISTRADOR` | `#btn-config-calendario-tipos` → modal (826) |

19 modais no total, todos com o mesmo esqueleto reutilizável.

Distribuição completa dos `data-role` na página (8 ocorrências): `ADMINISTRADOR` ×4 (linhas 27, 91, 134, 213), `ENCARREGADO` ×3 (35, 47, 155), `INSPETOR` ×1 (180). A contagem importa para o item 3.4.

**Módulos sem card, e por que isso está correto hoje:** Panes, Pedidos e Encarregado (Ciência) têm ícone no nav principal (`base.html:51,59,67`) mas nenhum conceito de "tipo/categoria" configurável — são só operacionais. A ausência de card não é uma lacuna por si só, é consistente com o padrão observado.

## 3. Oportunidades de melhoria (ordenadas por esforço, vitórias rápidas primeiro)

### 3.1 ✅ Remover handler órfão `btn-criar-inspecao` — Esforço: baixo — **FEITO**
> **Resolvido:** handler removido de `configuracoes.js`. Decisão do dono do produto: **não** adicionar o botão — a abertura de inspeções já existe na própria página `/inspecoes`, e um segundo caminho para a mesma ação não se pagava. A descrição do card (`configuracoes.html:167`) foi ajustada junto, para parar de prometer "abertura de novos eventos".

`configuracoes.js:111-113` registra um listener para `#btn-criar-inspecao` (navegaria para `/inspecoes`), mas **esse elemento não existe** em `configuracoes.html` (confirmado por busca no template inteiro). É inofensivo (`?.` evita erro), mas é código morto.
- **Reaproveitamento:** nenhum código novo — decisão binária: apagar as 3 linhas, ou adicionar o botão que falta no card "Inspeções" reaproveitando o handler já pronto (ele já aponta para o lugar certo).
- **Evidência a favor de adicionar o botão:** a descrição do próprio card (`configuracoes.html:167`) promete *"Configuração de tipos de inspeção, gerenciamento de tarefas template **e abertura de novos eventos**"* — mas os dois botões presentes cobrem só os dois primeiros. A funcionalidade está anunciada na UI e não tem porta de entrada; o handler órfão é o vestígio dela. Não é um empate: apagar as 3 linhas deixa a descrição mentindo, então nesse caso ela também precisa ser ajustada.

### 3.2 ✅ Completar dark mode do botão de Publicações — Esforço: baixo — **FEITO**
> **Resolvido:** `[data-theme="dark"] .btn-outline-publicacao` adicionada em `index.css`, na mesma lista dos outros overrides. As 6 regras mortas foram mantidas (limpeza é outro escopo, ver nota abaixo).

Das 7 cores de seção, 6 têm override para tema escuro em `index.css:387-392` (`[data-theme="dark"] .btn-outline-X`). Falta apenas `.btn-outline-publicacao` (definida em `index.css:359-366`), que é o card mais recente — foi esquecida na hora de adicionar.

**A proporção engana, e o achado é mais forte do que parece:** das 7 classes `.btn-outline-*` de seção, **6 não são usadas em lugar nenhum** — busca em `app/web/templates/` e `app/web/static/js/` não encontra `btn-outline-aeronave`, `-equipamento`, `-vencimento`, `-efetivo`, `-inspecao` nem `-calendario` (os `btn-outline-primary/-warning/-danger` que aparecem em `panes/detalhe.html` e `pedidos.html` são outra família, genérica). Ou seja, `index.css:387-392` é CSS morto. A **única** `.btn-outline-*` de seção efetivamente renderizada é `.btn-outline-publicacao` (`configuracoes_publicacoes.js:180`, botão de edição na lista de edições) — justamente a que não tem override.

Consequência: este é o único dos três itens visuais com impacto real na tela hoje. E o padrão a "copiar" é padrão de código morto — vale copiar a forma, não tirar dele a conclusão de que as outras 6 estão certas.
- **Reaproveitamento:** copiar literalmente o padrão das outras 6 linhas, só trocando a cor (`#818cf8` = índigo-400, o par claro de `#6366f1` na mesma escala que as outras seguem).
```css
[data-theme="dark"] .btn-outline-publicacao { color: #818cf8 !important; border-color: #818cf8 !important; }
```
- **Oportunidade adjacente (opcional):** se as 6 regras mortas forem removidas junto, some também a razão de existir dos pares `.btn-outline-X` não usados (`index.css:266-273, 284-291, 302-309, 320-327, 338-345, 377-384`). Não fazer isso no mesmo commit do fix — são coisas de risco diferente.

### 3.3 ✅ Diferenciar cor de `.btn-calendario` de `.btn-aeronave` — Esforço: baixo — **FEITO**
> **Resolvido:** Calendário passou para rosa `#ec4899` (hover `#db2777`, outline dark `#f472b6`). A faixa 300-340° era a única matiz livre sem invadir a semântica de `--status-danger` (~0°); rationale registrado em comentário no próprio `index.css`. Os 4 pontos foram alterados, incluindo `index.css:392` e o typo `#3b83f6` do ícone.

`.btn-aeronave` usa `var(--primary-color)` (`index.css:258`), que resolve para `#3b82f6` no tema claro. `.btn-calendario` usa `#3b82f6` **hardcoded** (`index.css:369`). No tema claro os dois cards ficam com o mesmo azul.

Precisão sobre o tema escuro — a colisão **não desaparece, e não é uma divergência**:
- **Botão preenchido:** em dark, `.btn-aeronave` acompanha `--primary-color` → `#60a5fa` (`index.css:50`), enquanto `.btn-calendario` fica preso em `#3b82f6`. Aqui sim as cores deixam de parear entre os temas.
- **Botão outline:** `index.css:392` força `[data-theme="dark"] .btn-outline-calendario` para `#60a5fa` — **exatamente o mesmo valor** de `.btn-outline-aeronave` (`index.css:387`). Não é o hardcode "não acompanhando": é a mesma colisão do tema claro, reproduzida à mão no escuro. (Na prática ambas são CSS morto — ver 3.2.)

Também no mesmo escopo, e não coberto acima: o **ícone** do card Calendário usa `#3b83f6` e `rgba(59, 131, 246, 0.1)` (`configuracoes.html:216`) — dígitos trocados em relação ao `#3b82f6` / `rgba(59, 130, 246, ...)` usado em todo o resto. É um typo, não uma terceira cor intencional; qualquer recolorização deve absorvê-lo.
- **Reaproveitamento:** trocar o hex fixo por um tom livre — nenhuma das 7 cores atuais usa, por exemplo, tons de vermelho/rosa. **São 4 pontos a alterar**, não 2: `.btn-calendario` (+`:hover`, `index.css:368-376`), `.btn-outline-calendario` (`:377-384`), o override dark da linha **392**, e o ícone em `configuracoes.html:216`. Esquecer a linha 392 mantém o outline colidindo com Aeronaves no tema escuro.

### 3.4 ✅ Resolver divergência de acesso (Admin vs. Encarregado) na página — **RESOLVIDO pela via (b)**

> **Decisão do dono do produto (2026-08-13): manter `/configuracoes` admin-only**, para simplificar o uso. Demandas específicas de ajuste e configuração são atendidas de forma controlada pelo próprio perfil admin, em vez de distribuir permissões por perfil. A via (a) foi **descartada** — não é backlog pendente.
>
> **Aplicado:** removidos os 8 `data-role` da página (todos decorativos, 3 deles prometendo acesso que a API nunca concedeu); `configuracoes.js` passou a checar só `ADMINISTRADOR`, com a mensagem de toast corrigida; comentário desatualizado em `auth_check.js:61` ("Admin ou Encarregado") alinhado ao código real. Um bloco de comentário no topo de `configuracoes.html` registra a decisão e avisa que recolocar `data-role` não é o caminho caso a página seja aberta no futuro — a ordem correta seria auditar o RBAC dos endpoints primeiro.
>
> O diagnóstico abaixo fica como registro de **por que** a via (a) foi descartada.

<details>
<summary>Diagnóstico original (histórico)</summary>

Quatro lugares do código discordavam sobre quem pode acessar `/configuracoes`:
- Backend: rota exige só `ADMINISTRADOR` puro (`router.py:214`, `AdminRequired`).
- Nav: o link do menu só aparece para `ADMINISTRADOR` (`auth_check.js:62-65`).
- Cliente: `configuracoes.js:19-25` checa `funcao !== 'ADMINISTRADOR' && funcao !== 'ENCARREGADO'` e mostra um toast dizendo *"Apenas administradores e encarregados podem acessar esta área"* — mas um ENCARREGADO nunca chega a executar esse JS, porque o servidor já barra com 403 antes do render.
- HTML: 8 atributos `data-role` (4 `ADMINISTRADOR`, 3 `ENCARREGADO`, 1 `INSPETOR` — ver §2), mas como `hasPermission` sempre retorna `true` para `ADMINISTRADOR` (`auth_check.js:92`), esses atributos hoje não escondem nada na prática — são decorativos, porque só admin chega na página.

Isso é uma decisão de produto pendente: **é preciso confirmar** se a intenção é (a) liberar a página parcialmente para ENCARREGADO/INSPETOR, ou (b) manter só ADMINISTRADOR e limpar os `data-role` vestigiais.

> [!WARNING]
> **A via (a) não é uma troca de uma linha.** Os `data-role` do HTML são *aspiracionais*, não um mecanismo pronto: o backend por trás da maioria dos cards é `AdminRequired` de forma independente, então liberar a rota entrega uma página cheia de botões que respondem 403.

**Por que a via (a) é cara — três obstáculos, verificados no código:**

**1. `EncarregadoOuAdmin` é a dependency errada.** `EncarregadoOuAdmin` = `require_role(*PRIVILEGED_FUNCTIONS)` = `{ENCARREGADO, ADMINISTRADOR}` (`app/modules/auth/roles.py:17`) — **exclui INSPETOR**. Com ela, o card de Publicações (`data-role="INSPETOR"`) continuaria inalcançável por inspetores, que é justamente o perfil para o qual ele foi marcado. A dependency que cobre os quatro valores de `data-role` da página é `EncarregadoInspetorOuAdmin` (`app/bootstrap/dependencies.py:159-161`), que já existe.

**2. `hasPermission` não tem hierarquia lateral.** `auth_check.js:97-103` só concede acesso por igualdade exata (mais o caso especial de `MANTENEDOR`). ENCARREGADO **não** satisfaz `data-role="INSPETOR"` e vice-versa. Mesmo com a rota aberta aos dois, encarregado não veria Publicações e inspetor não veria Equipamentos/Inspeções — cada um veria uma página parcial diferente. Isso pode até ser o desejado, mas é uma decisão a tomar, não um efeito automático.

**3. O backend barra independentemente — os `data-role` prometem o que a API não entrega:**

| Card (`data-role`) | Botão | Endpoint real | Dependency | Coerente? |
|---|---|---|---|---|
| Aeronaves | `#btn-alterar-status-aeronave` (`ENCARREGADO`) | `POST /aeronaves/{id}/toggle-status` | `EncarregadoOuAdmin` | ✅ sim |
| Equipamentos (`ENCARREGADO`) | `#btn-upload-xlsx` | `POST /equipamentos/inventario/upload-xlsx/*` | `EncarregadoOuAdmin` (`equipamentos/router.py:286`) | ✅ sim |
| Equipamentos (`ENCARREGADO`) | `#btn-novo-pn`, `#btn-gerenciar-catalogo` | `POST` / `PATCH` / `DELETE /equipamentos/` | `AdminRequired` (`equipamentos/router.py:45,66,76,103`) | ❌ **403** |
| Publicações (`INSPETOR`) | `#btn-gerenciar-edicoes` | `GET /publicacoes/api/edicoes` (+ `ativar`, `arquivar`, `relatorio`) | `AdminRequired` (`publicacoes/router.py:471,482,502,521`) | ❌ **403** |
| Publicações (`INSPETOR`) | `#btn-status-acervo` | `GET /publicacoes/api/duplicacao` | `AdminRequired` (`publicacoes/router.py:551`) | ❌ **403** |

Só **dois** controles estão genuinamente cabeados para não-admin. Os demais foram marcados por intenção, nunca por verificação.

**4. Há uma suposição de projeto explícita a ser renegociada.** `app/modules/publicacoes/router.py:461-463` registra em comentário: *"Todo endpoint aqui é `AdminRequired`. A página /configuracoes já exige Admin (`app/web/pages/router.py`), mas gate de página não é autorização: quem chama a API não passa necessariamente pela página."* Mudar a dependency da rota sem tocar nos módulos não quebra a segurança (o backend continua barrando — é justamente o ponto do comentário), mas quebra a **coerência da tela** e invalida silenciosamente o raciocínio ali documentado.

- **Custo real da via (a):** decisão de produto + escolher `EncarregadoInspetorOuAdmin` em `router.py:214` + ajuste em `auth_check.js:62` + **auditoria endpoint a endpoint** nos módulos `equipamentos`, `publicacoes` (ciclo de vida de edições), `calendario` e `aeronaves`, decidindo caso a caso o que relaxar — e alinhando os `data-role` ao resultado dessa auditoria, não o contrário. É um lote de médio/alto porte que atravessa 4 módulos, não uma limpeza.
- **Custo real da via (b):** baixo e contido, como descrito antes — remover o branch de ENCARREGADO em `configuracoes.js:19-25` (que hoje só produz uma mensagem falsa que ninguém vê) e os `data-role` não-`ADMINISTRADOR` que sobraram. **Recomendação:** fazer (b) agora e abrir (a) como item próprio se e quando o produto pedir, em vez de deixar a página no estado ambíguo atual.

</details>

### 3.5 Card "Sistemas ATA" (catálogo do módulo Panes) — Esforço: médio
Diferente de "Tipos de Controle" (Vencimentos), "Tipos de Inspeção" e "Tipos de Evento" (Calendário) — que têm CRUD completo com card+modal em `/configuracoes` — o catálogo de **Sistemas ATA**, usado para classificar Panes, só tem leitura: `app/modules/panes/router.py:24-35` expõe apenas `GET /sistemas`, sem POST/PUT/DELETE em nenhum router (confirmado por busca em todos os routers). Hoje só é editável via seed/SQL direto.
- **Por quê:** é um catálogo de "tipo" sem tela administrativa, ao lado de 3 exemplos já resolvidos do mesmo padrão. (A afirmação de que seria o *único* nessa condição não foi verificada exaustivamente — o que está confirmado é que este é somente-leitura.)
- **Reaproveitamento:** a UI é praticamente uma cópia do modal `#modal-tipo-controle` (`configuracoes.html:320-348`) e da função `salvarTipoControle` em `configuracoes.js` — só trocar os campos/endpoint. O esforço real está no backend (endpoints novos em `panes/router.py` e `panes/service.py`), não na parte de configurações.

### 3.6 Reagrupar os cards por categoria — Esforço: baixo/médio, fazer junto com um próximo card novo
Hoje os 7 cards são uma lista plana sem headers de seção. Funciona bem em 7; ao acrescentar um 8º ou 9º card (itens 3.5 ou o de Inventário, ver docs relacionados), a varredura visual começa a pesar sem agrupamento (ex.: "Frota & Manutenção", "Publicações & Documentação", "Efetivo & Acesso").
- **Reaproveitamento:** é reestruturação do HTML existente (agrupar os `<div class="card">` já prontos sob `<h3>` de seção), nenhum componente novo.
- Recomendação: não fazer isoladamente — combinar com a entrada do próximo card (3.5 ou o card de Inventário já especificado em `docs/backlog/resolvidos/modulo_inventario/enhange_gerenciar_inventario.md`, que já prevê explicitamente um botão em `/configuracoes` no RF-01 daquele documento).

### 3.7 Retomada de polling do upload ao recarregar a página — Esforço: médio
Já documentado como débito conhecido em `docs/backlog/modulo_publicacoes/12_refinamento_gestao_e_envio.md` (item B-06, linhas 72 e 287-291): se o usuário reabre `/configuracoes` no meio de um upload em `ENVIANDO`/`PROCESSANDO`, a barra de progresso não retoma sozinha — `currentUploadJobId` vive só em memória e o polling só é ligado dentro do fluxo de `tratarSubmitUpload`.

**Isto vale para o modo de processamento imediato, não para o agendado.** Em `modo_processamento=AGENDADO` o job termina em `AGUARDANDO_PROCESSAMENTO` e `iniciarPollingUpload` **para o polling de propósito** — há comentário explícito no código dizendo que não faz sentido manter o navegador pingando a cada 3s por horas, já que o processamento roda de madrugada (`publicacoes_processamento_hora_utc`, `config/__init__.py:138-147`). Nesse modo não há barra a retomar; o usuário confere pela lista de edições. Descrever o item como "upload agendado em `PROCESSANDO`" descreve um estado que o caminho agendado não alcança.
- **Reaproveitamento:** o loop de polling já existe — é `iniciarPollingUpload` em **`configuracoes_publicacoes.js:541-604`** (⚠️ *não* 462-518: essas linhas são o loop de **envio de partes** dentro de `tratarSubmitUpload`, que é o que o B-06 rotula corretamente como "loop de envio de partes"). O backend também já está pronto: `GET /publicacoes/api/edicoes/uploads?limit=1` (`publicacoes/router.py:1094-1113`, `listar_upload_jobs`) devolve os últimos jobs. Falta só, no `DOMContentLoaded` de `configuracoes_publicacoes.js:40-62`, consultar esse endpoint, e havendo job em `ENVIANDO`/`PROCESSANDO`, restaurar `currentUploadJobId` + abrir o container de progresso + chamar `iniciarPollingUpload(job.id)`.
- **Ressalva:** retomar o *polling* é barato; retomar o *envio* de um ZIP interrompido no meio das partes não é — o `File` do input não sobrevive ao reload. Só a primeira metade é escopo deste item (a segunda é o retry por parte, também em B-06).
- Não é um item de atalho/botão, mas está no mesmo card (Publicações) e vale registrar aqui por proximidade.

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
- Os únicos "settings" fora da UI são de nível de deployment (hora UTC do processamento noturno, `app/bootstrap/config/__init__.py:138-147`, e `PUBLICACOES_EDICOES_RETIDAS`, já registrado como dívida em `09_plano_configuracoes.md:351-353`) — baixo valor trazer para a UI, pois exigem restart do processo de qualquer forma.
- **Encarregado, Panes e Pedidos** não precisam de card hoje: são módulos puramente operacionais, sem conceito de tipo/categoria configurável.
- O card de Publicações já é a evidência de que o time vem seguindo a prática recomendada aqui: os recursos recentes de disco bruto agendado e PDF.js (commits `339d13b`, `315da0f`) foram **encaixados no card existente**, não viraram cards novos.

## 6. Priorização sugerida

| Ordem | Item | Esforço | Tipo |
|---|---|---|---|
| ~~1~~ | ~~3.2 Dark mode do botão Publicações~~ | Baixo | ✅ **feito** |
| ~~2~~ | ~~3.1 Remover handler órfão~~ | Baixo | ✅ **feito** |
| ~~3~~ | ~~3.3 Cor exclusiva do Calendário~~ | Baixo | ✅ **feito** |
| ~~4~~ | ~~3.4 **via (b)**: consolidar página como admin-only~~ | Baixo | ✅ **feito** |
| 1 | 3.7 Retomada de polling do upload | Médio | Robustez — **próximo** |
| 2 | 3.5 Card "Sistemas ATA" | Médio | Novo card (backend + UI) |
| 3 | 3.6 Reagrupamento por categoria | Baixo/Médio | Reorganização visual (fazer junto com o card de Inventário) |
| ~~—~~ | ~~3.4 **via (a)**: abrir a página a ENCARREGADO/INSPETOR~~ | Médio/Alto | ❌ **descartado** — decisão de produto: página permanece admin-only |

O primeiro lote (3.1, 3.2, 3.3) era trivial e sem risco — sendo que só o 3.2 mudou algo que o usuário enxerga. O 3.4 foi resolvido pela via (b): a página é admin-only por decisão, e a via (a) saiu do backlog. Os três restantes são de médio porte; 3.5 e 3.6 fazem sentido como lote conjunto, já que mexem na mesma área (grid de cards), enquanto 3.7 é independente e vive só no card de Publicações.

---

## 7. Nota de revisão (2026-08-13)

Este documento foi reconferido linha a linha contra o código. Conferiram exatamente: todas as referências de rota/dependency/JS/CSS da §1, os 13 números de modal da §2, a contagem "19 modais", `panes/router.py:24-35`, `efetivo.html:16`, `base.html:51,59,67`, as referências cruzadas a `12_refinamento` (B-06 em 72 e 287-291) e ao RF-01 de `enhange_gerenciar_inventario.md:224`, e toda a §5.

Foram corrigidos: a premissa de 3.4 (os `data-role` **não** estão prontos; dependency errada; esforço subestimado), a referência de linha e o rótulo da função em 3.7 (`462-518` era o loop de envio de partes, não o de polling), o diagnóstico de dark mode em 3.2 (6 das 7 regras são CSS morto) e a cláusula de tema escuro em 3.3 (`index.css:392` reproduz a colisão, não a diverge). Ajustes menores: contagem de linhas do template (1163), faixa do campo de hora UTC (138-147), `data-role` de nível de botão no card Aeronaves, e ressalva de escopo em 3.5.
