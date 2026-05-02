[TÍTULO]
Feature | Inspeções | Adicionar Data de Início e DPE na abertura da inspeção

[CONTEXTO]
Módulo: Inspeções  
Tela: Módulo de Inspeções → + Abrir Inspeção → Abrir Nova Inspeção

[OBJETIVO]
Adicionar os campos Data de Início e DPE na janela de abertura de uma nova inspeção.

[COMPORTAMENTO ESPERADO]
- Campo “Data de Início” exibido na abertura da inspeção
- Campo “Data de Início” preenchido automaticamente com a data da abertura
- Campo “Data de Início” editável manualmente
- Campo “DPE” exibido na mesma tela
- DPE calculada automaticamente com base nas regras definidas

[REGRAS]
- Data de Início pode ser alterada manualmente se necessário
- DPE deve respeitar a regra de cálculo baseada na duração dos tipos de inspeção
- Manter consistência com os dados salvos no backend

[DEPENDÊNCIAS]
- Campo “Duração” no Tipo de Inspeção
- Implementação da regra de cálculo da DPE

[RESTRIÇÕES]
- Não alterar outras etapas do fluxo de inspeção
- Não modificar regras de negócio fora da abertura da inspeção
- Não implementar aqui o cadastro da duração nem a lógica base de cálculo, apenas o uso dos campos na tela

[ACEITE]
- Janela “Abrir Nova Inspeção” exibe Data de Início e DPE
- Data de Início vem preenchida por padrão e pode ser editada
- DPE aparece calculada corretamente
- Dados persistem corretamente após salvar