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
- Controle de status (Aberta, Resolvida)
- Rastreabilidade de ações e responsáveis

O sistema será inicialmente um MVP leve, web-based e responsivo.

---

## 2. Visão Geral do Sistema

### 2.1 Perspectiva do Produto
O sistema será uma aplicação web acessível via navegador.

### 2.2 Usuários do Sistema
- Administrador
- Encarregado
- Mantenedor

---

## 3. Requisitos Funcionais

### 3.1 Autenticação
- RF-01: Tela de login (gatekeeper) com usuário e senha
- RF-02: Acesso somente após autenticação válida

### 3.2 Panes e Dashboard Operacional
- RF-03: Após login, o sistema deve direcionar o usuário para a página principal de panes
- RF-04: A página principal deve exibir a listagem operacional de panes com filtros
- RF-05: A dashboard com cards e cores pode permanecer disponível como tela secundária, sem navegação ativa
- RF-06: A página de panes deve oferecer filtros por texto, aeronave, status e data

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
- Usabilidade: interface leve e simples
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
- Gestão de Panes
- Dashboard operacional secundária
- Cadastros
- Upload

---

## 7. Futuro

- Histórico completo
- Dashboard analítico
- Integração com inspeções
