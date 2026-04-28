# Relatório de Bug: Inativar Aeronave via Configurações

## Descrição do Problema
Ao tentar alterar o status de uma aeronave para **INATIVA** através da página de Configurações, o sistema retorna um erro de conflito (HTTP 409) com a mensagem:
> “Use a ação de desativar para tornar a aeronave inativa.”

Além disso, o console do navegador registra uma violação de **Content Security Policy (CSP)** devido ao uso de handlers de eventos inline (`onclick`) no HTML.

---

## Análise Técnica

### 1. Motivo do Erro 409 (Conflict)
O erro ocorre na camada de serviço do módulo de aeronaves (`app/modules/aeronaves/service.py`). 

A função `atualizar_aeronave` possui uma trava de segurança explícita para evitar que o status **INATIVA** seja definido via uma atualização comum (PUT). O objetivo dessa trava é forçar o uso de endpoints específicos (`desativar_aeronave` e `reativar_aeronave`) que podem conter lógicas de negócio adicionais no futuro.

**Trecho do código causador (`app/modules/aeronaves/service.py`):**
```python
if "status" in changes:
    novo_status = changes["status"]
    if aeronave.status == StatusAeronave.INATIVA:
        raise ValueError("Aeronave inativa só pode ser reativada pela ação de reativar.")
    if novo_status == StatusAeronave.INATIVA:
        raise ValueError("Use a ação de desativar para tornar a aeronave inativa.") # <--- Erro aqui
```

No frontend (`app/web/static/js/configuracoes.js`), a função `alterarStatusAeronave` tenta realizar um `PUT` para `/aeronaves/{id}` enviando `{ "status": "INATIVA" }`, o que aciona a trava acima.

### 2. Motivo da Violação de CSP
O arquivo `app/bootstrap/main.py` define uma política de segurança rigorosa que proíbe a execução de scripts inline:
`script-src 'self';`

No entanto, o template `app/web/templates/configuracoes.html` utiliza atributos `onclick="..."` em diversos botões (ex: `onclick="closeModalStatus()"`). O navegador bloqueia essas ações por segurança, impedindo o fechamento de modais e outras interações rápidas que dependem desses atributos.

---

## Sugestão de Correção

### Para o Bug do Status (409 Conflict)
Existem duas abordagens possíveis, sendo a primeira a mais recomendada para manter a consistência da arquitetura:

1.  **Ajuste no Frontend (Recomendado):**
    *   Modificar a função `alterarStatusAeronave` no JS para detectar se o novo status é `INATIVA`.
    *   Se for `INATIVA`, disparar uma chamada para um novo endpoint (ou existente) de desativação, em vez do `PUT` genérico. 
    *   *Nota:* Atualmente o router possui `POST /{id}/toggle-status`, mas não possui um `POST /{id}/desativar` e `POST /{id}/reativar` expostos de forma direta que aceite o status selecionado. Seria ideal criar esses endpoints ou ajustar o `PUT` para permitir a transição se originada de um usuário autorizado.

2.  **Ajuste no Backend:**
    *   Remover a trava no `service.py` ou permitir que `atualizar_aeronave` aceite o status `INATIVA` se o usuário tiver as permissões necessárias (Encarregado/Admin), centralizando a lógica de validação de transição de estado em um único lugar.

### Para a Violação de CSP
1.  **Remover Handlers Inline:** 
    *   No arquivo `configuracoes.html`, remover todos os atributos `onclick`.
    *   No arquivo `configuracoes.js`, adicionar listeners de eventos via JavaScript para esses botões (ex: `document.getElementById('btn-close-modal').addEventListener('click', closeModalStatus)`).
2.  **Alternativa (Menos Segura):** 
    *   Adicionar `'unsafe-inline'` ao `script-src` na configuração da CSP no `main.py`. **Não recomendado** pois enfraquece a segurança do sistema contra ataques XSS.

---
**Relatório gerado em:** 2026-04-28
**Status:** Aguardando Instruções de Implementação.