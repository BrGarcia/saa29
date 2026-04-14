# Guia de Desenvolvimento de Software para Projetos Individuais

## 1. Metodologia Recomendada

Para projetos individuais, a melhor abordagem é combinar simplicidade com disciplina.

### Abordagem sugerida:
- Kanban para controle de fluxo
- Lean para tomada de decisão
- Scrum (adaptado) para cadência

### Estrutura de fluxo (Kanban):
- Backlog
- Em andamento
- Concluído

### Práticas recomendadas:
- Trabalhar em ciclos semanais
- Dividir entregas em pequenas partes
- Revisar progresso semanalmente

---

## 2. Documentação Essencial

Estrutura sugerida:

```
/docs
   ├── 01_vision.md
   ├── 02_requirements.md
   ├── 03_architecture.md
   ├── 04_data_model.md
   ├── 05_decisions.md
```

### 2.1 Vision
- Objetivo do sistema
- Problema que resolve
- Público-alvo
- Funcionalidades principais

### 2.2 Requirements

Exemplo:

```
RF01 - O sistema deve registrar inspeções
RF02 - O sistema deve alertar vencimentos

RNF01 - Interface simples
RNF02 - Persistência em nuvem
```

### 2.3 Architecture
- Tipo de sistema
- Tecnologias utilizadas
- Estrutura geral

### 2.4 Data Model
- Definição de entidades principais
- Relacionamentos

Exemplo:
- Aeronave
- Inspeção
- Item controlado
- Ordem de serviço

### 2.5 Decisions

Exemplo:

```
DEC-001: Uso de SQLite
Motivo: simplicidade e portabilidade
```

---

## 3. Organização de Pastas

```
/project
│
├── /src
│    ├── main.py
│    ├── config.py
│
│    ├── /domain
│    ├── /services
│    ├── /data
│    ├── /ui
│
├── /tests
├── /docs
├── /scripts
├── requirements.txt
└── README.md
```

### Separação de responsabilidades:
- domain: regras de negócio
- services: lógica da aplicação
- data: acesso a dados
- ui: interface

---

## 4. Organização das Entregas

### Estratégia: MVP incremental

Exemplo:

- v0.1: Cadastro de aeronaves
- v0.2: Cadastro de inspeções
- v0.3: Alertas de vencimento
- v0.4: Dashboard básico

### Conceito:
- Entregar sempre algo funcional
- Evoluir em pequenos incrementos

---

## 5. Controle de Tarefas

Formato sugerido:

```
[TIPO] Descrição

Ex:
[FEAT] Criar cadastro de aeronave
[FIX] Corrigir cálculo de vencimento
[TECH] Refatorar módulo de datas
```

---

## 6. Versionamento (Git)

### Padrão de commits:

```
feat: adiciona cadastro de aeronaves
fix: corrige cálculo de horas de voo
refactor: reorganiza camada de dados
docs: adiciona documentação inicial
```

### Boas práticas:
- Commits pequenos e frequentes
- Cada commit representa uma unidade lógica

### Estrutura de branches:
- main: versão estável
- dev: desenvolvimento
- feature/...: novas funcionalidades

---

## 7. Versionamento do Sistema

Formato:

```
v0.1.0
v0.2.0
v1.0.0
```

---

## 8. Boas Práticas

### Sempre fazer:
- Criar README claro
- Manter estrutura organizada
- Documentar decisões importantes

### Evitar:
- Código em um único arquivo
- Falta de padrão
- Commits genéricos

---

## 9. Ferramentas Recomendadas

- Editor: VSCode
- Versionamento: Git + GitHub
- Gestão de tarefas: Trello ou Notion
- Banco inicial: SQLite ou arquivos estruturados

---

## 10. Princípio Fundamental

"Você não precisa de processos complexos, precisa de consistência."

