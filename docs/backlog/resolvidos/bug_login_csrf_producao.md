# Bug resolvido: Producao | Login | Falha de validacao CSRF

## Resumo

O login em producao podia falhar com HTTP 403 e a mensagem:

> Erro de seguranca (CSRF). Recarregue a pagina.

A protecao CSRF permaneceu ativa. A correcao ajustou a entrega do token ao frontend e impediu que HTML dinamico com token CSRF fosse reaproveitado por cache de navegador, proxy, CDN ou service worker.

## Motivo da falha, em linguagem simples

O CSRF funciona como uma conferencia em duas partes:

1. O backend coloca um token bruto no HTML da pagina, na meta tag `csrf-token`.
2. O backend tambem grava no navegador um cookie assinado correspondente.
3. No login, o frontend envia o token da meta tag no header `X-CSRF-Token`.
4. O backend aceita o POST somente se o header e o cookie combinarem.

O problema provavel em producao era a dessincronia entre essas duas partes. Como as paginas HTML tinham token CSRF embutido, elas nao podiam ser cacheadas. Sem `Cache-Control: no-store`, um cache intermediario ou local poderia entregar uma pagina `/login` antiga, contendo uma meta tag de CSRF que nao correspondia ao cookie assinado atual do navegador. Nesse caso, as credenciais estavam corretas, mas o backend rejeitava a requisicao antes da autenticacao, retornando 403.

As mensagens de `contentscript.js`, `EventEmitter` e `ObjectMultiplex` nao foram tratadas como causa da falha porque aparentam vir de extensoes do navegador e nao explicam a validacao CSRF do backend.

## Como foi resolvido

### Backend

Arquivo alterado: `app/shared/middleware/csrf.py`

- HTML dinamico agora recebe:
  - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
  - `Pragma: no-cache`
  - `Expires: 0`
- Isso impede cache de paginas que carregam `<meta name="csrf-token">`.
- O cookie CSRF passou a respeitar a mesma politica de cookie seguro usada pela autenticacao:
  - `APP_ENV=production`; ou
  - `FORCE_SECURE_COOKIES=true`.

### Frontend

Arquivo alterado: `app/web/static/js/login.js`

- O login agora valida explicitamente se a meta tag CSRF existe antes de enviar o POST.
- A chamada `fetch('/auth/login')` agora envia:
  - `X-CSRF-Token`;
  - `Content-Type: application/x-www-form-urlencoded;charset=UTF-8`;
  - `credentials: 'same-origin'`.
- Isso deixa explicito que o navegador deve enviar os cookies da mesma origem junto com o header CSRF.

### Service worker

Arquivo alterado: `app/web/static/sw.js`

- Removido cache de pagina HTML dinamica (`/m/`).
- O service worker agora usa cache apenas para assets estaticos.
- Requisicoes de paginas HTML e APIs vao direto para a rede, evitando reaproveitar HTML com token CSRF antigo.
- A versao do cache foi atualizada para `saa29-mobile-v2` e caches antigos sao removidos na ativacao.

### Testes

Arquivo adicionado: `tests/security/test_login_csrf.py`

- Verifica que `/login` retorna token CSRF, cookie CSRF e headers de nao-cache.
- Verifica login com credenciais validas usando o caminho real de CSRF, sobrescrevendo o bypass de teste.
- Confirma que `/auth/login` deixa de retornar 403 quando header e cookie CSRF estao sincronizados.

## Verificacoes executadas

Comandos executados:

```bash
venv/bin/pytest tests/security/test_login_csrf.py -q
venv/bin/pytest tests/security/test_csrf.py -q
```

Resultado:

- `tests/security/test_login_csrf.py`: 2 testes passaram.
- `tests/security/test_csrf.py`: 9 testes passaram.

Tambem foi feita verificacao em processo separado com `APP_ENV=production`:

- `GET /login` retornou HTTP 200.
- Header `X-CSRF-Token` presente.
- Header `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` presente.
- Cookie `fastapi-csrf-token` emitido com `Secure`.
- Cookie `fastapi-csrf-token` emitido com `SameSite=lax`.

## Criterios de aceite

- Login com credenciais validas envia token CSRF valido.
- `POST /auth/login` com header e cookie sincronizados e aceito.
- O backend continua bloqueando requisicoes sem CSRF valido.
- A mensagem de erro CSRF nao aparece no login valido.
- A protecao CSRF nao foi desabilitada nem flexibilizada.

## Observacao para deploy

Apos publicar a correcao, usuarios que tenham service worker/cache antigo podem precisar recarregar a pagina uma vez. A nova versao do service worker remove caches antigos ao ativar.
