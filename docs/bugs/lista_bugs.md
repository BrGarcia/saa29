# Lista de Bugs Ativos e Histórico de Correções

Este documento rastreia os problemas técnicos identificados no SAA29 e o status de suas resoluções.

---

## BUG 01: Violação de Content Security Policy (CSP)
*   **Descrição:** A Política de Segurança de Conteúdo bloqueava a execução de scripts e handlers de eventos inline (`onclick`, `onmouseover`, etc.), impedindo o funcionamento de modais e interações no frontend.
*   **Localização Original:** Identificado inicialmente em `configuracoes.html`, mas presente em diversos arquivos JS que utilizavam atribuição direta de eventos (ex: `btn.onclick = ...`).
*   **Impacto:** Quebra de funcionalidade na interface (botões que não respondem).
*   **Solução Implementada:** 
    *   Remoção de todos os atributos `on*` dos templates HTML.
    *   Substituição de todas as atribuições diretas de eventos em JavaScript por `addEventListener`.
    *   Ajuste na lógica de criação dinâmica de elementos para garantir conformidade estrita com `script-src 'self'`.
*   **Status:** ✅ CORRIGIDO (2026-04-28)

---

## BUG 02: Erro 409 Conflict ao Inativar Aeronave
*   **Descrição:** Ao tentar alterar o status de uma aeronave para **INATIVA** via painel de configurações, o backend retornava um erro de conflito, exigindo o uso de um endpoint específico de desativação.
*   **Impacto:** Usuários (Encarregados) não conseguiam desativar aeronaves pela interface principal de administração.
*   **Causa Raiz:** Trava de segurança no `service.py` do módulo de aeronaves que bloqueava a transição para `INATIVA` dentro da função genérica de `atualizar_aeronave`.
*   **Solução Implementada:** 
    *   Remoção da restrição no `app/modules/aeronaves/service.py`, permitindo que o status seja alterado para qualquer valor válido do enum `StatusAeronave` através do método `PUT`, desde que o usuário possua as permissões de Encarregado ou Administrador.
*   **Status:** ✅ CORRIGIDO (2026-04-28)

---

## Histórico de Correções de Segurança (Audit)
*   Para detalhes sobre as 22 correções de segurança (C-01 a L-06), consulte `docs/relatorio/revisao_claude_v3.md` e a atualização no `docs/CHANGELOG.md`.
