# Sugestão — Envio de Atualizações das Publicações pela Web

> Proposta de fluxo para o envio de atualizações do acervo de publicações,
> consolidando [envio_publicacoes_zip.md](envio_publicacoes_zip.md) (por que
> não existe upload `.zip` via HTTP hoje) e
> [opcoes_upload_inspetor.md](opcoes_upload_inspetor.md) (as três opções de
> arquitetura para o INSPETOR), à luz do código atual do módulo
> (`app/modules/publicacoes/`) e dos achados da revisão de 2026-08-08
> (`app/modules/publicacoes/ACHADOS.md`).

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

## 7. Referências

- [envio_publicacoes_zip.md](envio_publicacoes_zip.md) — motivação dos limites e fluxo CLI atual.
- [opcoes_upload_inspetor.md](opcoes_upload_inspetor.md) — as três opções comparadas.
- [operacao_publicacoes.md](operacao_publicacoes.md) — runbook operacional do módulo.
- `app/modules/publicacoes/ACHADOS.md` — revisão de código de 2026-08-08 (achados citados nos §4–§5).
