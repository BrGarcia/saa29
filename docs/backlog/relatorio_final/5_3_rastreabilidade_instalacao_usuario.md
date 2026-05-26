# Backlog Item 5.3: Queda de Rastreabilidade na Instalação de Equipamentos (Usuario Nulo)

## 1. Descrição do Problema
O endpoint `/equipamentos/itens/{item_id}/instalar` ignorava os dados de identidade do usuário autenticado no router, invocando a camada de serviço sem passar o `usuario_id`. Isso causava a gravação de registros na tabela `instalacoes` com `usuario_id = NULL`, impossibilitando auditar quem realizou a movimentação aviônica física.

## 2. Plano de Implementação
1. **Passagem do Usuário no Router:** Em `app/modules/equipamentos/router.py`, modificar o endpoint de instalação para capturar `current_user: ExecucaoPermitida` (ou `CurrentUser` se aplicável).
2. **Atualização da assinatura do Service:** Atualizar a assinatura da função `instalar_item` em `app/modules/equipamentos/service.py` para incluir o argumento `usuario_id: uuid.UUID`.
3. **Associação no Modelo ORM:** Garantir que a instância de `Instalacao` receba explicitamente `usuario_id=usuario_id` antes de ser persistida via `db.add()`.

## 3. Critérios de Aceitação
* Qualquer chamada para o endpoint de instalação física de componente preenche a coluna `usuario_id` com o UUID do operador autenticado.
* O feed de movimentações e o histórico de auditoria exibem o trigrama correto do militar associado à instalação física do rádio/equipamento.
* Testes integrados validam que `instalacao.usuario_id == current_user.id` ao final do request.
