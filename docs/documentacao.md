# Documentação do Projeto SAA29 (Versão Otimizada)

Este documento organiza a documentação do projeto em camadas, separando conteúdo para humanos, IA e especificação técnica, visando máxima clareza e eficiência no uso com modelos de linguagem.

---

# 🧠 1. Camada de Contexto para IA (`docs/ia/`)

Arquivos otimizados para leitura por IA (baixo consumo de tokens e alta densidade semântica).

| Arquivo | Função |
|--------|-------|
| `CTX.md` | Estado global do projeto (fase, decisões, foco atual) |
| `modules.ctx` | Estrutura dos módulos (funções, entidades, dependências) |
| `flows.ctx` | Fluxos principais do sistema |
| `api.ctx` | Contratos de API |
| `rules.ctx` | Regras de negócio |
| `db.ctx` | Modelo de dados resumido |
| `mapa_repositorio.md` | Localização dos componentes no código |
| `glossario.md` | Definições de termos |
| `prompts_base.md` | Prompts reutilizáveis |

👉 Esta é a principal camada utilizada nos prompts de IA.

---

# 📦 2. Camada de Resumo (`docs/summaries/`)

Versões condensadas dos documentos principais.

| Arquivo | Função |
|--------|-------|
| `PROJECT_SUMMARY.md` | Visão geral do sistema |
| `SRS_SUMMARY.md` | Requisitos resumidos |
| `SPECS_SUMMARY.md` | Especificações técnicas resumidas |
| `MODEL_DB_SUMMARY.md` | Modelo de dados resumido |

👉 Usado junto com `.ctx` para tarefas comuns.

---

# 📚 3. Camada de Especificação (`docs/core/`)

Fonte de verdade completa do sistema.

| Arquivo | Função |
|--------|-------|
| `SRS.md` | Requisitos completos |
| `SPECS.md` | Especificações detalhadas |
| `MODEL_DB.md` | Modelagem completa do banco |

👉 Usado quando profundidade máxima é necessária.

---

# 🏗️ 4. Arquitetura e Segurança (`docs/architecture/`)

| Arquivo | Função |
|--------|-------|
| `Database.md` | Estrutura detalhada do banco |
| `RBAC.md` | Controle de acesso |
| `Security.md` | Políticas de segurança |

---

# 🧪 5. Testes (`docs/tdd/`)

| Arquivo | Função |
|--------|-------|
| `tdd_auth.md` | Testes de autenticação |
| `tdd_logistica.md` | Testes de logística |
| `tdd_operacional.md` | Testes operacionais |

---

# 📋 6. Planejamento (`docs/backlog/`)

| Arquivo | Função |
|--------|-------|
| `backlog.md` | Lista de tarefas e melhorias |

---

# 📊 7. Relatórios (`docs/relatorio/`)

| Arquivo | Função |
|--------|-------|
| `revisao_claude.md` | Auditoria técnica gerada por IA |

---

# 🧾 8. Legado (`docs/legacy/`)

| Arquivo | Função |
|--------|-------|
| `relatorio_arquitetural.md` | Histórico de decisões |
| `roadmap_resumido.md` | Planejamento antigo |

---

# 🧠 9. Metodologia (`docs/methodology/`)

| Arquivo | Função |
|--------|-------|
| `AKITA.md` | Diretrizes de desenvolvimento |
| `DoD.md` | Definition of Done (Critérios de conclusão) |
| `DoR.md` | Definition of Ready (Critérios para início) |

---

# ✈️ 10. Manuais Técnicos (`docs/fim/`)

Arquivos de referência técnica (FIM).

---

# 🎯 Estratégia de Uso

## Uso padrão com IA (90% dos casos)

Utilizar apenas contexto otimizado:

```
CTX.md
+ modules.ctx
+ flows.ctx
+ rules.ctx
+ summaries/*
```

👉 Evita envio de código desnecessário
👉 Maximiza economia de tokens
👉 Mantém alto nível de entendimento da IA

---

## Uso avançado (quando necessário)

Adicionar profundidade técnica:

```
+ SPECS.md
+ MODEL_DB.md
+ trecho de código específico
```

👉 Usar apenas quando:
- Implementação detalhada
- Debug específico
- Alteração estrutural

---

# 🔥 Princípio Central

> Separar contexto (IA) de documentação (humano) e de especificação (fonte de verdade)

---

# 📌 Resultado Esperado

- Menor consumo de tokens
- Maior precisão das respostas da IA
- Redução de ambiguidade
- Escalabilidade do projeto

---

# 🎯 Status da Organização

> **Status:** ✅ Reorganização de documentação concluída com sucesso!
> **Data de conclusão:** 2026-05-23

A estrutura de documentação está organizada de forma otimizada para humanos e agentes de IA, visando máxima eficiência no consumo de tokens e localização de informações.

---

## 📁 Estrutura Final do Diretório `docs/`

```
docs/
├── ia/                   # Camada de Contexto IA (alta densidade semântica)
│   ├── CTX.md            # Estado global e foco atual do projeto
│   ├── modules.ctx       # Estrutura e dependências dos módulos
│   ├── flows.ctx         # Fluxos principais de negócio
│   ├── api.ctx           # Contratos e assinaturas de API
│   ├── rules.ctx         # Regras de negócio do sistema
│   ├── db.ctx            # Resumo do modelo de dados do banco
│   ├── mapa_repositorio.md # Localização de arquivos e componentes
│   ├── glossario.md      # Termos e jargões técnicos do domínio
│   └── prompts_base.md   # Prompts úteis estruturados
├── summaries/            # Camada de Resumo (visões gerais condensadas)
│   ├── PROJECT_SUMMARY.md
│   ├── SRS_SUMMARY.md
│   ├── SPECS_SUMMARY.md
│   └── MODEL_DB_SUMMARY.md
├── core/                 # Camada de Especificação (Fonte de Verdade)
│   ├── SRS.md            # Requisitos completos do sistema
│   ├── SPECS.md          # Especificações detalhadas
│   └── MODEL_DB.md       # Modelagem completa do banco de dados (se houver)
├── architecture/         # Desenhos e especificações arquiteturais
│   ├── Database.md       # Diagrama e detalhes das tabelas
│   ├── RBAC.md           # Definição de papéis e permissões
│   ├── overview.md       # Visão geral arquitetural do monólito
│   ├── refatoracao_slot_posicao.md
│   └── referencia-api.md # Contratos técnicos
├── backlog/              # Planejamento e gestão de tarefas
│   ├── Melhorias Futuras/ # Idéias e planejamentos futuros
│   ├── resolvidos/        # Histórico de bugs e tarefas concluídas
│   └── implementacao_JSDoc.md
├── relatorio/            # Auditorias e relatórios de segurança/qualidade
│   ├── claude.md         # Primeira auditoria de segurança (2026-05-05)
│   └── claude_google.md  # Auditoria de segurança complementar (2026-05-11)
├── guides/               # Guias operacionais e manuais de setup
│   ├── cloudflare_r2.md  # Integração com storage R2
│   ├── guia-desenvolvimento.md
│   ├── guia-testes.md
│   └── migracao_postgresql.md
├── legacy/               # Documentos históricos e planos de ação antigos
│   ├── Auditoria_2026-03-30.md
│   ├── AUDIT_SUMMARY.md
│   ├── RELATORIO_COMPLETO.MD
│   ├── IMPLEMENTATION_PLAN.md
│   └── PROGRESS_2026_04_20.md
├── methodology/          # Normas e acordos de trabalho técnico
│   ├── CSP.md            # Padrões de segurança do Content Security Policy
│   └── merge_main.md     # Fluxo Git de merge na branch principal
├── fim/                  # Manuais técnicos aeronáuticos (Fault Isolation Manual)
│   ├── FIM1741_...PDF    # PDFs individuais de consulta
│   └── fim.json          # Indexador dos manuais
├── README.md             # Visão rápida de setup da documentação
├── CHANGELOG.md          # Registro histórico de alterações
├── CONTRIBUTING.md       # Manual do colaborador
├── ROADMAP.md            # Próximos passos do projeto
├── SECURITY.md           # Política de reporte de vulnerabilidades
├── CODE_OF_CONDUCT.md    # Código de conduta do projeto
├── documentacao.md       # Este arquivo
└── estrutura.md          # Estrutura geral de arquivos do repositório
```

---

*Última atualização do status: 2026-05-23*