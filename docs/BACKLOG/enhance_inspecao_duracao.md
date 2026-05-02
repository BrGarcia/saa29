[TÍTULO]
Feature | Configurações | Adicionar duração ao Tipo de Inspeção

[CONTEXTO]
Módulo: Configurações  
Tela: Inspeções → Novo Tipo de Inspeção

[OBJETIVO]
Adicionar campo de duração ao Tipo de Inspeção para uso no cálculo da data prevista de encerramento.

[COMPORTAMENTO ESPERADO]
- Campo “Duração” disponível na criação e edição  
- Valor persistido corretamente  
- Dado acessível para futuras regras de negócio

[REGRAS]
- Definir unidade da duração (ex: dias) 
- Validar entrada (não nulo, valor positivo, menor que 180)  
- Garantir compatibilidade com registros existentes

[DEPENDÊNCIAS]
- Necessário para cálculo da DPE na abertura da inspeção (a ser implementado em outra issue docs\BACKLOG\enhance_inspecao_calc_dpe.md)

[RESTRIÇÕES]
- Não implementar cálculo da DPE nesta issue  
- Não alterar outras funcionalidades de inspeção

[ACEITE]
- Tipo de inspeção pode ser criado/editado com duração  
- Valor salvo corretamente  
- Sem impacto em funcionalidades existentes