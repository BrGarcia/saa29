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

CTX.md  
+ modules.ctx  
+ flows.ctx  
+ rules.ctx  
+ summaries/*  

👉 Evita envio de código desnecessário  
👉 Maximiza economia de tokens  
👉 Mantém alto nível de entendimento da IA  

---

## Uso avançado (quando necessário)

Adicionar profundidade técnica:

+ SPECS.md  
+ MODEL_DB.md  
+ trecho de código específico  

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