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

### [CORRIGIDO] SEGURANÇA - Bypass de CSRF via header em qualquer ambiente que não seja `"production"`

- **Local:** `app/shared/middleware/csrf.py` — linhas 31–34 (variável `skip_csrf`)
- **Descrição:** A guarda CSRF é desativada quando `settings.app_env != "production"` E o cliente envia `X-Skip-CSRF: true`. Qualquer ambiente cujo `APP_ENV` seja `"staging"`, `"homolog"`, `"qa"`, `"dev"` etc. aceita esse bypass. Como o header é trivialmente forjável, basta um atacante saber dessa convenção para emitir POST/PUT/PATCH/DELETE sem token CSRF contra esses ambientes — incluindo CSRF clássico via formulário cross-origin se cookies de sessão forem enviados (o `samesite="lax"` reduz mas não elimina, p.ex. em navegação top-level POST/POSTs invertidos via técnicas conhecidas).
- **Impacto:** Em ambientes de staging/homologação expostos a rede (com dados próximos aos de produção e usuários reais para testes), um endpoint mutador pode ser invocado sem CSRF. Em sistema aeronáutico, isso permite p.ex. registrar pane, fechar inspeção ou reativar usuário sem proteção.
- **Sugestão:** Restringir o bypass exclusivamente a `app_env == "testing"` (mesma convenção já usada por `app/shared/core/limiter.py:9`). Idealmente, validar também via segredo compartilhado em vez de literal `"true"`, ou eliminar o header e usar a marcação interna do conftest via `request.scope["app"].state.testing = True`.
- **Hash:** `c8e4a2`

---

### [CORRIGIDO] BUG - `_obter_ou_criar_item_por_pn` cria `ItemEquipamento` sem herdar controles de vencimento

- **Local:** `app/modules/equipamentos/service.py` — função `_obter_ou_criar_item_por_pn`, linhas 351–363
- **Descrição:** Quando o operador ajusta o inventário informando um S/N inexistente (`ajustar_inventario_item`), o helper instancia um novo `ItemEquipamento` e faz `db.flush()` sem replicar os controles definidos em `EquipamentoControle` para aquele modelo. Isso diverge do fluxo oficial `criar_item_com_heranca` (linhas 112–144), que itera sobre os templates e cria um `ControleVencimento` por tipo. Assim, S/Ns nascidos pela rota de ajuste de inventário ficam sem nenhum registro de vencimento — ausentes da matriz de vencimentos e dos alertas.
- **Impacto:** Itens instalados em aeronaves podem permanecer indefinidamente sem rastreio de inspeção/calibração, violando o requisito de rastreabilidade aeronáutica. A matriz (`montar_matriz_vencimentos`) marcará `VENCIDO` por ausência de vencimento (linha 275), mascarando o problema como "operacional" em vez de "inexistente".
- **Sugestão:** Após `db.add(item)`/`db.flush()` em `_obter_ou_criar_item_por_pn`, replicar o bloco de herança de `criar_item_com_heranca`: consultar `EquipamentoControle` por `modelo_id` e inserir um `ControleVencimento` por template. Melhor ainda, extrair essa lógica para um helper único reutilizado por ambos.
- **Hash:** `4d9c1b`

---

### [CORRIGIDO] BUG - `excluir_anexo` apaga o registro do banco antes de remover o arquivo do storage

- **Local:** `app/modules/panes/service.py` — função `excluir_anexo`, linhas 625–645
- **Descrição:** A função executa `await db.delete(anexo); await db.flush()` e só então chama `await storage_svc.delete(anexo.caminho_arquivo)`. Se o storage falhar (R2 indisponível, permissão, rede), o arquivo permanece no bucket sem nenhum registro no banco que aponte para ele — torna-se órfão e indelével pela aplicação. Inversamente, o flush não confirma a transação: o commit só ocorre em `get_db()` ao final do request; se o `storage_svc.delete` levantar e propagar, a transação faz rollback (o anexo "volta") mas o caminho `anexo.caminho_arquivo` foi lido em memória — arquivo ainda intacto, mas a ordem cria janelas de inconsistência difíceis de raciocinar.
- **Impacto:** Acúmulo silencioso de PDFs/imagens órfãs no storage (custo + risco LGPD/sigilo aeronáutico, pois anexos podem conter fotos de panes com dados sensíveis). Sem reconciliação periódica, esses arquivos não podem ser removidos.
- **Sugestão:** Inverter a ordem: capturar `caminho = anexo.caminho_arquivo`, executar `await storage_svc.delete(caminho)`; em caso de sucesso, fazer `await db.delete(anexo)`. Em caso de exceção do storage, registrar em log e ainda deletar o registro só se o erro indicar "arquivo não existe". Alternativamente, mover o caminho para uma fila de limpeza assíncrona (`AnexoExpurgo`) e ter um worker que reconcilia.
- **Hash:** `7e2f50`

---

### [CORRIGIDO] BUG - `processar_imagem_background` deixa anexos com `caminho_arquivo="processando"` permanentemente em caso de falha total

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

---

## 2026-05-06 (rodada 2)

### [CORRIGIDO] BUG - `alternar_status_aeronave` força INATIVA em aeronave sob inspeção

- **Local:** `app/modules/aeronaves/service.py` — função `alternar_status_aeronave`, linhas 48–52
- **Descrição:** O `else` do toggle aplica `StatusAeronave.INATIVA` a **qualquer** status que não seja `INATIVA`, incluindo `INSPECAO`. Um Encarregado que acione o toggle em uma aeronave atualmente em inspeção irá sobrepor o status `INSPECAO` para `INATIVA` sem cancelar a inspeção no banco. Quando a inspeção for concluída ou cancelada, o módulo de inspeções reverte para `DISPONIVEL`, ignorando a inativação.
- **Impacto:** Estado da aeronave fica inconsistente com a inspeção em andamento. Aeronave inativa aparece como sob inspeção no módulo de inspeções, podendo mascarar o encerramento da inspeção ou liberá-la prematuramente.
- **Sugestão:** Adicionar guarda antes do `else`: `if aeronave.status == StatusAeronave.INSPECAO: raise ValueError("Aeronave está sob inspeção ativa. Cancele ou conclua a inspeção antes de alterar o status.")`. Ou restringir o toggle apenas ao par `DISPONIVEL ↔ INATIVA`.
- **Hash:** `2c9d5f`

---

### [CORRIGIDO] BUG - `registrar_execucao` usa periodicidade hardcoded de 12 meses quando a regra está ausente

- **Local:** `app/modules/vencimentos/service.py` — função `registrar_execucao`, linha 147
- **Descrição:** `periodicidade = regra.periodicidade_meses if regra else 12` — se o `EquipamentoControle` associado ao item não for encontrado (deleção posterior, item criado pelo bug `4d9c1b`, inconsistência de dados), a execução é registrada com 12 meses de periodicidade sem qualquer aviso, log ou exceção. O próximo `data_vencimento` é calculado incorretamente para itens com periodicidade diferente (ex.: calibração semestral de 6 meses vira 12 meses).
- **Impacto:** Datas de vencimento incorretas ficam registradas com aparência de dados válidos. Em sistema aeronáutico, prazos de calibração e inspeção incorretos representam risco operacional direto e podem passar por auditorias sem detecção.
- **Sugestão:** Substituir o fallback silencioso por uma exceção explícita: `if not regra: raise domain_exc.EntidadeNaoEncontradaError("Regra de periodicidade não encontrada para este item/controle.")`. O operador é forçado a corrigir os dados antes de registrar a execução.
- **Hash:** `8e3b7a`

---

### [CORRIGIDO] ARQUITETURA - `atualizar_aeronave` aceita `status = INSPECAO` diretamente via PUT

- **Local:** `app/modules/aeronaves/service.py` — função `atualizar_aeronave`, linhas 89–97
- **Descrição:** O campo `status` do schema de atualização não é filtrado em `atualizar_aeronave`. Um administrador pode enviar `{"status": "INSPECAO"}` via `PUT /aeronaves/{id}` sem criar nenhum registro em `Inspecao`, sem tarefas, sem rastreabilidade de abertura. O comentário no código (`# Removida a trava que impedia definir como INATIVA via PUT`) confirma que a guarda foi intencionalmente removida, mas sem restringir os valores permitidos.
- **Impacto:** Aeronave fica com `status = INSPECAO` sem inspeção correspondente no banco, corrompendo a lógica de `abrir_inspecao` (que bloqueia abertura se já houver status `INSPECAO` via join) e impedindo a criação de novas inspeções legítimas.
- **Sugestão:** Remover `status` dos campos atualizáveis via `atualizar_aeronave` (ou restringir a `{DISPONIVEL, INATIVA}`). Transições para `INSPECAO` devem ocorrer exclusivamente pelo módulo de inspeções.
- **Hash:** `5f1c4d`

---

### [CORRIGIDO] BUG - Alterar periodicidade de `EquipamentoControle` não recalcula `data_vencimento` dos itens existentes

- **Local:** `app/modules/vencimentos/service.py` — função `associar_controle_a_equipamento`, linhas 69–72
- **Descrição:** Quando uma regra de periodicidade já existente é atualizada (`existing.periodicidade_meses = periodicidade`), os registros `ControleVencimento` de todos os itens daquele modelo **não** têm seu `data_vencimento` recalculado. O novo prazo só passa a valer na próxima chamada a `registrar_execucao`. Enquanto isso, todos os itens exibem datas calculadas com a periodicidade antiga.
- **Impacto:** Uma redução de periodicidade (ex.: 12 → 6 meses) não é refletida imediatamente na matriz de vencimentos. Itens que deveriam aparecer como `VENCENDO` continuam como `OK` até o próximo registro de execução, criando uma janela de falsa conformidade na frota.
- **Sugestão:** Após atualizar `existing.periodicidade_meses`, recalcular `data_vencimento` para todos os `ControleVencimento` cujo `data_ultima_exec` não é nulo: `novo_vencimento = cv.data_ultima_exec + relativedelta(months=periodicidade)`. Itens sem `data_ultima_exec` permanecem com status `VENCIDO` como já ocorre.
- **Hash:** `a2e6c8`

---

### [CORRIGIDO] BUG - Bulk UPDATEs via `__table__.update()` em `vencimentos/service.py` ficam defasados no identity map da sessão

- **Local:** `app/modules/vencimentos/service.py` — funções `registrar_execucao` (linha 153), `prorrogar_vencimento` (linha 340) e `cancelar_prorrogacao` (linha 369)
- **Descrição:** As três funções desativam `ProrrogacaoVencimento` ativa usando SQL bruto via `__table__.update()`. Esse mecanismo atualiza o banco diretamente mas **não sincroniza o identity map da sessão SQLAlchemy**: instâncias de `ProrrogacaoVencimento` já carregadas na sessão (ex.: via `selectinload(ControleVencimento.prorrogacoes)`) permanecem com `ativo=True` em memória. Se a mesma sessão serializar a resposta logo após (como ocorre em `registrar_execucao` que retorna o `vencimento` cujas `prorrogacoes` podem já estar no cache), o JSON de resposta retornará a prorrogação como ainda ativa, contradizendo o que foi gravado.
- **Impacto:** Resposta da API pode divergir do estado real do banco na mesma requisição. Em `prorrogar_vencimento`, a prorrogação anterior aparecerá como ativa na resposta mesmo tendo sido revogada, confundindo o frontend e quebrando a exibição do histórico de prorrogações.
- **Sugestão:** Após cada `__table__.update()`, invalidar o cache da sessão com `await db.execute(select(1))` + `session.expire_all()`, ou reescrever usando ORM: buscar as instâncias ativas, setar `.ativo = False` individualmente e usar `flush()`. A abordagem ORM é mais segura e alinhada ao padrão do projeto.
- **Hash:** `9b4f1e`

---

## 2026-05-07

### [CORRIGIDO] BUG/SEGURANÇA - `R2StorageService.delete()` engole exceções e neutraliza a correção `7e2f50` em produção

- **Local:** `app/shared/core/storage.py` — método `R2StorageService.delete`, linhas 134–142, em conjunto com `app/modules/panes/service.py:651–664` (`excluir_anexo`)
- **Descrição:** A correção `7e2f50` (rodada anterior) inverteu a ordem de remoção em `excluir_anexo` para tentar apagar do storage *antes* do banco, esperando que uma exceção do storage abortasse o `db.delete(anexo)`. Porém, o método `R2StorageService.delete` envolve `s3_client.delete_object` em `try/except Exception: return False` — qualquer falha (rede, credencial, 5xx do R2, AccessDenied) é silenciada e devolvida como `False`. O chamador em `excluir_anexo` **não inspeciona o booleano de retorno**: ele apenas espera por exceção. Logo, em qualquer falha real do R2, o fluxo prossegue, executa `db.delete(anexo)` e o registro é apagado, deixando o objeto órfão no bucket. Localmente (`LocalStorageService.delete`) a falha é menos provável e a função não engole exceções, mas o backend padrão de produção é R2.
- **Impacto:** A garantia documentada do hash `7e2f50` ("apaga storage ANTES do banco") deixa de existir em produção. Volta a haver acúmulo silencioso de PDFs/fotos órfãs no R2, com custo crescente e risco LGPD/sigilo aeronáutico (anexos de panes podem conter evidência fotográfica sensível). Pior: a UI mostra sucesso, e o operador acredita que o anexo foi totalmente expurgado.
- **Sugestão:** Em `R2StorageService.delete`, deixar a exceção propagar (ou re-erguer como `RuntimeError` com contexto) em vez de devolver `False` silencioso. Em `excluir_anexo`, além disso, tratar explicitamente o booleano: `if not await storage_svc.delete(...): raise ValueError("Falha ao remover do storage.")`. Tratar 404/`NoSuchKey` do R2 como sucesso idempotente (caminho já não existe). Considerar também enfileirar caminhos a expurgar em `AnexoExpurgo` para reconciliação assíncrona.
- **Hash:** `c1a8b9`

---

### [CORRIGIDO] BUG - `abrir_inspecao` aceita aeronave INATIVA e a "reativa" silenciosamente sobrescrevendo `aeronave.status`

- **Local:** `app/modules/aeronaves/...` e `app/modules/inspecoes/service.py` — função `abrir_inspecao`, linhas 346–396
- **Descrição:** A função busca a aeronave (linhas 346–348) mas não valida `aeronave.status`. Mais adiante, executa incondicionalmente `aeronave.status = StatusAeronave.INSPECAO.value` (linha 396). Isso permite que uma aeronave em `INATIVA` (deliberadamente removida de serviço pelo Encarregado) seja reaberta de fato via abertura de inspeção, contornando o fluxo correto: reativar → inspecionar. Trata-se da contraparte simétrica das correções `5f1c4d` (PUT direto para INSPECAO) e `2c9d5f` (toggle force INATIVA em INSPECAO): a entrada `INATIVA → INSPECAO` permaneceu desprotegida.
- **Impacto:** Estado da frota deixa de refletir decisões operacionais. Uma aeronave inativada (p.ex. por dano estrutural, aguardando aprovação para retorno) pode ser tirada do limbo administrativo por qualquer ENCARREGADO/INSPETOR/ADMIN ao abrir uma inspeção, sem nenhum log de reativação. Quebra o princípio de transição explícita de status em sistema aeronáutico.
- **Sugestão:** Após buscar a aeronave em `abrir_inspecao`, antes de qualquer outra validação, adicionar: `if aeronave.status == StatusAeronave.INATIVA.value: raise ValueError("Aeronave inativa. Reative a aeronave antes de abrir inspeção.")`. Padrão idêntico ao já adotado em `criar_pane` (`panes/service.py:99–100`).
- **Hash:** `b4d7e6`

---

### [CORRIGIDO] SEGURANÇA - `refresh_access_token` não detecta reuso de refresh token revogado (RFC 6849 BCP §10.4)

- **Local:** `app/modules/auth/router.py` — endpoint `POST /auth/refresh`, linhas 110–240
- **Descrição:** A rota faz rotação de refresh token (gera novo, revoga antigo) corretamente em fluxo legítimo. Porém, ao receber um refresh token cujo `jti` existe na tabela `TokenRefresh` mas com `revogado_em IS NOT NULL` (já consumido), o código apenas devolve 401 e segue: o filtro `(TokenRefresh.revogado_em.is_(None))` na linha 154 simplesmente exclui a linha do resultado e cai no `if not stored_token: raise 401`. Isso descumpre o OAuth 2.0 Security BCP §10.4 (RFC 6749/6819): se um refresh token já revogado aparece de novo, é forte evidência de cópia/roubo do cookie e a família inteira de tokens emitidos para aquele usuário deveria ser invalidada (revoke-all-active-tokens-for-user) — caso contrário, o atacante e o usuário legítimo continuam conseguindo refrescar enquanto se revezam.
- **Impacto:** Em sistema aeronáutico com perfis privilegiados (ENCARREGADO, ADMIN), um refresh token vazado por XSS futuro, log indevido ou cookie copiado em estação compartilhada permite ao atacante manter acesso por 7 dias mesmo após o usuário legítimo refrescar (e vice-versa), sem qualquer detecção. Não há trilha de "sessão suspeita" para o ADMIN reagir.
- **Sugestão:** No bloco que hoje retorna 401 quando `stored_token` é `None`, antes de devolver, fazer uma segunda consulta sem o filtro de `revogado_em` para o mesmo `jti`. Se a linha existir e estiver revogada, executar `UPDATE token_refresh SET revogado_em = NOW() WHERE usuario_id = :uid AND revogado_em IS NULL` (revoga toda a família ativa do usuário) e gravar evento de segurança em log. Resposta continua 401, mas todos os tokens daquele usuário são invalidados — usuário legítimo é forçado a re-autenticar e o atacante perde o acesso.
- **Hash:** `8a2f31`

---

### [CORRIGIDO] SEGURANÇA - Endpoints de inventário/instalação aceitam qualquer usuário autenticado (sem RBAC)

- **Local:** `app/modules/equipamentos/router.py` — `instalar_item` (linha 165), `remover_item` (linha 182), `ajustar_inventario` (linha 233)
- **Descrição:** Os três endpoints declaram apenas `_: CurrentUser` ou `current_user: CurrentUser` como dependência, sem `ensure_role(...)` nem uso de aliases como `ExecucaoPermitida`/`EncarregadoOuAdmin`. Como `CurrentUser` exige somente JWT válido, **qualquer perfil cadastrado** (incluindo INSPETOR — cuja função é vistoriar, não movimentar — ou novos perfis "VIEWER" futuros) consegue: instalar item em slot, registrar remoção, e ajustar S/N de inventário (com `forcar_transferencia` inclusive). Fluxos análogos do mesmo módulo já aplicam papel (`AdminRequired` para criar PN/SN, slots), e em `panes/router.py` o padrão é `ensure_role("MANTENEDOR", "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")` para mutações.
- **Impacto:** Segregação de funções (separation of duties) é quebrada justamente nas rotas que mais demandam rastreabilidade aeronáutica — quem instala/remove material aviônico fica gravado na `Instalacao.usuario_id`, mas não há controle de papel. Um INSPETOR pode mover SNs sem autorização operacional; um perfil novo de baixo privilégio adicionado no futuro herdaria automaticamente esse acesso.
- **Sugestão:** Trocar a dependência: em `instalar_item` e `remover_item`, usar `ExecucaoPermitida` (MANTENEDOR/ENCARREGADO/ADMINISTRADOR); em `ajustar_inventario`, usar `EncarregadoOuAdmin` (mais restritivo, dado o `forcar_transferencia`). Auditar testes para garantir cobertura dos 403 esperados.
- **Hash:** `e9c0a4`

---

### [CORRIGIDO] ARQUITETURA - `R2StorageService` instanciado a cada chamada cria novo cliente boto3 por request

- **Local:** `app/shared/core/storage.py` — `get_storage_service` (linhas 145–150) e `R2StorageService.__init__` (linhas 78–93); chamadores em `app/modules/panes/service.py` (linhas 526, 565, 581, 652, 671)
- **Descrição:** A factory devolve `R2StorageService()` novo em cada invocação. O `__init__` chama `boto3.client("s3", ...)` — operação cara: resolução de credencial, configuração de assinatura SigV4, alocação de pool HTTPS, instanciação de `botocore.session`. Cada upload, download, ou delete dispara essa criação (5 chamadas em `panes/service.py` para o mesmo request de upload com fallback). Em paralelo, um `BackgroundTasks` de processamento de imagem cria *outras* instâncias dentro de `processar_imagem_background` (linhas 565 e 581).
- **Impacto:** Latência adicional perceptível por request com anexo (handshake TLS adicional + setup botocore), pressão maior no pool de conexões/file descriptors e custos elevados em janelas de upload em massa. Em ambiente Cloud Run/serverless onde há risco de cold-start, agrava p99. Não há leak permanente, mas há desperdício consistente. `LocalStorageService` sofre do mesmo problema em menor escala (recriação de `Path` e `mkdir`).
- **Sugestão:** Tornar `get_storage_service` um singleton via `@functools.lru_cache(maxsize=1)` (mesmo padrão de `get_settings`) ou armazenar a instância em `app.state` na inicialização do FastAPI (`bootstrap/events.py`). Cliente boto3 é thread-safe e reutilizável; pode ser compartilhado em todo o processo. Cuidar para invalidar o cache em testes que mockam `settings`.
- **Hash:** `7d52cb`

---

## 2026-05-07 (rodada 2)

### SEGURANÇA - `adicionar_responsavel` aceita `papel` arbitrário enviado pelo cliente

- **Local:** `app/modules/panes/router.py:319-340` em conjunto com `app/modules/panes/service.py:698-701`
- **Descrição:** O endpoint `POST /panes/{pane_id}/responsaveis` valida apenas que MANTENEDOR/INSPETOR só podem adicionar a si mesmos (`usuario_id == current_user.id`), mas **não valida o campo `papel` do payload**. O service grava `papel=dados.papel.value` literalmente, sem cruzar com `Usuario.funcao`. Assim, um MANTENEDOR pode chamar a rota com `{"usuario_id": <ele mesmo>, "papel": "ADMINISTRADOR"}` e ficar registrado na pane com papel ADMINISTRADOR. Compare com `concluir_pane` (`panes/service.py:402-405`), onde o papel armazenado é forçado para `usuario.funcao` (papel real do banco), demonstrando que o padrão do projeto é não confiar no cliente.
- **Impacto:** Corrupção dos registros de responsabilidade aeronáutica. Auditorias e relatórios sobre uma pane podem exibir "ADMIN: Sgt Fulano" mesmo o usuário sendo MANTENEDOR. Embora hoje `PaneResponsavel.papel` seja apenas exibido, qualquer futura regra (filtros tipo "panes resolvidas por ENCARREGADO", export para SAA/QA) que confie nesse campo aplicará privilégio errado. Quebra explícita de rastreabilidade.
- **Sugestão:** No `service.adicionar_responsavel`, buscar o `Usuario` por `dados.usuario_id` e gravar `papel=usuario.funcao`, ignorando o que veio no payload (espelhando `concluir_pane`). Como alternativa, validar no router: `if dados.papel.value != current_user.funcao and current_user.funcao not in {"ENCARREGADO","ADMINISTRADOR"}: raise 403`. Idealmente remover o campo `papel` do schema `AdicionarResponsavel`.
- **Hash:** `f5d2a7`

---

### [FALSO POSITIVO] SEGURANÇA - `adicionar_tarefa_avulsa` aceita perfil MANTENEDOR

- **Local:** `app/modules/inspecoes/router.py:419-429` — endpoint `POST /inspecoes/{inspecao_id}/tarefas`
- **Descrição:** A auditoria anterior apontou que o endpoint exige apenas `_: CurrentUser`, permitindo que um MANTENEDOR adicione tarefas avulsas a uma inspeção, diferindo do restante do módulo que restringe mutações a `EncarregadoInspetorOuAdmin`. A auditoria interpretou isso como quebra de segregação de funções.
- **Análise do Setor (Regra de Negócio Real):** A premissa da auditoria estava equivocada em relação ao fluxo de trabalho real. Na prática da manutenção aeronáutica, **todo mantenedor pode e DEVE relatar falhas identificadas**, inserindo-as como tarefas extras na inspeção. Isso é um princípio basilar da **SEGURANÇA DE VOO**. Retirar esse privilégio criaria um gargalo perigoso.
- **Sugestão/Ação:** Nenhuma restrição no código deve ser feita. O comportamento atual está **CORRETO**. Recomenda-se atualizar a documentação de RBAC para explicitar que a inserção de tarefas avulsas em inspeções é permitida a todos os mantenedores.
- **Hash:** `3a9c8e`

---

### BUG/RASTREABILIDADE - `instalar_item` grava `Instalacao` com `usuario_id=NULL`

- **Local:** `app/modules/equipamentos/router.py:165-174` e `app/modules/equipamentos/service.py:424-444`
- **Descrição:** O router `instalar_item` declara `_: ExecucaoPermitida` e **descarta** o usuário autenticado — não o passa para o service. O service `instalar_item(db, item_id, aeronave_id, slot_id, data_instalacao)` instancia `Instalacao(...)` sem incluir o campo `usuario_id`, gerando o registro com `usuario_id=NULL`. Compare com `remover_item` (linha 446), que aceita e atribui `usuario_id=current_user.id`, e com `_efetivar_troca_no_slot` (linha 405), que utiliza `dados.usuario_id`. A coluna `Instalacao.usuario_id` existe justamente para auditar quem efetuou a movimentação.
- **Impacto:** Toda instalação registrada via `POST /equipamentos/itens/{item_id}/instalar` perde a rastreabilidade do executor. Em sistema aeronáutico, cada movimentação de S/N precisa ter usuário responsável identificado para auditoria. O Dashboard ("Movimentações Recentes" — `dashboard/service.py:160-193`) e o `listar_historico_recente` (`equipamentos/service.py:460-522`) exibirão `usuario_trigrama=NULL` para essas instalações, deixando "buracos" no histórico de inventário. A correção `e9c0a4` (RBAC) controla *quem pode chamar*; este bug invalida o registro *de quem chamou*.
- **Sugestão:** No router, trocar `_: ExecucaoPermitida` por `current_user: ExecucaoPermitida` e passar `usuario_id=current_user.id` ao service. No service, adicionar parâmetro `usuario_id: uuid.UUID` à assinatura e atribuir em `Instalacao(..., usuario_id=usuario_id)`. Adicionar teste que verifica `instalacao.usuario_id == current_user.id` após a chamada.
- **Hash:** `d4b8f1`

---

### ARQUITETURA - `ajustar_inventario_item` executa `db.rollback()` direto no service

- **Local:** `app/modules/equipamentos/service.py:321-330`
- **Descrição:** O service captura exceções do `flush` e chama `await db.rollback()` antes de devolver mensagem polida. O padrão do projeto é deixar a dependência `get_db()` (`bootstrap/dependencies.py:30-38`) gerenciar `commit/rollback` via try/except no generator. Um `rollback()` no meio do request descarta também qualquer escrita anterior feita na mesma transação e deixa a sessão SQLAlchemy em estado parcialmente inválido para operações subsequentes. Hoje a função é chamada isoladamente, mas o anti-padrão repete o problema já corrigido em `auth/service.py` (hash `a9f2b1`) e `efetivo/service.py` (hash `f3b7e9`).
- **Impacto:** Acoplamento do service à infraestrutura de transação. Se um futuro endpoint compor `ajustar_inventario_item` com outras escritas (ex.: log de auditoria, criação de evento), o rollback "engole" silenciosamente o trabalho anterior. Inconsistência de padrão dificulta manutenção e revisão.
- **Sugestão:** Remover o `try/except + rollback`. Para distinguir `"FOREIGN KEY constraint failed"`, deixar a `IntegrityError` propagar e tratá-la no router (ou converter em exceção de domínio levantada *após* o flush bem-sucedido). `get_db()` cuida do rollback ao detectar a exceção propagada.
- **Hash:** `e0c4d3`

---

### BUG - `hash_senha` trunca por caracteres em vez de bytes (bcrypt 72-byte limit)

- **Local:** `app/modules/auth/security.py:22-37` — funções `hash_senha` e `verificar_senha`
- **Descrição:** Para contornar o limite de 72 **bytes** do bcrypt, ambas as funções fazem `senha_plana[:72]`. Em Python, `[:72]` opera em **pontos de código (caracteres)**, não em bytes. Para senhas com caracteres não-ASCII (acentuação portuguesa, emojis, símbolos UTF-8 multibyte), 72 caracteres podem ocupar de 73 até ~288 bytes — passlib/bcrypt pode rejeitar (versões recentes com `truncate_error=True`) ou truncar internamente em ponto diferente. Como `verificar_senha` aplica o mesmo `[:72]` por caracteres, o cadastro e o login podem divergir após upgrades do passlib.
- **Impacto:** Usuário cuja senha contenha "ção", "á", emojis ou qualquer caractere multibyte pode (a) ter `_pwd_context.hash` levantando exceção mascarada como erro 500 no cadastro, (b) cadastrar com sucesso mas falhar autenticação após upgrade do passlib (mismatch entre o byte-truncate interno do passlib e o char-truncate da aplicação), ou (c) ter sua senha silenciosamente encurtada — reduzindo a entropia que o usuário acreditava ter. Risco de bloqueio em massa de contas após upgrade de dependência.
- **Sugestão:** Truncar em bytes preservando UTF-8 válido: `senha_bytes = senha_plana.encode("utf-8")[:72]; senha_ajustada = senha_bytes.decode("utf-8", errors="ignore")`. Aplicar idêntico em `hash_senha` e `verificar_senha`. Alternativamente (mais robusto), pré-hashear com SHA-256 antes do bcrypt: `bcrypt_input = base64.b64encode(hashlib.sha256(senha_plana.encode("utf-8")).digest())` (32 bytes raw → 44 bytes b64, sempre < 72) — elimina o limite e padroniza o tamanho. Adicionar teste com senha contendo "manutenção_aeronáutica🛩️" e ≥40 caracteres.
- **Hash:** `7b3f9a`
