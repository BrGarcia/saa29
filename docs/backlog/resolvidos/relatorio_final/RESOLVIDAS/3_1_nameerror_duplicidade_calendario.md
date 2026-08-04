# Backlog Item 3.1: NameError em Runtime devido a código duplicado no Calendário

## 1. Descrição do Problema
O arquivo `app/modules/calendario/service.py` continha duplicidade de código com versões antigas das funções de serviço na metade inferior, as quais referenciavam variáveis globais inexistentes (como `PRIVILEGED_ROLES` e `ADMIN_ROLES`), ocasionando erros de importação (`NameError`) e riscos de sobrescrever as correções de segurança.

## 2. Plano de Implementação
1. **Remoção física do código obsoleto:** Identificar a linha divisória (ex: após a linha 327) onde a replicação de código inicia.
2. **Expurgo total:** Deletar integralmente a metade inferior de `app/modules/calendario/service.py` correspondente ao trecho duplicado.
3. **Validação de referências:** Certificar-se de que a metade superior importa e usa corretamente os papéis de RBAC canônicos importados de `app.modules.auth.roles`.
4. **Verificação de Importação:** Rodar interpretador python importando o módulo para garantir que nenhum `NameError` ou `AttributeError` ocorra.

## 3. Critérios de Aceitação
* O arquivo `app/modules/calendario/service.py` não contém duplicidade de código nem funções repetidas (como `get_events`, `delete_event`, etc.).
* O comando de importação `python -c "import app.modules.calendario.service"` executa sem levantar exceções.
* Todos os testes de calendário em `tests/test_calendario.py` executam e passam com sucesso.
