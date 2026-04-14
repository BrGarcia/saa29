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
| Senhas | Hashing bcrypt via `passlib` |
| Tokens | JWT assinado com HS256 + expiração |
| Validação | Pydantic v2 com tipagem estrita |
| Upload | Validação de MIME type + tamanho máximo |
| Credenciais | Variáveis de ambiente via `.env` (nunca no código) |
| SQL Injection | Prevenido pelo ORM SQLAlchemy (parameterized queries) |

---

## Dependências com Alertas de Segurança

Execute periodicamente para verificar vulnerabilidades nas dependências:

```bash
pip audit
# ou
safety check -r requirements.txt
```
