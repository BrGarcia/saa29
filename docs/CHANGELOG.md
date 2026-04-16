# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)  
e aderente ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.0.1] – 2026-04-16

### Corrigido
- **Bug crítico 500 – Mapper `Instalacao` não encontrado**: `Aeronave` tem `relationship("Instalacao", ...)`, mas em `app/main.py` o módulo `app.equipamentos.models` era importado *depois* de `app.aeronaves.models`. O SQLAlchemy tentava resolver o nome `"Instalacao"` no registry antes da classe existir. **Fix:** invertida a ordem dos imports — `app.equipamentos.models` agora precede `app.aeronaves.models`. Comentário de aviso adicionado para prevenir regressão futura.
- **Bug crítico 500 – `AttributeError: _static_cache_key`**: Em `app/panes/service.py`, `_get_year_func` usava `func.Integer` nos dois caminhos de `cast()`. `func.Integer` cria uma chamada SQL chamada `"Integer"` (não é um tipo), tornando a query não-cacheável. **Fix:** importado `Integer` de `sqlalchemy` e substituído `func.Integer` → `Integer` nas chamadas `.cast()` para SQLite e PostgreSQL.

---

## [0.7.0] – 2026-03-31

### Adicionado
- **Hardening de JWT**: Implementada Blacklist de tokens (JTI) no logout e redução do tempo de expiração para 120 minutos (AUD-03, AUD-18).
- **Proteção XSS Centralizada**: Nova função `escapeHtml` no `app.js` aplicada em todas as renderizações dinâmicas de tabelas (AUD-04).
- **Validação MIME Estrita**: Integração com `python-magic` para validar conteúdo real de arquivos no upload (AUD-09).
- **Scripts de Ambiente Local**: Criados `scripts/init_local.py` e `scripts/run_app.py` para setup rápido com SQLite.

### Modificado
- **UX de Edição**: O ícone de edição na listagem de panes agora abre o modal "Editar Ocorrência" diretamente, sem sair da página.
- **Segurança RBAC**: Endpoints de Aeronaves e Equipamentos agora exigem explicitamente nível `EncarregadoOuAdmin` para operações de escrita (AUD-05, AUD-12).
- **Hardening de Configuração**: Validação em tempo de inicialização que impede o uso de segredos inseguros em ambiente de produção (AUD-08).
- **Purga de Legados**: Remoção completa da role `INSPETOR` e seus aliases em favor do sistema de 3 níveis oficial (AUD-02).

### Corrigido
- **Proteção de Admin**: Implementada trava que impede a auto-exclusão de usuários e a exclusão do último administrador do sistema (AUD-17).
- **Bug de Listagem**: Adicionado limite default de 100 registros na listagem de panes para prevenir negação de serviço (AUD-14).
- **Trusted Hosts**: Adicionado `testserver` aos hosts permitidos para viabilizar execução de testes automatizados.

---

## [1.0.0] – 2026-03-29

### Adicionado
- **Filtros Avançados de Panes**: Busca por intervalo de datas e por aeronave específica no backend e frontend.
- **Gestão de Lixeira (Restore)**: Funcionalidade para restaurar panes excluídas via Soft Delete (acessível por Encarregados e Administradores).
- **Infraestrutura de Produção**: Configuração de servidor Gunicorn com workers Uvicorn, Dockerfile otimizado e docker-compose persistente.
- **CI/CD Automatizado**: Workflow do GitHub Actions para validação de Lint, Type Check e Testes em todo push.
- **Segurança de Rede**: Middlewares `TrustedHost` e `CORSMiddleware` configurados para ambiente real.

### Modificado
- **Fluxo de Status Simplificado**: Remoção do status intermediário `EM_PESQUISA`. O ciclo de vida da pane agora é direto: `ABERTA` → `RESOLVIDA`.
- **Layout de Intervenção**: Redesign da tela de detalhes da pane com cabeçalho dinâmico (matrícula), descrição em largura total e blocos de ações/anexos lado a lado.
- **Autoatribuição de Mantenedor**: Mantenedores agora podem assumir panes para si mesmos sem restrição de gestor.
- **Conclusão Automática**: O usuário que finaliza uma pane é automaticamente registrado como responsável técnico.

---

## [0.6.0] – 2026-03-29

### Adicionado
- **Reestruturação RBAC (3 Papéis)**: Migração para o sistema oficial `ADMINISTRADOR`, `ENCARREGADO` e `MANTENEDOR`.
- **Gestão de Efetivo (CRUD)**: Endpoints `PUT` e `DELETE` para usuários, com interface administrativa completa em modal.
- **Campo Trigrama**: Implementação de código de 3 letras para militares em todo o sistema (DB, API e Frontend).
- **Delegar Pane**: Funcionalidade para Encarregados e Administradores atribuírem responsáveis às panes.

### Corrigido
- Falha Crítica: Resolvido `ImportError` em `dependencies.py` que causava downtime do servidor.
- Fix: Botão "Ver" em anexos agora abre corretamente os arquivos em nova aba.
- Fix: Login e registro de usuários alinhados com o novo schema Pydantic (`password` vs `senha_bruta`).

---

## [0.5.0] – 2026-03-28

### Adicionado
- Implementação completa da **Interface MVP (Fase 5)** utilizando Jinja2, Vanilla JS e CSS Glassmorphism.
- Funcionalidade de **RBAC no Frontend**: controle dinâmico de visibilidade das views Dashboard, Frota e Efetivo para `ADMINISTRADOR`, `ENCARREGADO` e `MANTENEDOR`.
- Tela **Dashboard**: visão operacional priorizando panes `ABERTA` e `EM_PESQUISA`.
- Tela **Histórico** (Panes): com cálculo automático de código (ddd/yy), filtros funcionais, e exibição condicional de Ação Corretiva.
- Telas administrativas: **Frota (Aeronaves)** e **Efetivo (Usuários)** totalmente funcionais.
- Ações na interface: registrar pane com envio em background de imagens, e concluir/assumir alterando status e responsáveis atrelados silenciosamente ao JWT em cache.
- Lixeira inteligente: Implementação de Soft Delete (coluna `ativo=False`) na estrutura de Panes consumível via botão "DELETE" na interface.

---

## [0.4.1] – 2026-03-28

### Corrigido
- Resolução de travamento "silencioso" no fim da execução do `pytest` (fechamento forçado do `test_engine.dispose()`).
- Ocultamento de avisos de depreciação de bibliotecas (`pytest-asyncio` e `jose`) via `pytest.ini` para logs limpos.
- Validação final e declaração de estabilidade da Fase 3 (Codificação dos Módulos).

---

## [0.4.0] – 2026-03-27

### Adicionado
- Implementação completa da API autenticada (Dia 4 – Método Akita).
- Módulo **Auth**: Login (JWT), Hashing (Bcrypt), Perfil do usuário.
- Módulo **Aeronaves**: CRUD completo com validações de unicidade.
- Módulo **Panes**: Lógica de abertura, edição e conclusão. Sistematização de transições de status.
- Módulo **Equipamentos**: Sistema de herança de controles, propagação automática e cálculo de vencimentos.
- Infraestrutura: Suporte a downloads de anexos e montagem de arquivos estáticos.
- Dependência: `python-dateutil` para cálculos de datas complexos.

### Corrigido
- Compatibilidade de UUIDs em SQLite/aiosqlite nos testes (uso de `select()` ao invés de `db.get()`).
- Fixtures de testes agora suportam autenticação JWT real.
- Status do Roadmap e fix de stubs nos routers (via `fix_routers.py`).

---

## [0.3.0] – 2026-03-27

### Modificado
- Reorganização da documentação em subpastas em `docs/` (`architecture`, `agile`, `development`, `api`, `requirements`, `methodology`).
- `README.md` atualizado para servir como hub central de documentação.
- Links internos de documentação corrigidos em todos os arquivos Markdown.

---

## [0.2.0] – 2026-03-27

### Adicionado
- `CONTRIBUTING.md` – guia completo para equipe de implementação
- `ROADMAP.md` – roteiro de entregas por fase (Método Akita)

---

## [0.1.0] – 2026-03-27

### Adicionado
- Estrutura completa de pastas e módulos (Método Akita – Dia 2)
- 11 modelos ORM declarados com SQLAlchemy 2.x:
  - `Usuario`, `Aeronave`
  - `Equipamento`, `TipoControle`, `EquipamentoControle`, `ItemEquipamento`, `Instalacao`, `ControleVencimento`
  - `Pane`, `Anexo`, `PaneResponsavel`
- Schemas Pydantic v2 para todos os domínios
- Stubs de services e routers com algoritmos documentados via `# TODO (Dia 4)`
- Enums centralizados em `app/core/enums.py`
- Configuração: `requirements.txt`, `.env.example`, `.gitignore`
- Infraestrutura: `docker-compose.yml`, `Dockerfile`, `alembic.ini`
- Migrações Alembic: `migrations/env.py` (suporte async)
- Suite de testes Pytest: `conftest.py` + 4 arquivos `test_*.py` com stubs
- `README.md` com visão geral, stack e instruções de uso

### Documentação de requisitos
- `00_SRS.md` – Software Requirements Specification
- `01_SPECS.md` – Especificação de Algoritmos
- `03_MODEL_DB.md` – Modelo de Banco de Dados
- `04_AKITA.MD` – Metodologia de desenvolvimento

---

[Unreleased]: https://github.com/BrGarcia/saa29/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/BrGarcia/saa29/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/BrGarcia/saa29/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/BrGarcia/saa29/compare/v0.3.0...v0.7.0
[0.3.0]: https://github.com/BrGarcia/saa29/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BrGarcia/saa29/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BrGarcia/saa29/releases/tag/v0.1.0
