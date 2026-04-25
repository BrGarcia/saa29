# TDD: Operacional (Aeronaves / Panes)

Documentação de testes para o ciclo de vida operacional da frota e manutenção.

**Arquivos de testes:** `tests/unit/test_aeronaves.py`, `tests/unit/test_panes.py`

## 1. Cenários de Teste

### 1.1 Gestão de Aeronaves
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-O01 | Cadastro de Aeronave | Criar registro com status OPERACIONAL. | ✅ |
| CT-O02 | Matrícula Duplicada | Lançar erro 409 Conflict. | ✅ |
| CT-O03 | Inativação de Aeronave | Mudar status para INATIVA (Toggle). | ✅ |
| CT-O04 | Listar Aeronaves | Filtrar inativas por padrão. | ✅ |

### 1.2 Gerenciamento de Panes
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-O05 | Abertura de Pane | Nova pane associada à aeronave com status ABERTA. | ✅ |
| CT-O06 | Registro de Correção | Pane passa para status CORRIGIDA. | ✅ |
| CT-O07 | Fechamento de Pane | Apenas ENCARREGADO/ADMIN pode fechar. | ✅ |
| CT-O08 | Histórico de Panes | Listar panes por período e aeronave. | ✅ |

---

## 2. Falhas Identificadas / Dívida Técnica
- **Ajuste de Status:** Verificar se a lógica de toggle de status em aeronaves é idempotente.
