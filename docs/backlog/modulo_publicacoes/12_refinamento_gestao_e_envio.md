# Refinamento — Gestão e Envio das Publicações a partir do Disco Completo

> **Data:** 2026-08-10 · **Escopo:** especificação executável, sem código nesta entrega.
>
> Este documento traduz os achados de
> [`11_achados_disco_completo.md`](11_achados_disco_completo.md) em mudanças de **gestão** (nomes,
> categorias e revisões vindos do disco) e de **envio** (os discos `Program` e `Program_Operational`
> chegam em momentos diferentes e precisam poder ser enviados separadamente). A visualização atual
> de `/publicacoes` (árvore Categoria → Manual → Capítulo) **não muda** — só melhora com dados que
> hoje faltam. O que muda é como o acervo chega ao servidor e como o controle da edição é mostrado
> em `/configuracoes`.
>
> **Decisões do responsável (2026-08-10):**
> 1. Se o disco operacional chegar depois de a edição já estar **VIGENTE**, o envio **acumula na
>    própria edição vigente**, in place — não abre uma edição derivada.
> 2. Entre os dois discos, para um manual presente nos dois: **a maior revisão vence**
>    (`version/*.txt`), independentemente de qual disco chegou primeiro.
> 3. O operador sobe o **ZIP da pasta do disco crua** (`Program/` ou `Program_Operational/`, como
>    saiu do DVD) — a normalização (extrair só o que interessa, montar a árvore de manuais) acontece
>    no servidor, não na mão do operador.
>
> **Ressalva registrada, não uma objeção em aberto:** acumular na edição vigente faz
> `publicacoes_acessos.edicao_id` deixar de identificar um conteúdo fixo no tempo — duas consultas à
> mesma edição, antes e depois do segundo disco, podem ver manuais diferentes. A compensação é a
> **trilha por remessa** (§5): cada disco recebido fica registrado com origem, data e diff próprio,
> então "o que a edição continha em cada momento" continua respondível, só que por remessa dentro da
> edição em vez de por edição inteira.

---

## 1. Motivação e o que muda

O fluxo de envio web (M4.Web, ver [`envio_publicacoes.md`](envio_publicacoes.md)) foi construído sob
a premissa **um ZIP = uma edição completa do acervo**. Essa premissa nunca bateu com a operação real:
os dois discos do `DISCO_COMPLETO` — manutenção (`Program/`) e operacional (`Program_Operational/`)
— são remessas independentes, tipicamente com meses de diferença entre uma e outra, e o `11` mediu
que juntos somam 18.746 PDFs (3,3× o que o módulo indexava até agora) e trazem 4 fontes de metadados
estruturados que hoje são ignoradas.

| Ganho do `11` | Prioridade lá | O que destrava aqui |
|---|---|---|
| `manual_details.xml` — nomes PT-BR | Alta | §4 — descrição do manual sem depender só do toml |
| `manual_type.xml` — `catid` | Alta | §4 — fecha a D-01 sem reescrever `categorias_manuais.toml` |
| 15 `index_2.0/` exclusivos da raiz | Alta | §3 — 49 manuais com metadado Lucene, não 34 |
| 4 manuais exclusivos do operacional | Alta | §3, §6 — entram sempre, sem conflito de revisão |
| `version/*.txt` — revisão e data | Alta | §4, §6 — popula `manuais.revisao`/`revisao_data` (colunas que já existem e nunca são escritas) e vira o critério de merge |
| `Program/Index/` (PDX proprietário) | — | Confirmado sem uso — nem é citado de novo |

**O que não muda**, para deixar explícito o que este documento preserva:

- A árvore de `/publicacoes` (Categoria → Manual → Capítulo) e o viewer.
- `catalog.<rotulo>.db` — um índice de busca por edição (ADR-004, "Resolução do índice por edição").
- O RBAC: `INSPETOR`/`ADMINISTRADOR` envia, só `ADMINISTRADOR` ativa
  (`docs/architecture/adr/004-modulo-publicacoes.md`).
- O acervo continua não-versionado; o repositório continua guardando só `tests/fixtures/fim/`.

---

## 2. Defeitos bloqueantes do pipeline atual (medidos, não suspeitos)

Nenhum dos itens abaixo é hipotético — cada um foi confirmado lendo o código listado. B-01 a B-04
bloqueiam **qualquer** envio, do disco que for; são pré-requisito das seções seguintes, não uma
melhoria paralela.

| # | Onde | Achado | Efeito |
|---|---|---|---|
| B-01 | `scripts/publicacoes/publicar.py:425,435,436,438,440,442,569,573,574,576,580` | `if args.de-upload:` — o parser Python lê isso como `args.de - upload` (subtração), não como o atributo `args.de_upload` que o `argparse` cria a partir de `--de-upload` | `NameError: name 'upload' is not defined` na primeira linha executável de `main()` sempre que `--de-upload` é passado. **O script está quebrado hoje mesmo fora do fluxo web** — qualquer chamada `python -m scripts.publicacoes.publicar --de-upload ...` falha antes de fazer qualquer trabalho. É a causa provável dos jobs que ficam presos em `PROCESSANDO` e que o commit `eecad2b` (auto-healing) contorna sem corrigir a causa. |
| B-02 | `publicar.py:277` `max_entradas: int = 10000` (padrão de `validar_pacote_zip`) | `Program/Data/` sozinho tem 12.117 PDFs, mais os diretórios de capítulo e os ~15×10 arquivos de `index_2.0/` — passa de 10.000 entradas com folga | O ZIP do disco de manutenção é **recusado sempre** pela validação, mesmo corrigindo B-01 |
| B-03 | `publicar.py:257-263` `EXTENSOES_ZIP_PROIBIDAS` (denylist) | O disco cru traz `TechData.exe`, `*.dll`, `MESSAGE.JAR`, `*.js` (Flash/instalador — ver `11_achados_disco_completo.md` §5) | A denylist detecta a primeira ocorrência e **recusa o pacote inteiro** — incompatível com a decisão "subir a pasta do disco como veio" (decisão 3) |
| B-04 | `app/modules/publicacoes/router.py:800` `getattr(get_settings(), "publicacoes_upload_max_gb", 4)` | A chave `publicacoes_upload_max_gb` não existe em `app/bootstrap/config/__init__.py` (conferido — só `publicacoes_acervo_dir`, `publicacoes_index_path`, `publicacoes_categorias_path`, `publicacoes_avulsas_max_upload_mb`, `publicacoes_edicoes_retidas`, `publicacoes_snapshots_retidos`) | Teto de 4 GB fixo e **não documentado nem configurável** — o disco de manutenção sozinho tem 2,0 GB; margem apertada para crescer |
| B-05 | `app/modules/publicacoes/service.py:1256` `os.kill(job.processo_pid, 0)` dentro de `limpar_jobs_upload_estagnados` | No Windows, `os.kill(pid, sig)` só entende `signal.CTRL_C_EVENT`/`CTRL_BREAK_EVENT`; qualquer outro valor de `sig` (incluindo `0`, usado aqui como probe POSIX de "processo existe?") cai no caminho que chama `TerminateProcess` | Em desenvolvimento no Windows, o **probe de liveness mata o worker que estava vivo** — o auto-healing "cura" um job saudável transformando-o em falha. Em Linux o `kill(pid, 0)` é inofensivo (comportamento POSIX real); o bug é específico da plataforma de dev |
| B-06 | `app/web/static/js/configuracoes_publicacoes.js:462-500` (loop de envio de partes) | Partes enviadas em série (`for` com `await`), sem retry por parte; nenhuma consulta a job ativo ao carregar `/configuracoes` | Uma parte que falha por instabilidade de rede aborta o envio inteiro de um ZIP de ~2 GB, sem retomar; e quem recarrega a página no meio de um `PROCESSANDO` perde a barra de progresso até o polling ser religado manualmente |

> [!IMPORTANT]
> B-01 explica por que a Fase 3/4/5 do `envio_publicacoes.md` está marcada `[x]` (código escrito) mas
> o fluxo nunca foi exercitado ponta a ponta com um upload real: os testes unitários de `publicar.py`
> chamam as funções internas diretamente (`inventariar_acervo`, `calcular_diff`, ...), nunca
> `main()` com `--de-upload`, então o bug de sintaxe do atributo nunca foi pego por eles.

---

## 3. Ingestão do disco cru (normalização no servidor)

A decisão 3 ("subir a pasta do disco como veio") desloca todo o trabalho de reconhecer o disco para
o servidor. Este é o mapeamento a implementar, manual → decisão:

- **Descoberta de manuais canônicos:** cada subpasta de primeiro nível de `Program/Data/` (ou
  `Program_Operational/Data/`) é um manual candidato — **exceto** `Data-ALX/`, que é uma réplica
  aninhada do próprio disco de manutenção com o índice Lucene "antigo" (§2.2 do `11`), não um manual.
  Sem essa exclusão explícita, `indexar.descobrir_manuais` (`scripts/publicacoes/indexar.py:142-172`)
  trataria `Data-ALX` como um único manual de 5.724 PDFs, duplicando o acervo inteiro dentro dele
  mesmo.
- **Resolução do índice Lucene:** PDFs sempre vêm da raiz `Program/Data/<MANUAL>/` (revisão mais
  recente, ver §2.2 do `11`); `index_2.0/` é procurado primeiro na própria raiz e, se ausente, em
  `Program/Data/Data-ALX/Data/<MANUAL>/index_2.0/`. Essa busca em dois níveis é **exatamente** o que
  `indexar.localizar_index_lucene` (`indexar.py:175-189`) já faz — reaproveitar a função sem
  reescrevê-la, só apontando `acervo` para a raiz do disco extraído. Só três arquivos por manual são
  lidos (`_0.fnm`, `_0.fdx`, `_0.fdt` — ver `catalog.iter_index`, `catalog.py:123-173`); os `.pdx`/
  `.idx` de `Program/Index/` continuam fora, como o `11` já veredictou.
- **Allowlist de extração** (substitui a denylist de B-03): do ZIP só é extraído o que casa com
  `.pdf`, `.fnm`, `.fdx`, `.fdt`, `.xml`, `.ini`, `.txt`, `.lst` (case-insensitive). O resto —
  `.exe`, `.dll`, `.jar`, `.swf`, `.bmp`, `.ico`, `.rav`, `.fr3` — é **ignorado silenciosamente na
  extração**, nunca gravado em disco, e a contagem do que foi ignorado entra no relatório da remessa
  (§5). As defesas de Zip-Slip (checagem de `..`/caminho absoluto) e zip-bomb (teto de descomprimido
  e razão de compressão) de `validar_pacote_zip` (`publicar.py:271-332`) continuam como estão —
  allowlist é adicional, não substitui contenção de caminho.
- **Metadados da remessa, preservados à parte:** `manual_details.xml`, `manual_type.xml`,
  `collections.ini` (Latin-1 — atenção à decodificação) e `version/*.txt` são copiados para
  `Manuais/_metadados/<origem>/` dentro do acervo de trabalho. Esse subdiretório não tem PDF na raiz,
  então `descobrir_manuais` já o ignora (linha 168-170: "Diretório sem PDF — ignorado", log
  informativo, sem erro).
- **Código canônico por manual:** a chave usada em `Manual.codigo` (e, por consequência, nas chaves
  de `config/categorias_manuais.toml` e no UUID v5 de `catalog.documento_id_deterministico`) é o
  nome de pasta do **disco de manutenção**, porque é o que já está em produção. Manuais que só
  existem no disco operacional entram com o próprio nome de pasta de lá (ex.: `1BS_ALX_0000`). Para
  o caso registrado no `11` §2.3 — `BO_314PT_0000` no operacional é o mesmo manual que `BO_314PT` na
  raiz do disco de manutenção — o apelido é resolvido por `(type, partnumber)` do
  `manual_details.xml`: `type="BO_314PT" partnumber="0000"` casa os dois códigos de pasta em um só
  `Manual.codigo` canônico (`BO_314PT`). O mesmo XML define 4 sinônimos de `type` a tratar como
  aliases do mesmo manual, não manuais distintos: `SDS`=`AMM_PART1`, `AMM`=`AMM_PART2`,
  `SRMI`=`SRM_PART1`, `SRM`=`SRM_PART2` (`11_achados_disco_completo.md` §3.1, nota).
- **Requisito operacional de disco:** durante a ingestão de uma remessa, o pico de uso é
  aproximadamente ZIP recebido (até 2,0-2,2 GB por disco) + extração temporária (mesmo tamanho) +
  acervo já existente (até 3,1 GB somando os dois discos) — **~10 GB livres** é a orientação a colocar
  no runbook operacional da VPS.

> [!WARNING]
> A extração roda no subprocesso isolado (`python -m scripts.publicacoes.publicar --de-upload`,
> ADR-004 "Isolamento de Processamento via Subprocesso"), não no worker web — mas ainda assim é I/O
> pesado; nenhuma mudança na arquitetura de isolamento é necessária, só o volume de disco.

---

## 4. Metadados: o que passa a vir do disco

| Campo | Hoje | Passa a ser | Efeito visível na UI |
|---|---|---|---|
| `manuais.descricao_pt` | `config/categorias_manuais.toml`; sem entrada, cai no `_default` (`{codigo}`) | toml (autoridade) → `manual_details.xml` (`custom-description`) → código cru | Os manuais que só existem no disco completo (os 15 `index_2.0/` exclusivos + os 4 do operacional) deixam de aparecer como `BO_314PT_0000` na árvore e passam a mostrar "Boletins Operacionais" |
| `manuais.categoria` | toml; sem entrada, `"Outros"` | toml (autoridade) → `catid` de `manual_type.xml`, mapeado para um rótulo de categoria via `collections.ini` → `"Outros"` | Mesma árvore Categoria → Manual, mas menos manuais caindo em "Outros" |
| `manuais.revisao` / `manuais.revisao_data` | **Colunas existem em `app/modules/publicacoes/models.py:172-173` e nunca são escritas** — nenhuma chamada a `service.sincronizar_catalogo` (`service.py:693-787`) passa esses campos, e `Manual()` nunca os recebe em `indexar.py`. `revisao` já é lido e devolvido por `service.listar_manuais_vigentes` (`service.py:497,516`) e já está no schema `ManualListItem.revisao` (`schemas.py:192`) — o campo chega ao cliente e é sempre `null` hoje | Parseado de `version/<CODIGO>.txt` de cada disco (regra de qual disco vale, ver §6) | A UI (que já recebe o campo) passa a poder mostrar "Rev. 14 · 25/04/2016" — não precisa de mudança de schema, só de o backend parar de deixar o campo vazio |

**Formato de `version/*.txt` a fixar no parser** (3 linhas, medido no `11` §3.5):

```
Rev. 11
Date: 07/25/2016
TR: 
```

- `Rev.` é texto livre — aparece como `11`, `08`, `6`, `00` e também `N/A` (ex.: `1BS_ALX_0000`,
  sem revisão numérica por ser um boletim avulso). Regex de extração: `^Rev\.\s*(.+)$`.
- `Date:` está em **MM/DD/YYYY**, não DD/MM/YYYY — confirmado pelas três amostras do `11` que só
  fazem sentido nesse formato: `10/21/2013`, `03/31/2014` (dia 31 não existe como mês) e
  `08/26/2013` (dia 26 não existe como mês). Regex: `^Date:?\s*(.+)$`, parse com `%m/%d/%Y`.
- `TR:` não tem uso conhecido no módulo — ignorar.

**Decisão sobre autoridade de categoria (fecha D-01 sem reescrever o toml):**
`config/categorias_manuais.toml` continua sendo a fonte que a árvore usa — é curado à mão, testado
contra os títulos reais dos documentos (ver o cabeçalho do próprio arquivo) e é o que já está em
produção. Os XMLs do disco **não sobrescrevem** entradas existentes do toml; eles preenchem apenas
manuais sem entrada e alimentam um **relatório de divergência por remessa** (formato: "N manuais sem
entrada no toml; sugestão por `catid`: `<trecho TOML pronto para colar>`"), para que alguém revise e
cole antes da próxima indexação — o mesmo espírito de "arquivo nunca quebra a indexação, mas avisa"
que o cabeçalho de `categorias_manuais.toml` já declara.

---

## 5. Remessa como unidade de envio

Hoje o módulo só conhece **edição** como unidade. Este refinamento introduz **remessa**: um envio de
um disco específico, dentro de uma edição. A tabela abaixo é o modelo de dados; a migração real fica
para a fase de implementação (§9, Fase 2).

- **`OrigemRemessa`** — novo enum em `app/shared/core/enums.py`, ao lado de `StatusUploadJob`:
  `MANUTENCAO` (`Program/`) e `OPERACIONAL` (`Program_Operational/`).
- **`publicacoes_upload_jobs.origem`** — coluna nova, `OrigemRemessa`, **nullable** (jobs existentes
  não têm origem e não devem quebrar ao ler).
- **Tabela nova `manuais_remessas`**: `id`, `edicao_id` (FK `manuais_edicoes`), `origem`
  (`OrigemRemessa`), `job_id` (FK `publicacoes_upload_jobs`, nullable — permite registrar remessas
  aplicadas fora do fluxo web, ex. CLI), `recebida_em`, `criado_por_id`, contadores
  (`manuais_novos`, `manuais_atualizados`, `manuais_descartados_por_revisao`,
  `arquivos_ignorados_allowlist`) e `relatorio_diff` (Text — o diff **desta** remessa, não da
  edição inteira). **Esta tabela é a compensação da decisão "acumular na vigente"** (ver a ressalva
  na abertura do documento): mesmo que o conteúdo da edição mude sob os pés depois de ativada, cada
  remessa aplicada fica registrada com quando e o que trouxe.
- **`manuais.origem`** — coluna nova em `Manual`, `OrigemRemessa`, nullable, gravada com a origem de
  onde veio a **cópia vigente** daquele manual (depois do merge de §6). Sustenta dois usos de UI:
  "este manual só existe porque o disco operacional já chegou" e o relatório de conflito ("FIM_1741
  ficou na revisão do disco de manutenção, o operacional foi descartado").
- **API — `POST /publicacoes/api/edicoes/uploads`:** `schemas.UploadIniciarIn` ganha o campo
  `origem: OrigemRemessa`. A recusa atual em `router.py:811-818` ("já existe edição com esse rótulo
  que está VIGENTE → 409") deixa de se aplicar quando a remessa é uma acumulação sobre a mesma
  edição vigente — vira o caminho normal, não uma exceção.
- **Rate limit:** `@limiter.limit("5/hour")` (`router.py:782`) precisa ser revisitado — duas remessas
  do mesmo operador em sequência (manutenção, depois operacional, possivelmente com uma retentativa
  no meio) cabem nesse teto, mas com pouca folga; registrar como item de ajuste na Fase 2, não
  necessariamente subir o número — só confirmar que 2 discos + 1 retry cabem.

---

## 6. Merge por revisão (a regra escolhida)

A granularidade da decisão é **por manual inteiro**, nunca por arquivo avulso: os PDFs de um manual
se referenciam entre capítulos (índice, remissões), e misturar revisões diferentes dentro do mesmo
manual corrompe a navegação de um jeito que não aparece até alguém abrir o documento errado.

Cascata de decisão, nesta ordem, quando um manual existe nos dois discos:

1. **`Rev.` numérico de `version/<CODIGO>.txt` dos dois lados** → o maior vence.
2. **Empate de `Rev.`, ou `Rev.` não numérico (`N/A`)** → `Date:` mais recente vence.
3. **`version/` ausente de um dos lados** → precedência fixa: manutenção vence sobre operacional
   (é a fonte que já está em produção e, historicamente, a mais atualizada — ver `11` §3.5, "o disco
   de manutenção é ~3 anos mais recente").
4. **Manual exclusivo de um disco** (os 4 do operacional, os 15 exclusivos da raiz de manutenção) →
   entra sempre, sem disputa.

O perdedor de um conflito **nunca é apagado em silêncio** — vai para `_merge_conflicts/<caminho>` e
entra no relatório da remessa. Esse comportamento já existe em
`scripts/publicacoes/merge_data.py` (`planejar_merge`/`aplicar_merge`, linhas 74-142); o que muda é
o critério de desempate. Hoje `planejar_merge` decide por `mtime` do arquivo
(`merge_data.py:96-104`), que numa cópia de DVD reflete a data em que o arquivo foi *copiado para o
disco de origem da remessa*, não a revisão do manual — um critério que já era frágil antes deste
refinamento e que os dois discos tornam claramente errado (copiar o disco operacional por último
faria seu `mtime` vencer mesmo sendo a revisão de 2013).

**Mudança de especificação:** `planejar_merge` passa a receber uma função de decisão de conflito
(parâmetro com um padrão sensato), permitindo plugar o critério por revisão (cascata acima) como
padrão do fluxo de disco, mantendo o critério por `mtime` disponível como recurso genérico para quem
chamar o script fora do contexto de disco (ex.: merge de uma remessa avulsa sem `version/`).

---

## 7. Indexação acumulativa

**Invariante a declarar em destaque, porque quebrar isso é silencioso e grave:** toda remessa
reindexa a **árvore acumulada inteira** da edição, nunca só os manuais que vieram no ZIP daquela
remessa.

Motivo medido: `indexar.abrir_catalog_novo` (`scripts/publicacoes/indexar.py:261-281`) sempre
constrói um `catalog.<rotulo>.db` **do zero** num arquivo temporário e faz `os.replace` no final.
Se uma segunda remessa (o disco operacional) rodasse `indexar.main` apontando só para os manuais
daquele ZIP, o índice de busca resultante teria só os manuais do operacional — os 12.117 PDFs do
disco de manutenção, já publicados, sumiriam da busca (não do catálogo leve, que não tem esse
problema porque `service.sincronizar_catalogo`, `service.py:693-787`, reconcilia apenas os manuais
do payload recebido). É exatamente o cenário que o aviso de `indexar.py:503-515`
("manual(is) da edição estão no catálogo mas fora desta execução — saíram do índice de busca") foi
escrito para sinalizar — com remessas parciais, deixa de ser um aviso de borda e passa a acontecer
a cada segundo disco, a menos que a reindexação sempre parta do acervo consolidado em disco (que já
inclui a remessa anterior, pós-merge de §6).

**Otimização especificada como fase própria e separável** (não bloqueia o fluxo funcional): modo
incremental de reindexação. `publicar.inventariar_acervo` já calcula hash SHA-256 por PDF para o
diff, e `catalog.documento_id_deterministico` já gera um `document_id` estável por
(edição, manual, file_key) — logo, um documento cujo hash não mudou entre a reindexação anterior e
esta pode ter suas linhas de `documents`/`pages` **copiadas** do `catalog.<rotulo>.db` anterior via
`ATTACH DATABASE`, em vez de reprocessado com `pypdfium2` (que é o custo dominante da indexação).
`finalizar_catalog` (`rebuild` + `optimize` do FTS5, achado B7) continua obrigatório ao final,
porque o FTS5 de conteúdo externo não se popula com `INSERT OR REPLACE` direto — copiar linhas de
`pages` tem a mesma lacuna que inserir do zero.

**Snapshot deixa de ser recompactado a cada remessa.** Hoje `publicar.criar_snapshot_zip`
(`publicar.py:196-203`) re-zipa o acervo inteiro (até 3,1 GB) toda vez que o script roda. O ZIP que
o operador acabou de enviar **já é** um snapshot válido daquele disco — em vez de zipar de novo,
copiar a chave já consolidada do multipart (`publicacoes/uploads/<job_id>/edicao.zip`) para
`publicacoes/snapshots/<rotulo>/<origem>.zip` (`copy_object` no storage) antes de apagar a chave
temporária de upload.

---

## 8. Gestão na interface (visualização preservada)

- **`/publicacoes`:** nenhuma mudança estrutural na árvore Categoria → Manual → Capítulo nem no
  viewer. O único efeito visível é dado que já tinha campo reservado e estava vazio: a revisão por
  manual (§4), e nomes/categorias melhor preenchidos para os manuais que hoje caem em "Outros" ou
  aparecem com o código cru.
- **`/configuracoes` → modal "Edições do Acervo"** (`configuracoes_publicacoes.js`,
  `montarLinhaEdicao`/`montarAcoesEdicao`): cada edição passa a expandir para a **composição por
  remessa** — origem (Manutenção/Operacional), data de recebimento, contadores da tabela
  `manuais_remessas`, e um link de relatório por remessa (não mais um único
  `manuais_edicoes.relatorio_diff` sobrescrito a cada publicação, como é hoje). Um indicador simples
  — "disco operacional ainda não recebido" — quando a edição só tem remessa `MANUTENCAO`.
- **Relatório de diff:** deixa de ser o campo único `manuais_edicoes.relatorio_diff`
  (`gerar_relatorio_markdown`, `publicar.py:149-188`, sobrescrito pela linha 543 a cada publicação) e
  passa a ser um relatório por remessa, guardado em `manuais_remessas.relatorio_diff`. O modal de
  relatório (`abrirModalRelatorio`, `configuracoes_publicacoes.js:293-311`) passa a listar remessas
  de uma edição em vez de abrir direto o relatório único da edição.
- **Retomada de acompanhamento** (parte de gestão de B-06): ao abrir `/configuracoes`, consultar
  `GET /publicacoes/api/edicoes/uploads?limit=1` e, se houver um job em `ENVIANDO`/`PROCESSANDO`,
  religar `iniciarPollingUpload` automaticamente — hoje quem recarrega a página no meio de um envio
  perde a barra de progresso até fechar e reabrir o modal manualmente (o polling só começa dentro do
  fluxo de `tratarSubmitUpload`, `configuracoes_publicacoes.js:417-518`).

---

## 9. Fases, com gate verificável cada

| Fase | Conteúdo | Gate |
|---|---|---|
| 0 | Corrigir B-01 a B-05 (§2) | `python -m scripts.publicacoes.publicar --edicao teste --dry-run` roda até o fim sem exceção; `limpar_jobs_upload_estagnados` não derruba um processo vivo no Windows |
| 1 | Normalizador de disco cru (§3): exclusão de `Data-ALX` como manual, allowlist de extração, cópia de metadados para `_metadados/<origem>/`, resolução de apelido via `manual_details.xml` | Rodar contra um disco sintético de teste (§10) produz a árvore de manuais esperada, sem `.exe` extraído |
| 2 | Remessa (§5): enum `OrigemRemessa`, tabela `manuais_remessas`, coluna `manuais.origem`, migração Alembic, `origem` na API de upload | Duas remessas seguidas na mesma edição (a segunda depois de VIGENTE) não são recusadas por 409; `manuais_remessas` tem uma linha por envio |
| 3 | Merge por revisão em `merge_data.py` (§6): função de decisão plugável, critério por `version/*.txt` como padrão do fluxo de disco | Testes de merge com revisões cruzadas nas duas ordens de chegada (manutenção primeiro, operacional primeiro) convergem para o mesmo vencedor |
| 4 | Indexação acumulativa (§7): sempre reindexar o acervo consolidado; modo incremental via `ATTACH` como otimização à parte; snapshot por cópia de objeto | Segunda remessa não reduz a contagem de documentos buscáveis da primeira; tempo de reindexação da segunda remessa (modo incremental) menor que reprocessar tudo |
| 5 | UI de envio robusto (§8, parte de B-06): retry por parte, retomada de polling ao recarregar, composição por remessa no modal | Interromper a rede no meio de uma parte não aborta o envio inteiro; recarregar `/configuracoes` durante `PROCESSANDO` religa a barra sozinha |
| 6 | Testes + atualizar `03_especificacao_tecnica.md` §0.1 e `08_status_de_implementacao.md` | Suíte completa verde; `08` reflete o novo modelo de remessa |

---

## 10. Verificação

Como testar sem depender do DVD real (18.746 PDFs não cabem em fixture de repositório): montar dois
"discos" sintéticos em `tests/fixtures/` — poucos PDFs cada, um `version/` com revisões cruzadas
propositalmente (um manual mais novo no disco de manutenção, outro mais novo no operacional), um
`manual_details.xml` reduzido cobrindo o caso de apelido (`BO_314PT_0000` → `BO_314PT`), um manual
presente só no operacional, e uma pasta `Data-ALX/` fake para garantir que a exclusão funciona.

Casos a cobrir:

- Allowlist descarta `.exe`/`.dll`/`.jar` do ZIP sintético sem recusar o pacote inteiro.
- `Data-ALX/` nunca vira um `Manual.codigo` próprio.
- `BO_314PT_0000` (operacional) e `BO_314PT` (manutenção) resolvem para o mesmo `Manual.codigo`.
- Merge escolhe a revisão maior nas duas ordens de chegada (manutenção→operacional e
  operacional→manutenção dão o mesmo resultado final).
- Segunda remessa **não** encolhe o índice de busca da primeira (contagem de documentos buscáveis
  não cai depois da segunda reindexação).
- `manuais_remessas` registra uma linha por envio, com contadores coerentes com o relatório.

**Testes existentes que não podem regredir** (rodar a suíte completa antes de considerar qualquer
fase concluída): `tests/unit/test_publicacoes_publicar.py`, `tests/unit/test_publicacoes_merge_data.py`,
`tests/unit/test_zip_validator.py`, `tests/unit/test_publicacoes_upload_job.py`,
`tests/unit/test_publicacoes_edicoes.py`, `tests/unit/test_publicacoes_catalog.py`,
`tests/integration/test_publicacoes_upload_api.py`, `tests/integration/test_publicacoes_busca.py`,
`tests/security/test_publicacoes_xss.py`.

---

## 11. Referências

- [`11_achados_disco_completo.md`](11_achados_disco_completo.md) — base factual deste refinamento.
- [`envio_publicacoes.md`](envio_publicacoes.md) — backlog original do M4.Web (fases já marcadas
  `[x]`, mas ver B-01: nunca exercitado ponta a ponta com upload real).
- [`03_especificacao_tecnica.md`](03_especificacao_tecnica.md) — contrato de dados/rotas a atualizar
  na Fase 6.
- [`08_status_de_implementacao.md`](08_status_de_implementacao.md) — painel de progresso a atualizar
  conforme as fases da §9 avançam.
- [`../../architecture/adr/004-modulo-publicacoes.md`](../../architecture/adr/004-modulo-publicacoes.md)
  — decisões de arquitetura que este documento não reabre (isolamento por subprocesso, índice por
  edição, RBAC).
