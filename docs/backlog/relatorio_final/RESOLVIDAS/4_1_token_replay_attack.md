# Backlog Item 4.1: Falha de Detecção no Reuso de Refresh Token (Token Replay Attack)

## 1. Descrição do Problema
O fluxo anterior do endpoint `/auth/refresh` apenas barrava a renovação quando o token enviado estava revogado, sem executar nenhuma contra-medida ativa. O OAuth 2.0 Security Best Current Practice (RFC 6849 §10.4) exige que, se um refresh token já revogado for reutilizado, isso indica roubo do cookie e toda a árvore de refresh tokens ativos para o respectivo usuário deve ser invalidada em cascata para segurança.

## 2. Plano de Implementação
1. **Verificação no DB:** Modificar a lógica do endpoint `/auth/refresh` em `app/modules/auth/router.py`. Ao receber um JTI inexistente ou revogado, verificar se o JTI já consta como revogado no banco.
2. **Expurgo em Cascata (Revoke All):** Se o JTI recebido já estiver com `revogado_em` preenchido (ou seja, já foi consumido e rotacionado):
   - Atualizar todos os registros de `TokenRefresh` ativos (`revogado_em IS NULL`) do respectivo `usuario_id` para `revogado_em = agora`.
   - Logar aviso estruturado de segurança com severidade `WARNING` contendo os detalhes do usuário para fins de auditoria.
3. **Bloqueio:** Levantar erro HTTP `401 Unauthorized` forçando a re-autenticação.

## 3. Critérios de Aceitação
* A chamada ao endpoint `/auth/refresh` usando um refresh token antigo e já rotacionado resulta em erro `401 Unauthorized`.
* Todos os outros refresh tokens ativos emitidos anteriormente para o mesmo usuário são invalidados no banco (`revogado_em` recebe o timestamp da tentativa de ataque).
* Os testes em `tests/security/test_refresh_token.py` rodam e cobrem o fluxo de invalidação em cascata.
