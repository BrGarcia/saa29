# Backlog Item 7.2: Risco de DoS em Requisições de Calendário por Ranges Amplos

## 1. Descrição do Problema
O endpoint `/api/v1/calendario/eventos` permitia filtrar por qualquer intervalo de datas (`start_date` a `end_date`), sem restringir o range máximo. Isso expunha a aplicação a ataques de Negação de Serviço (DoS) e estouros de memória. Um cliente malicioso solicitando um range de 100 anos forçava o uvicorn a consultar, ordenar e serializar milhares de linhas em uma única requisição.

## 2. Plano de Implementação
1. **Validação de Range no Router:** No arquivo `app/modules/calendario/router.py`, na rota de listagem de eventos:
   - Calcular a diferença de dias entre `end_date` e `start_date`.
   - Se `(end_date - start_date).days > 366`, levantar erro HTTP `422 Unprocessable Entity` com a mensagem `"Range máximo permitido: 366 dias."`.
2. **Defesa de Limite de Consulta:** Adicionar uma restrição de contagem física nas queries SQLAlchemy da camada de serviço (`app/modules/calendario/service.py`):
   - Adicionar `.limit(5000)` à consulta de eventos de calendário e eventos de DPE de inspeção.
   - Emitir um log estruturado com severidade `WARNING` se o limite de registros for atingido para sinalizar abuso ou necessidade de paginação.

## 3. Critérios de Aceitação
* Requisições para `/api/v1/calendario/eventos` com intervalos superiores a 1 ano (366 dias) retornam status `422 Unprocessable Entity`.
* Consultas normais com intervalos permitidos executam com limite defensivo de 5.000 linhas, não travando a thread principal da aplicação.
* A suíte de testes unitários em `tests/test_calendario.py` cobre e valida a rejeição de ranges amplos.
