# Dashboard de Testes TDD - SAA29

Este diretório centraliza a documentação de todos os testes do sistema, organizados por domínios de negócio. Para implementar novos testes, oriente-se pelos documentos específicos abaixo.

## 1. Dashboard de Status Geral

| Domínio | Documento de Referência | Testes Unitários | Testes de API | Status Geral |
| :--- | :--- | :--- | :--- | :--- |
| **Core (Auth/Usuários)** | [tdd_auth.md](tdd_auth.md) | ✅ 100% | ✅ 100% | **Estável** |
| **Operacional (Anv/Panes)** | [tdd_operacional.md](tdd_operacional.md) | ✅ 90% | ✅ 80% | **Polimento** |
| **Logística (Inv/Vencim)** | [tdd_logistica.md](tdd_logistica.md) | 🟡 60% | 🟡 40% | **Em Desenvolvimento** |

---

## 2. Estrutura de Documentação

Para manter a organização, não criamos arquivos por "funcionalidade", mas por **Domínio**:

1.  **[tdd_auth.md](tdd_auth.md):** Tudo relacionado a login, tokens JWT, criação de usuários e níveis de acesso (RBAC).
2.  **[tdd_operacional.md](tdd_operacional.md):** Ciclo de vida da aeronave e gerenciamento de panes (abertura, fechamento, correção).
3.  **[tdd_logistica.md](tdd_logistica.md):** Catálogo de PNs, controle de números de série, situação do inventário nas aeronaves e regras de periodicidade/vencimento.

---

## 3. Como usar com Agentes de IA

Quando solicitar a criação de um teste, basta dizer:
> "Leia a pasta `docs/tdd/` e implemente os testes pendentes no domínio de [Logística/Operacional/Auth]."

Os arquivos seguem o padrão:
- **Cenários de Teste (CT):** Descrição clara da entrada e resultado esperado.
- **Falhas Conhecidas:** Registro de bugs encontrados que impedem o teste de passar (Dívida Técnica).

---

## 4. Comandos Rápidos

```bash
# Rodar todos os testes
python -m pytest

# Rodar um domínio específico
python -m pytest tests/unit/test_auth.py
python -m pytest tests/unit/test_aeronaves.py tests/unit/test_panes.py
python -m pytest tests/unit/test_equipamentos.py tests/unit/test_inventario.py
```
