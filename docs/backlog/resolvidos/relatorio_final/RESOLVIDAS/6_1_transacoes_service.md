# Backlog Item 6.1: Acoplamento de Transações no Service (`db.commit` e `db.rollback` internos)

## 1. Descrição do Problema
Diversas funções na camada de serviço (`app/modules/auth/service.py`, `app/modules/efetivo/service.py` e `app/modules/equipamentos/service.py`) acoplavam regras de negócio e infraestrutura de banco de dados executando commits (`db.commit()`) ou rollbacks (`db.rollback()`) explícitos. Esse comportamento quebra o padrão de transação por request (Unit of Work) do FastAPI, gerando transações parciais ou quebras de integridade caso múltiplos serviços sejam encadeados em um único escopo de request.

## 2. Plano de Implementação
1. **Substituir commits/rollbacks por flush:** Localizar todas as ocorrências de `await db.commit()` e `await db.rollback()` dentro dos arquivos da pasta `app/modules/*/service.py`.
2. **Uso exclusivo de flush:** Trocar estas linhas por `await db.flush()`. O flush sincroniza o estado em memória com as constraints de banco de dados sem efetivar o commit físico da transação, mantendo as alterações pendentes.
3. **Delegação de Transação:** Assegurar que o commit final ou rollback seja gerido unicamente pela dependência global do banco em `app/bootstrap/dependencies.py` (`get_db`) ao término do request de forma automática.

## 3. Critérios de Aceitação
* Nenhuma função de serviço (`app/modules/*/service.py`) possui chamadas diretas a `db.commit()` ou `db.rollback()`.
* Erros e exceções gerados na camada de serviço disparam rollback automático do request gerenciado pelo middleware do FastAPI.
* Cenários de transações combinadas (múltiplas operações em um único endpoint) executam com sucesso ou revertem juntas de forma atômica.
