[FEATURE] Encarregado | Criar módulo de ciência e acompanhamento de alterações

[CONTEXTO]

Há necessidade de um novo módulo/página específica para o Encarregado, consolidando alterações realizadas pelos Mantenedores em um fluxo de visualização e ciência.

[OBJETIVO]

Criar um módulo exclusivo para listar alterações pendentes de ciência, permitindo ao Encarregado acompanhar e registrar visualmente que tomou conhecimento das mudanças.

[COMPORTAMENTO ESPERADO]

- Exibir uma página própria para o módulo Encarregado.
- Listar apenas alterações pendentes de marcação com visto.
- Exibir os registros de forma sucinta, em cards empilhados.
- Organizar os cards por origem da alteração:
  - [PANES] Pane não-programadas concluídas. Ex. [AERONAVE] [DESCRICAO DA PANE] [SOLUÇAO DA PANE] [TRIGRAMA DO RESPONSAVEL]
  - [INSPEÇÃO] Tarefas realizadas.: EX [AERONAVE] [TAREFA FINALIZADA] [TRIGRAMA DO RESPONSAVEL]
  - [INVENTÁRIO] Últimas alterações no inventário. [AERONAVE][SLOT][SN QUE SAIU][SN QUE ENTROU][TRIGRAMA DO RESPONSAVEL]
  - [VENCIMENTOS] Últimas alterações nos vencimentos. [AERONAVE][EQUIPAMENTO][TIPO DE CONTROLE][DATA VENCIMENTO NOVO][TRIGRAMA DO RESPONSAVEL]
- Incluir um botão de visto estilo check ao lado de cada item.
- O módulo deve servir para ciência e apoio operacional ao lançamento posterior no sistema interno da FAB.

[DEPENDÊNCIAS]

- Registros de alterações já existentes nos módulos de origem.
- Definição da lógica de seleção dos itens pendentes de visto.

[RESTRIÇÕES]

- O módulo deve apenas visualizar registros.
- Não deve realizar alterações no banco de dados.
- Não deve editar, confirmar ou concluir registros no SAA29.
- Não deve alterar o fluxo dos módulos de origem.
- Manter apresentação objetiva e compacta.

[ACEITE]

- Existe uma página própria para o módulo Encarregado.
- A página lista apenas alterações pendentes de visto.
- Os itens aparecem em cards empilhados, separados por categoria.
- Cada item exibe um botão de visto visual.
- Nenhuma ação do módulo altera dados persistidos no banco.
- O módulo atende ao objetivo de ciência e acompanhamento operacional.