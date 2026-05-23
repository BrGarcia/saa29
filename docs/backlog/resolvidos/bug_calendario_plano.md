# Plano de correcao - Bug Calendario

## Diagnostico

O problema tem duas causas confirmadas e uma incompatibilidade secundaria no dashboard.

1. Dashboard chama uma rota inexistente

- `app/web/static/js/dashboard.js` usa:
  - `GET /calendario/eventos?...`
- O router do calendario esta registrado em `app/bootstrap/main.py` apenas com:
  - `prefix="/api/v1/calendario"`
- Portanto a rota real e:
  - `GET /api/v1/calendario/eventos?...`

Resultado: o Dashboard recebe `404 Not Found` antes mesmo de chegar ao backend do modulo de calendario.

2. Pagina Calendario chama a rota correta, mas o backend quebra no agregador de inspecoes

- `app/web/static/js/calendario.js` usa corretamente:
  - `GET /api/v1/calendario/eventos?...`
- O endpoint entra em `app/modules/calendario/router.py::listar_eventos`.
- O router chama `service.get_events(...)`.
- `service.get_events(...)` agrega:
  - eventos proprios do calendario;
  - DPE de inspecoes;
  - tarefas futuras.
- A falha esta em `app/modules/calendario/service.py::_get_inspection_events`:
  - `from app.modules.inspecoes.models import Inspecao, StatusInspecao`
- `StatusInspecao` nao existe em `app.modules.inspecoes.models`.
- O enum correto esta em:
  - `app.shared.core.enums.StatusInspecao`

Resultado: a chamada a `/api/v1/calendario/eventos` levanta `ImportError` em tempo de execucao e responde `500 Internal Server Error`.

Confirmacao local:

- Comando executado:
  - `venv/bin/python -m pytest tests/test_calendario.py -q`
- Resultado relevante:
  - `ImportError: cannot import name 'StatusInspecao' from 'app.modules.inspecoes.models'`
  - falhas em `test_router_lista_eventos_com_censura_backend` e `test_get_eventos_agrega_dpe_de_inspecoes`

3. Mesmo apos corrigir a rota do Dashboard, o mini-calendario ainda nao renderizaria eventos corretamente

O contrato retornado por `CalendarEventPayload` usa:

- `start`
- `end`
- `source`
- `title`
- `backgroundColor`
- `icon`
- `owner_trigram`

Mas `dashboard.js` filtra/renderiza usando campos antigos/inexistentes:

- `data_inicio`
- `data_prevista`
- `data`
- `tipo`
- `titulo`
- `descricao`

Resultado esperado apos corrigir apenas a URL: a requisicao deixa de dar 404, mas os indicadores do Dashboard podem continuar vazios ou sem classe visual porque `new Date(undefined)` gera `Invalid Date` e `e.tipo` e sempre `undefined`.

## Plano de correcao

### 1. Padronizar o frontend no endpoint versionado

Arquivo:

- `app/web/static/js/dashboard.js`

Alterar a chamada:

- de `/calendario/eventos?...`
- para `/api/v1/calendario/eventos?...`

Decisao: manter `/api/v1/calendario` como rota canonica, porque:

- o router ja esta registrado assim em `app/bootstrap/main.py`;
- a pagina Calendario ja usa esse prefixo;
- os testes existentes usam `CALENDARIO_URL = "/api/v1/calendario"`;
- criar alias `/calendario/eventos` manteria duas rotas para o mesmo contrato e preservaria a divergencia.

### 2. Corrigir o import do enum de status de inspecao

Arquivo:

- `app/modules/calendario/service.py`

Alterar o import lazy dentro de `_get_inspection_events`:

```python
from app.modules.inspecoes.models import Inspecao
from app.shared.core.enums import StatusInspecao
```

Manter o import lazy de `Inspecao` dentro da funcao para preservar a intencao atual de evitar ciclo entre modulos.

### 3. Ajustar o mini-calendario ao contrato real do endpoint

Arquivo:

- `app/web/static/js/dashboard.js`

Trocar a filtragem por dia para usar intersecao de periodo, alinhada com `calendario.js::eventsForDay`:

- usar `new Date(e.start)` e `new Date(e.end)`;
- considerar evento visivel no dia se `start < dayEnd && end >= dayStart`;
- evitar `data_inicio || data_prevista || data`.

Trocar a classificacao visual:

- usar `e.source` em vez de `e.tipo`;
- mapear `source === "inspecao"` para classe `insp`;
- mapear `source === "calendario"` para uma classe propria, ou usar `backgroundColor` inline no indicador;
- manter abertura para futuras fontes (`vencimento`, `pane`, `tarefa`) se o backend passar a emiti-las.

Trocar o texto do tooltip:

- usar `e.title`;
- opcionalmente complementar com `[owner_trigram]`, `icon` e horario;
- remover dependencias de `titulo` e `descricao`.

### 4. Atualizar testes que estao fora do contrato atual de privacidade

Arquivo:

- `tests/test_calendario.py`

Ha uma falha independente do 500:

- `test_rbac_censura_privado_para_terceiro_sem_privilegio` espera `owner_trigram == "OWN"`;
- `format_event_for_user` atualmente retorna `owner_trigram=None` para evento privado de terceiro.

O comportamento do codigo atual e coerente com a protecao de privacidade ja documentada em `docs/relatorio/claude.md`: nao vazar identidade do dono em evento privado censurado.

Plano:

- atualizar o teste para esperar `owner_trigram is None`;
- atualizar tambem o teste de router que valida censura backend;
- manter `title == "Particular"`, `notes is None`, `event_type_id is None`, `owner_user_id is None`, `can_edit is False`, `can_delete is False`;
- validar cor neutra via `backgroundColor == private_color or "#9CA3AF"`, se aplicavel.

### 5. Checar migracao do banco em ambiente local/producao

O modelo atual de calendario referencia colunas adicionadas por migracao posterior:

- `event_types.private_color`
- `calendar_events.deleted_at`
- `calendar_events.deleted_by_user_id`

Migracao relevante:

- `migrations/versions/20260511_0900_d1e2f3a4b5c6_calendario_privacidade_e_soft_delete.py`

Antes de validar no navegador, confirmar que o banco usado pela aplicacao recebeu essa migracao. Se nao recebeu, a rota tambem pode responder 500 por erro SQL ao consultar colunas inexistentes.

Verificacao recomendada:

- `venv/bin/alembic current`
- `venv/bin/alembic upgrade head`
- repetir `GET /api/v1/calendario/eventos?...`

## Sequencia de implementacao

1. Corrigir `StatusInspecao` em `app/modules/calendario/service.py`.
2. Corrigir URL do Dashboard para `/api/v1/calendario/eventos`.
3. Corrigir parse/render do mini-calendario para usar `start`, `end`, `source`, `title`.
4. Atualizar testes de privacidade do calendario para o contrato vigente.
5. Rodar testes focados:
   - `venv/bin/python -m pytest tests/test_calendario.py -q`
6. Fazer verificacao manual:
   - abrir Dashboard;
   - confirmar ausencia de `GET /calendario/eventos` no console;
   - confirmar `GET /api/v1/calendario/eventos` com `200`;
   - abrir pagina Calendario;
   - confirmar ausencia de toast "Erro desconhecido na API";
   - confirmar renderizacao de eventos e DPE de inspecoes.

## Criterios de aceite

- Dashboard nao chama mais `/calendario/eventos`.
- Dashboard recebe `200` de `/api/v1/calendario/eventos`.
- Pagina Calendario recebe `200` de `/api/v1/calendario/eventos`.
- Backend nao levanta `ImportError` ao agregar DPE de inspecoes.
- Mini-calendario renderiza eventos usando `start/end/source/title`.
- Nao ha toast de erro ao abrir a pagina Calendario.
- `tests/test_calendario.py` passa.
- Nenhuma alteracao de CSP e necessaria.
