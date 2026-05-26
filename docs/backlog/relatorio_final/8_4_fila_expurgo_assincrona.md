# Backlog Item 8.4: Criação de Fila de Expurgo Assíncrona para Arquivos

## 1. Descrição do Problema
O expurgo físico de imagens e documentos no Cloudflare R2 é realizado de forma síncrona durante a chamada HTTP `DELETE /{pane_id}/anexos/{anexo_id}`. A espera pela resposta de rede de rede externa bloqueia a thread de execução do uvicorn, degradando a performance e expondo o servidor a lentidões se o R2 responder de forma demorada.

## 2. Plano de Implementação
1. **Adicionar tabela de expurgo:** Criar modelo ORM `AnexoExpurgo` para armazenar caminhos/keys de arquivos que precisam ser removidos fisicamente do storage.
2. **Gravação rápida no banco:** No endpoint de exclusão, em vez de deletar síncronamente:
   - Gravar a key do arquivo na tabela de expurgo.
   - Remover a linha do anexo e retornar `204 No Content` imediatamente para o cliente.
3. **Worker de segundo plano:** Criar tarefa em background periódica no FastAPI (`BackgroundTasks` ou agendada) ou script de cron que consulta `AnexoExpurgo`, exclui os objetos no Cloudflare R2 e remove os itens da fila de expurgo após confirmação.

## 3. Critérios de Aceitação
* A rota de exclusão de anexo responde de forma instantânea sem realizar chamadas de rede externas síncronas para o Cloudflare R2.
* Os caminhos são acumulados na fila de expurgo e limpos de forma assíncrona.
* Logs registram a limpeza de cada arquivo físico com sucesso ou tentativas de re-processamento em caso de indisponibilidade de rede.
