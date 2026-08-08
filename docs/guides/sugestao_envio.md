# Sugestão — Envio de Atualizações das Publicações pela Web

> Proposta de fluxo para o envio de atualizações do acervo de publicações,
> consolidando [docs\guides\envio_publicacoes_zip.md](envio_publicacoes_zip.md) (por que
> não existe upload `.zip` via HTTP hoje) e
> [docs\guides\opcoes_upload_inspetor.md](opcoes_upload_inspetor.md) (as três opções de
> arquitetura para o INSPETOR), à luz do código atual do módulo
> (`app/modules/publicacoes/`) e dos achados da revisão de 2026-08-08
> ([docs/backlog/modulo_publicacoes/dividas/ACHADOS.md](../backlog/modulo_publicacoes/dividas/ACHADOS.md)).

---

## 1. Resumo da recomendação

**Adotar a Opção 1 (Presigned URL para o Cloudflare R2) como caminho de
envio, com quatro ajustes obrigatórios em relação ao desenho descrito no
guia** — e mantendo o fluxo CLI (`publicar.py` + `rsync`) como caminho de
contingência documentado, não como fluxo removido.

Os quatro ajustes:

| # | Ajuste | Por quê |
|---|--------|---------|
| 1 | **Multipart presigned upload**, não um `PUT` único | Um `PUT` de ~3 GB numa única requisição não tem retomada: uma oscilação aos 90% recomeça do zero. O R2 suporta multipart presigned (partes de 100–200 MB), o que dá retry por parte e barra de progresso real. |
| 2 | **Processamento em processo separado, nunca `BackgroundTasks`** | O guia sugere `BackgroundTask` nativa, mas inventário + extração de texto (pypdfium2) + FTS5 sobre milhares de PDFs é trabalho de minutos, CPU-bound e faminto de RAM — dentro do worker web ele disputa o event loop com as requisições e estoura o gate do M4 (RSS por worker < 200 MB). Rodar como **subprocesso** (`python -m scripts.publicacoes.publicar --edicao <rotulo> --de-upload <key>`), reutilizando o script que já existe e é idempotente por construção (UUID v5). |
| 3 | **Pipeline de validação do ZIP antes de extrair** | Os riscos que motivaram a proibição original (§5.11) não somem com o upload indo ao R2 — eles se movem para a etapa de descompactação na VPS. Ver §4. |
| 4 | **Separação de papéis: INSPETOR envia, ADMIN ativa** | Hoje todo o ciclo de vida de edições é `AdminRequired` no router. Enviar e processar pode ser liberado ao INSPETOR; a **ativação** (que muda o que a organização inteira lê como manual em vigor) deve continuar sendo decisão de Admin, com `publicado_por_id` na trilha de auditoria — como já é. |

Por que não as outras opções:

- **Opção 2 (chunked para a VPS):** funciona, mas soma os dois piores custos —
  disco temporário de 3–6 GB na VPS (o gate do M4 é justamente "disco < 60%")
  e lógica própria de controle/montagem de chunks para manter. A Opção 1
  entrega a mesma UX com o volume trafegando fora da VPS.
- **Opção 3 (dropzone de rede):** é a mais simples de codar, mas depende de
  infraestrutura fora da aplicação (SMB/SFTP mapeado por TI), não dá progresso
  nem erro legível ao usuário, e um serviço de monitoramento de pasta é uma
  fonte clássica de processamento de arquivo pela metade (copiar 3 GB pelo
  Explorer não é atômico). Vale apenas como plano B se o CORS do R2 for
  bloqueio real.

---

## 2. Fluxo proposto, ponta a ponta

```
INSPETOR (navegador)                 FastAPI (VPS)                    R2 / Worker
────────────────────                 ─────────────                    ───────────
1. Seleciona o .zip no card
   Publicações de /configuracoes
2. POST /api/edicoes/uploads  ────►  valida rótulo, papel, tamanho
                                     declarado; cria registro de
                                     upload (status=ENVIANDO);
                                     gera presigned multipart  ────►  R2: URLs por parte
3. PUT das partes direto no R2 ───────────────────────────────────►  R2 recebe o volume
   (progresso por parte, retry)
4. POST /api/edicoes/uploads/{id}/concluir ►  confere ETags/manifesto;
                                     status=PROCESSANDO; dispara
                                     SUBPROCESSO publicar.py ──────►  worker: baixa do R2 em
                                                                      streaming, valida ZIP (§4),
                                                                      extrai contido, indexa,
                                                                      gera catalog.<rotulo>.db,
                                                                      grava edição AGUARDANDO_
                                                                      ATIVACAO + relatorio_diff
5. GET /api/edicoes/uploads/{id}  ◄─  status + % (polling simples,
   (a cada 3–5 s)                     lido de tabela de jobs)
6. UI mostra relatório de diff;
   botão [ATIVAR] aparece p/ ADMIN ►  POST /api/edicoes/{id}/ativar
                                      (fluxo ATUAL, atômico, intocado)
```

Pontos que o fluxo preserva do desenho existente (e que não devem mudar):

- **A ativação continua sendo só a troca do ponteiro** em
  `manuais_edicoes.status` — atômica, instantânea, reversível (reverter =
  ativar a anterior). O upload apenas *abastece* edições em
  `AGUARDANDO_ATIVACAO`.
- **A recusa de ativar sem índice em disco (409)** já protege contra ativar
  uma edição cujo processamento falhou no meio — o botão só aparece quando
  `indice_disponivel=true` na listagem, exatamente como hoje.
- **Idempotência:** reprocessar o mesmo ZIP da mesma edição converge para o
  mesmo estado (chaves determinísticas, `sincronizar_catalogo` reconcilia) —
  então "tentar de novo" é sempre seguro e é a resposta padrão para falha.

---

## 3. O que precisa ser construído

| Peça | Esforço | Observações |
|------|---------|-------------|
| Tabela `publicacoes_uploads` (id, rotulo, status, progresso, erro, key R2, usuario, timestamps) | pequeno | É também a trilha de auditoria do envio. |
| Endpoints `POST /uploads`, `POST /uploads/{id}/concluir`, `GET /uploads/{id}` | pequeno | Sob `/publicacoes/api/`, role INSPETOR-ou-ADMIN; rate limit baixo (ex.: 5/hora) — é operação rara. |
| Presigned multipart no `StorageService` (boto3 já presente para o R2) | pequeno | + regra de CORS no bucket para o domínio da aplicação (único pré-requisito de infra). |
| JS do card: seleção do arquivo, upload por partes com progresso, polling | médio | Vanilla JS, mesmo padrão dos outros cards. |
| Adaptação do `publicar.py` para modo `--de-upload <key>` (baixar do R2 em streaming + validar ZIP) | médio | Reutiliza todo o pipeline de inventário/indexação existente. |
| Supervisão do subprocesso (um job por vez, status na tabela, log em arquivo) | médio | Um lock simples ("já existe upload PROCESSANDO") basta — não há por que processar duas edições em paralelo. |

---

## 4. Validação do ZIP (inegociável)

Os quatro limites da tabela do guia original continuam valendo; o que muda é
*onde* são tratados. Antes de extrair qualquer entrada:

1. **Contenção de caminho (Zip-Slip):** rejeitar entradas com caminho
   absoluto, `..`, ou drive letter; extrair sempre resolvendo contra o
   diretório de destino e conferindo `is_relative_to` — a mesma disciplina que
   a revisão apontou como quebrada no fallback de `_resolver_pdf`
   (ACHADOS.md, ALTO): **corrigir aquele achado é pré-requisito deste
   projeto**, para não construir a porta nova ao lado de uma porta aberta.
2. **Zip bomb:** teto de tamanho descomprimido total (ex.: 2× o esperado da
   edição), teto de razão de compressão por entrada e de número de entradas —
   abortar cedo, não ao encher o disco.
3. **Allowlist dentro do ZIP:** aceitar apenas `.pdf`, `fim.json`,
   `index_2.0/*` e a árvore de diretórios esperada; qualquer outra extensão
   reprova o pacote inteiro com erro legível no relatório do upload.
4. **Rótulo da edição:** validar contra a regra que já existe
   (`_RE_ROTULO_INDICE` em `service.py`) **antes** de criar qualquer coisa —
   e criar a edição explicitamente com `status=AGUARDANDO_ATIVACAO` (nunca
   confiar no default `VIGENTE` de `obter_ou_criar_edicao`; ver achado ALTO
   correspondente na revisão).

---

## 5. Fora do escopo desta proposta (mas relacionados)

- **Publicações avulsas** (BO/BS/NPO/BT) já têm upload web funcional e leve
  (`POST /api/avulsas/{id}/anexos`) — nada muda.
- **Atualizações incrementais de um único manual**: o mesmo fluxo serve
  (o ZIP pode conter só o manual atualizado; `sincronizar_catalogo` reconcilia
  apenas os manuais presentes no payload, por desenho). Vale confirmar antes o
  achado "manuais que saíram do acervo nunca são removidos" (ACHADOS.md,
  MÉDIO A CONFIRMAR) para definir se o envio incremental precisa de uma flag
  "reconciliação completa".
- **FIM renumerado em edição futura**: o prefixo `FIM1741_` cravado em
  `catalog.nome_pdf_de_procedimento` (ACHADOS.md, MÉDIO) vai quebrar em
  silêncio na primeira edição enviada com FIM novo — tratar junto com este
  projeto, já que ele é o que torna o envio de edições novas rotina.

---

## 6. Sequência sugerida de implementação

1. Corrigir os pré-requisitos de segurança/robustez apontados na revisão
   (`_resolver_pdf`, default de `obter_ou_criar_edicao`).
2. Presigned multipart no `StorageService` + CORS no bucket (validável por
   script antes de existir UI).
3. Tabela de uploads + endpoints + subprocesso chamando `publicar.py
   --de-upload` com as validações do §4.
4. UI do card (upload com progresso + polling + exibição do relatório).
5. Runbook: atualizar `operacao_publicacoes.md` com o fluxo web e manter o
   fluxo CLI como contingência.

---

## 7. Implementação detalhada da Opção 1

> Plano de construção, ancorado no código existente: `StorageService`
> (`app/shared/core/storage.py`) já tem `R2StorageService` com boto3; a
> dependência de papel `InspetorOuAdmin` já existe
> (`app/bootstrap/dependencies.py:155`); e o `publicar.py` já expõe
> `--edicao`, `--acervo`, `--relatorio-dir` — o modo de upload é uma extensão
> do parser atual, não um script novo.

### 7.1 Infra e configuração (pré-requisito único)

Regra de CORS no bucket R2 — sem ela nada funciona, e há uma pegadinha real:
além de permitir `PUT`, é preciso **expor o header `ETag`**, porque o
JavaScript precisa ler o ETag de cada parte para concluir o multipart:

```json
[
  {
    "AllowedOrigins": ["https://<dominio-da-aplicacao>"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["content-type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Settings novas (`get_settings()`): `publicacoes_upload_max_gb` (teto do ZIP,
ex.: 4), `publicacoes_upload_parte_mb` (ex.: 100) e
`publicacoes_staging_dir` (ex.: `var/publicacoes/staging/`). As chaves no R2
são sempre geradas pelo servidor no padrão
`publicacoes/uploads/<job_id>/edicao.zip` — o cliente nunca escolhe key.

### 7.2 Modelo de dados: `publicacoes_upload_jobs`

Uma linha por tentativa de envio — é o estado que a UI consulta e a trilha de
auditoria de quem enviou o quê:

```
id                UUID PK
rotulo            String(20)  NOT NULL  — validado com _RE_ROTULO_INDICE na entrada
status            Enum: ENVIANDO | PROCESSANDO | CONCLUIDO | FALHOU | CANCELADO
etapa             String(60)  — "baixando", "validando zip", "indexando AMM_PART1…"
progresso_pct     Integer     — 0–100, atualizado pelo worker
erro              Text NULL   — mensagem legível quando FALHOU
file_key          String(500) — key no R2 (gerada pelo servidor)
upload_id_r2      String(200) — id do multipart, para concluir/abortar
tamanho_declarado BigInteger  — bytes informados no início
edicao_id         UUID NULL FK manuais_edicoes  — preenchido ao concluir
criado_por_id     UUID FK usuarios (RESTRICT)
created_at / updated_at
```

Duas regras estruturais, ambas com precedente no módulo:

1. **Índice único parcial "um job ativo por vez"** (`status IN (ENVIANDO,
   PROCESSANDO)`) — mesmo padrão de `uq_manuais_edicoes_vigente_unica`. É o
   lock de single-flight: não existe motivo para processar duas edições em
   paralelo numa VPS pequena, e a constraint fecha a corrida que uma checagem
   em Python deixaria aberta (lição do achado RISCO-01 da revisão).
2. **Máquina de estados só avança**:

```
ENVIANDO ──concluir──► PROCESSANDO ──worker ok──► CONCLUIDO
   │                        │
   ├─cancelar/24h──► CANCELADO (aborta multipart no R2)
   └─erro───────────► FALHOU ◄──worker falhou────┘
```

### 7.3 Extensão do `StorageService`

Quatro métodos novos na ABC, implementados no `R2StorageService` com o
`s3_client` que já existe (todos via `_run_in_executor`, como os atuais):

```python
async def iniciar_multipart(self, file_key: str, content_type: str) -> str: ...
    # create_multipart_upload → UploadId
async def presign_parte(self, file_key: str, upload_id: str, numero: int) -> str: ...
    # generate_presigned_url("upload_part", ExpiresIn=3600)
async def concluir_multipart(self, file_key, upload_id, partes: list[dict]) -> None: ...
    # complete_multipart_upload com [{PartNumber, ETag}]
async def abortar_multipart(self, file_key: str, upload_id: str) -> None: ...
```

`LocalStorageService` (dev sem R2) não suporta presigned URLs do R2. Para garantir
que o desenvolvimento local e os testes funcionem sem dependência da nuvem:
implementar os métodos de multipart no `LocalStorageService` salvando e
montando partes localmente em `var/publicacoes/staging/chunks/<job_id>/`. No
router, caso `storage_backend == "local"`, os endpoints de parte realizam o `PUT`
diretamente contra a API para gravação na pasta de staging local. O caminho de
produção permanece usando a presigned URL do R2.

### 7.4 Endpoints (router.py, seção nova "Upload de edições")

Todos sob `/publicacoes/api/edicoes/uploads`, role `InspetorOuAdmin`
(dependência já existente), rate limit apertado — é operação rara:

| Método/rota | Faz | Recusas |
|---|---|---|
| `POST /uploads` `{rotulo, tamanho_bytes, nome_arquivo}` | valida rótulo (`_validar_rotulo`) e teto de tamanho; cria o job `ENVIANDO`; `iniciar_multipart`; devolve `{job_id, tamanho_parte_mb}` | 409 se já há job ativo (constraint §7.2); 409 se o rótulo já é de edição `VIGENTE`/`ARQUIVADA`; 400 rótulo inválido |
| `POST /uploads/{id}/partes` `{numero}` | devolve URL presigned daquela parte — **sob demanda**, uma por vez, o que dá retry natural (pedir de novo = URL nova) sem gerar 30 URLs antecipadas | 409 se o job não está `ENVIANDO` |
| `POST /uploads/{id}/concluir` `{partes: [{numero, etag}]}` | `concluir_multipart`; `HEAD` no objeto conferindo tamanho == declarado; transiciona para `PROCESSANDO`; dispara o subprocesso (§7.5) | 409 estado errado; 400 partes faltando |
| `POST /uploads/{id}/cancelar` | aborta o multipart no R2 (senão o R2 cobra pelas partes órfãs) e marca `CANCELADO`; se `PROCESSANDO`, sinaliza o worker | — |
| `GET /uploads/{id}` / `GET /uploads?limit=10` | status/etapa/progresso/erro — é o que a UI faz polling | — |

A **ativação não ganha endpoint novo**: quando o job chega a `CONCLUIDO`, a
edição aparece na listagem existente (`GET /api/edicoes`) com
`indice_disponivel=true`, e o botão `[ATIVAR]` segue `AdminRequired`.

### 7.5 Worker: subprocesso `publicar.py --de-upload`

Extensão do parser atual (que já tem `--edicao`, `--acervo`,
`--pular-upload`, `--relatorio-dir`):

```bash
python -m scripts.publicacoes.publicar \
    --edicao 2027 --de-upload publicacoes/uploads/<job_id>/edicao.zip --job-id <job_id>
```

Sequência dentro do script (tudo que já existe é reaproveitado sem mudança):

1. **Checar disco**: `shutil.disk_usage` — exigir espaço para ZIP + extração
   + margem; senão `FALHOU` com erro legível ("libere X GB").
2. **Baixar em streaming** (`download_fileobj`) para
   `<staging>/<job_id>/edicao.zip` — nunca materializar em RAM.
3. **Validar o ZIP** (checklist do §4: contenção, bomba, allowlist, contagem)
   lendo o índice central do ZIP **antes** de extrair qualquer byte.
4. **Extrair contido** para `<staging>/<job_id>/Manuais/`.
5. **Rodar o pipeline existente** com `--acervo <staging>/<job_id>/Manuais`:
   inventário, diff por hash, extração de texto, `catalog.<rotulo>.db`,
   edição `AGUARDANDO_ATIVACAO` explícita, `relatorio_diff`.
6. **Promover o staging ao acervo definitivo**
   (`var/publicacoes/acervo/edicoes/<rotulo>/`) com `os.replace` do diretório
   — a promoção é o último passo, então um crash em qualquer etapa anterior
   nunca deixa acervo pela metade no lugar definitivo.
7. Marcar `CONCLUIDO` (+ `edicao_id`), apagar o staging local e apagar explicitamente o ZIP temporário do R2 (`s3_client.delete_object(Bucket=bucket, Key=file_key)` da chave em `publicacoes/uploads/<job_id>/edicao.zip`) — evitando acúmulo de arquivos temporários de 3 GB no bucket R2 (o snapshot oficial retido da edição é gravado separadamente em `publicacoes/snapshots/<rotulo>.zip`).

O job row em `publicacoes_upload_jobs` é atualizado dinamicamente pelo próprio script
(que abre sua própria sessão assíncrona de banco via `get_session_factory()`, mesmo
padrão de `indexar.py`) em fronteiras de etapa e a cada manual processado — com 34
manuais, isso dá progresso em incrementos graduais de ~3%, permitindo o acompanhamento em tempo real na UI.

Supervisão no lado web (`app/bootstrap/tasks.py` é o lugar natural):

- disparo com `asyncio.create_subprocess_exec`, guardando o PID no job;
- **recuperação de crash**: na subida da aplicação, todo job `PROCESSANDO`
  cujo processo não existe mais vira `FALHOU` ("processo interrompido —
  reenvie"); como o pipeline é idempotente, reenviar é sempre seguro;
- **faxina diária**: abortar multiparts `ENVIANDO` com mais de 24 h e apagar
  stagings órfãos (multipart incompleto no R2 custa dinheiro).

### 7.6 Front-end (vanilla JS, card Publicações)

`publicacoes_upload.js`, mesmo padrão dos outros cards:

1. `<input type="file" accept=".zip">` + drag-and-drop na área do card.
2. Fatiar com `File.prototype.slice` no tamanho de parte informado pelo
   servidor; enviar com `fetch` PUT, **2 partes em paralelo** (bom uso do
   link sem saturar), lendo o `ETag` do response header de cada uma.
3. Retry por parte (3 tentativas, backoff; ao esgotar, pedir URL nova ao
   endpoint de partes — cobre URL expirada em upload longo).
4. Barra de progresso do envio = partes confirmadas × tamanho; depois do
   `concluir`, troca para polling de `GET /uploads/{id}` a cada 3–5 s
   mostrando `etapa` + `progresso_pct`.
5. Estados finais: `CONCLUIDO` → recarrega a lista de edições e mostra o link
   do relatório de diff; `FALHOU` → exibe `erro` com botão "tentar novamente"
   (que simplesmente inicia um job novo).
6. `beforeunload` com aviso enquanto `ENVIANDO` (fechar a aba mata o envio;
   o processamento, não — ele roda no servidor).

### 7.7 Segurança — resumo do que cada camada garante

| Camada | Garantia |
|---|---|
| Endpoint inicial | papel `InspetorOuAdmin`; rótulo validado com a regra já existente do módulo; teto de tamanho declarado; key gerada só pelo servidor |
| Presigned URL | curta duração (1 h), escopo de UMA parte de UM objeto; o navegador nunca vê credencial do R2 |
| Concluir | tamanho real conferido contra o declarado antes de processar |
| Worker | validação completa do ZIP (§4) antes de extrair; extração contida; disco checado antes; staging isolado até a promoção final |
| Ativação | continua `AdminRequired`, atômica e reversível — o upload não consegue mudar o que está em vigor |
| Auditoria | job row registra quem enviou, quando, qual rótulo e o resultado; `publicado_por_id` continua registrando quem ativou |

### 7.8 Testes mínimos para o gate

- **Unidade (validador de ZIP)**: fixtures com Zip-Slip (`../`, caminho
  absoluto, drive letter), zip bomb (razão de compressão alta), extensão fora
  da allowlist, ZIP saudável de amostra — o validador é código puro, barato
  de cobrir exaustivamente.
- **Unidade (máquina de estados)**: transições ilegais devolvem 409; job
  ativo bloqueia segundo `POST /uploads` (a constraint, não só o código).
- **Integração**: fluxo completo contra `LocalStorageService`/modo dev com um
  mini-acervo de 2 manuais — do `POST /uploads` até `indice_disponivel=true`
  e ativação bem-sucedida.
- **Integração (recuperação)**: matar o worker no meio → job vira `FALHOU`
  na subida; reenviar converge (idempotência já testada pelo módulo).
- **Manual, uma vez**: upload real de ~3 GB via R2 em rede doméstica típica,
  medindo memória do worker web durante (deve ficar plana — nada do volume
  passa por ele).

### 7.9 Ordem de entrega (fatias verificáveis)

1. `StorageService` multipart + script de teste de CORS (sem UI — valida a
   infra primeiro, que é o único risco fora do nosso controle).
2. Migração + model do job + endpoints com testes (worker ainda fake).
3. `publicar.py --de-upload` (download, validação, staging, promoção) +
   testes do validador.
4. Supervisão (disparo, recuperação de crash, faxina).
5. JS do card + polling.
6. Runbook em `operacao_publicacoes.md` + remoção do aviso "não há upload
   web" de `envio_publicacoes_zip.md` (apontando para este fluxo).

---

## 8. Referências

- [envio_publicacoes_zip.md](envio_publicacoes_zip.md) — motivação dos limites e fluxo CLI atual.
- [opcoes_upload_inspetor.md](opcoes_upload_inspetor.md) — as três opções comparadas.
- [operacao_publicacoes.md](operacao_publicacoes.md) — runbook operacional do módulo.
- `app/modules/publicacoes/ACHADOS.md` — revisão de código de 2026-08-08 (achados citados nos §4–§5).
