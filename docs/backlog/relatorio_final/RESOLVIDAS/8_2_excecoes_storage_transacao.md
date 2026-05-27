# Backlog Item 8.2: Tratamento de Exceções de Storage em Transação

## 1. Descrição do Problema
O R2StorageService engolia exceções retornando `False` no método `delete()`. Isso impedia que falhas de comunicação com a API da Cloudflare abortassem a transação no banco de dados, fazendo com que o registro de um anexo fosse excluído do banco mesmo que o arquivo físico permanecesse no storage de produção, gerando arquivos órfãos.

## 2. Plano de Implementação
1. **Remover try/except silencioso no Storage:** Em `app/shared/core/storage.py`, no método `delete()` da classe `R2StorageService`, remover a captura genérica de erros que retorna `False` e permitir que exceções de rede/autenticação botocore/boto3 propaguem.
2. **Tratar erro de arquivo inexistente (404/NoSuchKey):** Tratar apenas o erro 404 (NoSuchKey) como sucesso idempotente (retornando `True`), pois o arquivo já não existe.
3. **Tratar o retorno no Service:** Em `excluir_anexo` do arquivo `app/modules/panes/service.py`, lançar exceção explícita se a remoção falhar, abortando o `db.delete(anexo)`.

## 3. Critérios de Aceitação
* Qualquer erro de rede ou de credenciais com o Cloudflare R2 durante a exclusão de um anexo impede a deleção do registro no banco de dados.
* Em caso de falha do storage, a transação da requisição sofre rollback e o registro permanece intacto no sistema.
* Arquivos que já foram removidos no storage retornam sucesso (idempotência).
