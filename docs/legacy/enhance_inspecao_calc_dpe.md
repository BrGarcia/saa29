[TÍTULO]
Enhancement | Inspeções | Implementar cálculo da DPE

[CONTEXTO]
Módulo: Inspeções  
Tela: Abertura de Inspeção / Regras de negócio

[OBJETIVO]
Calcular automaticamente a Data Prevista para Encerramento (DPE) com base na duração dos Tipos de Inspeção.

[COMPORTAMENTO ESPERADO]
- DPE calculada a partir da Data de Início  
- Considerar o Tipo de Inspeção com maior duração  
- DPE = Data de Início + duração (maior entre os tipos)  
- Atualizar automaticamente ao alterar Data de Início ou Tipo(s)

[REGRAS]
- Utilizar duração cadastrada no Tipo de Inspeção  
- Se múltiplos tipos, usar o de maior duração  
- Definir comportamento para ausência de duração (fallback ou bloqueio)

[DEPENDÊNCIAS]
- Campo “Duração” implementado no Tipo de Inspeção

[RESTRIÇÕES]
- Não alterar UI além do necessário para exibição da DPE  
- Não modificar fluxo de criação de inspeção além do cálculo

[ACEITE]
- DPE calculada corretamente conforme regras  
- Recalcula ao alterar parâmetros relevantes  
- Sem erros ou inconsistências  
- Compatível com inspeções existentes