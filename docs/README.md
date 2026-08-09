# 📚 Documentação Oficial — SAA29

> **Sistema de Gestão de Panes, Aeronaves e Inventário A-29 (FAB)**  
> *Versão do Projeto: 1.4.0 (Novembro/2026)*

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-blue)](https://sqlite.org)
[![Uso Interno](https://img.shields.io/badge/Uso-Interno%20FAB-yellow)]()

---

## 🗺️ Mapa de Navegação da Documentação

A documentação do SAA29 é organizada em camadas para facilitar a consulta por desenvolvedores e modelos de IA:

```text
docs/
├── README.md                 # 📍 [VOCÊ ESTÁ AQUI] Índice principal da documentação
├── ROADMAP.md                # 🗺️ Planejamento estratégico e versões (v1.0 -> v4.0)
│
├── architecture/             # 🏗️ Arquitetura, Banco de Dados, RBAC, API e ADRs
│   ├── Database.md           # Modelagem relacional detalhada
│   ├── RBAC.md               # Controle de permissões (Mantenedor, Inspetor, Encarregado, Admin)
│   ├── overview.md           # Visão geral da arquitetura monolítica modular
│   ├── referencia-api.md     # Contratos e endpoints da API REST
│   └── adr/                  # Registros de Decisão de Arquitetura (ADRs)
│
├── backlog/                  # 📋 Backlog, Especificações Ativas e Histórico
│   ├── feature_controle_pedidos.md  # [ATIVO] Especificação da Central de Pedidos (v2.0)
│   ├── mockup_pedidos.html          # [ATIVO] Mockup visual interativo
│   ├── Melhorias Futuras/           # Roadmap de propostas (XLSX, WhatsApp, ToDo, Manual FIM)
│   └── resolvidos/                  # Histórico de tarefas e bugs concluídos
│
├── core/                     # 📚 Fonte da Verdade (Requisitos e Especificações)
│   ├── SRS.md                # Requisitos de Software
│   └── SPECS.md              # Especificação Técnica Funcional
│
├── fim/                      # 📖 PDFs do Fault Isolation Manual (FIM - Manuais A-29)
│
├── guides/                   # 🛠️ Manuais Práticos, Infraestrutura e Governança
│   ├── guia-desenvolvimento.md  # Guia de ambiente e boas práticas
│   ├── guia-testes.md           # Suíte de testes (Pytest)
│   ├── cloudflare_r2.md         # Backup remoto e sync de banco
│   ├── migracao_postgresql.md   # Plano de migração de banco
│   ├── CODE_OF_CONDUCT.md       # Código de Conduta
│   ├── CONTRIBUTING.md          # Guia de Contribuição
│   └── SECURITY.md              # Política de Segurança
│
├── ia/                       # 🧠 Camada de Contexto para Inteligência Artificial (.ctx)
│   ├── CTX.md                # Estado global e decisões atuais
│   ├── mapa_repositorio.md   # Mapeamento de código
│   ├── prompts_base.md       # Prompts padrão e auditoria
│   └── *.ctx                 # Ficheiros de contexto compacto (db, api, flows, rules, modules)
│
├── legacy/                   # 📦 Histórico de Auditorias Antigas e Referências
│   └── auditorias_antigas/   # Auditorias consolidadas (Codex, Opus, etc.)
│
├── manual/                   # 📖 Manual do Usuário Final do Sistema
│   └── manual_sistema.md     # Guia passo a passo por perfil de usuário
│
├── methodology/              # 📈 Metodologia, Estado Atual/Futuro e Changelog
│   ├── ESTADO_ATUAL_E_FUTURO.MD # Guia descritivo e visão geral do software
│   ├── CHANGELOG.md          # Histórico de mudanças por versão
│   ├── NEXT.md               # Próximas ações prioritárias
│   ├── CSP.md                # Política de Content Security Policy
│   └── merge_main.md         # Guia de integração de branches
│
├── summaries/                # 📝 Resumos Executivos de Requisitos e Modelos
└── tdd/                      # 🧪 Guias de Testes por Módulo
```

---

## 🚀 Início Rápido

```bash
git clone <repo>
cd SAA29
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

python -m alembic upgrade head
python scripts/db/init_db.py
python scripts/run_app.py
```

Documentação interativa da API no navegador:
`http://localhost:8000/docs`

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI |
| ORM | SQLAlchemy 2.x async |
| Banco padrão | SQLite + aiosqlite |
| Migrações | Alembic |
| Validação | Pydantic v2 |
| Auth | JWT (HS256) + refresh token + blacklist |
| Frontend | Jinja2 + Vanilla JS + CSS |
| Segurança | CSRF, CSP, Zero Trust, RBAC, Rate Limiting |
| Upload/Storage | Local ou Cloudflare R2 |

---

## 📌 Documentos Essenciais por Perfil

- **Para Desenvolvedores:** [Guia de Desenvolvimento](guides/guia-desenvolvimento.md) | [Guia de Testes](guides/guia-testes.md) | [Especificações Técnicas](core/SPECS.md)
- **Para Arquitetos:** [Visão Geral de Arquitetura](architecture/overview.md) | [Modelagem de Banco](architecture/Database.md) | [Referência da API](architecture/referencia-api.md)
- **Para Operação / Hangar:** [Manual do Sistema](manual/manual_sistema.md) | [ROADMAP](ROADMAP.md) | [Estado Atual e Futuro](methodology/ESTADO_ATUAL_E_FUTURO.MD)
