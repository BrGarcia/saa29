# Módulo WhatsApp — Estudo de Viabilidade e Plano de Implementação

> **Versão:** 2.0 — 20 de agosto de 2026
> **Versão anterior:** 1.0 — 17 de abril de 2026, substituída na íntegra por este documento. O texto original permanece recuperável no histórico do git, em `docs/backlog/Melhorias Futuras/implementacao_whatsapp.md` (commit e3af49b); todos os pontos dele que foram corrigidos estão tabelados no **Anexo A**.
> **Status:** Backlog — bloqueado por decisão institucional (§2) antes de qualquer linha de código.
>
> A v2 é uma revisão técnica da v1. Foram encontrados **25 erros conceituais, factuais ou de
> aderência ao código real do SAA29** — todos listados com o "antes/depois" no **Anexo A**.
> As três correções mais graves:
> 1. O modelo de cobrança descrito na v1 **não existe mais** desde 01/07/2025 (§4).
> 2. O ponto de integração proposto na v1 dispara a notificação **antes do commit** (§7.2).
> 3. A v1 não trata **confidencialidade operacional** de dados de disponibilidade de frota (§2).

---

## 0. Sumário executivo

| | |
| :--- | :--- |
| **Recomendação técnica** | Meta WhatsApp Cloud API (canal oficial), com padrão *outbox* + worker |
| **Recomendação de conteúdo** | **Alerta sem carga**: mensagem neutra + link para o SAA29, sem matrícula/ATA/descrição |
| **Custo estimado** | R$ 10 a R$ 65/mês, conforme nº de destinatários e eventos (§4.3) — a v1 subestimou |
| **Esforço** | ~24–34 h de desenvolvimento + 2 a 15 dias corridos de espera externa (§12) |
| **Bloqueio atual** | Autorização da seção/comando quanto ao tráfego de dados operacionais em plataforma de terceiros (§2) |
| **Decisão pendente** | Lista de destinatários **ou** grupo? A API oficial **não envia para grupos** (§3.5) |

**O que muda em relação à v1, em uma frase:** o WhatsApp continua viável e barato, mas
não é "4 horas de trabalho e R$ 5/mês" — é um subsistema de notificação com fila, retentativa,
webhook, consentimento e auditoria, cujo maior risco não é técnico, é de sigilo operacional.

---

## 1. Objetivo e escopo

### 1.1 Objetivo
Notificar automaticamente, via WhatsApp, os responsáveis pela manutenção quando ocorrerem
eventos relevantes no SAA29.

### 1.2 Eventos candidatos (gatilhos)

| Evento | Origem no código | Prioridade |
| :--- | :--- | :---: |
| Pane aberta que torna a aeronave INDISPONÍVEL | `panes/service.py::criar_pane` + `sincronizar_status_aeronave` | **Alta** |
| Pane aberta (demais casos) | `panes/service.py::criar_pane` | Média |
| Pane resolvida | `panes/service.py::concluir_pane` | Média |
| Vencimento crítico a expirar | `modules/vencimentos` | Média (fase 2) |
| Usuário criado/desativado | `modules/auth` | **Fora de escopo** — evento administrativo, sem urgência operacional; e-mail/sistema já bastam |

> **Correção à v1 — o gatilho "AOG/alta prioridade" não é implementável hoje.**
> A v1 recomenda "ativar notificações apenas para panes de alta prioridade ou AOG", mas o modelo
> `Pane` (`app/modules/panes/models.py`) **não possui campo de prioridade ou criticidade** — só
> `status` (`ABERTA`/`RESOLVIDA`), `sistema_ata_id`, `descricao` e datas.
> Duas saídas:
> - **(A) Recomendada — critério derivado, sem migração:** notificar quando a pane fizer a aeronave
>   transitar de `DISPONIVEL` para `INDISPONIVEL` em `sincronizar_status_aeronave()`. Isso é,
>   operacionalmente, a definição de AOG, e usa uma regra que já existe e já é fonte única de verdade.
> - **(B) Campo novo:** adicionar `criticidade` em `Pane` + migração Alembic + UI. Só justifica se o
>   critério de criticidade for independente da disponibilidade da aeronave.

### 1.3 Fora de escopo desta fase
Conversas bidirecionais completas (abrir pane pelo WhatsApp), envio de anexos/fotos,
notificação para efetivo externo ao esquadrão, e integração com o módulo mobile (que já
tem PWA e pode receber Web Push — ver §3.6).

---

## 2. Restrição nº 1: sigilo operacional e LGPD

> Esta seção não existia na v1 e é a razão de o módulo estar **bloqueado**, não "pronto para codar".

O SAA29 gerencia manutenção de uma frota **A-29 Super Tucano**. O conteúdo proposto na v1 para a
mensagem — matrícula da aeronave, sistema ATA afetado, descrição da pane e data — é, em conjunto,
um **retrato de indisponibilidade da frota**. Ao enviá-lo por WhatsApp:

- o dado sai do domínio institucional e transita/é retido por infraestrutura da Meta;
- fica replicado em aparelhos **pessoais**, fora de qualquer política de descarte;
- permanece em backups de nuvem do próprio celular (iCloud/Google), fora de controle;
- em caso de perda/roubo de aparelho, o histórico completo de panes vai junto.

### 2.1 Princípio recomendado: "alerta sem carga"

A notificação deve funcionar como **campainha**, não como relatório:

```
🔧 SAA29 — Nova pane registrada.
Consulte os detalhes no sistema: https://<dominio>/panes
```

Vantagens, além do sigilo:
- Elimina o risco de reprovação/erro de parâmetro por texto livre (§9.2);
- Reduz o template a zero ou um parâmetro → menos pontos de falha;
- Mantém o SAA29 como fonte única de verdade (o usuário sempre vê o estado atual, não um retrato);
- Torna a discussão de classificação da informação trivial: nada operacional trafega.

Uma variante intermediária, **se autorizada**: incluir apenas um identificador não sensível
(ex.: nº sequencial da pane) para permitir busca direta, sem matrícula nem descrição.

### 2.2 LGPD e consentimento

O número de WhatsApp de um militar/servidor é **dado pessoal** (Lei 13.709/2018). Requisitos:

| Requisito | Implementação |
| :--- | :--- |
| Base legal e finalidade declarada | Registrar no termo de adesão: "notificação de manutenção do SAA29" |
| **Opt-in explícito** (também exigido pela Política da Meta) | Tabela `notificacao_destinatario` com `opt_in_em`, `opt_in_origem`, `opt_in_ip` |
| **Opt-out a qualquer tempo** | Botão no perfil do usuário **e** palavra-chave `SAIR` processada pelo webhook |
| Minimização | §2.1 — "alerta sem carga" |
| Retenção | Expurgo do outbox e dos logs de envio após N dias (sugestão: 90) |
| Transparência | Tela de configurações listando quem recebe o quê |

> **Não usar lista fixa em variável de ambiente** (como a `WHATSAPP_DESTINATARIOS` da v1): uma
> string no `.env` não registra consentimento, não tem data, não tem opt-out e não sai do ar quando
> a pessoa é transferida ou desativada no sistema.

### 2.3 Ação requerida antes do desenvolvimento
1. Homologar com a seção/comando **qual conteúdo** pode trafegar (recomendação: §2.1).
2. Definir se o uso é em **número institucional** (recomendado) ou pessoal.
3. Colher opt-in formal dos destinatários.

---

## 3. Opções de integração

### 3.1 Opção A — Meta WhatsApp Cloud API (oficial)

| Aspecto | Detalhe |
| :--- | :--- |
| **Provedor** | Meta |
| **Tipo** | API oficial hospedada pela Meta (Graph API) |
| **Estabilidade** | Alta |
| **Custo** | Por mensagem de template entregue (§4) |
| **Risco de bloqueio** | **Baixo — não nulo** (ver abaixo) |
| **Requisitos** | Conta Meta Business + verificação de negócio + número dedicado |
| **Complexidade** | Média (alta se incluir webhook) |

> **Correção à v1 — "Risco de banimento: Nenhum (canal oficial)" é falso.**
> O canal oficial não é imune a bloqueio, apenas o bloqueio é *previsível e sinalizado*. A Meta mantém
> um **quality rating** por número (verde/amarelo/vermelho) alimentado por bloqueios e denúncias dos
> destinatários. As consequências reais são:
> - rebaixamento do *messaging limit* (nº de destinatários únicos/24 h);
> - **pausa automática de um template** com muitas reações negativas (24 h, 3 dias, ou desativação);
> - restrição ou banimento do número por violação da Política Comercial.
>
> Ou seja: enviar sem opt-in a quem não quer receber **derruba o canal oficial também**. O risco é
> baixo *porque* existe opt-in e volume pequeno — não porque a API é oficial.

**Como funciona**
1. App do tipo *Business* no Meta for Developers, com o produto WhatsApp ativado.
2. Número de telefone cadastrado, verificado e **registrado com PIN de 2 etapas** (§10).
3. Templates submetidos e aprovados pela Meta (§9).
4. O SAA29 faz `POST /{version}/{PHONE_NUMBER_ID}/messages` com o template preenchido.
5. (Opcional, mas recomendado) A Meta chama o webhook do SAA29 com o status de entrega.

### 3.2 Opção B — Evolution API (self-hosted)

| Aspecto | Detalhe |
| :--- | :--- |
| **Provedor** | Open-source (Apache-2.0) |
| **Tipo** | Auto-hospedado via Docker; usa **Baileys** por baixo |
| **Estabilidade** | Média — acompanha mudanças do protocolo WhatsApp Web |
| **Custo** | Sem licença (custa o servidor + manutenção) |
| **Risco de banimento** | **Alto** para envio automatizado (ver abaixo) |
| **Requisitos** | Docker + número WhatsApp comum + (dependendo da versão) Postgres/Redis |
| **Complexidade** | Alta |

> **Correção à v1 — o risco não é "moderado", é alto.**
> Evolution API e WAHA não falam com uma API da Meta: eles **reimplementam o protocolo do WhatsApp
> Web** (via Baileys). Isso é expressamente vedado pelos Termos de Serviço do WhatsApp, que proíbem
> clientes não autorizados e envio automatizado. Não há SLA, não há aviso prévio e não há recurso:
> o número simplesmente é banido, junto com o histórico de conversas dele. Para um número
> **institucional**, esse é um risco desproporcional ao benefício de economizar ~R$ 30/mês.

Detalhe de implementação (v2 da Evolution API): `POST /message/sendText/{instance}`, header `apikey`,
corpo `{"number": "...", "text": "..."}`. **Atenção à versão** — a v1 da Evolution usava
`{"number": ..., "textMessage": {"text": ...}}`, e o exemplo da v1 deste documento não indicava versão.

### 3.3 Opção C — WAHA (WhatsApp HTTP API)

| Aspecto | Detalhe |
| :--- | :--- |
| **Tipo** | Auto-hospedado via Docker; motores NOWEB (Baileys), WEBJS e GOWS |
| **Custo** | **WAHA Core gratuito com limitações; WAHA Plus é pago (assinatura)** |
| **Risco de banimento** | Alto (mesma natureza da Opção B) |
| **Complexidade** | Média-Alta |

> **Correção à v1 — WAHA não é simplesmente "gratuito".** O Core é livre, porém limitado
> (nº de sessões e recursos de mídia/segurança ficam na edição Plus, paga). Conferir a matriz de
> recursos vigente antes de contar com qualquer funcionalidade específica.

### 3.4 Sobre a "NOTA MENTAL: pesquisar Baileys" (v1)

**Respondida — Baileys não é uma quarta opção; é o que já roda dentro das opções B e C.**

- Baileys é uma biblioteca **TypeScript/Node.js** que implementa o protocolo WhatsApp Web
  multi-device via WebSocket (sem navegador headless, diferente das libs antigas baseadas em Puppeteer).
- Evolution API e WAHA (motor NOWEB) são, essencialmente, **um invólucro HTTP em volta do Baileys**.
- Usar Baileys direto significa: (a) escrever e manter um **serviço Node.js separado** dentro de uma
  stack Python/FastAPI; (b) gerenciar a persistência da sessão (credenciais do pareamento) e a
  reconexão; (c) assumir o **mesmo risco de banimento**, sem o invólucro pronto.
- Licença/termos do repositório (WhiskeySockets/Baileys) devem ser conferidos na fonte antes de
  qualquer uso — o projeto declara explicitamente não ter vínculo com o WhatsApp.

**Conclusão:** só considerar Baileys direto se a migração para Node.js
(`docs/MIGRACAO_NODEJS_ESPECIFICACAO.md`) for adiante **e** o risco de banimento for aceito. Caso
contrário, ele não adiciona nada sobre a Opção B.

### 3.5 Comparativo corrigido

| Critério | Meta Cloud API | Evolution API | WAHA |
| :--- | :---: | :---: | :---: |
| Custo mensal (cenário SAA29) | R$ 10–65 (§4.3) | R$ 0 de licença + VPS + manutenção | Core R$ 0 / Plus pago + VPS |
| Estabilidade | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Risco de bloqueio do número | Baixo (gerenciável) | **Alto** | **Alto** |
| Conformidade com os Termos do WhatsApp | ✅ | ❌ | ❌ |
| Envia para **grupos** | ❌ | ✅ | ✅ |
| Mensagem de texto livre | Só dentro da janela de 24 h (§5) | ✅ | ✅ |
| Status de entrega/leitura | ✅ (via webhook) | Parcial | Parcial |
| Infra adicional | Nenhuma | Docker + VPS + banco | Docker + VPS |
| Manutenção recorrente | Renovação de token/versão da API | Reconexão de sessão, QR, updates | Idem |

> **Contradição da v1 resolvida.** O objetivo declarado na v1 era "enviar para **um grupo** ou lista
> de responsáveis", e a recomendação era a Meta Cloud API — que **não envia para grupos**. As duas
> coisas não podem coexistir. **Decisão adotada nesta v2: lista de destinatários individuais**, que é
> o único caminho compatível com o canal oficial (e, de quebra, o único compatível com opt-out
> individual e com a §2). Se "grupo" for requisito inegociável, a única saída é a Opção B/C, com o
> risco da §3.2 assumido formalmente.

### 3.6 Alternativa que a v1 não considerou: Web Push no PWA

O módulo mobile do SAA29 **já tem service worker e PWA**. Notificação via Web Push:
custo zero, sem intermediário externo, sem número de telefone, sem LGPD de dado de contato,
sem sigilo trafegando fora, e sem risco de banimento. Em contrapartida: exige o app instalado,
tem entrega menos confiável em iOS e não alcança quem não abriu o sistema.

**Recomendação:** tratar Web Push como o canal **padrão** e o WhatsApp como canal de **exceção**
(apenas eventos de alta prioridade). Isso reduz volume, custo e superfície de exposição
simultaneamente. Avaliar em estudo próprio.

---

## 4. Modelo de cobrança vigente (correção principal da v1)

> ⚠️ **A v1 descreve um modelo de preços que foi descontinuado.** Ela fala em "custo por **conversa**
> iniciada" e em "as primeiras **1.000 conversas** de serviço grátis por mês". Nenhuma das duas coisas
> vale mais.

### 4.1 O que mudou

| Data | Mudança |
| :--- | :--- |
| **01/11/2024** | O pacote de **1.000 conversas gratuitas/mês foi extinto**. Em troca, **conversas de serviço passaram a ser gratuitas e ilimitadas**, e templates **utility** enviados dentro de uma janela de atendimento aberta passaram a ser gratuitos. |
| **01/07/2025** | Fim do modelo por **conversa de 24 h**. Passa a valer cobrança **por mensagem**, por categoria de template (marketing / utility / authentication). Mensagens de serviço (texto livre) seguem gratuitas. |

**Consequência prática para o SAA29:** antes, várias mensagens dentro da mesma janela de 24 h eram
cobradas como **uma** conversa. Agora **cada mensagem de template para cada destinatário é cobrada
separadamente**. É por isso que a conta da v1 ficou baixa demais.

### 4.2 Tabela de referência (Brasil — conferir a tabela oficial vigente antes de orçar)

| Categoria | Uso no SAA29 | Preço unitário aprox. |
| :--- | :--- | :---: |
| **Utility** | Alerta de pane/conclusão | ~US$ 0,008 / mensagem |
| Authentication | Não se aplica | ~US$ 0,03 / mensagem |
| Marketing | **Não usar** | ~US$ 0,06 / mensagem |
| **Service** (texto livre na janela de 24 h) | Respostas do bot de consulta | **Grátis** |
| Utility dentro de janela de atendimento aberta | Alerta a quem acabou de falar com o bot | **Grátis** |

> A Meta reajusta a tabela por país periodicamente. Tratar estes valores como ordem de grandeza,
> não como orçamento fechado — conferir a tabela oficial de preços antes de qualquer contratação.

### 4.3 Custo real do SAA29 (corrigido — multiplicado por destinatário)

Fórmula: `mensagens/mês = eventos/mês × destinatários` · `custo = mensagens × US$ 0,008`
Base: 4 panes/dia ≈ 120 aberturas/mês. Câmbio de referência: R$ 5,50/US$.

| Cenário | Eventos/mês | Destinatários | Mensagens/mês | US$/mês | R$/mês |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Cenário da v1** (só abertura, 1 destinatário) | 120 | 1 | 120 | 0,96 | ~5 |
| Abertura + conclusão, 2 destinatários | 240 | 2 | 480 | 3,84 | ~21 |
| Abertura + conclusão, 6 destinatários | 240 | 6 | 1.440 | 11,52 | **~63** |
| **Recomendado** — só AOG (~30% das aberturas), 6 destinatários | 36 | 6 | 216 | 1,73 | **~10** |

**Leitura:** o número de R$ 5/mês da v1 era o piso absoluto (um destinatário, metade dos eventos).
O custo real é dominado pelo **tamanho da lista**, não pelo volume de panes. Restringir o gatilho a
AOG (§1.2) é o que mantém o custo em uma casa decimal.

### 4.4 Risco de recategorização de template

A Meta **classifica automaticamente** o template no momento da aprovação e pode **recategorizá-lo**
depois. Se um template `utility` for reclassificado como `marketing`, o custo por mensagem sobe
cerca de **8×** sem aviso no código. Mitigações: manter o texto estritamente transacional (sem
convites, promoções ou linguagem de engajamento), monitorar a categoria no WhatsApp Manager, e
alarmar em cima do custo mensal.

---

## 5. Push × Pull — o que é grátis, e por quê

### 5.1 A regra que governa tudo: a janela de 24 h
Mensagens de **texto livre** só podem ser enviadas dentro de **24 h após a última mensagem enviada
pelo usuário**. Fora dessa janela, **apenas templates aprovados** — e templates `utility` fora da
janela são cobrados. Passada a janela, a tentativa de texto livre falha com erro `131047`.

### 5.2 Push (notificação ativa)
- Sempre inicia fora da janela → **sempre template, sempre cobrado**.
- Vantagem: proatividade real (o mecânico não precisa lembrar de consultar).
- Complexidade: baixa no envio, **média/alta** quando se soma fila, retentativa e auditoria (§7).

### 5.3 Pull (bot de consulta)
- O usuário manda "oi" / "panes" → abre a janela → a resposta do SAA29 é **texto livre e gratuita**.
- **Correção à v1:** o motivo da gratuidade não é o pacote de "1.000 conversas/mês" (extinto). É que
  **mensagens de serviço são gratuitas e ilimitadas** desde 11/2024. O resultado (custo zero) é o
  mesmo — a justificativa da v1 é que estava errada, e o teto de 1.000 não existe.
- **Custo escondido que a v1 não mencionou:** o Pull **exige um webhook público em HTTPS**, com
  certificado válido, handshake de verificação e validação de assinatura (§7.6). Isso não é "média
  complexidade" — é o item mais caro do projeto e o que mais mexe na segurança do SAA29.

### 5.4 O webhook não é opcional nem no Push
Sem consumir os eventos `statuses` do webhook, o sistema **não sabe se a mensagem foi entregue**.
O `200 OK` do `POST /messages` significa apenas "aceito para envio" — falhas de entrega
(número inexistente, usuário sem WhatsApp, template pausado) chegam **depois**, só pelo webhook.
Um alerta de AOG que silenciosamente não chegou é pior do que não ter alerta.

---

## 6. Recomendação

### 🏆 Meta Cloud API, em duas fases, com "alerta sem carga"

1. **Fase 1 — Push mínimo confiável.** Somente o gatilho AOG (§1.2-A), template sem dados
   operacionais (§2.1), envio via outbox + worker (§7), webhook **apenas** para `statuses`.
   Custo estimado: ~R$ 10/mês. É o que entrega valor com a menor superfície de risco.
2. **Fase 2 — Pull (bot de consulta).** Reaproveita o mesmo webhook para mensagens recebidas,
   com comandos `PANES`, `STATUS <matrícula>`, `SAIR`. Custo marginal ~zero. Só faz sentido depois
   que a Fase 1 estiver estável e auditada.

**Por que não a Evolution API / WAHA:** economizar ~R$ 30/mês em troca de um número institucional
sujeito a banimento sem aviso, com manutenção de sessão recorrente, é um mau negócio para um sistema
cuja função é avisar sobre indisponibilidade de aeronave. Reconsiderar apenas se a Meta Business
Verification for inviável administrativamente.

**Reavaliar antes de tudo:** o Web Push do PWA (§3.6) resolve boa parte do caso de uso com custo
zero e sem exposição externa.

---

## 7. Arquitetura proposta (corrigida para o código real do SAA29)

### 7.1 Erro estrutural da v1: onde a notificação era disparada

A v1 propõe `criar_pane() ──► commit DB ──► enviar_notificacao()` e manda "chamar
`enviar_notificacao()` após `criar_pane()`". **No SAA29 isso dispara antes do commit.**

Verificado no código:
- `app/modules/panes/service.py::criar_pane` termina com `await db.flush()` / `db.refresh(...)` —
  **não commita**;
- `app/modules/panes/router.py::criar_pane` também não commita;
- o commit acontece na dependência `get_db` (`app/bootstrap/dependencies.py:34`), **depois** que o
  handler retorna, com `rollback()` no `except`.

Consequência: qualquer envio feito de dentro do service (ou do router) sai **antes** de a transação
ser confirmada. Se a serialização da resposta, um validador ou o próprio commit falhar, a pane é
revertida — mas a mensagem "Nova pane registrada" **já foi entregue** e não pode ser desfeita.
Fantasma clássico de notificação.

### 7.2 Correção: padrão *outbox* transacional

A gravação do evento entra **na mesma transação** da pane; o envio sai **fora** dela, feito por um
worker. Assim, "pane existe" e "notificação será enviada" são atômicos, e uma indisponibilidade
da Meta não segura a requisição HTTP do usuário.

```
 REQUISIÇÃO HTTP (rápida, sem rede externa)
┌──────────────────────────────────────────────────────────────┐
│ router.criar_pane                                            │
│   └─ service.criar_pane(db, ...)                             │
│        ├─ db.add(Pane)                                       │
│        └─ notificacoes.enfileirar(db, evento, destinatarios) │
│             └─ db.add(NotificacaoOutbox)  ◄── mesma transação│
│                                                              │
│   get_db ──► COMMIT  (pane + outbox, atômico)                │
└───────────────────────────────┬──────────────────────────────┘
                                │ after_commit (opcional: acorda o worker)
                                ▼
 WORKER (loop no lifespan, fora do ciclo da requisição)
┌──────────────────────────────────────────────────────────────┐
│ 1. claim atômico  UPDATE ... SET status='ENVIANDO' RETURNING │
│ 2. monta template, sanitiza parâmetros (§9.2)                │
│ 3. POST Graph API  (httpx.AsyncClient compartilhado)         │
│ 4. sucesso → ENVIADA + wamid  |  falha → backoff/ FALHOU     │
└───────────────────────────────┬──────────────────────────────┘
                                ▼
                       Meta Graph API  ──►  destinatários
                                │
                                ▼ webhook (statuses)
             POST /whatsapp/webhook ──► atualiza status de entrega
```

### 7.3 Concorrência: 2 workers Gunicorn

`gunicorn_conf.py` define `workers = 2` por padrão. Um loop de fila iniciado no `lifespan` roda
**uma vez por worker** → sem proteção, cada mensagem é enviada **em duplicidade**.

Solução (segue o precedente do módulo Publicações, que usa índice único parcial para o mesmo fim):
*claim* atômico antes de enviar, com `RETURNING` (SQLite ≥ 3.35, satisfeito pelo Python 3.12 do
projeto), e nunca "ler depois atualizar":

```sql
UPDATE notificacao_outbox
   SET status = 'ENVIANDO', reivindicado_em = :agora, reivindicado_por = :worker_id
 WHERE id = (SELECT id FROM notificacao_outbox
              WHERE status = 'PENDENTE' AND proxima_tentativa_em <= :agora
              ORDER BY criado_em LIMIT 1)
RETURNING id;
```

Registros presos em `ENVIANDO` há mais de N minutos (crash/restart) voltam para `PENDENTE` no
startup — mesmo tratamento que `recuperar_jobs_interrompidos()` já faz em `tasks.py`.

### 7.4 Modelo de dados (nova migração Alembic)

**`notificacao_destinatario`** — substitui a `WHATSAPP_DESTINATARIOS` do `.env`:

| Coluna | Tipo | Observação |
| :--- | :--- | :--- |
| `id` | UUID | |
| `usuario_id` | UUID FK → `usuarios.id` | nullable (permite contato avulso) |
| `telefone_e164` | str(20) | só dígitos, com DDI: `5521999998888` (§7.7) |
| `ativo` | bool | desligar sem apagar histórico |
| `eventos` | str/JSON | quais gatilhos assina (`AOG`, `PANE_ABERTA`, `PANE_RESOLVIDA`) |
| `opt_in_em`, `opt_in_origem`, `opt_out_em` | datetime/str | trilha de consentimento (§2.2) |

> `Usuario` (`app/modules/auth/models.py`) **não tem campo de telefone** — só `ramal`. Por isso a
> tabela própria, em vez de uma coluna nova em `usuarios`: ela carrega o consentimento, que é dado
> de outra natureza e tem ciclo de vida próprio.

**`notificacao_outbox`** — a fila:

| Coluna | Tipo | Observação |
| :--- | :--- | :--- |
| `id` | UUID | |
| `evento` | str(40) | `PANE_AOG`, `PANE_ABERTA`, `PANE_RESOLVIDA` |
| `entidade_tipo` / `entidade_id` | str / UUID | referência genérica (pane, vencimento…) |
| `destinatario_id` | UUID FK | **uma linha por destinatário** — retentativa é individual |
| `payload` | JSON | parâmetros do template, já sanitizados |
| `status` | str(15) | `PENDENTE` · `ENVIANDO` · `ENVIADA` · `ENTREGUE` · `FALHOU` · `DESCARTADA` |
| `tentativas` | int | |
| `proxima_tentativa_em` | datetime | backoff exponencial |
| `dedupe_key` | str **UNIQUE** | `f"{evento}:{entidade_id}:{destinatario_id}"` — idempotência |
| `wamid` | str | id da mensagem na Meta, para casar com o webhook |
| `erro_codigo` / `erro_msg` | str | diagnóstico |
| `criado_em` / `atualizado_em` | datetime | |

O `dedupe_key` único é o que impede duplicidade em retry, replay de webhook ou reprocessamento
após restart.

### 7.5 Política de retentativa

| Situação | Ação |
| :--- | :--- |
| HTTP 200 | `ENVIADA`, guarda `wamid`, aguarda webhook para `ENTREGUE` |
| HTTP 429 / 5xx / timeout | Retry com backoff exponencial (1 min, 5, 15, 60, 240), máx. 5 tentativas |
| 4xx permanente (template inexistente `132001`, parâmetros `132000`, número inválido `133010`) | `FALHOU` **sem retry** — retentar é desperdiçar chamada e sujar o quality rating |
| Evento AOG que falhou em todas as tentativas | Alarme no log **e** aviso visível no dashboard — nunca falhar em silêncio |

> **Correção à v1.** A v1 diz apenas "tratar como operação secundária com `try/except`". Um
> `try/except` que engole a exceção transforma "o alerta de AOG não chegou" em nada: sem log
> estruturado, sem retentativa, sem visibilidade. Falha silenciosa é aceitável para o *usuário*
> (a pane deve ser criada de qualquer jeito), **não** para o *sistema*.

### 7.6 Webhook — três obstáculos que a v1 não mencionou

1. **O middleware CSRF global do SAA29 bloquearia o POST da Meta.**
   `app/shared/middleware/csrf.py` valida CSRF em **todo** `POST/PUT/PATCH/DELETE`, com uma única
   exceção (o header de bypass usado nos testes). A Meta não envia token CSRF — o webhook receberia
   `403` em toda chamada. É preciso incluir uma isenção explícita por caminho
   (`/whatsapp/webhook`), estreita e documentada, protegida pela validação de assinatura abaixo.
2. **Validação de assinatura obrigatória.** Todo POST da Meta traz o header `X-Hub-Signature-256`
   (HMAC-SHA256 do **corpo bruto** com o App Secret). Sem conferir isso — em tempo constante
   (`hmac.compare_digest`) e sobre o corpo **antes** de qualquer parsing — o endpoint é um injetor
   público de eventos falsos. Também é preciso o handshake `GET` com `hub.mode`, `hub.verify_token`
   e devolução de `hub.challenge`.
3. **Infraestrutura.** A Meta exige **HTTPS público com certificado válido de CA** (autoassinado não
   serve) e resposta `200` rápida — caso contrário reenvia. Isso significa domínio + TLS no VPS, e
   `ALLOWED_HOSTS` incluindo esse domínio. Em desenvolvimento (localhost), só com túnel
   (`cloudflared`/`ngrok`).

Além disso: responder `200` **imediatamente** e processar depois (o evento entra numa fila/tarefa),
e tratar reentrega — a Meta pode enviar o mesmo evento mais de uma vez.

### 7.7 Detalhes de implementação que a v1 errou ou omitiu

| Item | Problema na v1 | Correção |
| :--- | :--- | :--- |
| Cliente HTTP | `async with httpx.AsyncClient()` a **cada** envio | Um `AsyncClient` único criado no `lifespan` (pool de conexões, TLS reaproveitado), com `timeout=10s` explícito |
| Versão da Graph API | `v21.0` fixa no código | Variável de configuração — versões da Graph API expiram em ~2 anos; `v21.0` (out/2024) já está no fim da vida |
| Resposta | `return response.json()` sem checar status | `raise_for_status()` + parsing do erro (`error.code`, `error.error_data.details`) |
| Telefone | String livre no `.env` | Normalizar para E.164 sem `+` (`55` + DDD + número). **Atenção ao nono dígito** de celulares brasileiros — normalizar na entrada e validar o formato |
| Segredo | "variável de ambiente" (correto) | Manter, e **não** logar o token; mascarar em qualquer dump de configuração. O `.env` do projeto já traz aviso explícito de não alteração |
| `httpx` | "adicionar se não estiver" | **Já está** em `requirements.txt` (linha 43), porém sob a seção "Testes". Mover para uma seção de produção e comentar o novo uso |

### 7.8 Arquivos a criar/modificar (caminhos reais)

> **Correção à v1 — nenhum dos três caminhos citados por ela existe.** `app/core/` e `app/panes/`
> estão vazios (só restos de `__pycache__`) e não há `app/config.py`. A estrutura real é
> `app/modules/<modulo>/{models,schemas,service,router}.py`, com infraestrutura em `app/bootstrap/`
> e utilitários em `app/shared/`.

| Arquivo | Ação |
| :--- | :--- |
| `app/modules/notificacoes/models.py` | **[NOVO]** `NotificacaoDestinatario`, `NotificacaoOutbox` |
| `app/modules/notificacoes/schemas.py` | **[NOVO]** Pydantic de destinatário e de payload do webhook |
| `app/modules/notificacoes/service.py` | **[NOVO]** `enfileirar()`, `processar_fila()`, `registrar_status()` |
| `app/modules/notificacoes/router.py` | **[NOVO]** `GET/POST /whatsapp/webhook` + CRUD de destinatários (RBAC: Encarregado) |
| `app/shared/services/whatsapp/client.py` | **[NOVO]** Cliente do provedor (interface + implementação Meta), isolado para permitir troca |
| `app/bootstrap/config/__init__.py` | **[MODIFICAR]** Campos `whatsapp_*` em `Settings` |
| `app/bootstrap/tasks.py` | **[MODIFICAR]** `notificacoes_outbox_task()`, no padrão dos loops existentes |
| `app/bootstrap/events.py` | **[MODIFICAR]** `asyncio.create_task(...)` no `lifespan` + criação/fechamento do `AsyncClient` |
| `app/bootstrap/main.py` | **[MODIFICAR]** `include_router(notificacoes_router, ...)` |
| `app/shared/middleware/csrf.py` | **[MODIFICAR]** Isenção de caminho para o webhook (§7.6.1) |
| `app/modules/panes/service.py` | **[MODIFICAR]** Chamar `enfileirar()` **dentro** da transação, em `criar_pane`/`concluir_pane` |
| `migrations/versions/xxxx_notificacoes.py` | **[NOVO]** Migração Alembic das duas tabelas |
| `.env.example` | **[MODIFICAR]** Documentar as variáveis `WHATSAPP_*` |
| `requirements.txt` | **[MODIFICAR]** Promover `httpx` a dependência de produção |
| `tests/notificacoes/` | **[NOVO]** Testes (§14) |
| `docs/architecture/adr/005-notificacoes-whatsapp.md` | **[NOVO]** Registrar a decisão (o projeto já usa ADRs) |

---

## 8. Configuração

Nomes em `snake_case` na classe `Settings` (pydantic-settings), lidos do `.env` em maiúsculas —
padrão já usado pelo projeto (`case_sensitive=False`).

```env
# --- Notificacoes WhatsApp ---
WHATSAPP_ATIVO=false                     # kill switch: desliga o envio sem redeploy
WHATSAPP_PROVIDER=meta                   # meta | evolution (interface trocavel)
WHATSAPP_GRAPH_VERSION=v23.0             # parametrizada: versoes da Graph API expiram
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=                   # System User token; NUNCA versionar
WHATSAPP_APP_SECRET=                     # valida X-Hub-Signature-256 do webhook
WHATSAPP_WEBHOOK_VERIFY_TOKEN=           # string aleatoria escolhida por voce (handshake GET)
WHATSAPP_TEMPLATE_ALERTA=saa29_alerta_pane
WHATSAPP_TEMPLATE_LANG=pt_BR
WHATSAPP_TIMEOUT_SEGUNDOS=10
WHATSAPP_MAX_TENTATIVAS=5
WHATSAPP_JANELA_SILENCIOSA=22:00-06:00   # eventos nao-AOG aguardam o fim da janela
WHATSAPP_SOMENTE_AOG=true                # fase 1: so o gatilho de alta prioridade
```

Notas:
- **`WHATSAPP_ATIVO`** é o interruptor que permite cortar o envio em incidente sem tocar em código.
- **Sem `WHATSAPP_DESTINATARIOS`** — a lista vive no banco, com consentimento (§7.4).
- **`WHATSAPP_JANELA_SILENCIOSA`**: notificação não-crítica às 3 h da manhã no celular pessoal é o
  caminho mais rápido para o usuário bloquear o número — e bloqueio derruba o quality rating (§3.1).
  Eventos AOG ignoram a janela, por definição.

---

## 9. Templates

### 9.1 Regras da Meta que a v1 violou

| Regra | Situação na v1 |
| :--- | :--- |
| O corpo **não pode começar nem terminar com variável** | ❌ O template `pane_concluida` termina em `📅 Data: {{4}}` → **reprovação na submissão** |
| Duas variáveis não podem ser adjacentes | ✅ ok |
| Variáveis numeradas sequencialmente a partir de `{{1}}` | ✅ ok |
| A quantidade de parâmetros enviados deve bater com a do template | ❌ O template `nova_pane` declara **4** variáveis, e o exemplo em Python envia **2** (`aeronave`, `descricao`) → erro **`132000`** em 100% dos envios |
| Valores de parâmetro **não podem conter quebra de linha, tabulação ou mais de 4 espaços seguidos** | ❌ `descricao` é texto livre digitado pelo usuário; a primeira pane com uma quebra de linha derruba o envio |
| É obrigatório fornecer **exemplos** de valor para cada variável na submissão | ❌ Não mencionado |
| Emoji e `*negrito*` são permitidos no corpo | ✅ ok |

### 9.2 Sanitização de parâmetros (obrigatória)

Todo valor que vier do banco precisa passar por uma normalização antes de virar parâmetro:

```python
import re

_ESPACOS = re.compile(r"\s+")

def sanitizar_param(valor: str | None, limite: int = 700) -> str:
    """Deixa o texto no formato aceito como parametro de template.

    A Meta rejeita parametros com quebra de linha, tabulacao ou mais de 4
    espacos consecutivos (erro 132000). `descricao` de pane e texto livre
    digitado pelo usuario, entao a normalizacao nao e opcional.
    """
    if not valor:
        return "-"                      # parametro vazio tambem e rejeitado
    texto = _ESPACOS.sub(" ", valor).strip()
    return texto[: limite - 1] + "…" if len(texto) > limite else texto
```

> Um parâmetro **vazio** também é recusado — daí o `"-"` como valor de fallback. Isso importa no
> SAA29: `criar_pane()` grava `"AGUARDANDO EDICAO"` quando a descrição vem vazia (RN-05), mas
> `sistema_ata_id` é opcional e pode ser nulo.

### 9.3 Templates propostos

**(A) Recomendado — "alerta sem carga" (§2.1), 1 parâmetro**

Nome: `saa29_alerta_pane` · Categoria: `Utility` · Idioma: `pt_BR`

```
🔧 *SAA29 — Alerta de Manutenção*

Um novo registro de {{1}} requer sua atenção.

Acesse o sistema para ver os detalhes.
```
Exemplo de `{{1}}`: `pane em aeronave` · Botão opcional do tipo *URL* apontando para o SAA29
(o botão não conta como variável de corpo e evita colar link no texto).

**(B) Somente se o conteúdo operacional for autorizado (§2.3), 4 parâmetros**

Nome: `saa29_nova_pane` · Categoria: `Utility` · Idioma: `pt_BR`

```
🔧 *Nova Pane Registrada*

✈️ Aeronave: {{1}}
📋 Sistema/Subsistema: {{2}}
📝 Descrição: {{3}}
📅 Data: {{4}}

Acesse o sistema para mais detalhes.
```
Os quatro parâmetros **devem** ser enviados, todos sanitizados (§9.2). Não termina em variável. ✅

**(C) Conclusão — versão corrigida**

Nome: `saa29_pane_resolvida` · Categoria: `Utility` · Idioma: `pt_BR`

```
✅ *Pane Resolvida*

✈️ Aeronave: {{1}}
📋 Sistema/Subsistema: {{2}}
👤 Concluída por: {{3}}
📅 Data: {{4}}

Acesse o sistema para o histórico completo.
```
A linha final foi acrescentada justamente para o corpo **não terminar em `{{4}}`** — sem ela, o
template da v1 é reprovado. (Também renomeado: no domínio do SAA29 o status é `RESOLVIDA`,
não "concluída" — `StatusPane` só tem `ABERTA` e `RESOLVIDA`.)

### 9.4 Envio — versão corrigida do exemplo da v1

```python
async def enviar_template(
    client: httpx.AsyncClient,      # instancia unica, criada no lifespan
    telefone_e164: str,             # "5521999998888" - so digitos, com DDI
    template: str,
    parametros: list[str],
) -> str:
    """Envia um template e devolve o wamid. Levanta em falha permanente."""
    settings = get_settings()
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_version}"
        f"/{settings.whatsapp_phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefone_e164,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": settings.whatsapp_template_lang},
            "components": [{
                "type": "body",
                # A quantidade tem que bater exatamente com a do template
                # aprovado, senao a Meta responde 132000.
                "parameters": [
                    {"type": "text", "text": sanitizar_param(p)} for p in parametros
                ],
            }],
        },
    }
    resposta = await client.post(
        url,
        headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
        json=payload,
        timeout=settings.whatsapp_timeout_segundos,
    )
    resposta.raise_for_status()      # a v1 devolvia .json() sem checar o status
    return resposta.json()["messages"][0]["id"]   # wamid, para casar com o webhook
```

---

## 10. Pré-requisitos na Meta (corrigidos e ampliados)

### Etapa 1 — Conta e número
1. Conta no **Meta Business Suite** e App do tipo *Business* no Meta for Developers, com o produto
   **WhatsApp** ativado.
2. **Business Verification** (verificação do negócio): envio de documentos da organização.
   **Este é o item de prazo mais longo do projeto** — pode levar dias — e a v1 não o menciona.
   Sem ele, o número fica preso no limite inicial de **250 destinatários únicos/24 h**.
3. **Número de telefone dedicado**, com três restrições que a v1 omite:
   - **não pode estar em uso** no aplicativo WhatsApp ou WhatsApp Business — é preciso excluir a
     conta lá antes de migrar, o que **apaga o histórico daquele número**;
   - precisa receber SMS ou chamada para verificação;
   - depois de verificado, precisa ser **registrado via API com um PIN de verificação em duas
     etapas** (`POST /{phone_number_id}/register`) — passo silencioso e causa comum de
     "por que nada envia".
4. **System User Token** no Business Manager, com as permissões `whatsapp_business_messaging` e
   `whatsapp_business_management`, e o ativo (WABA) atribuído ao System User. Configurar validade
   "nunca expira"; o token temporário do painel **expira em 24 h** e serve só para experimentar.

### Etapa 2 — Templates
5. Submeter os templates (§9.3) com **valores de exemplo** para cada variável. Aprovação costuma
   sair em minutos, mas pode levar até 24 h. Reprovação mais comum: corpo terminando em variável e
   categoria incompatível com o texto.

### Etapa 3 — Webhook (necessário já na Fase 1, para status de entrega)
6. Domínio com **HTTPS válido** apontando para o VPS, host incluído em `ALLOWED_HOSTS`.
7. Cadastrar a URL do webhook e o *verify token*; assinar o campo `messages`.
8. Guardar o **App Secret** para validar `X-Hub-Signature-256`.

### Etapa 4 — Testes
9. A Meta fornece um **número de teste** gratuito, com uma limitação relevante: ele só envia para
   **até 5 números de destino previamente cadastrados** no painel. Suficiente para homologar, e não
   substitui um teste com o número real antes de liberar para a equipe.
10. Em desenvolvimento local, expor o webhook por túnel (`cloudflared`, `ngrok`) — a Meta não
    entrega em `localhost`.

---

## 11. Observabilidade e runbook

### 11.1 O que monitorar
| Métrica | Por quê |
| :--- | :--- |
| Fila `PENDENTE` acima de N ou parada | Worker morto ou provedor fora do ar |
| Taxa de `FALHOU` | Token expirado, template pausado, números inválidos |
| Eventos **AOG** sem confirmação de entrega | O alerta crítico não chegou — exige ação humana |
| **Quality rating** e *messaging limit* no WhatsApp Manager | Degradação antecede restrição do número |
| Custo mensal x orçado | Detecta recategorização de template (§4.4) |

### 11.2 Erros comuns da Cloud API

| Código | Significado | Ação |
| :---: | :--- | :--- |
| `132000` | Nº de parâmetros diferente do template | **Bug** — não retentar; corrigir código/template |
| `132001` | Template não existe no par nome+idioma | Conferir nome e `pt_BR`; não retentar |
| `131047` | Fora da janela de 24 h (texto livre) | Enviar template |
| `131026` | Mensagem não entregável (número sem WhatsApp) | Marcar destinatário como inválido |
| `133010` | Número não registrado (falta o PIN da Etapa 1.3) | Registrar o número |
| `368` / `131031` | Conta restringida/banida por política | **Incidente** — parar envios, revisar conteúdo e opt-in |
| `4` / `80007` | Rate limit atingido | Backoff |

### 11.3 Logs
Log estruturado por envio: `evento`, `outbox_id`, `destinatario_id`, `wamid`, `tentativa`,
`status`, `codigo_erro`. **Nunca** logar o `ACCESS_TOKEN` nem o corpo completo da mensagem quando
ela contiver dados operacionais (§2).

---

## 12. Plano de execução e esforço

> **Correção à v1:** a estimativa de "~4–5 horas" cobre apenas escrever uma função de `POST` e
> chamá-la. Não inclui fila, retentativa, idempotência, webhook, tabelas, opt-in, testes, isenção
> de CSRF, deploy ou os prazos externos da Meta.

| Fase | Entrega | Esforço dev | Espera externa |
| :--- | :--- | :---: | :---: |
| **0. Decisão** | Autorização de conteúdo (§2.3) + escolha lista×grupo | — | dias |
| **1. Conta Meta** | App, número, verificação, token, registro por PIN | 2–3 h | **1–10 dias** (verificação) |
| **2. Templates** | Submissão e aprovação | 1 h | minutos–24 h |
| **3. Infra de fila** | Migração, modelos, `enfileirar()`, worker, claim atômico | 8–10 h | — |
| **4. Cliente Meta** | `whatsapp/client.py`, sanitização, retentativa, erros | 4–5 h | — |
| **5. Webhook** | Endpoint, assinatura, isenção CSRF, HTTPS/domínio | 5–7 h | — |
| **6. Destinatários** | CRUD + opt-in/opt-out + tela de configurações | 4–6 h | — |
| **7. Testes** | Unitários + integração com provedor falso (§14) | 4–5 h | — |
| **8. Deploy e piloto** | Piloto com 2–3 pessoas por 1 semana antes de abrir | 1–2 h | 1 semana |
| | **Total** | **~24–34 h** | **~2–15 dias** |

A **Fase 2 (bot de consulta / Pull)** acrescenta ~10–14 h sobre essa base, aproveitando o webhook.

---

## 13. Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
| :--- | :---: | :---: | :--- |
| Dado operacional exposto em aparelho pessoal | Média | **Alto** | "Alerta sem carga" (§2.1); autorização formal (§2.3) |
| Verificação de negócio negada/demorada | Média | Médio | Iniciar a Fase 1 **antes** do desenvolvimento; documentação da OM em ordem |
| Template recategorizado → custo 8× | Baixa | Médio | Texto estritamente transacional; monitorar categoria e custo (§4.4) |
| Número restringido por denúncias | Baixa | Alto | Opt-in real, janela silenciosa, volume baixo, opt-out fácil |
| Alerta AOG não entregue e ninguém percebe | Média | **Alto** | Webhook de `statuses` + alarme para AOG sem `ENTREGUE` (§11.1) |
| Envio duplicado (2 workers Gunicorn) | **Alta se ignorado** | Médio | Claim atômico + `dedupe_key` único (§7.3) |
| Notificação de pane revertida por rollback | **Alta se ignorado** | Médio | Outbox transacional (§7.2) |
| Token vazado em log/commit | Baixa | **Alto** | Só em `.env`, mascarar em logs, rotacionar ao suspeitar |
| Webhook aberto sem validar assinatura | **Alta se ignorado** | Alto | HMAC-SHA256 sobre o corpo bruto, `compare_digest` (§7.6.2) |
| Dependência de plataforma de terceiro para alerta crítico | Média | Médio | WhatsApp é canal **redundante**; o SAA29 continua sendo a fonte de verdade |

---

## 14. Critérios de aceite

**Funcionais**
1. Pane que torna a aeronave INDISPONÍVEL gera uma linha no outbox por destinatário ativo assinante.
2. Mensagem entregue em até 2 min do commit, em condições normais.
3. Falha da Meta **não** impede a criação da pane; a requisição HTTP do usuário não espera a rede externa.
4. Rollback da transação **não** gera notificação.
5. Reinício do servidor no meio do envio não duplica nem perde mensagem.
6. `SAIR` no WhatsApp desativa o destinatário e para os envios.
7. Webhook atualiza o status para `ENTREGUE`.

**Testes automatizados** (com provedor falso — nenhum teste deve chamar a Meta de verdade)
- `enfileirar()` grava na mesma transação; rollback não deixa resíduo no outbox.
- Claim atômico: duas execuções concorrentes do worker enviam a mensagem **uma** vez.
- `sanitizar_param`: quebra de linha, tabulação, espaços múltiplos, string vazia, texto > 700 chars.
- Retentativa: `429` agenda nova tentativa; `132000` marca `FALHOU` sem retentar.
- Webhook: assinatura inválida → `403`; válida → `200` e atualização de status; evento repetido é idempotente.
- `WHATSAPP_ATIVO=false` → nada é enviado, mas o outbox continua registrando.

---

## Anexo A — Correções aplicadas em relação à v1

### A.1 Erros factuais sobre a plataforma

| # | O que a v1 afirmava | Correção | Gravidade |
| :---: | :--- | :--- | :---: |
| 1 | "Cobrado por **conversa** iniciada" | Desde **01/07/2025** a cobrança é **por mensagem** (§4.1) | **Alta** |
| 2 | "Grátis as primeiras **1.000** conversas de serviço/mês" | Pacote extinto em **01/11/2024**; mensagens de serviço são gratuitas e **ilimitadas** (§4.1) | **Alta** |
| 3 | "Risco de banimento: **Nenhum** (canal oficial)" | Existe quality rating, pausa de template e restrição de número (§3.1) | **Alta** |
| 4 | Evolution/WAHA: risco "moderado" | **Alto** — reimplementam o protocolo do WhatsApp Web, contra os Termos (§3.2) | Média |
| 5 | WAHA: "gratuito" | **Core** gratuito com limitações; **Plus é pago** (§3.3) | Média |
| 6 | "250 destinatários/dia, escala automaticamente" | Só escala **após a Business Verification** (§10, Etapa 1.2) | Média |
| 7 | Pull é grátis "dentro das 1.000 conversas" | É grátis porque **mensagem de serviço é gratuita**; não há teto de 1.000 (§5.3) | Média |
| 8 | Custo do cenário SAA29: ~R$ 5/mês | Piso absoluto (1 destinatário, metade dos eventos). Real: R$ 10–65 (§4.3) | **Alta** |
| 9 | Estimativa total: 4–5 h | ~24–34 h + 2–15 dias de espera externa (§12) | Média |

### A.2 Erros que quebrariam a implementação

| # | Problema | Correção | Gravidade |
| :---: | :--- | :--- | :---: |
| 10 | Notificação chamada de dentro de `criar_pane()` — **antes do commit**, que ocorre em `get_db` | Outbox transacional + worker (§7.1–7.2) | **Crítica** |
| 11 | Exemplo envia **2** parâmetros para um template de **4** | Erro `132000` garantido; parâmetros devem casar (§9.1) | **Crítica** |
| 12 | Template `pane_concluida` **termina em variável** | Reprovado pela Meta; corrigido em §9.3-C | **Alta** |
| 13 | `descricao` (texto livre) usada como parâmetro sem sanitizar | Quebra de linha/tab/espaços derrubam o envio; `sanitizar_param()` (§9.2) | **Alta** |
| 14 | Webhook sem validação de `X-Hub-Signature-256` nem handshake `GET` | Endpoint público injetável; validação obrigatória (§7.6.2) | **Alta** |
| 15 | Não previa que o **CSRF middleware global** do SAA29 barraria o POST da Meta | Isenção explícita de caminho (§7.6.1) | **Alta** |
| 16 | Não previa os **2 workers Gunicorn** → envio duplicado | Claim atômico + `dedupe_key` (§7.3) | **Alta** |
| 17 | `httpx.AsyncClient()` novo a cada envio | Cliente único no `lifespan` (§7.7) | Baixa |
| 18 | `v21.0` fixa no código | Parametrizar — versões da Graph API expiram (§7.7) | Baixa |
| 19 | `return response.json()` sem checar status | `raise_for_status()` + mapeamento de erro (§7.7) | Média |
| 20 | "Falha silenciosa com `try/except`" como única estratégia | Retentativa com backoff, classificação de erro e alarme para AOG (§7.5) | Média |

### A.3 Erros de aderência ao SAA29 e omissões

| # | Problema | Correção | Gravidade |
| :---: | :--- | :--- | :---: |
| 21 | Caminhos inexistentes: `app/core/whatsapp.py`, `app/config.py`, `app/panes/service.py` | Estrutura real em §7.8 (`app/modules/`, `app/bootstrap/`, `app/shared/`) | Média |
| 22 | Gatilho "AOG/alta prioridade" — `Pane` **não tem** campo de prioridade | Critério derivado da transição para `INDISPONIVEL` (§1.2) | Média |
| 23 | `WHATSAPP_DESTINATARIOS` no `.env` | Tabela com opt-in/opt-out; `Usuario` sequer tem campo de telefone (§7.4) | Média |
| 24 | Objetivo pede "**grupo**", recomendação é a Cloud API — que **não envia para grupos** | Contradição resolvida: lista individual (§3.5) | Média |
| 25 | Nenhuma menção a **sigilo operacional** ou **LGPD** | §2 inteira — é o bloqueio atual do módulo | **Crítica** |

### A.4 Ajustes editoriais
- Numeração corrigida (a v1 tinha **duas seções "5"** — *Recomendação* e *Arquitetura*).
- "NOTA MENTAL: pesquisar Baileys" **respondida** e incorporada como §3.4.
- `httpx` — a v1 dizia "adicionar se ainda não estiver"; ele **já está** em `requirements.txt:43`,
  sob a seção "Testes", e só precisa ser promovido a dependência de produção.
- Terminologia alinhada ao domínio: `RESOLVIDA` em vez de "concluída" (§9.3-C).

---

## Anexo B — Decisões pendentes

| # | Pergunta | Responsável | Impacto |
| :---: | :--- | :--- | :--- |
| B1 | O conteúdo operacional (matrícula, ATA, descrição) pode trafegar por WhatsApp? | Seção/Comando | Define o template (§9.3-A ou B) e libera o módulo |
| B2 | Lista individual (oficial) ou grupo (não oficial, com risco de ban)? | Bruno + seção | Define provedor: Meta × Evolution/WAHA |
| B3 | Existe número institucional disponível e **fora do app WhatsApp**? | Administração | Bloqueia a Etapa 1 (§10) |
| B4 | Há domínio com HTTPS válido no VPS para o webhook? | Bruno | Bloqueia §7.6 |
| B5 | Web Push no PWA (§3.6) resolve o caso de uso com custo e risco menores? | Bruno | Pode reduzir o WhatsApp a canal de exceção — ou tornar o módulo desnecessário |
| B6 | Notificar só AOG ou toda pane? | Encarregado | Diferença de ~R$ 10 para ~R$ 63/mês (§4.3) |

---

*v2 — 20 de agosto de 2026. Revisão técnica da v1 (17/04/2026), com verificação cruzada contra o*
*código real do SAA29 (`app/modules/panes/`, `app/bootstrap/`, `app/shared/middleware/csrf.py`,*
*`gunicorn_conf.py`). Preços, limites e regras da plataforma Meta devem ser reconferidos na*
*documentação oficial no momento da implementação — mudam com frequência.*
