# ADR-002: Autenticacao via JWT com Refresh Token

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O sistema exige autenticacao de usuarios com acesso restrito por perfil. O projeto precisa atender tanto requisicoes da API quanto navegacao no frontend, sem depender de sessoes server-side tradicionais.

Tambem ha necessidade de:

- expiracao curta para reduzir impacto de token comprometido;
- logout efetivo;
- rotacao de refresh token;
- rastreabilidade de revogacao.

## Decisao

Adotar **JWT (HS256)** para access token e **refresh token persistido em banco** para renovacao da sessao.

Implementacao atual:

- access token com expiracao curta definida por `JWT_EXPIRE_MINUTES`;
- refresh token com validade de 7 dias;
- `jti` para cada token;
- blacklist para logout e revogacao;
- refresh token rotacionado a cada uso;
- cookie HttpOnly para o access token em login.

## Alternativas Consideradas

| Alternativa | Pro | Contra |
|-------------|-----|--------|
| Session server-side | Revogacao simples | Exige armazenamento central e estado no servidor |
| JWT sem blacklist | Simples | Logout real nao fica garantido |
| OAuth externo | Delegacao de identidade | Complexidade maior que a necessidade atual |
| JWT + refresh token (escolhido) | Curto prazo para access token e renovacao controlada | Requer persistencia auxiliar para revogacao e rotacao |

## Consequencias

**Positivas:**

- logout invalida a sessao de forma persistida;
- refresh token permite renovar a sessao sem expor senhas novamente;
- o frontend pode trabalhar com cookie HttpOnly e resposta JSON ao mesmo tempo;
- a blacklist sobrevive a reinicios da aplicacao;
- a separacao entre access e refresh reduz o tempo de exposicao do token principal.

**Negativas / Trade-offs:**

- o sistema passa a manter duas estruturas persistidas para autenticacao;
- rotacao de refresh token aumenta a complexidade do fluxo;
- a seguranca depende de `APP_SECRET_KEY` forte e configurada corretamente;
- `TokenRefresh.usuario_id` e armazenado como referencia logica, sem FK declarada no ORM.

## Referencias

- [`app/modules/auth/security.py`](../../../app/modules/auth/security.py)
- [`app/modules/auth/router.py`](../../../app/modules/auth/router.py)
- [`app/modules/auth/models.py`](../../../app/modules/auth/models.py)
- [`docs/architecture/03_MODEL_DB.md`](../03_MODEL_DB.md)
- [`docs/SECURITY.md`](../../SECURITY.md)
