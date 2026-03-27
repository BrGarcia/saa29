# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)  
e aderente ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Planejado
- Implementação da lógica de autenticação JWT + bcrypt
- CRUD completo de aeronaves, panes e equipamentos
- Suite de testes com cobertura ≥ 80%
- Interface frontend (a definir)
- Deploy com CI/CD

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
