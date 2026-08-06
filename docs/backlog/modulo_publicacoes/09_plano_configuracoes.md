# Plano — Gerência de Publicações em `/configuracoes` (M4 tarefa 4)

> **Contexto:** `08_status_de_implementacao.md` fecha o M4 em 6/8 e registra a tarefa 4 como
> não implementada por uma lacuna arquitetural concreta — não existe `catalog.db` por edição, então
> "ativar edição" mudaria o status no banco sem mudar o que a busca devolve. Este plano resolve
> primeiro essa lacuna e só então constrói a tela.
>
> **Escopo:** um card "Publicações" em `/configuracoes`, na estética já definida da página
> (card com tile de ícone + descrição + botões empilhados; modais `glass-panel` com tabela).
> Não muda nada da busca, do viewer nem das avulsas para o usuário final.

---

## 1. O problema real, em uma frase

`GET /publicacoes/api/busca` lê **um** arquivo fixo — `settings.publicacoes_index_path`
(`var/publicacoes/catalog.db`) — que `indexar.py`/`publicar.py` sobrescrevem a cada publicação.
Não há "índice da edição 2026" e "índice da edição 2025" coexistindo. Sem isso, ativar é teatro.

O desenho original (`search.py`, regra 2 do docstring) previa resolver isso com `os.replace()`:
o índice novo entra no lugar do antigo por troca atômica de arquivo. **Este plano propõe uma
solução diferente e melhor**, justificada na Fase 0.

---

## Fase 0 — `catalog.db` por edição (pré-requisito, não opcional) ✅ **IMPLEMENTADA**

> **Estado:** concluída. Decisão registrada no adendo do
> [ADR-004](../../architecture/adr/004-modulo-publicacoes.md). Custo medido: 1,0 ms mediana /
> 1,2 ms p95 por busca (200 amostras). 18 testes novos; suíte em 593 passando, ruff limpo.
> O que segue descreve o que foi construído — as divergências em relação ao plano original
> estão anotadas no fim da fase.

### Decisão: resolver o caminho pelo banco, não trocar arquivos

Cada edição passa a ter seu próprio arquivo, nomeado pelo rótulo:

```
var/publicacoes/
├── catalog.2026.db          ← edição "2026"
├── catalog.piloto-fim.db    ← edição "piloto-fim"
└── catalog.db               ← legado, usado só como fallback (ver compatibilidade)
```

E **o índice vigente é descoberto por consulta**, não por qual arquivo está num caminho fixo:

```python
# service.py
def caminho_indice_da_edicao(rotulo: str) -> Path: ...
async def caminho_indice_vigente(db) -> Path: ...   # lê manuais_edicoes WHERE status=VIGENTE
```

O router (que já tem `db` na assinatura) resolve o caminho e passa para `search.buscar(caminho, ...)`.
`search.py` continua sem saber o que é uma edição — recebe um `Path` e abre, exatamente como hoje.

**Por que isso em vez do `os.replace()` previsto originalmente:**

| | `os.replace()` | Resolver pelo banco |
|---|---|---|
| Ativar | move/copia arquivo de centenas de MB | um `UPDATE` dentro de uma transação |
| Reverter | precisa do arquivo antigo ainda existir e mover de volta | outro `UPDATE`, instantâneo |
| Atomicidade | atômica no FS, mas o status no banco e o arquivo mudam em momentos diferentes → janela de inconsistência | status **é** a fonte da verdade; não há dois lugares para divergir |
| Windows (ambiente de dev deste projeto) | `os.replace` sobre arquivo com handle aberto falha; symlink exige privilégio | irrelevante |
| Custo em runtime | zero | uma consulta indexada por busca (~1 ms sobre um p95 medido de 6,7 ms) |

O custo de uma consulta a mais por busca é real e deve ser medido, não presumido — ver o item de
verificação na Fase 3. Se incomodar, o alvo natural é um cache com TTL curto no `service`,
invalidado na ativação; **não** implementar o cache de saída, para não otimizar antes de medir.

A regra 2 do docstring de `search.py` ("uma conexão por consulta, nunca cacheada") continua válida e
fica **mais** importante, não menos: é ela que garante que a busca seguinte à ativação já abre o
arquivo novo. O parágrafo que justifica a regra pelo `os.replace()` precisa ser reescrito para
justificá-la pela troca de caminho.

### Passos

1. **`service.caminho_indice_da_edicao(rotulo)`** — deriva `catalog.<rotulo>.db` a partir do diretório
   de `settings.publicacoes_index_path`.
   **Sanitizar o rótulo** (`^[A-Za-z0-9._-]{1,20}$`, rejeitando o resto): `rotulo` vem do banco, mas
   é texto livre de 20 caracteres criado por script — um rótulo `../../algo` não pode virar leitura
   de arquivo arbitrário. Mesma postura defensiva de `_resolver_pdf` no router.
2. **`service.caminho_indice_vigente(db)`** — reusa `obter_edicao_vigente`, já existente.
3. **`indexar.py`** — quando `--indice` não for passado explicitamente, gravar em
   `catalog.<rotulo>.db` derivado de `--edicao`, em vez do caminho fixo.
4. **`publicar.py`** — passar o `--indice` correspondente à edição sendo publicada (hoje deixa o
   padrão). Isso é o que faz uma publicação **não** destruir o índice da edição vigente — hoje ela
   destrói, e é esse o motivo de a publicação atual só ser segura porque nada depende do índice antigo.
5. **Router** — `buscar` e `status_publicacoes` passam a resolver o caminho pelo banco.
6. **Compatibilidade** — se `catalog.<rotulo>.db` não existir mas o `catalog.db` legado existir,
   usar o legado e logar um aviso. Instalações que não reindexaram continuam funcionando; quem
   reindexar migra sozinho. Sem migration formal — o índice é descartável por ADR-004.

### Documentação da Fase 0

- **Amendar `docs/architecture/adr/004-modulo-publicacoes.md`** com uma seção "Resolução do índice
  por edição", registrando a decisão e o motivo de ela substituir o `os.replace()` previsto.
  É uma reversão de decisão registrada, não um detalhe de implementação — merece ficar no ADR.
- Reescrever a regra 2 do docstring de `search.py`.

### O que a execução mudou em relação ao planejado

- **`resolver_caminho_indice` ficou síncrona e separada de `caminho_indice_vigente`.** O plano
  falava de uma função só; na prática o teste de existência do arquivo toca o disco, o que a regra
  ASYNC do ruff proíbe dentro de `async def`. A divisão (pura → síncrona com disco → assíncrona com
  banco) saiu de graça e deixou as duas primeiras testáveis sem banco nenhum.
- **`publicar.py` não passa `--indice`.** O plano previa passar explicitamente; deixar o default do
  indexador derivar de `--edicao` mantém a regra num lugar só. Um caminho explícito ali seria uma
  segunda cópia da regra, no arquivo onde esquecê-la custa caro.
- **`abrir_catalog_novo` manteve o `os.replace`.** Ele não some: continua sendo o commit atômico da
  *própria indexação* (nunca deixar a busca ver um índice pela metade). O que a Fase 0 removeu foi o
  uso dele como mecanismo de *ativação*. O docstring foi corrigido para não confundir os dois.
- **A fixture de teste passou a gravar `catalog.<EDICAO>.db`.** Manter `catalog.db` faria a suíte
  passar pela queda de compatibilidade em vez do caminho real — verde enganoso.
- **Verificação por mutação.** O teste que sustenta a fase foi confirmado quebrando de propósito a
  resolução (fixando o rótulo) e conferindo que ele falha. Sem isso, "593 passando" não diria nada
  sobre esta mudança em específico.

---

## Fase 1 — Endpoints de gerência ✅ **IMPLEMENTADA**

> **Estado:** concluída. 21 testes em `tests/unit/test_publicacoes_edicoes.py`; suíte em 614
> passando, `ruff check .` limpo. Migration `c4e7a91d2b58` verificada nos dois ramos (com e sem
> edição vigente duplicada) contra uma cópia do banco real, incluindo `downgrade`.
>
> Divergências em relação ao planejado estão no fim da fase.

Todos sob o prefixo existente, com `AdminRequired` (a página `/configuracoes` já é
`AdminRequired` em `app/web/pages/router.py:110` — os endpoints repetem a exigência no servidor,
porque gate de página não é autorização).

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/publicacoes/api/edicoes` | Lista as edições: rótulo, status, `data_publicacao`, contagem de manuais/documentos, `indice_disponivel` (o arquivo existe?), `tem_relatorio`, `snapshot_key` |
| `GET` | `/publicacoes/api/edicoes/{id}/relatorio` | Devolve `relatorio_diff` (markdown cru, como texto) |
| `POST` | `/publicacoes/api/edicoes/{id}/ativar` | Promove a edição a `VIGENTE` |
| `POST` | `/publicacoes/api/edicoes/{id}/arquivar` | `ARQUIVADA` — ação separada e explícita |
| `GET` | `/publicacoes/api/duplicacao` | Expõe `service.medir_duplicacao_entre_edicoes`, **que já existe e hoje não tem endpoint nenhum** |

### `ativar` — regras

Uma única operação, uma única transação:

1. Alvo precisa estar em `AGUARDANDO_ATIVACAO` ou `ANTERIOR`. `ARQUIVADA` → 409 (artefatos de disco
   podem já ter sido descartados). Já `VIGENTE` → 409 explícito, não no-op silencioso.
2. **Pré-condição dura:** `caminho_indice_da_edicao(rotulo)` precisa existir em disco → senão 409
   com mensagem dizendo qual arquivo falta e que basta reindexar. É exatamente a checagem que
   impede o botão de mentir.
3. A edição hoje `VIGENTE` passa a `ANTERIOR`.
4. O alvo passa a `VIGENTE`.

"Reverter" **não é um endpoint separado** — reverter é ativar a edição `ANTERIOR`. Um caminho de
código, um conjunto de testes, mesma semântica. A tela é que rotula o botão como "Reverter" quando o
alvo é a `ANTERIOR`.

**Invariante a garantir e testar: no máximo uma edição `VIGENTE`.** Hoje isso não é imposto por
constraint (o campo é só indexado). Duas opções:
- (a) impor no serviço, dentro da transação — simples, suficiente para um único processo;
- (b) índice único parcial (`CREATE UNIQUE INDEX ... WHERE status='VIGENTE'`), que o SQLite suporta.

**Recomendação: as duas** — (a) para dar erro legível, (b) como rede de segurança se um dia houver
mais de um worker publicando. (b) é uma migration de uma linha.

**Múltiplas `ANTERIOR` são permitidas.** Ativar não arquiva a `ANTERIOR` antiga automaticamente:
descartar artefatos de disco é decisão humana explícita (`arquivar`), coerente com o comentário do
model `ManualEdicao` ("nunca sofre hard delete"). A retenção de duas edições online do gate do M4
vira um **aviso visível no card** quando houver mais de duas edições com índice em disco, não uma
regra que apaga coisas sozinha.

### Auditoria

Ativar uma edição muda o que toda a organização lê como manual vigente. Verificar se o módulo de
auditoria existente cobre isso automaticamente; se não cobrir, gravar `publicado_por_id` (campo já
existe em `manuais_edicoes` e hoje fica nulo, porque scripts offline não têm usuário logado — a
ativação pela tela **tem**) e registrar a transição.

### O que a execução mudou em relação ao planejado

- **O índice único parcial pegou um bug de verdade, no primeiro teste.** `ativar_edicao` rebaixava a
  vigente e promovia a nova num **único** `flush()`; o SQLAlchemy é livre para emitir os dois
  `UPDATE` em qualquer ordem, e quando emitia a promoção primeiro havia um instante com duas linhas
  `VIGENTE` — que o índice recusa, derrubando a operação inteira com `IntegrityError`. Corrigido com
  um flush separado (libera o lugar, depois ocupa), ambos na mesma transação. **Sem o índice, esse
  bug não existiria hoje e apareceria mais tarde, com dois workers.** Foi a rede de segurança
  encontrando o problema antes do problema encontrar a produção.
- **Um dos testes de recusa teve de descer para o nível de serviço.** `override_get_db` do conftest
  faz `rollback()` da transação de teste inteira em qualquer exceção que passe pela dependência,
  inclusive um 409 intencional — depois da requisição, as linhas só "flushadas" já não existem e
  `db.refresh()` falha. O teste por HTTP afirma o 409 e a mensagem; o efeito colateral (nada mudou
  de status) é afirmado chamando `service.ativar_edicao` direto.
- **A mensagem do 409 carrega o comando de reindexação.** Quem recebe esse erro é um administrador
  numa tela, não um desenvolvedor lendo log — o teste afirma a presença de
  `indexar --edicao <rotulo>` no `detail`.
- **`_item_da_edicao` relê pela mesma consulta da listagem.** Ativar/arquivar devolvem o item
  completo, com contagens e `indice_disponivel` recalculado, para a UI atualizar a linha sem uma
  segunda chamada — e ver exatamente o que a listagem mostraria.

---

## Fase 2 — O card e os modais

### Estética: seguir o padrão existente literalmente

O card entra no mesmo `grid` de `configuracoes.html`, com a mesma estrutura dos seis já lá:

```html
<div class="card" style="display: flex; flex-direction: column; gap: 1rem;" data-role="ADMINISTRADOR">
    <div style="display: flex; align-items: center; gap: 0.75rem;">
        <div style="width: 40px; height: 40px; border-radius: var(--radius-md);
                    background: rgba(99, 102, 241, 0.1); color: #6366f1; ...">
            <!-- Ícone de livro aberto — o MESMO path SVG já usado no nav de /publicacoes
                 em base.html:100-104. O módulo já tem identidade visual; reusá-la é o que
                 faz o card ser reconhecido como "aquilo do menu". -->
        </div>
        <h3 style="margin: 0; font-size: 1.25rem;">Publicações</h3>
    </div>
    <p style="color: var(--text-secondary); font-size: 0.9rem; margin: 0; flex-grow: 1;">
        Edições do acervo de manuais, ativação e reversão de publicações, relatórios de diff e
        estado do índice de busca.
    </p>
    <div style="display: flex; gap: 0.5rem; flex-direction: column;">
        <button class="btn btn-publicacao" id="btn-gerenciar-edicoes" style="width: 100%;">Gerenciar Edições</button>
        <button class="btn btn-publicacao" id="btn-status-acervo"     style="width: 100%;">Status do Acervo</button>
        <button class="btn btn-publicacao" id="btn-ir-avulsas"        style="width: 100%;">Publicações Avulsas</button>
    </div>
</div>
```

**Cor:** índigo `#6366f1`. As seis já usadas estão tomadas (azul primário → aeronaves; `#9b59b6`
roxo → equipamentos; `#e67e22` laranja → vencimentos; `#2ecc71` verde → efetivo; `#1abc9c` teal →
inspeções; `#3b82f6` azul → calendário). Índigo é distinguível de todas e vizinho do azul da
identidade do sistema.

**CSS:** adicionar `.btn-publicacao` / `.btn-publicacao:hover` / `.btn-outline-publicacao` em
`app/web/static/css/index.css`, na seção "Cores por Seção (Configurações)" (linha ~256), copiando
o bloco de 4 regras que todas as outras seguem — mesma estrutura, `box-shadow` com o rgba da cor,
`transform: translateY(-2px)` no hover.

**Botão "Publicações Avulsas"** apenas navega para `/publicacoes/avulsas`, como
`btn-config-efetivo` navega para `/efetivo` (`configuracoes.js:83-88`). É o atalho que faltava: hoje
só se chega às avulsas pelo link dentro de `/publicacoes`.

### Modal 1 — Gerenciar Edições

Padrão de modal já usado em "Tipos de Inspeção": `position: fixed; inset: 0` + `rgba(0,0,0,0.6)` +
`backdrop-filter: blur(4px)`, `.card.glass-panel` com `max-width: 900px; max-height: 90vh`, header
com `border-bottom` e `btn-icon` de fechar, tabela com `thead` em `rgba(0,0,0,0.1)`, footer com
`border-top` e `.btn.btn-outline` "Fechar".

| Rótulo | Publicada em | Documentos | Índice | Status | Ações |
|---|---|---|---|---|---|
| 2026 | 05/08/2026 | 5.724 | ✅ em disco | `AGUARDANDO_ATIVACAO` | **Ativar** · Relatório |
| piloto-fim | 12/03/2026 | 3 | ✅ em disco | `VIGENTE` | Relatório |
| 2025 | 08/2025 | 5.610 | ⚠️ ausente | `ANTERIOR` | Relatório |

- Badge de status reusa o pill inline de `configuracoes.js:981` (pílula com `rgba` tint +
  `var(--status-ok)` / `var(--status-danger)`), estendido para quatro estados: `VIGENTE` verde,
  `AGUARDANDO_ATIVACAO` laranja (`--status-warning`), `ANTERIOR` cinza (`--text-secondary`),
  `ARQUIVADA` vermelho.
- **"Ativar" só aparece quando `indice_disponivel === true`.** Quando o índice falta, no lugar do
  botão vai um texto explicando que é preciso reindexar. O botão nunca é oferecido para uma ação que
  o servidor vai recusar.
- Rótulo "Ativar" vira "Reverter para esta edição" quando o alvo está em `ANTERIOR`.
- `confirm()` antes de ativar, nomeando a edição que sai e a que entra — mesmo padrão de
  `alterarStatusAeronave` (`configuracoes.js:301`).
- Aviso no topo do modal quando houver mais de duas edições com índice em disco (gate de retenção).

### Modal 2 — Relatório de diff

Modal simples (`max-width: 800px`) exibindo `relatorio_diff` dentro de um
`<pre style="white-space: pre-wrap">` com `escapeHtml`.

**Não renderizar markdown.** Não há biblioteca de markdown no front do projeto, e injetar uma
(ou escrever um mini-renderer com `innerHTML`) para exibir texto gerado por script é risco de XSS
sem ganho real — o relatório é uma lista de contagens e nomes de arquivo, legível como texto puro.
Se um dia o relatório crescer a ponto de precisar de formatação, aí sim é uma decisão consciente.

### Modal 3 — Status do Acervo

Painel de leitura, sem ações. Consome `/publicacoes/api/status` (já existe) e
`/publicacoes/api/duplicacao` (Fase 1), em grid de "stat tiles" no estilo dos cards:

```
Edição vigente: 2026        Índice: disponível        Atualizado: 05/08/2026 21:14
Manuais: 34                 Documentos: 5.724         Páginas indexadas: 53.792
Sem camada de texto: 0      Mensagens FIM: 1.204      Duplicados por hash: 5.610
```

`documentos_sem_texto` em destaque de aviso quando `> 0` — é o número que dispara a discussão de
OCR (M4 tarefa 8), e hoje ele não aparece em lugar nenhum da interface.

### JavaScript

Nova seção ao final de `configuracoes.js`, no mesmo estilo do arquivo: `// @ts-check` com JSDoc,
`apiFetch`/`showToast`/`escapeHtml` globais, listeners registrados dentro do `DOMContentLoaded`
existente, **zero handler inline** (CSP — o arquivo inteiro já segue essa regra, com o comentário
"handlers para fechar modais (CSP compliant)" na linha 90).

O arquivo já tem 1.945 linhas. Se a seção nova passar de ~250, vale extraí-la para
`configuracoes_publicacoes.js` carregado no mesmo `{% block scripts %}` — decidir na hora de
escrever, não antes.

---

## Fase 3 — Testes

| Alvo | Teste |
|---|---|
| Resolução do índice | `caminho_indice_da_edicao` para rótulos normais; rótulo malicioso (`../x`) rejeitado; fallback para o `catalog.db` legado quando o por-edição não existe |
| Busca por edição | Indexar duas edições em arquivos separados, ativar uma, confirmar que `/api/busca` devolve o conteúdo daquela; ativar a outra e confirmar que **a mesma query devolve resultado diferente** — este é o teste que prova que ativar não é teatro |
| `ativar` — transições | `AGUARDANDO_ATIVACAO`→`VIGENTE` com demoção da anterior; `ANTERIOR`→`VIGENTE` (reverter); `ARQUIVADA`→409; já `VIGENTE`→409 |
| `ativar` — pré-condição | Índice ausente em disco → 409, e o status **não** muda |
| Invariante | Após qualquer sequência de ativações, exatamente uma `VIGENTE` |
| RBAC | Mantenedor e Encarregado → 403 em `ativar`/`arquivar`; Admin → 200. **Atenção ao harness:** `client_autenticado` sobrescreve `get_current_user` e ignora headers pelo resto do teste — usar setup via ORM direto, como `test_publicacoes_avulsas.py::_inserir_avulsa_direto` |
| Fumaça | `/configuracoes` continua 200 e contém `id="btn-gerenciar-edicoes"` |
| Performance | Confirmar que a consulta extra de resolução não estourou o alvo CA-01 (p95 < 300 ms) — medição, no mesmo formato da que já existe |

---

## Fase 4 — Documentação

1. **`08_status_de_implementacao.md`**: M4 tarefa 4 → ✅ e M4 → 8/8; remover as duas dívidas que
   deixam de existir (`catalog.db` por edição; tarefa 4 bloqueada); atualizar o gate do M4 —
   ativar/reverter passa a ✅, RSS/disco continuam 🔒 D-04.
2. **`docs/guides/operacao_publicacoes.md`**: substituir os três pontos que hoje dizem "🔒 pendente
   de implementação" (§1 diagrama passo 4, §2 "Nunca ativa a edição", §4 restauração passo 4) pelo
   procedimento real; acrescentar a `catalog.<rotulo>.db` na tabela de backup da §4.
3. **`docs/architecture/adr/004-modulo-publicacoes.md`**: a seção nova da Fase 0.
4. **`docs/architecture/referencia-api.md`**: os cinco endpoints novos, se o arquivo for mantido
   manualmente — verificar antes.

---

## Ordem de execução e commits

| # | Entrega | Commit sugerido |
|---|---|---|
| 1 | ✅ Fase 0 — índice por edição + ADR + testes de resolução/busca | `refactor(publicacoes): catalog.db por edicao, indice resolvido pelo banco` |
| 2 | ✅ Fase 1 — endpoints + migration do índice único parcial + testes | `feat(publicacoes): endpoints de ativacao e relatorio de edicao` |
| 3 | Fase 2 — card, modais, CSS, JS | `feat(publicacoes): card de gerencia em /configuracoes` |
| 4 | Fase 4 — documentação | junto do commit 3 |

A Fase 0 é entregável sozinha e **melhora o sistema mesmo que as fases seguintes não venham**: hoje
publicar uma edição nova destrói o índice da vigente, e a Fase 0 corrige isso por si só.

---

## O que este plano deliberadamente não faz

- **Não publica pela tela.** `publicar.py` roda ~150s no acervo medido e reindexa 5.724 PDFs — não
  cabe num request HTTP, e transformá-lo em job de background é um problema à parte (fila,
  progresso, cancelamento). A tela **ativa** o que o script publicou; publicar segue sendo operação
  de terminal, como o runbook descreve.
- **Não faz upload de acervo pela tela.** Decisão D-D: o acervo trafega por rsync/SSH, nunca HTTP.
- **Não deduplica fisicamente.** Continua sendo medição (M4 tarefa 5), dependente de D-04.
- **Não resolve o gate de RSS/disco da VPS** — 🔒 D-04, sem VPS não há o que medir.

## Verificação que só um humano pode fazer

A dívida "frontend sem verificação visual em navegador" de `08_status_de_implementacao.md` vale
igualmente para este card. Depois de implementado, alguém precisa abrir `/configuracoes` num
navegador real e conferir: layout do card no grid (inclusive no breakpoint de 300px do
`auto-fit`), os três modais, o badge de status nos quatro estados, e o console limpo de violações
de CSP.
