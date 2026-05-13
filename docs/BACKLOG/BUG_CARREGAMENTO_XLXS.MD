[TÍTULO]
Bug | Configurações | Upload XLSX do inventário falha e gera erro CSRF em nova tentativa

[CONTEXTO]
Módulo: Configurações  
Funcionalidade: “Carregamento Inventário (XLSX)”  
Endpoint: /equipamentos/inventario/upload-xlsx  
Arquivo utilizado: 5919.xlsx

[COMPORTAMENTO ATUAL]
Primeira tentativa:
- Sistema exibe relatório zerado:
  - Linhas lidas: 0
  - PNs encontrados: 0
  - PNs ignorados: 0
  - Itens atualizados: 0

Segunda tentativa de upload:
- Toast:
  “Erro de Segurança (CSRF): The CSRF signatures submitted do not match. Recarregue a página.”
- Console:
  POST /equipamentos/inventario/upload-xlsx → 403 (Forbidden)

[COMPORTAMENTO ESPERADO]
- XLSX deve ser processado corretamente na primeira tentativa
- Novos uploads devem funcionar sem necessidade de recarregar página
- Token CSRF deve permanecer válido durante o fluxo

[REPRODUÇÃO]
1. Abrir Configurações  
2. Selecionar “Carregamento Inventário (XLSX)”  
3. Enviar arquivo 5919.xlsx  
4. Observar relatório zerado  
5. Tentar novo upload → erro CSRF / 403

[HIPÓTESE]
- Parser XLSX não está reconhecendo o arquivo/layout
- Fluxo de upload pode estar invalidando ou regenerando incorretamente o token CSRF
- Token CSRF não está sendo atualizado/reutilizado corretamente após falha
- Possível ausência de sincronização entre cookie e header CSRF

[ANÁLISE CSP]
- Baixa probabilidade de relação com CSP
- Erro indica falha de validação CSRF (403), não bloqueio de política de conteúdo

[RESTRIÇÕES]
- Não remover proteção CSRF
- Não alterar CSP
- Preservar compatibilidade com uploads existentes

[ACEITE]
- XLSX processado corretamente
- Relatório apresenta dados reais processados
- Upload pode ser repetido sem recarregar página
- Sem erro CSRF ou 403
- Fluxo permanece seguro