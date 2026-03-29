# ROADMAP.md – Roteiro de Entregas

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

---

## Visão Geral

```
Dia 1: AI Jail       ██ Concluído
Dia 2: Fundação      ██ Concluído
Dia 3: Testes        ██ Concluído
Dia 4: Codificação   ██ Concluído
Dia 5: Otimização    ██ Concluído
Dia 6: Interface     ██ Concluído
Dia 7: Deploy/CI     ██ Concluído (Estável 1.0.0)
```

---

## ✅ Fase 1 – Fundação (Concluída)

> **Método Akita – Dia 2**

- [x] Documentação de requisitos ([`00_SRS.md`](./docs/requirements/00_SRS.md), [`01_SPECS.md`](./docs/requirements/01_SPECS.md), [`03_MODEL_DB.md`](./docs/architecture/03_MODEL_DB.md))
- [x] Definição de stack e arquitetura
- [x] Estrutura completa de pastas e módulos
- [x] Modelos ORM declarados (11 entidades)
- [x] Schemas Pydantic v2 para todos os domínios
- [x] Stubs de services e routers com algoritmos documentados
- [x] Configuração Docker, Alembic, Pytest
- [x] `requirements.txt`, `.env.example`, `README.md`

---

## ✅ Fase 2 – Testes (Concluída)

> **Método Akita – Dia 3**

### 2.1 Módulo Auth
- [x] `test_login_sucesso` — credenciais válidas retornam JWT
- [x] `test_login_senha_errada` — retorna 401
- [x] `test_login_usuario_inexistente` — retorna 401
- [x] `test_acesso_sem_token` — retorna 401
- [x] `test_acesso_token_invalido` — retorna 401
- [x] `test_criar_usuario` — status 201 com dados corretos
- [x] `test_criar_usuario_username_duplicado` — retorna 409

### 2.2 Módulo Aeronaves
- [x] `test_listar_aeronaves_vazio` — lista vazia, status 200
- [x] `test_criar_aeronave_sucesso` — status 201
- [x] `test_criar_aeronave_matricula_duplicada` — retorna 409
- [x] `test_buscar_aeronave_existente` — status 200
- [x] `test_buscar_aeronave_inexistente` — status 404

### 2.3 Módulo Panes
- [x] `test_criar_pane_sucesso` — status=ABERTA, status HTTP 201 (RN-02)
- [x] `test_criar_pane_descricao_vazia_padrao` — descrição = "AGUARDANDO EDICAO" (RN-05)
- [x] `test_criar_pane_aeronave_inexistente` — retorna 404 (RN-01)
- [x] `test_filtrar_panes_por_status` — filtro funcional (RF-06)
- [x] `test_filtrar_panes_por_texto` — filtro funcional (RF-06)
- [x] `test_concluir_pane_aberta` — status=RESOLVIDA, data_conclusao preenchida (RN-04)
- [x] `test_concluir_pane_ja_resolvida` — retorna 409
- [x] `test_transicao_invalida_resolvida_para_aberta` — rejeitar (RN-03)
- [x] `test_upload_imagem_valida` — status 201
- [x] `test_upload_tipo_invalido` — retorna 422

### 2.4 Módulo Equipamentos
- [x] `test_criar_equipamento` — status 201
- [x] `test_criar_item_herda_controles_do_equipamento` — 2 controles criados ([MODEL_DB §5.1](./docs/architecture/03_MODEL_DB.md))
- [x] `test_propagar_controle_para_itens_existentes` — propagação automática ([MODEL_DB §5.2](./docs/architecture/03_MODEL_DB.md))
- [x] `test_sem_duplicidade_controle_por_item` — UNIQUE constraint
- [x] `test_registrar_execucao_calcula_novo_vencimento` — cálculo correto de data
- [x] `test_instalar_item_em_aeronave` — status 201
- [x] `test_remover_item_de_aeronave` — data_remocao preenchida

---

## ✅ Fase 3 – Codificação (Concluída)

> **Método Akita – Dia 4**

### 3.1 Segurança e Auth (pré-requisito de tudo)
- [x] `app/auth/security.py` — `hash_senha`, `verificar_senha`, `criar_token`, `decodificar_token`
- [x] `app/dependencies.py` — `get_current_user` (JWT → Usuario)
- [x] `app/auth/service.py` — todos os métodos
- [x] `app/auth/router.py` — todos os endpoints

### 3.2 Aeronaves
- [x] `app/aeronaves/service.py` — CRUD completo
- [x] `app/aeronaves/router.py` — tratamento de erros

### 3.3 Panes (núcleo do sistema)
- [x] `app/panes/service.py`:
  - [x] `criar_pane()` — com validação de descricao vazia
  - [x] `listar_panes()` — filtros dinâmicos por texto, status, aeronave, data
  - [x] `editar_pane()` — validação de transições de status
  - [x] `concluir_pane()` — data_conclusao automática
  - [x] `upload_anexo()` — validação de tipo/tamanho, nome UUID
  - [x] `adicionar_responsavel()`
- [x] `app/panes/router.py` — todos os endpoints com tratamento de erros

### 3.4 Equipamentos (mais complexo)
- [x] `app/equipamentos/service.py`:
  - [x] `criar_tipo_controle()`
  - [x] `associar_controle_a_equipamento()` — com propagação para itens
  - [x] `criar_item_com_heranca()` — herança automática de controles
  - [x] `instalar_item()` / `remover_item()`
  - [x] `registrar_execucao()` — recalcular `data_vencimento`
  - [x] `calcular_vencimento()` — `data_exec + periodicidade_meses`
  - [x] `propagar_controle_para_itens()` — batch insert
- [x] `app/equipamentos/router.py` — todos os endpoints

### 3.5 Primeira Migração
- [x] Gerar migração inicial: `alembic revision --autogenerate -m "initial_schema"`
- [x] Revisar e aplicar: `alembic upgrade head`
- [x] Criar seed script (`scripts/seed.py`) com dados iniciais de aeronaves e usuários

---

## ✅ Fase 4 – Otimização (Concluída)

> **Objetivo:** Performance e qualidade de código. Só iniciar após todos os testes passarem.

- [x] Revisar queries N+1 com `selectinload` / `joinedload` onde necessário
- [x] Adicionar índices no banco (já especificados em [`03_MODEL_DB.md §6`](./docs/architecture/03_MODEL_DB.md))
- [x] Implementar paginação nas listagens (`limit` / `offset`)
- [x] Cache em memória para listagem de aeronaves (raramente muda)
- [x] Refatorar métodos de service acima de 50 linhas
- [x] Cobertura de testes progressiva e sem regressões (`pytest --cov`)
- [x] Análise estática: `ruff check app/` e `mypy app/`

---

## ✅ Fase 5 – Interface (Concluída)

> **Objetivo:** Frontend web para os usuários finais. Entregue no padrão Fab com Glassmorphism.

- [x] Definir stack de frontend (HTML/CSS Vanilla + JS + Jinja2)
- [x] Tela de login (RF-01) com armazenamento JWT em LocalStorage
- [x] Dashboard com cards e tabela simplificada apenas Ocorrências Abertas (RF-03, RF-04, RF-05)
- [x] Filtros em Histórico e visualização DDD/YY (RF-06)
- [x] Fluxo de nova pane: form + upload invisivel em background (RF-07)
- [x] Tela detalhada de pane com anexos (RF-09)
- [x] Botões e transições: concluir (grava ação corretiva), assumir, deletar logs (Soft Delete) (RF-10, RF-11, RF-12)
- [x] Telas de cadastro de Efetivo e Frota (Aeronaves) em modal (RF-14, RF-15)

---

## ✅ Fase 5.1 – Correções Críticas Pós-Review (Concluída)

> **Objetivo:** eliminar falhas de alta severidade identificadas na revisão técnica.

- [x] Remover exposição pública de anexos via `/uploads`
- [x] Servir anexos apenas por endpoint autenticado
- [x] Aplicar autorização no backend para delegação e exclusão de panes
- [x] Restringir edição de conteúdo de panes conforme RN-03
- [x] Alinhar contrato da listagem de panes com o frontend
- [ ] Completar filtros pendentes de excluídas/data no endpoint de listagem

---

## ✅ Fase 5.2 – Ajustes de Navegação e Operação (Concluída)

> **Objetivo:** consolidar `PANES` como fluxo principal e retirar a dashboard da navegação ativa sem perder a implementação.

- [x] Tornar `/panes` a página principal pós-login
- [x] Redirecionar a raiz `/` para `/panes`
- [x] Preservar a dashboard em rota secundária sem link no menu
- [x] Remover o atalho visível da dashboard da navegação lateral
- [x] Atualizar documentação funcional e de requisitos para refletir a nova navegação

---

## ✅ Fase 6 – Deploy e CI/CD (Dia 7) (Concluída)

- [x] Configurar pipeline CI (GitHub Actions):
  - [x] `pytest tests/ -v` a cada push
  - [x] `ruff check app/` (linter)
  - [x] `mypy app/` (type check)
- [x] Configurar ambiente de produção (Gunicorn + Uvicorn)
- [x] Variáveis de ambiente seguras no servidor
- [x] Middlewares de Segurança (CORS, TrustedHosts)
- [x] Persistência de volumes Docker para PostgreSQL e Uploads
- [x] Script de migração de dados v1.0 (Status Cleanup)

---

## Evoluções Futuras (Pós-MVP)

> Itens do [SRS §7](./docs/requirements/00_SRS.md) e [MODEL_DB §8](./docs/architecture/03_MODEL_DB.md) — não fazem parte do MVP.

| Feature | Descrição |
|---------|-----------|
| Dashboard analítico | Gráficos de panes por período, aeronave e sistema |
| Histórico de auditoria | Log completo de ações: criação, edição, conclusão |
| Alertas de vencimento | Notificações automáticas para controles próximos do vencimento |
| Integração inspecções | Vincular panes a inspeções programadas |
| App mobile | Interface nativa para tablets no hangar |

---

## Critérios de Aceite por Fase

| Fase | Critério de conclusão |
|------|----------------------|
| Fase 2 – Testes | Suite de testes completa, todos falhando esperadamente |
| Fase 3 – Codificação | `pytest tests/ -v` — 100% PASSED |
| Fase 4 – Otimização | Cobertura ≥ 80%, sem erros de linter/type check |
| Fase 5 – Interface | Todos os requisitos funcionais RF-01 a RF-16 demonstráveis |
| Fase 6 – Deploy | Sistema acessível via URL pública com HTTPS |
