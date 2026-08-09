# Política de Segurança (SECURITY.md)

## Versões Suportadas

| Versão | Suporte |
|--------|---------|
| 1.x.x  | ✅ Suporte ativo |
| 0.x.x  | ⚠️ Apenas críticos |

---

## Reportar uma Vulnerabilidade

**Não abra uma Issue pública para vulnerabilidades de segurança.**

### Como reportar

1. Envie um e-mail para o responsável técnico do projeto descrevendo:
   - Tipo de vulnerabilidade (ex: injeção SQL, XSS, exposição de credencial)
   - Passos para reprodução
   - Impacto potencial
   - Sugestão de correção (opcional)

2. Você receberá uma resposta em até **72 horas** com o status da análise.

3. Após confirmação e correção, a vulnerabilidade será divulgada responsavelmente.

---

## Escopo de Segurança

### Em escopo (reportar)
- Autenticação e autorização inadequadas
- Injeção SQL ou NoSQL
- Exposição de dados sensíveis (senhas, tokens)
- Upload irrestrito de arquivos maliciosos
- CSRF, XSS, clickjacking
- Configurações inseguras expostas

### Fora de escopo (não reportar)
- Ataques de força bruta sem bypass de rate limiting
- Ataques dependentes de acesso físico ao servidor
- Vulnerabilidades em dependências sem CVE ativo

---

## Boas Práticas Adotadas no Projeto

| Prática | Implementação |
|---------|--------------|
| Senhas | Hashing bcrypt via `passlib` (Min. 6 caracteres para testes) |
| Tokens (JWT) | Assinado com HS256 + 15 min de expiração |
| Refresh Token | Persistido em banco e entregue via Cookie HttpOnly / Secure / SameSite=Lax |
| CSP | `script-src 'self'` (Sem `'unsafe-inline'`) |
| XSS | Sanitização via `escapeHtml()` no JS e Jinja2 autoescaping |
| CSRF | Middleware com token em cookie e header. Bypass bloqueado em produção. |
| SQL Injection | Parameterized queries (SQLAlchemy) + `_escape_like` em filtros textuais |
| Validação | Pydantic v2 com tipagem estrita e validação de MIME/Tamanho de arquivos |
| RBAC (Backend) | Validação de `Depends(require_role)` em todos os endpoints de API e rotas HTML |
| Credenciais | Variáveis de ambiente via `.env` (nunca no código) |
| Cookies | Flags `secure` e `httponly` dinâmicas conforme ambiente (`settings.app_env`) |
| Manutenção | Rotina automatizada no lifespan para limpeza de tokens expirados |

---

## Arquitetura Zero Trust (Frontend)

Diferente de SPAs tradicionais que protegem rotas apenas no client-side, o SAA29 implementa proteção de interface no backend:

1. **Validação de Sessão em Rotas HTML:** Todas as rotas em `app/web/pages/router.py` exigem autenticação via `Depends(get_current_user)`.
2. **RBAC Síncrono:** Páginas administrativas (Ex: `/configuracoes`, `/efetivo`) validam o papel do usuário no momento da requisição do template. Se o usuário não possuir o privilégio, o servidor nega o HTML, impedindo a visualização da estrutura da página mesmo com scripts desativados.
3. **Cookies Seguros:** O `access_token` e o `refresh_token` são trafegados via cookies protegidos, minimizando o risco de roubo de tokens via XSS em comparação ao `localStorage`.

---

## Dependências com Alertas de Segurança

Execute periodicamente para verificar vulnerabilidades nas dependências:

```bash
pip audit
# ou
safety check -r requirements.txt
```
