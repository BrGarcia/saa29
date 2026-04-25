# TDD: Core (Auth / Usuários / Permissões)

Documentação de testes para a camada de segurança e gestão de usuários.

**Arquivos de testes:** `tests/unit/test_auth.py`

## 1. Cenários de Teste

### 1.1 Autenticação e JWT
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-A01 | Login com credenciais válidas | Retornar Token JWT e dados do usuário. | ✅ |
| CT-A02 | Login com senha incorreta | Retornar 401 Unauthorized. | ✅ |
| CT-A03 | Login com usuário inexistente | Retornar 401 Unauthorized. | ✅ |
| CT-A04 | Acesso com Token expirado | Retornar 401 (Token Expired). | ✅ |
| CT-A05 | Refresh Token | Gerar novo Access Token a partir do Refresh Token. | ✅ |

### 1.2 Gestão de Usuários e RBAC (Controle de Acesso)
| ID | Teste | Resultado Esperado | Status |
| :--- | :--- | :--- | :--- |
| CT-A06 | Criar usuário (Admin) | Novo usuário persistido no banco. | ✅ |
| CT-A07 | Bloqueio por múltiplas tentativas | Usuário bloqueado após 5 falhas. | ✅ |
| CT-A08 | Permissão MANTENEDOR | Acesso negado a rotas de configuração (403). | ✅ |
| CT-A09 | Permissão ENCARREGADO | Acesso permitido a rotas de inventário e panes. | ✅ |

---

## 2. Falhas Identificadas / Dívida Técnica
- *Nenhuma falha crítica impeditiva identificada no momento.*
