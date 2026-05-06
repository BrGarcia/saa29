# Plano de Correção: Relatório de Auditoria Claude


Este documento detalha o plano de ação para corrigir as vulnerabilidades e bugs identificados no relatório de auditoria `docs/relatorio/claude.md`. Todas as correções propostas respeitam estritamente as diretrizes de segurança (Zero Inline Scripts / CSP) e o contexto arquitetural do SAA29 (DDD, SQLAlchemy async).


## Visão Geral das Correções


A auditoria identificou 5 itens críticos, sendo 2 de segurança, 2 bugs na regra de negócios de inspeções e 1 problema arquitetural de gerenciamento de sessão de banco de dados.


---


## 1. Módulo de Autenticação e Segurança (Auth)


### 1.1 Correção: Revogação do Refresh Token no Logout (Hash: `e3a1f7`)
*   **Problema:** O endpoint `/auth/logout` revoga o Access Token mas deixa o `saa29_refresh_token` intacto e não atualiza o registro no banco, permitindo que a sessão seja renovada.
*   **Plano de Ação (`app/modules/auth/router.py`):**
    1.  No endpoint de logout, interceptar o cookie `saa29_refresh_token` do request.
    2.  Decodificar o JWT do refresh token para extrair o campo `jti`.
    3.  Buscar em `TokenRefresh` com esse `jti`.
    4.  Atualizar a coluna `revogado_em = func.now()`.
    5.  No objeto `response`, invocar `response.delete_cookie(key="saa29_refresh_token", path="/auth/refresh")`.


### 1.2 Correção: Verificação de Usuário Ativo no Middleware (Hash: `b2c9d4`)
*   **Problema:** A função `get_current_user` não barra usuários logicamente desativados.
*   **Plano de Ação (`app/bootstrap/dependencies.py`):**
    1.  Logo após a busca do usuário no banco de dados (`if usuario is None:`), adicionar:
        ```python
        if not usuario.ativo:
            raise credentials_exception
        ```
*   **Alinhamento CTX:** Garante a "revogação instantânea de acesso".


### 1.3 Arquitetura: Delegar Commit em `autenticar_usuario` (Hash: `a9f2b1`)
*   **Problema:** `autenticar_usuario` executa `await db.commit()` diretamente, encerrando prematuramente a transação.
*   **Plano de Ação (`app/modules/auth/service.py` e `router.py`):**
    1.  Substituir as chamadas de `await db.commit()` por `await db.flush()` em `autenticar_usuario`.
    2.  Refatorar `POST /auth/login` em `router.py` para capturar falhas de autenticação (`raise HTTPException`) apenas *depois* de fazer um commit manual ou forçar a execução isolada para manter o log de tentativas.


---


## 2. Módulo de Inspeções (Regras de Negócio)


### 2.1 Bug: Status da Aeronave na Conclusão/Cancelamento (Hash: `f1a3e8`)
*   **Problema:** Cancelar ou concluir joga a aeronave para `DISPONIVEL` ignorando inspeções paralelas.
*   **Plano de Ação (`app/modules/inspecoes/service.py`):**
    1.  Antes de alterar o status da aeronave em `cancelar_inspecao` e `concluir_inspecao`.
    2.  Verificar `inspecoes_ativas_paralelas = SELECT COUNT(*) ...`.
    3.  Apenas se o resultado for 0, definir `DISPONIVEL`.


### 2.2 Bug: Deduplicação de Tarefas Ignorando "Obrigatória" (Hash: `d7b5c2`)
*   **Problema:** Um cartão opcional sendo inserido antes de um obrigatório pode fazer a tarefa virar opcional.
*   **Plano de Ação (`app/modules/inspecoes/service.py`):**
    1.  Em `abrir_inspecao`, durante a deduplicação, fundir a restrição: `vistos[titulo]['obrigatoria'] = vistos[titulo]['obrigatoria'] or template.obrigatoria`.


---


## 3. Conformidade com CSP e Padrões (Docs)


Nenhuma das implementações exige alterações no frontend. Tratam-se de refatorações no backend (Python), logo a **Conformidade com a CSP** (`docs/methodology/CSP.md`) permanece intacta (Zero Inline Scripts). O banco de dados não sofrerá migrações (DDL), mantendo o `CTX.md`.


## Próximos Passos
*   [x] Revisar/Implementar o item 1.1 e 1.3 (Sessão de Auth e Refresh Token).
*   [x] Implementar item 1.2 (Soft-delete).
*   [x] Corrigir as funções de Inspeção (2.1 e 2.2).
