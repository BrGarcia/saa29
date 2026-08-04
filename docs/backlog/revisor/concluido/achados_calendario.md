# Achados de Revisão — Módulo `calendario`

> Revisão conforme `docs/backlog/revisor.md`, com contexto de `docs/backlog/00_mapa_arquitetural.md`.
> Nenhum arquivo de código foi alterado nesta sessão de revisão.

> ## ✅ SESSÃO DE CORREÇÃO CONCLUÍDA — 04/08/2026
> 6/8 corrigidos, 1 não corrigido por decisão consciente do usuário (RISCO-04, aceito como
> está), 1 resolvido só por documentação/decisão sem mudança de código (DÚVIDA-08, assimetria
> proposital). Suite completa: 421 testes, 0 falhas (7 novos em `tests/test_calendario.py`).
> BUG-01 e BUG-02 têm a mesma causa raiz e foram corrigidos juntos (`UTCDateTime` em
> `models.py`). RISCO-03 foi corrigido com um desenho ligeiramente diferente do proposto: em vez
> de manter o pre-check e só adicionar SAVEPOINT, o pre-check foi removido (eliminando a janela
> TOCTOU pela raiz, não só mitigando-a) e o SAVEPOINT + `except IntegrityError` passou a ser a
> única fonte de verdade, preservando o `ValueError`/400 já existente (não um novo status),
> conforme a correção proposta no próprio achado. Status por item marcado inline em cada achado
> abaixo (campo `**Status:**`).

---

### [BUG-01] `update_event` pode comparar datetime aware com naive e derrubar a request com 500

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/calendario/service.py:304-312`
- **Eixo:** Contrato / Banco
- **Problema:** ao editar um evento enviando só um dos dois campos de data (ex.: só `end_date`, mantendo `start_date` implícito), o código faz `start_date = update_data.get("start_date", event.start_date)` — usando o valor **recarregado do banco** para o campo não enviado — e compara com `end_date`, que veio do payload Pydantic já parseado como `datetime` **aware** (com `tzinfo`, se o cliente mandou offset/`Z`). Por causa do BUG-02 abaixo, `event.start_date` volta do SQLite como **naive** (sem `tzinfo`). `end_date < start_date` entre um `datetime` aware e um naive levanta `TypeError: can't compare offset-naive and offset-aware datetimes` em Python — exceção que não é `ValueError`, `LookupError` nem `PermissionError`, logo não é capturada por nenhum `except` do router (`router.py:106-113`) e vira 500 genérico.
- **Consequência:** `PUT /api/v1/calendario/eventos/{id}` com apenas um dos dois campos de data no corpo (o caso mais comum de edição parcial — mover só o horário de término, por exemplo) quebra com erro interno em vez de 400, sem mensagem útil ao cliente.
- **Correção proposta:** normalizar `event.start_date`/`event.end_date` para aware (mesmo fuso, ex. UTC) antes da comparação — ou, melhor, resolver o BUG-02 na raiz (coluna/serialização), o que também corrige este caso.
- **Risco de regressão:** BAIXO — a correção só afeta o caminho que hoje quebra.
- **Precisa de teste antes?** SIM — nenhum teste em `tests/test_calendario.py` envia `CalendarEventUpdate` com apenas um dos dois campos de data.
- **Status:** ✅ CORRIGIDO, resolvendo o BUG-02 na raiz (opção sugerida como "melhor" na própria correção proposta) — depois disso, `event.start_date`/`event.end_date` são sempre aware, então a comparação em `update_event` (`service.py:311`) nunca mais mistura aware×naive. Teste: `test_atualizar_evento_com_apenas_end_date_nao_derruba_com_typeerror` (usa `db.expire(...)` para simular a releitura de uma request posterior, o cenário real que expunha o bug).

---

### [BUG-02] Datas de evento perdem `tzinfo` ao ir e voltar do SQLite — deslocamento de horário silencioso

- **Classificação:** BUG
- **Severidade:** ALTA
- **Arquivo:** `app/modules/calendario/models.py:75-81`; `app/modules/calendario/service.py:356`
- **Eixo:** Banco / Contrato
- **Problema:** `start_date`, `end_date`, `created_at`, `updated_at` e `deleted_at` usam `DateTime(timezone=True)`. No dialeto SQLite (driver `aiosqlite`), esse tipo não tem suporte nativo a timezone: o valor é serializado como string e, na leitura, o result-processor padrão do SQLAlchemy para SQLite **não recupera o offset** — o objeto que volta do banco é um `datetime` **naive**, mesmo que o valor gravado tivesse `tzinfo=UTC` (ex.: `event.deleted_at = datetime.now(timezone.utc)` em `service.py:356`). O schema `CalendarEventOut`/`CalendarEventPayload` então serializa esse naive como se fosse hora local/sem fuso.
- **Consequência:** um evento criado agora (objeto ainda "quente" na sessão, com `tzinfo`) e o mesmo evento relido em uma request posterior (naive, vindo do banco) podem ser serializados de forma diferente para o cliente. O front-end (`new Date(isoString)` em JS) interpreta uma string ISO sem offset como hora **local do navegador**, não UTC — cliente em fuso diferente do servidor vê o evento em horário deslocado do que foi realmente cadastrado. Este é o mesmo eixo de risco que o mapa (`00_mapa_arquitetural.md` §6) já documenta como resultado negativo para outros módulos, mas aqui há um caso concreto de dado gravado/lido de forma inconsistente, não apenas ausência de timezone.
- **Correção proposta:** ao ler o objeto de volta do banco (ou antes de serializar), normalizar explicitamente para UTC (`value.replace(tzinfo=timezone.utc)` sabendo que o dado é sempre gravado em UTC) — ou adotar um `TypeDecorator` centralizado que garanta round-trip com timezone, reaproveitável pelos outros módulos com o mesmo padrão de coluna.
- **Risco de regressão:** MÉDIO — qualquer lugar que hoje compara `datetime` de evento contra `datetime.now(timezone.utc)` precisa ser revisado junto.
- **Precisa de teste antes?** SIM — testar que uma data gravada com offset não-UTC (ex. `-03:00`) é lida de volta apontando para o mesmo instante absoluto.
- **Status:** ✅ CORRIGIDO com um `TypeDecorator` (`UTCDateTime`, `models.py`), escopo local a este módulo (não centralizado em `shared/core` — os outros módulos com o mesmo padrão de coluna não foram tocados nesta sessão). Cobre os dois lados do round-trip: `process_bind_param` converte qualquer `datetime` aware para UTC antes de gravar, `process_result_value` reanexa `tzinfo=UTC` na leitura se vier naive. Achado real encontrado ao escrever o teste: só corrigir a leitura (como a correção proposta sugeria como suficiente) **não bastava** — o dialeto SQLite também descarta o offset na gravação, então uma data gravada com `-03:00` sem normalizar antes voltava reinterpretada como UTC, apontando para um instante 3h errado. Aplicado a todas as colunas de data de `EventType` e `CalendarEvent`. Teste: `test_datas_evento_mantem_timezone_ao_reler_do_banco` (usa offset `-03:00` de propósito, para não passar "por acaso" com um valor que já nasceria em UTC).

---

### [RISCO-03] Checagem de nome duplicado de `EventType` é TOCTOU sobre índice UNIQUE

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/calendario/service.py:219-223,243-247`
- **Eixo:** Concorrência / Banco
- **Problema:** `create_event_type` e `update_event_type` fazem `SELECT ... WHERE name == ...` e só então decidem inserir/atualizar. `EventType.name` tem `unique=True` no model (`models.py:32`). Entre o `SELECT` e o `flush()`, duas requisições concorrentes com o mesmo nome podem ambas passar pela checagem e uma delas estourar `IntegrityError` no `flush()`.
- **Consequência:** `IntegrityError` não é `ValueError`, então não é capturado pelos `except ValueError` de `router.py:34-35,49-50` — a segunda request concorrente recebe 500 em vez do 400 esperado ("Já existe um tipo de evento com o nome...").
- **Correção proposta:** capturar `IntegrityError` no service (ou no router) e traduzir para o mesmo `ValueError`/400 já usado no caminho não concorrente.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** SIM — requer teste de concorrência (duas coroutines criando o mesmo nome) ou ao menos um teste que force `IntegrityError` diretamente.
- **Status:** ✅ CORRIGIDO, com um desenho ligeiramente diferente do proposto: em vez de manter o `SELECT` de pre-check e só adicionar o `except IntegrityError` por cima (o que deixaria a janela TOCTOU tecnicamente aberta, só mais estreita), o pre-check foi **removido** em `create_event_type`/`update_event_type` — o `UNIQUE` de `EventType.name` dentro de um `SAVEPOINT` (`db.begin_nested()`) passou a ser a única checagem, cobrindo o caminho comum e a corrida real com o mesmo código, sempre traduzindo `IntegrityError` para o mesmo `ValueError`/400 já usado (não um novo status — conforme a correção proposta pediu explicitamente). Testes: `test_criar_tipo_evento_com_nome_duplicado_levanta_valueerror_via_savepoint`, `test_atualizar_tipo_evento_com_nome_duplicado_levanta_valueerror_via_savepoint`. Achado real ao escrever o teste de update: depois que um `flush()` falha dentro de `begin_nested()` sobre um objeto **já persistente** (não recém-criado), a sessão fica presa (`PendingRollbackError`) para qualquer operação seguinte na mesma sessão — diferente do caminho de criação, onde a mesma sessão segue utilizável após a falha (verificado pelo teste de create, que reaproveita a sessão em seguida). Isso não afeta produção (cada request usa uma sessão nova, e `get_db` já faz `rollback()` completo em qualquer exceção — `bootstrap/dependencies.py:35-36`), mas está fora do escopo deste achado corrigir a reutilização de sessão pós-falha; documentado inline no teste.

---

### [RISCO-04] Limite de 5.000 registros por consulta trunca o calendário sem sinalizar ao cliente

- **Classificação:** RISCO
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/calendario/service.py:22-23,114,119-129,156,161-171`
- **Eixo:** Contrato / Performance
- **Problema:** `_get_calendar_events` e `_get_inspection_events` aplicam `.limit(_QUERY_LIMIT)` (5.000) como proteção contra DoS e logam um `logger.warning` quando o limite é atingido — mas a API não expõe esse truncamento ao cliente (sem campo `truncated`, sem header, sem 206). Além disso, a detecção `len(events) == _QUERY_LIMIT` é uma aproximação: se existirem exatamente 5.000 eventos no período sem estarem truncados (caso raro, mas possível), o log de alerta dispara um falso positivo; e se existirem mais de 5.000, o `warning` é o único sinal — em nenhum log dos dois pontos aparece o total real disponível (seria necessário um `COUNT(*)` separado para saber quanto foi cortado).
- **Consequência:** em um range de datas muito populado (ex.: 366 dias, o máximo permitido pelo router), eventos podem desaparecer silenciosamente da grade do calendário sem que o usuário ou o time de operação percebam — só apareceria em log de servidor, que ninguém no time operacional vê.
- **Correção proposta:** quando o limite for atingido, sinalizar isso no payload de resposta (ex. campo `truncated: bool` em algum envelope, ou reduzir a paginação a um range obrigatório menor) em vez de apenas logar.
- **Risco de regressão:** BAIXO — é uma adição, não uma mudança de comportamento existente.
- **Precisa de teste antes?** NÃO (mudança aditiva, mas exige decisão de contrato de API — ver pergunta ao desenvolvedor).
- **Status:** 🚫 NÃO CORRIGIDO — decisão consciente do usuário nesta sessão: aceitar como está (proteção contra DoS, range já limitado a 366 dias pelo router, 5.000 eventos num único calendário é cenário extremo). Mantido apenas o log de alerta existente; risco registrado, sem mudança de contrato de API.

---

### [MELHORIA-05] Terceiro dialeto de erro de domínio: `LookupError`/`PermissionError` nativos, só neste módulo

- **Classificação:** MELHORIA
- **Severidade:** MÉDIA
- **Arquivo:** `app/modules/calendario/service.py:239,263,284,306,316,337,365,371,390`; `app/modules/calendario/router.py:47-50,62-65,91-96,108-113`
- **Eixo:** Arquitetura
- **Problema:** confirma o que o mapa arquitetural (`00_mapa_arquitetural.md` §5, linha da tabela "Erro de domínio no service") já registrou como fato do projeto: `calendario` é o único módulo que usa `LookupError` e `PermissionError`, exceções nativas do Python reaproveitadas com semântica de domínio, enquanto `inspecoes`/`equipamentos` usam `domain_exc.*` tipado e `panes`/`aeronaves` usam `ValueError` cru. Um terceiro padrão, sem nenhum dos outros módulos referenciá-lo.
- **Consequência:** quem for reusar lógica de erro entre módulos (ex. um middleware genérico de tradução de exceção de domínio para HTTP) precisa conhecer três convenções diferentes; `LookupError`/`PermissionError` também são superclasses usadas pela stdlib para outros fins, então um `except LookupError` genérico em código futuro pode capturar mais do que o pretendido.
- **Correção proposta:** migrar para as exceções tipadas de `app/shared/core/exceptions.py` (`domain_exc.EntidadeNaoEncontradaError`, etc.), alinhando com o padrão já adotado por `inspecoes` e `equipamentos` — é uma correção arquitetural transversal, não urgente isoladamente.
- **Risco de regressão:** MÉDIO — troca o tipo de exceção capturado em 4 pontos do router; qualquer teste que dependa do tipo de exceção (não só do status HTTP) precisa ser revisto.
- **Precisa de teste antes?** SIM.
- **Status:** ✅ CORRIGIDO, escopo confirmado com o usuário (migrar agora, contido a este módulo — sem tocar `inspecoes`/`equipamentos`/`panes`). `LookupError`→`domain_exc.EntidadeNaoEncontradaError` (404), `PermissionError`→`domain_exc.PermissaoNegadaError` (403) em todo `calendario/service.py`. Como essas exceções já carregam seu próprio `status_code` (são `HTTPException`), o router não precisa mais de `except LookupError`/`except PermissionError` — os 4 pontos que faziam essa tradução manual (`router.py`) foram simplificados, mantendo só os `except ValueError` (que continuam mapeando para 400, fora do escopo desta migração). Testes: `test_update_event_type_inexistente_levanta_domain_exc_tipado`, `test_create_event_para_terceiro_sem_privilegio_levanta_domain_exc_tipado`.

---

### [MELHORIA-06] `_get_task_events` é função morta: descarta os parâmetros e sempre retorna lista vazia

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/calendario/service.py:197-203`
- **Eixo:** Arquitetura
- **Problema:** `_get_task_events(db, start_date, end_date)` faz `_ = (db, start_date, end_date); return []` — recebe os três parâmetros só para descartá-los, sem nenhum `TODO`/comentário explicando a intenção futura. É chamada incondicionalmente em `get_events` (`service.py:90`) a cada `GET /eventos`.
- **Consequência:** nenhuma além de uma chamada de função supérflua por request — sem efeito funcional, mas é ruído para quem lê o código tentando entender de onde vêm os eventos do calendário (anti-padrão #9 do `revisor.md`, "código morto").
- **Correção proposta:** remover a chamada e a função até que a fonte de "eventos de tarefa" seja implementada, ou adicionar um comentário `TODO` com contexto (ticket/decisão) se for propositalmente um placeholder.
- **Risco de regressão:** BAIXO.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO. `_get_task_events` e sua chamada em `get_events` removidas. Teste: `test_get_task_events_foi_removida` (trava a remoção, evitando que a função morta seja reintroduzida sem querer).

---

### [MELHORIA-07] Router de `event_types` devolve objeto ORM cru; exceções relançadas sem `from exc`

- **Classificação:** MELHORIA
- **Severidade:** BAIXA
- **Arquivo:** `app/modules/calendario/router.py:17-23,26-36,38-50`
- **Eixo:** Arquitetura / Tratamento de erros
- **Problema:** dois achados relacionados no mesmo trecho. (1) `listar_tipos_evento`, `criar_tipo_evento` e `atualizar_tipo_evento` retornam o objeto `EventType` (ORM) direto, deixando o FastAPI serializar via `response_model` — confirmando o outro item de divergência do mapa (`00_mapa_arquitetural.md` §5, "Serialização de resposta"): `calendario` é o único módulo que não chama `Schema.model_validate(...)` explicitamente antes de retornar. (2) todos os `raise HTTPException(...)` dentro dos blocos `except ValueError as exc` / `except LookupError as exc` do arquivo (linhas 35, 48, 50, 64, 65, 92, 94, 96, 109, 111, 113) não usam `raise ... from exc`, perdendo o traceback original da exceção capturada (checklist **D** do `revisor.md`).
- **Consequência:** (1) é hoje inofensivo porque o `response_model` faz a validação, mas mascara implicitamente o mesmo campo que a serialização explícita torna visível (ex. algum campo interno futuro adicionado ao model vazaria até alguém notar via `response_model`); (2) dificulta debug em produção — um erro 400/404/403 no log perde o `__cause__` que apontaria para a exceção real de origem.
- **Correção proposta:** (1) trocar os `return` por `schemas.EventTypeOut.model_validate(...)` explícito, alinhando com o padrão da maioria dos módulos; (2) adicionar `from exc` em todos os `raise HTTPException` dentro de blocos `except ... as exc`.
- **Risco de regressão:** BAIXO — ambas as mudanças são mecânicas e não alteram comportamento observável.
- **Precisa de teste antes?** NÃO.
- **Status:** ✅ CORRIGIDO, os dois pontos. (1) `listar_tipos_evento`, `criar_tipo_evento` e `atualizar_tipo_evento` agora chamam `schemas.EventTypeOut.model_validate(...)` explicitamente antes de retornar (endpoints de `eventos` não foram tocados — fora da linha citada por este achado). (2) todos os `raise HTTPException(...)` restantes dentro de `except ValueError as exc` (os únicos que sobraram depois da migração do MELHORIA-05) agora usam `from exc`. Sem teste novo — mudanças mecânicas, comportamento observável inalterado, cobertas pelos testes de endpoint já existentes.

---

### [DÚVIDA-08] `ENCARREGADO` pode criar/editar/transferir eventos de terceiros, mas só `ADMINISTRADOR` pode excluir

- **Classificação:** DÚVIDA
- **Severidade:** —
- **Arquivo:** `app/modules/calendario/service.py:283-284,305-306,314-317,336-337`
- **Eixo:** Segurança
- **Problema:** `has_privilege` (papéis `ENCARREGADO` e `ADMINISTRADOR`, via `PRIVILEGED_FUNCTIONS`) autoriza criar evento para terceiro (283-284), editar evento de terceiro (305-306) e transferir a titularidade do evento (`owner_user_id`, 314-317) — inclusive lendo o campo `notes` de um evento privado de outro usuário, já que `_should_censor` só censura para quem não é dono nem privilegiado. Mas a exclusão (`delete_event`, 336-337) exige especificamente `ADMIN_FUNCTIONS` (só `ADMINISTRADOR`), excluindo `ENCARREGADO`.
- **Consequência:** um `ENCARREGADO` tem mais alcance de escrita (criar/editar/ler notas privadas/transferir) do que de exclusão sobre o mesmo recurso — assimetria que pode ser proposital (excluir é destrutivo e sem soft-undo visível na UI) ou pode ser um descuido ao copiar `ADMIN_FUNCTIONS` em vez de `PRIVILEGED_FUNCTIONS` na função de delete.
- **Correção proposta:** nenhuma até confirmação — se intencional, documentar a assimetria no docstring de `delete_event`; se não, alinhar `delete_event` para aceitar `PRIVILEGED_FUNCTIONS` como os demais métodos do módulo.
- **Risco de regressão:** MÉDIO se a resposta for "alinhar" — amplia quem pode excluir.
- **Precisa de teste antes?** SIM, se a decisão for mudar o comportamento.
- **Resposta do usuário:** proposital — documentar, não alinhar. Excluir é destrutivo e não tem tela de restauração visível para o soft-delete (10.5), então faz sentido restringir mais a exclusão do que a edição.
- **Status:** ✅ RESOLVIDO por documentação, sem mudança de comportamento. Assimetria documentada inline em `delete_event` (`service.py`). Nenhum teste novo — comportamento não mudou.

---

## Resumo

- Total de achados: 8
- BUG: 2 (CRÍTICA: 0, ALTA: 2, MÉDIA: 0, BAIXA: 0)
- RISCO: 2
- MELHORIA: 3
- DÚVIDA: 1
- **Corrigidos: 6/8** — 1 não corrigido por decisão consciente do usuário (RISCO-04, aceito como
  está) e 1 resolvido só por documentação (DÚVIDA-08, assimetria proposital, sem mudança de
  comportamento)

## Arquivos revisados

- `app/modules/calendario/__init__.py`
- `app/modules/calendario/models.py`
- `app/modules/calendario/schemas.py`
- `app/modules/calendario/service.py`
- `app/modules/calendario/router.py`
- `tests/test_calendario.py` (para verificar cobertura existente)
- `app/bootstrap/dependencies.py`, `app/modules/auth/roles.py`, `app/shared/core/enums.py` (contexto de RBAC/enums usados pelo módulo)
- `migrations/versions/20260508_1200_c4d5e6f7a8b9_add_calendario_module.py` e
  `20260511_0900_d1e2f3a4b5c6_calendario_privacidade_e_soft_delete.py`

## Não revisado / limitações

- Rate limiting: nenhum endpoint de `calendario` tem `@limiter.limit(...)` — não é um achado isolado do módulo, é o padrão de 116 dos 117 endpoints do sistema (`00_mapa_arquitetural.md` §5/§7.5), citado aqui só para registro.
- Ausência de camada `repositories/`: idem — padrão de 100% dos módulos, não é achado deste módulo (mapa §1).
- O front-end (`app/web/static/js/*.js`, templates de calendário) não foi lido em profundidade; o efeito do BUG-02 sobre a UI foi inferido do comportamento padrão de `new Date()` em JavaScript, não de leitura do JS específico da tela de calendário.
- `_get_task_events` (MELHORIA-06) sugere que existe um conceito de "eventos de tarefa" ainda não implementado — não há como avaliar se algum outro módulo (`inspecoes`?) já cobre essa necessidade sem uma investigação maior, fora do escopo desta sessão.

## Perguntas para o desenvolvedor (respondidas)

- **RISCO-04:** o truncamento silencioso em 5.000 registros é aceitável como está (proteção contra DoS, achado registrado apenas para consciência) ou deveria virar um sinal explícito no contrato da API? **Resposta: aceitar como está.** Não corrigido.
- **DÚVIDA-08:** a assimetria entre "quem pode editar/transferir" (`ENCARREGADO`+`ADMINISTRADOR`) e "quem pode excluir" (só `ADMINISTRADOR`) é uma decisão de produto deliberada? **Resposta: proposital — documentar, não alinhar.** Docstring de `delete_event` atualizado.
- **MELHORIA-05** (pergunta adicional desta sessão de correção, já que o achado marcava como "não urgente isoladamente"): migrar `LookupError`/`PermissionError` para `domain_exc` agora, contido a este módulo, ou deixar como risco documentado? **Resposta: migrar agora, escopo contido a este módulo.** Implementado.
