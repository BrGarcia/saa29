# Relatório de Auditoria — SAA29 (claude_google)

Este relatório contém achados **complementares** ao `docs/relatorio/claude.md`, identificados por análise independente. Não há duplicidade com os hashes já registrados naquele arquivo (`c5a1b9`, `9d3f2a`, `b7e4c1`, `4f8d6e`, `8c2b5d`, etc.).

---

## 2026-05-11

### [CORRIGIDO] BUG-CRÍTICO — service.py contém código duplicado que causa NameError em runtime

- **Local:** `app/modules/calendario/service.py:330-577`
- **Descrição:** O arquivo contém as funções corrigidas (linhas 1-327) seguidas de uma cópia **integral das funções antigas** (linhas 330-577), incluindo `has_privilege`, `is_owner`, `should_censor`, `format_event_for_user`, `get_events`, `_get_calendar_events`, `_get_inspection_events`, `_get_task_events`, `list_event_types`, `create_event`, `update_event`, `delete_event`, `_ensure_user_exists`, `_ensure_event_type_exists` e `_get_event_or_raise`. As funções duplicadas na metade inferior referenciam `PRIVILEGED_ROLES` e `ADMIN_ROLES` (variáveis que foram removidas na metade superior), causando `NameError` se Python resolver a versão inferior durante a importação. Além disso, a metade antiga contém todas as vulnerabilidades que as correções 10.1–10.5 pretendiam eliminar: sem filtro de status, sem soft-delete, com alias `"ADMIN"`, sem `.limit()`, com `db.delete()` físico, e com vazamento de `owner_trigram` em eventos censurados.
- **Impacto:** O módulo inteiro pode falhar com `NameError` em runtime ao importar o service (se Python avaliar as definições duplicadas), ou — pior — as funções antigas podem sobrescrever as corrigidas durante a importação do módulo (Python executa top-to-bottom e a última definição prevalece). Neste caso, **todas as correções 10.1–10.5 estariam efetivamente revertidas** em produção silenciosamente: a censura de privacidade voltaria a vazar dados, o delete seria físico, e o filtro de status seria removido. Risco de regressão total.
- **Sugestão:** Remover as linhas 330-577 integralmente. Essas funções são uma cópia residual da versão pré-correção que não deveria existir. Após a remoção, validar que o módulo importa sem erro e que os testes de calendário passam.
- **Hash:** `a3f7d2`

---

### [BUG] DASHBOARD — mini-calendário do dashboard filtra eventos com campos errados

- **Local:** `app/web/static/js/dashboard.js:290-295` — função `renderCalendarView`
- **Descrição:** O mini-calendário do dashboard consome o endpoint `/calendario/eventos` e tenta filtrar eventos por dia usando os campos `e.data_inicio`, `e.data_prevista` e `e.data`. Porém, o schema `CalendarEventPayload` retorna os campos `start` e `end` (não `data_inicio`, `data_prevista` nem `data`). O resultado: `new Date(undefined)` retorna `Invalid Date`, e o filtro `eDate.getDate() === currentDate.getDate()` retorna `false` para **todos** os eventos. Nenhum indicador de evento jamais aparece no mini-calendário do dashboard.
- **Impacto:** O mini-calendário do dashboard é puramente decorativo — mostra os dias da semana mas nunca exibe indicadores de eventos, independentemente de quantos eventos existam. O usuário vê um calendário vazio e pode concluir que não há eventos, quando na verdade o filtro no frontend está quebrado.
- **Sugestão:** Substituir `e.data_inicio || e.data_prevista || e.data` por `e.start` (que é o campo real do `CalendarEventPayload`). Para eventos de dia inteiro, usar `new Date(e.start)` e `new Date(e.end)` para verificar interseção com o dia, análogo ao que `calendario.js:199-202` faz corretamente na função `eventsForDay`.
- **Hash:** `e2b4c8`

---

### [BUG] DASHBOARD — mini-calendário classifica tipo de evento com campo inexistente

- **Local:** `app/web/static/js/dashboard.js:300-303` — função `renderCalendarView`
- **Descrição:** A lógica de coloração dos indicadores verifica `e.tipo` contra `'INSPECAO'`, `'VENCIMENTO'` e `'PANE'`. Porém, o `CalendarEventPayload` não possui campo `tipo` — o campo equivalente é `source` (valores: `"calendario"`, `"inspecao"`). Resultado: `e.tipo` é sempre `undefined`, nenhuma classe CSS (`insp`, `venc`, `pane`) é aplicada, e todos os indicadores (caso o bug anterior seja corrigido) teriam aparência idêntica — sem distinção visual entre tipos de evento.
- **Impacto:** Perda total da funcionalidade de distinção visual por cor no mini-calendário do dashboard. Mesmo corrigindo o bug de filtragem (`e2b4c8`), os indicadores seriam todos da mesma cor genérica.
- **Sugestão:** Substituir `e.tipo` por `e.source` e ajustar os valores comparados: `if (e.source === 'inspecao') typeClass = 'insp';`. Para eventos do calendário próprio, usar `e.icon` ou `e.backgroundColor` diretamente para diferenciar visualmente. Exemplo: `else if (e.source === 'calendario') typeClass = 'cal';`.
- **Hash:** `f1c9a5`

---

### [BUG] CALENDÁRIO — seed de tipos não preenche `private_color` para tipos privados existentes

- **Local:** `scripts/seed/seed_calendario.py:33-44` — função `run`
- **Descrição:** O seed atualiza `visibility_type`, `color`, `icon` e `active` para tipos existentes, mas **não atualiza nem preenche** o novo campo `private_color` introduzido pela migração 10.2. A migração Alembic preenche `private_color='#9CA3AF'` para tipos com `visibility_type='private'` existentes no momento da migração, mas se o seed rodar **após** a migração (cenário de rebuild limpo com `init_db.py`), o tipo "Consulta" será criado com `private_color=None`. O service faz fallback com `event.event_type.private_color or "#9CA3AF"`, então o impacto visual é mascarado — porém o campo fica inconsistente entre deploys com migração e deploys limpos.
- **Impacto:** Inconsistência de dados entre ambientes (produção migrada vs. desenvolvimento com seed limpo). Se no futuro o fallback `or "#9CA3AF"` for removido ou a lógica depender de `private_color IS NOT NULL` para determinar se um tipo é privado, o comportamento divergirá entre ambientes.
- **Sugestão:** Adicionar `"private_color": "#9CA3AF"` ao item "Consulta" em `BASE_EVENT_TYPES` e atualizar o campo no bloco `else` do seed: `existing.private_color = item.get("private_color")`.
- **Hash:** `d7e3b1`

---

### [SEGURANÇA] CALENDÁRIO — `update_event` permite escrever campos protegidos via `setattr` genérico

- **Local:** `app/modules/calendario/service.py:258-259` (bloco corrigido) e `528-529` (bloco duplicado)
- **Descrição:** A função `update_event` itera sobre `data.model_dump(exclude_unset=True)` e executa `setattr(event, field, value)` para cada campo. O schema `CalendarEventUpdate` não inclui campos como `created_by_user_id`, `created_at`, `deleted_at` ou `deleted_by_user_id` — então em teoria estão protegidos pela validação do Pydantic. **Porém**, o campo `notes` é aceito sem limitação de tamanho. O schema define `notes: str | None = None` sem `max_length`. Um payload malicioso com `notes` contendo megabytes de texto será aceito, serializado e persistido no campo `Text` do banco sem restrição.
- **Impacto:** Permite armazenamento ilimitado de dados no campo `notes`, potencializando consumo de disco e memória na serialização da resposta. Em cenário de abuso, um cliente poderia enviar repetidamente payloads com `notes` de vários MB, inflando o banco de dados. Embora o impacto direto seja limitado pelo tamanho do request (configuração do uvicorn/reverse proxy), a falta de validação no schema é uma lacuna defensiva.
- **Sugestão:** Adicionar `max_length` ao campo `notes` em `CalendarEventCreate` e `CalendarEventUpdate`: `notes: str | None = Field(default=None, max_length=2000)`. O valor de 2000 caracteres é compatível com o campo `Text` do modelo e suficiente para justificativas operacionais. Adicionar o mesmo em `CalendarEventOut` como documentação do contrato.
- **Hash:** `b8a1f4`

---
