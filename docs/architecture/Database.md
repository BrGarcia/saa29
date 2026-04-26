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
| **5. Vencimentos** | `tipos_controle`, `equipamento_controles`, `controle_vencimentos`, `prorrogacoes` | Implementado |
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
| `serial_number` | String(50) | UNIQUE, NOT NULL, INDEX | Numero de serie |
| `matricula` | String(20) | UNIQUE, NOT NULL, INDEX | Matricula operacional |
| `modelo` | String(50) | NOT NULL, default `A-29` | Modelo da aeronave |
| `status` | String(20) | NOT NULL, default `OPERACIONAL` | `OPERACIONAL` \| `INSPEÇÃO` \| `ESTOCADA` |

---

## 5. Dominio de Equipamentos (Fisico)

### 5.1 Modelos de Equipamento (PN)
**Tabela:** `modelos_equipamento`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Identificador único |
| `part_number` | String(50) | UNIQUE, NOT NULL | Part Number |
| `nome_generico` | String(100) | NOT NULL | Nome do equipamento |

### 5.2 Itens de Equipamento (SN)
**Tabela:** `itens_equipamento`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Identificador único |
| `modelo_id` | UUID | FK | Referência ao PN |
| `numero_serie` | String(100) | NOT NULL | Serial Number físico |

### 5.3 Instalacoes
**Tabela:** `instalacoes`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `item_id` | UUID | FK | Item instalado |
| `aeronave_id` | UUID | FK | Aeronave destino |
| `slot_id` | UUID | FK | Posição física |
| `data_instalacao` | Date | NOT NULL | Data da instalação |

---

## 6. Dominio de Vencimentos (Temporal)

### 6.1 Tipos de Controle
**Tabela:** `tipos_controle`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Identificador único |
| `nome` | String(10) | UNIQUE | Código (CRI, TLV, etc) |

### 6.2 Controle de Vencimentos
**Tabela:** `controle_vencimentos`  
| Coluna | Tipo | Restricoes | Descricao |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PK | Identificador único |
| `item_id` | UUID | FK | Item controlado |
| `data_ultima_exec` | Date | nullable | Última execução |
| `data_vencimento` | Date | nullable | Próximo vencimento |
| `status` | String(20) | NOT NULL | OK, VENCENDO, VENCIDO, PENDENTE |

---

## 7. Dominio de Panes

(Mantém as especificações originais de `panes`, `anexos` e `pane_responsaveis`).

---

## 8. Diagramas e Consultas
(Mantém os diagramas Mermaid e consultas SQL originais).
