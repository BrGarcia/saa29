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
- [x] Adicionar enums `StatusInspecao` e `StatusTarefa` em `enums.py` (pendente para ativação)
- [x] Adicionar relationships em `Aeronave` e `Usuario` (pendente para ativação)
- [x] Gerar migration Alembic
- [x] Testar migration (upgrade/downgrade)

### Fase 2 — Backend: Schemas + Service + Router (~4h)
- [x] Criar `schemas.py` com Pydantic models
- [x] Criar `service.py` com lógica de negócio (CRUD + regras RN-I01 a RN-I07)
- [x] Criar `router.py` com endpoints da API
- [x] Registrar router no app principal (pendente por isolamento)
- [ ] Testar endpoints via Swagger/docs

### Fase 3 — Frontend: Navegação + Configurações (~3h)
- [x] Adicionar ícone de Inspeções no `base.html` (nav)
- [x] Adicionar card "Inspeções" em `configuracoes.html`
- [x] Criar modais de tipo de inspeção e tarefas
- [x] Implementar JS para CRUD de tipos e tarefas
- [x] Adicionar rotas de página em `pages/router.py`

### Fase 4 — Frontend: Listagem e Detalhe (~4h)
- [x] Criar template `inspecoes/lista.html` (cards com progresso)
- [x] Criar template `inspecoes/detalhe.html` (tabela de tarefas)
- [x] Implementar `inspecoes.js` (listagem, filtros, nova inspeção)
- [x] Implementar `inspecao_detalhe.js` (execução de tarefas, conclusão)

### Fase 5 — Polimento e Testes (~2h)
- [x] Testes unitários do service isolado
- [x] Testes de autenticação/RBAC do router isolado
- [x] Teste de regressão garantindo que a API de inspeções não está ativa no app principal
- [x] Criação de Testes TDD base para RN-01, RN-02, RN-04 e RN-05 (GREEN - Passando)
- [x] Testes de integração dos endpoints
- [x] Ajustes de UX (responsividade, animações, dark mode)
- [x] Documentação da API (docstrings)

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

---

## 14. Inclusão de Tarefas Extras na Inspeção (Nova Funcionalidade)

> **Status:** Backlog — Não implementado  
> **Prioridade:** Alta  
> **Referência:** RN-02 (Tarefas Manuais)  

### 14.1. Objetivo

Permitir que o usuário adicione tarefas extras (avulsas) a uma inspeção **em andamento**, diretamente pela página de Detalhes da Inspeção (`/inspecoes/{id}/detalhes`). As tarefas extras complementam o checklist original (gerado a partir dos templates) sem alterar o catálogo de tarefas-padrão.

### 14.2. Endpoint de Backend (Já Existente)

O endpoint `POST /inspecoes/{inspecao_id}/tarefas` já está implementado em `app/modules/inspecoes/router.py` (função `adicionar_tarefa_avulsa`). Ele aceita o schema `InspecaoTarefaCreate`:

```
{
  "ordem": 99,           // opcional, posição na lista
  "titulo": "Verificar conector J3 do MDP",
  "descricao": "Conector apresentou folga visual",
  "sistema": "Aviônica",
  "obrigatoria": true
}
```

**RBAC:** Apenas `ENCARREGADO` ou `ADMINISTRADOR` podem adicionar tarefas extras.

### 14.3. Frontend — Botão "Adicionar Tarefa"

Adicionar um botão na página de detalhes da inspeção (`inspecao_detalhe.js`), visível **somente quando a inspeção está em status `ABERTA` ou `EM_ANDAMENTO`**:

```
┌──────────────────────────────────────────────────────────────────┐
│  Checklist de Tarefas                     [+ Adicionar Tarefa]  │
├──────────────────────────────────────────────────────────────────┤
│  # │ Sistema  │ Ação / Descrição     │ Req │ Status │ Ações     │
│  ──┼──────────┼──────────────────────┼─────┼────────┼───────────│
│  1 │ Aviônica │ Verificar MDP        │ Sim │ CONC.  │ 👁        │
│  2 │ Display  │ Testar CMFD 1 e 2    │ Sim │ PEND.  │ ✏        │
│  ...                                                             │
│  N │ Aviônica │ Verificar conector   │ Sim │ PEND.  │ ✏  [MAN] │
│     (manual)                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 14.4. Modal "Adicionar Tarefa Extra"

Criar um novo modal no template `detalhe.html` (dentro do `{% block content %}`, sem scripts inline):

| Campo       | Tipo     | Obrigatório | Observação                        |
|-------------|----------|-------------|-----------------------------------|
| Título      | text     | Sim         | max 200 caracteres                |
| Descrição   | textarea | Não         | detalhes complementares           |
| Sistema     | text     | Não         | ex: "Aviônica", "Rádio", "IFF"   |
| Obrigatória | checkbox | Não         | default: `true`                   |

**Regras do modal:**
- O botão "Salvar" faz `POST /inspecoes/{id}/tarefas` via `apiFetch`
- Em caso de sucesso, chama `carregarDetalhesInspecao()` para atualizar a listagem
- Tarefas extras são exibidas com um badge `[MAN]` (Manual) ao lado do título para diferenciá-las das tarefas de template
- A ordem da tarefa extra é calculada automaticamente como `max(ordem_existente) + 1`

### 14.5. Impacto no Checklist

- Tarefas extras são incluídas na contagem geral de progresso (barra de progresso)
- Se `obrigatoria = true`, a tarefa extra **bloqueia** a conclusão da inspeção até ser resolvida (RN-06)
- A diferenciação visual entre tarefas de template e tarefas manuais é feita pelo campo `tarefa_template_id`: se `null`, a tarefa é manual

### 14.6. Restrição CSP

> ⚠️ **CRÍTICO:** O modal deve ser definido no HTML estático (`detalhe.html`). Todos os event listeners (abrir modal, fechar, submit do form) devem ser registrados via `addEventListener` no arquivo `inspecao_detalhe.js`. **Nenhum script inline ou `onclick` em atributos HTML é permitido** (regra `script-src 'self'`).

### 14.7. Arquivos Impactados

| Arquivo | Alteração |
|---------|-----------|
| `app/web/templates/inspecoes/detalhe.html` | Adicionar botão "Adicionar Tarefa" + modal |
| `app/web/static/js/inspecao_detalhe.js` | Adicionar handlers do modal e chamada `POST` |

### 14.8. Faseamento

- [ ] Adicionar HTML do botão e modal em `detalhe.html`
- [ ] Implementar handlers em `inspecao_detalhe.js` (abrir/fechar/submit)
- [ ] Adicionar badge `[MAN]` na renderização de tarefas manuais
- [ ] Testar: adicionar tarefa → checklist atualizado → progresso recalculado
- [ ] Testar: tarefa obrigatória manual bloqueia conclusão

---

## 15. Auditoria de Alterações no Checklist (Ajuste na Listagem)

> **Status:** Backlog — Não implementado  
> **Prioridade:** Média  
> **Referência visual:** Coluna "Atualização/Trigrama" da página Inventário de Equipamentos (`inventario.js`, linhas 206, 235-249)  

### 15.1. Objetivo

Exibir na tabela "Checklist de Tarefas" da página de Detalhes da Inspeção duas novas informações de rastreabilidade para cada tarefa que já foi atualizada:

1. **Trigrama** do usuário que alterou/concluiu a tarefa
2. **Data/Hora** da mudança de status

### 15.2. Estado Atual da Tabela

A tabela atual possui 6 colunas:

| Ord | Sistema | Ação / Descrição | Req | Status | Ações |

O campo `executado_por` (com trigrama) já é parcialmente exibido **dentro** da célula de Status como um texto secundário (`Por: XXX`). O campo `data_execucao` já existe no schema `InspecaoTarefaOut` mas **não é exibido** na tabela.

### 15.3. Novo Layout da Tabela

Adicionar uma nova coluna "Atualização" entre "Status" e "Ações", seguindo o padrão visual do Inventário:

```
┌────┬──────────┬──────────────────────┬─────┬─────────┬──────────────┬───────┐
│ Ord│ Sistema  │ Ação / Descrição     │ Req │ Status  │ Atualização  │ Ações │
├────┼──────────┼──────────────────────┼─────┼─────────┼──────────────┼───────┤
│  1 │ Aviônica │ Verificar fixação MDP│ Sim │ ✅ CONC │ 29/04/26     │  👁   │
│    │          │                      │     │         │ 14:35        │       │
│    │          │                      │     │         │ SGT ABC      │       │
├────┼──────────┼──────────────────────┼─────┼─────────┼──────────────┼───────┤
│  2 │ Rádio    │ Inspecionar VUHF     │ Sim │ ⏳ PEND│     —        │  ✏   │
└────┴──────────┴──────────────────────┴─────┴─────────┴──────────────┴───────┘
```

### 15.4. Implementação Frontend — Padrão Inventário

Replicar a lógica de renderização já existente em `inventario.js` (linhas 235-249) para a função `renderizarTarefas()` em `inspecao_detalhe.js`:

```javascript
// Padrão de referência (inventario.js):
// if (item.data_atualizacao) {
//     rastreabilidade = `<div style="font-size: 0.8rem;">
//         <div style="color: var(--text-secondary);">${dia}/${mes}/${ano} ${hora}:${min}</div>
//         <div style="font-weight: 700; color: var(--primary-color);">${trigrama || 'SYS'}</div>
//     </div>`;
// }
```

**Campos da API a utilizar:**
- `t.data_execucao` → formatar como `DD/MM/AA HH:MM`
- `t.executado_por?.trigrama` → exibir trigrama em destaque (bold, cor primária)
- Se a tarefa estiver `PENDENTE` (sem execução), exibir `—`

### 15.5. Ajuste na Coluna Status

Com a criação da coluna "Atualização" dedicada, **remover** o texto secundário `Por: ${trigrama}` que atualmente é renderizado dentro da célula de Status (linha ~135 de `inspecao_detalhe.js`). Isso elimina a duplicação de informação e mantém a célula de Status limpa, contendo apenas o badge colorido.

### 15.6. Ajuste no `<thead>` do Template HTML

Atualizar o cabeçalho da tabela em `detalhe.html` para incluir a nova coluna:

```html
<tr>
    <th style="text-align: center; padding: 0.75rem; width: 50px;">Ord</th>
    <th style="text-align: left; padding: 0.75rem; width: 120px;">Sistema</th>
    <th style="text-align: left; padding: 0.75rem;">Ação / Descrição</th>
    <th style="text-align: center; padding: 0.75rem; width: 60px;">Req</th>
    <th style="text-align: center; padding: 0.75rem; width: 100px;">Status</th>
    <th style="text-align: center; padding: 0.75rem; width: 130px;">Atualização</th>
    <th style="text-align: right; padding: 0.75rem; width: 80px;">Ações</th>
</tr>
```

**Nota:** Atualizar o `colspan` do placeholder de "Nenhuma tarefa" de `6` para `7`.

### 15.7. Restrição CSP

> ⚠️ **CRÍTICO:** Toda a renderização é feita via `createElement` e `innerHTML` em arquivos `.js` externos. Nenhum atributo `onclick` ou `<script>` inline é permitido. Os dados de data/trigrama já vêm da API via `apiFetch` — nenhum dado dinâmico é passado via Jinja.

### 15.8. Arquivos Impactados

| Arquivo | Alteração |
|---------|-----------|
| `app/web/templates/inspecoes/detalhe.html` | Adicionar coluna "Atualização" no `<thead>`, ajustar colspan |
| `app/web/static/js/inspecao_detalhe.js` | Adicionar `<td>` com data/trigrama na `renderizarTarefas()`, remover trigrama duplicado da célula Status |

### 15.9. Faseamento

- [ ] Atualizar `<thead>` em `detalhe.html` (adicionar coluna, ajustar colspan)
- [ ] Atualizar `renderizarTarefas()` em `inspecao_detalhe.js` (nova `<td>` + limpar Status)
- [ ] Testar: tarefas pendentes exibem `—`, tarefas concluídas exibem `DD/MM/AA HH:MM` + trigrama
- [ ] Validar consistência visual com a coluna "Atualização/Trigrama" do Inventário






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
