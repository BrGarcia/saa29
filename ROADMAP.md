# ROADMAP.md – Roteiro de Entregas

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29

---

## Visão Geral

```
Dia 1: AI Jail       ██ Concluído
Dia 2: Fundação      ██ Concluído  ← estamos aqui
Dia 3: Testes        ░░ Pendente
Dia 4: Codificação   ░░ Pendente
Dia 5: Otimização    ░░ Pendente
Dia 6: Interface     ░░ Pendente
Dia 7: Deploy/CI     ░░ Pendente
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

## 🔲 Fase 2 – Testes (Dia 3)

> **Objetivo:** TDD — escrever todos os testes antes de implementar qualquer lógica.  
> **Entregável:** Suite de testes completa, todos falhando (expected).

### 2.1 Módulo Auth
- [ ] `test_login_sucesso` — credenciais válidas retornam JWT
- [ ] `test_login_senha_errada` — retorna 401
- [ ] `test_login_usuario_inexistente` — retorna 401
- [ ] `test_acesso_sem_token` — retorna 401
- [ ] `test_acesso_token_invalido` — retorna 401
- [ ] `test_criar_usuario` — status 201 com dados corretos
- [ ] `test_criar_usuario_username_duplicado` — retorna 409

### 2.2 Módulo Aeronaves
- [ ] `test_listar_aeronaves_vazio` — lista vazia, status 200
- [ ] `test_criar_aeronave_sucesso` — status 201
- [ ] `test_criar_aeronave_matricula_duplicada` — retorna 409
- [ ] `test_buscar_aeronave_existente` — status 200
- [ ] `test_buscar_aeronave_inexistente` — status 404

### 2.3 Módulo Panes
- [ ] `test_criar_pane_sucesso` — status=ABERTA, status HTTP 201 (RN-02)
- [ ] `test_criar_pane_descricao_vazia_padrao` — descrição = "AGUARDANDO EDICAO" (RN-05)
- [ ] `test_criar_pane_aeronave_inexistente` — retorna 404 (RN-01)
- [ ] `test_filtrar_panes_por_status` — filtro funcional (RF-06)
- [ ] `test_filtrar_panes_por_texto` — filtro funcional (RF-06)
- [ ] `test_concluir_pane_aberta` — status=RESOLVIDA, data_conclusao preenchida (RN-04)
- [ ] `test_concluir_pane_ja_resolvida` — retorna 409
- [ ] `test_transicao_aberta_para_em_pesquisa` — aceitar ([SPECS §8](./docs/requirements/01_SPECS.md))
- [ ] `test_transicao_invalida_resolvida_para_aberta` — rejeitar (RN-03)
- [ ] `test_upload_imagem_valida` — status 201
- [ ] `test_upload_tipo_invalido` — retorna 422

### 2.4 Módulo Equipamentos
- [ ] `test_criar_equipamento` — status 201
- [ ] `test_criar_item_herda_controles_do_equipamento` — 2 controles criados ([MODEL_DB §5.1](./docs/architecture/03_MODEL_DB.md))
- [ ] `test_propagar_controle_para_itens_existentes` — propagação automática ([MODEL_DB §5.2](./docs/architecture/03_MODEL_DB.md))
- [ ] `test_sem_duplicidade_controle_por_item` — UNIQUE constraint
- [ ] `test_registrar_execucao_calcula_novo_vencimento` — cálculo correto de data
- [ ] `test_instalar_item_em_aeronave` — status 201
- [ ] `test_remover_item_de_aeronave` — data_remocao preenchida

---

## 🔲 Fase 3 – Codificação (Dia 4)

> **Objetivo:** Fazer todos os testes da Fase 2 passarem.  
> **Regra:** Implementar na ordem abaixo. Não avançar sem os testes passando.

### 3.1 Segurança e Auth (pré-requisito de tudo)
- [ ] `app/auth/security.py` — `hash_senha`, `verificar_senha`, `criar_token`, `decodificar_token`
- [ ] `app/dependencies.py` — `get_current_user` (JWT → Usuario)
- [ ] `app/auth/service.py` — todos os métodos
- [ ] `app/auth/router.py` — todos os endpoints

### 3.2 Aeronaves
- [ ] `app/aeronaves/service.py` — CRUD completo
- [ ] `app/aeronaves/router.py` — tratamento de erros

### 3.3 Panes (núcleo do sistema)
- [ ] `app/panes/service.py`:
  - [ ] `criar_pane()` — com validação de descricao vazia
  - [ ] `listar_panes()` — filtros dinâmicos por texto, status, aeronave, data
  - [ ] `editar_pane()` — validação de transições de status
  - [ ] `concluir_pane()` — data_conclusao automática
  - [ ] `upload_anexo()` — validação de tipo/tamanho, nome UUID
  - [ ] `adicionar_responsavel()`
- [ ] `app/panes/router.py` — todos os endpoints com tratamento de erros

### 3.4 Equipamentos (mais complexo)
- [ ] `app/equipamentos/service.py`:
  - [ ] `criar_tipo_controle()`
  - [ ] `associar_controle_a_equipamento()` — com propagação para itens
  - [ ] `criar_item_com_heranca()` — herança automática de controles
  - [ ] `instalar_item()` / `remover_item()`
  - [ ] `registrar_execucao()` — recalcular `data_vencimento`
  - [ ] `calcular_vencimento()` — `data_exec + periodicidade_meses`
  - [ ] `propagar_controle_para_itens()` — batch insert
- [ ] `app/equipamentos/router.py` — todos os endpoints

### 3.5 Primeira Migração
- [ ] Gerar migração inicial: `alembic revision --autogenerate -m "initial_schema"`
- [ ] Revisar e aplicar: `alembic upgrade head`
- [ ] Criar seed script (`scripts/seed.py`) com dados iniciais de aeronaves e usuários

---

## 🔲 Fase 4 – Otimização (Dia 5)

> **Objetivo:** Performance e qualidade de código. Só iniciar após todos os testes passarem.

- [ ] Revisar queries N+1 com `selectinload` / `joinedload` onde necessário
- [ ] Adicionar índices no banco (já especificados em [`03_MODEL_DB.md §6`](./docs/architecture/03_MODEL_DB.md))
- [ ] Implementar paginação nas listagens (`limit` / `offset`)
- [ ] Cache em memória para listagem de aeronaves (raramente muda)
- [ ] Refatorar métodos de service acima de 50 linhas
- [ ] Cobertura de testes ≥ 80% (`pytest --cov`)
- [ ] Análise estática: `ruff check app/` e `mypy app/`

---

## 🔲 Fase 5 – Interface (Dia 6)

> **Objetivo:** Frontend web para os usuários finais.

- [ ] Definir stack de frontend (sugestão: Next.js ou HTML puro com HTMX — discutir com equipe)
- [ ] Tela de login (RF-01)
- [ ] Dashboard com cards de panes por status com cores (RF-03, RF-04, RF-05)
- [ ] Filtros: texto, aeronave, status, data (RF-06)
- [ ] Fluxo de nova pane: seleção de aeronave → upload → descrição (RF-07)
- [ ] Tela detalhada de pane com anexos (RF-09)
- [ ] Botões: editar, anexar imagem, concluir (RF-10, RF-11, RF-12)
- [ ] Telas de cadastro: efetivo, aeronaves, equipamentos (RF-14, RF-15, RF-16)
- [ ] Design responsivo para uso em dispositivos móveis

---

## 🔲 Fase 6 – Deploy e CI/CD (Dia 7)

- [ ] Configurar pipeline CI (GitHub Actions):
  - [ ] `pytest tests/ -v` a cada push
  - [ ] `ruff check app/` (linter)
  - [ ] `mypy app/` (type check)
- [ ] Configurar ambiente de produção (VPS / Coolify)
- [ ] Variáveis de ambiente seguras no servidor
- [ ] HTTPS com certificado SSL
- [ ] Backup automático do PostgreSQL
- [ ] Monitoramento de uptime

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
