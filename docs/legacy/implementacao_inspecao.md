# Plano de Implementação — Módulo de Inspeções

> **Projeto:** SAA29 — Sistema de Apoio à Aviônica A-29
> **Status:** 📋 Planejamento de Implementação (Atualizado)
> **Fonte da Verdade:** `docs/architecture/Database.md` (Domínio de Inspeções)

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

## 5. Endpoints da API Rest

| Rota Base: `/api/inspecoes` | Descrição | Roles Mínimas |
| :--- | :--- | :--- |
| `GET`, `POST /tipos` | CRUD de Tipos de Inspeção | ENCARREGADO |
| `GET`, `POST /tarefas` | CRUD de Catálogo de Tarefas | ENCARREGADO |
| `POST /tipos/{id}/tarefas` | Vincular tarefa a um tipo | ENCARREGADO |
| `GET`, `POST /eventos` | Listar e Abrir novo Evento | ENCARREGADO (POST) / MANTENEDOR (GET) |
| `GET /eventos/{id}` | Detalhes do evento e tarefas | MANTENEDOR |
| `POST /eventos/{id}/tarefas/{t_id}/executar` | Concluir tarefa específica | MANTENEDOR |
| `POST /eventos/{id}/tarefas` | Adicionar tarefa manual | MANTENEDOR |
| `POST /eventos/{id}/tarefas/{t_id}/pane`| Gerar pane a partir de tarefa | MANTENEDOR |
| `POST /eventos/{id}/concluir` | Fechar Evento de Inspeção | ENCARREGADO |

---

## 6. Frontend (Jinja2 + JS)

### 6.1 Página de Configurações (`/configuracoes`)
- Criar cards para: **Tipos de Inspeção** e **Catálogo de Tarefas**.
- Modais em JS para gerenciar o vínculo N:N entre tipos e tarefas (definir ordem e obrigatoriedade).

### 6.2 Operacional (`/inspecoes`)
- **Lista de Eventos**: Mostrar cards com barra de progresso (Tarefas concluídas vs Total), status, aeronave, tipos aplicados.
- **Botão Nova Inspeção**: Modal que seleciona a aeronave e um array de `tipos_inspecao_id` (suporte a combo).

### 6.3 Detalhes do Evento (`/inspecoes/{id}/detalhes`)
- Interface principal para o mantenedor.
- Checklist dinâmico listando as `inspecao_tarefas`.
- Botões em cada tarefa: "Marcar como Concluída" e "Relatar Pane".
- Exibir trigrama do executor (`executada_por.trigrama`) e timestamp nas tarefas já feitas.
- Botão "Concluir Inspeção" validando RN-06 no frontend e backend.

---

## 7. Ordem de Execução Recomendada

1. **Fase 1**: Models + Enums + Alembic Migration.
2. **Fase 2**: Schemas Pydantic + Service (CRUD Tipos/Tarefas e lógica de Deduplicação de Evento).
3. **Fase 3**: Rotas da API (`router.py`) com RBAC.
4. **Fase 4**: Integração em `configuracoes.html` (Frontend Administrativo).
5. **Fase 5**: Criação das telas `/inspecoes` e `/inspecoes/detalhes` (Frontend Operacional).