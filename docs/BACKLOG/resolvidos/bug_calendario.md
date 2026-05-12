[TÍTULO]
Bug | Calendário | Falha no carregamento de eventos no Dashboard e página Calendário

[CONTEXTO]
Módulos afetados:
- Dashboard → card “Calendário”
- Página “Calendário”

Frontend:
- dashboard.js
- calendario.js
- app.js

Endpoints:
- /calendario/eventos
- /api/v1/calendario/eventos

[COMPORTAMENTO ATUAL]
Dashboard:
- Card exibe “Erro ao carregar calendário”
- Console:
  GET /calendario/eventos?... → 404 (Not Found)

Página Calendário:
- Toast: “Erro desconhecido na API”
- Console:
  GET /api/v1/calendario/eventos?... → 500 (Internal Server Error)

[COMPORTAMENTO ESPERADO]
- Eventos do calendário devem carregar corretamente no Dashboard e na página Calendário
- Endpoints devem responder sem erro
- UI deve renderizar os eventos normalmente

[REPRODUÇÃO]
1. Abrir Dashboard → erro no card Calendário
2. Abrir página Calendário → erro 500 e toast de falha

[HIPÓTESE]
- Inconsistência entre rotas utilizadas:
  - Dashboard usa /calendario/eventos
  - Página usa /api/v1/calendario/eventos
- Possível endpoint inexistente no Dashboard (404)
- Possível erro interno no backend ao processar eventos (500)
- Divergência de prefixo de API ou registro incorreto das rotas

[RESTRIÇÕES]
- Não alterar CSP
- Não modificar lógica dos eventos além do necessário
- Manter compatibilidade entre Dashboard e módulo Calendário

[ACEITE]
- Dashboard carrega eventos sem erro
- Página Calendário carrega eventos corretamente
- Sem erros 404 ou 500
- Sem toast de erro
- Rotas padronizadas e consistentes