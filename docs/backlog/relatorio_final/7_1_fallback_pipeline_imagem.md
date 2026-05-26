# Backlog Item 7.1: Tratamento de Erros e Estados Incompletos no Pipeline de Imagem

## 1. Descrição do Problema
O processamento de imagens do pipeline (`imgdiet`) rodava de forma assíncrona em tarefas de segundo plano (`BackgroundTasks`). Quando ocorriam erros críticos no processamento da imagem e no upload subsequente do arquivo original (fallback), o registro da imagem no banco de dados mantinha-se indefinidamente com o status temporário `"processando"`, quebrando a interface do usuário e deixando um arquivo inacessível sem aviso de erro visível.

## 2. Plano de Implementação
1. **Tratamento de Exceção no Background Worker:** Em `app/modules/panes/service.py`, na função `processar_imagem_background`, expandir o bloco `except Exception as exc` externo.
2. **Atualização de Status de Erro:**
   - No caso de falha do processamento WebP E falha no upload original de fallback, abrir uma sessão isolada de banco de dados (`get_session_factory`).
   - Buscar o `Anexo` pelo `anexo_id` e definir `caminho_arquivo = "ERRO"`.
   - Salvar as alterações via commit físico do worker assíncrono.
3. **Tratamento na UI:** Ajustar o frontend em `panes.js` ou na exibição do anexo para tratar o valor `"ERRO"`, exibindo um alerta textual "Falha no upload/processamento" e disponibilizando um botão para que o operador exclua o registro quebrado.

## 3. Critérios de Aceitação
* Em caso de falha no pipeline de imagem em background, o registro no banco não permanece com status `"processando"` após a falha.
* O valor de `caminho_arquivo` recebe o valor `"ERRO"` ou o registro é expurgado caso as tentativas de upload falhem de forma completa.
* A interface do usuário reflete o estado de erro, impedindo o download de um link quebrado e alertando o operador.
