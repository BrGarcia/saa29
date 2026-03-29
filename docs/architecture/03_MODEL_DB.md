from pathlib import Path

content = """# MODEL_DB.md  
**Modelo de Banco de Dados – Sistema de Gestão de Panes (Eletrônica A-29) – Versão Refinada**

---

## 1. Visão Geral

Este modelo contempla:

- Gestão de panes
- Controle de efetivo
- Gestão de aeronaves
- Controle avançado de equipamentos com rastreabilidade por número de série
- Sistema de vencimentos baseado em herança automática por tipo de equipamento

Banco recomendado: PostgreSQL

---

## 2. Entidades

---

### 2.1 Usuários (Efetivo)

Tabela: usuarios

- id (PK)
- nome
- posto
- especialidade
- funcao
- ramal
- trigrama (3 LETRAS)
- username (UNIQUE)
- senha_hash
- created_at

---

### 2.2 Aeronaves

Tabela: aeronaves

- id (PK)
- part_number
- serial_number (UNIQUE)
- matricula (UNIQUE)
- modelo
- status
- created_at

---

### 2.3 Equipamentos (Tipo / Part Number)

Tabela: equipamentos

- id (PK)
- part_number
- nome (ex: VUHF2, ELT, MDP)
- sistema (ex: COM, NAV, AP)
- descricao
- created_at

---

### 2.4 Tipos de Controle

Tabela: tipos_controle

- id (PK)
- nome (TBV, RBA, CRI)
- descricao
- periodicidade_meses
- created_at

---

### 2.5 Relação Equipamento x Controle (TEMPLATE)

Tabela: equipamento_controles

- id (PK)
- equipamento_id (FK)
- tipo_controle_id (FK)

CONSTRAINT UNIQUE(equipamento_id, tipo_controle_id)

---

### 2.6 Itens de Equipamento (Serial Number)

Tabela: itens_equipamento

- id (PK)
- equipamento_id (FK)
- numero_serie (UNIQUE)
- status (ativo, estoque, removido)
- created_at

---

### 2.7 Instalação em Aeronaves (Histórico)

Tabela: instalacoes

- id (PK)
- item_id (FK)
- aeronave_id (FK)
- data_instalacao
- data_remocao

---

### 2.8 Controle de Vencimentos (INSTÂNCIA REAL)

Tabela: controle_vencimentos

- id (PK)
- item_id (FK)
- tipo_controle_id (FK)
- data_ultima_exec
- data_vencimento
- status (OK, VENCENDO, VENCIDO)
- origem (PADRAO, ESPECIFICO)
- created_at

CONSTRAINT UNIQUE(item_id, tipo_controle_id)

---

### 2.9 Panes

Tabela: panes

- id (PK)
- aeronave_id (FK)
- status (ABERTA, EM_PESQUISA, RESOLVIDA)
- sistema_subsistema
- descricao
- data_abertura
- data_conclusao
- criado_por (FK usuarios)
- concluido_por (FK usuarios)
- created_at

---

### 2.10 Anexos

Tabela: anexos

- id (PK)
- pane_id (FK)
- caminho_arquivo
- tipo
- created_at

---

### 2.11 Responsáveis por Pane

Tabela: pane_responsaveis

- id (PK)
- pane_id (FK)
- usuario_id (FK)
- papel
- created_at

---

## 3. Relacionamentos

- equipamentos 1:N itens_equipamento  
- equipamentos N:N tipos_controle (via equipamento_controles)  
- itens_equipamento 1:N controle_vencimentos  
- itens_equipamento 1:N instalacoes  
- aeronaves 1:N instalacoes  
- aeronaves 1:N panes  
- panes 1:N anexos  
- panes N:N usuarios  

---

## 4. Regras de Negócio (Banco)

- Todo item deve herdar controles do seu equipamento
- Não permitir duplicidade de controle por item
- data_conclusao só existe se status = RESOLVIDA
- descrição padrão: "AGUARDANDO EDICAO"

---

## 5. Algoritmos de Herança

### 5.1 Ao criar ITEM

- Buscar controles do equipamento
- Criar registros em controle_vencimentos

---

### 5.2 Ao criar novo controle para equipamento

- Buscar todos os itens existentes
- Criar controles faltantes

---

## 6. Índices Recomendados

- INDEX em controle_vencimentos(status)
- INDEX em controle_vencimentos(data_vencimento)
- INDEX em itens_equipamento(equipamento_id)
- INDEX em panes(status)
- INDEX em panes(aeronave_id)

---

## 7. Observações Técnicas

- Usar UUID para escalabilidade
- Usar ENUM para status
- Armazenar imagens em cloud (S3 ou similar)

---

## 8. Evoluções Futuras

- Dashboard de vencimentos
- Alertas automáticos
- Auditoria completa
- Integração com manutenção programada

---

## 9. Conclusão

Modelo preparado para:

- Rastreabilidade completa por serial
- Controle de manutenção aeronáutica realista
- Escalabilidade e robustez operacional
"""

file_path = Path('/mnt/data/MODEL_DB_v2.md')
file_path.write_text(content)

file_path