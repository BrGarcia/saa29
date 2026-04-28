# Revisão Externa — SAA29 (Verificação V2)

Realizei uma verificação detalhada no código-fonte para confirmar a implementação das correções pontuadas no relatório `docs/relatorio/revisao_claude.md`.

A grande maioria das correções foi aplicada corretamente. Abaixo está o status detalhado da auditoria:

### ✅ Itens Implementados com Sucesso

**🔴 CRITICAL**
*   **C-01:** O bypass de CSRF em `app/shared/middleware/csrf.py` agora exige que o ambiente não seja de produção (`settings.app_env != "production"`).
*   **C-02:** A flag `secure` no cookie `saa29_token` (`app/modules/auth/router.py`) agora é ativada dinamicamente quando em produção.

**🟠 HIGH**
*   **H-01:** A diretiva `'unsafe-inline'` foi removida da CSP (`script-src`) no arquivo `app/bootstrap/main.py`.
*   **H-02:** A função `escapeHtml()` está sendo usada na atribuição de dados via `innerHTML` nos arquivos JS do frontend (ex: `panes_lista.js`).
*   **H-03 e H-04:** O endpoint de login agora retorna os valores `"hidden"` no payload de resposta para o `access_token` e o `refresh_token`, forçando o uso seguro através dos cookies, que incluem um novo cookie seguro `saa29_refresh_token`.
*   **H-05:** O valor de expiração `JWT_EXPIRE_MINUTES` foi ajustado para os corretos `15` minutos padrão (`app/bootstrap/config.py` e `.env`).
*   **H-06:** A dependência `_: EncarregadoOuAdmin` foi adicionada na rota `ajustar_inventario` (`app/modules/equipamentos/router.py`), garantindo o RBAC.

**🟡 MEDIUM**
*   **M-01:** O bloco `try/except` do refresh (`auth/router.py`) agora re-levanta (raise) `HTTPException` corretamente antes de capturar falhas genéricas.
*   **M-02:** O double-commit foi resolvido, priorizando-se o uso de `db.flush()` nos services para deixar o fechamento por conta da dependência (ex: no `auth/service.py`).
*   **M-03:** A função de segurança `_escape_like` agora também está sendo usada na busca de estoque para evitar injeção (`app/modules/equipamentos/service.py`).
*   **M-04:** A senha em modo de testes do mantenedor e encarregado foi atualizada para "123456", resolvendo o limite inferior de caracteres estipulado.
*   **M-05:** Uma rotina contínua (`limpar_tokens_expirados()`) foi adicionada no Lifespan em `app/bootstrap/main.py` para limpar ativamente a base.
*   **M-07:** O backup R2 assíncrono passou a usar o `asyncio.create_subprocess_exec` corretamente.
*   **M-08:** A nomenclatura das extensões na sintaxe de comprehension foi corrigida no `file_validators.py` para não sobrescrever a extensão do upload (`e for exts in ALLOWED_MIME_TYPES...`).

**🔵 LOW**
*   **L-01:** Status das aeronaves agora são baseados nativamente no enumerador `Enum(StatusAeronave)`.
*   **L-02:** Retido como comportamento intencional.
*   **L-03:** Uma nova função utilitária `dispose_engine()` no encapsulamento de DB está sendo invocada em `main.py`.
*   **L-04:** A busca de carga client-side (`apiFetch`) redundante para verificação de chaves foi suprimida antes do POST no `configuracoes.js`.
*   **L-05:** A assinatura das lógicas do arquivo `app/modules/vencimentos/service.py` agora tipam `dados` adequadamente utilizando seus schemas correspondentes.
*   **L-06:** O default da `database_url` foi devidamente modificado para `sqlite+aiosqlite:///./saa29_local.db`.

---

### ❌ Item Pendente (Não Implementado)

Encontrei apenas **um apontamento** que não foi integralmente solucionado:

*   **M-06 · Frontend Auth Check Apenas por `localStorage`**
    *   **Situação Atual:** No arquivo de rotas das páginas HTML (`app/web/pages/router.py`), as páginas que deveriam ser protegidas ou de acesso restrito (como `/configuracoes` e `/efetivo`) **não receberam** nenhuma validação de dependência de papel no lado do backend (como seria o uso de `Depends(EncarregadoOuAdmin)` ou a simples validação da sessão).
    *   **Impacto:** Qualquer ator com o conhecimento da URL pode ainda efetuar um GET e carregar a estrutura HTML estática das views, contornando a checagem client-side caso bloqueiem scripts, dependendo integralmente do bloqueio do acesso aos dados provenientes das rotas `/api`.
