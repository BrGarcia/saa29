# 📊 Proposta de Melhoria Futura: Aplicação do Teorema de Bayes no SAA29

> **Status:** 🟡 Em Análise / Backlog de Melhorias Futuras  
> **Data:** 2026-08-09  
> **Autor:** Antigravity AI / Equipe SAA29  
> **Módulos Impactados:** `panes`, `equipamentos`, `pedidos`, `vencimentos`, `inspecoes`, `publicacoes` (Automação de Diretivas e Ajuste Fino)

---

## 1. Visão Geral e Fundamentação

O **Teorema de Bayes** calcula a probabilidade condicional de um evento $A$ ocorrer dado que o evento $B$ já foi observado:

$$P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}$$

No contexto do **SAA29 (Manutenção Aeronáutica da FAB)**, a abordagem bayesiana oferece um motor de decisão probabilístico altamente eficiente para lidar com incertezas operacionais. Ao contrário de modelos de inteligência artificial pesados ou redes neurais "caixa-preta", o método Bayesiano:
1. **Funciona com poucos dados iniciais (*Cold Start*):** Permite iniciar com distribuições *prior* extraídas dos manuais do fabricante e ajustar as probabilidades (*posteriors*) conforme a frota acumula histórico de manutenção.
2. **É 100% Explicável e Auditável:** Apresenta razões matemáticas claras para cada recomendação, essencial em aviação militar.
3. **Possui Desempenho Ultrarrápido:** Executa em milissegundos dentro do backend FastAPI sem necessidade de GPU ou infraestrutura externa.

---

## 2. Casos de Uso Detalhados por Módulo

### 2.1 Módulos `panes` e `equipamentos`: Diagnóstico Probabilístico de Panes

* **Problema:** Quando uma pane ocorre (ex: *"queda de pressão hidráulica durante o voo"*), técnicos costumam inspecionar ou substituir múltiplos componentes em sequência até encontrar a causa real.
* **Solução Bayesiana:**
  * $A_i$: Causa raiz (ex: falha na bomba hidráulica, vazamento em atuador, falha no sensor de pressão).
  * $B$: Sintomas reportados + dados de horas de voo + histórico da aeronave.
  * O sistema calcula $P(\text{Causa } A_i \mid \text{Sintomas } B)$ e apresenta a lista de causas ordenadas pela maior probabilidade.
* **Impacto Operacional:** Redução expressiva do MTTR (*Mean Time to Repair*) e eliminação de substituição desnecessária de peças sem defeito.

---

### 2.2 Módulo `pedidos` (Central de Pedidos): Ranking Probabilístico de Risco AOG e Lead Time

* **Problema:** Na Central de Pedidos, demandas urgentes (`EMERGENCIA`) competem com rotina (`NORMAL`), mas a urgência administrativa nem sempre reflete o risco real de paralisar uma aeronave (*Aircraft On Ground* - AOG).
* **Solução Bayesiana:**
  * **Score de Risco de AOG:** Calcular $P(\text{Paralisação da Aeronave} \mid \text{Slot Vazio}, \text{Estoque da Base}, \text{Missão Agendada})$.
  * **Previsão Bayesiana de Lead Time:** Calcular $P(\text{Atraso do Pedido} > X \text{ dias} \mid \text{Part Number}, \text{Fornecedor}, \text{Histórico de Entrega})$.
* **Impacto Operacional:** A fila de pedidos é ordenada dinamicamente por impacto probabilístico real na disponibilidade da frota.

---

### 2.3 Módulo `vencimentos`: Ajuste Preditivo da Taxa de Degradação

* **Problema:** Prazos de inspeção e calibração são baseados em horas nominais ou calendário estático, ignorando perfis de missão e histórico de lotes.
* **Solução Bayesiana:**
  * Calcular $P(\text{Falha Precoce do Item} \mid \text{Severidade de Operação}, \text{Histórico do Lote}, \text{Condições Ambientais})$.
* **Impacto Operacional:** Antecipação automática de pedidos de reposição para itens com alto risco bayesiano de falha antes do vencimento nominal.

---

### 2.4 Automação de Diretivas e IA (`automacao_diretivas.py` e `ajuste_fino.py` - Passo 7)

* **Problema:** Na automação da triagem de diretivas técnicas e no fine-tuning dos modelos de IA, é necessário validar as análises sem precisar de revisão humana em 100% dos documentos.
* **Solução Bayesiana:**
  * **Triagem Naive Bayes:** Classificação rápida de aplicabilidade e gravidade de diretivas por modelo de aeronave/sistema.
  * **Auditoria Humana por Incerteza (Active Learning):** Calcular a probabilidade de erro/incerteza da LLM para determinada diretiva. Se $P(\text{Erro}) > \text{Threshold}$, o documento é marcado para auditoria do especialista.
* **Impacto Operacional:** O especialista humano foca apenas nos 5% a 10% de casos em que o modelo apresenta incerteza estatística.

---

### 2.5 Módulo `inspecoes`: Amostragem Ponderada de Qualidade (EEXD e Delineamento)

* **Problema:** Fiscalização de qualidade por amostragem aleatória pode ignorar tarefas críticas.
* **Solução Bayesiana:**
  * Calcular $P(\text{Inconformidade} \mid \text{Complexidade da Tarefa}, \text{Sistema da Aeronave}, \text{Histórico})$.
* **Impacto Operacional:** Amostragem focada em inspeções com maior probabilidade condicional de inconsistência.

---

## 3. Matriz de Impacto vs. Esforço

| Caso de Uso | Módulos | Impacto na Produtividade | Esforço de Implementação | Prioridade Recomendada |
| :--- | :--- | :---: | :---: | :---: |
| **Diagnóstico de Panes** | `panes`, `equipamentos` | 🔴 Alto | 🟡 Médio | **1º Lugar** |
| **Triagem de Incerteza IA** | `publicacoes`, scripts IA | 🔴 Alto | 🟢 Baixo | **2º Lugar** |
| **Priorização de Pedidos** | `pedidos` | 🟡 Médio | 🟢 Baixo | **3º Lugar** |
| **Amostragem de Inspeções**| `inspecoes` | 🟡 Médio | 🟡 Médio | 4º Lugar |
| **Vencimentos Preditivos** | `vencimentos` | 🟡 Médio | 🔴 Alto | 5º Lugar |

---

## 4. Requisitos para Futura Implementação

Quando esta funcionalidade for priorizada para desenvolvimento, o fluxo deve seguir:
1. **Modelagem da Tabela de Conhecimento:** Criar estruturas de banco de dados (`model_priors` ou histórico de frequências) para guardar as probabilidades a priori.
2. **Camada de Serviço Dedicada:** Criar um serviço desacoplado em `app/shared/services/bayesian_engine.py` (mantendo as rotas finas segundo o `INICIO.MD`).
3. **Interface Visual (Dashboard):** Exibir os percentuais de probabilidade/confiança nas telas de Panes, Pedidos e Delineamento.
