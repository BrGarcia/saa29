# SRS - SAA29

Documento sincronizado com o codigo-fonte em 22/04/2026.

## 1. Introducao

### 1.1 Objetivo

Este documento descreve os requisitos funcionais e nao funcionais do SAA29, um sistema web para gestao de panes, aeronaves, efetivo e inventario de equipamentos do A-29.

### 1.2 Escopo

O sistema permite:

- autenticar usuarios com JWT;
- gerenciar efetivo com perfis e permissao por papel;
- cadastrar e consultar aeronaves;
- registrar, filtrar, editar, concluir e restaurar panes;
- anexar arquivos as panes;
- gerenciar catalogo de equipamentos, slots, itens fisicos e controles de vencimento;
- consultar inventario por aeronave;
- operar com armazenamento local ou Cloudflare R2.

### 1.3 Visao do Produto

O produto e uma aplicacao web monolitica com:

- interface HTML server-side;
- API JSON;
- persistencia relacional via SQLAlchemy async;
- suporte a SQLite no desenvolvimento e opcao de PostgreSQL no futuro.

## 2. Perfis de Usuario

- Administrador
- Encarregado
- Mantenedor

## 3. Requisitos Funcionais

### 3.1 Autenticacao e Usuario

- RF-01: o sistema deve permitir login com usuario e senha.
- RF-02: o sistema deve impedir acesso sem autenticacao valida.
- RF-03: o sistema deve emitir access token JWT e refresh token apos login bem-sucedido.
- RF-04: o sistema deve permitir renovacao de acesso via refresh token valido.
- RF-05: o sistema deve permitir logout com invalidacao da sessao atual.
- RF-06: o sistema deve listar, criar, atualizar, desativar e restaurar usuarios conforme permissao.
- RF-07: o sistema deve permitir troca de senha pelo proprio usuario autenticado.
- RF-08: o sistema deve bloquear temporariamente contas com falhas repetidas de login.

### 3.2 Aeronaves

- RF-09: o sistema deve listar aeronaves cadastradas.
- RF-10: o sistema deve permitir cadastrar aeronave.
- RF-11: o sistema deve permitir consultar aeronave por identificador.
- RF-12: o sistema deve permitir atualizar dados da aeronave.
- RF-13: o sistema deve permitir alternar o status operacional da aeronave.

### 3.3 Panes

- RF-14: o sistema deve permitir registrar nova pane vinculada a uma aeronave.
- RF-15: o sistema deve listar panes com filtros por texto, status, aeronave, data e exclusao logica.
- RF-16: o sistema deve permitir consultar pane detalhada com anexos e responsaveis.
- RF-17: o sistema deve permitir editar panes abertas.
- RF-18: o sistema deve permitir concluir panes.
- RF-19: o sistema deve permitir anexar arquivos a pane.
- RF-20: o sistema deve permitir listar, baixar e remover anexos de pane conforme permissao.
- RF-21: o sistema deve permitir adicionar responsaveis a uma pane.
- RF-22: o sistema deve permitir desativar e restaurar panes.

### 3.4 Equipamentos e Inventario

- RF-23: o sistema deve permitir cadastrar modelos de equipamento.
- RF-24: o sistema deve permitir cadastrar slots de inventario vinculados a modelo.
- RF-25: o sistema deve permitir cadastrar itens fisicos por modelo e numero de serie.
- RF-26: o sistema deve permitir vincular tipos de controle a um modelo de equipamento.
- RF-27: o sistema deve criar controles de vencimento para itens conforme associacao de modelo e controle.
- RF-28: o sistema deve permitir registrar execucao de controle de vencimento.
- RF-29: o sistema deve permitir consultar controles de vencimento por item.
- RF-30: o sistema deve permitir instalar e remover itens em aeronaves.
- RF-31: o sistema deve permitir consultar o inventario atual por aeronave.
- RF-32: o sistema deve permitir consultar o historico recente de movimentacoes de inventario.
- RF-33: o sistema deve permitir ajustar o numero de serie real de um slot.

### 3.5 Interface Web

- RF-34: o sistema deve disponibilizar pagina principal para panes.
- RF-35: o sistema deve disponibilizar tela de detalhes de pane.
- RF-36: o sistema deve disponibilizar telas de efetivo, aeronaves e inventario.
- RF-37: o sistema deve exibir feedback visual de operacoes bem sucedidas ou rejeitadas.

## 4. Requisitos Nao Funcionais

- RNF-01: o sistema deve responder dentro de tempo aceitavel para uso operacional, com meta de menos de 2 segundos para operacoes comuns.
- RNF-02: o sistema deve proteger acesso com JWT, hash de senha, CSRF, rate limiting e headers de seguranca.
- RNF-03: o sistema deve manter rastreabilidade com auditoria de datas, soft delete e blacklist de tokens.
- RNF-04: o sistema deve funcionar em SQLite no desenvolvimento.
- RNF-05: o sistema deve permitir uso com PostgreSQL em ambiente apropriado.
- RNF-06: o sistema deve ser testavel com banco isolado em memoria.
- RNF-07: o sistema deve manter separacao clara entre router, service, schema e model.
- RNF-08: o sistema deve permitir armazenamento local ou em Cloudflare R2.

## 5. Regras de Negocio

- RN-01: toda pane deve estar vinculada a uma aeronave.
- RN-02: o status inicial de pane deve ser `ABERTA`.
- RN-03: apenas panes `ABERTA` podem ser editadas.
- RN-04: ao concluir uma pane, a data de conclusao deve ser preenchida automaticamente.
- RN-05: descricao vazia de pane deve virar `AGUARDANDO EDICAO`.
- RN-06: apenas `ENCARREGADO` e `ADMINISTRADOR` podem executar operacoes administrativas.
- RN-07: o usuario `MANTENEDOR` pode assumir responsabilidade somente para si mesmo.
- RN-08: aeronave, modelo de equipamento, slot e item fisico nao podem ter duplicidade nos campos unicos definidos no banco.
- RN-09: o acesso autenticado deve aceitar header `Authorization` e cookie `saa29_token`.
- RN-10: logout deve invalidar o token atual por blacklist.
- RN-11: um item fisico pode ter multiplos controles de vencimento, um por tipo de controle.
- RN-12: a associacao de controle a modelo deve propagar o controle para os itens existentes daquele modelo.

## 6. Modulos

- Autenticacao e usuarios
- Aeronaves
- Panes
- Equipamentos e inventario
- Upload e storage
- Interface web

## 7. Fora de Escopo

- dashboard analitico avancado;
- integracao com sistemas externos de manutencao;
- app mobile nativo;
- autenticao federada externa;
- workflow completo de inspecoes nao implementado ainda.
