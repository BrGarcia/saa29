# Estudo de Viabilidade: Notificação via WhatsApp

Este documento analisa as opções de integração do SAA29 com o WhatsApp para envio de notificações automáticas quando um registro (pane, usuário, etc.) é criado no sistema.

---

## 1. Objetivo

Enviar uma mensagem automática via WhatsApp para um grupo ou lista de responsáveis sempre que:
- Uma nova pane for registrada.
- Uma pane for concluída.
- (Opcional) Um usuário for criado ou desativado.

---

## 2. Opções de Integração

Existem **três caminhos** viáveis, cada um com trade-offs distintos:

### Opção A: WhatsApp Cloud API (Oficial da Meta)

| Aspecto | Detalhe |
| :--- | :--- |
| **Provedor** | Meta (Facebook) |
| **Tipo** | API oficial, hospedada pela Meta |
| **Estabilidade** | ✅ Alta — mantida pela própria Meta |
| **Custo** | 💲 Cobrado por mensagem template entregue |
| **Risco de banimento** | ✅ Nenhum (canal oficial) |
| **Requisitos** | Conta Meta Business verificada + número de telefone dedicado |
| **Complexidade** | Média |

#### Como funciona
1. Você cria um **App** no [Meta for Developers](https://developers.facebook.com/).
2. Cadastra um **número de telefone** para envio (não pode ser o pessoal).
3. Cria **templates de mensagem** pré-aprovados pela Meta (ex: "Nova pane registrada: {{aeronave}} - {{descricao}}").
4. O backend do SAA29 faz um `POST` para a Graph API da Meta com o template preenchido.

#### Custos estimados (Brasil)
- **Mensagens Utility (Notificações proativas):** ~US$ 0.0080 por conversa iniciada pelo sistema (sempre cobradas).
- **Mensagens Service (Atendimento/Pull):** Grátis (as primeiras 1.000 do mês), desde que o usuário inicie a conversa.
- **Cenário SAA29 (Push - 4 panes/dia):** ~US$ 0,96/mês (~R$ 5,00/mês).
- **Cenário SAA29 (Pull - Mecânico consulta bot):** **R$ 0,00/mês** (Custo zero dentro das 1.000 conversas).

#### Exemplo de payload
```python
import httpx

async def enviar_whatsapp_meta(telefone: str, aeronave: str, descricao: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,  # Ex: "5521999998888"
        "type": "template",
        "template": {
            "name": "nova_pane",
            "language": {"code": "pt_BR"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": aeronave},
                    {"type": "text", "text": descricao},
                ]
            }]
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()
```

#### Variáveis de ambiente necessárias
```env
WHATSAPP_PROVIDER=meta
WHATSAPP_PHONE_NUMBER_ID=123456789
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx
WHATSAPP_TEMPLATE_NOVA_PANE=nova_pane
WHATSAPP_DESTINATARIOS=5521999998888,5521999997777
```

---

### Opção B: Evolution API (Self-Hosted, Gratuito)

| Aspecto | Detalhe |
| :--- | :--- |
| **Provedor** | Open-source (GitHub) |
| **Tipo** | Auto-hospedado via Docker |
| **Estabilidade** | ⚠️ Média — depende de updates do WhatsApp Web |
| **Custo** | ✅ Gratuito (apenas custo do servidor) |
| **Risco de banimento** | ⚠️ Moderado — usa emulação do WhatsApp Web |
| **Requisitos** | Servidor com Docker + número WhatsApp regular |
| **Complexidade** | Alta (requer manter infraestrutura) |

#### Como funciona
1. Deploy de um container Docker com a Evolution API.
2. Escaneia QR Code para vincular um número WhatsApp existente.
3. O SAA29 faz `POST` para o endpoint local da Evolution API.
4. A mensagem é enviada como se fosse do WhatsApp Web.

#### Exemplo de payload
```python
import httpx

async def enviar_whatsapp_evolution(telefone: str, mensagem: str):
    url = f"http://localhost:8080/message/sendText/{INSTANCE_NAME}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": telefone,  # Ex: "5521999998888"
        "text": mensagem
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.json()
```

#### Variáveis de ambiente necessárias
```env
WHATSAPP_PROVIDER=evolution
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=sua_api_key
EVOLUTION_INSTANCE_NAME=saa29
WHATSAPP_DESTINATARIOS=5521999998888,5521999997777
```

#### Riscos
- **Banimento:** O WhatsApp pode bloquear o número se detectar uso automatizado.
- **Instabilidade:** Atualizações do WhatsApp Web podem quebrar a conexão temporariamente.
- **Manutenção:** Requer manter o container sempre rodando e monitorar reconexões.

---

### Opção C: WAHA (WhatsApp HTTP API)

| Aspecto | Detalhe |
| :--- | :--- |
| **Provedor** | Open-source (GitHub) |
| **Tipo** | Auto-hospedado via Docker |
| **Estabilidade** | ⚠️ Média — similar à Evolution API |
| **Custo** | ✅ Gratuito (apenas custo do servidor) |
| **Risco de banimento** | ⚠️ Moderado |
| **Requisitos** | Servidor com Docker + número WhatsApp regular |
| **Complexidade** | Média-Alta |

Funciona de forma muito similar à Evolution API, porém com uma API mais simples e focada apenas em envio/recebimento de mensagens.

---

## 3. Comparativo Resumido

| Critério | Meta Cloud API | Evolution API | WAHA |
| :--- | :---: | :---: | :---: |
| **Custo mensal (SAA29)** | ~R$ 5 | R$ 0 (+ servidor) | R$ 0 (+ servidor) |
| **Estabilidade** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Risco de ban** | Nenhum | Moderado | Moderado |
| **Setup inicial** | Médio | Alto | Médio-Alto |
| **Manutenção** | Zero | Constante | Constante |
| **Envia para grupos** | ❌ (só individual) | ✅ | ✅ |
| **Mensagem livre** | ❌ (precisa template) | ✅ | ✅ |
| Infra adicional | Nenhuma | Docker + VPS | Docker + VPS |

---

## 4. Modelos de Interação: Push vs Pull

Para a **Opção A (Meta Cloud API)**, podemos adotar duas estratégias principais:

### Estratégia "Push" (Notificação Ativa)
O sistema detecta uma nova pane e envia a mensagem imediatamente para uma lista de contatos.
*   **Vantagem:** Rapidez e proatividade (ideal para panes AOG/Críticas).
*   **Custo:** Pago por conversa (~R$ 0,04 por evento).
*   **Complexidade:** Baixa (HTTP POST de template).

### Estratégia "Pull" (Bot de Consulta)
O usuário (mecânico/piloto) envia uma mensagem para o bot (ex: "Oi" ou "/minhaspanes") para obter informações.
*   **Vantagem:** **Gratuito** (nas primeiras 1.000 conversas/mês). Flexibilidade de conteúdo (texto livre).
*   **Custo:** R$ 0,00.
*   **Complexidade:** Média (requer Webhook para processar mensagens recebidas).

---

## 5. Recomendação para o SAA29

### 🏆 Recomendação: **Abordagem Híbrida (Meta Cloud API)**

**Justificativa:** Unir o melhor dos dois mundos para garantir confiabilidade com custo quase zero.

1.  **Alertas Críticos (Push):** Ativar notificações automáticas apenas para panes de alta prioridade ou "AOG".
2.  **Consulta de Status (Pull):** Implementar um bot de comando para consultas gerais (gratuito).
3.  **Confiabilidade:** A API oficial da Meta garante que as mensagens críticas não sejam bloqueadas.

### Alternativa viável: **Evolution API (Opção B)**
Indicada apenas se:
- Não for possível criar uma conta Meta Business.
- O uso for estritamente interno e de baixo volume.
- Já houver um servidor VPS disponível para hospedar o container Docker.

---

## 5. Arquitetura proposta (Meta Cloud API)

```
┌──────────────────────────────────────────────────────┐
│                     SAA29 Backend                    │
│                                                      │
│  criar_pane() ──► commit DB ──► enviar_notificacao() │
│                                        │             │
│                                        ▼             │
│                              WhatsAppService         │
│                              (app/core/whatsapp.py)  │
│                                        │             │
└────────────────────────────────────────│─────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Meta Graph API      │
                              │  POST /messages      │
                              │  (template: nova_pane)│
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │     WhatsApp         │
                              │  Destinatários       │
                              │  (lista configurável)│
                              └─────────────────────┘
```

### Arquivos a criar/modificar

| Arquivo | Ação |
| :--- | :--- |
| `app/core/whatsapp.py` | **[NOVO]** Serviço de envio de notificações WhatsApp |
| `app/config.py` | **[MODIFICAR]** Adicionar variáveis `WHATSAPP_*` |
| `app/panes/service.py` | **[MODIFICAR]** Chamar `enviar_notificacao()` após `criar_pane()` e `concluir_pane()` |
| `.env.example` | **[MODIFICAR]** Documentar as variáveis WhatsApp |
| `requirements.txt` | **[MODIFICAR]** Adicionar `httpx` (se ainda não estiver) |

---

## 6. Pré-requisitos para Implementação

### Etapa 1: Configuração na Meta (Manual)
1. Criar conta no [Meta Business Suite](https://business.facebook.com/).
2. Criar um App do tipo "Business" no [Meta for Developers](https://developers.facebook.com/).
3. Ativar o produto "WhatsApp" no App.
4. Cadastrar e verificar um **número de telefone** para envio.
5. Criar e submeter para aprovação o **template de mensagem**:
   - Nome: `nova_pane`
   - Categoria: `Utility`
   - Idioma: `pt_BR`
   - Corpo: `🔧 *Nova Pane Registrada*\n\n✈️ Aeronave: {{1}}\n📋 Sistema: {{2}}\n📝 Descrição: {{3}}\n📅 Data: {{4}}`
6. Gerar um **Access Token permanente** (System User Token).

### Etapa 2: Implementação no SAA29 (Código)
1. Criar `app/core/whatsapp.py` com a classe `WhatsAppService`.
2. Adicionar variáveis ao `app/config.py`.
3. Integrar no fluxo de `criar_pane()` e `concluir_pane()`.
4. O envio deve ser **assíncrono e não-bloqueante** — uma falha no WhatsApp não deve impedir a criação da pane.

### Etapa 3: Teste
1. A Meta oferece um **número de teste** e um **token temporário** para desenvolvimento.
2. Validar envio para o número de teste antes de ativar em produção.

---

## 7. Exemplo de Template para Aprovação

### Template: `nova_pane`
```
🔧 *Nova Pane Registrada*

✈️ Aeronave: {{1}}
📋 Sistema/Subsistema: {{2}}
📝 Descrição: {{3}}
📅 Data: {{4}}

Acesse o sistema para mais detalhes.
```

### Template: `pane_concluida`
```
✅ *Pane Concluída*

✈️ Aeronave: {{1}}
📋 Sistema/Subsistema: {{2}}
👤 Concluída por: {{3}}
📅 Data: {{4}}
```

---

## 8. Estimativa de Esforço

| Etapa | Tempo estimado |
| :--- | :--- |
| Setup Meta Business + App | 1–2 horas |
| Aprovação do template | 1–24 horas (automático pela Meta) |
| Implementação `whatsapp.py` | 1 hora |
| Integração no `panes/service.py` | 30 minutos |
| Testes locais + deploy | 1 hora |
| **Total** | **~4–5 horas** |

---

## 9. Considerações de Segurança

- **Access Token:** Deve ser armazenado como variável de ambiente, nunca no código.
- **Rate Limiting:** A Meta impõe limites de envio (inicialmente 250 destinatários únicos/dia, escala automaticamente).
- **Opt-in:** Os destinatários devem ter concordado em receber mensagens (requisito da Meta).
- **Falha silenciosa:** O sistema deve **continuar funcionando** mesmo que o WhatsApp esteja indisponível. O envio da notificação deve ser tratado como uma operação secundária com `try/except`.

---

*Documento criado em 17 de abril de 2026 como estudo de viabilidade para integração WhatsApp no SAA29.*
