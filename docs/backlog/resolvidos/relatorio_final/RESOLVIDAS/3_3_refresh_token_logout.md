# Backlog Item 3.3: Reuso e vazamento de tokens de sessão após Logout

## 1. Descrição do Problema
O endpoint de logout (`/auth/logout`) expurgava o token de acesso (`saa29_token`), mas mantinha o refresh token ativo no banco e o cookie do cliente correspondente inalterado. Isso permitia que a sessão fosse renovada usando `/auth/refresh` mesmo após o operador solicitar a saída do sistema.

## 2. Plano de Implementação
1. **Invalidação de cookies no client:** Garantir que o endpoint de logout adicione instruções de deleção para os cookies `saa29_token` e `saa29_refresh_token` (com o respectivo `path="/auth/refresh"`).
2. **Revogação lógica do Refresh Token no banco:**
   - Obter o refresh token do cookie `saa29_refresh_token` durante a requisição de logout.
   - Decodificar o token para obter o JTI (`jwt_id`).
   - Consultar o registro correspondente na tabela `TokenRefresh` e preencher `revogado_em = datetime.now(timezone.utc)`.
3. **Commit da Sessão:** Persistir a revogação no banco para assegurar a persistência.

## 3. Critérios de Aceitação
* Uma requisição para `/auth/logout` apaga ambos os cookies do navegador.
* O refresh token correspondente ao JTI da sessão que realizou logout é marcado como revogado no banco de dados.
* Uma chamada subsequente a `/auth/refresh` com o token revogado deve falhar com status `401 Unauthorized`.
