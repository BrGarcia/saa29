# Changelog

Todas as mudancas notaveis deste projeto sao documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e aderente ao [Versionamento Semantico](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### Added
- Módulo `efetivo` criado para gerenciamento de indisponibilidades do pessoal (férias, dispensa, etc.).
- Sincronizacao da documentacao principal com a estrutura atual do repositorio.
- Cobertura de arquitetura, API, requisitos e guias de desenvolvimento alinhada ao estado real do projeto.

### Changed
- Refatoração arquitetural (Fase 1, 2 e 3 concluidas): Extração das lógicas temporais e regras de manutenção do módulo `equipamentos` para o novo módulo especializado `vencimentos`.
- Unificação do status operacional das aeronaves para `DISPONIVEL` e `INDISPONIVEL` em todo o sistema.
- Refatoração do script de inicialização do banco (`init_db.py`) e dos seeds de desenvolvimento para suportar a nova hierarquia do SQLAlchemy Registry.
- `README.md` reescrito para refletir a arquitetura monolitica modular, o bootstrap em `app/bootstrap/main.py`, os scripts reais e a lista atual de modulos.
- Referencias de setup e execucao ajustadas para `scripts/run_app.py`, `scripts/db/init_db.py` e `scripts/db/seed.py`.

---

## [1.0.1] - 2026-04-16

### Fixed
- Ordem de importacao dos modelos ajustada para registrar corretamente o mapper de `Instalacao` antes do uso das relations em `Aeronave`.
- Correcao de casting no service de panes para evitar falha de cache em queries de ano.

---

## [1.0.0] - 2026-03-29

### Added
- Filtros avancados de panes por aeronave, texto, status e data.
- Soft delete e restauracao de panes.
- Estrutura inicial de arquitetura web com FastAPI, Jinja2, JS e CSS.
- Suite de testes automatizada e pipeline de validacao.
- Base de seguranca com JWT, RBAC e middlewares de rede.

### Changed
- Ciclo de vida da pane simplificado para `ABERTA -> RESOLVIDA`.
- Conclusao passou a registrar automaticamente o usuario responsavel.

---

## [0.7.0] - 2026-03-31

### Added
- Blacklist de JWT no logout.
- Hardening de seguranca para headers, uploads e login.
- Scripts de ambiente local para bootstrap e execucao.

### Changed
- Endpoints de Aeronaves e Equipamentos passaram a exigir permissao explicita em escrita.

---

## [0.1.0] - 2026-03-27

### Added
- Estrutura inicial do projeto, modelos ORM, schemas Pydantic e documentacao base.

