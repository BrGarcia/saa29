# MODEL_DB.md  
**Modelo de Banco de Dados – Sistema de Gestão de Panes (Eletrônica A-29)**

## 1. Visão Geral

Este documento descreve a modelagem relacional inicial do banco de dados para o sistema de gestão de panes.

O modelo segue normalização básica (3FN) e separação por entidades principais.

---

## 2. Entidades Principais

### 2.1 Usuarios (Efetivo)

Tabela: usuarios

| Campo            | Tipo        | Descrição |
|------------------|------------|----------|
| id               | UUID / INT | Identificador único |
| nome             | VARCHAR    | Nome completo |
| posto            | VARCHAR    | Posto/Graduação |
| especialidade    | VARCHAR    | BMA, BET, etc |
| funcao           | VARCHAR    | Chefe, encarregado, etc |
| ramal            | VARCHAR    | Contato |
| username         | VARCHAR    | Login |
| senha_hash       | VARCHAR    | Senha criptografada |
| created_at       | TIMESTAMP  | Data de criação |

---

### 2.2 Aeronaves

Tabela: aeronaves

| Campo            | Tipo        | Descrição |
|------------------|------------|----------|
| id               | UUID / INT | Identificador |
| matricula        | VARCHAR    | Ex: 5956 |
| modelo           | VARCHAR    | Ex: A-29 |
| status           | VARCHAR    | Ativa, manutenção, etc |
| created_at       | TIMESTAMP  | Data |

---

### 2.3 Equipamentos

Tabela: equipamentos

| Campo            | Tipo        | Descrição |
|------------------|------------|----------|
| id               | UUID / INT | Identificador |
| nome             | VARCHAR    | Nome do equipamento |
| tipo             | VARCHAR    | Categoria |
| descricao        | TEXT       | Detalhes |
| created_at       | TIMESTAMP  | Data |

---

### 2.4 Panes

Tabela: panes

| Campo                | Tipo        | Descrição |
|----------------------|------------|----------|
| id                   | UUID / INT | Identificador |
| aeronave_id          | FK         | Relação com aeronave |
| status               | VARCHAR    | ABERTA / RESOLVIDA / PESQUISA |
| sistema_subsistema   | VARCHAR    | Identificação técnica |
| descricao            | TEXT       | Descrição da pane |
| data_abertura        | TIMESTAMP  | Automática |
| data_conclusao       | TIMESTAMP  | Preenchida ao concluir |
| criado_por           | FK         | Usuário |
| concluido_por        | FK         | Usuário |
| created_at           | TIMESTAMP  | Data |

---

### 2.5 Anexos

Tabela: anexos

| Campo            | Tipo        | Descrição |
|------------------|------------|----------|
| id               | UUID / INT | Identificador |
| pane_id          | FK         | Relação com pane |
| caminho_arquivo  | VARCHAR    | URL ou path |
| tipo             | VARCHAR    | imagem |
| created_at       | TIMESTAMP  | Data |

---

### 2.6 Relacionamento Operacional

Tabela: pane_responsaveis

| Campo            | Tipo        | Descrição |
|------------------|------------|----------|
| id               | UUID / INT | Identificador |
| pane_id          | FK         | Pane |
| usuario_id       | FK         | Militar |
| papel            | VARCHAR    | Responsável, executor |
| created_at       | TIMESTAMP  | Data |

---

## 3. Relacionamentos

- aeronaves 1:N panes  
- usuarios 1:N panes (criação/conclusão)  
- panes 1:N anexos  
- panes N:N usuarios (via pane_responsaveis)  

---

## 4. Índices Recomendados

- INDEX em panes(status)
- INDEX em panes(aeronave_id)
- INDEX em panes(data_abertura)
- INDEX em usuarios(username)

---

## 5. Regras de Integridade

- pane.aeronave_id obrigatório
- status com valores controlados (ENUM recomendado)
- data_conclusao só pode existir se status = RESOLVIDA
- descrição não pode ser nula (usar "AGUARDANDO EDICAO")

---

## 6. Observações Técnicas

- Banco recomendado: PostgreSQL
- Uso de UUID para escalabilidade
- Armazenamento de imagens via cloud (S3 ou similar)

---

## 7. Evoluções Futuras

- Histórico de alterações (audit log)
- Versionamento de panes
- Integração com manutenção programada
