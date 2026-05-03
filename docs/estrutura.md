# Estrutura do Projeto SAA29

Este documento descreve a organização de pastas e arquivos do projeto, focado na modularidade e escalabilidade da aplicação de controle de manutenção.

## 📂 Visão Geral (Raiz)

| Diretório/Arquivo | Descrição |
| :--- | :--- |
| `app/` | Código-fonte principal da aplicação FastAPI. |
| `scripts/` | Automações, scripts de manutenção e sistema de Seeds. |
| `migrations/` | Histórico de versões do banco de dados (Alembic). |
| `docs/` | Documentação técnica, arquitetura e backlogs. |
| `templates/` | Arquivos HTML (Jinja2) para a interface web. |
| `static/` | Ativos estáticos (CSS, JS, Imagens). |
| `tests/` | Suíte de testes automatizados. |
| `var/` | Dados persistentes locais (SQLite, Uploads). |
| `Dockerfile` | Definição da imagem Docker do projeto. |
| `docker-compose.yml` | Orquestração do ambiente de desenvolvimento/produção. |

---

## 🏗️ Núcleo da Aplicação (`app/`)

A pasta `app` segue uma estrutura modular por domínios:

### `app/modules/`
Contém os módulos de negócio independentes:
*   **`inspecoes/`**: Gestão de tipos de inspeção, templates de tarefas e abertura de ordens.
*   **`auth/`**: Autenticação, RBAC (Controle de Acesso) e segurança.
*   **`aeronaves/`**: Gerenciamento da frota e status operacional.
*   **`equipamentos/`**: Inventário e componentes instalados.
*   **`vencimentos/`**: Controle de calendários e horas de voo para manutenção.
*   **`efetivo/`**: Gestão de pessoal e indisponibilidades.
*   **`panes/`**: Registro e histórico de falhas técnicas.

---

## 📚 Documentação Otimizada (`docs/`)

Organizada em camadas para consumo humano e por IA:

### 1. Camada de Contexto IA (`docs/ia/`)
Arquivos compactos de alta densidade semântica para prompts:
*   `CTX.md`: Estado global e foco atual.
*   `modules.ctx`, `flows.ctx`, `api.ctx`, `rules.ctx`, `db.ctx`: Contratos e regras resumidas.

### 2. Camada de Resumo (`docs/summaries/`)
Visões gerais condensadas:
*   `PROJECT_SUMMARY.md`, `SRS_SUMMARY.md`, `SPECS_SUMMARY.md`, `MODEL_DB_SUMMARY.md`.

### 3. Camada de Especificação (Fonte de Verdade)
*   **`docs/core/`**: Requisitos (`SRS.md`) e Especificações (`SPECS.md`).
*   **`docs/architecture/`**: Modelagem de dados, RBAC e Segurança.

### 4. Gestão e Guias
*   **`docs/backlog/`**: Tarefas pendentes, histórico de implementação e rastreio de bugs.
*   **`docs/guides/`**: Manuais de setup, testes e infraestrutura.
*   **`docs/legacy/`**: Histórico de auditorias, decisões antigas e materiais de referência.

---

## 🌱 Sistema de Carga de Dados (`scripts/seed/`)

Responsável por popular o ambiente com dados realistas para testes:
*   `seed.py`: Orquestrador da carga sequencial.
*   `seed_tarefas.py`: Repositório central de tarefas e vinculação a templates.
*   `seed_inspecoes.py`: Lógica de simulação operacional (horas de voo e randomização de pacotes).

---

## 🐳 Inicialização e Docker

*   **`scripts/start.sh`**: Ponto de entrada do container (Alembic + Bootstrap).
*   **`scripts/init_local.py`**: Ferramenta para reset total do ambiente (SQLAlchemy Create + Alembic Stamp).

---
*Última atualização: 2026-05-03*
