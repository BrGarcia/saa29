# Role-Based Access Control (RBAC) - SAA29

Este documento descreve a matriz de permissões e a implementação técnica do controle de acesso baseado em papéis (RBAC) no sistema SAA29.

A modelagem foi ajustada para refletir melhor a realidade operacional da manutenção aeronáutica, separando claramente os papéis de execução, coordenação e fiscalização.

---

## 1. Perfis de Usuário (Roles)

O sistema possui quatro níveis de acesso, definidos no enum `TipoPapel` (`app/shared/core/enums.py`):

1. **MANTENEDOR**  
   Perfil operacional responsável pela execução das tarefas de manutenção, registro de panes e baixa de serviços.

2. **ENCARREGADO**  
   Responsável pela coordenação da equipe e gestão operacional da manutenção. Atua na distribuição de tarefas e controle do fluxo de trabalho.

3. **INSPETOR**  
   Responsável pela fiscalização técnica, controle de qualidade e gestão de inspeções e vencimentos.  
   **Não executa tarefas**, atuando exclusivamente como autoridade técnica e de validação.

4. **ADMINISTRADOR**  
   Gestão completa do sistema, incluindo efetivo, frota e configurações. Possui todas as permissões.

---

## 2. Matriz de Permissões

| Módulo | Funcionalidade                           | Man | Enc | Insp | Adm |

### **Geral**
| | Login / Logout / Alterar própria senha          | ✅ | ✅ | ✅ | ✅ |

### **Panes**
| | Registrar nova pane                             | ✅ | ✅ | ✅ | ✅ |
| | Visualizar listagem e detalhes                  | ✅ | ✅ | ✅ | ✅ |
| | Adicionar anexos e comentários                  | ✅ | ✅ | ❌ | ✅ |
| | Assumir responsabilidade (si mesmo)             | ✅ | ✅ | ❌ | ✅ |
| | Atribuir responsabilidade a terceiros           | ❌ | ✅ | ❌ | ✅ |
| | Editar descrição / sistema (após criação)       | ❌ | ✅ | ❌ | ✅ |
| | Concluir / fechar pane                          | ✅ | ✅ | ❌ | ✅ |
| | Excluir (soft delete) / Restaurar pane          | ❌ | ✅ | ❌ | ✅ |

### **Aeronaves**
| | Listar e detalhar frota                         | ✅ | ✅ | ✅ | ✅ |
| | Alternar status operacional                     | ❌ | ✅ | ✅ | ✅ |
| | Atualizar dados técnicos                        | ❌ | ❌ | ❌ | ✅ |
| | Cadastrar nova aeronave                         | ❌ | ❌ | ❌ | ✅ |

### **Equipamentos**
| | Consultar inventário e modelos                  | ✅ | ✅ | ✅ | ✅ |
| | Consultar histórico de movimentações            | ✅ | ✅ | ✅ | ✅ |
| | Cadastrar PN / Slot / Item físico               | ❌ | ❌ | ❌ | ✅ |
| | Instalar / Remover equipamento                  | ✅ | ✅ | ❌ | ✅ |
| | Ajustar S/N real (Sincronismo)                  | ✅ | ✅ | ❌ | ✅ |

### **Vencimentos**
| | Consultar matriz de vencimentos                 | ✅ | ✅ | ✅ | ✅ |
| | Registrar execução de tarefa                    | ✅ | ✅ | ❌ | ✅ |
| | Controlar vencimentos (análise)                 | ❌ | ✅ | ✅ | ✅ |
| | Prorrogar vencimento (Engenharia)               | ❌ | ✅ | ✅ | ✅ |
| | Gerenciar regras de periodicidade               | ❌ | ❌ | ❌ | ✅ |

> Nota: A prorrogação de vencimento exige justificativa técnica (assessoramento técnico).

---

### **Inspeções**
| | Listar inspeções e catálogo                     | ✅ | ✅ | ✅ | ✅ |
| | Executar tarefa (checklist)                     | ✅ | ✅ | ❌ | ✅ |
| | Abrir inspeção                                  | ❌ | ✅ | ✅ | ✅ |
| | Cancelar inspeção                               | ❌ | ✅ | ✅ | ✅ |
| | Concluir inspeção                               | ❌ | ✅ | ✅ | ✅ |
| | Validar inspeção (qualidade)                    | ❌ | ✅ | ✅ | ✅ |
| | Gerenciar tipos e catálogo de tarefas           | ❌ | ❌ | ❌ | ✅ |

---

### **Administração**
| | Gerenciar Efetivo (Usuários)                    | ❌ | ❌ | ❌ | ✅ |
| | Acesso à página de Configurações                | ❌ | ❌ | ❌ | ✅ |

---

## 3. Implementação Técnica

O controle de acesso é aplicado em duas camadas:

---

### 3.1 Camada de API (Back-end)

Utiliza injeção de dependência do FastAPI (`app/bootstrap/dependencies.py`):

- `CurrentUser` → Usuário autenticado
- `EncarregadoOuAdmin` → ENCARREGADO ou ADMINISTRADOR
- `InspetorOuAdmin` → INSPETOR ou ADMINISTRADOR
- `AdminRequired` → Apenas ADMINISTRADOR

#### Exemplo:

```python
@router.post("/")
async def abrir_inspecao(
    dados: schemas.InspecaoCreate,
    db: DBSession,
    usuario: EncarregadoOuAdmin

3.2 Camada de Interface (Front-end)

As rotas em app/web/pages/router.py controlam o acesso às páginas:

@router.get("/efetivo", response_class=HTMLResponse)
async def efetivo_page(
    request: Request,
    _=Depends(require_role("ADMINISTRADOR"))
):
    return templates.TemplateResponse("efetivo.html", {"request": request})

    Elementos de interface (botões, ações críticas) devem ser:

ocultados por perfil
controlados via resposta do endpoint /auth/me
protegidos também no backend (nunca confiar apenas no front)

4. Auditoria e Rastreabilidade

Todas as ações críticas (conclusão de panes, registro de vencimentos, alterações de inventário) gravam o `usuario_id` do executor no banco de dados, permitindo a rastreabilidade total das operações realizadas por cada perfil: 

usuario_id
data/hora
tipo da ação


5. Modelo Conceitual de Papéis

O sistema segue a seguinte separação lógica:

MANTENEDOR → EXECUTA
ENCARREGADO → COORDENA
INSPETOR → FISCALIZA
ADMINISTRADOR → GERENCIA O SISTEMA

6. Diretrizes Importantes
O INSPETOR não executa tarefas
O ENCARREGADO não valida qualidade final
O ADMINISTRADOR não deve ser usado na operação diária
Toda ação crítica deve ser auditável
Backend é a fonte de verdade para autorização

7. Conclusão

A introdução do papel de INSPETOR torna o sistema mais aderente à realidade da manutenção aeronáutica, separando claramente execução, coordenação e fiscalização.

Essa estrutura melhora:

controle operacional
qualidade da manutenção
governança do sistema
capacidade de auditoria