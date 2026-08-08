# Plano de Implementação — Prévia do Explorador em Paralelo à UI Atual

> **Pergunta que originou este plano:** *"é possível criar uma janela/menu temporária para
> visualização de como ficaria o módulo nessa formatação, rodando as duas formatações
> simultaneamente para testes e verificação local?"*
>
> **Resposta: sim.** Mesmo app, mesmo processo, mesmo banco, mesma sessão de login, mesmos dados
> reais. Um link alterna entre as duas. Nenhum segundo servidor, nenhuma cópia de dados, nenhum
> fixture fictício.
>
> **Escopo deste documento:** o mecanismo de convivência e o plano de execução da prévia. O conteúdo
> funcional do explorador (o que ele mostra e por quê) está em
> [`melhorias.md`](melhorias.md) — este documento não o repete.
>
> **Status: PROMOVIDO.** O desenvolvedor testou a prévia manualmente (Fases 0–3) e decidiu adotá-la
> — "prefiro muito mais essa versão, quero usar essa nova visualização no projeto". `/publicacoes` e
> `/publicacoes/viewer/{doc_id}` **são**, hoje, o explorador e o viewer avançado — não uma prévia
> paralela. A flag `publicacoes_preview_explorador` foi removida, o router temporário
> (`publicacoes_preview_router.py`) foi apagado, e os arquivos `preview/`/`_preview_` foram
> renomeados para seus nomes definitivos. §8 registra o que a promoção mudou em relação ao plano
> original — este documento vira registro datado a partir daqui; o corpo abaixo (§1–7) descreve o
> mecanismo **como ele existiu durante a avaliação**, não o estado atual do código.
>
> A decisão veio do uso direto, não do roteiro comparativo formal do §4 — não há artefato do "gate
> de decisão" além do julgamento do desenvolvedor. Registrado para quem ler isto depois perguntando
> "cadê a comparação das 7 tarefas".

---

## 1. Como as duas versões convivem

### 1.1 Estratégia escolhida: rota paralela + flag de ambiente

| Estratégia | Veredito |
|---|---|
| **A. Rota paralela `/publicacoes/acervo`, arquivos novos, flag de ambiente** | ✅ **Escolhida** — isolamento total; descartar a perdedora é `git rm` de uma lista fechada de arquivos |
| B. Mesma rota com `?ui=explorador` ramificando o template | ❌ Mistura as duas UIs no mesmo handler; a remoção vira edição cirúrgica em código compartilhado |
| C. Branch git separada | ❌ Não atende ao pedido — não é possível comparar as duas lado a lado se só uma roda por vez |

### 1.2 O que a prévia compartilha com a UI atual

Compartilha **tudo que é backend**:

- Os mesmos endpoints (`GET /publicacoes/api/manuais`, `.../capitulos`, `.../documentos`,
  `/api/busca`, `/api/status`, `/doc/{id}/pdf`).
- O mesmo `service.py`, o mesmo `catalog.<rotulo>.db`, a mesma edição vigente.
- O mesmo RBAC (`get_current_user`) e a mesma auditoria (`publicacoes_acessos`).

**Nenhuma lógica de negócio é duplicada.** A prévia é HTML + CSS + JS sobre APIs que já existem. É
o que torna a comparação honesta — as duas telas leem exatamente o mesmo acervo, no mesmo instante.

### 1.3 A flag

Nova entrada em `app/bootstrap/config/__init__.py`, no bloco `--- Módulo Publicações ---`:

```python
publicacoes_preview_explorador: bool = Field(
    default=False,
    description=(
        "Liga a PRÉVIA do explorador do acervo em /publicacoes/acervo, para "
        "avaliação lado a lado com a UI atual. Temporária: sai do código quando "
        "a decisão de 10_plano_preview_explorador.md for tomada."
    ),
)
```

**Comportamento:** flag desligada → as rotas da prévia respondem **404**, não 403. Um 403 confirmaria
que a rota existe; 404 é o padrão correto para funcionalidade que não deve ser descoberta.

**Por que gate único, e não o duplo de `enable_test_users`?** O precedente
(`auth/service.py:375`, `app_env == "development" AND enable_test_users`) existe porque aquela flag
**cria três contas privilegiadas com senha trivial** — ligá-la por engano em produção é incidente de
segurança. Esta flag só renderiza HTML diferente sobre APIs já autenticadas e já cobertas por RBAC:
o pior caso de ligá-la por engano é um usuário ver uma tela experimental. Exigir
`app_env == "development"` também impediria avaliar a prévia numa instância de homologação, que é
onde a comparação tem mais valor.

> Se a prévia for exposta numa instância compartilhada com usuários reais, aí sim vale restringir a
> `AdminRequired` — mas isso muda o que se está medindo (a UX de quem vai usar o sistema é a do
> mecânico, não a do Admin). Decidir na hora, não agora.

### 1.4 Como o usuário alterna entre as duas

Três pontos de entrada, todos condicionados à flag:

1. **Faixa no topo de `/publicacoes`** (UI atual): `Experimentar o novo explorador →`.
2. **Faixa no topo de `/publicacoes/acervo`** (prévia): `⚗ PRÉVIA — em avaliação · Voltar à versão
   atual`. Sempre visível, com contraste próprio, para que ninguém confunda prévia com produto.
3. **Preferência não é lembrada.** Nada de `localStorage` escolhendo a UI de entrada: durante a
   avaliação, `/publicacoes` deve continuar abrindo a versão atual, sempre. Uma preferência
   persistida faria metade dos testes acontecerem na tela errada sem ninguém notar.

---

## 2. Inventário de arquivos

### 2.1 Arquivos NOVOS (todos descartáveis em bloco)

```
app/web/pages/publicacoes_preview_router.py        # router próprio, não misturado ao pages/router.py
app/web/templates/publicacoes/preview/acervo.html  # tela do explorador
app/web/templates/publicacoes/preview/viewer.html  # viewer avançado (rota própria — ver §3.4)
app/web/templates/publicacoes/preview/_faixa.html  # a faixa "PRÉVIA", incluída pelas duas
app/web/static/css/publicacoes_preview.css
app/web/static/js/publicacoes_preview_acervo.js
app/web/static/js/publicacoes_preview_viewer.js
tests/unit/test_publicacoes_preview.py
```

Subdiretório `preview/` e prefixo `publicacoes_preview_` não são estética: são o que permite que a
remoção seja `git rm -r` de dois diretórios e três arquivos, sem varredura manual.

### 2.2 Arquivos EXISTENTES tocados — e só estes

| Arquivo | Mudança | Linhas (ordem de grandeza) |
|---|---|---|
| `app/bootstrap/config/__init__.py` | 1 campo `Field` | ~8 |
| `app/bootstrap/main.py` | 1 `import` + 1 `include_router` condicional | ~3 |
| `app/web/templates/publicacoes/lista.html` | bloco `{% if preview_explorador %}` com o link | ~4 |
| `app/web/pages/router.py` | passar `preview_explorador` no contexto de `publicacoes_lista_page` | ~2 |
| `.env.example` | a variável documentada, comentada | ~2 |

**~19 linhas em 5 arquivos.** Se a prévia for descartada, é o total do que precisa ser revertido
fora dos arquivos novos.

### 2.3 O que NÃO é tocado

`app/modules/publicacoes/*` inteiro (service, router, models, schemas, search, catalog, avulsas),
`publicacoes/viewer.html`, `manual.html`, `capitulo.html`, `mobile/publicacoes.html`,
`publicacoes.js`, `publicacoes_viewer.js`.

**Exceção deliberada, na Fase 2:** o endpoint de busca por nome/caminho
(`GET /publicacoes/api/catalogo/busca`, §2.2 de `melhorias.md`) entra em `router.py`/`service.py`.
É **aditivo e útil independentemente da decisão** — se a prévia for descartada, o endpoint fica e
passa a servir a UI atual. Por isso ele é a única parte do backend que a prévia adiciona, e por isso
ele **não** leva prefixo `preview`.

### 2.4 Ordem de rotas

`/publicacoes/acervo` é segmento literal — não colide com `/publicacoes/manuais/{codigo}` nem com
`/publicacoes/viewer/{doc_id}`, e o cuidado de ordenação registrado em `pages/router.py:130` não se
aplica. Ainda assim, o router da prévia é registrado **antes** de `pages_router` em
`app/bootstrap/main.py`, seguindo a ordem que o arquivo já usa.

---

## 3. Fases

### Fase 0 — O mecanismo, provado vazio (meio dia)

Flag, router, rota `/publicacoes/acervo` renderizando só a faixa "PRÉVIA" e o link de volta; link de
ida em `/publicacoes`.

**Critério de pronto:** com a flag ligada, alterna-se entre as duas telas sem perder a sessão; com a
flag desligada, `/publicacoes/acervo` devolve 404 e `/publicacoes` fica idêntica a hoje (nem o link
aparece).

Fase de valor desproporcional ao tamanho: prova que a convivência funciona **antes** de qualquer
investimento em UI.

### Fase 1 — Explorador navegável

Layout de duas colunas, árvore Categoria → Manual → Capítulo com carga preguiçosa, breadcrumb
clicável, painel de conteúdo, alternância lista/ícones, voltar/avançar por `history`.
Client-fetch puro via `apiFetch`, sobre os 3 endpoints existentes.

**Critério de pronto:** os 34 manuais navegáveis sem recarga de página; `AMM_PART2_1651`
(1.148 PDFs / 51 capítulos) expande e pagina sem travar — **medido**, não impressionístico.

### Fase 2 — Busca por nome e caminho

Endpoint `GET /publicacoes/api/catalogo/busca` (aditivo, sem prefixo `preview` — ver §2.3) +
consumo na caixa do explorador, com as duas modalidades ("por nome" / "no conteúdo").

⚠️ Debounce ≥ 400 ms e mínimo de 3 caracteres. `GET /api/busca` tem `@limiter.limit("30/minute")`:
busca a cada tecla gera 429 em segundos.

### Fase 3 — Viewer avançado, em rota própria

`/publicacoes/acervo/viewer/{doc_id}`, template e JS próprios. **O viewer atual não é modificado** —
é o que permite comparar os dois e descartar um sem risco.

Zoom, ajustar à largura/página, rotação, tela cheia, campo de página editável, miniaturas sob demanda
(`IntersectionObserver`), busca de texto no documento via `catalog.db`.

Duas restrições que não mudam: **`<canvas>`, nunca iframe/embed/object** (`X-Frame-Options: DENY`
é global, decisão D-F) e **nada de CDN** (CSP `script-src 'self'` — o PDF.js vendorizado é o único
motor disponível, e basta).

⚠️ Miniaturas renderizam do `pdfDocumento` **já carregado**. Um segundo `fetch` em `/doc/{id}/pdf`
dispara `service.registrar_acesso` de novo e duplica a linha de auditoria.

### Fase 4 — Mobile

Árvore como drawer, viewer em largura total, alvos de toque ≥ 44 px. Rota `/m/publicacoes/acervo`
sob a mesma flag. `mobile/publicacoes.html` permanece intacto.

---

## 4. Gate de decisão

A prévia não é entregável: existe para produzir uma decisão. Este é o critério.

### 4.1 Roteiro de comparação

Executar **a mesma tarefa nas duas UIs**, cronometrando e contando cliques:

| # | Tarefa | O que mede |
|---|---|---|
| 1 | Chegar a um documento conhecido (`AMM_PART1_1651` › `CHAPTER_21` › primeiro doc) | Navegação dirigida |
| 2 | Descobrir o que existe sobre ATA 36 sem saber o código do manual | Navegação exploratória |
| 3 | Achar um trecho por texto ("sangria do compressor") e abrir na página certa | Busca por conteúdo |
| 4 | Achar um capítulo pelo nome da pasta | Busca por nome (só a prévia tem) |
| 5 | Ler um procedimento de 40 páginas de ponta a ponta | Ergonomia do viewer |
| 6 | Tarefas 1 e 3 no celular | Mobile |
| 7 | Abrir `AMM_PART2_1651` inteiro | Escala — o pior caso real |

### 4.2 Critérios de aprovação da prévia

Para substituir a UI atual, a prévia precisa, **cumulativamente**:

1. Não perder em nenhuma das 7 tarefas (tempo ou cliques).
2. Ganhar claramente em pelo menos 3.
3. Console limpo de violações de CSP em navegador real (`docs/methodology/CSP.md` §5).
4. Nenhuma linha extra em `publicacoes_acessos` por abrir um documento uma vez.
5. Funcionar no celular sem zoom horizontal.
6. Preservar as URLs compartilháveis existentes (redirecionamento, se mudar).

### 4.3 Os três desfechos possíveis

| Desfecho | O que acontece |
|---|---|
| **Prévia aprovada** | Promoção: `preview/` sai do nome dos arquivos, a flag some, a UI atual é removida, `/publicacoes/manuais/...` redireciona para o explorador. Novo documento de status no `08`. |
| **Prévia rejeitada** | `git rm -r app/web/templates/publicacoes/preview/` + os 5 arquivos estáticos/router/teste, e reverter as ~19 linhas da §2.2. **O endpoint de busca por nome fica** e passa a servir a UI atual. |
| **Aproveitamento parcial** | O mais provável. Itens isolados (viewer com zoom/miniaturas, busca por nome, breadcrumb clicável) migram para a UI atual; o layout de explorador é descartado. Cada item vira tarefa no `08`. |

### 4.4 Prazo de validade

**A flag é temporária e precisa de data.** Uma flag de prévia sem prazo vira código morto
permanente, e este módulo já carrega dívida de verificação visual desde o M1.

Proposta: **a decisão sai em até 30 dias corridos após a Fase 3 ficar pronta.** Sem decisão no
prazo, o desfecho padrão é "rejeitada" (§4.3) — remoção é mais barata que manter dois caminhos vivos
indefinidamente.

---

## 5. Riscos do arranjo de prévia

| Risco | Mitigação |
|---|---|
| **Auditoria inflada** — as duas UIs registram acesso em `publicacoes_acessos` durante a avaliação | É acesso real de usuário real; não filtrar nem falsear. Registrar a janela de avaliação no `08` para quem for ler o histórico depois entender o pico |
| **Flag ligada por engano em produção** | Default `False`; teste que afirma o default e que a rota devolve 404 com a flag desligada |
| **Prévia vira permanente** | Prazo de validade explícito (§4.4) e lista de remoção fechada (§2.1) |
| **Divergência de comportamento** entre as duas | Backend 100% compartilhado (§1.2) — divergência só pode ser de apresentação, que é justamente o que se quer comparar |
| **Prévia sem testes contamina a suíte** | `tests/unit/test_publicacoes_preview.py` cobre só o essencial: flag off → 404, flag on → 200 autenticado, ids do template batendo com os que o JS busca. O padrão de rigor da UI definitiva só se aplica se ela vencer |
| **Comparar duas telas sem nenhuma ter sido vista em navegador** | A UI atual **nunca foi aberta em navegador real** (dívida do `08`). Antes de comparar, abrir as telas atuais e registrar o que se vê — senão a comparação é contra uma tela imaginada |

---

## 6. Custo estimado

| Fase | Escopo | Esforço |
|---|---|---|
| 0 | Flag, router, faixa, alternância | ~0,5 dia |
| 1 | Explorador navegável | ~2 dias |
| 2 | Busca por nome (endpoint + UI) | ~1 dia |
| 3 | Viewer avançado | ~2–3 dias |
| 4 | Mobile | ~1 dia |
| — | Avaliação e decisão (§4) | ~0,5 dia |

**Total: ~7–8 dias.** As Fases 0 e 1 (~2,5 dias) já entregam material suficiente para uma decisão
preliminar sobre o layout — vale pausar ali e conferir antes de investir nas Fases 3 e 4, que são a
maior parte do custo.

---

## 7. Encaixe na documentação

- Complementa `melhorias.md` (o **quê**); este é o **como conviver e como decidir**.
- Não altera `03_especificacao_tecnica.md` nem o ADR-004. Nenhuma decisão travada é revista: as
  restrições de canvas (D-F), CSP, edição vigente (RN-08/ADR-004) e RBAC valem igual na prévia.
- As fases são rastreadas em `08_status_de_implementacao.md` — ver a seção "Prévia do explorador do
  acervo" lá para o estado tarefa a tarefa.
- Quando a decisão sair, este documento vira registro datado — como `04` e `07` — e não é reescrito.

---

## 8. Estado real após a implementação das Fases 0–3

**Executado numa única rodada, sem pausa entre fases** — decisão do desenvolvedor ("implemente
direto até a fase 3"), não a pausa preliminar sugerida em §6. Fase 4 (mobile) ficou de fora por
instrução explícita do mesmo pedido — não é lacuna, é escopo.

### 8.1 O que existe

| Item | Onde |
|---|---|
| Flag `publicacoes_preview_explorador` | `app/bootstrap/config/__init__.py` |
| Router da prévia (`/publicacoes/acervo`, `/publicacoes/acervo/viewer/{doc_id}`) | `app/web/pages/publicacoes_preview_router.py` |
| Templates | `app/web/templates/publicacoes/preview/{_faixa,acervo,viewer}.html` |
| CSS (layout de duas colunas, árvore, cards, toolbar do viewer2, miniaturas) | `app/web/static/css/publicacoes_preview.css` |
| JS do explorador (árvore, breadcrumb, histórico, lista/ícones, ordenar, busca) | `app/web/static/js/publicacoes_preview_acervo.js` |
| JS do viewer avançado (zoom, ajuste, rotação, tela cheia, miniaturas, busca no documento, favoritos) | `app/web/static/js/publicacoes_preview_viewer.js` |
| Endpoint aditivo de busca por nome/caminho | `GET /publicacoes/api/catalogo/busca` (`router.py`, `service.buscar_no_catalogo`) |
| Filtro `documento_id` na busca por conteúdo | `GET /publicacoes/api/busca?documento_id=` (`search.py`, `router.py`) |
| Testes novos | `tests/unit/test_publicacoes_preview.py` (rotas), `tests/unit/test_publicacoes_catalogo_busca.py` (busca por nome), 2 testes em `tests/integration/test_publicacoes_busca.py` (filtro por documento) |

**279 testes de publicações passam** (era 66 no início desta iniciativa); suíte completa do projeto
em 658, todos verdes. `ruff check app/` limpo.

### 8.2 O que foi verificado em navegador real (não só testado)

Sessão completa em Chrome headless via CDP, autenticado, contra o acervo real (34 manuais, 5.724
documentos, edição `2026` vigente):

1. Árvore expande Categoria → Manual → Capítulo; **`AMM_PART2_1651` (o pior caso: 1.148 documentos,
   51 capítulos) abre sem travar** — os 51 capítulos aparecem na árvore e como cards no painel.
2. Seleção de capítulo carrega documentos paginados; troca lista ↔ ícones sem recarregar.
3. Busca "por nome" acha capítulo pelo nome da pasta (`CHAPTER_21`) — o caso que o FTS de conteúdo
   não cobre.
4. Busca "no conteúdo" devolve snippet com `<mark>` real, reaproveitando `/api/busca` sem mudança de
   comportamento.
5. Botão "voltar" navega pelo histórico do navegador corretamente.
6. Abrir um documento por clique real (não link direto) leva ao viewer avançado com `#page=1`.
7. Viewer avançado: zoom manual (+/− chegou a 259%), "ajustar à página" recalcula o fit, rotação
   90° gira a página, miniaturas renderizam com conteúdo real (mesmo `pdfDocumento`, sem novo
   `fetch`), busca dentro do documento devolve página e trecho, favoritar/desfavoritar alterna o
   ícone.
8. **Console sem uma única violação de CSP ou erro em nenhum dos dois temas**, em nenhuma das telas.

### 8.3 Ajustes ao design original durante a implementação

- **Cards de pasta em todo nível, não só documentos.** O design original prendia o painel de
  conteúdo aos 3 níveis descritos em §Tarefa 1; na implementação, o painel também mostra as
  **categorias** como cards na raiz (`/publicacoes/acervo` sem parâmetro) — ganho de simetria, sem
  custo (os dados já estavam em memória).
- **Endpoint de busca por documento reaproveita `/api/busca`** em vez de um endpoint novo dedicado:
  um parâmetro `documento_id` opcional em cima da rota já existente, mais barato que duplicar o
  contrato de resposta.
- **Miniaturas com `IntersectionObserver`** — confirmado renderizando só o necessário (2 miniaturas
  de um documento de 2 páginas, ambas visíveis; comportamento sob demanda não pôde ser diferenciado
  neste teste específico por o documento ser curto — o mecanismo é o mesmo independente do tamanho).

### 8.4 O que faltava antes da promoção (histórico — ver §8.5)

- **Fase 4 (mobile)** — não iniciada, por decisão explícita. **Ainda não iniciada** — a promoção não
  mudou isto; mobile continua na experiência própria de `mobile/publicacoes.html`.
- **Gate de decisão (§4)** — o roteiro de 7 tarefas comparativas **não foi executado formalmente**.
  A decisão veio do uso direto pelo desenvolvedor, registrado no topo deste documento.
- ~~Prazo de validade (§4.4)~~ — sem objeto: a prévia foi promovida antes de qualquer prazo vencer.

### 8.5 Promoção — o que mudou entre "prévia sob flag" e "versão definitiva"

Executada na mesma sessão, imediatamente após o desenvolvedor aprovar. Cada arquivo de §8.1
(coluna "Onde") foi tocado; a tabela abaixo é o de-para.

| Antes (prévia) | Depois (definitivo) |
|---|---|
| Flag `publicacoes_preview_explorador` (`Settings`) | **Removida** — sem flag, sem gate, sempre ativo |
| `app/web/pages/publicacoes_preview_router.py` | **Apagado** — as duas rotas viraram os handlers de `/publicacoes` e `/publicacoes/viewer/{doc_id}` em `app/web/pages/router.py` |
| `/publicacoes/acervo` | `/publicacoes` (a home antiga — busca+FIM renderizados por `service` — foi substituída) |
| `/publicacoes/acervo/viewer/{doc_id}` | `/publicacoes/viewer/{doc_id}` (o viewer clássico simples — foi substituído) |
| `app/web/templates/publicacoes/preview/{acervo,viewer,_faixa}.html` | `_faixa.html` apagado (sem mais alternância de UI); conteúdo de `acervo.html`/`viewer.html` movido para `app/web/templates/publicacoes/{lista,viewer}.html` |
| `app/web/static/css/publicacoes_preview.css` | `app/web/static/css/publicacoes.css` — regras `.pub-preview-faixa*` removidas, `.pub-viewer2-*` renomeado para `.pub-viewer-*` |
| `app/web/static/js/publicacoes_preview_acervo.js` | `app/web/static/js/publicacoes_explorador.js` |
| `app/web/static/js/publicacoes_preview_viewer.js` | conteúdo movido para `app/web/static/js/publicacoes_viewer.js` (substituiu o viewer clássico ali); ids `pub-viewer2-*` renomeados para `pub-viewer-*` |
| `tests/unit/test_publicacoes_preview.py` (testava a flag) | Apagado — os testes de id/contrato que sobreviveram foram incorporados em `test_pagina_lista_retorna_200_autenticado`/`test_pagina_viewer_retorna_200_autenticado` (`tests/integration/test_publicacoes_busca.py`) |

**Duas lacunas fechadas na promoção, não previstas no design original das Fases 1–3** — a home
antiga (`lista.html`) tinha duas capacidades que o explorador, como desenhado, não cobria:

1. **Resolução de mensagem do FIM** (CAS/EICAS → procedimento) — sem isso, promover o explorador
   sem mais nada teria **removido** uma ferramenta operacional real. Virou um `<details>`
   recolhível na sidebar (`GET /api/fim`, mesmo endpoint de sempre).
2. **`?q=` como contrato de deep link** — `app/web/static/js/inspecao_detalhe.js` linka
   `/publicacoes?q=<título do item>` para o checklist de inspeção "buscar no manual" (M3). O
   explorador agora lê `?q=` no load e dispara a busca "no conteúdo" automaticamente, preservando o
   contrato sem o outro lado (`inspecao_detalhe.js`) precisar mudar.

`/publicacoes/manuais/{codigo}[/{capitulo}]` (`manual.html`/`capitulo.html`) **não foram tocadas** —
continuam servindo `mobile/publicacoes.html`, que ainda não tem o explorador (Fase 4).

**Verificação pós-promoção** (Chrome real, sem flag): `/publicacoes/acervo` devolve 404 (rota
antiga não existe mais); `/publicacoes` mostra o explorador com o link de avulsas e o resolvedor
FIM, sem faixa; abrir um documento pela árvore leva a `/publicacoes/viewer/{id}` (não mais
`/acervo/viewer/`); `/publicacoes?q=sangria` dispara a busca automaticamente; `/m/publicacoes` e o
link para `/publicacoes/manuais/{codigo}` continuam idênticos. Console limpo em todas as telas.
**650 testes passam** (658 antes da promoção → 650 depois: saiu `test_publicacoes_preview.py`
inteiro — a flag que ele testava não existe mais —, saiu um teste obsoleto de SSR da home antiga em
`test_publicacoes_navegacao.py`, e entraram testes novos de id/contrato e do deep link `?q=` em
`test_publicacoes_busca.py`). `ruff check app/` limpo.
