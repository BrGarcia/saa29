# Duvidas e Pendencias - Modulo Calendario

## P5 - To-Do service
- Situacao: nao existe modulo `todo_service` ou tabela de To-Do no codigo atual.
- Decisao aplicada: o agregador do calendario possui adaptador `_get_task_events()` no-op, retornando lista vazia ate o modulo de tarefas/deadlines existir.
- Impacto: filtro de UI `Tarefas` ja existe, mas nao exibira eventos enquanto nao houver fonte persistida para tarefas.
