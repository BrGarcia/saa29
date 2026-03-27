# ADR-002: Autenticação via JWT (Stateless)

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O sistema requer autenticação de usuários (RF-01, RF-02) com acesso exclusivo após login válido. O sistema é acessado por múltiplos clientes (navegadores) em rede interna.

## Decisão

Autenticação **stateless via JWT (JSON Web Token)** assinado com algoritmo **HS256**, armazenado no cliente (header `Authorization: Bearer <token>`).

- Biblioteca: `python-jose[cryptography]`
- Senha: hash `bcrypt` via `passlib`
- Expiração padrão: **8 horas** (configurável via `JWT_EXPIRE_MINUTES`)

## Alternativas Consideradas

| Alternativa | Prós | Contras |
|-------------|------|---------|
| Session-based (cookies) | Revogação imediata | Requer armazenamento server-side (Redis/DB) |
| JWT stateless (escolhido) | Sem estado no servidor, escalável | Revogação exige blacklist |
| OAuth2 externo | Delegação de identidade | Complexidade desnecessária para MVP interno |

## Consequências

**Positivas:**
- Sem necessidade de armazenamento de sessão no servidor
- Tokens carregam o payload do usuário (username, funcao)
- Compatível com qualquer cliente (browser, mobile, API)

**Negativas / Trade-offs:**
- Logout real requer implementação de blacklist (deferida para v2.0)
- Token comprometido é válido até expirar (mitigado pela expiração curta)
- `APP_SECRET_KEY` deve ser longa, aleatória e **nunca versionada**

## Referências
- [RFC 7519 – JSON Web Token](https://tools.ietf.org/html/rfc7519)
- [`app/auth/security.py`](../../../app/auth/security.py)
- [SECURITY.md](../../../SECURITY.md)
