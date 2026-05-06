# Plano de Correção: Relatório de Auditoria Claude


Este documento detalha o plano de ação para corrigir as vulnerabilidades e bugs identificados no relatório de auditoria `docs/relatorio/claude.md`. Todas as correções propostas respeitam estritamente as diretrizes de segurança (Zero Inline Scripts / CSP) e o contexto arquitetural do SAA29 (DDD, SQLAlchemy async).


## Visão Geral das Correções


A primeira auditoria (05/05/2026) identificou 5 itens críticos, sendo 2 de segurança, 2 bugs na regra de negócios de inspeções e 1 problema arquitetural de gerenciamento de sessão de banco de dados.
A segunda auditoria (06/05/2026) identificou 5 novos achados: 1 de segurança (CSRF), 3 bugs (inventário e processamento de anexos) e 1 problema arquitetural (commit prematuro em efetivo).

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


## 3. Core e Segurança (2026-05-06)


### 3.1 Segurança: Bypass de CSRF em ambientes não-produção (Hash: `c8e4a2`)
*   **Problema:** O header `X-Skip-CSRF: true` desativa a validação em qualquer ambiente exceto `production`, permitindo bypass em staging/homologação.
*   **Plano de Ação (`app/shared/middleware/csrf.py`):**
    1.  Modificar a validação para que a exceção só ocorra quando `settings.app_env == "testing"`.
    2.  Remover ou limitar rigorosamente o uso do header `X-Skip-CSRF`.


---


## 4. Módulo de Equipamentos / Inventário (2026-05-06)


### 4.1 Bug: Ajuste de inventário não herda controles de vencimento (Hash: `4d9c1b`)
*   **Problema:** A criação de um novo `ItemEquipamento` via ajuste de inventário ignora a matriz de vencimentos daquele modelo de equipamento.
*   **Plano de Ação (`app/modules/equipamentos/service.py`):**
    1.  Em `_obter_ou_criar_item_por_pn`, logo após o `db.add(item)` e `db.flush()`, adicionar a lógica de herança.
    2.  Consultar `EquipamentoControle` associado ao `modelo_id`.
    3.  Inserir os registros correspondentes em `ControleVencimento` para o novo item.
    4.  *(Opcional/Recomendado)* Extrair a lógica de herança de `criar_item_com_heranca` para um helper reutilizável.


---


## 5. Módulo de Panes / Anexos (2026-05-06)


### 5.1 Bug: Ordem de exclusão de anexo gera arquivos órfãos (Hash: `7e2f50`)
*   **Problema:** A função deleta o registro do banco antes de tentar apagar do storage (R2). Se o storage falhar, o banco sofre rollback, mas o arquivo fica órfão.
*   **Plano de Ação (`app/modules/panes/service.py`):**
    1.  Em `excluir_anexo`, capturar o `caminho_arquivo`.
    2.  Tentar remover primeiro do storage com `await storage_svc.delete(caminho)`.
    3.  Apenas após o sucesso no storage, deletar o registro do banco `await db.delete(anexo)` e `await db.flush()`.
    4.  Tratar exceções do storage apropriadamente.


### 5.2 Bug: Imagens de background travadas em "processando" (Hash: `b6a8d3`)
*   **Problema:** Falhas no processamento em background deixam o anexo eternamente com `caminho_arquivo="processando"`, quebrando a UI.
*   **Plano de Ação (`app/modules/panes/service.py`):**
    1.  Em `processar_imagem_background`, no bloco de fallback genérico (`except Exception`), atualizar o registro no banco para um estado de erro.
    2.  Abrir uma nova sessão (pois a anterior já pode ter falhado) e alterar o `caminho_arquivo` para algo como `"ERRO"` ou apagar o registro.


---


## 6. Módulo de Efetivo (2026-05-06)


### 6.1 Arquitetura: Commit prematuro no registro de indisponibilidade (Hash: `f3b7e9`)
*   **Problema:** Funções `registrar_indisponibilidade` e `remover_indisponibilidade` chamam `await db.commit()` diretamente no service, quebrando o padrão de transação por request.
*   **Plano de Ação (`app/modules/efetivo/service.py`):**
    1.  Substituir os `await db.commit()` por `await db.flush()`.
    2.  Remover chamadas desnecessárias de `await db.refresh(...)` após deleção se for o caso.


---


## 7. Conformidade com CSP e Padrões (Docs)


Nenhuma das implementações exige alterações no frontend. Tratam-se de refatorações no backend (Python), logo a **Conformidade com a CSP** (`docs/methodology/CSP.md`) permanece intacta (Zero Inline Scripts). O banco de dados não sofrerá migrações (DDL), mantendo o `CTX.md`.


## Próximos Passos
*   [x] Revisar/Implementar o item 1.1 e 1.3 (Sessão de Auth e Refresh Token).
*   [x] Implementar item 1.2 (Soft-delete).
*   [x] Corrigir as funções de Inspeção (2.1 e 2.2).
*   [x] Implementar correção CSRF (3.1).
*   [x] Corrigir bug de herança no inventário (4.1).
*   [x] Corrigir bugs de ordem de exclusão e estado de anexos (5.1 e 5.2).
*   [x] Refatorar commits do módulo de Efetivo (6.1).
