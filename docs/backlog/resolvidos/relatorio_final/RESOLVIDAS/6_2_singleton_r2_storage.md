# Backlog Item 6.2: Instanciação Ineficiente de Conexões no R2StorageService

## 1. Descrição do Problema
A função fábrica de storage `get_storage_service` em `app/shared/core/storage.py` instanciava um novo `R2StorageService` a cada requisição ou chamada. O construtor do `R2StorageService` criava um cliente `boto3` para o Cloudflare R2 a cada chamada, incorrendo em resolução cara de credenciais, assinatura SigV4, setup de conexão HTTP/TLS e latência adicional no processamento.

## 2. Plano de Implementação
1. **Importação do lru_cache:** Importar o decorador `lru_cache` de `functools` em `app/shared/core/storage.py`.
2. **Transformar em Singleton:** Decorar a função `get_storage_service()` com `@lru_cache(maxsize=1)`. Isso faz com que a primeira chamada gere a instância do storage service e as chamadas subsequentes reutilizem a mesma instância e pool de conexão HTTPS persistente.
3. **Gerenciar Mocks em Testes:** Em arquivos de testes que mockam as configurações do R2 (`tests/conftest.py` ou unitários), certificar-se de limpar o cache da fábrica de storage usando `get_storage_service.cache_clear()` para evitar reutilização de credenciais de teste em produção e vice-versa.

## 3. Critérios de Aceitação
* A função `get_storage_service()` retorna a mesma referência de objeto em chamadas repetidas dentro de um mesmo ciclo de workers do servidor.
* A suíte de testes de upload de arquivos no storage executa sem lentidão ou estouro de file descriptors de sockets abertos.
* Os testes passam e limpam os estados de cache de singleton de forma confiável.
