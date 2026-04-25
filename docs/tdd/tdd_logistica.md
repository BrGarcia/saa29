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
| CT-L11 | Prorrogar Vencimento | Adicionar dias extras via documento da Engenharia. | ✅ |
| CT-L12 | Cancelar Prorrogação | Desativar extensão de prazo ativa. | ✅ |
| CT-L13 | Execução vs Prorrogação | Registrar execução deve desativar prorrogação ativa. | ✅ |
| CT-L14 | Matriz de Vencimentos | Gerar visão Frota x Equipamento x Controle. | ✅ |

---

## 2. Falhas Corrigidas e Dívida Técnica

### 2.1 Correção de Integridade em Instalações (IntegrityError)
- **Falha anterior:** `NOT NULL constraint failed: instalacoes.slot_id`.
- **Causa:** O endpoint `/itens/{item_id}/instalar` e o service correspondente não lidavam com o `slot_id`, que é obrigatório na arquitetura V2 (Vinculação Física x Slot).
- **Ações Realizadas:**
    1.  **Schema:** Atualizado `InstalacaoCreate` para incluir `slot_id` como campo obrigatório.
    2.  **Service:** Refatorado `instalar_item` para aceitar e persistir o `slot_id`.
    3.  **Router:** Ajustado o endpoint `POST /itens/{item_id}/instalar` para repassar o `slot_id` ao serviço.
    4.  **Testes:** Atualizado `tests/unit/test_equipamentos.py` para criar slots dinâmicos e fornecer IDs válidos nos testes de instalação/remoção.
- **Status:** ✅ Corrigido, validado e integrado.

### 2.2 Resolução de Conflitos de Unicidade (409 Conflict)
- **Falha:** Erros intermitentes ao criar aeronaves e PNs devido ao reuso de Serial Numbers e Matrículas entre testes (persistência de `db.commit()` no service).
- **Ação:** Implementado uso de prefixos e sufixos UUID nos helpers de teste (`criar_aeronave_helper`, `criar_equipamento_helper`) para garantir unicidade absoluta em cada execução.
- **Status:** ✅ Resolvido.

---

## 3. Ambiente e Dependências

### 3.1 Validação de Arquivos (libmagic)
- **Falha:** `ImportError` em testes de upload no módulo de Panes.
- **Solução:** Instalado `python-magic-bin` no ambiente Windows.
- **Status:** ✅ Ambiente configurado e testes passando.
