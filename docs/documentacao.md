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

# 🚧 Plano de Reorganização (Pós-Próximo Módulo)

> **Status:** ⏳ Aguardando conclusão do próximo módulo para implementação.
> **Gatilho:** Executar após finalização e merge do módulo em andamento.

Esta seção consolida as decisões necessárias e os passos seguros identificados durante a análise de viabilidade realizada em 2026-05-03.

---

## ❓ Decisões Pendentes (Definir antes de implementar)

As questões abaixo precisam ser respondidas antes de mover qualquer arquivo:

| # | Questão | Opções |
|:---|:---|:---|
| 1 | Para onde vai `docs/api/referencia-api.md`? | `docs/core/` ou `docs/architecture/` |
    **Resposta:** docs/architecture/
| 2 | Para onde vão os guias de `docs/development/`? | Criar `docs/guides/` ou mover para `docs/core/` |
    **Resposta:** Criar docs/guides/
| 3 | `docs/archive/` deve ser mantido como está? | Manter ou consolidar em `docs/legacy/` |
    **Resposta:** Consolidar em docs/legacy/
| 4 | `docs/bugs/` vai para `docs/backlog/`? | Mover ou manter separado |
    **Resposta:** Mover para docs/backlog/
| 5 | Arquivos raiz (`CHANGELOG.md`, `CONTRIBUTING.md`, etc.) ficam na raiz de `docs/`? | Sim (padrão de repositório) |
    **Resposta:** Sim (padrão de repositório)

Justificativa curta

referencia-api.md combina mais com arquitetura porque documenta contrato técnico e integrações.
docs/development/ merece uma pasta própria de guias, porque isso separa instruções operacionais de especificação formal.
archive/ e legacy/ têm a mesma função prática: material histórico, então vale consolidar.
bugs/ é trabalho pendente, correção e triagem, então faz mais sentido dentro de backlog/.
Os arquivos de controle do repositório ficam melhor na raiz de docs/ para acesso rápido.
---

Estrutura final sugerida
docs/
├── README.md
├── documentacao.md
├── estrutura.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── core/
├── summaries/
├── architecture/
├── ia/
├── guides/
├── backlog/
├── relatorio/
├── legacy/
├── methodology/
├── fim/

## ✅ Passos Seguros (Já aprovados para execução)

Estas operações são de baixo risco e podem ser feitas com `git mv` para preservar histórico:

### Etapa 1 — Renomeações e movimentações simples (Concluído ✅)

- [x] Renomear contexto de IA (`ia/contex.md` -> `ia/CTX.md`)
- [x] Criar camada `docs/core/` (mover `requirements/` -> `core/`)
- [x] Renomear pasta `BACKLOG` para `backlog` (lowercase)
- [x] Ajuste de metodologia (`04_AKITA.MD` -> `AKITA.md`)
- [x] Remover pasta vazia `security/`
- [x] Resolver decisões pendentes (Q1-Q5):
  - [x] Mover `docs/api/referencia-api.md` -> `docs/architecture/`
  - [x] Mover `docs/development/` -> `docs/guides/`
  - [x] Consolidar `docs/archive/` -> `docs/legacy/`
  - [x] Mover `docs/bugs/` -> `docs/backlog/`

```bash
# Renomear contexto de IA
git mv docs/ia/contex.md docs/ia/CTX.md

# Criar camada core (requirements → core)
mkdir docs/core
git mv docs/requirements/00_SRS.md docs/core/SRS.md
git mv docs/requirements/01_SPECS.md docs/core/SPECS.md

# Renomear pasta BACKLOG para backlog (lowercase)
git mv docs/BACKLOG docs/backlog

# Ajuste de metodologia
git mv docs/methodology/04_AKITA.MD docs/methodology/AKITA.md

# Remover pasta vazia
rmdir docs/security
```

### Etapa 2 — Criar arquivos `.ctx` para IA

Criar na pasta `docs/ia/` com conteúdo condensado extraído dos documentos existentes:

- [x] `modules.ctx` — estrutura dos módulos (extrair de `mapa_repositorio.md`)
- [x] `flows.ctx` — fluxos principais do sistema (extrair de `contex.md`)
- [x] `api.ctx` — contratos de API (extrair de `docs/architecture/referencia-api.md`)
- [x] `rules.ctx` — regras de negócio (extrair de `architecture/Database.md` + `RBAC.md`)
- [x] `db.ctx` — modelo de dados resumido (extrair de `architecture/Database.md`)

### Etapa 3 — Criar camada `docs/summaries/`

Criar pasta e os 4 arquivos de resumo condensados:

- [x] `PROJECT_SUMMARY.md` — visão geral do sistema
- [x] `SRS_SUMMARY.md` — requisitos resumidos (de `core/SRS.md`)
- [x] `SPECS_SUMMARY.md` — especificações técnicas resumidas
- [x] `MODEL_DB_SUMMARY.md` — modelo de dados resumido

---

## 📁 Estrutura Final Esperada

```
docs/
├── ia/                   # Contexto para IA (tokens otimizados)
│   ├── CTX.md            # Estado global do projeto
│   ├── modules.ctx
│   ├── flows.ctx
│   ├── api.ctx
│   ├── rules.ctx
│   ├── db.ctx
│   ├── mapa_repositorio.md
│   ├── glossario.md
│   └── prompts_base.md
├── summaries/            # Resumos condensados
│   ├── PROJECT_SUMMARY.md
│   ├── SRS_SUMMARY.md
│   ├── SPECS_SUMMARY.md
│   └── MODEL_DB_SUMMARY.md
├── core/                 # Fonte de verdade
│   ├── SRS.md
│   ├── SPECS.md
│   └── MODEL_DB.md
├── architecture/         # Arquitetura técnica (sem alteração)
├── backlog/              # Planejamento (lowercase)
├── tdd/                  # Testes (sem alteração)
├── development/          # Guias de desenvolvimento (decisão pendente)
├── api/                  # Referência API (decisão pendente)
├── relatorio/            # Relatórios
├── legacy/               # Documentos históricos
├── archive/              # Arquivos antigos (manter como está)
├── bugs/                 # Rastreamento de bugs (decisão pendente)
├── methodology/          # Metodologia de desenvolvimento
├── fim/                  # Manuais técnicos FIM (sem alteração)
├── agile/                # Critérios de Definition of Done/Ready
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── documentacao.md       # Este arquivo
└── estrutura.md
```

---

*Análise de viabilidade realizada em: 2026-05-03*
*Última atualização do plano: 2026-05-03*