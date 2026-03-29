# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)  
e aderente ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Planejado
- Fase 6: Deploy automatizado com GitHub Actions
- Pipeline de CI/CD para qualidade de código

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

[Unreleased]: https://github.com/BrGarcia/saa29/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/BrGarcia/saa29/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/BrGarcia/saa29/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BrGarcia/saa29/releases/tag/v0.1.0
