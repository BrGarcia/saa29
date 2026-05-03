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

### Outros subdiretórios:
*   **`bootstrap/`**: Inicialização do banco de dados (`database.py`), configurações (`config.py`) e rotas principais.
*   **`shared/`**: Recursos compartilhados (Ex: enums, utils, base models).
*   **`web/`**: Controladores que servem as páginas Jinja2 (frontend monolítico).

---

## 🌱 Sistema de Carga de Dados (`scripts/seed/`)

Responsável por popular o ambiente com dados realistas para testes:
*   `seed.py`: Orquestrador da carga sequencial.
*   `seed_tarefas.py`: Repositório central de tarefas e vinculação a templates.
*   `seed_inspecoes.py`: Lógica de simulação operacional (horas de voo e randomização de pacotes).
*   `seed_auth.py`, `seed_aeronaves.py`, etc: Seeds específicos de cada módulo.

---

## 🐳 Inicialização e Docker

*   **`scripts/start.sh`**: Ponto de entrada do container. Garante:
    1.  Verificação de dependências.
    2.  Aplicação de migrações (`alembic upgrade head`).
    3.  Inicialização básica do banco.
*   **`scripts/init_local.py`**: Ferramenta para reset total do ambiente (Drop -> Create -> Seed).

---
*Última atualização: 2026-05-03*
