# Modelo de Banco de Dados - SAA29
Documento sincronizado com o codigo-fonte em 24/04/2026.
Fontes da verdade:

- `app/modules/auth/models.py`
- `app/modules/aeronaves/models.py`
- `app/modules/panes/models.py`
- `app/modules/equipamentos/models.py`
- `app/shared/core/enums.py`

---

## 1. Visao Geral

O banco de dados atual do SAA29 possui os seguintes domínios:

| Dominio | Tabelas | Status |
| :--- | :--- | :---: |
| **1. Autenticacao** | `usuarios`, `token_blacklist`, `token_refresh` | Implementado |
| **2. Efetivo** | `indisponibilidades` | Em Planejamento |
| **3. Aeronaves** | `aeronaves` | Implementado |
| **4. Equipamentos** | `modelos_equipamento`, `slots_inventario`, `itens_equipamento`, `instalacoes` | Implementado |
| **5. Vencimentos** | `tipos_controle`, `equipamento_controles`, `controle_vencimentos`, `prorrogacoes_vencimento` | Implementado |
| **6. Panes** | `panes`, `anexos`, `pane_responsaveis` | Implementado |

---

## 2. Dominio de Autenticacao

### 2.1 Usuarios

**Tabela:** `usuarios`  
**Arquivo:** `app/modules/auth/models.py` -> classe `Usuario`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador unico |
| `nome` | String(150) | NOT NULL | Nome completo |
| `posto` | String(30) | NOT NULL | Posto ou graduacao |
| `especialidade` | String(50) | nullable | Especialidade tecnica |
| `funcao` | String(50) | NOT NULL | `ADMINISTRADOR` \| `ENCARREGADO` \| `MANTENEDOR` |
| `ramal` | String(20) | nullable | Ramal de contato |
| `trigrama` | String(3) | nullable | Identificacao curta |
| `username` | String(50) | UNIQUE, NOT NULL, INDEX | Login do usuario |
| `senha_hash` | String(255) | NOT NULL | Hash bcrypt |
| `ativo` | bool | NOT NULL, INDEX, default `True` | Exclusao logica |
| `failed_login_attempts` | int | NOT NULL, default `0` | Bloqueio por tentativa |
| `locked_until` | DateTime tz | nullable | Bloqueio temporario |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

### 2.2 Token Blacklist e Refresh
(Mantém as especificações originais de `token_blacklist` e `token_refresh`).

---

## 3. Dominio de Efetivo [PLANEJADO]

### 3.1 Indisponibilidades

**Tabela:** `indisponibilidades`  
**Arquivo:** `app/modules/efetivo/models.py` (Proposto)

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador unico |
| `usuario_id` | UUID | FK -> `usuarios.id`, NOT NULL | Militar afastado |
| `tipo` | String(20) | NOT NULL | `FERIAS` \| `DISPENSA` \| `MISSAO` \| `FOLGA` |
| `data_inicio` | Date | NOT NULL | Inicio do afastamento |
| `data_fim` | Date | NOT NULL | Fim previsto |
| `observacao` | String(500) | nullable | Justificativa ou numero do BI |

---

## 4. Dominio de Aeronaves

### 4.1 Aeronaves

**Tabela:** `aeronaves`  
**Arquivo:** `app/modules/aeronaves/models.py` -> classe `Aeronave`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador unico |
| `part_number` | String(50) | nullable | Part number da aeronave |
| `serial_number` | String(50) | UNIQUE, NOT NULL, INDEX | Numero de serie |
| `matricula` | String(20) | UNIQUE, NOT NULL, INDEX | Matricula operacional |
| `modelo` | String(50) | NOT NULL, default `A-29` | Modelo da aeronave |
| `status` | String(20) | NOT NULL, default `DISPONIVEL` | `DISPONIVEL` \| `INDISPONIVEL` \| `INSPEÇÃO` \| `ESTOCADA` \| `INATIVA` |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

---

## 5. Dominio de Equipamentos (Fisico)

Arquivo base: `app/modules/equipamentos/models.py`

### 5.1 Modelos de Equipamento (PN)
**Tabela:** `modelos_equipamento`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `part_number` | String(50) | UNIQUE, NOT NULL, INDEX | Part Number |
| `nome_generico` | String(100) | NOT NULL | Nome do equipamento |
| `descricao` | String(500) | nullable | Descrição adicional |
| `created_at` | DateTime tz | default `now()` | Auditoria |

### 5.2 Slots de Inventário
**Tabela:** `slots_inventario`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `nome_posicao` | String(100) | NOT NULL, INDEX | Posição na aeronave (ex: MDP1) |
| `sistema` | String(50) | nullable | Sistema vinculado |
| `modelo_id` | UUID | FK -> `modelos_equipamento.id`, NOT NULL | PN exigido para a posição |

### 5.3 Itens de Equipamento (SN)
**Tabela:** `itens_equipamento`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `modelo_id` | UUID | FK -> `modelos_equipamento.id`, NOT NULL, INDEX | Referência ao PN |
| `numero_serie` | String(100) | NOT NULL, INDEX | Serial Number físico |
| `status` | String(20) | NOT NULL, default `ATIVO` | `ATIVO` \| `ESTOQUE` \| `REMOVIDO` |
| `created_at` | DateTime tz | default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |
*Restrição: UNIQUE(modelo_id, numero_serie).*

### 5.4 Instalacoes
**Tabela:** `instalacoes`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `item_id` | UUID | FK -> `itens_equipamento.id`, NOT NULL, INDEX | Item instalado |
| `aeronave_id` | UUID | FK -> `aeronaves.id`, NOT NULL, INDEX | Aeronave destino |
| `slot_id` | UUID | FK -> `slots_inventario.id`, NOT NULL, INDEX | Posição física |
| `usuario_id` | UUID | FK -> `usuarios.id`, nullable | Usuário que registrou |
| `data_instalacao` | Date | NOT NULL | Data da instalação |
| `data_remocao` | Date | nullable | Data da remoção (se removido) |
| `created_at` | DateTime tz | default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

---

## 6. Dominio de Vencimentos (Temporal)

Arquivo base: `app/modules/equipamentos/models.py` (compartilhado com equipamentos físicos)

### 6.1 Tipos de Controle
**Tabela:** `tipos_controle`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `nome` | String(10) | UNIQUE, NOT NULL, INDEX | Código (CRI, TLV, etc) |
| `descricao` | String(300) | nullable | Descrição detalhada do tipo |
| `created_at` | DateTime tz | default `now()` | Auditoria |

### 6.2 Equipamento Controles (Templates)
**Tabela:** `equipamento_controles`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `modelo_id` | UUID | FK -> `modelos_equipamento.id`, NOT NULL | PN base |
| `tipo_controle_id` | UUID | FK -> `tipos_controle.id`, NOT NULL | Tipo de controle vinculado |
| `periodicidade_meses` | int | NOT NULL | Prazo padrão para o PN |
*Restrição: UNIQUE(modelo_id, tipo_controle_id).*

### 6.3 Controle de Vencimentos
**Tabela:** `controle_vencimentos`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `item_id` | UUID | FK -> `itens_equipamento.id`, NOT NULL, INDEX | Item físico controlado |
| `tipo_controle_id` | UUID | FK -> `tipos_controle.id`, NOT NULL | Referência ao tipo |
| `data_ultima_exec` | Date | nullable | Última execução real |
| `data_vencimento` | Date | nullable, INDEX | Próximo vencimento |
| `status` | String(20) | NOT NULL, default `OK` | `OK` \| `VENCENDO` \| `VENCIDO` \| `PRORROGADO` |
| `origem` | String(20) | NOT NULL, default `PADRAO` | `PADRAO` \| `ESPECIFICO` |
| `created_at` | DateTime tz | default `now()` | Auditoria |
*Restrição: UNIQUE(item_id, tipo_controle_id).*

### 6.4 Prorrogações de Vencimento
**Tabela:** `prorrogacoes_vencimento`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `controle_id` | UUID | FK -> `controle_vencimentos.id`, NOT NULL, INDEX | Controle estendido |
| `numero_documento` | String(50) | NOT NULL | Documento autorizador |
| `data_concessao` | Date | NOT NULL | Data da autorização |
| `data_nova_vencimento` | Date | NOT NULL | Nova data teto |
| `dias_adicionais` | int | NOT NULL | Tempo extra |
| `motivo` | String(500) | nullable | Motivo técnico |
| `observacao` | String(500) | nullable | Extra |
| `registrado_por_id`| UUID | FK -> `usuarios.id`, nullable | Usuário vinculante |
| `ativo` | bool | NOT NULL, default `True` | Se está ativa ou revogada |
| `created_at` | DateTime tz | default `now()` | Auditoria |

---

## 7. Dominio de Panes

Arquivo base: `app/modules/panes/models.py`

### 7.1 Panes
**Tabela:** `panes`
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `aeronave_id` | UUID | FK -> `aeronaves.id`, NOT NULL, INDEX | Aeronave afetada |
| `status` | String(20) | NOT NULL, default `ABERTA`, INDEX | `ABERTA` \| `RESOLVIDA` |
| `sistema_subsistema` | String(100) | nullable | Sistema afetado |
| `descricao` | Text | NOT NULL | Detalhes da pane |
| `data_abertura` | DateTime tz | NOT NULL, default `now()` | Abertura |
| `data_conclusao` | DateTime tz | nullable | Quando foi fechada |
| `observacao_conclusao` | Text | nullable | Ação corretiva tomada |
| `comentarios` | Text | nullable | Observações internas |
| `ativo` | bool | default `True`, INDEX | Soft delete |
| `criado_por_id` | UUID | FK -> `usuarios.id`, NOT NULL | Responsável abertura |
| `concluido_por_id` | UUID | FK -> `usuarios.id`, nullable | Responsável fechamento |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

### 7.2 Anexos
**Tabela:** `anexos`
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `pane_id` | UUID | FK -> `panes.id`, NOT NULL, INDEX | Pane relacionada |
| `caminho_arquivo` | String(500) | NOT NULL | Caminho salvo |
| `tipo` | String(20) | NOT NULL, default `IMAGEM` | `IMAGEM` \| `DOCUMENTO` |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

### 7.3 Pane Responsáveis
**Tabela:** `pane_responsaveis`
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `pane_id` | UUID | FK -> `panes.id`, NOT NULL, INDEX | Pane referenciada |
| `usuario_id` | UUID | FK -> `usuarios.id`, NOT NULL | Usuário delegado |
| `papel` | String(30) | NOT NULL | Papel atuante |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

---

## 8. Diagramas e Consultas
(Mantém os diagramas Mermaid e consultas SQL originais).


# 9. Dominio de Inspecoes

Arquivo base sugerido: `app/modules/inspecoes/models.py`

---

## 9.1 Tipos de Inspecao

**Tabela:** `tipos_inspecao`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `codigo` | String(20) | UNIQUE, NOT NULL, INDEX | Código (Y, 2Y, A, 4A) |
| `nome` | String(100) | NOT NULL | Nome da inspeção |
| `descricao` | String(300) | nullable | Descrição detalhada |
| `ativa` | bool | NOT NULL, default `True` | Controle de uso |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

---

## 9.2 Catalogo de Tarefas de Inspecao

**Tabela:** `tarefas_inspecao`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `nome` | String(150) | NOT NULL | Nome curto da tarefa |
| `descricao` | Text | NOT NULL | Descrição detalhada |
| `referencia` | String(100) | nullable | Referência técnica (manual, MPD, etc) |
| `ativa` | bool | NOT NULL, default `True` | Controle de uso |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

---

## 9.3 Vinculo Tipo de Inspecao x Tarefas

**Tabela:** `tipos_inspecao_tarefas`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `tipo_inspecao_id` | UUID | FK -> `tipos_inspecao.id`, NOT NULL, INDEX | Tipo de inspeção |
| `tarefa_id` | UUID | FK -> `tarefas_inspecao.id`, NOT NULL, INDEX | Tarefa vinculada |
| `ordem` | int | nullable | Ordem de execução |
| `obrigatoria` | bool | NOT NULL, default `True` | Se a tarefa é obrigatória |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

**Restrição:** UNIQUE(`tipo_inspecao_id`, `tarefa_id`)

---

## 9.4 Evento de Inspecao (Entrada da Aeronave)

**Tabela:** `inspecao_eventos`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `aeronave_id` | UUID | FK -> `aeronaves.id`, NOT NULL, INDEX | Aeronave em inspeção |
| `status` | String(20) | NOT NULL, default `ABERTA`, INDEX | `ABERTA` \| `EM_EXECUCAO` \| `CONCLUIDA` \| `CANCELADA` |
| `observacao` | Text | nullable | Observações gerais |
| `aberta_por_id` | UUID | FK -> `usuarios.id`, NOT NULL | Responsável pela abertura |
| `aberta_em` | DateTime tz | NOT NULL, default `now()` | Data de abertura |
| `concluida_em` | DateTime tz | nullable | Data de conclusão |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

---

## 9.5 Tipos Aplicados ao Evento

**Tabela:** `inspecao_evento_tipos`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `evento_id` | UUID | FK -> `inspecao_eventos.id`, NOT NULL, INDEX | Evento de inspeção |
| `tipo_inspecao_id` | UUID | FK -> `tipos_inspecao.id`, NOT NULL | Tipo aplicado |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |

**Restrição:** UNIQUE(`evento_id`, `tipo_inspecao_id`)

---

## 9.6 Tarefas Executadas na Inspecao

**Tabela:** `inspecao_tarefas`

| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK, default `uuid4` | Identificador único |
| `evento_id` | UUID | FK -> `inspecao_eventos.id`, NOT NULL, INDEX | Evento vinculado |
| `tarefa_id` | UUID | FK -> `tarefas_inspecao.id`, nullable | Referência ao catálogo |
| `descricao` | Text | NOT NULL | Snapshot da tarefa (permite edição manual) |
| `origem` | String(20) | NOT NULL | `TEMPLATE` \| `MANUAL` |
| `status` | String(20) | NOT NULL, default `PENDENTE`, INDEX | `PENDENTE` \| `EM_EXECUCAO` \| `CONCLUIDA` |
| `observacao` | Text | nullable | Observações da execução |
| `executada_por_id` | UUID | FK -> `usuarios.id`, nullable | Quem executou |
| `executada_em` | DateTime tz | nullable | Data/hora da execução |
| `pane_id` | UUID | FK -> `panes.id`, nullable | Pane gerada (se houver) |
| `created_at` | DateTime tz | NOT NULL, default `now()` | Auditoria |
| `updated_at` | DateTime tz | nullable, onupdate `now()` | Auditoria |

---

## 9.7 Regras de Negócio (Importante)

### Geração de tarefas no evento

Ao criar um `inspecao_evento` com múltiplos tipos:

1. Buscar tarefas de cada tipo em `tipos_inspecao_tarefas`
2. Unificar pelo `tarefa_id`
3. Remover duplicadas
4. Inserir em `inspecao_tarefas` com:
   - `origem = TEMPLATE`
   - `descricao` copiada do catálogo (snapshot)

---

### Tarefas manuais

- Podem ser adicionadas diretamente em `inspecao_tarefas`
- `origem = MANUAL`
- `tarefa_id = NULL`

---

### Execução

Quando uma tarefa for concluída:
- Atualizar `status = CONCLUIDA`
- Preencher:
  - `executada_por_id`
  - `executada_em`

A UI usa:
- `usuarios.trigrama` + `executada_em` → badge visual

---

### Integração com Panes

Se houver anomalia:
- Criar registro em `panes`
- Vincular via `inspecao_tarefas.pane_id`

---

### Status da Aeronave

Durante inspeção:
- `aeronaves.status = INSPEÇÃO`

Ao concluir:
- Retornar para `DISPONIVEL` ou `INDISPONIVEL` conforme contexto

---

## 9.8 Relacionamentos

- `aeronaves 1 → N inspecao_eventos`
- `inspecao_eventos 1 → N inspecao_evento_tipos`
- `tipos_inspecao 1 → N inspecao_evento_tipos`
- `tipos_inspecao N → N tarefas_inspecao` (via `tipos_inspecao_tarefas`)
- `inspecao_eventos 1 → N inspecao_tarefas`
- `inspecao_tarefas 0..1 → 1 panes`
- `usuarios 1 → N execuções`

---

## 9.9 Decisão Arquitetural (Resumo)

- Catálogo central de tarefas → evita duplicação
- Tipos de inspeção → combináveis (Y, A, 2Y, 4A)
- Evento único por entrada → simplifica operação
- Snapshot da tarefa → protege histórico
- Deduplicação por `tarefa_id` → essencial
- Tarefa manual → flexibilidade operacional
- Integração com panes → reaproveita domínio existente