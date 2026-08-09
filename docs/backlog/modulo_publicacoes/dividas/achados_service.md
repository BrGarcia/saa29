# Achados de Revisão — `app/modules/publicacoes/service.py`

> Revisão focada neste arquivo, escopo contido a `app/modules/publicacoes/`. Segue o formato de
> `docs/backlog/revisor/concluido/achados_*.md` (classificação, eixo, correção proposta, risco de
> regressão).
>
> **Duas passadas.** A 1ª foi automatizada (`code-review`, nível `high`) e produziu os achados
> BUG-01, BUG-02, RISCO-01 e RISCO-02. A 2ª foi uma **leitura manual linha a linha do arquivo
> inteiro** (1.071 linhas), que confirmou os quatro anteriores e acrescentou BUG-03, RISCO-03 e
> quatro itens de melhoria/dúvida. Todo achado foi verificado contra o código real — linha exata,
> leitura do trecho completo e, quando o disparo depende de outro arquivo, leitura desse arquivo.
> Nenhum achado é especulativo sem mecanismo concreto de disparo identificado.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 08/08/2026
> **9/9 corrigidos.** Suíte completa: 662 testes, 0 falhas — novos testes em
> `test_publicacoes_catalogo_busca.py` (BUG-02, RISCO-03), `test_publicacoes_indice_edicao.py`
> (BUG-01), `test_publicacoes_edicoes.py` (BUG-01), `test_publicacoes_favoritos.py` (RISCO-01) e
> `test_publicacoes_busca.py` (BUG-03, RISCO-02). Uma migration nova
> (`b523f301e9f1_publicacoes_m5_fim_map_por_edicao`), validada em upgrade → downgrade → upgrade
> contra uma **cópia** do banco local (nunca o `var/db` real).
>
> **Decisões tomadas com o usuário antes de implementar** (respostas às "Perguntas para o
> desenvolvedor" abaixo): BUG-03 pela **opção 1** (escopar `manuais_fim_map` por edição, com
> migration); nenhum rótulo real em uso hoje foge do regex do BUG-01; DÚVIDA-01 resolvida como
> "defesa deliberada".
>
> **RISCO-01 seguiu o mesmo desenho do precedente** (`achados_calendario.md`, RISCO-03): SAVEPOINT
> + `except IntegrityError` como única fonte de verdade. Diferença de nuance entre as duas funções
> deste arquivo: em `favoritar_documento`/`favoritar_avulsa` o pre-check foi **removido** (mesma
> escolha do precedente — não há "get" nelas, só "criar se não existir"); em `obter_ou_criar_edicao`
> o `SELECT` foi **mantido** porque ali ele não é um pre-check de duplicidade, é o "get" do próprio
> get-or-create — o SAVEPOINT cobre só a corrida residual entre esse `SELECT` e o `INSERT`.
>
> **Achado fora do escopo original, descoberto ao implementar o RISCO-01:** `tests/conftest.py` não
> tinha o workaround padrão do SQLAlchemy para SAVEPOINT em SQLite/aiosqlite
> (`isolation_level=None` no `connect` + `BEGIN` explícito no evento `begin` — ver
> [docs do dialeto SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl)).
> Sem ele, `db.begin_nested()` "libera" a SAVEPOINT de um jeito que o driver confunde com commit
> implícito da transação inteira — um `session.rollback()` logo depois não desfaz nada, e a linha
> sobrevive para o próximo teste que reusa a mesma conexão do pool do engine de testes. Isso já
> valia para `calendario.service.create_event_type` (usa o mesmo `begin_nested()` desde a correção
> do RISCO-03 de `achados_calendario.md`), mas ficou invisível porque `EventType.name` não colide
> entre testes com nomes diferentes; aqui colidiu de cara porque `manuais_edicoes` tem um índice
> único parcial sobre `status`, que colide **entre rótulos diferentes**. Reproduzido isolado (fora
> da suíte) antes de aplicar a correção. Corrigido em `tests/conftest.py` com o recipe oficial do
> SQLAlchemy; suíte inteira (662 testes, todos os módulos) roda limpa depois — inclusive
> `tests/test_calendario.py`, que também tinha esse bug latente sem nenhum teste expondo.

---

### [BUG-01] `RotuloInvalidoError` não tratada em dois pontos, apesar de já existir o guard em `_indice_existe`

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `service.py:205` (`resolver_caminho_indice`) e `:335` (`ativar_edicao`)
- **Eixo:** Contrato / Robustez
- **Problema:** `caminho_indice_da_edicao(rotulo)` levanta `RotuloInvalidoError` quando `rotulo` não
  casa com `_RE_ROTULO_INDICE` (`^[A-Za-z0-9._-]{1,20}$`, linha 158). `_indice_existe` (linha 222)
  já sabe disso e captura a exceção, devolvendo `False`. Dois outros pontos chamam a mesma função
  **sem capturar**:
  - `resolver_caminho_indice` (linha 205) — chamada por `caminho_indice_vigente`, que alimenta
    **`GET /api/busca` e `GET /api/status`** (o próprio docstring diz isso, linha 234).
  - `ativar_edicao` (linha 335) — dentro da mensagem do `ConflitoNegocioError` que o bloco anterior
    (linha 332, via `_indice_existe`) monta exatamente para o caso "rótulo inválido/sem índice". O
    código já *sabe* que está tratando um rótulo problemático quando chega nessa linha, e mesmo
    assim chama a função desprotegida.
  - **Raiz:** `obter_ou_criar_edicao` (linha 84) nunca valida `rotulo` contra `_RE_ROTULO_INDICE`
    antes de persistir. O único lugar que valida é `caminho_indice_da_edicao`, chamado tarde demais
    (na hora de resolver o índice, não na de criar a edição).
- **Alcançável como?** `scripts/publicacoes/indexar.py --edicao <valor> --indice <caminho>` — ao
  passar `--indice` explicitamente, a linha `args.indice or service.caminho_indice_da_edicao(args.edicao)`
  (`indexar.py:603`) nunca chama `caminho_indice_da_edicao`, então a validação de `--edicao` nunca
  roda; `--edicao` é `argparse` de string livre, sem regex nem `choices` (`indexar.py:562-566`). O
  rótulo inválido é então persistido sem erro por `obter_ou_criar_edicao` (`indexar.py:493`).
- **Consequência:** se essa edição virar `VIGENTE`, **toda busca e todo status quebram com 500 não
  tratado** — não o erro limpo que o resto do módulo garante. E tentar *ativar* essa edição para
  corrigir também quebra com 500 em vez do 409 informativo.
- **Correção proposta:** validar `rotulo` contra `_RE_ROTULO_INDICE` dentro de
  `obter_ou_criar_edicao`, levantando erro de domínio claro **na criação** — mesma lógica do
  precedente `achados_calendario.md` BUG-01/BUG-02 ("resolver na raiz corrige os derivados"). Como
  reforço, envolver a linha 335 em `try/except RotuloInvalidoError` com mensagem genérica.
- **Risco de regressão:** BAIXO se a validação for só na criação. MÉDIO se também alterar
  `resolver_caminho_indice`, por tocar caminho quente de busca.
- **Precisa de teste antes?** SIM — (1) `obter_ou_criar_edicao` rejeita rótulo com espaço/`/`/>20
  chars; (2) edição com rótulo inválido não derruba `/api/busca` nem `/api/status`.
- **Status:** ✅ CORRIGIDO na raiz, como proposto: `obter_ou_criar_edicao` (`service.py`) valida
  contra `_RE_ROTULO_INDICE` antes de persistir. Reforços adicionais: `ativar_edicao` e
  `resolver_caminho_indice` agora envolvem `caminho_indice_da_edicao` em
  `try/except RotuloInvalidoError` (409/queda para o legado, em vez de 500); o regex trocou
  `^...$` por `^...\Z` (`$` casava antes de um `\n` final); `scripts/publicacoes/indexar.py`
  valida `--edicao` logo após o parse, antes do `--indice` explícito poder mascarar a validação.
  Testes: `test_obter_ou_criar_edicao_rejeita_rotulo_invalido`,
  `test_edicao_com_rotulo_invalido_nao_derruba_api_status`,
  `test_ativar_edicao_com_rotulo_invalido_retorna_409_nao_500`
  (`test_publicacoes_edicoes.py`); `test_rotulo_com_newline_final_e_recusado`,
  `test_rotulo_invalido_cai_para_o_legado_em_vez_de_derrubar_a_busca`
  (`test_publicacoes_indice_edicao.py`).

---

### [BUG-02] `buscar_no_catalogo` não escapa curingas de LIKE — único ponto do arquivo que quebra o padrão SEC-07

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `service.py:568-577`
- **Eixo:** Contrato / Busca
- **Problema:** `padrao = f"%{termo}%"` é usado cru em 5 colunas (`titulo`, `capitulo`, `file_key`
  do documento; `codigo`, `descricao_pt` do manual), todas via `.ilike(padrao)` **sem** `escape=`.
  O mesmo arquivo já resolve exatamente isto em dois outros lugares — `buscar_por_mensagem_fim`
  (linha 788) e `listar_fim_por_ata` (linha 818) — com `escape_like(termo)`
  (`app/shared/core/db_utils.py`, comentado como "SEC-07") + `.like(padrao, escape="\\")`.
  `buscar_no_catalogo` é o único dos três que não segue o padrão; nem importa `escape_like`.
- **Consequência:** `_` e `%` digitados viram curinga de SQL em vez de caractere literal.
  Especialmente ruim aqui porque o domínio é dominado por nomes com `_` (`AMM_PART2_1651`,
  `CHAPTER_21` — ver `01_achados_do_acervo.md`). Buscar `CHAPTER_21` já tem esse comportamento
  hoje: cada `_` casa qualquer caractere, então o usuário recebe resultados a mais do que o termo
  literal pediria — silenciosamente, sem erro, contradizendo o docstring da função ("sem sintaxe de
  operador para o usuário aprender"). Não é vazamento entre edições (o filtro
  `Manual.edicao_id == vigente.id` continua valendo), é **precisão de busca errada**.
- **Correção proposta:** o padrão já estabelecido no mesmo arquivo:
  ```python
  from app.shared.core.db_utils import escape_like
  padrao = f"%{escape_like(termo)}%"
  # ... e cada .ilike(padrao) vira .ilike(padrao, escape="\\")
  ```
- **Risco de regressão:** BAIXO — padrão mecânico já em produção em duas outras funções do mesmo
  arquivo; só estreita o casamento, nunca amplia.
- **Precisa de teste antes?** SIM — nenhum teste em `tests/unit/test_publicacoes_catalogo_busca.py`
  busca termo com `_`/`%` verificando tratamento literal.
- **Status:** ✅ CORRIGIDO exatamente como proposto — `escape_like(termo)` + `escape="\\"` nas 5
  colunas. Testes: `test_busca_trata_sublinhado_como_literal_nao_curinga`,
  `test_busca_trata_porcentagem_como_literal_nao_curinga`
  (`test_publicacoes_catalogo_busca.py`).

---

### [BUG-03] `sincronizar_fim_map` apaga o mapa do FIM inteiro e o reaponta para a edição *indexada por último*, não para a VIGENTE

- **Classificação:** BUG
- **Severidade:** MÉDIA
- **Arquivo:** `service.py:704-748` (em especial a linha 732, `delete(ManualFimMap)` sem `WHERE`)
- **Eixo:** Banco / Consistência entre edições
- **Achado da 2ª passada (leitura manual).**
- **Problema:** `manuais_fim_map` **não tem coluna de edição** (`models.py`: só `id`, `mensagem`,
  `procedimento`, `documento_id`) — é uma tabela global. `sincronizar_fim_map` recebe uma `edicao`,
  executa `await db.execute(delete(ManualFimMap))` — **sem filtro, apaga a tabela inteira** — e
  repopula resolvendo `documento_id` contra os documentos *daquela* edição (linhas 718-724). O
  resultado é que a tabela sempre reflete **a última edição indexada**, que não é necessariamente
  a `VIGENTE`.
- **Alcançável como?** É o **fluxo normal de publicação**, não um caso exótico. Indexar/publicar
  uma edição nova (`indexar.py --edicao 2027`, que chama `sincronizar_fim_map` em
  `indexar.py:529`) cria essa edição como `AGUARDANDO_ATIVACAO` enquanto a anterior segue
  `VIGENTE`. A partir desse instante e **até alguém ativar a nova**, o mapa do FIM aponta para os
  documentos da edição nova, enquanto a busca e a navegação servem a vigente. O mesmo vale para
  reindexar uma edição antiga para corrigir metadado.
- **Consequência:** `GET /api/fim` e `GET /api/fim/por-ata/{ata}` (este alimenta o bloco
  "Procedimentos FIM do ATA XX" no detalhe da pane, M3 tarefa 1) devolvem `doc_id`/`viewer_url`
  apontando para documentos de uma edição diferente da que todo o resto do módulo está servindo.
  **Mitigação parcial que já existe:** ao abrir esse documento, o viewer detecta que ele não é da
  edição vigente e mostra a faixa "Esta é uma REVISÃO ANTERIOR do documento" (via
  `obter_equivalente_vigente`/`DocumentoViewerOut.edicao_vigente`) — então o erro é **visível ao
  usuário**, não totalmente silencioso. Ainda assim é confuso (o mecânico pediu o procedimento
  vigente e recebeu um aviso de revisão anterior) e, no caso do bloco na pane, o link leva para
  fora da edição em vigor sem que ninguém tenha pedido isso.
- **Correção proposta:** duas opções, com trade-off explícito:
  1. **Escopar a tabela por edição** — acrescentar `edicao_id` a `manuais_fim_map` (migration),
     trocar o `delete` global por `delete(...).where(ManualFimMap.edicao_id == edicao.id)`, e
     filtrar as leituras (`buscar_por_mensagem_fim`, `listar_fim_por_ata`) pela edição vigente.
     Mais fiel ao modelo do resto do módulo (tudo é escopado por edição) e à retenção de 2 edições
     online; custa uma migration.
  2. **Resolver `documento_id` na leitura, não na indexação** — guardar só
     `(mensagem, procedimento)` e resolver o documento por `file_key` contra a edição vigente na
     hora da consulta. Elimina a classe inteira de bug (nunca há FK "velha" gravada), mas move
     trabalho para o caminho quente e muda o contrato de duas funções de leitura.
- **Risco de regressão:** MÉDIO nas duas opções — muda o que `GET /api/fim` devolve em instalações
  onde a divergência já existe hoje (nesse caso, o comportamento *deve* mudar).
- **Precisa de teste antes?** SIM — teste que indexa a edição A, ativa A, indexa B (sem ativar) e
  afirma que `buscar_por_mensagem_fim` continua resolvendo para documentos de **A**. Nenhum teste
  atual exercita duas edições contra o mapa do FIM (`test_publicacoes_favoritos.py:238` e
  `test_publicacoes_busca.py:703` usam uma edição só).
- **Status:** ✅ CORRIGIDO pela **opção 1** (escopar por edição, decisão tomada com o usuário).
  `ManualFimMap` ganhou `edicao_id` (FK CASCADE) e a `UniqueConstraint` de `mensagem` virou
  `(edicao_id, mensagem)` — achado que o próprio texto do achado não tinha registrado: sem isso, a
  mesma mensagem não poderia existir em duas edições retidas ao mesmo tempo, que é o estado normal
  entre uma publicação e a próxima. Migration `b523f301e9f1_publicacoes_m5_fim_map_por_edicao`
  (backfill pela edição real do documento referenciado quando `documento_id` existe; pela VIGENTE
  mais recente quando não existe; descarta o que sobrar sem VIGENTE nenhuma). `sincronizar_fim_map`
  agora faz `delete(ManualFimMap).where(edicao_id == edicao.id)` em vez de `delete(ManualFimMap)`
  global. `buscar_por_mensagem_fim`, `listar_fim_por_ata` e `status_do_catalogo` passaram a filtrar
  pela edição VIGENTE. Migration validada em upgrade → downgrade → upgrade contra uma cópia do
  banco local (1.377 linhas, backfill 100% sem NULL). Teste:
  `test_indexar_edicao_nao_vigente_nao_apaga_o_mapa_da_vigente`
  (`tests/integration/test_publicacoes_busca.py`).

---

### [RISCO-01] `favoritar_documento`/`favoritar_avulsa`: checagem-então-ação sobre `UniqueConstraint`, mesmo padrão do RISCO-03 já corrigido em `calendario`

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `service.py:1001-1028` (`favoritar_documento`), `:1031-1052` (`favoritar_avulsa`) e
  — mesma classe, alcance muito menor — `:84-105` (`obter_ou_criar_edicao`)
- **Eixo:** Concorrência
- **Problema:** as funções fazem `SELECT` pelo par e só inserem se `existente is None` — sem
  `try/except IntegrityError` nem `SAVEPOINT` em volta do `db.add()`/`flush()`.
  `PublicacaoFavorito` tem duas `UniqueConstraint` cobrindo exatamente esses pares (`models.py`,
  achado B1). Entre o `SELECT` e o `flush()`, duas requisições concorrentes para o mesmo par passam
  as duas pela checagem — a segunda estoura `IntegrityError` não capturado.
  `obter_ou_criar_edicao` tem o mesmo formato sobre `ManualEdicao.rotulo` (`unique=True`), mas só é
  chamada por script offline de execução única — registrada aqui por ser o mesmo padrão, não por
  ter alcance comparável.
- **Consequência:** o docstring de `favoritar_documento` promete explicitamente "Idempotente:
  favoritar duas vezes o mesmo documento devolve o favorito já existente em vez de violar a
  `UniqueConstraint`" — a promessa só vale em série. Um duplo toque na estrela de favorito (gesto
  comum em UI de toque) pode disparar duas requisições quase simultâneas e a segunda recebe 500 em
  vez do comportamento idempotente documentado.
- **Correção proposta:** mesmo remédio já aplicado em `calendario` (RISCO-03,
  `achados_calendario.md`): envolver `db.add()`/`flush()` em `db.begin_nested()` (SAVEPOINT) e
  capturar `IntegrityError`, recuperando e devolvendo o favorito existente — cobre o caminho comum
  e a corrida real com o mesmo código, sem um segundo SELECT.
- **Risco de regressão:** BAIXO — só afeta o caminho que hoje quebra.
- **Precisa de teste antes?** SIM — teste que force a corrida (inserir a linha concorrente antes do
  `flush()`, ou duas coroutines) ou que provoque `IntegrityError` diretamente.
- **Status:** ✅ CORRIGIDO com o mesmo desenho do precedente (`achados_calendario.md`, RISCO-03):
  `favoritar_documento`/`favoritar_avulsa` chamam um helper `_favoritar` novo que faz
  `db.begin_nested()` + `db.add()`/`flush()` e captura `IntegrityError`, devolvendo o favorito
  já existente — pre-check removido, SAVEPOINT como única fonte de verdade. Mesmo padrão aplicado a
  `obter_ou_criar_edicao`, mas mantendo o `SELECT` inicial (ali ele é o "get" do get-or-create, não
  um pre-check redundante). Achado real ao implementar: `tests/conftest.py` não suportava SAVEPOINT
  corretamente com SQLite/aiosqlite (ver nota no topo deste arquivo) — corrigido antes de fechar
  este item, senão os testes de corrida vazavam dados entre si. Testes:
  `test_favoritar_documento_apos_corrida_devolve_o_existente`,
  `test_favoritar_avulsa_apos_corrida_devolve_o_existente` (`test_publicacoes_favoritos.py`).

---

### [RISCO-02] `sincronizar_fim_map` chaveia por basename sem qualificador de manual/capítulo e sem ordenação determinística

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `service.py:718-730`
- **Eixo:** Banco / Correção de dados
- **Problema:** `por_nome` é construído com
  `{file_key.rsplit("/", 1)[-1].upper(): doc_id for doc_id, file_key in documentos}` a partir de
  **todos** os documentos da edição (não só do manual FIM), sem `ORDER BY` na query que produz
  `documentos` (linhas 719-724). Dict comprehension com chaves repetidas mantém só a **última**
  ocorrência — e "última" depende da ordem que o banco devolve, que sem `ORDER BY` não é garantida
  nem estável entre execuções.
- **Consequência:** dois documentos da mesma edição com o mesmo nome de arquivo (capítulos
  diferentes, ou manuais diferentes — o código não impede) fazem `manuais_fim_map.documento_id`
  apontar silenciosamente para o documento "errado", e qual dos dois pode mudar entre
  reindexações. Não medido contra o acervo real de 5.724 documentos nesta sessão — é um risco
  estrutural (o código não se defende do caso), não uma colisão observada.
- **Correção proposta:** qualificar a chave por manual (`f"{manual.codigo}/{basename}"`) e/ou
  adicionar `ORDER BY` estável, para que uma colisão real seja ao menos determinística; idealmente
  logar aviso quando uma chave for sobrescrita, para a colisão aparecer em log em vez de silenciosa.
- **Risco de regressão:** BAIXO — defensivo; só muda comportamento se uma colisão real já existir.
- **Precisa de teste antes?** SIM — teste sintético com dois documentos de mesmo basename em
  manuais/capítulos diferentes.
- **Nota:** se a correção do **BUG-03** seguir a opção 1 (escopar por edição), vale resolver os
  dois juntos — mexem no mesmo bloco de código.
- **Status:** ✅ CORRIGIDO junto com o BUG-03, como a nota acima antecipava. A query de
  `documentos` em `sincronizar_fim_map` ganhou `ORDER BY Manual.codigo, ManualDocumento.file_key`
  e o dict comprehension virou laço explícito com `logger.warning` quando uma chave é sobrescrita —
  colisão determinística e visível em log, não mais silenciosa. Teste:
  `test_sincronizar_fim_map_colisao_de_basename_e_deterministica`
  (`tests/integration/test_publicacoes_busca.py`).

---

### [RISCO-03] `limit` não é clampado em duas funções, contrariando o propósito declarado de `LIMITE_MAXIMO_LISTAGEM`

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `service.py:512-548` (`listar_documentos_do_manual`) e `:551-599` (`buscar_no_catalogo`)
- **Eixo:** Contrato / Consistência interna
- **Achado da 2ª passada (leitura manual).**
- **Problema:** `LIMITE_MAXIMO_LISTAGEM = 100` (linha 49) tem um comentário que declara sua razão
  de existir: *"Existe além dos `le=` do FastAPI porque o service também é chamado por scripts, que
  não passam por Query"*. Duas funções do arquivo honram isso — `buscar_por_mensagem_fim`
  (linha 787) e `listar_fim_por_ata` (linha 817) fazem `limit = min(limit, LIMITE_MAXIMO_LISTAGEM)`.
  Mas `listar_documentos_do_manual` e `buscar_no_catalogo` passam `limit` direto para `.limit()`
  sem clampar, e nenhuma das duas guarda `offset` contra valor negativo.
- **Consequência:** **nenhuma via HTTP** — todos os endpoints que chamam essas funções declaram
  `Query(..., le=100)` (`router.py:326`, `:364`), então o FastAPI já rejeita valores maiores. O
  risco é exatamente o que o comentário da constante antecipou: um script ou uma chamada interna
  futura que não passe por `Query` pode pedir `limit=1_000_000` e materializar o acervo inteiro em
  memória. É inconsistência com a invariante declarada pelo próprio arquivo, não um bug ativo.
- **Correção proposta:** aplicar `limit = min(limit, LIMITE_MAXIMO_LISTAGEM)` e
  `offset = max(0, offset)` nas duas funções, como as outras duas já fazem.
- **Risco de regressão:** BAIXO — nenhum chamador atual pede mais que 100.
- **Precisa de teste antes?** NÃO (mudança defensiva), mas um teste chamando o service direto com
  `limit=10_000` e afirmando ≤ 100 trava a invariante.
- **Status:** ✅ CORRIGIDO em `listar_documentos_do_manual` e `buscar_no_catalogo`
  (`limit = max(1, min(limit, LIMITE_MAXIMO_LISTAGEM))`, `offset = max(0, offset)`), e reforçado em
  `buscar_por_mensagem_fim`/`listar_fim_por_ata`, que já tinham o teto (`min`) mas não o piso — sem
  ele, `limit=-1` significa "sem limite" no SQLite, o oposto da invariante que a constante existe
  para garantir. Teste: `test_busca_no_catalogo_limita_a_limite_maximo_listagem`
  (`test_publicacoes_catalogo_busca.py`).

---

### [MELHORIA-01] Imports locais sem necessidade de ciclo, e a mesma exceção acessada por dois caminhos no mesmo arquivo

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `service.py:785`, `:815` (`escape_like`); `:1009`, `:1056` (`domain_exc`)
- **Eixo:** Arquitetura / Legibilidade
- **Achado da 2ª passada (leitura manual).**
- **Problema:** o arquivo importa `EntidadeNaoEncontradaError` no topo (linha 42) e a usa
  diretamente nas linhas 255 e 466 — mas nas linhas 1012 e 1067 usa
  `domain_exc.EntidadeNaoEncontradaError`, com `from app.shared.core import exceptions as domain_exc`
  importado **dentro da função**. É a mesma exceção, alcançada por dois caminhos, um deles com
  import local. O mesmo vale para `escape_like`, importado localmente duas vezes (785, 815).
  **Verificado:** `app/shared/core/db_utils.py` não tem nenhum import (arquivo de funções puras) e
  `app/shared/core/exceptions.py` já está no topo — **nenhum dos dois tem risco de ciclo**, ao
  contrário dos imports locais de `catalog` (716) e `avulsas` (1034), que são de dentro do próprio
  módulo e têm justificativa real.
- **Consequência:** nenhuma funcional. Ruído de leitura e uma pegadinha para quem for adicionar uso
  novo de `EntidadeNaoEncontradaError` e não souber qual dos dois estilos seguir.
- **Correção proposta:** subir `escape_like` para o topo, e padronizar o acesso à exceção num
  caminho só (o import do topo já existente).
- **Risco de regressão:** BAIXO — mecânico.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO como proposto — `escape_like` subiu para o topo (removidos os dois
  imports locais); `favoritar_documento` e `remover_favorito` usam o `EntidadeNaoEncontradaError`
  já importado no topo, sem o `domain_exc` local. Mecânico, sem teste dedicado (coberto pela suíte
  existente).

---

### [MELHORIA-02] `listar_edicoes` faz I/O de disco sequencial dentro de list comprehension

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `service.py:282-295`
- **Eixo:** Performance
- **Achado da 2ª passada (leitura manual).**
- **Problema:** `"indice_disponivel": await _indice_existe(edicao.rotulo)` está dentro de uma list
  comprehension, e `_indice_existe` faz `await asyncio.to_thread(caminho.is_file)`. Os `await`
  numa comprehension são **sequenciais**: para N edições são N despachos de thread em série, não em
  paralelo.
- **Consequência:** desprezível hoje — `PUBLICACOES_EDICOES_RETIDAS = 2`, então são 2–3 `stat()`
  por chamada de uma tela de gerência raramente aberta. Registrado por ser um padrão que escala mal
  se a retenção crescer, e porque a alternativa é trivial.
- **Correção proposta:** `asyncio.gather(*(_indice_existe(e.rotulo) for e, _, _ in linhas))` antes
  da comprehension, e indexar o resultado. Ou deixar como está e registrar a decisão — com 2
  edições, `gather` é complexidade sem ganho medível.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO como proposto — `asyncio.gather` sobre os rótulos antes da comprehension,
  resultado indexado por posição (`zip`). Sem teste dedicado (comportamento observável idêntico,
  coberto pela suíte existente de `listar_edicoes`).

---

### [MELHORIA-03] `medir_duplicacao_entre_edicoes` calcula contagens que nunca usa e faz interseção em Python

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `service.py:866-893`
- **Eixo:** Performance / Simplificação
- **Achado da 2ª passada (leitura manual).**
- **Problema:** `hashes_vigente` é montado como `dict` de `hash → count` por um
  `GROUP BY hash_sha256` (linhas 866-873), mas o **valor da contagem nunca é lido** — a linha 893
  (`sum(1 for h in hashes_anteriores if h in hashes_vigente)`) só testa pertencimento da chave. O
  `func.count()` e o `GROUP BY` são trabalho desperdiçado. Além disso, `hashes_anteriores`
  materializa **todos** os hashes da edição anterior em memória Python (potencialmente 5.724
  strings) para fazer uma interseção que o banco faria com um `JOIN`/`EXISTS`.
- **Consequência:** nenhuma correção — o número devolvido está certo. É custo de memória e CPU
  desnecessário num endpoint `AdminRequired` de uso esporádico. A query de contagem total
  (linhas 874-883) também varre `manuais_documentos` inteira sem `WHERE`, usando `FILTER` para
  separar as duas edições — funciona, mas cresce com o total de edições retidas.
- **Correção proposta:** trocar por um único `SELECT COUNT(*)` com `EXISTS`/`IN` entre as duas
  edições, deixando a interseção no banco; ou, no mínimo, trocar o `dict` com `GROUP BY` por um
  `set` de `SELECT DISTINCT hash_sha256`.
- **Risco de regressão:** BAIXO — mesmo número, menos trabalho. Testar contra o caso já coberto.
- **Precisa de teste antes?** NÃO (já há teste do valor devolvido em
  `tests/unit/test_publicacoes_edicoes.py`), mas confirmar que o teste existente cobre o caso com
  duplicatas reais antes de mexer.
- **Status:** ✅ CORRIGIDO como proposto — `SELECT COUNT(*)` com `hash_sha256.in_(subquery da
  vigente)` substitui o `GROUP BY`+`dict` (contagem descartada) e a materialização de todos os
  hashes da anterior em Python; a query de totais ganhou
  `WHERE Manual.edicao_id.in_((vigente.id, anterior.id))`. Correção: o teste que trava o valor
  devolvido está em `tests/unit/test_publicacoes_favoritos.py:269-301`
  (`test_duplicacao_conta_hashes_repetidos_entre_vigente_e_anterior`), não em
  `test_publicacoes_edicoes.py` como o achado original apontava — confirmado que já cobre
  duplicata real e continua passando sem alteração.

---

### [DÚVIDA-01] Defesa assimétrica contra "duas edições VIGENTE" entre duas funções do mesmo arquivo

- **Classificação:** DÚVIDA
- **Severidade:** —
- **Arquivo:** `service.py:137-146` (`obter_edicao_vigente`) vs. `:123-134` (`obter_equivalente_vigente`)
- **Eixo:** Banco / Robustez
- **Achado da 2ª passada (leitura manual).**
- **Problema:** `obter_edicao_vigente` se defende explicitamente da possibilidade de haver mais de
  uma edição `VIGENTE`: `.order_by(data_publicacao.desc()).limit(1)` antes de
  `scalar_one_or_none()`. Já `obter_equivalente_vigente` filtra por `ManualEdicao.status == VIGENTE`
  **sem `limit`** e chama `scalar_one_or_none()` — se houvesse duas vigentes, levantaria
  `MultipleResultsFound` (500). O índice único parcial `uq_manuais_edicoes_vigente_unica`
  (`models.py:80-86`) torna as duas defesas teoricamente desnecessárias; o fato de uma existir e a
  outra não sugere que a primeira foi escrita antes do índice (ou por desconfiança dele).
- **Consequência:** nenhuma enquanto o índice parcial estiver em vigor nos dois dialetos. A dúvida
  é sobre intenção: o `.limit(1)` é cinto-e-suspensório deliberado (e então
  `obter_equivalente_vigente` deveria ter o mesmo) ou resíduo pré-índice (e então poderia sair)?
- **Correção proposta:** nenhuma até decisão. Se "defesa deliberada", alinhar
  `obter_equivalente_vigente`; se "resíduo", remover o `.limit(1)` e documentar que o índice é a
  única garantia.
- **Risco de regressão:** BAIXO em qualquer direção.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ RESOLVIDA — decisão: "defesa deliberada". `obter_equivalente_vigente` ganhou o
  mesmo `.limit(1)` de `obter_edicao_vigente`, com comentário explicando que o índice único parcial
  é a garantia primária e o `.limit(1)` é cinto-e-suspensório proposital, não resíduo.

---

## Observações que não viraram achado

Registradas para não serem "redescobertas" numa próxima revisão:

- **`registrar_acesso` depende de eager-load feito pelo chamador** (`service.py:975`,
  `documento.manual.edicao_id`). Se receber um `ManualDocumento` que não veio de `obter_documento`
  — por exemplo um de `listar_documentos_do_manual`, que **não** faz `selectinload` — o acesso a
  `.manual` dispara lazy load em contexto async e falha com `MissingGreenlet`. **Não é achado
  porque:** o único chamador (`router.py:432`) já obtém o documento por `obter_documento`, e o
  docstring da função declara a exigência explicitamente. É um contrato documentado, não um bug —
  mas é frágil se surgir um segundo chamador.
- **`listar_favoritos` (`service.py:987`) não tem limite algum.** Sem paginação nem clamp. Não é
  achado porque o volume é limitado pelo comportamento do próprio usuário (favoritos são criados um
  a um, manualmente) e não há caminho para inflá-lo em massa.
- **`sincronizar_catalogo` carrega todos os documentos de um manual como objetos ORM completos**
  (`service.py:650-657`) — até 1.148 para `AMM_PART2_1651`. Não é achado porque roda offline, no
  indexador, onde memória não é o gargalo (o gate do M4 mede RSS do *worker web*, não do script).

---

## Resumo

- Total de achados: **9** (era 4 na 1ª passada)
- BUG: 3 (MÉDIA: 3)
- RISCO: 3 (MÉDIA: 2, BAIXA: 1)
- MELHORIA: 3 (BAIXA: 3)
- DÚVIDA: 1
- **Corrigidos: 9/9** — sessão de correção em 08/08/2026, suíte completa (662 testes) verde. Ver
  bloco no topo do arquivo para o resumo das decisões de desenho.

### Ordem sugerida de correção

1. **BUG-02** — menor esforço, maior retorno imediato: é o padrão já estabelecido no mesmo arquivo,
   afeta busca que usuários usam hoje, e a correção é mecânica.
2. **BUG-03 + RISCO-02** — juntos, por mexerem no mesmo bloco. Exige decisão de desenho antes
   (escopar por edição vs. resolver na leitura) e, na opção 1, uma migration.
3. **RISCO-01** — tem precedente pronto para copiar (`calendario`, RISCO-03).
4. **BUG-01** — barato se ficar só na validação em `obter_ou_criar_edicao`.
5. **RISCO-03 + MELHORIA-01** — mecânicos, cabem numa passada de limpeza junto de qualquer um dos
   acima.
6. **MELHORIA-02, MELHORIA-03, DÚVIDA-01** — só se alguém já estiver no arquivo por outro motivo.

## Metodologia

- **1ª passada:** revisão automatizada (`code-review`, nível `high`), 5 candidatos; 1 descartado por
  duplicar a causa raiz do BUG-01 (os dois pontos citados são os mesmos dois call sites já cobertos).
- **2ª passada:** leitura manual do arquivo inteiro (1.071 linhas), função por função. Confirmou os
  4 achados anteriores sem alteração de severidade e acrescentou BUG-03, RISCO-03, MELHORIA-01/02/03
  e DÚVIDA-01 — todos em categorias que a revisão automatizada não cobriu (consistência entre
  edições, invariantes declaradas pelo próprio arquivo, custo de I/O, convenção de import).
- Cada achado foi verificado contra o código atual (linha exata, leitura do trecho completo) e,
  quando o disparo depende de outro arquivo, com leitura desse arquivo. Nenhum achado é
  especulativo sem mecanismo concreto identificado.
- **Escopo:** só `app/modules/publicacoes/service.py`. Os demais arquivos do módulo
  (`router.py`, `search.py`, `catalog.py`, `avulsas.py`, `models.py`, `schemas.py`) não foram
  revisados — só lidos na medida em que `service.py` os referenciava.

## Arquivos lidos para confirmar contexto (sem revisão própria)

- `app/shared/core/db_utils.py` — confirma o padrão SEC-07 do BUG-02 e a ausência de ciclo do
  MELHORIA-01.
- `app/modules/publicacoes/models.py` — `PublicacaoFavorito` (2 `UniqueConstraint`, RISCO-01),
  `ManualFimMap` (ausência de `edicao_id`, BUG-03), `uq_manuais_edicoes_vigente_unica` (DÚVIDA-01).
- `app/modules/publicacoes/router.py` — clamps `le=100` que hoje encobrem o RISCO-03; único
  chamador de `registrar_acesso`.
- `scripts/publicacoes/indexar.py` — alcançabilidade do BUG-01 (`--edicao`/`--indice`) e do BUG-03
  (chamada de `sincronizar_fim_map` no fluxo de publicação).

## Perguntas para o desenvolvedor — respondidas em 08/08/2026

- **BUG-03 (a mais importante):** qual das duas opções de correção? Escopar `manuais_fim_map` por
  edição custa uma migration mas mantém o modelo coerente com o resto do módulo; resolver na
  leitura elimina a classe de bug mas muda duas funções de leitura e move trabalho para o caminho
  quente.
  **Resposta:** opção 1 (escopar por edição). Implementado com a migration
  `b523f301e9f1_publicacoes_m5_fim_map_por_edicao`.
- **BUG-01:** algum rótulo real em uso foge de `[A-Za-z0-9._-]{1,20}`? Se não, validar em
  `obter_ou_criar_edicao` é sem risco prático.
  **Resposta:** não — todos os rótulos em uso (`piloto-fim`, `teste-fim`, `2027`,
  `edicao-anterior`, …) já respeitam o regex. Validação aplicada sem risco prático confirmado.
- **RISCO-02:** vale medir contra o acervo real (34 manuais, 5.724 documentos) se já existe colisão
  de basename, antes de escolher entre `ORDER BY` defensivo e qualificar a chave por manual?
  **Resposta:** não medido nesta sessão — aplicada a correção defensiva mínima (`ORDER BY` + log de
  aviso), que não exige decidir isso agora: se uma colisão real existir, ela aparece em log em vez
  de silenciosa, e qualificar a chave por manual fica como melhoria futura se o log acender.
- **DÚVIDA-01:** o `.limit(1)` de `obter_edicao_vigente` é defesa deliberada contra falha do índice
  parcial, ou resíduo de antes de o índice existir?
  **Resposta:** defesa deliberada — `obter_equivalente_vigente` foi alinhada com o mesmo `.limit(1)`.
