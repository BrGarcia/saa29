# Plano de trabalho corrente — módulo `publicacoes`

> **Este é o documento de "o que fazer agora".** O nome do arquivo diz `configuracoes` porque a
> primeira etapa era o card de `/configuracoes`; ele passou a abrigar também as etapas seguintes, em
> vez de a pasta virar uma sucessão de planos de uma etapa cada. O nome ficou para não quebrar as
> referências já gravadas em commits, no `08` e no adendo do ADR-004.
>
> **Se você é novo no módulo, leia nesta ordem:**
> 1. [`00_indice.md`](00_indice.md) — mapa da pasta e quais documentos mudam;
> 2. [`08_status_de_implementacao.md`](08_status_de_implementacao.md) — o que já existe, com
>    evidência verificável;
> 3. [`03_especificacao_tecnica.md`](03_especificacao_tecnica.md) §0.1 — o que mudou desde o
>    planejamento original;
> 4. **este documento** — o que falta, em ordem de execução.
>
> **Estado das etapas:**
>
> | Etapa | Assunto | Situação |
> |---|---|:--|
> | 1 | Gerência de publicações em `/configuracoes` (M4 tarefa 4) | ✅ Fases 0, 1 e 2 implementadas |
> | 2 | **Navegação do acervo** (lacuna do M1) | ⚪ **Próxima — é aqui que você começa** |
>
> Cada etapa é independente: a 2 não depende de nada da 1.

---

# Etapa 1 — Gerência de Publicações em `/configuracoes` (M4 tarefa 4) ✅

> **Contexto:** `08_status_de_implementacao.md` fechava o M4 em 6/8 e registrava a tarefa 4 como
> não implementada por uma lacuna arquitetural concreta — não existia `catalog.db` por edição, então
> "ativar edição" mudaria o status no banco sem mudar o que a busca devolve. Esta etapa resolveu
> primeiro essa lacuna e só então construiu a tela.
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

## Fase 2 — O card e os modais ✅ **IMPLEMENTADA**

> **Estado:** concluída. `app/web/static/js/configuracoes_publicacoes.js` (arquivo separado, como o
> plano previa para o caso de passar de ~250 linhas), card e 3 modais em `configuracoes.html`,
> `.btn-publicacao` em `index.css`. 8 testes de fumaça amarrando template e JS pelos ids; suíte em
> 622 passando, `ruff check .` limpo, `node --check` no JS.
>
> **Não verificado em navegador** — sem acesso a browser nesta sessão. Ver "Verificação que só um
> humano pode fazer", no fim deste documento.

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

### O que a execução mudou em relação ao planejado

- **Arquivo separado**, como a ressalva previa: a seção passou de 250 linhas.
  `configuracoes_publicacoes.js` é carregado no mesmo `{% block scripts %}`, depois de
  `configuracoes.js`. Conferido que **nenhum** nome de função ou constante do arquivo novo colide
  com o antigo — os dois são scripts clássicos e dividem o escopo global; uma colisão sobrescreveria
  silenciosamente a função do outro.
- **Um botão "Arquivar" por linha**, que o plano não detalhava — sem ele o endpoint de arquivar
  existiria sem porta de entrada na tela.
- **A mensagem de erro do servidor é repassada como está** no toast. O 409 de ativar carrega o
  motivo e o comando de reindexação; trocá-lo por "erro ao ativar" perderia justamente a parte útil.
- **O aviso de retenção usa limite fixo 2** no JS, não `PUBLICACOES_EDICOES_RETIDAS`. O valor existe
  em `Settings` mas não é exposto por endpoint nenhum; expor uma configuração inteira só para isso
  não se pagava. Se o limite mudar, muda em dois lugares — registrado como dívida no `08`.
- **Testes de fumaça amarram template e JS pelos ids.** É o modo de falha silencioso desta fase: um
  id renomeado no template deixa o `addEventListener` sem alvo e o botão para de funcionar sem erro
  em lugar nenhum.
- **A Fase 1 deixou um teste instável que só apareceu agora.**
  `test_trocar_edicao_vigente_muda_o_que_a_busca_devolve` (Fase 0) trocava `status` na mão, num
  flush único — o mesmo padrão que o índice único parcial recusa. O SQLAlchemy ordena UPDATEs da
  mesma tabela por chave primária, e como as edições têm UUID aleatório, a promoção vinha antes do
  rebaixamento em cerca de 1/3 das execuções. A suíte da Fase 1 passou por sorte do sorteio.
  Corrigido usando `service.ativar_edicao` no teste, que é o caminho real e já faz o flush em duas
  etapas; 8 execuções seguidas limpas, e o teste passou a exercitar a Fase 1 de quebra.
  **Lição:** um índice novo pode transformar código correto-por-acidente em falha intermitente, e
  uma suíte verde numa execução não prova ausência disso — rodar duas vezes é barato.

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
| 3 | ✅ Fase 2 — card, modais, CSS, JS | `feat(publicacoes): card de gerencia em /configuracoes` |
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

---
---

# Etapa 2 — Navegação do acervo (lacuna do M1) ⚪ PRÓXIMA

> **Se você acabou de chegar ao módulo, é aqui que se começa.** Nada nesta etapa depende da Etapa 1.

## 2.1 O problema, e como ele passou despercebido

Hoje `/publicacoes` é **só busca**. Sem digitar um termo, a página não mostra documento nenhum. E os
dois filtros de refino ("Manual (código)" e "Capítulo") são `<input type="text">` livres: para
filtrar por manual você precisa **já saber** que o código é `FIM_1741`, e que o capítulo se chama
`CHAPTER_36`. Nada na interface revela esses valores.

Resultado prático: um mecânico que não sabe o que procurar não tem por onde entrar em um acervo de
34 manuais e 5.724 documentos.

**Isto estava especificado, com rota e tudo, e nunca virou tarefa.** A tabela de rotas de
[`03_especificacao_tecnica.md`](03_especificacao_tecnica.md) §3 lista **duas páginas HTML** que não
existem no código:

| Rota da especificação | Observação na spec | Situação real |
|---|---|---|
| `GET /publicacoes/manuais/{manual_path}` | "capítulos" | ❌ **não existe** |
| `GET /publicacoes/manuais/{manual_path}/{capitulo}` | "documentos" | ❌ **não existe** |

E a matriz RBAC §7 lista, como primeira linha, a ação *"Navegar catálogo / buscar / abrir PDF"*,
liberada para os quatro perfis. Ou seja: a navegação estava **na tabela de rotas e na matriz de
permissões**, e mesmo assim não virou tarefa de nenhum marco — nem M1, nem M2, nem M3, nem M4.

### Auditoria completa das rotas (feita em 06/08/2026)

Cruzando a §3 com as rotas realmente registradas na aplicação:

| Rota da §3 | Situação |
|---|---|
| `GET /publicacoes/manuais/{manual_path}` | ❌ ausente — **esta etapa** |
| `GET /publicacoes/manuais/{manual_path}/{capitulo}` | ❌ ausente — **esta etapa** |
| `POST /publicacoes/api/edicoes/{id}/reverter` | ⚠️ ausente **por decisão**: reverter é ativar a edição `ANTERIOR`, pelo mesmo endpoint `/ativar`. Um caminho de código só. Registrado na §0.1 do contrato |
| Todas as demais (16) | ✅ existem |

Rotas que existem e a §3 não previa (acrescentadas durante a implementação, todas legítimas):
`/api/documentos/{doc_id}`, `/api/fim/por-ata/{ata}`, `/api/favoritos*`, `/api/duplicacao`,
`/api/edicoes/{id}/relatorio`, `/api/edicoes/{id}/arquivar`.

Reproduza a auditoria com:

```bash
python -c "
import app.bootstrap.main as m
for r in sorted({(r.path, ','.join(sorted(r.methods-{'HEAD','OPTIONS'}))) for r in m.app.routes if getattr(r,'methods',None) and r.path.startswith(('/publicacoes','/m/publicacoes'))}):
    print(r)
"
```

**Lição de processo:** os gates de marco conferem a lista de tarefas, não a tabela de rotas. Uma
rota especificada em §3 que ninguém transformou em tarefa não é vista por gate nenhum. **Ao fechar
um marco, rode a auditoria acima e cruze com a §3** — foi o cruzamento que faltou por quatro marcos
seguidos.

## 2.2 Fatos medidos do acervo (base para o desenho)

Medidos em 06/08/2026 no banco local, edição `2026`. **Reproduza antes de confiar** — o acervo pode
ter mudado:

```bash
python -c "
import sqlite3
c = sqlite3.connect('file:var/db?mode=ro', uri=True)
E = \"(select id from manuais_edicoes where rotulo='2026')\"
print(list(c.execute(f'select categoria, count(*) from manuais where edicao_id={E} group by 1 order by 2 desc')))
"
```

| Fato | Valor | Consequência para o desenho |
|---|---|---|
| Manuais na edição | 34 | Cabe numa única resposta; não precisa paginar o primeiro nível |
| Categorias distintas | 7 | Agrupar por categoria no primeiro nível |
| Maior categoria | `Ordens Técnicas` — **17 dos 34** | Metade do acervo cai num grupo só; ele precisa vir recolhido por padrão, ou domina a tela |
| Maior manual | `AMM_PART2_1651` — 51 capítulos, **1.148 documentos** | **Nunca** carregar todos os documentos de um manual de uma vez |
| Menor manual | `OTFN1A29AB5_0001` — 1 capítulo, 2 documentos | O desenho precisa não parecer absurdo para um manual de 2 arquivos |
| Documentos com `ata_codigo` | 3.973 de 5.724 (69%) | Dá para rotular a maioria dos capítulos por ATA, mas **não todos** — precisa de fallback |
| Capítulo vazio (`''`) na edição `2026` | **0** | No layout do acervo todo PDF está sob um capítulo |
| Capítulo vazio na edição `piloto-fim` | **2** | Mas o caso existe: o piloto tinha PDFs soltos na raiz. **Trate `capitulo == ''`**, não presuma que sumiu |
| `descricao_pt` preenchida | Sim, legível | Ex.: `AMM Parte II — Manual de Manutenção da Aeronave (práticas de manutenção)`. **Exiba isto**, não o código |

Nomes de capítulo são crus do diretório: `010_FRONTMATTER`, `015_TRINDEX`, `CHAPTER_05`,
`040_FISEC_CHAPTER_21`. Feios, mas ordenáveis por prefixo numérico (RN-05).

## 2.3 Colunas disponíveis (não precisa migration)

Tudo o que a navegação precisa **já existe no banco principal**. Esta etapa não tem migration.

```
manuais              : id, edicao_id, codigo, descricao_pt, categoria, path,
                       revisao, revisao_data, created_at, updated_at
manuais_documentos   : id, manual_id, capitulo, ata_codigo, file_key, titulo,
                       sort_order, paginas, has_text, revision_status,
                       hash_sha256, created_at, updated_at
```

**Regra que atravessa a etapa inteira:** toda consulta é escopada pela **edição VIGENTE**
(`service.obter_edicao_vigente`). Navegar tem de mostrar o acervo em vigor, não a união de todas as
edições retidas. Um `join` esquecido aqui faz o mesmo documento aparecer duas vezes com ids
diferentes (achado B2 — o `document_id` inclui a edição no UUID v5).

**Nada disso toca `catalog.db`.** Navegação é catálogo, não busca full-text: banco principal,
SQLAlchemy, `service.py`. `search.py` não é alterado nesta etapa.

---

## Fase N1 — Endpoints de catálogo

Três rotas novas em `app/modules/publicacoes/router.py`, sob o prefixo `/publicacoes/api/`, todas
com `CurrentUser` (qualquer perfil autenticado — a matriz RBAC §7 libera para os quatro).

### `GET /api/manuais`

Lista os manuais da edição vigente. Sem paginação (são 34).

```jsonc
[
  {
    "codigo": "AMM_PART2_1651",
    "descricao": "AMM Parte II — Manual de Manutenção da Aeronave (práticas de manutenção)",
    "categoria": "Manutenção",
    "capitulos": 51,
    "documentos": 1148,
    "revisao": null          // manuais_documentos.revisao do manual, quando houver
  }
]
```

Ordenação: `categoria`, depois `codigo`. O agrupamento por categoria é feito no cliente — devolver
uma lista plana mantém o schema simples e deixa a UI livre para agrupar ou não.

Implementação: `select(Manual, count(distinct capitulo), count(documento.id))` com
`outerjoin(ManualDocumento)` + `group_by(Manual.id)`, filtrando `Manual.edicao_id == vigente.id`.
**`outerjoin`, não `join`** — um manual sem documento nenhum não pode sumir da listagem (é como se
descobre que a indexação falhou para ele).

### `GET /api/manuais/{codigo}/capitulos`

```jsonc
{
  "manual": { "codigo": "FIM_1741", "descricao": "FIM — Manual de Isolamento de Falhas", "categoria": "Manutenção" },
  "capitulos": [
    { "capitulo": "040_FISEC_CHAPTER_21", "ata_codigo": "21", "documentos": 34 },
    { "capitulo": "010_FRONTMATTER",      "ata_codigo": null, "documentos": 8 }
  ]
}
```

- `ata_codigo`: `max(ata_codigo)` do grupo — dentro de um capítulo do acervo o valor é constante
  quando existe; `max` evita `GROUP BY` extra. Quando `null`, a UI cai no nome cru.
- Ordenação por `capitulo` (o prefixo numérico já ordena, RN-05).
- Manual inexistente na edição vigente → **404**, com `EntidadeNaoEncontradaError`.

### `GET /api/manuais/{codigo}/documentos`

| Parâmetro | Tipo | Padrão | Observação |
|---|---|---|---|
| `capitulo` | `str \| None` | `None` | `None` = todos os capítulos do manual |
| `limit` | `int` 1–100 | 50 | |
| `offset` | `int` ≥ 0 | 0 | |

```jsonc
{
  "total": 1148,
  "results": [
    {
      "doc_id": "…uuid…",
      "titulo": "Bleed Air Leak Detection",
      "capitulo": "040_FISEC_CHAPTER_21",
      "ata_codigo": "21",
      "paginas": 12,
      "has_text": true,
      "viewer_url": "/publicacoes/viewer/…uuid…"
    }
  ]
}
```

- Ordenação: `sort_order`, depois `titulo` — `sort_order` é o prefixo numérico do arquivo (RN-05) e
  é o que reproduz a ordem que o mecânico vê no DVD.
- `viewer_url` montado pelo helper `_viewer_url` que já existe no router, **sem** `#page` (a
  navegação abre o documento no começo; quem quer a página do trecho vem pela busca).
- `has_text=false` deve chegar na resposta e ser exibido como aviso: é um PDF que a busca não
  alcança (E-01), e o usuário precisa saber que não adianta procurar por texto ali.

### Schemas (`app/modules/publicacoes/schemas.py`)

`ManualListItem`, `CapituloItem`, `RespostaCapitulos`, `DocumentoCatalogoItem`,
`RespostaDocumentosCatalogo`. Seguir o padrão do arquivo: `model_config = ConfigDict(from_attributes=True)`
só onde há ORM direto; nas agregações, montar o schema explicitamente a partir do `dict` do service
(como `EdicaoListItem` faz).

### Testes — `tests/unit/test_publicacoes_navegacao.py` (arquivo novo)

| Teste | O que prova |
|---|---|
| `test_listar_manuais_agrupa_contagens` | Contagem de capítulos e documentos bate com o inserido |
| `test_manual_sem_documentos_ainda_aparece` | O `outerjoin` — o modo de falha é o manual sumir da tela quando a indexação falhou para ele |
| `test_listar_manuais_so_da_edicao_vigente` | Cria duas edições com o mesmo código de manual e confirma que só a vigente aparece. **É o teste central da etapa** |
| `test_capitulos_ordenados_por_prefixo` | RN-05 |
| `test_capitulo_sem_ata_devolve_nulo` | Os 31% sem `ata_codigo` |
| `test_capitulo_vazio_e_representado` | O caso do `piloto-fim` (`capitulo == ''`) não some nem quebra |
| `test_documentos_paginados_e_ordenados_por_sort_order` | |
| `test_documentos_filtrados_por_capitulo` | |
| `test_manual_inexistente_retorna_404` | |
| `test_navegacao_exige_autenticacao` | 401 sem sessão |
| `test_mantenedor_pode_navegar` | A matriz §7 libera para os quatro perfis — inclusive o mais restrito |

**Armadilhas do harness** (já custaram tempo antes; leia antes de escrever teste):
- `client_autenticado` sobrescreve `get_current_user` e **ignora o header `Authorization` pelo resto
  do teste**. Para exercitar outro perfil no mesmo teste, insira os dados via ORM direto — ver
  `tests/unit/test_publicacoes_avulsas.py::_inserir_avulsa_direto`.
- `override_get_db` do `conftest` faz `rollback()` da transação de teste inteira em **qualquer**
  exceção que passe pela dependência, inclusive um 404 intencional. Depois de uma requisição que
  devolve erro, as linhas só "flushadas" já não existem. Afirme o estado do banco **antes** da
  requisição que falha, ou chame o `service` direto — ver
  `tests/unit/test_publicacoes_edicoes.py::test_ativar_sem_indice_nao_altera_o_status`.
- Use sufixo único em qualquer campo com `UNIQUE` (`uuid.uuid4().hex[:6]`). Já houve colisão de
  matrícula custando ~10% de falha intermitente.

**Commit:** `feat(publicacoes): endpoints de navegacao do catalogo`

---

## Fase N2 — Páginas de navegação (desktop)

### Forma: páginas com URL real, como a §3 especificou

A especificação define **duas páginas HTML**, não um drill-down em JavaScript numa página só. Siga
isso — e não por obediência ao documento, mas porque a escolha é melhor para o uso real:

| | Páginas com URL (§3) | Drill-down em JS |
|---|---|---|
| Mandar "veja o capítulo 21 do FIM" para um colega | cola o link | impossível |
| Botão voltar do navegador | funciona | não funciona |
| Favoritar um capítulo no navegador | funciona | não funciona |
| Requisições | 1 por página | 1 por nível |

Num hangar, "manda o link do capítulo" é operação real. O drill-down perderia isso.

### As três telas

```
/publicacoes                          → home: busca + índice dos 34 manuais por categoria
/publicacoes/manuais/{codigo}         → capítulos do manual
/publicacoes/manuais/{codigo}/{cap}   → documentos do capítulo, cada um → viewer
```

**Rotas em `app/web/pages/router.py`.** Atenção à convenção já registrada na §3: rotas estáticas
antes das paramétricas no mesmo nível. `/publicacoes/avulsas` e `/publicacoes/viewer/{id}` já estão
declaradas; `/publicacoes/manuais/...` não colide com elas, mas **declare-as depois de
`/publicacoes/avulsas`** para manter o padrão de `equipamentos/router.py:194-195`.

O `{codigo}` na URL é o `manuais.codigo` (ex.: `AMM_PART2_1651`), não o `path` do disco — o path é
detalhe de infraestrutura e não deve aparecer em URL. A §3 chama o parâmetro de `{manual_path}`;
**use `{codigo}`** e registre a divergência na §0.1 do contrato.

### Índice na home (`lista.html`)

Bloco "Navegar no acervo" **acima** do card de busca, com os 34 manuais agrupados pelas 7
categorias. Renderizado no servidor a partir de `GET /api/manuais`? **Não** — renderize no servidor
direto do `service`, sem passar pela API. A página já tem o `db`; uma chamada HTTP a si mesma seria
um salto desnecessário. A API existe para o mobile e para os `<select>` de refino.

- **`Ordens Técnicas` (17 dos 34) vem recolhido**, os outros 6 grupos abertos. Metade do acervo num
  grupo só domina a tela se vier aberto.
- Use `<details>/<summary>` nativo: acessível por teclado de graça, funciona sem JS, e não há
  componente de acordeão no projeto para reusar — escrever um seria inventar padrão novo.
- Exiba `descricao_pt`, com o `codigo` em texto secundário. Ninguém procura por `AMM_PART2_1651`.

### Página de capítulos

- Rótulo: `ATA {ata_codigo} — {capitulo}` quando houver `ata_codigo` (69% dos documentos); senão só
  o nome cru. **Não invente tradução** para `010_FRONTMATTER`.
- `capitulo == ''` exibe "(raiz do manual)" — o caso existe na edição `piloto-fim`.
- Contagem de documentos por capítulo em cada linha.
- Breadcrumb: `Publicações › {descricao do manual}`.

### Página de documentos

- Ordenados por `sort_order` (RN-05: é a ordem que o mecânico vê no DVD).
- Cada linha: título, nº de páginas, link para `/publicacoes/viewer/{doc_id}`.
- `has_text == false` ganha aviso com `title` explicando que o documento **não é alcançável pela
  busca** (E-01) — o usuário precisa saber que não adianta procurar texto ali.
- Paginação: `?offset=`/`?limit=` na própria URL, com links "anterior/próxima". Server-side, para
  não perder a propriedade de URL compartilhável. O maior capítulo medido tem poucas dezenas de
  documentos, então 50 por página basta.
- Breadcrumb: `Publicações › {manual} › {capítulo}`.

### Conserto dos filtros de refino (mesmo commit)

Trocar os dois `<input type="text">` do card de busca em `lista.html` por `<select>`:
- **Manual**: populado de `GET /api/manuais`.
- **Capítulo**: populado de `GET /api/manuais/{codigo}/capitulos` quando um manual é escolhido;
  desabilitado enquanto não houver manual.

**É aqui que a API da Fase N1 ganha uso no desktop.** E fecha o buraco de descoberta que originou a
etapa: hoje os campos exigem conhecimento que a interface não fornece.

### Arquivos

| Arquivo | Mudança |
|---|---|
| `app/web/pages/router.py` | 2 rotas HTML novas |
| `app/web/templates/publicacoes/manual.html` | **novo** — capítulos |
| `app/web/templates/publicacoes/capitulo.html` | **novo** — documentos |
| `app/web/templates/publicacoes/lista.html` | Bloco "Navegar no acervo" + os 2 `<select>` |
| `app/web/static/js/publicacoes.js` | Popular os `<select>`. **Sem handler inline** (CSP) |

### Testes a acrescentar em `tests/unit/test_publicacoes_navegacao.py`

`test_pagina_manual_lista_capitulos`, `test_pagina_capitulo_lista_documentos`,
`test_pagina_manual_inexistente_retorna_404`, `test_home_lista_os_manuais_por_categoria`,
e um que afirme que o link do documento aponta para `/publicacoes/viewer/{id}`.

**Commit:** `feat(publicacoes): paginas de navegacao do acervo`

---

## Fase N3 — Navegação no mobile (`/m/publicacoes`)

`app/web/templates/mobile/publicacoes.html` tem exatamente o mesmo problema. A forma muda:

- **Uma lista por vez**, navegando pelas mesmas URLs do desktop (`/publicacoes/manuais/...`) —
  reusar as rotas evita um segundo conjunto de telas para manter em sincronia. Decidir na hora
  se os templates do desktop já servem no mobile ou se precisam de variantes.
- Alvos de toque **≥ 44 px** (CA-03, já é critério do módulo).
- Nenhum backend novo: ou as páginas da N2, ou os endpoints da N1.

Decidir na hora de escrever se vale extrair o JS comum com o desktop. **Não extrair antes de haver
duplicação real** — as duas telas podem divergir de forma legítima.

**Commit:** `feat(publicacoes): navegacao do acervo no mobile`

---

## Fase N4 — Documentação da Etapa 2

1. **`03_especificacao_tecnica.md`**: acrescentar as 3 rotas em §3 e uma linha na §0.1 registrando
   que a navegação chegou depois. É o contrato — precisa listar as rotas que existem.
2. **`08_status_de_implementacao.md`**: fechar a dívida "navegação ausente"; registrar as novas
   (verificação visual, e o que ficou de fora).
3. **Este documento**: marcar N1–N3 como implementadas, com a seção "O que a execução mudou em
   relação ao planejado" — que é o que torna estes planos úteis depois.
4. **`00_indice.md`**: nada a mudar, salvo se surgir documento novo.

---

## Ordem de execução e commits — Etapa 2

| # | Entrega | Commit |
|---|---|---|
| 1 | Fase N1 — 3 endpoints + schemas + 11 testes | `feat(publicacoes): endpoints de navegacao do catalogo` |
| 2 | Fase N2 — 2 páginas HTML + índice na home + selects de refino | `feat(publicacoes): paginas de navegacao do acervo` |
| 3 | Fase N3 — navegador mobile | `feat(publicacoes): navegacao do acervo no mobile` |
| 4 | Fase N4 — documentação | junto do commit 3 |

Rode a suíte **duas vezes** antes de cada commit. Uma execução verde não prova ausência de teste
instável — foi assim que a Fase 1 desta pasta deixou passar uma falha de ~1/3.

## O que a Etapa 2 deliberadamente não faz

- **Não indexa nem publica nada.** É leitura de catálogo.
- **Não navega o acervo B (avulsas).** `/publicacoes/avulsas` já tem lista com filtros próprios; o
  problema é do acervo A.
- **Não mostra edições não vigentes.** Navegar é sobre o acervo em vigor. Chegar a um documento de
  edição anterior continua sendo pelo link direto, com o banner "REVISÃO ANTERIOR" que o viewer já
  exibe.
- **Não renomeia capítulos no banco.** O rótulo bonito é de exibição; `capitulo` continua sendo a
  chave crua do diretório, que é o que casa com o disco.

## Verificação que só um humano pode fazer

Depois de N2/N3, alguém precisa abrir num navegador real e conferir: a árvore com `Ordens Técnicas`
recolhido, um manual grande (`AMM_PART2_1651`, 51 capítulos) sem travar a página, o "carregar mais"
dentro de um capítulo, os `<select>` de refino populados, e a tela mobile com alvos de toque
confortáveis. Nada disso é afirmável por teste de fumaça.
