# Melhorias de Navegação — "Explorador de Documentos" no Módulo `publicacoes`

> **Status: adotado.** A proposta abaixo virou a implementação real de `/publicacoes` e
> `/publicacoes/viewer/{doc_id}` — ver [`10_plano_preview_explorador.md`](10_plano_preview_explorador.md)
> §8 para o que foi construído e `08_status_de_implementacao.md` para o estado atual. Este
> documento fica como registro do *porquê* de cada decisão de design; o corpo abaixo não foi
> reescrito.
>
> **Origem.** Este documento nasceu de um prompt genérico ("crie o protótipo visual de um sistema
> web para gerenciamento e visualização de PDFs, inspirado no Windows Explorer"). O prompt foi
> escrito **sem conhecimento do módulo que já existe** — pede protótipo com dados fictícios, leitura
> automática de diretórios e um viewer completo, três coisas que ou já estão prontas, ou colidem com
> decisões travadas do projeto.
>
> Esta versão substitui o prompt por um **plano de melhoria executável**, medido contra o código de
> `app/modules/publicacoes/` e `app/web/templates/publicacoes/` no estado da branch
> `feature/modulo-publicacoes` (commit `dc6ceca`).
>
> **Veredito em uma frase:** a visualização é viável e vale a pena — mas como **Etapa 3 de UI sobre
> a navegação que a Etapa 2 já entregou**, não como sistema novo. Cerca de 60% do que o prompt pede
> já existe; 25% é trabalho de frontend sobre APIs prontas; 15% precisa de endpoint ou coluna nova;
> e cinco premissas do prompt precisam ser abandonadas.

---

## 1. O que já existe (medido, não estimado)

| Capacidade pedida no prompt | Estado hoje | Onde |
|---|---|---|
| Navegar por pastas e subpastas | ✅ Existe, em 3 páginas encadeadas | `/publicacoes` → `/publicacoes/manuais/{codigo}` → `.../{capitulo}` |
| Árvore hierárquica | 🟡 Parcial — `<details>`/`<summary>` por categoria na home, não árvore persistente | `publicacoes/lista.html:14-26` |
| Breadcrumb | 🟡 Existe, textual e raso (2 níveis) | `manual.html:6-8`, `capitulo.html:6-10` |
| Área principal com conteúdo da pasta | ✅ Tabela paginada de documentos | `capitulo.html:17-64` |
| Ícones distintos pasta/PDF | ❌ Não existe | — |
| Ordenação | 🟡 Fixa (`sort_order` do RN-05), não escolhível pelo usuário | `service.listar_documentos_do_manual:539` |
| Lista ↔ ícones | ❌ Não existe | — |
| Pesquisa global | ✅ Full-text BM25 sobre o **conteúdo** das páginas | `GET /publicacoes/api/busca`, `search.py` |
| Visualizador integrado | ✅ PDF.js vendorizado, render em `<canvas>` | `viewer.html`, `publicacoes_viewer.js` |
| Navegação entre páginas + "X de Y" | ✅ Botões ‹ › e contador (contador não editável) | `publicacoes_viewer.js:82-84` |
| Download | ✅ | `viewer.html:30` |
| Miniaturas, zoom, ajustar largura/página, rotação, tela cheia, busca no PDF | ❌ Nenhum existe | — |
| Impressão | ❌ Não existe (e tem restrição — ver §3.4) | — |
| Responsividade / mobile | 🟡 Template mobile separado, sem árvore recolhível | `mobile/publicacoes.html` |
| Suportar milhares de documentos | ✅ Paginação server-side (`limit` ≤ 100) | `router.listar_documentos_do_manual:318` |

**Dimensão real do acervo** (`01_achados_do_acervo.md` §1, medido em 04–05/08/2026):
5.724 PDFs · 1,0 GB · 34 manuais · ~57.000 páginas · maior manual `AMM_PART2_1651` com **1.148 PDFs
em 51 capítulos**. Categorias vêm de `config/categorias_manuais.toml` (8 rótulos, `Outros` é
fallback).

---

## 2. Veredito item a item do prompt original

### 2.1 Viável, e o trabalho é só frontend (APIs já prontas)

| Item | Como se resolve | Endpoint que já serve |
|---|---|---|
| Barra lateral com árvore de pastas | Componente de árvore com carga preguiçosa por nó | `GET /api/manuais`, `GET /api/manuais/{codigo}/capitulos` |
| Área principal da pasta selecionada | Já é a tabela de `capitulo.html`, movida para dentro do layout | `GET /api/manuais/{codigo}/documentos` |
| Breadcrumb clicável completo | Categoria › Manual › Capítulo, todos navegáveis | dados já vêm nas respostas acima |
| Ícones pasta/PDF | SVG inline, como o resto do projeto | — |
| Expandir/recolher a árvore, manter pasta atual, voltar à raiz | Estado no cliente + `history.pushState` | — |
| Botões voltar/avançar | `history.back()`/`forward()` sobre as URLs já existentes | — |
| Alternância lista ↔ ícones | CSS, preferência em `localStorage` | — |
| Ordenação por nome | `sort_order` (default) ou título A–Z, ordenado no cliente dentro da página | — |
| Árvore vira drawer no mobile | Mesmo componente, `<dialog>`/painel deslizante | — |

### 2.2 Viável, mas exige backend novo

| Item | O que falta | Custo |
|---|---|---|
| **Pesquisa por nome de arquivo, nome de pasta e caminho** | O FTS indexa **texto de página**, não nomes. Buscar "AMM CHAPTER_21" hoje não acha o capítulo. Precisa de `GET /api/catalogo/busca` fazendo `ILIKE` em `manuais_documentos.titulo` / `.capitulo` / `.file_key` + `manuais.codigo` / `.descricao_pt`, escopado à edição vigente. | Baixo — 1 função de service + 1 endpoint + schema |
| **Resultado indicando o caminho completo** | Os dados existem (`manual.codigo` + `capitulo`), mas nem `ResultadoBusca` nem `DocumentoCatalogoItem` montam o path legível. | Trivial |
| **Ordenação por tamanho / data de modificação** | **Não existe no modelo.** `ManualDocumento` não tem `tamanho_bytes` nem `mtime` — só `created_at`/`updated_at` (data da indexação, não do arquivo) e `revisao_data`. Exige migration + coleta no indexador. | Médio — migration + `scripts/publicacoes/indexar.py` + reindexação de 5.724 arquivos |
| **Zoom, ajustar à largura, ajustar à página, rotação, tela cheia, campo "página X" editável** | Tudo é API do PDF.js já vendorizado (`getViewport({ scale, rotation })`, `requestFullscreen`). Nenhuma dependência nova, nenhuma mudança de CSP. | Médio — reescrita de `publicacoes_viewer.js` |
| **Miniaturas das páginas na lateral** | PDF.js renderiza a partir do **mesmo** `pdfDocumento` já carregado. ⚠️ Não fazer segundo `fetch` de `/doc/{id}/pdf`: essa rota chama `service.registrar_acesso` e um segundo fetch duplicaria a linha de auditoria. Renderizar sob demanda (`IntersectionObserver`) — um manual de 500 páginas não pode gerar 500 canvases de uma vez. | Médio |
| **Pesquisa de texto dentro do PDF** | Duas rotas: (a) `findController` do PDF.js, no cliente; (b) consultar `catalog.db`, que **já tem o texto por página indexado**, e devolver as páginas que casam. A opção (b) é mais barata, mais rápida e reaproveita `search.py` — mas precisa de um endpoint filtrando por `document_id`. Recomendo (b). | Médio |

### 2.3 Não se aplica ou precisa de outra forma

| Item do prompt | Por quê | O que fazer em vez disso |
|---|---|---|
| **"Crie o protótipo visual com dados fictícios realistas"** | Não é protótipo: é um módulo em produção, com 5.724 documentos reais, RBAC, auditoria de acesso e suíte de testes. Dado fictício aqui esconderia justamente os problemas de escala que importam. | Construir sobre o acervo real; validar com `AMM_PART2_1651` (o pior caso). |
| **Coluna "Tipo"** | 100% dos 5.724 arquivos são PDF (censo de extensões, `01_achados` §2). Coluna sempre igual. | Trocar por **ATA**, **Páginas** e **Revisão** — que variam e o mecânico usa. |
| **Duplo clique para abrir** | Não existe em touch, e é um antipadrão de acessibilidade (sem equivalente de teclado). | Clique simples abre (como hoje); `Enter` no item focado abre; setas navegam. |
| **Pastas de profundidade arbitrária** | O modelo é fixo: `Manual` → `capitulo` → `ManualDocumento`. E isso **casa com o disco**: a estrutura real medida é `<MANUAL>/<CAPÍTULO>/arquivo.PDF`, exatamente 2 níveis (`01_achados` §1.2). | Árvore de 3 níveis lógicos: **Categoria → Manual → Capítulo**. Não construir recursão genérica para uma profundidade que não existe. |
| **Um único explorador cobrindo tudo** | Há **dois acervos**. O A (manuais) tem árvore de diretórios; o B (avulsas: BO/BS/NPO/BT) são registros de banco com anexos no storage/R2 — não têm pasta, têm tipo/ano/status/aplicabilidade. | Explorador cobre o acervo A. Avulsas continuam em `/publicacoes/avulsas`, alcançáveis pela busca global e por um nó fixo na barra lateral. |
| **"Não transformar em dashboard"** | Concordo, e já é assim — mas note que `/publicacoes` hoje acumula busca + FIM + navegação numa página só. | A Etapa 3 é a oportunidade de separar: explorador na tela cheia, resolução de mensagem do FIM como painel lateral ou rota própria. |

---

## 3. Premissas do prompt que colidem com decisões travadas

Estas cinco não são detalhes de implementação — mudá-las mudaria o que o módulo garante.

### 3.1 ❌ "Novos PDFs no diretório aparecem automaticamente no sistema"

**Colide com:** RN-08 (edições) e ADR-004.

O catálogo **não** é lido do disco em runtime. Ele é gerado offline por
`python -m scripts.publicacoes.indexar --edicao <rotulo>`, que produz um `catalog.<rotulo>.db`
dedicado; a edição com `status = VIGENTE` no banco decide qual índice a busca abre
(`service.caminho_indice_vigente`). Ativar uma edição é ato deliberado de Admin
(`POST /api/edicoes/{id}/ativar`), com relatório de diff lido antes.

Isso existe para sustentar uma afirmação de auditoria: *"a pane de março seguiu o procedimento
vigente em março"* — daí `PublicacaoAcesso.edicao_id` e o snapshot do título. Um acervo que muda
sozinho ao copiar um arquivo numa pasta destrói essa garantia.

> **Decisão: manter como está.** O explorador navega o **catálogo da edição vigente**, não o
> sistema de arquivos. Onde o prompt diz "pasta", leia "nó do catálogo".
>
> A melhoria legítima nesta linha é de **feedback**, não de automatismo: mostrar no explorador
> qual edição está sendo navegada e quando o índice foi gerado — `GET /api/status` já devolve
> `edicao` e `atualizado_em`.

### 3.2 ❌ Visualizador em `iframe` / `embed` / `object`

**Colide com:** decisão D-F (`03_especificacao_tecnica.md` §4.4).

`X-Frame-Options: DENY` é global na aplicação e bloqueia qualquer elemento que crie um browsing
context, **mesmo same-origin** — confirmado como bug real em `panes_detalhe.js`
(`docs/backlog/revisor/achados_panes_iframe_pdf.md`). Já resolvido: o viewer usa `<canvas>` + PDF.js.

> **Decisão: manter.** Todo recurso novo do viewer é construído sobre o `<canvas>`.

### 3.3 ❌ Bibliotecas de UI vindas de CDN

**Colide com:** CSP `script-src 'self'`.

Nada de CDN — nem componente de árvore, nem ícones, nem fontes. O PDF.js está vendorizado em
`app/web/static/js/pdfjs/` justamente por isso, e o delta `worker-src 'self'` já foi negociado.

> **Decisão:** árvore, drawer e alternância de visualização em JS vanilla, no padrão do projeto
> (`apiFetch`/`escapeHtml`/`showToast` como globais de `app.js`).

### 3.4 🟡 "Impressão" não tem caminho bom

Sem `iframe`, não há como acionar o diálogo de impressão nativo do PDF. As opções reais:

1. **Baixar e imprimir no leitor do sistema** — funciona hoje, custo zero, é o que recomendo.
2. Renderizar todas as páginas em canvas e `window.print()` — inviável para um documento de 500
   páginas, e a qualidade de impressão de canvas é pior que a do PDF vetorial.

> **Decisão:** rotular o botão existente como **"Baixar / Imprimir"** e não construir impressão
> própria. Se a demanda for real, reabrir com número de uso.

### 3.5 🟡 Busca instantânea esbarra em rate limit

`GET /api/busca` tem `@limiter.limit("30/minute")`. Um campo de busca global que dispara a cada
tecla estoura isso em segundos e o usuário leva 429.

> **Decisão:** debounce ≥ 400 ms e busca só a partir de 3 caracteres. O endpoint novo de busca por
> **nome/caminho** (§2.2) consulta o banco principal, não o FTS — pode ter limite mais folgado, mas
> precisa de um, e a decisão do valor é da Etapa 3.

---

## 4. Proposta ajustada — Etapa 3: Explorador do Acervo

Sucessora natural da Etapa 2 de `09_plano_configuracoes.md` (que entregou as rotas de navegação).
A Etapa 2 resolveu **"é possível chegar ao documento"**; a Etapa 3 resolve **"é agradável e rápido
chegar ao documento"**.

### Tarefa 1 — Layout de explorador em `/publicacoes/acervo`

Rota nova, **sem remover** `/publicacoes/manuais/{codigo}[/{capitulo}]` — as URLs atuais são
compartilháveis e estão em uso; viram alvo de redirecionamento ou coexistem.

- Duas colunas: árvore à esquerda (Categoria → Manual → Capítulo), conteúdo à direita.
- Breadcrumb clicável no topo, com voltar/avançar/subir.
- Client-fetch via `apiFetch` sobre os 3 endpoints existentes — **e aqui a Etapa 3 realinha o
  módulo ao padrão do resto do app**, resolvendo a dívida "navegação renderizada direto do
  `service`" registrada em `08_status_de_implementacao.md`.
- Carga preguiçosa por nó: expandir um manual busca seus capítulos; expandir um capítulo busca a
  primeira página de documentos. Nunca carregar os 5.724 de uma vez.
- CSS em arquivo próprio (`app/web/static/css/publicacoes_acervo.css`), não inline — é a primeira
  tela do módulo que não cabe em `style=""`.

### Tarefa 2 — Busca por nome e caminho

`GET /publicacoes/api/catalogo/busca?q=` — casa contra título, capítulo, `file_key`, código e
descrição do manual, escopado à edição vigente. Resultados exibem **o caminho completo**
(`Manutenção › AMM_PART1_1651 › CHAPTER_21`) e abrem o documento no viewer.

Complementa, não substitui, o FTS: a caixa do explorador oferece as duas modalidades
("por nome" / "no conteúdo"), com "no conteúdo" reusando `/api/busca` intacto.

### Tarefa 3 — Viewer completo

Sobre o `<canvas>` e o PDF.js já presentes:
zoom (±, %), ajustar à largura, ajustar à página, rotação, tela cheia, campo de página editável,
miniaturas laterais sob demanda (`IntersectionObserver`), e busca de texto **dentro do documento**
via `catalog.db` (endpoint filtrando por `document_id`).

Barra de ferramentas discreta, que recolhe — a exigência do prompt de "não competir visualmente com
o documento" é correta e vale manter.

### Tarefa 4 — Mobile

Árvore vira drawer lateral; conteúdo e viewer ocupam a largura toda; alvos de toque ≥ 44 px (padrão
já seguido em `mobile/publicacoes.html`).

### Tarefa 5 (opcional, decidir antes de começar) — Tamanho e data

Migration adicionando `tamanho_bytes` e `mtime_arquivo` a `manuais_documentos`, coleta no indexador,
reindexação. **Só fazer se alguém realmente ordenar por isso** — para manual técnico, "tamanho do
arquivo" raramente é critério de busca; ATA e revisão são.

---

## 5. Riscos

| Risco | Mitigação |
|---|---|
| Árvore travar em `AMM_PART2_1651` (1.148 PDFs, 51 capítulos) | Carga preguiçosa + paginação já existente; **medir com esse manual antes de fechar a etapa** — é o pior caso real, não hipotético |
| Miniaturas duplicarem linhas de auditoria | Renderizar do `pdfDocumento` já carregado; nunca refazer `fetch` em `/doc/{id}/pdf` |
| Busca instantânea gerar 429 | Debounce e mínimo de caracteres (§3.5) |
| Reescrever o viewer quebrar o que funciona | Os testes atuais cobrem ids do template batendo com o JS; ampliar antes de mexer |
| Etapa 3 herdar a dívida de verificação visual | Esta etapa **precisa** de navegador real — todo o módulo já acumula essa dívida desde o M1 (ver `08`) |

---

## 6. Gate de saída sugerido

1. Explorador abre e navega os 34 manuais sem recarregar a página.
2. `AMM_PART2_1651` expande e pagina sem travar (medido, não impressionístico).
3. Busca por nome acha um capítulo por nome de pasta; busca por conteúdo continua idêntica.
4. Viewer com zoom, rotação, tela cheia, miniaturas e busca interna, aberto num navegador real com
   **console limpo de violações de CSP** (`docs/methodology/CSP.md` §5).
5. Mobile: drawer abre/fecha, documento legível sem zoom horizontal.
6. Nenhuma linha extra em `publicacoes_acessos` por abrir o viewer uma vez.

---

## 7. Onde este documento se encaixa

- **Não substitui** `03_especificacao_tecnica.md` (contrato) nem `08_status_de_implementacao.md`
  (progresso). Se a Etapa 3 for aprovada, ela entra como seção nova em `09_plano_configuracoes.md`
  e as tarefas passam a ser rastreadas no `08`.
- **Não altera** nenhuma decisão do ADR-004. As colisões da §3 foram resolvidas a favor das
  decisões existentes.
- **Status:** proposta. Nada aqui foi implementado.
