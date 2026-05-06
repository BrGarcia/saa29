## 2026-05-05

### SEGURANÇA - Logout não revoga o refresh token

- **Local:** `app/modules/auth/router.py` — endpoint `POST /auth/logout`
- **Descrição:** O logout apaga o cookie `saa29_token` e insere o JTI do access token na blacklist, mas **não** deleta o cookie `saa29_refresh_token` nem marca o refresh token como revogado no banco (`TokenRefresh.revogado_em`). Um atacante (ou o próprio usuário em sessão comprometida) pode chamar `POST /auth/refresh` após o logout e obter um novo access token válido com o cookie de refresh que permanece ativo.
- **Impacto:** Logout efetivo não existe. Sessões não podem ser encerradas de forma confiável — crítico em sistema aeronáutico com controle de acesso por papel.
- **Sugestão:** No `logout`, buscar o TokenRefresh pelo JTI do refresh token (decodificando o cookie `saa29_refresh_token` se presente), setar `revogado_em = agora`, e chamar `response.delete_cookie(key="saa29_refresh_token", path="/auth/refresh")`.
- **Hash:** `e3a1f7`

---

### SEGURANÇA - `get_current_user` não verifica se o usuário está ativo

- **Local:** `app/bootstrap/dependencies.py` — função `get_current_user`
- **Descrição:** Após validar o JWT e checar a blacklist, a função busca o usuário pelo `username` mas não verifica `usuario.ativo`. Um usuário desativado via `DELETE /auth/usuarios/{id}` continua com acesso a todos os endpoints protegidos enquanto seu token não expirar (até 15 minutos).
- **Impacto:** Desligamento de militar do efetivo não impede acesso imediato ao sistema. Viola o princípio de revogação instantânea de acesso em contexto aeronáutico.
- **Sugestão:** Adicionar após a busca: `if not usuario.ativo: raise credentials_exception`.
- **Hash:** `b2c9d4`

---

### BUG - `cancelar_inspecao` e `concluir_inspecao` ignoram inspeções ativas paralelas da mesma aeronave

- **Local:** `app/modules/inspecoes/service.py` — funções `cancelar_inspecao` (linha 583) e `concluir_inspecao` (linha 568)
- **Descrição:** Ao cancelar ou concluir uma inspeção, o código define incondicionalmente `aeronave.status = StatusAeronave.DISPONIVEL`. Porém, `abrir_inspecao` só bloqueia duplicidade de *tipos* — duas inspeções com tipos distintos na mesma aeronave podem coexistir. Se a inspeção B for cancelada enquanto a inspeção A ainda está ativa, a aeronave aparece como `DISPONIVEL` mesmo estando em inspeção.
- **Impacto:** Aeronave pode ser marcada disponível enquanto fisicamente imobilizada em inspeção, com risco de dupla-alocação operacional.
- **Sugestão:** Antes de setar `DISPONIVEL`, verificar se existem outras inspeções ativas para a aeronave: `SELECT COUNT(*) FROM inspecoes WHERE aeronave_id = ? AND status IN ('ABERTA','EM_ANDAMENTO') AND id != ?`. Só restaurar o status se o resultado for zero.
- **Hash:** `f1a3e8`

---

### BUG - Deduplicação de tarefas em `abrir_inspecao` usa ordem de entrada para determinar `obrigatoria`

- **Local:** `app/modules/inspecoes/service.py` — função `abrir_inspecao`, linha 405–411
- **Descrição:** Quando múltiplos tipos de inspeção compartilham uma tarefa com o mesmo título, apenas o primeiro encontrado é mantido (`vistos` set por título). O flag `obrigatoria` do template descartado é silenciosamente ignorado. Se o tipo listado primeiro tiver a tarefa como opcional (`obrigatoria=False`) e o segundo como obrigatória (`True`), a tarefa criada será opcional — podendo ser ignorada na conclusão da inspeção.
- **Impacto:** Tarefa obrigatória pode ser tratada como opcional por acidente de ordem nos `tipos_inspecao_ids` enviados pelo cliente, permitindo conclusão de inspeção incompleta.
- **Sugestão:** Na deduplicação, usar `obrigatoria = any(t.obrigatoria for t in duplicatas)` — uma tarefa é obrigatória se ao menos um template a marca assim.
- **Hash:** `d7b5c2`

---

### ARQUITETURA - `db.commit()` direto dentro de `autenticar_usuario` viola o padrão de sessão do projeto

- **Local:** `app/modules/auth/service.py` — função `autenticar_usuario`, linhas 56 e 62
- **Descrição:** Todos os demais services usam `db.flush()` e delegam o commit à dependência `get_db()`. `autenticar_usuario` chama `await db.commit()` diretamente (em caso de falha e em caso de sucesso). Isso encerra a transação corrente prematuramente. Se o router precisar realizar outra operação na mesma sessão após o retorno (ex: criar `TokenRefresh` no login), essa operação estará em uma nova transação implícita — podendo causar inconsistências caso um dos passos falhe.
- **Impacto:** No fluxo atual do login (`router.py`), o `TokenRefresh` é adicionado *após* `autenticar_usuario` retornar; se houver falha depois do commit do service, o log de tentativas foi persistido mas o refresh token não, em estado inconsistente.
- **Sugestão:** Substituir ambos os `await db.commit()` por `await db.flush()`, alinhando com o padrão do projeto e deixando o commit para `get_db()`.
- **Hash:** `a9f2b1`
