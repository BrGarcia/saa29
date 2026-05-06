[TÍTULO]
Bug | Panes | Erro 422 ao editar pane (rota interpretando "sistemas" como UUID)

[CONTEXTO]
Módulo: Panes  
Tela: Lista de Panes → botão “Editar”  
Frontend: panes_lista.js / app.js  
Endpoint chamado: GET /panes/sistemas

[COMPORTAMENTO ATUAL]
- Toast: erro de parsing de UUID em "pane_id"
- Backend tenta interpretar "sistemas" como UUID
- Console: GET /panes/sistemas → 422 (Unprocessable Entity)
- Falha ao carregar dados da pane para edição

[COMPORTAMENTO ESPERADO]
- Botão “Editar” deve carregar corretamente os dados da pane selecionada
- Endpoint deve receber um UUID válido (pane_id)
- Modal de edição deve abrir sem erro

[REPRODUÇÃO]
1. Acessar página PANES  
2. Clicar em “Editar” em qualquer registro  
3. Observar erro 422 e falha no carregamento

[HIPÓTESE]
- Rota dinâmica /panes/{pane_id} está capturando “sistemas”
- Conflito com rota estática (ex: /panes/sistemas)
- Frontend chamando endpoint incorreto ao abrir modal
- Possível erro na montagem da URL (faltando ID da pane)

[RESTRIÇÕES]
- Não alterar CSP  
- Não quebrar rotas existentes de panes  
- Manter consistência com padrão de rotas já utilizado

[ACEITE]
- Endpoint chamado com UUID válido  
- Modal de edição abre corretamente  
- Sem erro 422  
- Sem tentativa de parsing incorreto de UUID