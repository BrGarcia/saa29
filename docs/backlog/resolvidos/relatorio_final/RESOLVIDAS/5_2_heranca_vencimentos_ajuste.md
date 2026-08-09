# Backlog Item 5.2: Omissão de Herança de Vencimentos em Ajustes de Inventário

## 1. Descrição do Problema
Ao registrar um ajuste de inventário (`ajustar_inventario_item`) com um Serial Number (S/N) inédito no banco, o sistema instanciava o `ItemEquipamento` no banco, mas não vinculava os prazos de vencimento associados ao Part Number correspondente (`EquipamentoControle`). Isso causava lacunas na matriz de vencimentos, com componentes operando sem monitoramento.

## 2. Plano de Implementação
1. **Helper único de criação de itens:** Extrair a lógica de herança de vencimentos de `criar_item_com_heranca` para um método utilitário reutilizável ou garantir sua chamada em `_obter_ou_criar_item_por_pn` em `app/modules/equipamentos/service.py`.
2. **Herdar periodicidade:**
   - Buscar os `EquipamentoControle` vinculados ao `modelo_id` do item físico criado.
   - Para cada regra, instanciar um `ControleVencimento` com o respectivo `tipo_controle_id`, vinculando ao `item_id` recém-criado, com status padrão inicial de `StatusVencimento.VENCIDO.value` (forçando que seja registrado um primeiro evento de calibração/execução).

## 3. Critérios de Aceitação
* Qualquer item cadastrado de forma automática via ajuste de inventário passa a constar com seus respectivos prazos na tabela `controle_vencimentos`.
* A matriz de vencimentos (`/vencimentos/matriz`) exibe o novo componente recém-cadastrado no status correto (iniciando em `VENCIDO` se nunca executado).
* O teste unitário `test_criar_item_herda_controles_do_equipamento` valida o fluxo tanto no cadastro direto quanto na via indireta de ajuste.
