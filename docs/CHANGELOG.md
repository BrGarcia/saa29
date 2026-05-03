# Changelog

Todas as mudancas notaveis deste projeto sao documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e aderente ao [Versionamento Semantico](https://semver.org/lang/pt-BR/).

---

## [1.2.0] - 2026-04-28

### Fixed
- **Segurança (Auditoria Externa):** Implementação de 22 correções críticas, altas e médias identificadas em auditoria de segurança.
- **CSRF & Cookies:** Bypass de CSRF restrito a ambientes não-produção e flag `secure` dinâmica para cookies de sessão.
- **Headers & CSP:** Remoção de `'unsafe-inline'` da CSP e fortalecimento dos headers de segurança.
- **Autenticação:** Implementação de `refresh_token` seguro (HttpOnly), ajuste de expiração JWT para 15min e rotina de limpeza automática de tokens expirados.
- **Proteção XSS:** Aplicação sistemática de `escapeHtml()` no frontend para manipulações de DOM via `innerHTML`.
- **Arquitetura Zero Trust:** Validação de autenticação e RBAC (papéis) agora aplicada no backend para todas as rotas de páginas HTML, eliminando a dependência exclusiva de checagem client-side.
- **SQL Injection:** Proteção contra injeção em buscas via LIKE utilizando a função utilitária `_escape_like`.
- **Estabilidade:** Correção de double-commit em services, melhoria na concorrência de backups R2 e tipagem estrita em serviços de vencimentos.
- **Domínio:** Status de aeronaves migrado para `Enum` nativo e atualização de senhas padrão de teste para conformidade com requisitos de complexidade.

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

### Added
- **RBAC v2:** Implementação do novo papel `INSPETOR`, focado exclusivamente em fiscalização e validação, sem permissões de execução. O Enum `TipoPapel`, matriz de permissões (`RBAC.md`) e dependências (`ExecucaoPermitida`, `InspetorOuAdmin`) foram devidamente atualizados.
- Usuário de teste (`inspetor`) adicionado ao seed de desenvolvimento.

### Fixed
- **Segurança (CSRF):** Correção do erro 403 Forbidden ("Falha na sincronia de segurança") ao executar rotas com método `PATCH` (ex: execução de vencimentos) devido a configuração incompleta na biblioteca `fastapi-csrf-protect`.
- **Frontend:** Atualizada a lógica de `apiFetch` em `app.js` para diferenciar corretamente os erros de permissão de RBAC dos erros genuínos de CSRF (ambos retornam 403), exibindo agora a mensagem correta retornada pela API.
- **Frontend (RBAC):** Suporte a múltiplos papéis na tag HTML `data-role` (ex: `data-role="ENCARREGADO,INSPETOR"`) para controle preciso de visibilidade de botões.

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

