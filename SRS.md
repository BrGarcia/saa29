# SRS.md  
**Sistema de Gestão de Panes – Eletrônica A-29**

## 1. Introdução

### 1.1 Objetivo
Este documento descreve os requisitos funcionais e não funcionais do sistema web para gestão de panes de manutenção aeronáutica, com foco em simplicidade, desempenho e usabilidade em ambiente operacional militar.

### 1.2 Escopo
O sistema permitirá:
- Autenticação de usuários
- Cadastro de efetivo
- Cadastro de aeronaves
- Registro e gerenciamento de panes
- Upload de imagens associadas às panes
- Controle de status (Aberta, Em Pesquisa, Resolvida)
- Rastreabilidade de ações e responsáveis

O sistema será inicialmente um MVP leve, web-based e responsivo.

---

## 2. Visão Geral do Sistema

### 2.1 Perspectiva do Produto
O sistema será uma aplicação web acessível via navegador.

### 2.2 Usuários do Sistema
- Administrador
- Militar/Mantenedor

---

## 3. Requisitos Funcionais

### 3.1 Autenticação
- RF-01: Tela de login com usuário e senha
- RF-02: Acesso somente após autenticação válida

### 3.2 Dashboard
- RF-03: Lista de panes após login
- RF-04: Exibição em formato de cards
- RF-05: Cores por status
- RF-06: Filtros por texto, aeronave, status e data

### 3.3 Nova Pane
- RF-07: Fluxo guiado (aeronave → imagem → descrição)
- RF-08: Status inicial = Aberta

### 3.4 Visualização
- RF-09: Tela detalhada da pane

### 3.5 Atualização
- RF-10: Editar descrição
- RF-11: Anexar imagens
- RF-12: Concluir pane
- RF-13: Atualização automática ao concluir

### 3.6 Cadastros
- RF-14: Efetivo
- RF-15: Aeronaves
- RF-16: Equipamentos

---

## 4. Requisitos Não Funcionais

- Desempenho: resposta < 2s
- Usabilidade: interface simples
- Segurança: autenticação e criptografia
- Escalabilidade: banco relacional
- Disponibilidade: acesso web

---

## 5. Regras de Negócio

- RN-01: Pane vinculada a aeronave
- RN-02: Status inicial = Aberta
- RN-03: Apenas panes abertas podem ser editadas
- RN-04: Conclusão gera data automática
- RN-05: Texto vazio = "AGUARDANDO EDICAO"

---

## 6. Módulos

- Autenticação
- Dashboard
- Gestão de Panes
- Cadastros
- Upload

---

## 7. Futuro

- Histórico completo
- Dashboard analítico
- Integração com inspeções
