# Backlog Item 3.2: Bypass de Proteção CSRF fora de ambiente de produção

## 1. Descrição do Problema
O middleware de proteção contra CSRF permitia desativar a verificação de mutações (POST, PUT, PATCH, DELETE) se o cabeçalho `X-Skip-CSRF: true` estivesse presente em qualquer ambiente com `APP_ENV != "production"`. Isso expunha ambientes de homologação e testes de laboratório a ataques de requisição cross-origin maliciosos.

## 2. Plano de Implementação
1. **Restringir bypass de CSRF:** Modificar a lógica do middleware em `app/shared/middleware/csrf.py` para limitar a condição `skip_csrf` unicamente a `settings.app_env == "testing"`.
2. **Exigir cabeçalho específico de teste:** Adicionar a verificação do cabeçalho `X-Skip-CSRF: true` apenas em escopo de teste automatizado e nunca em homologação/qa/dev.
3. **Revisar testes integrados:** Assegurar que os testes de API em `tests/conftest.py` injetem o header de bypass apenas em ambiente isolado de teste.

## 3. Critérios de Aceitação
* Chamadas mutadoras (POST/PUT/PATCH/DELETE) realizadas em ambientes de staging/QA/dev sem o cabeçalho correto de CSRF devem falhar com status `403 Forbidden`.
* O bypass via header `X-Skip-CSRF` só é aceito se o `APP_ENV` for explicitamente `"testing"`.
* A suíte de testes de CSRF (`tests/security/test_csrf.py`) roda e passa em sua totalidade.
