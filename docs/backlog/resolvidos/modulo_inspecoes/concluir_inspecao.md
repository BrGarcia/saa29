[TÍTULO]
Botão “Concluir Inspeção” não altera status mesmo com todas tarefas concluídas

[CONTEXTO]
Módulo de Inspeções → Detalhes da Inspeção  
Ação: clicar em “Concluir Inspeção”

[COMPORTAMENTO ATUAL]
Mesmo com todas as tarefas concluídas, ao clicar em “Concluir Inspeção”:
- nenhuma ação efetiva ocorre  
- status permanece “em andamento”  
- sem feedback claro de erro

[COMPORTAMENTO ESPERADO]
Ao concluir todas as tarefas e acionar o botão:
- inspeção deve mudar para status “concluída”  
- alteração deve ser persistida  
- UI deve refletir novo status

[REPRODUÇÃO]
1. Abrir uma inspeção  
2. Concluir todas as tarefas  
3. Clicar em “Concluir Inspeção”  
4. Status não muda

[HIPÓTESE]
- Falha na chamada do endpoint (não disparada ou erro silencioso)  
- Validação backend impedindo conclusão  
- Estado frontend não sincronizado após ação  
- Possível ausência de trigger de atualização de status

[RESTRIÇÕES]
Não alterar CSP  
Não impactar fluxo de tarefas ou inspeções existentes

[ACEITE]
- Botão executa ação corretamente  
- Status muda para “concluída”  
- Persistência confirmada após reload  
- UI atualizada sem inconsistências  
- Sem erros silenciosos