# Plano de Implementação — Módulo de Inspeções

> **Projeto:** SAA29 — Sistema de Apoio à Aviônica A-29  
> **Data:** 2026-04-25  
> **Status:** Implementação inicial isolada iniciada em 2026-04-29  

---

## 0. Estado Atual da Implementação

Em `2026-04-29`, foi iniciado um scaffold backend isolado em `app/modules/inspecoes/`.

Arquivos criados:

- `app/modules/inspecoes/__init__.py`
- `app/modules/inspecoes/models.py`
- `app/modules/inspecoes/schemas.py`
- `app/modules/inspecoes/service.py`
- `app/modules/inspecoes/router.py`

Escopo implementado:

- modelos ORM locais para `TipoInspecao`, `TarefaTemplate`, `Inspecao` e `InspecaoTarefa`;
- schemas Pydantic e enums locais ao módulo, sem alterar `app/shared/core/enums.py`;
- service com CRUD inicial, abertura de inspeção com instanciação de tarefas, bloqueio de duplicidade ativa, atualização de tarefa com rastreabilidade, cancelamento e conclusão condicionada a tarefas obrigatórias;
- router FastAPI definido, mas ainda não registrado no app principal.

Isolamento mantido:

- não houve alteração em `app/bootstrap/main.py`;
- não houve import dos modelos de inspeção no bootstrap;
- não houve migration Alembic;
- não houve alteração em `Aeronave`, `Usuario`, `base.html`, `configuracoes.html`, rotas web ou frontend ativo;
- o módulo não altera o schema do banco nem aparece na API ativa enquanto não for registrado explicitamente.

Validação executada:

- `venv/bin/python -m py_compile app/modules/inspecoes/...`
- import de `app.modules.inspecoes.models`, `schemas`, `service` e `router`;
- `sqlalchemy.orm.configure_mappers()` com modelos principais carregados.
- `venv/bin/python -m pytest tests/unit/test_inspecoes.py -q` (`12 passed`);
- `venv/bin/python -m pytest tests/unit -q` (`88 passed`).

---

## 1. Visão Geral

O módulo gerencia eventos de inspeções programadas das aeronaves A-29. O modelo suporta a aplicação de **múltiplos tipos de inspeção** em um único **evento** (ex: combinar Inspeção Y com 2Y e 4A), unificando e deduplicando as tarefas com base em um **catálogo central**.

---

## 2. Modelagem de Dados

Conforme a arquitetura estabelecida, criar em `app/modules/inspecoes/models.py`:

1. **`tipos_inspecao`**: Tipos (Y, 2Y, A, etc). Campos: `id`, `codigo`, `nome`, `descricao`, `ativa`.
2. **`tarefas_inspecao`**: Catálogo de tarefas (evita duplicação). Campos: `id`, `nome`, `descricao`, `referencia`, `ativa`.
3. **`tipos_inspecao_tarefas`**: Vínculo N:N. Campos: `id`, `tipo_inspecao_id`, `tarefa_id`, `ordem`, `obrigatoria`.
4. **`inspecao_eventos`**: Evento de manutenção da aeronave. Campos: `id`, `aeronave_id`, `status` (`ABERTA`, `EM_EXECUCAO`, `CONCLUIDA`, `CANCELADA`), `aberta_por_id`, `aberta_em`, `concluida_em`, `observacao`.
5. **`inspecao_evento_tipos`**: Tipos aplicados ao evento (N:N). Campos: `id`, `evento_id`, `tipo_inspecao_id`.
6. **`inspecao_tarefas`**: Snapshot das tarefas instanciadas. Campos: `id`, `evento_id`, `tarefa_id` (nullable), `descricao` (copiada do catálogo), `origem` (`TEMPLATE` | `MANUAL`), `status` (`PENDENTE`, `EM_EXECUCAO`, `CONCLUIDA`), `executada_por_id`, `executada_em`, `pane_id` (nullable), `observacao`.

---

## 3. Regras de Negócio (RN)

- **RN-01 (Unificação e Snapshot)**: Ao abrir um evento com múltiplos tipos, buscar tarefas associadas, **deduplicar** por `tarefa_id`, e instanciar em `inspecao_tarefas` copiando a `descricao` (snapshot) e definindo `origem='TEMPLATE'`.
- **RN-02 (Tarefas Manuais)**: Permite adicionar tarefas de `origem='MANUAL'` diretamente ao evento (`tarefa_id` nulo).
- **RN-03 (Execução)**: Ao concluir uma tarefa, o sistema autocompleta `executada_por_id` e `executada_em`.
- **RN-04 (Integração com Panes)**: Se houver anomalia, uma Pane deve ser criada e vinculada via `inspecao_tarefas.pane_id`.
- **RN-05 (Status Aeronave)**: A aeronave muda para `INSPEÇÃO` na abertura do evento. Ao concluir, retorna para `DISPONIVEL` (ou `INDISPONIVEL` caso restem panes impeditivas).
- **RN-06 (Fechamento do Evento)**: O evento só pode ser concluído se todas as tarefas estiverem resolvidas (`CONCLUIDA`).

---

## 4. Segurança e RBAC

O SAA29 exige controle de acesso via decorador `@require_roles`:
- **Administrador / Encarregado**: Possuem acesso total. Podem gerenciar o catálogo, criar/editar tipos, e abrir/fechar/cancelar eventos de inspeção.
- **Mantenedor**: Possui acesso restrito. Pode visualizar eventos em andamento e executar tarefas, bem como adicionar tarefas manuais ou relatar panes.

---

## 8. Página de Configurações — Seção Inspeções

Adicionar novo card na grade do `configuracoes.html`:

```
┌─────────────────────────────────────────────┐
│ 🔍 Inspeções                                │
│                                             │
│ Cadastro de tipos de inspeção e definição   │
│ das tarefas padrão para cada tipo.          │
│                                             │
│ [+ Cadastrar Tipo de Inspeção]              │
│ [✏ Editar Tipo de Inspeção]                 │
│ [📋 Gerenciar Tarefas do Tipo]              │
└─────────────────────────────────────────────┘
```

### Modais necessários:
1. **Modal Cadastrar/Editar Tipo** — código, nome, descrição
2. **Modal Gerenciar Tarefas** — listar tarefas do tipo selecionado, adicionar/remover/reordenar (drag-and-drop ou setas)

---

## 9. Página de Listagem (`/inspecoes`)

### Layout proposto:

```
┌──────────────────────────────────────────────────────────────────┐
│  Filtros: [Tipo ▼] [Status ▼] [Aeronave ▼]  [🔍 Buscar]        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  FAB 5916   │  │  FAB 5902   │  │  FAB 5700   │              │
│  │  IF-100H    │  │  IPG        │  │  IF-50H     │              │
│  │  ██████░░   │  │  █████████░ │  │  ████░░░░░  │              │
│  │  12/18 tasks│  │  28/30 tasks│  │  8/20 tasks  │              │
│  │  Status: EM │  │  Status: EM │  │  Status: AB  │              │
│  │  ANDAMENTO  │  │  ANDAMENTO  │  │  ERTA        │              │
│  │ [Detalhes →]│  │ [Detalhes →]│  │ [Detalhes →] │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  [+ Nova Inspeção]                                               │
└──────────────────────────────────────────────────────────────────┘
```

### Informações no card:
- Matrícula da aeronave
- Tipo de inspeção (código)
- Barra de progresso (tarefas concluídas / total)
- Status com badge colorido
- Data de abertura
- Link para página de detalhes

---

## 10. Página de Detalhe (`/inspecoes/{id}/detalhes`)

### Layout proposto:

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Voltar   Inspeção IF-100H — FAB 5916                         │
│  Status: EM_ANDAMENTO    Aberta em: 20/04/2026 por SGT SILVA    │
│  Progresso: ████████░░░░░░ 12/18 tarefas (67%)                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  # │ Tarefa                    │ Sistema  │ Status    │ Executor │
│  ──┼───────────────────────────┼──────────┼───────────┼──────────│
│  1 │ Verificar fixação MDP     │ Aviônica │ ✅ CONC.  │ SGT ABC  │
│  2 │ Testar CMFD 1 e 2         │ Display  │ ✅ CONC.  │ SGT DEF  │
│  3 │ Inspecionar VUHF          │ Rádio    │ ⏳ PEND.  │ —        │
│  4 │ Verificar antena IFF      │ IFF      │ ⏳ PEND.  │ —        │
│  ...                                                             │
│                                                                  │
│  [Concluir Inspeção]   [Cancelar Inspeção]                       │
└──────────────────────────────────────────────────────────────────┘
```

### Interações:
- Clicar em uma tarefa pendente → abre modal para marcar como concluída (selecionar executor + observação)
- Badge de status com cores (verde=concluída, amarelo=pendente, cinza=N/A)
- Botão "Concluir Inspeção" só habilitado quando todas obrigatórias estão resolvidas

---

## 11. Faseamento da Implementação

### Fase 1 — Banco de Dados e Models (~2h)
- [x] Criar `app/modules/inspecoes/__init__.py` (isolado, sem autoimport do router)
- [x] Criar `app/modules/inspecoes/models.py` (4 tabelas)
- [x] Adicionar enums `StatusInspecao` e `StatusTarefa` localmente em `schemas.py` para manter isolamento
- [ ] Adicionar enums `StatusInspecao` e `StatusTarefa` em `enums.py` (pendente para ativação)
- [ ] Adicionar relationships em `Aeronave` e `Usuario` (pendente para ativação)
- [ ] Gerar migration Alembic
- [ ] Testar migration (upgrade/downgrade)

### Fase 2 — Backend: Schemas + Service + Router (~4h)
- [x] Criar `schemas.py` com Pydantic models
- [x] Criar `service.py` com lógica de negócio (CRUD + regras RN-I01 a RN-I07)
- [x] Criar `router.py` com endpoints da API
- [ ] Registrar router no app principal (pendente por isolamento)
- [ ] Testar endpoints via Swagger/docs

### Fase 3 — Frontend: Navegação + Configurações (~3h)
- [ ] Adicionar ícone de Inspeções no `base.html` (nav)
- [ ] Adicionar card "Inspeções" em `configuracoes.html`
- [ ] Criar modais de tipo de inspeção e tarefas
- [ ] Implementar JS para CRUD de tipos e tarefas
- [ ] Adicionar rotas de página em `pages/router.py`

### Fase 4 — Frontend: Listagem e Detalhe (~4h)
- [ ] Criar template `inspecoes/lista.html` (cards com progresso)
- [ ] Criar template `inspecoes/detalhe.html` (tabela de tarefas)
- [ ] Implementar `inspecoes.js` (listagem, filtros, nova inspeção)
- [ ] Implementar `inspecao_detalhe.js` (execução de tarefas, conclusão)

### Fase 5 — Polimento e Testes (~2h)
- [x] Testes unitários do service isolado
- [x] Testes de autenticação/RBAC do router isolado
- [x] Teste de regressão garantindo que a API de inspeções não está ativa no app principal
- [x] Criação de Testes TDD base para RN-01, RN-02, RN-04 e RN-05 (GREEN - Passando)
- [ ] Testes de integração dos endpoints
- [ ] Ajustes de UX (responsividade, animações, dark mode)
- [ ] Documentação da API (docstrings)

---

## 12. Impacto em Arquivos Existentes

| Arquivo | Alteração |
|---------|-----------|
| `app/shared/core/enums.py` | Adicionar `StatusInspecao`, `StatusTarefa` |
| `app/modules/aeronaves/models.py` | Adicionar relationship `inspecoes` |
| `app/modules/auth/models.py` | Adicionar relationships de inspeção |
| `app/web/templates/base.html` | Adicionar ícone na nav |
| `app/web/templates/configuracoes.html` | Adicionar card + modais |
| `app/web/static/js/configuracoes.js` | Adicionar funções de CRUD inspeção |
| `app/web/pages/router.py` | Adicionar rotas `/inspecoes` |
| `app/bootstrap/` | Registrar router de inspeções |
| `migrations/` | Nova migration Alembic |

---

## 13. Considerações Técnicas

### Performance
- Usar `joinedload` para carregar tarefas e executores no detalhe da inspeção
- Índices em `inspecoes.aeronave_id`, `inspecoes.status`, `inspecao_tarefas.inspecao_id`
- Paginação na listagem de inspeções

### Segurança
- Apenas `ENCARREGADO` e `ADMINISTRADOR` podem abrir/concluir inspeções
- `MANTENEDOR` pode apenas executar tarefas atribuídas
- Validação JWT em todos os endpoints (padrão existente)

### Integridade
- `ON DELETE RESTRICT` para aeronave e tipo (impedir exclusão com inspeções vinculadas)
- `ON DELETE CASCADE` para tarefas ao excluir inspeção cancelada
- Constraint `UNIQUE(aeronave_id, tipo_inspecao_id)` filtrado por status não-finalizado (RN-I07)








==================================

Plano criado com sucesso em docs/implementacao_inspecao.md. Aqui está um resumo dos pontos-chave:

📋 Resumo do Plano
Banco de Dados — 4 novas tabelas:

tipos_inspecao — catálogo de tipos (IF-50H, IPG, IPE, etc.)
tarefas_template — tarefas padrão por tipo de inspeção
inspecoes — inspeções realizadas (vinculadas a aeronaves + usuários)
inspecao_tarefas — tarefas instanciadas com rastreio de executor
Frontend — 3 áreas:

Ícone na nav ao lado de Panes, Inventário e Frota
Página /inspecoes com cards mostrando aeronaves em inspeção + barra de progresso
Página /inspecoes/{id}/detalhes com tabela de tarefas, status e executor
Card em /configuracoes para cadastro de tipos e tarefas-template
7 regras de negócio (instanciação automática de tarefas, validação de conclusão, rastreabilidade obrigatória, etc.)

5 fases de implementação (~15h estimadas total)

❓ Decisões pendentes para você validar:
Os tipos de inspeção sugeridos (IF-50H, IF-100H, IPG, IPE) são adequados ao contexto da unidade?
Deseja que a abertura de inspeção altere automaticamente o status da aeronave para INDISPONIVEL?
A regra de unicidade (não permitir 2 inspeções ativas do mesmo tipo na mesma aeronave) faz sentido?
Quer começar a implementação por alguma fase específica?
