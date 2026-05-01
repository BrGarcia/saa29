[TÍTULO]
Cores dos botões na janela “Selecione a Aeronave” não refletem corretamente o status da aeronave

[CONTEXTO]
Página: /panes  
Ação: clicar em “+ Registrar Pane”  
Janela: “Selecione a Aeronave”

[COMPORTAMENTO ATUAL]
Os botões das matrículas exibem apenas duas cores:
- verde para aeronaves disponíveis
- amarelo para os demais status

[COMPORTAMENTO ESPERADO]
As cores devem refletir corretamente os status da aeronave:
- verde = disponível
- azul = inspeção
- amarelo = indisponível
- cinza = estocada

[REPRODUÇÃO]
1. Acessar /panes  
2. Clicar em “+ Registrar Pane”  
3. Abrir “Selecione a Aeronave”  
4. Observar cores incorretas dos botões

[RESTRIÇÕES]
- Alterar somente os campos/trechos relacionados à exibição dessas cores
- Não mexer nas demais lógicas do sistema
- Se houver necessidade de mudança mais ampla, realizar um commit antes da alteração

[ACEITE]
- Cada status da aeronave deve ter a cor correta
- Nenhuma lógica funcional do sistema deve ser afetada
- A matriz de aeronaves deve refletir fielmente os status atuais