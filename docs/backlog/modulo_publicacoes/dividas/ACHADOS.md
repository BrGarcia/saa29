# ACHADOS — revisão do módulo `publicacoes`

Ordem de revisão: por tamanho decrescente (service.py, router.py, models.py,
catalog.py, schemas.py, search.py, avulsas.py, __init__.py).

---

## app/modules/publicacoes/service.py — revisado em 2026-08-08

### [ALTO] `obter_ou_criar_edicao` trata QUALQUER `IntegrityError` como corrida de rótulo
- **Local:** linhas 139–148, função `obter_ou_criar_edicao`
- **Problema:** o `except IntegrityError` assume que a violação veio do
  `unique=True` de `rotulo` e devolve `scalar_one()` da edição com aquele
  rótulo. Mas o INSERT também pode violar o índice único parcial
  `uq_manuais_edicoes_vigente_unica` (só uma edição VIGENTE), e o parâmetro
  tem **default `status=StatusEdicao.VIGENTE`** — criar uma edição nova com o
  default quando já existe uma vigente viola esse índice, não o de rótulo.
  Nesse caso o SELECT de fallback por `rotulo` não encontra nada e
  `scalar_one()` levanta `NoResultFound`.
- **Impacto:** em vez de um erro de domínio claro ("já existe edição vigente"),
  o chamador (indexador) recebe `NoResultFound` — erro enganoso que mascara a
  causa real. Se algum caminho de requisição chamar com o default, vira 500.
- **Correção sugerida:** inspecionar `exc.orig` / o nome da constraint antes de
  assumir corrida de rótulo; no fallback, usar `scalar_one_or_none()` e, se
  vier `None`, relançar como `ConflitoNegocioError` explicando que já há uma
  edição vigente. Considerar trocar o default para um status não-vigente
  (ex.: `AGUARDANDO_ATIVACAO`), forçando o chamador a ser explícito.
- **A CONFIRMAR:** com que `status` `scripts/publicacoes/indexar.py` chama esta
  função (fora do escopo desta revisão); e a existência exata do índice parcial
  em `models.py` (verificada na revisão de models.py, adiante).

### [MÉDIO] `_favoritar` pode estourar `NoResultFound` quando o `IntegrityError` é de FK, não de unicidade
- **Local:** linhas 1129–1152, função `_favoritar`
- **Problema:** o `except IntegrityError` assume violação da
  `UniqueConstraint` (favorito duplicado) e devolve
  `(await db.execute(select(...).where(*filtros))).scalar_one()`. Mas o INSERT
  também pode falhar por **FK**: `sincronizar_catalogo` remove documentos
  obsoletos (RN-09), então um favorito num documento recém-removido gera
  `IntegrityError` de FK — o SELECT de fallback não encontra linha nenhuma e
  `scalar_one()` levanta `NoResultFound`.
- **Impacto:** usuário favorita um documento durante uma reindexação e recebe
  500 em vez de 404 ("documento não encontrado"). Janela pequena, mas o
  pre-check `obter_documento` em `favoritar_documento` (linha 1163) não fecha
  a corrida — só a estreita.
- **Correção sugerida:** usar `scalar_one_or_none()` no fallback; se `None`,
  relançar `EntidadeNaoEncontradaError` (o alvo do favorito deixou de existir).

### [MÉDIO] Corrida entre duas ativações concorrentes vira 500, não 409
- **Local:** linhas 410–428, função `ativar_edicao`
- **Problema:** duas requisições ativando edições diferentes ao mesmo tempo
  leem a MESMA `anterior` via `obter_edicao_vigente`, ambas a rebaixam e ambas
  promovem a sua — a segunda a commitar viola
  `uq_manuais_edicoes_vigente_unica` e o `IntegrityError` sobe sem tratamento.
  Há também um TOCTOU menor: `_indice_existe` (linha 393) confere o arquivo
  antes do commit; o arquivo pode sumir entre a checagem e o uso.
- **Impacto:** erro 500 para o segundo operador; nenhum dado corrompido (a
  transação faz rollback), mas a mensagem não explica o conflito.
- **Correção sugerida:** capturar `IntegrityError` no router/service e converter
  em `ConflitoNegocioError` ("outra ativação em andamento — recarregue a
  tela"), ou serializar via `SELECT ... FOR UPDATE` da linha vigente (Postgres).

### [MÉDIO — A CONFIRMAR] `sincronizar_catalogo`: documento que muda de manual pode violar PK
- **Local:** linhas 705–779, função `sincronizar_catalogo`
- **Problema:** a reconciliação é por manual: insere os documentos novos do
  manual A e só remove os obsoletos do próprio manual dentro da iteração dele.
  Se um documento (mesmo `id` UUID v5) "mudar" do manual B para o manual A e A
  for processado antes de B, o INSERT em A ocorre enquanto a linha ainda existe
  sob B → violação de PK no `flush()` da linha 779.
- **Impacto:** a reindexação aborta com `IntegrityError` no meio do lote.
- **A CONFIRMAR:** depende da fórmula do UUID v5 (§2.2). Se o UUID incluir o
  código do manual, mover arquivo entre manuais gera id NOVO e o problema não
  existe. Verificar em `catalog.py` (revisão adiante) onde o id é derivado.

### [MÉDIO — A CONFIRMAR] `sincronizar_catalogo` nunca remove manuais que saíram do acervo
- **Local:** linhas 687–781, função `sincronizar_catalogo`
- **Problema:** por decisão documentada, só os manuais presentes no payload são
  reconciliados — mas isso vale também para a reindexação COMPLETA: um manual
  retirado do acervo em disco não aparece no payload e permanece no catálogo
  da edição para sempre, com todos os seus documentos navegáveis.
- **Impacto:** navegação e busca por nome (`buscar_no_catalogo`) continuam
  oferecendo um manual que não existe mais; o download do PDF falharia.
  Para acervo aeronáutico, exibir publicação inexistente é problema de
  rastreabilidade.
- **A CONFIRMAR:** se `scripts/publicacoes/indexar.py` tem outro mecanismo para
  remoção de manuais (fora do escopo desta pasta). Se não tiver, falta uma
  operação "reconciliação completa" que apague manuais ausentes do payload.

### [MÉDIO — A CONFIRMAR] `sincronizar_fim_map` depende de `nome_pdf_de_procedimento` devolver MAIÚSCULAS
- **Local:** linhas 820–835, função `sincronizar_fim_map`
- **Problema:** `por_nome` é chaveado por `file_key.rsplit("/", 1)[-1].upper()`,
  e a resolução faz `por_nome.get(nome_pdf_de_procedimento(procedimento))` SEM
  `.upper()`. Se `nome_pdf_de_procedimento` devolver qualquer coisa fora de
  caixa alta, nenhum procedimento resolve documento (todos `documento_id=NULL`)
  silenciosamente — o retorno `com_documento` até denuncia, mas nada falha.
- **Correção sugerida:** aplicar `.upper()` também no lookup, tornando o
  contrato local em vez de implícito.
- **A CONFIRMAR:** verificar a implementação de `nome_pdf_de_procedimento` em
  `catalog.py` (revisão adiante).

### [BAIXO] `obter_ou_criar_edicao` ignora divergência de `status` da edição existente
- **Local:** linhas 127–131, função `obter_ou_criar_edicao`
- **Problema:** se a edição já existe, o parâmetro `status` é ignorado em
  silêncio — o chamador que pediu `VIGENTE` pode receber uma `ARQUIVADA` sem
  aviso.
- **Correção sugerida:** logar (ou documentar no docstring) que `status` só
  vale na criação.

### [BAIXO] `buscar_no_catalogo` não normaliza `termo` (sem `strip()`)
- **Local:** linha 648, função `buscar_no_catalogo`
- **Problema:** espaço acidental no início/fim entra no padrão LIKE
  (`"% amm%"`) e reduz resultados. `buscar_por_mensagem_fim` já faz
  `termo.strip()` — os dois deveriam concordar.
- **Correção sugerida:** `padrao = f"%{escape_like(termo.strip())}%"`.

### [BAIXO — A CONFIRMAR] Ativação não registra QUANDO a edição entrou em vigor
- **Local:** linhas 423–428, função `ativar_edicao`
- **Problema:** a ativação grava `publicado_por_id` mas nenhum timestamp da
  ativação; se `data_publicacao` for a data de CRIAÇÃO da edição (verificar em
  `models.py`), a trilha de auditoria responde "quem ativou" mas não "quando"
  — e para vigência de publicação técnica, o "quando" importa.
- **Correção sugerida:** gravar um `data_ativacao`/atualizar `data_publicacao`
  na ativação, ou registrar o evento em tabela de auditoria.

### [BAIXO — A CONFIRMAR] `listar_favoritos` sem eager loading — N+1 em potencial
- **Local:** linhas 1115–1126, função `listar_favoritos`
- **Problema:** devolve `PublicacaoFavorito` sem `selectinload` de
  `documento`/`avulsa`; se o router serializar título/manual de cada favorito,
  é uma query por linha.
- **A CONFIRMAR:** como `router.py` consome esta lista (revisão adiante).

**concluído: service.py (10 achados)**

---

## app/modules/publicacoes/router.py — revisado em 2026-08-08

### [ALTO] `_resolver_pdf`: fallback de fixtures anula a checagem de contenção (path traversal)
- **Local:** linhas 69–72, função `_resolver_pdf`
- **Problema:** o caminho principal valida `caminho.is_relative_to(base)` —
  exatamente a "defesa em profundidade" que o docstring promete ("um catálogo
  adulterado não deve virar leitura arbitrária de disco"). Mas quando essa
  checagem falha (ou o arquivo não existe), o código cai em
  `fixture_fallback = (Path("tests/fixtures/fim") / file_key).resolve()` e
  devolve o arquivo **sem nenhuma checagem de contenção**. Um `file_key`
  adulterado com `../../../../etc/passwd` (ou `..\..\` no Windows) falha a
  checagem principal, resolve para fora de `tests/fixtures/fim` e, se o
  arquivo existir, é servido.
- **Impacto:** leitura arbitrária de arquivo do servidor por usuário
  autenticado, condicionada a um catálogo adulterado — o cenário exato que a
  contenção existia para neutralizar. Agrava: o fallback roda em PRODUÇÃO
  (caminho relativo ao CWD do processo) para QUALQUER documento cujo arquivo
  suma do acervo, não só para o piloto FIM.
- **Correção sugerida:** aplicar a mesma contenção ao fallback
  (`fixture_base = Path("tests/fixtures/fim").resolve()` +
  `caminho.is_relative_to(fixture_base)`), e condicioná-lo a ambiente de
  teste/dev (settings), nunca produção.

### [ALTO — A CONFIRMAR] Filtro `documento_id` da busca pode nunca casar (formato do UUID)
- **Local:** linha 123, função `buscar`
- **Problema:** o filtro passa `str(documento_id)` — UUID canônico COM hífens
  — para `search.buscar`, que compara contra a coluna `document_id` do
  `catalog.db`. O próprio módulo documenta (service.py, `obter_documento`) que
  UUIDs em SQLite podem estar gravados "em hex sem hífens". Se o `catalog.db`
  gravar `document_id` sem hífens, a busca interna do viewer
  (`publicacoes_viewer.js`) devolve sempre 0 resultados, em silêncio.
- **A CONFIRMAR:** formato em que `catalog.py`/`indexar.py` gravam
  `document_id` no `catalog.db` e como `search.py` compara — verificado nas
  revisões de search.py e catalog.py, adiante.

### [MÉDIO — A CONFIRMAR] `buscar_avulsas`: snippet pode estourar em `ementa` nula
- **Local:** linhas 586–594, função interna `_item` de `buscar_avulsas`
- **Problema:** `fonte = a.ementa if texto.lower() in a.ementa.lower() else a.titulo`
  chama `.lower()` em `a.ementa` sem tratar `None`. Se `ementa` for coluna
  anulável (verificar em `models.py`), buscar com `texto=` numa avulsa sem
  ementa dá `AttributeError` → 500.
- **Correção sugerida:** `fonte = a.ementa if (a.ementa and texto.lower() in a.ementa.lower()) else a.titulo`.
- **A CONFIRMAR:** anulabilidade de `ementa` no model (revisão de models.py).

### [MÉDIO — A CONFIRMAR] `listar_favoritos` → `FavoritoOut.model_validate`: risco de lazy-load em contexto async
- **Local:** linha 724, função `listar_favoritos`
- **Problema:** `service.listar_favoritos` devolve ORM sem eager loading; se
  `FavoritoOut` (schemas.py) expuser atributos das relações `documento`/
  `avulsa`, `model_validate(..., from_attributes)` dispara lazy-load fora de
  greenlet (`MissingGreenlet`) ou N+1.
- **A CONFIRMAR:** campos de `FavoritoOut` na revisão de schemas.py.

### [BAIXO] `principal` chega por query string num endpoint multipart
- **Local:** linha 664, função `upload_anexo_avulsa`
- **Problema:** `principal: bool = False` sem `Form(...)` vira **query param**
  num endpoint que recebe `multipart/form-data`. O cliente que mandar
  `principal` como campo do form (o natural em upload) é ignorado em silêncio
  — o anexo nunca é marcado como principal.
- **Correção sugerida:** `principal: bool = Form(default=False)`.

### [BAIXO] `_item_da_edicao` recarrega a listagem inteira para devolver uma linha
- **Local:** linhas 512–528, função `_item_da_edicao`
- **Problema:** após ativar/arquivar, refaz `listar_edicoes` completo —
  agregação sobre todas as edições + um `is_file()` em thread por edição —
  para filtrar UMA linha em Python.
- **Impacto:** desperdício pequeno hoje (poucas edições); cresce linearmente
  com edições retidas.
- **Correção sugerida:** consulta escopada por `edicao_id` reutilizando a
  mesma projeção.

**concluído: router.py (6 achados)**

---

## app/modules/publicacoes/models.py — revisado em 2026-08-08

### [MÉDIO] Favoritos somem em silêncio na reindexação (`ondelete="CASCADE"`)
- **Local:** linhas 526–528, classe `PublicacaoFavorito`
- **Problema:** `documento_id` tem `ondelete="CASCADE"`. `sincronizar_catalogo`
  remove documentos que saíram do acervo (RN-09) — cada remoção apaga junto,
  sem aviso, os favoritos de todos os usuários naquele documento. O módulo
  tratou exatamente esse cenário com cuidado para a auditoria
  (`publicacoes_acessos` usa SET NULL + snapshot do título, achado B4), mas
  não para favoritos.
- **Impacto:** perda silenciosa de dado do usuário: a estrela some da lista
  sem qualquer indicação. Como o `id` do documento é UUID v5 por
  (edição, manual, file_key), até um documento renomeado/movido na MESMA
  edição gera id novo e mata o favorito.
- **Correção sugerida:** decisão consciente: ou manter CASCADE e aceitar
  (documentando), ou SET NULL + snapshot do título (padrão de
  `publicacoes_acessos`) para a UI mostrar "este favorito não está mais no
  acervo".

### [MÉDIO — A CONFIRMAR] `uq_manuais_fim_map_edicao_mensagem` × `sincronizar_fim_map` sem dedupe
- **Local:** linhas 290–294 (constraint) e service.py linhas 834–845
- **Problema:** a tabela exige UMA linha por (edição, mensagem), mas
  `sincronizar_fim_map` insere uma linha por PAR (mensagem, procedimento) sem
  deduplicar a entrada. Se o `fim.json` tiver a mesma mensagem apontando para
  dois procedimentos (ou um par repetido), o flush viola a constraint e a
  reindexação inteira do mapa aborta.
- **Impacto:** `IntegrityError` no meio da sincronização; como o DELETE da
  fatia da edição já rodou na mesma transação, o rollback é o que salva de
  perder o mapa — mas a reindexação falha sem mensagem de domínio.
- **A CONFIRMAR:** se o parser do `fim.json` (catalog.py, revisão adiante)
  garante mensagem única por edição.

### [BAIXO] Busca por mensagem do FIM não consegue usar o índice composto
- **Local:** linhas 300–305 (comentário) e service.py linha 903
- **Problema:** o comentário afirma que a `UniqueConstraint (edicao_id,
  mensagem)` "já cria o índice composto que a busca por mensagem usa", mas a
  busca aplica `func.upper(ManualFimMap.mensagem).LIKE` — função sobre a
  coluna impede o uso do índice na parte `mensagem` (resta o prefixo
  `edicao_id`).
- **Impacto:** varredura das linhas da edição a cada consulta — irrelevante
  com ~253 linhas, mas o comentário documenta uma otimização que não existe.
- **Correção sugerida:** gravar `mensagem` já normalizada em caixa alta (o
  domínio CAS é caixa alta) e comparar sem `upper()`, ou criar índice
  funcional.

### [BAIXO] FKs de `manuais_documentos` sem índice na coluna referenciadora
- **Local:** linhas 309–311 (`ManualFimMap.documento_id`) e 526–528
  (`PublicacaoFavorito.documento_id`)
- **Problema:** ambas as colunas são FK para `manuais_documentos.id` sem
  índice próprio. No Postgres, cada DELETE de documento (reindexação remove
  em lote) dispara verificação de FK que varre as tabelas referenciadoras
  inteiras, linha a linha.
- **Impacto:** performance de reindexação degrada com o crescimento de
  favoritos/fim_map; hoje pequeno.
- **Correção sugerida:** `index=True` nas duas colunas.

### Pendências de arquivos anteriores resolvidas por este arquivo
- **service.py / `obter_ou_criar_edicao` [ALTO]:** o índice parcial
  `uq_manuais_edicoes_vigente_unica` EXISTE (linhas 80–86) — o cenário do
  achado se sustenta. Nota: o default do model é `AGUARDANDO_ATIVACAO`
  (linha 111), o que reforça que o default `VIGENTE` do service destoa.
- **service.py / ativação sem timestamp [BAIXO → confirmado]:**
  `data_publicacao` tem `default=func.now()` na CRIAÇÃO (linhas 96–101);
  nenhuma coluna registra o momento da ativação. O achado se confirma.
- **router.py / snippet com `ementa` nula [MÉDIO → descartado]:** `ementa` é
  `nullable=False` (linhas 395–397). Não há bug — item retirado.
- **service.py / PK duplicada ao mover documento entre manuais [MÉDIO]:** o
  comentário do model (linha 212) diz que o UUID v5 é de
  (edição, manual, file_key) — se confirmado em catalog.py, mover documento
  entre manuais gera id NOVO e o cenário não ocorre. Confirmação final na
  revisão de catalog.py.

**concluído: models.py (4 achados)**

---

## app/modules/publicacoes/catalog.py — revisado em 2026-08-08

### [MÉDIO] `nome_pdf_de_procedimento` tem o prefixo `FIM1741_` cravado no código
- **Local:** linhas 392–400, função `nome_pdf_de_procedimento`
- **Problema:** o nome do PDF é montado como `f"FIM1741_{procedimento}-.PDF"`.
  A convenção foi medida no `FIM_1741` do acervo ATUAL — mas o módulo inteiro
  é desenhado para republicação anual (RN-08): quando a próxima edição vier
  com o FIM renumerado (ex.: `FIM_1850`), TODOS os lookups de
  `sincronizar_fim_map` deixam de casar e o mapa inteiro grava
  `documento_id = NULL`, silenciosamente (o retorno `com_documento: 0` é o
  único sinal, e nada o transforma em erro).
- **Impacto:** na primeira republicação com FIM renumerado, a resolução
  mensagem→PDF morre em silêncio: o mecânico volta a procurar o procedimento
  no papel.
- **Correção sugerida:** derivar o prefixo do código real do manual FIM da
  edição (já conhecido pelo indexador), ou ao menos fazer
  `sincronizar_fim_map` falhar/alertar alto quando `com_documento` cai a zero
  com documentos presentes na edição.

### [BAIXO] Colisão de basename dentro de um manual sobrescreve metadado em silêncio
- **Local:** linhas 322–332, função `carregar_indice_manual`
- **Problema:** `indice[nome_pdf] = MetadadoLucene(...)` — dois documentos do
  MESMO manual cujo `filename` resolva para o mesmo basename (capítulos
  diferentes com arquivo homônimo) fazem o último vencer, sem warning. O
  módulo trata a colisão análoga em `sincronizar_fim_map` com
  `logger.warning`; aqui ela passa despercebida.
- **Correção sugerida:** logar a colisão como lá.

### [BAIXO] `carregar_categorias` estoura com entrada TOML de nível superior que não seja tabela
- **Local:** linhas 423–429, função `carregar_categorias`
- **Problema:** `valores.get(...)` assume que todo valor de nível superior do
  TOML é tabela; uma linha solta como `versao = "1"` no arquivo faz
  `str.get` → `AttributeError`, derrubando a carga inteira — contra o espírito
  documentado da função ("manual desconhecido... em vez de derrubar o lote").
- **Correção sugerida:** `if not isinstance(valores, dict): continue` (com
  warning).

### Pendências de arquivos anteriores resolvidas por este arquivo
- **service.py / lookup do FIM em maiúsculas [MÉDIO → descartado]:**
  `nome_pdf_de_procedimento` termina em `.upper()` (linha 400) — o contrato
  de caixa alta se cumpre. Não há bug (mas o achado do prefixo `FIM1741_`
  acima é a fragilidade real dessa função).
- **service.py / PK duplicada ao mover documento entre manuais [MÉDIO → descartado]:**
  `documento_id_deterministico` inclui `manual_codigo` no input do UUID v5
  (linhas 287–289) — documento movido entre manuais gera id NOVO; o cenário
  de violação de PK não ocorre. (O documento "movido" vira remoção + inserção,
  o que reforça o achado dos favoritos em CASCADE, models.py.)
- **models.py / mensagem duplicada × UniqueConstraint [MÉDIO → mitigado]:**
  `carregar_fim_json` deduplica mensagens com warning (linhas 374–389) —
  desde que o indexador passe por ele (é a única fonte no módulo), a
  constraint não é violada. Permanece a observação de que
  `sincronizar_fim_map` em si não se defende se receber pares de outra origem.

**concluído: catalog.py (3 achados)**

---

## app/modules/publicacoes/schemas.py — revisado em 2026-08-08

### [MÉDIO — A CONFIRMAR] `PublicacaoAvulsaOut.anexos` pode disparar lazy-load em contexto async
- **Local:** linhas 304–321, classe `PublicacaoAvulsaOut`
- **Problema:** o schema tem `from_attributes=True` e o campo `anexos` mapeia a
  RELAÇÃO `PublicacaoAvulsa.anexos`. Se `avulsas.obter_avulsa`/`criar_avulsa`/
  `atualizar_avulsa` devolverem a entidade sem eager loading
  (`selectinload(PublicacaoAvulsa.anexos)`), o `model_validate` do router
  dispara lazy-load fora de greenlet → `MissingGreenlet`/500 (AsyncSession).
- **A CONFIRMAR:** eager loading nas funções de `avulsas.py` (próxima revisão
  após search.py, pela ordem de tamanho).

### [BAIXO] Campos de texto obrigatórios aceitam string vazia ou só espaços
- **Local:** linhas 261–278, classe `PublicacaoAvulsaCreate`
- **Problema:** `numero`, `emissor` e `titulo` têm `max_length` mas nenhum
  `min_length`/strip — `numero=""` (ou `"   "`) passa na validação e entra na
  chave de unicidade `(tipo, numero, ano)`. `ementa` tem `min_length=20`, mas
  20 espaços também passam.
- **Impacto:** registros com identificador vazio/ilegível no acervo de
  publicações — dado ruim difícil de corrigir depois (a chave única passa a
  ocupar o "slot" do tipo/ano).
- **Correção sugerida:** `min_length=1` + `str_strip_whitespace=True` no
  `model_config` (ou validator que faça strip antes do min_length).

### [BAIXO — A CONFIRMAR] `PublicacaoAvulsaUpdate` sem validação cruzada de status × substituição
- **Local:** linhas 281–291, classe `PublicacaoAvulsaUpdate`
- **Problema:** o schema aceita `status=SUBSTITUIDO` sem `substituida_por_id`,
  `substituida_por_id` sem mudar o status, e potencialmente auto-referência
  (`substituida_por_id` = a própria avulsa). O comentário do campo pede "usar
  junto", mas nada obriga.
- **A CONFIRMAR:** se `avulsas.atualizar_avulsa` valida essas combinações
  (revisão de avulsas.py).

### [BAIXO] `RespostaFim.total` é o tamanho da página, não o total de resultados
- **Local:** linha 73 (schema) e router.py linhas 180–181 e 208–209
- **Problema:** o router preenche `total=len(pares)` com `pares` já limitado
  por `limit` — diferente de `RespostaBusca.total`/`RespostaCatalogoBusca.total`,
  que trazem a contagem real. Com mais resultados que o limite, o cliente lê
  "total: 20" e não tem como saber que há mais.
- **Correção sugerida:** contagem separada (como nas outras respostas) ou
  documentar que é o tamanho da página devolvida.

### Pendências de arquivos anteriores resolvidas por este arquivo
- **router.py/service.py / N+1 e lazy-load em favoritos [MÉDIO/BAIXO → descartados]:**
  `FavoritoOut` (linhas 154–160) só expõe colunas escalares (`id`,
  `documento_id`, `avulsa_id`, `created_at`) — não há lazy-load nem N+1 no
  servidor. Observação de API que fica: a lista devolve só IDs, então exibir
  título/manual dos favoritos exige uma chamada extra por item no cliente —
  N+1 movido para HTTP, vale conferir como a UI consome.

**concluído: schemas.py (4 achados)**

---

## app/modules/publicacoes/search.py — revisado em 2026-08-08

### [BAIXO] Paginação sem desempate estável no `ORDER BY`
- **Local:** linhas 76–80 (`_SELECT_RESULTADOS`)
- **Problema:** `ORDER BY score ASC` sem critério de desempate. Páginas com o
  mesmo score BM25 (comum em documentos repetitivos) não têm ordem garantida
  entre execuções — com `LIMIT/OFFSET`, um resultado pode aparecer em duas
  páginas ou sumir de ambas ao paginar.
- **Correção sugerida:** `ORDER BY score ASC, p.rowid` (ou
  `p.document_id, p.page_number`) como desempate determinístico.

### [BAIXO] `_status_sincrono` pode estourar `FileNotFoundError` fora do tratamento
- **Local:** linha 263, função `_status_sincrono`
- **Problema:** `caminho.stat()` roda depois de fechar a conexão; se o arquivo
  for removido/trocado entre a abertura e o `stat()` (reindexação escreve os
  índices no mesmo diretório), sobe `FileNotFoundError` — `status_indice` só
  captura `IndiceIndisponivelError`, então vira 500 em `/api/status`.
- **Correção sugerida:** capturar `OSError` em `status_indice` (mesma resposta
  `disponivel: False`), ou fazer o `stat()` antes/dentro do bloco protegido.

### Pendências de arquivos anteriores resolvidas por este arquivo (+ indexar.py, leitura externa de contrato)
- **router.py / filtro `documento_id` com formato errado [ALTO → descartado]:**
  o contrato é hifenizado dos dois lados. `scripts/publicacoes/indexar.py`
  grava `str(doc_id)` — forma canônica COM hífens — em `documents.document_id`
  e `pages.document_id` (linhas 415–430 do script, comentário explícito), e o
  router passa `str(documento_id)`, idêntico. A busca interna do viewer casa.
  **Dependência registrada:** o contrato "sempre `str(uuid)` com hífens no
  catalog.db" está distribuído entre `search.buscar` (docstring), o router e o
  indexador externo — um teste de regressão cruzando os dois lados protegeria
  contra regressão silenciosa.

**concluído: search.py (2 achados)**

---

## app/modules/publicacoes/avulsas.py — revisado em 2026-08-08

### [MÉDIO] Cadeia de substituição com três lacunas de integridade
- **Local:** linhas 143–154, função `atualizar_avulsa`
- **Problema:** a validação de `status=SUBSTITUIDO` exige `substituida_por_id`
  e confere que o alvo existe/está ativo, mas:
  1. **auto-substituição não é bloqueada** — `substituida_por_id == avulsa_id`
     passa (o alvo "existe e está ativo": é ela mesma), criando um elo cego
     circular, exatamente o que o docstring diz querer evitar;
  2. `substituida_por_id` enviado SEM `status=SUBSTITUIDO` é ignorado em
     silêncio (só é aplicado dentro do branch do SUBSTITUIDO) — o cliente acha
     que gravou e nada mudou;
  3. voltar o status para `VIGENTE` não limpa `substituida_por_id` — fica uma
     publicação "vigente" apontando para a que a substituiu.
- **Impacto:** cadeia de substituição — o mecanismo de rastreabilidade de
  vigência do acervo B — pode ficar circular, incompleta ou contraditória.
- **Correção sugerida:** rejeitar `substituida_por_id == avulsa_id` (400);
  rejeitar `substituida_por_id` sem `status=SUBSTITUIDO` (400 explícito);
  limpar o ponteiro ao sair de SUBSTITUIDO.

### [MÉDIO] `criar_avulsa`: `aplicabilidade` inválida vira 500
- **Local:** linhas 102–106, função `criar_avulsa`
- **Problema:** os `aeronave_id` da aplicabilidade não são validados: um id
  inexistente viola a FK, e um id REPETIDO na lista viola a PK composta
  `(avulsa_id, aeronave_id)` — nos dois casos o `flush()` da linha 106 estoura
  `IntegrityError` fora do savepoint (que só cobre o flush da avulsa), virando
  500. Detalhe extra: a avulsa em si já foi gravada pelo flush anterior dentro
  do savepoint liberado — se o handler global não der rollback na transação,
  fica uma avulsa sem a aplicabilidade pedida.
- **Correção sugerida:** `set(dados.aplicabilidade)` para deduplicar + validar
  existência das aeronaves (ou capturar `IntegrityError` desse flush e
  devolver erro de domínio).

### [MÉDIO] `adicionar_anexo` grava TODO anexo como `application/pdf`
- **Local:** linha 267, função `adicionar_anexo`
- **Problema:** `storage.upload(conteudo, nome_original, "application/pdf")` —
  content-type cravado, mas o endpoint aceita "PDF escaneado **ou imagem**"
  (router.py, linha 663). Uma imagem JPEG/PNG sobe ao storage etiquetada como
  PDF; quando `obter_anexo_avulsa` redireciona para URL do R2, o navegador
  recebe `Content-Type: application/pdf` para um JPEG.
- **Impacto:** anexo de imagem abre quebrado (viewer de PDF tentando ler JPEG)
  quando servido pelo storage remoto.
- **Correção sugerida:** propagar o content-type real (o router tem
  `arquivo.content_type`, já validado por `validate_file_upload`).

### [MÉDIO] Invariante "um anexo principal" não é garantida
- **Local:** linhas 269–277, função `adicionar_anexo`
- **Problema:** marcar um anexo novo como `principal=True` não desmarca o
  principal anterior, e nenhuma constraint impede dois `principal=True` na
  mesma avulsa (models.py não tem índice único parcial para isso). O propósito
  do campo — "qual anexo abre por padrão quando há mais de um" — fica
  indefinido com dois marcados.
- **Correção sugerida:** no mesmo fluxo, `UPDATE ... SET principal = false`
  nos demais anexos da avulsa antes de gravar o novo; idealmente índice único
  parcial `(avulsa_id) WHERE principal`.

### [BAIXO] Upload ao storage antes do INSERT, sem compensação
- **Local:** linhas 266–277, função `adicionar_anexo`
- **Problema:** o arquivo sobe ao storage e só depois a linha é gravada; se o
  `flush`/commit falhar, o arquivo fica órfão no storage (não há delete
  compensatório nem job de limpeza referenciado no módulo).
- **Impacto:** lixo acumulando no R2/disco a cada falha; sem corrupção.
- **Correção sugerida:** `try/except` com `storage.delete(file_key)` na falha,
  ou rotina periódica de órfãos.

### [BAIXO] `obter_anexo` ignora o soft delete da avulsa
- **Local:** linhas 281–294, função `obter_anexo`
- **Problema:** filtra só por `anexo_id` + `avulsa_id`, sem conferir
  `PublicacaoAvulsa.ativo` — todos os outros caminhos passam por
  `obter_avulsa`, que esconde inativas. Quem guardou o link direto do anexo
  continua baixando o arquivo de uma publicação excluída.
- **Correção sugerida:** join/exists com `PublicacaoAvulsa.ativo.is_(True)`
  (ou chamar `obter_avulsa` antes, como `adicionar_anexo` faz).

### [BAIXO] `buscar_avulsas` sem desempate na ordenação
- **Local:** linha 237, função `buscar_avulsas`
- **Problema:** `ORDER BY data_recebimento DESC` sem tiebreaker — publicações
  recebidas no mesmo dia (comum: remessas em lote) não têm ordem estável entre
  páginas (mesmo problema apontado em search.py).
- **Correção sugerida:** acrescentar `.desc()` de `created_at` ou `id` como
  desempate.

### [BAIXO] PATCH não permite LIMPAR campos opcionais
- **Local:** linhas 153–162, função `atualizar_avulsa`
- **Problema:** a semântica `if campo is not None` impede zerar
  `sistema_ata_id` (classificação ATA errada não pode ser removida, só
  trocada). Com Pydantic, `model_fields_set` distingue "ausente" de "null
  explícito".
- **Correção sugerida:** usar `dados.model_fields_set` para aplicar `None`
  explícito.

### Pendências de arquivos anteriores resolvidas por este arquivo
- **schemas.py / lazy-load de `PublicacaoAvulsaOut.anexos` [MÉDIO → descartado]:**
  `obter_avulsa` carrega `anexos` com `selectinload` (linhas 119–121), e
  `criar_avulsa` devolve via `obter_avulsa` justamente por isso (comentário
  nas linhas 108–112); `atualizar_avulsa`/`excluir_avulsa` também partem de
  `obter_avulsa`. Não há lazy-load.
- **schemas.py / validação cruzada status × substituição [BAIXO → parcialmente confirmado]:**
  existe validação (SUBSTITUIDO exige o id), mas as lacunas viraram o achado
  MÉDIO "cadeia de substituição" acima.

**concluído: avulsas.py (7 achados)**

---

## app/modules/publicacoes/__init__.py — revisado em 2026-08-08

Nenhum achado relevante. (Apenas docstring de documentação do módulo, sem código.)

**concluído: __init__.py (0 achados)**

---

# SUMÁRIO FINAL — 2026-08-08

Correção de contagem: a seção de avulsas.py diz "7 achados", mas contém 8
(4 MÉDIO + 4 BAIXO).

## Contagem por severidade (após verificação cruzada entre arquivos)

| Severidade | Vigentes | Observação |
|---|---|---|
| CRÍTICO | 0 | — |
| ALTO | 2 | `_resolver_pdf` (router) e `obter_ou_criar_edicao` (service) |
| MÉDIO | 9 | inclui 1 "A CONFIRMAR" (manuais órfãos, depende de indexar.py) |
| BAIXO | 17 | melhorias, casos de borda e performance |
| Descartados na verificação | 7 | suspeitas registradas e depois refutadas com evidência (formato do `documento_id`, lazy-loads, `ementa` nula, PK ao mover documento, caixa do lookup FIM, N+1 de favoritos) |
| Mitigado | 1 | unique do fim_map × dedupe (coberto por `carregar_fim_json`) |

Por arquivo: service.py 10 · router.py 6 · models.py 4 · catalog.py 3 ·
schemas.py 4 · search.py 2 · avulsas.py 8 · __init__.py 0.

## Os 5 itens a tratar primeiro

1. **[ALTO] router.py `_resolver_pdf` — fallback de fixtures sem contenção.**
   É a única porta para leitura arbitrária de disco no módulo e anula uma
   defesa que o próprio código documenta. Correção pequena (aplicar
   `is_relative_to` ao fallback e restringi-lo a ambiente de teste).

2. **[ALTO] service.py `obter_ou_criar_edicao` — `IntegrityError` ambíguo +
   default `status=VIGENTE`.** No caminho do indexador, o erro real ("já
   existe edição vigente") vira `NoResultFound` enganoso. Trocar o default e
   distinguir a constraint violada.

3. **[MÉDIO] catalog.py `nome_pdf_de_procedimento` — prefixo `FIM1741_`
   cravado.** Bomba-relógio da republicação anual: a próxima edição com FIM
   renumerado zera a resolução mensagem→documento em silêncio. Derivar o
   prefixo do manual FIM real da edição e alarmar quando `com_documento` = 0.

4. **[MÉDIO] avulsas.py — cadeia de substituição (auto-referência, ponteiro
   órfão, campo ignorado).** É o mecanismo de vigência do acervo B; as três
   lacunas são baratas de fechar e evitam dado contraditório difícil de
   depurar depois.

5. **[MÉDIO] models.py `PublicacaoFavorito.documento_id` CASCADE — favoritos
   somem em silêncio a cada reindexação.** Perda silenciosa de dado de
   usuário; decidir explicitamente entre documentar o comportamento ou migrar
   para SET NULL + snapshot (padrão já adotado em `publicacoes_acessos`).

Menção honrosa: **service.py `sincronizar_catalogo` nunca remove manuais que
saíram do acervo** (MÉDIO, A CONFIRMAR em `scripts/publicacoes/indexar.py`) —
se confirmado, é o item de integridade de catálogo mais relevante depois dos
cinco acima.
