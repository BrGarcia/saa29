[TÍTULO]
Enhancement | Panes | Adicionar lista de Sistemas/ATA no registro de pane

[CONTEXTO]
Módulo: Panes  
Tela: + Registrar Pane → “Nova Ocorrência”  
Campo: “Sistema / ATA (Opcional)”

[OBJETIVO]
Padronizar o preenchimento do campo Sistema/ATA através de uma lista pré-definida.

[COMPORTAMENTO ESPERADO]
- Campo exibido como lista suspensa (dropdown)  
- Exibir código ATA + nome do sistema  
- Permitir seleção opcional (não obrigatório)  

[LISTA DE VALORES]
22 | VOO AUTOMÁTICO  
23 | COMUNICAÇÃO  
27 | COMANDOS DE VOO  
31 | INDICAÇÃO E REGISTRO  
34 | RÁDIO-NAVEGAÇÃO  
42 | AVIÔNICA INTEGRADA  
94 | HOTAS  
97 | SISTEMA DE GRAVAÇÃO  

[REGRAS]
- Campo continua opcional  
- Valor selecionado deve ser persistido corretamente  
- Exibir ATA e descrição de forma legível (ex: “22 - VOO AUTOMÁTICO”)

[RESTRIÇÕES]
- Não alterar outros campos do formulário  
- Não tornar o campo obrigatório  
- Manter compatibilidade com registros existentes

[ACEITE]
- Dropdown exibido corretamente  
- Valores conforme lista definida  
- Seleção salva corretamente  
- Campo pode permanecer vazio sem erro