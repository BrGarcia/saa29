# Plano de Resposta à Auditoria — SAA29

**Data:** 2026-03-30  
**Versão Alvo:** 0.7.0  
**Status:** Planejamento de Implementação  

Este documento detalha o plano de ação para mitigar as 22 vulnerabilidades e falhas técnicas identificadas no arquivo `Auditoria.md`.

---

## 🚀 Fase 1: Correções Críticas (Prioridade Imediata)

Foco em estabilidade do sistema, integridade de dados e proteção contra roubo de sessão.

### 1.1 · AUD-01: Correção de Crash em Panes (Tuple Unpacking)
*   **Ação:** Refatorar `app/panes/service.py` para desestruturar a tupla `(Pane, seq, ano)` retornada por `buscar_pane`.
*   **Arquivos:** `app/panes/service.py`.
*   **Validação:** Testar edição, conclusão e exclusão de panes via interface e verificar ausência de `AttributeError`.

### 1.2 · AUD-02: Alinhamento de Enums (Remoção de INSPETOR)
*   **Ação:** Substituir todas as referências de `INSPETOR` por `ADMINISTRADOR` ou remover conforme o contexto.
*   **Arquivos:** `app/core/enums.py`, `templates/efetivo.html`, `app/auth/schemas.py`, `app/panes/models.py`, `app/dependencies.py`, `tests/test_auth.py`.
*   **Validação:** Verificar se o cadastro de efetivo permite salvar novos usuários sem erro 422.

### 1.3 · AUD-04: Proteção contra XSS (Sanitização Frontend)
*   **Ação:** Implementar função `escapeHtml` centralizada em `static/js/app.js` e aplicá-la em todas as interpolações de strings dinâmicas em `innerHTML`.
*   **Arquivos:** `static/js/app.js`, `templates/efetivo.html`, `templates/panes/lista.html`.
*   **Validação:** Tentar inserir `<script>alert(1)</script>` em um campo e verificar se ele é renderizado como texto literal.

### 1.4 · AUD-03: Invalidação de JWT no Logout
*   **Ação:** Implementar uma blacklist em memória (com previsão para Redis no futuro) para armazenar JTIs (JWT IDs) invalidados até sua expiração natural.
*   **Arquivos:** `app/auth/security.py`, `app/auth/router.py`, `app/config.py`.
*   **Validação:** Tentar usar um token antigo após realizar o logout; o acesso deve ser negado.

---

## 🛡️ Fase 2: Hardening de Segurança e RBAC (Severidade Alta)

Foco em controle de acesso e configurações de ambiente seguras.

### 2.1 · AUD-05 & AUD-12: Implementação de RBAC (Aeronaves e Equipamentos)
*   **Ação:** Adicionar dependências `EncarregadoOuAdmin` em todos os endpoints de escrita (POST, PUT, DELETE) e toggles de status.
*   **Arquivos:** `app/aeronaves/router.py`, `app/equipamentos/router.py`.
*   **Validação:** Tentar alterar uma aeronave com um usuário de perfil `MANTENEDOR` (deve retornar 403 Forbidden).

### 2.2 · AUD-09: Validação MIME-type Rigorosa
*   **Ação:** Adicionar `python-magic` ao `requirements.txt` e forçar interrupção do upload caso a biblioteca de análise de cabeçalhos binários não esteja disponível.
*   **Arquivos:** `requirements.txt`, `app/panes/service.py`.
*   **Validação:** Tentar fazer upload de um arquivo `.sh` renomeado para `.jpg`.

### 2.3 · AUD-06, AUD-07, AUD-08: Configurações de Middleware e App
*   **Ação:** 
    *   Restringir `allow_methods` e `allow_headers` no CORS.
    *   Remover `"*"` de `allowed_hosts`.
    *   Adicionar validador para `APP_SECRET_KEY` em ambiente de produção.
*   **Arquivos:** `app/main.py`, `app/config.py`.

### 2.4 · AUD-10 & AUD-11: Integridade de Dados em Updates
*   **Ação:** Definir `CAMPOS_EDITAVEIS` explícitos para usuários e trocar `exclude_none` por `exclude_unset` em equipamentos.
*   **Arquivos:** `app/auth/service.py`, `app/equipamentos/service.py`.

---

## ⚙️ Fase 3: Estrutura, Auditoria e Manutenibilidade (Severidade Média/Baixa)

Melhorias estruturais e prevenção de erros operacionais.

### 3.1 · AUD-15: Reestruturação do Template Base (Jinja2)
*   **Ação:** Isolar blocos de lógica `{% if %}` do Jinja2 para não quebrar a hierarquia de tags HTML, facilitando a manutenção e correção de erros de renderização.
*   **Arquivos:** `templates/base.html`.

### 3.2 · AUD-17: Proteção contra Auto-Exclusão de Admin
*   **Ação:** Validar no backend se o `usuario_id` sendo excluído é o mesmo do `usuario_logado` ou se é o último administrador do sistema.
*   **Arquivos:** `app/auth/service.py`.

### 3.3 · AUD-14: Reforço de Paginação
*   **Ação:** Garantir que o método `listar_panes` sempre aplique um `.limit(100)` caso nenhum filtro seja fornecido.
*   **Arquivos:** `app/panes/service.py`.

### 3.4 · AUD-18: Ajuste de Sessão JWT
*   **Ação:** Reduzir `jwt_expire_minutes` de 480 (8h) para 120 (2h).
*   **Arquivos:** `app/config.py`.

---

## 📈 Cronograma Estimado

| Fase | Esforço (h) | Responsável |
|------|-------------|-------------|
| **Fase 1** | 4h | Gemini CLI |
| **Fase 2** | 6h | Gemini CLI |
| **Fase 3** | 4h | Gemini CLI |
| **Testes Finais** | 2h | Auditoria Final |

---

**Nota Final:** Ao término de cada fase, um commit parcial será realizado e os testes de integração serão executados para garantir que nenhuma regressão foi introduzida.
