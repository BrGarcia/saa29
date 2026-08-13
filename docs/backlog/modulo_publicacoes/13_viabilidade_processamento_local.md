# Viabilidade — Processamento Local do Disco Completo + Envio Manual ao Cloudflare R2

> **Data:** 2026-08-11 · **Escopo:** resposta verificada em código à pergunta "dá para processar os
> discos no meu computador e mandar só um arquivo pronto para o Cloudflare, apontando o sistema para
> ele?" — sem código nesta entrega, mas com o caminho de menor esforço e o que falta construir.
>
> **Resposta curta: sim, é viável, e boa parte já é a arquitetura recomendada hoje** (ADR-004 e
> `docs/guides/operacao_publicacoes.md` já descrevem "processar localmente, revisar, depois publicar
> na VPS"). A parte que **não** funciona como a ideia original supunha: não existe hoje um único
> `publicacoes.db` que baste enviar — são **três artefatos de natureza diferente**, e um deles (os
> PDFs) precisa continuar existindo como arquivos em disco na máquina que roda o SAA29, não dentro de
> um banco. A seção 3 detalha por quê.

---

## 0. Relação com outros documentos desta pasta

Este documento responde a uma pergunta pontual — cabe entre o `11` (o que tem nos discos) e o `12`
(o que fazer com isso). Não substitui nenhum dos dois: as Fases 0–3 do `12` (§9) continuam sendo
pré-requisito para ler os discos `Program`/`Program_Operational` crus, **local ou remotamente** — ver
§5 abaixo.

Existe também um rascunho anterior, **[`esboco_processamento_publicacoes.md`](esboco_processamento_publicacoes.md)**,
com data de hoje, não referenciado no `00_indice.md`. Ele acerta a motivação (indexação é pesada,
rodar fora da VPS é seguro pela ADR-004) mas erra em dois pontos verificados em código:

1. Descreve um "Viewer PDF: gera presigned URLs / Proxy para R2" — **isso não existe hoje**.
   `router.py:409-448` serve o PDF com `FileResponse` lido do disco local via `_resolver_pdf`
   (`router.py:48-79`); não há nenhum branch que leia do R2 para servir um documento. Construir isso
   é viável, mas é uma mudança de arquitetura própria, não um efeito colateral do processamento local
   — ver §3 e §6.
2. Propõe subir os PDFs individualmente para `publicacoes/acervo/<edicao>/<manual>/<pdf>` no R2 e um
   novo endpoint `sincronizar_offline`. É uma solução válida, mas mais código novo do que a §4 propõe
   — a Fase B da §6 é essencialmente essa proposta, mantida como opção mais ambiciosa, não como o
   caminho recomendado para uma solução dita "temporária".

---

## 1. O que já existe e já é a arquitetura pretendida

Duas decisões já tomadas dizem que processar fora da VPS é não só permitido como desejado:

- **ADR-004, decisão 2** (`docs/architecture/adr/004-modulo-publicacoes.md:42-45`): a indexação
  (extração de texto por página, `scripts/publicacoes/indexar.py`) roda **offline**, nunca no
  processo web. Consequência registrada explicitamente (linha 74-75): *"A indexação pode rodar em
  qualquer máquina com o acervo montado (não precisa ser o servidor de produção) — inclusive antes de
  qualquer decisão de hospedagem estar tomada."*
- **`docs/guides/operacao_publicacoes.md` §1** já documenta esse fluxo de ponta a ponta: rodar
  `python -m scripts.publicacoes.publicar --edicao <rotulo>` **na estação de publicação** (qualquer
  máquina, inclusive Windows — o guia já assume isso), revisar o relatório de diff, e só então
  transferir para a VPS. Frase literal do guia: *"A estação de publicação (...) e a VPS de produção
  não precisam ser a mesma máquina."*

A única coisa que esse fluxo já documentado usa hoje para "transferir" é `rsync`/SSH (§3 do guia,
decisão D-D — *"o acervo nunca trafega por HTTP entre a estação de publicação e a VPS"*). A pergunta
desta seção não é "posso processar localmente" — **isso já é o padrão** — é "posso trocar o `rsync`
por um envio manual ao Cloudflare R2 como canal de transferência". A resposta está na §4.

---

## 2. Os dois "bancos" do módulo — nenhum dos dois é um `publicacoes.db` único

A ideia original ("gerar um arquivo `publicacoes.db` e enviar") pressupõe um banco único. O módulo
tem dois, de natureza diferente (ADR-004, "Consequências negativas", linha 79):

| | Banco principal (`manuais`, `manuais_edicoes`, `manuais_documentos`, `publicacoes_upload_jobs`) | `catalog.<rotulo>.db` |
|---|---|---|
| Onde mora | Dentro do `DATABASE_URL` da aplicação (`app/bootstrap/config/__init__.py:55`, SQLite por padrão: `sqlite+aiosqlite:///./saa29_local.db`) | Arquivo SQLite dedicado, um por edição, fora do Alembic e do `DATABASE_URL` |
| Como é escrito | SQLAlchemy, dentro do processo que roda `publicar.py`/`indexar.py`, contra **a sessão daquela execução** — não existe hoje um passo de "exportar essas linhas para um arquivo portátil e importar depois" | `sqlite3` puro (`indexar.py`), escrito do zero a cada reindexação e trocado por `os.replace` |
| É portável como arquivo solto? | **Não diretamente** — é uma escrita ORM em uma sessão viva, não um artefato gerado à parte. Ver §4.2 para o que isso implica na prática | **Sim, hoje, sem mudança nenhuma de código** — é só um arquivo `.db`, autocontido, sem dependência de rede nem de outro banco (ADR-004, decisão 1) |
| Já é seguro abrir só com `sqlite3` (sem SQLAlchemy)? | Não se aplica (é sempre via ORM) | Sim, obrigatório — abrir via SQLAlchemy dispararia o listener de backup R2 registrado na classe `Session` inteira (`app/bootstrap/events.py:34-41`), documentado em ADR-004 linhas 38-40 |

Confirmação de que o app é SQLite-only hoje, o que simplifica a resposta (não existe complicação de
"Postgres em produção, SQLite localmente"): `app/bootstrap/database.py:1-4` — *"Focado exclusivamente
em SQLite para o MVP SAA29"* — sem branch de dialeto em `get_engine()`, sem `psycopg2`/`asyncpg` no
projeto, e `scripts/maintenance/r2_manager.py:25-26` tem um guard explícito que **desativa** o backup
R2 do banco principal se `DATABASE_URL` não for SQLite.

---

## 3. Por que "só apontar para o Cloudflare" não é suficiente para os PDFs

Ponto verificado em código, é o achado central deste documento: **o SAA29 nunca lê o PDF do R2 para
servir ao usuário — sempre lê do disco local da máquina que roda o processo web.**

- `GET /publicacoes/doc/{doc_id}/pdf` (`router.py:409-448`, função `obter_pdf`) resolve o caminho do
  arquivo com `_resolver_pdf(documento.manual.path, documento.file_key)` (`router.py:48-79`), que
  monta `publicacoes_acervo_dir / manual.path / file_key` **em disco local** e só retorna se
  `caminho.is_file()` for verdadeiro (`router.py:60-72`). Sem o arquivo físico, a rota responde 404
  ("Arquivo físico do documento não encontrado.", `router.py:435-439`).
- A resposta é `FileResponse` — todo o arquivo é streamado do disco (`router.py:444-448`). Não há
  `pypdfium2` nem qualquer geração de imagem no servidor: quem renderiza a página é o **navegador**,
  via pdf.js (`app/web/static/js/publicacoes_viewer.js:359`, `getDocument({ url: ...})` apontando
  para essa mesma rota) — confirmando que o cliente busca o PDF inteiro e pagina localmente.
- `catalog.<rotulo>.db` não ajuda aqui: seu schema (`indexar.py:91-118`) só tem `documents` (metadado
  textual) e `pages(document_id, page_number, text)` — **texto**, para o FTS5, nunca imagem/BLOB.

**Consequência prática:** search e navegação por metadado funcionariam com só o banco principal +
`catalog.db` sincronizados; abrir qualquer documento no viewer devolveria 404 até o PDF físico existir
em `var/publicacoes/acervo/` na máquina que serve a aplicação. "Apontar para o Cloudflare" só resolve
o problema se alguém também construir um caminho de leitura de PDF a partir do R2 (URL presignada ou
proxy) — que é trabalho novo, não uma consequência automática de ter os arquivos no R2. Fica registrado
como opção B na §6, não como o caminho recomendado para uma solução temporária.

---

## 4. Caminho recomendado — reaproveitar o snapshot ZIP que já existe

A boa notícia: o módulo **já produz e já sobe ao R2**, sem nenhuma mudança de código, exatamente o
artefato que resolve o problema dos PDFs — só que hoje ele é usado como cópia de segurança, não como
canal de transferência primário.

### 4.1 O que `publicar.py` já faz sozinho, hoje

Rodando localmente (Windows, sem tocar em `--de-upload` — que está quebrado, ver §5.3):

```bash
python -m scripts.publicacoes.publicar --edicao 2027
```

- Grava as linhas de `manuais`/`manuais_edicoes`/`manuais_documentos` no `DATABASE_URL` **que
  estiver configurado na sua máquina** (local, homologação — o que for).
- Reindexação completa: gera `var/publicacoes/catalog.2027.db` do zero — arquivo autocontido, pronto
  para copiar.
- Gera `var/publicacoes/relatorios/relatorio_publicacao_2027.md` para revisão humana.
- **Zipa o acervo inteiro e envia para `publicacoes/snapshots/2027.zip` no R2**
  (`criar_snapshot_zip`, `publicar.py:196-203`; `enviar_snapshot`, `publicar.py:232-238`) — isso já é
  um upload real ao Cloudflare, hoje, sem escrever uma linha de código. `--pular-upload` desliga esse
  passo se não for desejado; `PUBLICACOES_SNAPSHOTS_RETIDOS` (padrão 3) poda snapshots antigos
  automaticamente.

Ou seja: **o "arquivo pronto para enviar ao Cloudflare" já existe** — é `publicacoes/snapshots/<edicao>.zip`.
O que falta é usar esse ZIP como *entrada* do lado da VPS, no lugar de esperar o `rsync`.

### 4.2 O passo que falta — puramente manual, sem código novo

No lado do servidor (com acesso SSH/console — não HTTP, preservando o espírito da decisão D-D de não
expor o acervo cru à rede pública):

```bash
# 1. Baixar o snapshot que a estação local já subiu automaticamente
aws s3 cp s3://<bucket>/publicacoes/snapshots/2027.zip . --endpoint-url $R2_ENDPOINT
unzip 2027.zip -d var/publicacoes/acervo/

# 2. Rodar publicar.py NA PRÓPRIA VPS, apontando para o DATABASE_URL de produção —
#    isso escreve as linhas de manuais/manuais_edicoes ali, e reconstrói o catalog.db
#    localmente (rápido: o inventário bate 1:1 com o que já foi indexado na estação
#    local, mesmos hashes SHA-256 — publicar.py reconhece e só confirma consistência)
python -m scripts.publicacoes.publicar --edicao 2027 --pular-upload
```

Isso é **literalmente o mesmo procedimento que `operacao_publicacoes.md` §3 já descreve**, só trocando
a etapa de transferência (`rsync -avz --checksum ...`) por "baixar o ZIP do R2 e descompactar". Nenhum
arquivo novo, nenhuma rota nova, nenhuma migração. O `catalog.2027.db` gerado localmente na sua máquina
não precisa nem ser transferido — ele é reconstruído na VPS a partir dos mesmos PDFs, o que já
resolve o problema do "banco principal" da §2 (as linhas são escritas de novo, contra o `DATABASE_URL`
certo, em vez de tentar mover um arquivo `.db` que carrega uma sessão viva).

> [!IMPORTANT]
> Isso só reduz *quando* e *onde* a CPU é gasta (a indexação pesada roda uma vez, na sua máquina, e
> de novo na VPS só para confirmar hash — rápido). Não elimina a necessidade de acesso à VPS para
> rodar o segundo comando. Se o objetivo é eliminar até esse acesso (ex.: alguém sem SSH faz só o
> envio), aí sim é preciso o trabalho novo da opção B (§6).

### 4.3 Se quiser pular o segundo comando na VPS

Copiar manualmente o `catalog.<rotulo>.db` junto com o ZIP (dois arquivos no R2 em vez de um) e, na
VPS, só descompactar o acervo + colocar o `.db` em `var/publicacoes/` — sem rodar `publicar.py` de
novo lá — funciona para a **busca** (o índice já está pronto), mas **não** popula
`manuais`/`manuais_edicoes` no banco principal, então a edição não aparece para ativação em
`/configuracoes` nem a árvore Categoria → Manual do explorador é atualizada (essas duas coisas vêm do
banco principal, não do `catalog.db` — ver `service.listar_manuais_vigentes`,
`app/modules/publicacoes/service.py:497,516`, citado no `12`). Por isso a §4.2 recomenda rodar
`publicar.py --pular-upload` na VPS mesmo sendo redundante com a indexação local — é o passo que
grava o banco principal, e hoje não tem atalho para pular só essa parte sem também pular a
reindexação (`--pular-indexacao` some com a reindexação, mas ainda grava o banco a partir do
`catalog.db` recém-gerado — checar `indexar.gravar_no_banco_principal`, `indexar.py:481-539`, chamado
dentro do mesmo `main()`).

---

## 5. O que falta construir de qualquer jeito — independente de local ou nuvem

Processar localmente **não** resolve sozinho o problema original do `12`: ler os discos crus
(`Program/`, `Program_Operational/`) automaticamente. Isso é trabalho ainda não construído, e é
exatamente o mesmo trabalho esteja ele rodando no seu computador ou na VPS:

- **Normalização do disco cru** (`12` §3): exclusão de `Data-ALX/`, allowlist de extração, cópia de
  metadados XML, resolução de apelido via `manual_details.xml`. Hoje essa lógica só existe dentro do
  branch `--de-upload` de `publicar.py` — que está **quebrado** (ver §5.3) e, mesmo corrigido, seria
  acionado só pelo fluxo de upload web, não por uma chamada de script direta.
- **Merge por revisão** (`12` §6): `scripts/publicacoes/merge_data.py` (`planejar_merge`,
  `merge_data.py:74`; `aplicar_merge`, `merge_data.py:109`) hoje decide por `mtime` do arquivo, não
  pela cascata de `version/*.txt` que o `12` especifica. `12` já registra a mudança necessária (função
  de decisão plugável) — não fica diferente rodando localmente.
- **Metadados de nome/categoria/revisão** (`12` §4): parsing de `manual_details.xml`,
  `manual_type.xml`, `collections.ini`, `version/*.txt` — ainda não implementado em lugar nenhum do
  código hoje.

**Recomendação prática, até essas fases do `12` serem implementadas:** continue usando
`scripts/publicacoes/merge_data.py` (por `mtime`, sabendo da limitação) para montar manualmente a
pasta `Manuais/` a partir dos discos, exatamente como `operacao_publicacoes.md` §2 já orienta hoje —
processar "localmente" não pula essa etapa, só muda onde a etapa roda.

### 5.1–5.3 Bugs que bloqueiam o caminho *errado* (não o recomendado aqui)

Registrado para não confundir: os defeitos B-01 a B-06 do `12` (§2) bloqueiam o fluxo **web**
(`--de-upload`, upload HTTP multipart pela tela de `/configuracoes`). O caminho recomendado na §4
usa `publicar.py` **sem** `--de-upload` — o mesmo comando que `operacao_publicacoes.md` já documenta
e que os testes existentes (`tests/unit/test_publicacoes_publicar.py`) exercitam nas funções internas.
Nenhum desses bugs entra no caminho da §4. Isso é uma vantagem adicional de usar o snapshot ZIP como
canal: contorna B-01/B-02/B-03 (que são todos específicos do parsing de `--de-upload` e da validação
de ZIP vinda de upload web) sem precisar corrigi-los primeiro.

---

## 6. Duas opções, se o objetivo for eliminar também o acesso SSH à VPS

Se "temporariamente" significa que nem sempre haverá alguém com acesso SSH para rodar o segundo
`publicar.py` na VPS (§4.2), duas rotas ficam abertas — nenhuma delas é o caminho recomendado por
padrão, por serem mais código para algo que o enunciado descreve como temporário:

**Opção A — endpoint de sincronização mínimo** (esboço mais enxuto do que o `esboco_processamento_publicacoes.md` propõe): um único endpoint `AdministradorRequired`, ex. `POST /publicacoes/api/edicoes/sincronizar-snapshot`, que recebe só `{edicao, snapshot_key}`, baixa o ZIP do R2 no processo web (fora de request síncrona — via o mesmo subprocesso isolado da ADR-004), extrai para `var/publicacoes/acervo/`, e chama `publicar.py --acervo <extraído> --pular-upload` como já acontece hoje internamente. Reaproveita quase tudo; a única peça nova é o endpoint que dispara o download+extração no lugar do humano rodar o comando via SSH.

**Opção B — servir PDF a partir do R2** (o que o `esboco_processamento_publicacoes.md` desenha): mudar `_resolver_pdf`/`obter_pdf` (`router.py:48-79`, `409-448`) para, quando `storage_backend == "r2"`, gerar uma URL presignada (`R2StorageService.get_url`, já existe em `app/shared/core/storage.py:197` — mas hoje só é chamado para anexos sob o prefixo `anexos/`, não para o acervo de publicações) e redirecionar, em vez de `FileResponse` do disco. Isso elimina a necessidade de o acervo existir em disco na VPS — mas é uma mudança de arquitetura, não um ajuste de operação, e vale uma decisão própria (custo de egress do R2 por PDF servido, cache, etc.) — não algo a decidir de passagem neste documento.

Nenhuma das duas é necessária para o caminho recomendado na §4, que já funciona hoje sem escrever código.

---

## 7. Resumo — o que responder à ideia original

| Pergunta original | Resposta |
|---|---|
| "Processar os discos no meu computador" | Sim — já é o padrão documentado (`operacao_publicacoes.md`, ADR-004) |
| "Gerar um arquivo `publicacoes.db` só" | Não existe um único arquivo — existem dois bancos de natureza diferente (§2) mais os PDFs em si (§3), que juntos formam o que hoje já é gerado automaticamente como `publicacoes/snapshots/<edicao>.zip` no R2 |
| "Enviar para o Cloudflare manualmente" | Já acontece hoje, automaticamente, para o ZIP do acervo (§4.1) — falta só usar esse ZIP como entrada do lado do servidor em vez do `rsync` (§4.2), o que não exige código novo |
| "No meu sistema eu apontaria só para o Cloudflare" | Não totalmente — o servidor sempre lê o PDF do disco local para servir ao navegador (§3); "apontar para o Cloudflare" sem mudança de código significa baixar+extrair o ZIP no servidor, não ler direto do R2 a cada requisição |
| Falta build | A leitura automática dos discos crus (`12` Fases 0–3) continua sendo pré-requisito, local ou remoto (§5) |

---

## 8. Referências

- [`12_refinamento_gestao_e_envio.md`](12_refinamento_gestao_e_envio.md) — defeitos B-01 a B-06 e as
  fases de normalização/merge que continuam pendentes independente deste documento.
- [`11_achados_disco_completo.md`](11_achados_disco_completo.md) — base factual dos discos.
- [`esboco_processamento_publicacoes.md`](esboco_processamento_publicacoes.md) — rascunho anterior;
  ver §0 para onde este documento diverge dele, verificado em código.
- [`../../guides/operacao_publicacoes.md`](../../guides/operacao_publicacoes.md) — o runbook cujo
  fluxo local→VPS este documento reaproveita, só trocando `rsync` por download do snapshot R2 (§4).
- [`../../architecture/adr/004-modulo-publicacoes.md`](../../architecture/adr/004-modulo-publicacoes.md)
  — decisão 1 (por que `catalog.db` nunca abre via SQLAlchemy) e decisão 2 (indexação roda em
  qualquer máquina), citadas nas §§1–2.
- `app/modules/publicacoes/router.py:48-79,409-448` — por que o PDF precisa estar em disco local
  (§3).
- `app/shared/core/storage.py` — `R2StorageService`, incluindo `get_url` (presigned GET, §6 opção B)
  e o cliente `boto3` direto de `scripts/publicacoes/publicar.py:_obter_cliente_s3` (`publicar.py:206-229`),
  que já faz o upload do snapshot hoje (§4.1).
