# Pane & Melhoria: Dessincronia de CSRF no Login e Calibração de Segurança (Account Lockout)

## 1. Resumo do Problema

Durante o fluxo de login, ao errar a senha pela primeira vez, qualquer tentativa subsequente imediata falha com o alerta/toast:

> **"Erro de segurança (CSRF). Recarregue a página."**

Isso força o usuário a atualizar a página (F5) para tentar logar novamente e cria a falsa percepção de que a conta foi bloqueada logo na primeira tentativa incorreta.

---

## 2. Causa Raiz Técnica

### 2.1. Dessincronização do Token CSRF (Causa Principal da Pane)

O sistema adota o padrão de proteção CSRF com par de tokens (Cookie assinado + Header `X-CSRF-Token` com token bruto):

1. **Carregamento da página:** Ao acessar `/login`, o servidor renderiza a meta tag `<meta name="csrf-token" content="...">` e define o cookie assinado `fastapi-csrf-token`.
2. **1ª tentativa (senha incorreta):**
   - O JavaScript ([`app/web/static/js/login.js`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/web/static/js/login.js)) envia o formulário via `POST /auth/login` com o cabeçalho `X-CSRF-Token`.
   - O backend valida o CSRF (sucesso), checa a senha e retorna `HTTP 401 Unauthorized` ("Credenciais inválidas.").
   - O middleware de segurança ([`app/shared/middleware/csrf.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/shared/middleware/csrf.py)), ao processar qualquer resposta de mutação (POST), **rotaciona o token de segurança**:
     - Atualiza o cookie `fastapi-csrf-token` no navegador com um novo valor assinado.
     - Envia o novo token bruto no cabeçalho de resposta `X-CSRF-Token`.
3. **2ª tentativa (sem recarregar a página):**
   - O script `login.js` **não atualiza a tag `<meta name="csrf-token">`** com o token recebido no header da resposta de erro anterior.
   - Na nova tentativa, `login.js` envia o **token antigo** presente no HTML.
   - O backend compara o token antigo do header com o novo cookie já atualizado no navegador.
   - Havendo divergência, o `CSRFMiddleware` rejeita a requisição com `HTTP 403 Forbidden` e exibe a mensagem de erro de CSRF.

---

### 2.2. Rigidez nas Políticas de Bloqueio (*Account Lockout* e *Rate Limit*)

Além da falha de CSRF, os parâmetros de bloqueio de segurança encontram-se fixados diretamente no código-fonte (*hardcoded*):

1. **Account Lockout no Banco de Dados** ([`app/modules/auth/service.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/modules/auth/service.py#L26-L27)):
   - `_LOCKOUT_MAX_TENTATIVAS = 5`
   - `_LOCKOUT_DURACAO_MINUTOS = 15`
2. **Rate Limiting da Rota** ([`app/modules/auth/router.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/modules/auth/router.py#L44)):
   - `@limiter.limit("5/minute")`

Esses limites podem ser calibrados e tornados configuráveis via `.env` para facilitar o fluxo de trabalho da equipe.

---

## 3. Sugestão de Correções

### Correção 1: Sincronização Dinâmica do CSRF no `login.js` (Frontend)

Atualizar o script de login para extrair o `X-CSRF-Token` retornado pelo servidor em qualquer resposta (seja sucesso, erro 401 ou erro 429) e sincronizar a tag `<meta name="csrf-token">`, exatamente como já é feito no restante da aplicação ([`app.js`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/web/static/js/app.js)).

**Exemplo de alteração em [`app/web/static/js/login.js`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/web/static/js/login.js):**

```javascript
// Após a execução do fetch:
const response = await fetch('/auth/login', { ... });

// Sincroniza o novo token CSRF emitido pelo middleware (seja 200, 401 ou outro status)
const novoCsrfToken = response.headers.get('X-CSRF-Token');
if (novoCsrfToken && csrfMeta) {
    csrfMeta.setAttribute('content', novoCsrfToken);
}
```

---

### Correção 2: Parametrização do Lockout e Rate Limit via `.env` (Backend)

Tornar as variáveis de tentativas e tempos configuráveis no arquivo de configurações ([`app/bootstrap/config.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/bootstrap/config.py)):

1. **Adicionar campos na classe `Settings`:**
   ```python
   # app/bootstrap/config.py
   auth_lockout_max_tentativas: int = 5
   auth_lockout_duracao_minutos: int = 15
   auth_login_rate_limit: str = "10/minute"
   ```

2. **Utilizar as variáveis no serviço de autenticação:**
   - Em [`app/modules/auth/service.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/modules/auth/service.py), consumir `get_settings().auth_lockout_max_tentativas` e `get_settings().auth_lockout_duracao_minutos`.

3. **Utilizar o rate limit configurável no router:**
   - Em [`app/modules/auth/router.py`](file:///Users/bruno/Documents/Gemini/10_PROJETOS/SAA29/app/modules/auth/router.py), referenciar a taxa definida nas configurações.

---

### Correção 3: Criação de Teste Automatizado de Regressão

Adicionar um teste em `tests/security/test_login_csrf.py` validando o cenário:
1. `GET /login` -> obtém token inicial.
2. `POST /auth/login` com senha incorreta -> recebe 401 + novo header `X-CSRF-Token`.
3. `POST /auth/login` imediato usando o novo token -> recebe 401 (Credenciais inválidas), **nunca 403 (CSRF Error)**.

---

## 4. Critérios de Aceite

- [ ] Usuário erra a senha na primeira tentativa e recebe "Login ou senha incorretos."
- [ ] Usuário corrige a senha na segunda tentativa (sem recarregar a página) e consegue autenticar normalmente.
- [ ] Usuário erra a senha múltiplas vezes consecutivas e continua recebendo "Login ou senha incorretos" até o limite de lockout configurado.
- [ ] Apenas ao atingir o limite configurado (ex: 5 falhas), a conta é temporariamente desabilitada pelo tempo estipulado.
- [ ] Parâmetros de tentativas e minutos podem ser ajustados via variáveis de ambiente (`.env`).
