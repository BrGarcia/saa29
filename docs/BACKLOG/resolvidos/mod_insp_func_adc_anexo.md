Implementar funcionalidade de adicionar anexos na pagina Detalhes da Inspeção
esses anexos serao as documentcoes fisicas como inventario fisico, delineamento, liberacao, fotos, relatorios de testes etc.
fluxo da inspecao: 
    quando uuma aeronave entra em inspecao, o INSPETOR (role a ser implementada) ou ENCARREGADO, vai à aeroonave
    com uma prancheta e um formulario verificando as inconsistencias da aeronave (panes ou desgastes natural) que nao
    estejam previstos nos cartoes de tarefa do catalogo global. e esse documento  sera usado para criar as tarefas 
    manualmente no futuro. 
    o mantenedor durante a realizacao da inspecao tambem tem uma ficha de inventario, para ele conferir em loco 
    se os seriais dos equipamentos estao corretos e se estao instalados nos slots corretos. os que estao errados ou 
    nao estao instalados geram panes a serem corrigidas posteriormente.
    Ao final da inspecao o INSPETOR/ENCARREGADO vem com outra ficha em papel e verifica se tudo esta correto.
    A ideia e que esses documentos sejam anexados na inspecao, para que fique registrado na historia da aeronave.
    na pagina de detalhes da inspecao, deve haver um botao de "Anexar Documento" que permita ao usuario enviar um arquivo. esse arquivo sera armazenado no banco de dados e podera ser visualizado na pagina de detalhes da inspecao.
    os arquivos serao enviados para a R2.
    