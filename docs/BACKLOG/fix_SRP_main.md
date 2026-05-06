# Refatoração do `app/bootstrap/main.py` (SRP)

## 1. Contexto e Problema
O arquivo principal de inicialização da aplicação (`app/bootstrap/main.py`) cresceu de forma orgânica e atualmente possui mais de 300 linhas. Ele está assumindo múltiplas responsabilidades que fogem ao escopo de um orquestrador (factory), violando o Princípio da Responsabilidade Única (SRP - Single Responsibility Principle). 

Atualmente, o `main.py` gerencia:
- Definição de Middlewares customizados (ex: `SecurityHeadersMiddleware`).
- Lógica de tarefas em segundo plano e agendamentos (Backup no R2, Limpeza de Tokens).
- Regras de negócio de infraestrutura (Inicialização da "Frota Padrão" no banco de dados).
- Manipulação customizada de exceções (Redirecionamentos de HTTP 401/403).
- Registro de rotas e ciclo de vida (`lifespan`).

Isso torna o arquivo difícil de testar, manter e compreender. 

## 2. Objetivo
Extrair as lógicas auxiliares do `main.py` para arquivos de módulos específicos, deixando o `main.py` puramente como o ponto de entrada e orquestração (`create_app`) do framework FastAPI.

## 3. Estrutura Proposta

A extração deve criar/utilizar os seguintes arquivos:

- **`app/shared/middleware/security.py`**
  - Receberá a classe `SecurityHeadersMiddleware`.
- **`app/shared/services/background_tasks.py`** (ou `app/bootstrap/tasks.py`)
  - Receberá as lógicas `_token_cleanup_task`, `_debounced_backup`, `_run_r2_backup` e `_mark_db_dirty`.
- **`app/bootstrap/events.py`** (ou `app/bootstrap/lifespan.py`)
  - Receberá a função assíncrona `lifespan(app: FastAPI)` que coordena a inicialização do app.
- **`app/shared/core/exceptions.py`**
  - Receberá a função `custom_http_exception_handler` para centralizar a lógica de fallback de erros HTTP.
- **`app/bootstrap/seed.py`** (ou integrado em `database.py`)
  - Receberá a função `_ensure_default_aeronaves` e a variável `FROTA_PADRAO`, já que se trata de popular o banco e não de criar o servidor.

## 4. Plano de Implementação Passo a Passo

### Passo 1: Extrair o Middleware de Segurança
1. Criar o arquivo `app/shared/middleware/security.py`.
2. Mover a classe `SecurityHeadersMiddleware` para este arquivo.
3. Importar o middleware de volta no `main.py` na função `_register_middlewares`.

### Passo 2: Extrair Handlers de Exceção
1. Criar `app/shared/core/exceptions.py`.
2. Mover a lógica de `custom_http_exception_handler` para dentro de uma função registradora `setup_exception_handlers(app: FastAPI)`.
3. Chamar `setup_exception_handlers(app)` dentro de `create_app` no `main.py`.

### Passo 3: Extrair Tarefas em Segundo Plano (Background Tasks)
1. Criar `app/bootstrap/tasks.py` (ou em `shared/services`).
2. Mover `_token_cleanup_task`, lógica do debounce e backups do R2.
3. Garantir que as importações do banco e do settings não criem importações circulares.

### Passo 4: Extrair Lógica de Inicialização de Banco de Dados
1. Mover `_ensure_default_aeronaves()` e `FROTA_PADRAO` para um arquivo responsável por setup de DB (como `app/bootstrap/database.py` ou um novo `app/bootstrap/seed.py`).

### Passo 5: Extrair Ciclo de Vida (Lifespan)
1. Criar `app/bootstrap/lifespan.py`.
2. Mover a função `lifespan`. Ela importará as tarefas de background criadas no Passo 3 e o seed criado no Passo 4.
3. Importar a função `lifespan` no `main.py` e passar para a inicialização do `FastAPI()`.

### Passo 6: Limpeza e Validação do `main.py`
1. O `main.py` agora deverá conter apenas as importações necessárias, as rotinas `_register_middlewares`, `_register_routers`, `_mount_static` e a função principal `create_app()`.
2. Rodar a bateria de testes e o linter (`ruff` / `mypy`) para garantir que as importações estão corretas e o sistema continua operante.
3. Testar a inicialização local do servidor garantindo que os backups, seeds e middlewares continuam sendo carregados normalmente.

## 5. Critérios de Aceite
- O arquivo `app/bootstrap/main.py` tem menos de 150 linhas.
- Nenhum comportamento existente (roteamento, redirecionamento, backups, seed) foi quebrado.
- A aplicação passa no comando `pytest` (ou equivalente no projeto).
- O linter / formatador acusa 0 erros na refatoração.