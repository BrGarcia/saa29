# Histórico de Bugs e Correções Críticas

Este documento sumariza os problemas técnicos resolvidos recentemente para estabilização do SAA29.

---

### 1. Violação de CSP (Content Security Policy)
- **Sintoma:** Botões e modais não funcionavam; erro "Refused to execute script" no console.
- **Causa:** Uso de atributos `onclick="..."` no HTML, bloqueados pela política de segurança XSS.
- **Solução:** Migração de handlers inline para `addEventListener` em arquivos `.js` externos.
- **Status:** ✅ CORRIGIDO

### 2. Bloqueio de Método PATCH (Erro 405)
- **Sintoma:** Erro `405 Method Not Allowed` ao editar Part Numbers ou executar manutenções.
- **Causa:** O verbo `PATCH` não estava na lista de métodos permitidos do `CORSMiddleware`.
- **Solução:** Inclusão de `"PATCH"` nas configurações globais em `app/bootstrap/main.py`.
- **Status:** ✅ CORRIGIDO

### 3. Conflito na Inativação (Erro 409)
- **Sintoma:** Erro de conflito ao tentar mudar status da aeronave para "INATIVA" via Configurações.
- **Causa:** Restrição no `service.py` que exigia endpoint exclusivo para desativação.
- **Solução:** Ajuste no `app/modules/aeronaves/service.py` para permitir a transição via `PUT` genérico.
- **Status:** ✅ CORRIGIDO

### 4. Erro 500 na Exclusão de PN
- **Sintoma:** Erro "Internal Server Error" ao tentar excluir um Part Number do catálogo.
- **Causa:** Uso de `scalar_one_or_none()` em query que retornava múltiplos itens vinculados.
- **Solução:** Substituição por `.first()` no `app/modules/equipamentos/service.py`.
- **Status:** ✅ CORRIGIDO

### 5. Pane Excluída Não Abre na Tela de Detalhes
- **Sintoma:** Ao abrir `/panes/{id}/detalhes` de uma pane excluída, a página carregava o template mas a API retornava `404 Pane não encontrada`, impedindo a visualização.
- **Causa:** O frontend consultava `GET /panes/{id}`, porém o backend filtrava panes inativas por padrão (`Pane.ativo == True`), tratando uma pane excluída como inexistente no detalhamento.
- **Solução:** O endpoint de detalhe passou a buscar a pane com inclusão de inativas, o download de anexos ficou consistente com essa regra, e a tela de detalhe passou a renderizar panes excluídas em modo somente leitura, bloqueando edição, conclusão, comentários, delegação e upload/exclusão de anexos.
- **Status:** ✅ CORRIGIDO

### 6. Erro 404 ao Atualizar Tarefa de Inspeção
- **Sintoma:** Ao tentar salvar a execução de uma tarefa de inspeção, a interface falhava silenciosamente e o console indicava `404 Not Found` para a rota `tarefas/ID`.
- **Causa:** O frontend (`inspecao_detalhe.js`) chamava a URL `/inspecoes/{inspecao_id}/tarefas/{tarefa_id}` usando o método `PATCH`, enquanto o backend esperava `/inspecoes/tarefas/{tarefa_id}` via `PUT`.
- **Solução:** O JS foi corrigido para realizar a requisição HTTP `PUT` no endpoint exato correspondente ao roteador da API.
- **Status:** ✅ CORRIGIDO

### 7. Falha de Auditoria em Tarefas "N/A"
- **Sintoma:** Ao mudar o status de uma tarefa de inspeção para "N/A", a coluna de atualização não exibia a data, hora ou o trigrama de quem tomou a decisão.
- **Causa:** O backend (`service.py`) limpava deliberadamente o campo de executor e data de execução quando o status recebido era "N/A" ou "PENDENTE".
- **Solução:** O status `N/A` foi agrupado junto ao status `CONCLUIDA` na lógica de negócio, exigindo um executor válido e registrando o timestamp exato do momento da alteração para garantir rastreabilidade.
- **Status:** ✅ CORRIGIDO

---
*Última atualização: 2026-04-30*
