[STATUS: RESOLVIDO]
[TÍTULO]
Erro 409 ao ativar tarefa no Catálogo (MissingGreenlet / updated_at)

[CONTEXTO]
Configurações → “Gerenciar Tarefas do Catálogo” → “Catálogo Global de Tarefas”  
Ação: editar tarefa e alterar status (inativa → ativa)  
Endpoint: /inspecoes/tarefas-catalogo/{id}

[COMPORTAMENTO ATUAL]
Erro 409 (Conflict) ao salvar alteração.

Erro backend:
MissingGreenlet ao acessar campo "updated_at" em TarefaCatalogoOut

Mensagem:
"greenlet_spawn has not been called; can't call await_only() here"

Console:
PUT/GET /inspecoes/tarefas-catalogo/{id} → 409

[COMPORTAMENTO ESPERADO]
Alteração de status deve ser persistida normalmente, retornando objeto atualizado sem erro.

[REPRODUÇÃO]
1. Configurações  
2. Gerenciar Tarefas do Catálogo  
3. Editar tarefa inativa  
4. Alterar para ativa  
5. Salvar → erro 409

[HIPÓTESE]
Atributo "updated_at" está sendo acessado fora de contexto assíncrono válido (ORM lazy load / sessão fechada / ausência de greenlet no SQLAlchemy async).

[RESTRIÇÕES]
Não alterar CSP  
Não impactar outras operações de inspeção

[ACEITE]
- Status atualizado com sucesso  
- Sem erro MissingGreenlet  
- Campo updated_at retornado corretamente  
- Sem erro 409  
- UI atualiza sem falha