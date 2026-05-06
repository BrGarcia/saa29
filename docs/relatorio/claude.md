## 2026-05-05

### [CORRIGIDO] SEGURANÇA - Logout não revoga o refresh token

- **Local:** `app/modules/auth/router.py` — endpoint `POST /auth/logout`
- **Descrição:** O logout apaga o cookie `saa29_token` e insere o JTI do access token na blacklist, mas **não** deleta o cookie `saa29_refresh_token` nem marca o refresh token como revogado no banco (`TokenRefresh.revogado_em`). Um atacante (ou o próprio usuário em sessão comprometida) pode chamar `POST /auth/refresh` após o logout e obter um novo access token válido com o cookie de refresh que permanece ativo.
- **Impacto:** Logout efetivo não existe. Sessões não podem ser encerradas de forma confiável — crítico em sistema aeronáutico com controle de acesso por papel.
- **Sugestão:** No `logout`, buscar o TokenRefresh pelo JTI do refresh token (decodificando o cookie `saa29_refresh_token` se presente), setar `revogado_em = agora`, e chamar `response.delete_cookie(key="saa29_refresh_token", path="/auth/refresh")`.
- **Hash:** `e3a1f7`

---

### [CORRIGIDO] SEGURANÇA - `get_current_user` não verifica se o usuário está ativo

- **Local:** `app/bootstrap/dependencies.py` — função `get_current_user`
- **Descrição:** Após validar o JWT e checar a blacklist, a função busca o usuário pelo `username` mas não verifica `usuario.ativo`. Um usuário desativado via `DELETE /auth/usuarios/{id}` continua com acesso a todos os endpoints protegidos enquanto seu token não expirar (até 15 minutos).
- **Impacto:** Desligamento de militar do efetivo não impede acesso imediato ao sistema. Viola o princípio de revogação instantânea de acesso em contexto aeronáutico.
- **Sugestão:** Adicionar após a busca: `if not usuario.ativo: raise credentials_exception`.
- **Hash:** `b2c9d4`

---

### [CORRIGIDO] BUG - `cancelar_inspecao` e `concluir_inspecao` ignoram inspeções ativas paralelas da mesma aeronave

- **Local:** `app/modules/inspecoes/service.py` — funções `cancelar_inspecao` (linha 583) e `concluir_inspecao` (linha 568)
- **Descrição:** Ao cancelar ou concluir uma inspeção, o código define incondicionalmente `aeronave.status = StatusAeronave.DISPONIVEL`. Porém, `abrir_inspecao` só bloqueia duplicidade de *tipos* — duas inspeções com tipos distintos na mesma aeronave podem coexistir. Se a inspeção B for cancelada enquanto a inspeção A ainda está ativa, a aeronave aparece como `DISPONIVEL` mesmo estando em inspeção.
- **Impacto:** Aeronave pode ser marcada disponível enquanto fisicamente imobilizada em inspeção, com risco de dupla-alocação operacional.
- **Sugestão:** Antes de setar `DISPONIVEL`, verificar se existem outras inspeções ativas para a aeronave: `SELECT COUNT(*) FROM inspecoes WHERE aeronave_id = ? AND status IN ('ABERTA','EM_ANDAMENTO') AND id != ?`. Só restaurar o status se o resultado for zero.
- **Hash:** `f1a3e8`

---

### [CORRIGIDO] BUG - Deduplicação de tarefas em `abrir_inspecao` usa ordem de entrada para determinar `obrigatoria`

- **Local:** `app/modules/inspecoes/service.py` — função `abrir_inspecao`, linha 405–411
- **Descrição:** Quando múltiplos tipos de inspeção compartilham uma tarefa com o mesmo título, apenas o primeiro encontrado é mantido (`vistos` set por título). O flag `obrigatoria` do template descartado é silenciosamente ignorado. Se o tipo listado primeiro tiver a tarefa como opcional (`obrigatoria=False`) e o segundo como obrigatória (`True`), a tarefa criada será opcional — podendo ser ignorada na conclusão da inspeção.
- **Impacto:** Tarefa obrigatória pode ser tratada como opcional por acidente de ordem nos `tipos_inspecao_ids` enviados pelo cliente, permitindo conclusão de inspeção incompleta.
- **Sugestão:** Na deduplicação, usar `obrigatoria = any(t.obrigatoria for t in duplicatas)` — uma tarefa é obrigatória se ao menos um template a marca assim.
- **Hash:** `d7b5c2`

---

### [CORRIGIDO] ARQUITETURA - `db.commit()` direto dentro de `autenticar_usuario` viola o padrão de sessão do projeto

- **Local:** `app/modules/auth/service.py` — função `autenticar_usuario`, linhas 56 e 62
- **Descrição:** Todos os demais services usam `db.flush()` e delegam o commit à dependência `get_db()`. `autenticar_usuario` chama `await db.commit()` diretamente (em caso de falha e em caso de sucesso). Isso encerra a transação corrente prematuramente. Se o router precisar realizar outra operação na mesma sessão após o retorno (ex: criar `TokenRefresh` no login), essa operação estará em uma nova transação implícita — podendo causar inconsistências caso um dos passos falhe.
- **Impacto:** No fluxo atual do login (`router.py`), o `TokenRefresh` é adicionado *após* `autenticar_usuario` retornar; se houver falha depois do commit do service, o log de tentativas foi persistido mas o refresh token não, em estado inconsistente.
- **Sugestão:** Substituir ambos os `await db.commit()` por `await db.flush()`, alinhando com o padrão do projeto e deixando o commit para `get_db()`.
- **Hash:** `a9f2b1`

---

## 2026-05-06

### SEGURANÇA - Bypass de CSRF via header em qualquer ambiente que não seja `"production"`

- **Local:** `app/shared/middleware/csrf.py` — linhas 31–34 (variável `skip_csrf`)
- **Descrição:** A guarda CSRF é desativada quando `settings.app_env != "production"` E o cliente envia `X-Skip-CSRF: true`. Qualquer ambiente cujo `APP_ENV` seja `"staging"`, `"homolog"`, `"qa"`, `"dev"` etc. aceita esse bypass. Como o header é trivialmente forjável, basta um atacante saber dessa convenção para emitir POST/PUT/PATCH/DELETE sem token CSRF contra esses ambientes — incluindo CSRF clássico via formulário cross-origin se cookies de sessão forem enviados (o `samesite="lax"` reduz mas não elimina, p.ex. em navegação top-level POST/POSTs invertidos via técnicas conhecidas).
- **Impacto:** Em ambientes de staging/homologação expostos a rede (com dados próximos aos de produção e usuários reais para testes), um endpoint mutador pode ser invocado sem CSRF. Em sistema aeronáutico, isso permite p.ex. registrar pane, fechar inspeção ou reativar usuário sem proteção.
- **Sugestão:** Restringir o bypass exclusivamente a `app_env == "testing"` (mesma convenção já usada por `app/shared/core/limiter.py:9`). Idealmente, validar também via segredo compartilhado em vez de literal `"true"`, ou eliminar o header e usar a marcação interna do conftest via `request.scope["app"].state.testing = True`.
- **Hash:** `c8e4a2`

---

### BUG - `_obter_ou_criar_item_por_pn` cria `ItemEquipamento` sem herdar controles de vencimento

- **Local:** `app/modules/equipamentos/service.py` — função `_obter_ou_criar_item_por_pn`, linhas 351–363
- **Descrição:** Quando o operador ajusta o inventário informando um S/N inexistente (`ajustar_inventario_item`), o helper instancia um novo `ItemEquipamento` e faz `db.flush()` sem replicar os controles definidos em `EquipamentoControle` para aquele modelo. Isso diverge do fluxo oficial `criar_item_com_heranca` (linhas 112–144), que itera sobre os templates e cria um `ControleVencimento` por tipo. Assim, S/Ns nascidos pela rota de ajuste de inventário ficam sem nenhum registro de vencimento — ausentes da matriz de vencimentos e dos alertas.
- **Impacto:** Itens instalados em aeronaves podem permanecer indefinidamente sem rastreio de inspeção/calibração, violando o requisito de rastreabilidade aeronáutica. A matriz (`montar_matriz_vencimentos`) marcará `VENCIDO` por ausência de vencimento (linha 275), mascarando o problema como "operacional" em vez de "inexistente".
- **Sugestão:** Após `db.add(item)`/`db.flush()` em `_obter_ou_criar_item_por_pn`, replicar o bloco de herança de `criar_item_com_heranca`: consultar `EquipamentoControle` por `modelo_id` e inserir um `ControleVencimento` por template. Melhor ainda, extrair essa lógica para um helper único reutilizado por ambos.
- **Hash:** `4d9c1b`

---

### BUG - `excluir_anexo` apaga o registro do banco antes de remover o arquivo do storage

- **Local:** `app/modules/panes/service.py` — função `excluir_anexo`, linhas 625–645
- **Descrição:** A função executa `await db.delete(anexo); await db.flush()` e só então chama `await storage_svc.delete(anexo.caminho_arquivo)`. Se o storage falhar (R2 indisponível, permissão, rede), o arquivo permanece no bucket sem nenhum registro no banco que aponte para ele — torna-se órfão e indelével pela aplicação. Inversamente, o flush não confirma a transação: o commit só ocorre em `get_db()` ao final do request; se o `storage_svc.delete` levantar e propagar, a transação faz rollback (o anexo "volta") mas o caminho `anexo.caminho_arquivo` foi lido em memória — arquivo ainda intacto, mas a ordem cria janelas de inconsistência difíceis de raciocinar.
- **Impacto:** Acúmulo silencioso de PDFs/imagens órfãs no storage (custo + risco LGPD/sigilo aeronáutico, pois anexos podem conter fotos de panes com dados sensíveis). Sem reconciliação periódica, esses arquivos não podem ser removidos.
- **Sugestão:** Inverter a ordem: capturar `caminho = anexo.caminho_arquivo`, executar `await storage_svc.delete(caminho)`; em caso de sucesso, fazer `await db.delete(anexo)`. Em caso de exceção do storage, registrar em log e ainda deletar o registro só se o erro indicar "arquivo não existe". Alternativamente, mover o caminho para uma fila de limpeza assíncrona (`AnexoExpurgo`) e ter um worker que reconcilia.
- **Hash:** `7e2f50`

---

### BUG - `processar_imagem_background` deixa anexos com `caminho_arquivo="processando"` permanentemente em caso de falha total

- **Local:** `app/modules/panes/service.py` — funções `upload_anexo` (linhas 511–520) e `processar_imagem_background` (linhas 540–592)
- **Descrição:** Quando `is_background=True`, `upload_anexo` cria o `Anexo` com placeholder `"processando"`. Se tanto o `process_image` quanto o fallback de upload original falharem (bloco `except Exception as fallback_exc`), o erro é apenas logado e o registro permanece com `caminho_arquivo="processando"` para sempre. Não há retry, marcação de erro, ou expurgo. Tentativas posteriores de servir esse anexo via `obter_url_anexo("processando")` chamarão o storage com um caminho inexistente.
- **Impacto:** UI exibirá ícones quebrados/links 404 indefinidamente. Como anexos costumam ser evidência fotográfica de panes (usadas em auditoria), uma evidência ausente sem indicação clara prejudica rastreabilidade. O usuário acredita que o upload foi efetivado.
- **Sugestão:** No `except` externo do fallback, abrir uma nova sessão e atualizar o anexo para um estado terminal (`caminho_arquivo="ERRO"` ou um campo dedicado `status_processamento`) ou deletar o registro inteiramente para que o usuário refaça o upload. Adicionalmente, expor um worker de reprocessamento ou um endpoint admin para listar/limpar anexos em estado `"processando"` há mais de N minutos.
- **Hash:** `b6a8d3`

---

### [CORRIGIDO] ARQUITETURA - `db.commit()` direto em `efetivo/service.py` repete o anti-padrão já corrigido em auth

- **Local:** `app/modules/efetivo/service.py` — funções `registrar_indisponibilidade` (linha 35) e `remover_indisponibilidade` (linha 62)
- **Descrição:** Mesmo problema do hash `a9f2b1` (já corrigido em `auth/service.py`): ambas as funções chamam `await db.commit()` diretamente, encerrando a transação dentro do service em vez de delegar para `get_db()`. Como o router pode encadear lógica adicional (ex.: notificação de mudança de disponibilidade, log de auditoria) numa mesma transação, o commit prematuro fragmenta a unidade de trabalho. Adicionalmente, em `remover_indisponibilidade`, o `db.commit()` ocorre antes do `return True` mas a função não tem `db.flush()` antes do `db.delete()` — confiando no commit. Isso é inconsistente com o restante do projeto.
- **Impacto:** Indisponibilidade pode ser persistida mesmo se uma operação subsequente do request falhar; impossibilita transações compostas (ex.: criar indisponibilidade + log de quem registrou) e quebra a uniformidade do padrão de sessão, dificultando manutenção.
- **Sugestão:** Substituir `await db.commit()` por `await db.flush()` nas duas funções e remover o `await db.refresh(indisp)` (que continuará funcionando após flush — o objeto já está na sessão). Deixar o commit para `get_db()`.
- **Hash:** `f3b7e9`
