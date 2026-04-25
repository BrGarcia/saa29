# TDD: Logística (Equipamentos / Inventário / Vencimentos)

Documentação de testes para a gestão de materiais, rastreabilidade física e controle de periodicidade.

**Arquivos de testes:** `tests/unit/test_equipamentos.py`, `tests/unit/test_inventario.py`

## 1. Cenários de Teste

### 1.1 Catálogo de Part Numbers (PN) e Itens (SN)
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-L01 | Cadastrar novo PN | Salvar modelo no catálogo (v1_x_stabilization). | ✅ |
| CT-L02 | PN Duplicado | Impedir criação e retornar 409. | ✅ |
| CT-L03 | Cadastrar Item Físico (SN) | Criar vínculo SN + PN. | ✅ |
| CT-L04 | Herança de Controles | Item herda automaticamente regras do modelo (PN). | ✅ |

### 1.2 Inventário de Aeronave
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-L05 | Listar Inventário por ANV | Retornar lista de slots e itens instalados. | ✅ |
| CT-L06 | Filtro de Inventário | Busca por nome de equipamento ou sistema. | ✅ |
| CT-L07 | Ajuste de Inventário | Sincronizar SN real com Slot da aeronave. | ✅ |

### 1.3 Regras de Vencimento e Periodicidade
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-L08 | Criar Regra por PN | Vincular PN a Controle com Meses. | ✅ |
| CT-L09 | Propagação de Regra | Criar ControleVencimento para itens existentes. | ✅ |
| CT-L10 | Registrar Execução | Calcular próxima data baseada na regra do PN. | ✅ |

---

## 2. Falhas Identificadas (Bugs Encontrados via TDD)

As falhas abaixo foram detectadas pela suite de testes e requerem correção no código-fonte:

### 2.1 Erro de Integridade em Instalações (IntegrityError)
- **Falha:** `NOT NULL constraint failed: instalacoes.slot_id`.
- **Causa:** O endpoint legacy `/itens/{item_id}/instalar` não envia o `slot_id` (que é obrigatório na arquitetura V2).
- **Ação:** Manter este teste como falha até que o endpoint seja atualizado ou substituído pelo "Ajuste de Inventário".

### 2.2 Persistência de Dados em Testes Unitários
- **Falha:** O uso de `db.commit()` nos serviços do `service.py` impede o rollback total no SQLite em memória.
- **Impacto:** Testes que usam a mesma aeronave ou PN podem entrar em conflito se rodados em sequência.
- **Ação:** Refatorar serviços para usar `flush()` em vez de `commit()`, delegando o commit para a camada de Router.
