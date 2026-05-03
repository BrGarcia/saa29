[TÍTULO]
Badge “MAN” exibida incorretamente em tarefas padrão da inspeção

[CONTEXTO]
Módulo de Inspeções → Detalhes da Inspeção  
Tabela: “Checklist de Tarefas” → coluna “Ação / Descrição”  
Funcionalidade: identificação de tarefas adicionadas manualmente

[COMPORTAMENTO ATUAL]
Todas as tarefas exibem badge “MAN”, inclusive aquelas que já fazem parte da inspeção (carregadas por template).

[COMPORTAMENTO ESPERADO]
- Tarefas padrão da inspeção (template): **não devem exibir badge**  
- Tarefas adicionadas manualmente:
  - devem ser identificadas  
  - exibir **TRIGRAMA do mantenedor** (em vez de “MAN”)

[REPRODUÇÃO]
1. Abrir uma inspeção  
2. Ir para “Checklist de Tarefas”  
3. Observar badge “MAN” em tarefas padrão

[HIPÓTESE]
- Falta de distinção entre origem da tarefa (template vs manual)  
- Campo/flag de origem não está sendo considerado no frontend  
- Badge sendo aplicado de forma genérica

[RESTRIÇÕES]
Não alterar CSP  
Não impactar lógica de criação/execução de tarefas  
Manter consistência com modelo de auditoria (TRIGRAMA)

[ACEITE]
- Tarefas de template sem badge  
- Tarefas manuais exibem TRIGRAMA correto  
- Identificação baseada na origem da tarefa  
- UI consistente e sem ambiguidade