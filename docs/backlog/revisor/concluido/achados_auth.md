# Achados de Revisão — Módulo `auth`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 03/08/2026
> 19/24 achados corrigidos, 1 parcial, 4 não corrigidos por exigirem decisão de produto/desenvolvedor
> (ver `## Perguntas para o desenvolvedor` ao final). Commit `872690b`. Suite completa: 334 testes, 0
> falhas. Status por item marcado inline em cada achado abaixo (campo `**Status:**`).

---

### [BUG-01] Refresh token nunca é revogado no logout

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/auth/router.py:298-311`
- **Eixo:** Segurança
- **Problema:** o cookie `saa29_refresh_token` é emitido com `path="/auth/refresh"` (`router.py:92,243`). Um POST para `/auth/logout` não está sob esse path, então o browser nunca envia esse cookie na requisição de logout. `request.cookies.get("saa29_refresh_token")` em `router.py:298` é, portanto, sempre `None` em uso real via navegador, e todo o bloco de revogação do refresh token (`router.py:298-311`) nunca executa. Confirmado do lado do cliente: `app/web/static/js/app.js:118-141` (`clearAuth()`) usa `fetch("/auth/logout", { credentials: 'same-origin' })`, sem enviar cookies fora do path do request.
- **Consequência:** um refresh token exfiltrado (XSS, log, proxy) continua válido por até 7 dias após o usuário fazer logout, e pode ser rotacionado indefinidamente enquanto não expira — o "logout" só invalida o access token de 15 min.
- **Correção proposta:** ou (a) emitir o cookie `saa29_refresh_token` com `path="/"` para que acompanhe o POST de logout, ou (b) fazer o endpoint `/auth/logout` também ler o refresh token do body/header explicitamente enviado pelo cliente, e ajustar `app.js` para enviá-lo.
- **Risco de regressão:** MÉDIO — mudar o `path` do cookie afeta todos os fluxos que o setam/leem (`login`, `refresh`).
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. Opção (a): cookie `saa29_refresh_token` passou a `path="/"` em login, refresh e logout. Teste de regressão em `tests/security/test_auth_achados_revisor.py`.

---

### [BUG-02] Troca/reset de senha não invalida sessões nem refresh tokens ativos

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/auth/service.py:183-211`
- **Eixo:** Segurança
- **Problema:** `alterar_senha` e `admin_resetar_senha` apenas sobrescrevem `usuario.senha_hash`. Nenhuma das duas funções revoga refresh tokens existentes (`TokenRefresh`) nem adiciona o `jti` do access token atual à blacklist.
- **Consequência:** o cenário de resposta a incidente mais comum — "a conta X foi comprometida, resete a senha" — não encerra a sessão do atacante. O access token continua válido por até 15 min e, pior, o refresh token continua válido e renovável por até 7 dias, mesmo após o admin já ter trocado a senha.
- **Correção proposta:** ao final de `alterar_senha` e `admin_resetar_senha`, revogar (via `UPDATE ... SET revogado_em = now()`) todos os `TokenRefresh` ativos do `usuario_id`. Access tokens em voo continuam expirando naturalmente em até 15 min (aceitável, mas registrar como trade-off).
- **Risco de regressão:** BAIXO — o próprio usuário que troca a senha esperaria ter que logar de novo nos outros dispositivos.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. `alterar_senha`/`admin_resetar_senha` revogam todos os `TokenRefresh` ativos do usuário via `_revogar_refresh_tokens_ativos`. Testado em `tests/security/test_auth_achados_revisor.py`.

---

### [BUG-03] Proteção do "último administrador" (AUD-17) contornável via `atualizar_usuario`

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/auth/service.py:157-180`
- **Eixo:** Segurança / Contrato
- **Problema:** `excluir_usuario` (`service.py:229-238`) verifica se o alvo é o último `ADMINISTRADOR` ativo antes de desativar. `atualizar_usuario` inclui `funcao` em `CAMPOS_EDITAVEIS` (`service.py:169`) e faz `setattr` sem nenhuma checagem equivalente.
- **Consequência:** `PUT /auth/usuarios/{usuario_id}` com `{"funcao": "MANTENEDOR"}` no último administrador do sistema (inclusive nele mesmo) remove o único admin sem passar pela trava do AUD-17. Não há como reverter pela UI — exige acesso direto ao banco.
- **Correção proposta:** replicar em `atualizar_usuario` a mesma checagem de "não é o último admin ativo" quando `campo == "funcao"` e o valor antigo é `ADMINISTRADOR` e o novo não é.
- **Risco de regressão:** BAIXO — a checagem só bloqueia o caso degenerado (zero admins), não altera o fluxo normal.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. `atualizar_usuario` replica a proteção do AUD-17 via `UPDATE` atômico condicional (mesma correção do RISCO-07). Testado.

---

### [BUG-04] `garantir_usuarios_essenciais` quebra a invariante de username case-insensitive

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/auth/service.py:274,318`
- **Eixo:** Banco / Contrato
- **Problema:** `criar_usuario` normaliza sempre para minúsculas antes de gravar (`service.py:101`, `username_lower = dados.username.lower()`), e toda busca de login/autorização usa `func.lower(Usuario.username)` (`app/shared/core/helpers.py:21-27`). Porém `garantir_usuarios_essenciais` busca o admin e os usuários de teste com `Usuario.username == admin_user` / `== user` (`service.py:274,318`) — comparação exata, sem `.lower()`. O índice único da coluna (`migrations/versions/20260418_2233_..._initial_schema_consolidated.py:91`) é sobre o valor cru, sem `COLLATE NOCASE`.
- **Consequência:** se `DEFAULT_ADMIN_USER` no `.env` estiver com qualquer maiúscula (ex.: `Admin`), a checagem `if not admin` nunca encontra o registro existente (criado em minúsculas por um seed anterior ou por `criar_usuario`) e insere um **segundo** usuário com username diferente por case, mas equivalente sob a regra de negócio. A partir daí, `buscar_usuario_por_username` (usado em todo login e em `get_current_user`) executa `func.lower(username) == "admin"` e encontra dois registros — `result.scalar_one_or_none()` em `helpers.py:27` levanta `MultipleResultsFound`, e **todo login e toda requisição autenticada do sistema inteiro passam a retornar 500** até o duplicado ser removido manualmente do banco.
- **Correção proposta:** normalizar para minúsculas antes de todas as buscas/inserções em `garantir_usuarios_essenciais` (`admin_user.lower()` e os literais da lista `usuarios_teste`), ou — melhor — impor a normalização na própria migration via `COLLATE NOCASE` / constraint, para que nenhum caminho futuro possa reintroduzir o problema.
- **Risco de regressão:** BAIXO — normalizar é estritamente mais restritivo, não quebra nenhum fluxo existente.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. `garantir_usuarios_essenciais` normaliza para lowercase antes de toda busca/insert. Testado.

---

### [RISCO-05] bcrypt síncrono bloqueando o event loop em toda autenticação

- **Classificação:** RISCO
- **Severidade:** ALTA
- **Arquivo:** `app/modules/auth/security.py:31-38`
- **Eixo:** Concorrência
- **Problema:** `hash_senha`/`verificar_senha` (via `passlib.CryptContext(schemes=["bcrypt"])`) são operações CPU-bound síncronas, chamadas diretamente (sem `run_in_executor`/threadpool) dentro de handlers `async def` — `service.py:52` (dummy hash em toda tentativa de login com usuário inexistente/inativo), `service.py:75` (verificação de senha real), `service.py:113` (criação de usuário), `service.py:194,210` (troca/reset de senha). O próprio comentário em `service.py:28-34` documenta a medição: **~227 ms por chamada**.
- **Consequência:** cada requisição de login (bem-sucedida ou não — o `_DUMMY_HASH` garante que o custo é pago sempre) bloqueia o único event loop do worker asyncio por ~227 ms, travando **todas as outras requisições em andamento** no mesmo processo (incluindo endpoints de outros módulos). Sob concorrência moderada em `/auth/login` (rate limit é só 5/min por IP, não global), isso vira um vetor de negação de serviço trivial de todo o sistema, não só do auth.
- **Correção proposta:** mover as chamadas de hash/verificação para um threadpool (`asyncio.to_thread` ou `run_in_executor`), mantendo a API `async` dos services que as chamam.
- **Risco de regressão:** MÉDIO — muda o modelo de execução de um caminho crítico (login); precisa validar que o dummy-hash de equalização de tempo (`_DUMMY_HASH`) continua cumprindo seu papel de mitigação de timing-oracle após a mudança.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. Todas as chamadas de `hash_senha`/`verificar_senha` em `service.py` (incluindo o `_DUMMY_HASH`) passaram por `asyncio.to_thread`. Suite completa (334 testes) permanece verde.

---

### [RISCO-06] Fluxo de refresh token não é exercitado por nenhum cliente real

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/web/static/js/app.js:151-200` (função `apiFetch`), `app/modules/auth/router.py:104-262`
- **Eixo:** Arquitetura / Contrato
- **Problema:** não há nenhuma chamada a `/auth/refresh` em `app/web/`. `apiFetch` trata 401 chamando `clearAuth()` diretamente (`app.js:182-184`), sem tentar renovar via refresh token antes.
- **Consequência:** toda a máquina de rotação de refresh token, detecção de reuso e revogação de família (o trecho mais complexo e mais testado do módulo) é, na prática, código morto do ponto de vista do usuário do frontend web — a sessão expira a cada 15 min e força novo login. Se essa é uma lacuna de integração e não uma decisão deliberada, é um item de UX/negócio relevante; se é deliberada, o código de refresh deveria ao menos estar marcado como "reservado para clientes de API".
- **Correção proposta:** decidir explicitamente: (a) integrar `apiFetch` para tentar `/auth/refresh` antes de deslogar no 401, ou (b) documentar que o refresh token é só para consumidores de API/mobile e simplificar a expectativa sobre a sessão web.
- **Risco de regressão:** BAIXO (é decisão de produto, não uma correção de bug isolado).
- **Precisa de teste antes?** NÃO (é decisão a tomar antes de qualquer código)
- **Status:** 🚫 NÃO CORRIGIDO — decisão de produto pendente (ver "Perguntas para o desenvolvedor" ao final deste documento). Nenhuma ação de código tomada nesta sessão de correção.

---

### [RISCO-07] TOCTOU na contagem do último administrador

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/auth/service.py:229-238`
- **Eixo:** Concorrência
- **Problema:** a contagem de admins ativos (`SELECT count(...)`) e o `UPDATE ativo=False` subsequente não estão numa transação com isolamento que impeça duas requisições concorrentes de lerem a mesma contagem antes de qualquer uma commitar.
- **Consequência:** duas requisições simultâneas para desativar os dois últimos administradores restantes podem ambas passar na checagem `admins_ativos <= 1` (cada uma vê `2` antes do commit da outra), resultando em zero administradores ativos — mesmo efeito final do BUG-03, mas por corrida em vez de rota alternativa.
- **Correção proposta:** usar `SELECT ... FOR UPDATE` (se o backend suportar) ou reformular como um `UPDATE` condicional atômico que só desative se a contagem de admins ativos, calculada na mesma query, for maior que 1.
- **Risco de regressão:** MÉDIO — mexe no mecanismo de proteção crítico; precisa de teste de concorrência dedicado.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. `excluir_usuario` reescrito como `UPDATE` atômico condicional (contagem + update na mesma instrução), fechando a janela de TOCTOU. Testado (cenário determinístico via `_isolar_administradores_ativos`; concorrência real de duas requisições simultâneas não foi simulada — ver nota abaixo).

---

### [RISCO-08] Rotação de refresh token sem lock — corrida entre requisições concorrentes

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/auth/router.py:145-186,222`
- **Eixo:** Concorrência
- **Problema:** o fluxo de `/auth/refresh` lê o `TokenRefresh` armazenado, decide se é reuso, e move `revogado_em` — mas duas requisições simultâneas com o mesmo refresh token (duas abas, retry de rede, `StrictMode` do React) leem o mesmo estado "ainda não revogado" antes de qualquer commit.
- **Consequência:** ou os dois pedidos emitem tokens novos e válidos a partir do mesmo pai (quebra a garantia de rotação single-use), ou — dependendo do timing — o segundo interpreta a revogação feita pelo primeiro como reuso malicioso e revoga a família inteira, deslogando o usuário de todos os dispositivos sem motivo real.
- **Correção proposta:** usar um `UPDATE ... WHERE jti = ? AND revogado_em IS NULL RETURNING *` atômico para decidir "ganhou a corrida" antes de prosseguir, em vez de `SELECT` seguido de `UPDATE` separado.
- **Risco de regressão:** MÉDIO — é o coração da lógica de segurança de refresh; exige teste de concorrência.
- **Precisa de teste antes?** SIM
- **Status:** ✅ CORRIGIDO — commit `872690b`. Claim atômico via `UPDATE ... WHERE jti = ? AND revogado_em IS NULL` antes de rotacionar; perdedor da corrida cai no caminho de revogação de família. Coberto pelos testes existentes de replay (`tests/security/test_refresh_token*.py`); concorrência real de duas requisições simultâneas não foi simulada.

---

### [RISCO-09] `except Exception` genérico no `/refresh` engole erros de infraestrutura sem log

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/auth/router.py:254-261`
- **Eixo:** Tratamento de erros
- **Problema:** o bloco `except Exception as e:` no fim de `refresh_access_token` converte qualquer exceção — incluindo falha de conexão com o banco, erro de driver, bug de programação — em `HTTPException(401, "Refresh token inválido")`. A variável `e` é capturada e nunca usada (nem logada).
- **Consequência:** uma indisponibilidade momentânea do banco durante o `/auth/refresh` se manifesta ao usuário como "sessão inválida", indistinguível de um ataque ou token expirado — e não deixa nenhum rastro nos logs para diagnóstico.
- **Correção proposta:** logar a exceção (`logger.exception(...)`) antes de converter para 401, e considerar não capturar exceções de infraestrutura (ex. erros de banco) no mesmo bloco que trata falhas de token — deixá-las propagar para o handler genérico de 500 (`app/shared/core/exceptions.py:91-97`).
- **Risco de regressão:** BAIXO — é aditivo (log) e mudança de escopo do `except`.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `logger.exception("Erro inesperado em /auth/refresh")` adicionado antes do 401. Escopo do `except` mantido (não separado de erros de infraestrutura, ver observação abaixo).

---

### [RISCO-10] `except Exception: pass` duplo no logout mascara falha de revogação

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/auth/router.py:294-295,310-311`
- **Eixo:** Tratamento de erros
- **Problema:** os dois blocos try/except do endpoint `/auth/logout` (inserção na blacklist do access token, e revogação do refresh token) engolem qualquer exceção silenciosamente (`except Exception: pass`), sem log.
- **Consequência:** se a inserção na `TokenBlacklist` falhar (ex.: erro transitório de banco), o endpoint ainda responde `204 No Content` como se o logout tivesse funcionado — mas o access token do usuário continua válido e utilizável por outra parte (ex.: um dispositivo diferente com o mesmo token vazado) até expirar naturalmente em até 15 min. Não há sinal nenhum de que isso aconteceu.
- **Correção proposta:** ao menos logar a exceção em ambos os blocos (`logger.warning`/`logger.exception`) para permitir diagnóstico; avaliar se a falha na blacklist deveria propagar como 500 em vez de 204 silencioso.
- **Risco de regressão:** BAIXO — logging é aditivo.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `logger.warning(...)` adicionado nos dois blocos (blacklist e revogação de refresh), com `exc_info=True`. Avaliação de propagar como 500 não foi feita (mantido 204 silencioso após log).

---

### [RISCO-11] Cookies de sessão sem `Secure` fora de `app_env == "production"`

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/auth/router.py:76-84,227-235`
- **Eixo:** Segurança
- **Problema:** `secure = settings.app_env == "production"` é a única condição que decide o atributo `Secure` dos cookies `saa29_token` e `saa29_refresh_token`. Qualquer ambiente que não seja literalmente `"production"` (ex.: `staging`, `homolog`) — mesmo que sirva a aplicação atrás de HTTPS — recebe cookies de sessão sem `Secure`.
- **Consequência:** em qualquer ambiente intermediário servido por HTTPS mas com `APP_ENV != production`, os cookies de autenticação podem ser enviados também por HTTP em caso de downgrade/MITM, pois o navegador não os marca como HTTPS-only.
- **Correção proposta:** decidir `secure` a partir de uma flag explícita (ex. `settings.force_secure_cookies` ou detectar o esquema real da requisição) em vez de comparar string de ambiente; ou documentar que qualquer ambiente não-dev **deve** usar `APP_ENV=production`.
- **Risco de regressão:** BAIXO — tende a ser estritamente mais seguro.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. Novo `settings.force_secure_cookies` (env `FORCE_SECURE_COOKIES`); `secure = app_env == "production" or force_secure_cookies` em login e refresh.

---

### [DÚVIDA-12] Corpo de login/refresh retorna a string literal `"hidden"` no lugar do token

- **Classificação:** DÚVIDA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/router.py:96-101,247-252`
- **Eixo:** Contrato
- **Problema:** `schemas.Token.access_token`/`refresh_token` são preenchidos com a string literal `"hidden"` em vez do valor real — o token de fato só viaja pelo cookie HttpOnly. Ao mesmo tempo, `oauth2_scheme`/`get_token_from_request` (`app/bootstrap/dependencies.py:17,43-57`) aceitam o token via header `Authorization: Bearer`, e o botão *Authorize* do Swagger/OpenAPI depende do valor real vir no corpo de `/auth/login`.
- **Consequência:** se for intencional ("nunca expor token fora do cookie HttpOnly, por design"), o `response_model` está mentindo sobre o conteúdo do campo e a integração via Swagger/header fica quebrada para qualquer cliente não-cookie. Se não for intencional, é uma regressão que impede uso via API/mobile.
- **Correção proposta:** confirmar com o desenvolvedor a intenção; se confirmado "cookie-only", simplificar o schema (remover os campos ou documentá-los como sempre opacos) e considerar remover o suporte a header Authorization desse fluxo para não sugerir uma capacidade que não existe.
- **Risco de regressão:** BAIXO (é decisão de contrato, não bug).
- **Precisa de teste antes?** NÃO
- **Status:** 🚫 NÃO CORRIGIDO — decisão de produto pendente (ver "Perguntas para o desenvolvedor"). Nenhuma ação de código tomada nesta sessão de correção.

---

### [MELHORIA-13] `max_age` do cookie de access token hardcoded, duplicando a fonte de verdade

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/router.py:82,233`
- **Eixo:** Arquitetura
- **Problema:** `max_age=15*60` está hardcoded nos dois `set_cookie` do access token, enquanto a expiração real do JWT vem de `settings.jwt_expire_minutes` (`security.py:56`). É exatamente o problema que `refresh_token_expire_days` foi introduzido para eliminar no cookie de refresh (comentário em `app/bootstrap/config/__init__.py:51-59`), mas não foi replicado aqui.
- **Consequência:** se `jwt_expire_minutes` for alterado no futuro, o cookie do access token expira num tempo diferente do JWT que ele carrega, criando uma janela onde o cookie existe mas o token dentro dele já expirou (ou vice-versa).
- **Correção proposta:** usar `settings.jwt_expire_minutes * 60` como `max_age`, igual ao padrão já aplicado ao refresh token.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `max_age` dos dois `set_cookie` do access token passou a `settings.jwt_expire_minutes * 60`.

---

### [MELHORIA-14] `TokenRefresh.usuario_id` sem `ForeignKey`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/models.py:197-201`
- **Eixo:** Banco
- **Problema:** a coluna `usuario_id` é indexada mas não declara `ForeignKey("usuarios.id")`, nem em `models.py` nem na migration original (`migrations/versions/20260419_2300_a1b2c3d4e5f6_add_token_refresh_table.py:28`).
- **Consequência:** nada impede um `TokenRefresh` órfão (usuário deletado sem cascata correspondente) e SQLite não vai recusar a inserção de um `usuario_id` inexistente, mesmo com `foreign_keys=ON` no PRAGMA (`app/bootstrap/database.py`), porque a constraint simplesmente não existe.
- **Correção proposta:** adicionar `ForeignKey("usuarios.id", ondelete=...)` e migration correspondente — decidir a política de cascade (provavelmente `CASCADE`, já que exclusão de usuário é lógica/soft-delete, então na prática isso só importa se um dia existir hard-delete).
- **Risco de regressão:** MÉDIO — requer migration em tabela existente.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `ForeignKey("usuarios.id", ondelete="CASCADE")` adicionada em `models.py` + migration `20260803_0900_c9d8e7f6a5b4`, validada com upgrade/downgrade em banco de teste.

---

### [MELHORIA-15] Busca por username com `func.lower()` não usa o índice único existente

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/shared/core/helpers.py:21-27`
- **Eixo:** Banco
- **Problema:** `ix_usuarios_username` é um índice único sobre a coluna crua (`migrations/versions/20260418_2233_..._initial_schema_consolidated.py:91`), mas toda busca de autenticação faz `func.lower(Usuario.username) == username.lower()`, o que em SQLite não usa esse índice — resulta em varredura completa da tabela `usuarios` em toda requisição autenticada (via `get_current_user`).
- **Consequência:** hoje irrelevante com poucas dezenas de usuários; se a tabela crescer, cada requisição autenticada paga um full scan.
- **Correção proposta:** criar um índice funcional `CREATE INDEX ON usuarios (lower(username))`, ou normalizar a coluna para minúsculas na gravação (já é o caso hoje, ver BUG-04) e comparar diretamente sem `func.lower()` nos dois lados.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** 🚫 NÃO CORRIGIDO — otimização de baixa prioridade, sem impacto hoje (poucas dezenas de usuários). BUG-04 já garante que a gravação é sempre lowercase, mas `helpers.buscar_usuario_por_username` continua comparando via `func.lower()` dos dois lados (não usa o índice). Índice funcional não foi criado.

---

### [MELHORIA-16] `service.py` mistura `HTTPException` cru com as exceções tipadas de domínio

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/service.py:11,69-72`
- **Eixo:** Arquitetura
- **Problema:** o restante do módulo usa `domain_exc.EntidadeNaoEncontradaError`/`ConflitoNegocioError` (`app/shared/core/exceptions.py`), mas o bloqueio de conta por tentativas falhas levanta `HTTPException(429, ...)` diretamente, importada do FastAPI dentro da camada de serviço.
- **Consequência:** nenhuma hoje (o handler trata `HTTPException` igual), mas acopla a camada de serviço ao transporte HTTP (item F do checklist) e diverge do padrão do próprio módulo.
- **Correção proposta:** criar uma exceção de domínio dedicada (ex. `ContaBloqueadaError`, status 429) em `app/shared/core/exceptions.py` e usá-la aqui.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. Nova `domain_exc.ContaBloqueadaError` (429) em `app/shared/core/exceptions.py`, usada em `autenticar_usuario` no lugar do `HTTPException` cru.

---

### [MELHORIA-17] Módulo `auth` não usa seu próprio catálogo `roles.py`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/service.py:229,282,290-291`, `app/bootstrap/dependencies.py:148-166`
- **Eixo:** Arquitetura
- **Problema:** `roles.py` declara `ALL_FUNCTIONS`/`PRIVILEGED_FUNCTIONS`/`ADMIN_FUNCTIONS` com a instrução explícita "adicionar novos papéis APENAS aqui... evita aliases indevidos" (`roles.py:5-7`), mas o próprio `auth` usa o literal `"ADMINISTRADOR"` repetido em `service.py` e os atalhos `AdminRequired`/`EncarregadoRequired`/etc. em `dependencies.py` também usam strings literais. Hoje só `calendario/service.py` importa `roles.py`.
- **Consequência:** o mecanismo de centralização existe mas não é seguido nem pelo módulo dono dele — qualquer futura renomeação de papel (ex. `ADMINISTRADOR` → `ADMIN`) exigiria caçar strings em vez de mudar uma constante.
- **Correção proposta:** substituir os literais por referências a `roles.ADMIN_FUNCTIONS`/etc. em `auth` e `dependencies.py`.
- **Risco de regressão:** BAIXO — refatoração mecânica, sem mudança de comportamento.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `roles.py` ganhou constantes escalares (`ADMINISTRADOR`, `ENCARREGADO`, etc.); `service.py` e `dependencies.py` (atalhos `AdminRequired`/`EncarregadoOuAdmin`/etc.) passaram a referenciá-las em vez de literais.

---

### [MELHORIA-18] `ADMIN_PASSWORD_RESET` lido via `os.getenv` direto, contradizendo o próprio comentário do arquivo

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/service.py:299`
- **Eixo:** Configuração
- **Problema:** o comentário em `service.py:55-58` estabelece `settings.app_env` como "fonte única de verdade" para não ter "duas fontes divergentes para a mesma decisão de segurança", citando `os.getenv` direto como o próprio risco a evitar — mas `os.getenv("ADMIN_PASSWORD_RESET", ...)` na linha 299 faz exatamente isso, sem passar por `Settings`.
- **Consequência:** inconsistente com o resto do arquivo; se `Settings` cachear/validar env vars de forma diferente do processo (ex. `.env` vs ambiente do processo), esse flag pode divergir do restante da configuração.
- **Correção proposta:** promover `ADMIN_PASSWORD_RESET` a um campo de `Settings` (`app/bootstrap/config/__init__.py`) e usá-lo daqui, igual ao padrão já aplicado para `app_env`.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. Novo campo `settings.admin_password_reset` (env `ADMIN_PASSWORD_RESET`, case-insensitive via pydantic-settings); `service.py` usa `settings.admin_password_reset` no lugar de `os.getenv`.

---

### [MELHORIA-19] Código morto: schemas e imports sem uso

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/schemas.py:18,57,90`; `app/modules/auth/router.py:15-16`
- **Eixo:** Testes / Manutenibilidade
- **Problema:** `LoginRequest`, `RefreshTokenRequest` e `TokenPayload` (`schemas.py`) não têm nenhum consumidor no projeto (o login usa `OAuth2PasswordRequestForm`, o refresh lê o cookie diretamente). Em `router.py`, os imports `EncarregadoRequired` e `oauth2_scheme` (linhas 15-16) também não são referenciados em nenhum handler do arquivo.
- **Consequência:** nenhuma em runtime; custo de manutenção — um leitor pode assumir que `LoginRequest` é o contrato real do endpoint de login e ficar confuso ao ver `OAuth2PasswordRequestForm` sendo usado de fato.
- **Correção proposta:** remover os três schemas não usados e os dois imports órfãos (ou, se forem parte de um contrato público planejado, adicionar um comentário explicando por que existem sem uso).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `LoginRequest`, `RefreshTokenRequest`, `TokenPayload` removidos de `schemas.py`; imports órfãos `EncarregadoRequired`/`oauth2_scheme` removidos de `router.py`.

---

### [MELHORIA-20] Comentário desatualizado sobre os gatilhos de criação de usuários de teste

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/service.py:307-311`
- **Eixo:** Manutenibilidade (anti-padrão §7.2 do `revisor.md`)
- **Problema:** o comentário em `service.py:307-310` descreve o segundo gatilho como `enable_dev_seeds=True`, mas a condição real na linha seguinte testa `settings.enable_test_users`. `enable_dev_seeds` é um campo *diferente* e existe separadamente em `app/bootstrap/config/__init__.py:79` (documentado para permitir "dados de teste (panes, inspeções, etc)").
- **Consequência:** um leitor futuro que confie no comentário para decidir qual variável de ambiente setar em um deploy de teste vai configurar a flag errada e não conseguir criar as contas de teste (ou pior, pensar que configurou corretamente).
- **Correção proposta:** corrigir o comentário para citar `enable_test_users`.
- **Risco de regressão:** BAIXO — é só o comentário.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. Comentário corrigido para citar `enable_test_users`.

---

### [RISCO-21] Relacionamentos `lazy="select"` em `Usuario` sob sessão assíncrona

- **Classificação:** RISCO
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/models.py:111-145`
- **Eixo:** Concorrência / Banco
- **Problema:** os seis relacionamentos declarados em `Usuario` (`panes_criadas`, `panes_concluidas`, `responsabilidades`, `inspecoes_abertas`, `inspecoes_concluidas`, `tarefas_inspecao_executadas`) usam `lazy="select"` — carregamento lazy síncrono, que sob `AsyncSession` levanta `MissingGreenlet` se algum código acessar o atributo fora de um contexto já resolvido (ex. um `Schema.model_validate()` que inclua esses campos, ou um novo endpoint futuro que itere `usuario.panes_criadas`).
- **Consequência:** hoje não observado como bug ativo (nenhum código atual em `auth` acessa esses atributos), mas é uma armadilha latente — qualquer novo código que os toque quebra em runtime com um erro cuja causa raiz (lazy loading assíncrono) não é óbvia pela mensagem.
- **Correção proposta:** documentar explicitamente "nunca acessar estes atributos fora de `selectinload` explícito", ou considerar `lazy="raise"` para falhar cedo e de forma clara em vez de silenciosamente funcionar até alguém tropeçar.
- **Risco de regressão:** BAIXO se apenas documentado; MÉDIO se `lazy="raise"` quebrar algum uso indireto não mapeado nesta revisão (módulos `panes`/`inspecoes` declaram o outro lado desses relacionamentos e não foram revisados aqui).
- **Precisa de teste antes?** SIM (para a opção `lazy="raise"`)
- **Status:** ⚠️ CORRIGIDO PARCIALMENTE — commit `872690b`. Optou-se pela opção mais segura (documentar) em vez de `lazy="raise"`, exatamente pelo risco MÉDIO citado acima (módulos `panes`/`inspecoes` não foram revisados). Comentário de alerta adicionado em `models.py` sobre os 6 relacionamentos.

---

### [MELHORIA-22] `GET /usuarios` sem paginação

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/router.py:347-359`
- **Eixo:** Contrato
- **Problema:** `listar_usuarios` retorna a lista completa do efetivo sem `limit`/`offset` nem `skip`/`page`.
- **Consequência:** hoje inofensivo (efetivo de uma unidade é pequeno), mas diverge do checklist C ("paginação ausente em endpoints de listagem") e não escala.
- **Correção proposta:** adicionar parâmetros opcionais de paginação, mantendo o comportamento atual como default se não fornecidos (evita breaking change).
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `GET /usuarios` ganhou `limit`/`offset` opcionais (default preserva o comportamento atual — retorna tudo).

---

### [MELHORIA-23] Senha mínima de 6 caracteres sem política de complexidade

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/schemas.py:33,49,54`
- **Eixo:** Segurança
- **Problema:** `UsuarioCreate.password`, `SenhaUpdate.nova_senha` e `AdminSenhaUpdate.nova_senha` exigem apenas `min_length=6`, sem checagem de complexidade (letras, números, símbolos) nem contra listas de senhas comuns.
- **Consequência:** senhas fracas como `"123456"` (aliás, literalmente usada como senha dos usuários de teste em `service.py:329`) passam na validação.
- **Correção proposta:** avaliar se a política atual é aceitável para o contexto do sistema (efetivo militar, ambiente interno) antes de propor mudança — não é claramente um bug, mas vale registrar como melhoria de postura de segurança.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** 🚫 NÃO CORRIGIDO — o próprio achado já classifica como "não claramente um bug"; decisão de postura de segurança para o contexto (efetivo militar, ambiente interno), não tomada nesta sessão.

---

### [MELHORIA-24] Rate limiting cobre só `/login`; `/refresh` e troca de senha ficam sem limite

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/auth/router.py:36,362-376`
- **Eixo:** Segurança
- **Problema:** `@limiter.limit("5/minute")` existe apenas no endpoint de login (consistente com o achado transversal do mapa arquitetural, §5, "1 único endpoint de todo o sistema"). `PUT /auth/usuarios/senha` (`alterar_senha`) verifica `senha_atual` contra o hash armazenado antes de trocar — ou seja, é um segundo oráculo de senha, sem nenhum rate limit próprio. `/auth/refresh` também não tem limite.
- **Consequência:** um atacante autenticado (ou que tenha capturado um access token válido) pode tentar força bruta contra `senha_atual` em `PUT /usuarios/senha` sem nenhuma trava de tentativas, diferente do fluxo de login que tem lockout dedicado.
- **Correção proposta:** aplicar `@limiter.limit(...)` também em `alterar_senha` e `/auth/refresh`.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO
- **Status:** ✅ CORRIGIDO — commit `872690b`. `@limiter.limit` aplicado em `/auth/refresh` (20/minute) e `PUT /auth/usuarios/senha` (5/minute).

---

## Resumo

- Total de achados: 24
- BUG: 4 (CRÍTICA: 0, ALTA: 4, MÉDIA: 0, BAIXA: 0)
- RISCO: 9 (ALTA: 1, MÉDIA: 5, BAIXA: 3)
- MELHORIA: 10 (todas BAIXA)
- DÚVIDA: 1 (BAIXA)

### Status da correção (03/08/2026, commit `872690b`)

- ✅ Corrigidos: 19/24 (BUG-01, 02, 03, 04 · RISCO-05, 07, 08, 09, 10, 11 · MELHORIA-13, 14, 16, 17, 18, 19, 20, 22, 24)
- ⚠️ Parcial: 1/24 (RISCO-21 — documentado, não migrado para `lazy="raise"`)
- 🚫 Não corrigidos: 4/24 (RISCO-06, DÚVIDA-12, MELHORIA-15, MELHORIA-23 — decisão de produto/desenvolvedor pendente ou otimização de baixa prioridade)

## Arquivos revisados

- `app/modules/auth/router.py` (integral, 435 linhas)
- `app/modules/auth/service.py` (integral, 357 linhas)
- `app/modules/auth/models.py` (integral, 227 linhas)
- `app/modules/auth/schemas.py` (integral, 94 linhas)
- `app/modules/auth/security.py` (integral, 103 linhas)
- `app/modules/auth/roles.py` (integral, 19 linhas)
- `app/modules/auth/__init__.py` (integral, 4 linhas)
- `app/bootstrap/dependencies.py` (integral — dependências de auth usadas por todo o sistema)
- `app/bootstrap/config/__init__.py` (parcial — campos relevantes a JWT/cookies/seed)
- `app/bootstrap/tasks.py` (integral — para validar `limpar_tokens_expirados`)
- `app/shared/core/helpers.py`, `app/shared/core/exceptions.py`, `app/shared/core/enums.py` (integrais)
- `app/shared/middleware/csrf.py` (integral)
- `app/web/static/js/app.js` (trechos de `clearAuth`/`apiFetch`)
- `migrations/versions/20260418_2233_..._initial_schema_consolidated.py` (trecho da tabela `usuarios`)
- `migrations/versions/20260419_2300_a1b2c3d4e5f6_add_token_refresh_table.py` (integral)
- `tests/unit/test_auth.py`, `tests/unit/test_auth_contas.py`, `tests/security/test_refresh_token.py`, `tests/security/test_refresh_token_rotacao.py` (nomes de teste, para mapear cobertura)

## Não revisado / limitações

- **CSRF**: verificado que `CSRFMiddleware` (`app/shared/middleware/csrf.py:57`) cobre POST/PUT/PATCH/DELETE sem isenção para `/auth/login` ou `/auth/logout` (a isenção antiga foi removida, conforme comentário no próprio arquivo). Não é achado.
- **Validação do segredo JWT**: `app/bootstrap/config/__init__.py:108-133` rejeita `app_secret_key` vazio, com valor default inseguro, ou com menos de 32 caracteres, no boot. Verificado, não é achado.
- **`limpar_tokens_expirados`**: não é código morto — `app/bootstrap/tasks.py:87-102` a agenda a cada hora via `token_cleanup_task`.
- **Migrations × models de `auth`**: sem divergência encontrada entre as colunas declaradas em `models.py` e as migrations correspondentes.
- **Pydantic v1/v2 misturado e `async def`/`def` misturado**: já verificados como negativos no mapa arquitetural (`00_mapa_arquitetural.md` §6) para o projeto inteiro; não reaberto aqui.
- **Ausência da camada `repositories/`**: é o padrão de fato de 100% dos módulos do projeto (`00_mapa_arquitetural.md` §1), que orienta explicitamente a não reportar isso como achado isolado de um módulo.
- **Estratégia de hashing**: o pré-hash SHA-256+base64 antes do bcrypt (`security.py:24-28`) trata corretamente a limitação de 72 bytes do bcrypt. Correto, não é achado.
- **Cobertura de teste**: os 4 arquivos (871 linhas) cobrem bem login (sucesso, falha, case-insensitive, payload inválido), RBAC básico, CRUD de usuário, e o fluxo de rotação/reuso de refresh token e sua não-aceitação como access token. **Lacunas identificadas mas não aprofundadas por já estarem cobertas nos achados acima**: nenhum teste para o lockout de 5 tentativas e seu desbloqueio por tempo; nenhum teste para a revogação (inexistente) de refresh token no logout (BUG-01); nenhum teste que exercite o bypass do último-admin via `atualizar_usuario` (BUG-03); nenhum teste de concorrência para os cenários de corrida descritos (RISCO-07, RISCO-08).
- **Módulos consumidores de `auth`**: `calendario.service`, `panes.service`, `efetivo` e outros que dependem de `Usuario`/RBAC não foram revisados em profundidade — apenas o suficiente para confirmar os pontos de acoplamento já mapeados em `00_mapa_arquitetural.md` §4. Uma eventual mudança em `lazy="select"` dos relacionamentos de `Usuario` (achado 21) precisaria ser validada contra o uso real em `panes`/`inspecoes`.
- **Efeito de mudanças de cookie/path no frontend `app/web/`**: revisado apenas o suficiente para confirmar BUG-01 (função `clearAuth`); o restante do JS do frontend (formulário de login, tratamento de erro de refresh) não foi lido linha a linha.

## Perguntas para o desenvolvedor

- **DÚVIDA-12**: os campos `access_token`/`refresh_token` do corpo de resposta sempre retornarem a string literal `"hidden"` é uma decisão deliberada de "nunca expor o token fora do cookie HttpOnly"? Se sim, o `response_model` e o suporte a `Authorization: Bearer` (via `oauth2_scheme`) deveriam ser simplificados para não sugerir uma capacidade que não existe de fato.
- **RISCO-06**: o fluxo de refresh token (rotação, detecção de reuso) foi deixado sem integração no frontend web de propósito — reservado para um consumidor de API/mobile futuro — ou é uma lacuna de integração pendente?
- **BUG-02**: ao resetar a senha de um usuário (fluxo do admin), é esperado que isso também derrube as sessões ativas desse usuário, ou o comportamento atual (só a senha muda) é intencional para não expulsar o próprio usuário no meio de um trabalho em andamento?
