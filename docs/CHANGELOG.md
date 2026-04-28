# Changelog

Todas as mudancas notaveis deste projeto sao documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e aderente ao [Versionamento Semantico](https://semver.org/lang/pt-BR/).

---

## [1.1.0] - 2026-04-28

### Fixed
- **Segurança (CSP):** Remoção completa de scripts inline e handlers de eventos (`onclick`, `onkeyup`, etc.) em todos os templates HTML para conformidade estrita com a política `script-src 'self'`.
- **Arquitetura Frontend:** Migração da lógica de interface para arquivos `.js` especializados utilizando `addEventListener`, melhorando a manutenibilidade e segurança contra XSS.
- **Bug de Aeronaves:** Identificada a causa do erro 409 (Conflict) ao tentar inativar aeronaves via interface de configurações (Backlog para correção em 1.1.1).

### Added
- Documentação de análise de bug em `docs/relatorio/relatorio_bug_inativar_anv.md`.
- Reforço da infraestrutura de eventos no frontend para todos os modais do sistema.

---

## [Unreleased]

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

