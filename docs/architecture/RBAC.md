# Role-Based Access Control (RBAC) - SAA29

Este documento descreve a matriz de permissões e a implementação técnica do controle de acesso baseado em papéis (RBAC) no sistema SAA29.

## 1. Perfis de Usuário (Roles)

O sistema possui três níveis de acesso, definidos no enum `TipoPapel` (`app/shared/core/enums.py`):

1.  **MANTENEDOR**: Perfil operacional focado na execução de manutenção e reporte de panes.
2.  **ENCARREGADO**: Gestão operacional da linha de voo, coordenação de equipe e controle de qualidade. Possui todas as permissões do Mantenedor.
3.  **ADMINISTRADOR**: Gestão total do sistema, incluindo efetivo e frota. Possui todas as permissões do Encarregado.

---

## 2. Matriz de Permissões

| Módulo 	| Funcionalidade 							| Mant| Enc |Adm |

| **Geral** 
| | Login / Logout / Alterar própria senha 				| ✅ | ✅ | ✅ |

| **Panes** 
| | Registrar nova pane 						        | ✅ | ✅ | ✅ |
| | Visualizar listagem e detalhes 						| ✅ | ✅ | ✅ |
| | Adicionar anexos e comentários 						| ✅ | ✅ | ✅ |
| | Assumir responsabilidade (si mesmo) 				| ✅ | ✅ | ✅ |
| | Atribuir responsabilidade a terceiros 				| ❌ | ✅ | ✅ |
| | Editar descrição / sistema (após criação) 			| ❌ | ✅ | ✅ |
| | Remover anexos / Concluir pane 						| ✅ | ✅ | ✅ |
| | Excluir (soft delete) / Restaurar pane 				| ❌ | ✅ | ✅ |

| **Aeronaves** 
| | Listar e detalhar frota 				            | ✅ | ✅ | ✅ |
| | Alternar status operacional 						| ❌ | ✅ | ✅ |
| | Atualizar dados técnicos 							| ❌ | ❌ | ✅ |
| | Cadastrar nova aeronave								| ❌ | ❌ | ✅ |

| **Equipamentos**
| | Consultar inventário e modelos 		                | ✅ | ✅ | ✅ |
| | Consultar histórico de movimentações 				| ✅ | ✅ | ✅ |
| | Cadastrar PN / Slot / Item físico 					| ❌ | ✅ | ✅ |
| | Instalar / Remover equipamento						| ✅ | ✅ | ✅ |
| | Ajustar S/N real (Sincronismo) 						| ✅ | ✅ | ✅ |

| **Vencimentos** 
| | Consultar matriz de vencimentos 			        | ✅ | ✅ | ✅ |
| | Registrar execução de tarefa 						| ✅ | ✅ | ✅ |
| | Gerenciar regras de periodicidade 					| ❌ | ❌ | ✅ |
| | Prorrogar vencimento (Engenharia) 			        | ❌ | ✅ | ✅ | * Nota: A prorrogação de vencimento exige justificativa técnica (Acessoramento Técnico do parque)

| **Inspeções** 
| | Listar inspeções e catálogo 			            | ✅ | ✅ | ✅ |
| | Executar tarefa (marcar checklist) 					| ✅ | ✅ | ✅ |
| | Abrir / Cancelar / Concluir inspeção	 			| ❌ | ✅ | ✅ |
| | Gerenciar Tipos e Catálogo de Tarefas 				| ❌ | ✅ | ✅ |

| **Administração**
| | Gerenciar Efetivo (Usuários) 					    | ❌ | ❌ | ✅ |
| | Acesso à página de Configurações 					| ❌ | ❌ | ✅ |

---

## 3. Implementação Técnica

O controle de acesso é aplicado de forma redundante em duas camadas:

### 3.1. Camada de API (Back-end)
Utiliza injeção de dependência do FastAPI (`app/bootstrap/dependencies.py`):

*   `CurrentUser`: Apenas garante que o usuário está autenticado.
*   `EncarregadoOuAdmin`: Restringe a operação aos papéis de ENCARREGADO ou ADMINISTRADOR.
*   `AdminRequired`: Restringe a operação exclusivamente ao papel de ADMINISTRADOR.

**Exemplo de uso:**
```python
@router.post("/")
async def abrir_inspecao(
    dados: schemas.InspecaoCreate,
    db: DBSession,
    usuario_atual: EncarregadoOuAdmin,  # Validação de papel
):
    ...
```

### 3.2. Camada de Interface (Front-end)
As rotas de página em `app/web/pages/router.py` protegem o acesso aos templates:

```python
@router.get("/efetivo", response_class=HTMLResponse)
async def efetivo_page(request: Request, _=Depends(require_role("ADMINISTRADOR"))):
    return templates.TemplateResponse("efetivo.html", {"request": request})
```

Além disso, elementos de UI (botões de exclusão, modais de admin) são ocultados via lógica de renderização condicional ou JavaScript baseado no perfil retornado pelo endpoint `/auth/me`.

---

## 4. Auditoria e Rastreabilidade

Todas as ações críticas (conclusão de panes, registro de vencimentos, alterações de inventário) gravam o `usuario_id` do executor no banco de dados, permitindo a rastreabilidade total das operações realizadas por cada perfil.
