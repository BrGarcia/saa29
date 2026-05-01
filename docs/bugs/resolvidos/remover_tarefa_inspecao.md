[TÍTULO]
Erro 404 ao remover tarefa de template de inspeção

[CONTEXTO]
Configurações → Inspeções → “Gerenciar Tipos (templates)”  
Janela: “Tipos de Inspeção” → “Gerenciar Tarefas”  
Ação: Remover tarefa  
Endpoint: DELETE /inspecoes/tipos/{tipo_id}/tarefas/{tarefa_id}

[COMPORTAMENTO ATUAL]
Erro 404 (Not Found) ao tentar remover tarefa do template.

Console:
DELETE /inspecoes/tipos/{tipo_id}/tarefas/{tarefa_id} → 404

Stack:
- apiFetch (app.js:85)
- removerTarefaTemplate (configuracoes.js:938)

[COMPORTAMENTO ESPERADO]
Tarefa deve ser removida do template com sucesso e lista atualizada sem erro.

[REPRODUÇÃO]
1. Configurações  
2. Gerenciar Tipos (templates)  
3. Selecionar tipo de inspeção  
4. Gerenciar Tarefas  
5. Remover tarefa → erro 404

[HIPÓTESE]
- Endpoint inexistente ou rota incorreta no backend  
- Divergência entre ID enviado e recurso existente  
- Possível mismatch entre rota definida e chamada no frontend

[RESTRIÇÕES]
Não alterar CSP  
Não impactar outras operações de templates/inspeções

[ACEITE]
- DELETE executado com sucesso  
- Tarefa removida do template  
- Lista atualizada corretamente  
- Sem erro 404 no console