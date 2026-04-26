# Proposta de Implementação: Dashboard Central (Visão Geral)

## 1. Visão Geral e Objetivo
O objetivo deste Dashboard é atuar como o "Centro de Comando" do sistema SAA29. Ele fornecerá uma visão rápida, centralizada e intuitiva das principais pendências e do status atual da operação (aeronaves, manutenções, inventário e, futuramente, efetivo). 

A premissa principal de design é a **facilidade de uso e navegação intuitiva**. O usuário deve bater o olho e saber exatamente o que demanda atenção imediata, sem precisar navegar por múltiplos menus para descobrir.

## 2. Navegação e Acesso
- **Botão Superior:** Um botão ou link em destaque na barra de navegação superior (Header) chamado "Dashboard" ou "Visão Geral".
- **Acesso Global:** Como a barra superior é persistente, o usuário poderá voltar ao Dashboard de qualquer lugar do sistema com apenas um clique.
- **Home Page (Sugestão):** O Dashboard deve ser a primeira tela exibida logo após o login com sucesso, servindo como ponto de partida diário.

## 3. Estrutura Visual (Os Cards)
A tela será dividida em "Cards" (ou widgets) responsivos. Cada card resume um domínio e serve como um atalho rápido para a página detalhada daquele módulo.

### 3.1. Card: Panes Abertas
- **Conteúdo:** Exibe um contador grande com o total de panes com status `ABERTA` ou `EM_PESQUISA`. 
- **Lista Rápida:** Pode listar as 3 a 5 panes mais antigas ou críticas (ex: matrícula da aeronave e sistema afetado).
- **Ação:** Um botão "Ver todas as panes" que direciona para a listagem de panes já filtrada.

### 3.2. Card: Resumo de Vencimentos
- **Conteúdo:** Replicar o painel visual que já existe no topo da página de "Controle de Vencimentos".
- **Indicadores:** Quantidade de itens `VENCIDOS` (vermelho) e `VENCENDO` (amarelo/laranja nos próximos 30/60 dias).
- **Ação:** Clique direciona para o módulo de vencimentos para tratativas.

### 3.3. Card: Aeronaves em Inspeção
- **Conteúdo:** Lista rápida das matrículas das aeronaves que estão atualmente paradas para inspeção (manutenção programada).
- **Indicadores:** Pode mostrar o tipo de inspeção e a previsão de término, se houver.
- **Ação:** Direciona para o módulo de frota/inspeções.

### 3.4. Card: Últimas Alterações no Inventário
- **Conteúdo:** Um mini-feed (timeline) mostrando as movimentações mais recentes (ex: "Rádio VUHF S/N 123 instalado na FAB 5900", "Item XYZ removido").
- **Foco:** Apenas as últimas 5 ações para não poluir a tela.
- **Ação:** Direciona para o histórico completo do inventário.

### 3.5. Card: Indisponibilidade do Efetivo (Visão Futura)
- **Conteúdo:** Resumo de quem do setor eletrônico não está disponível no dia ou na semana (Férias, Serviço de Escala, Dispensa Médica, Missão).
- **Objetivo:** Ajudar o encarregado a saber rapidamente com quem ele pode contar no pátio hoje.

## 4. UX e Trade-offs (Funcionalidade vs. Simplicidade)
Como a prioridade é a **facilidade de uso**, o Dashboard deve ser primariamente **Informativo e Direcional**, e não um local de operação complexa. 

**Decisão arquitetural sugerida:** Não colocaremos botões de edição complexa (ex: "Concluir Pane", "Realizar Inspeção") diretamente no Dashboard. Isso exigiria modais complexos e sobrecarregaria a interface. O fluxo será: *Ler o resumo no Dashboard -> Clicar no card -> Operar na tela específica do módulo*. Isso mantém a interface limpa e o código modular.

---

## 5. Questões para Definição (Por favor, responda antes de codificarmos)

Para garantirmos que a implementação fique exatamente como você imagina, preciso da sua opinião nos seguintes pontos:

1. **Página Inicial:** Você concorda que o Dashboard seja a página inicial padrão logo após o login, ou prefere que a tela inicial continue sendo alguma outra (ex: lista de panes) e o Dashboard seja acessado apenas ao clicar no botão superior?
2. **Interatividade dos Cards:** Seguindo a regra da simplicidade, sugiro que clicar no Card leve o usuário para a página completa do módulo. Você prefere assim, ou gostaria de poder resolver pendências simples (como dar "OK" num vencimento) diretamente da tela do Dashboard sem mudar de página?
3. **Prioridade Visual:** Dos 4 cards iniciais (Panes, Vencimentos, Aeronaves em Inspeção, Inventário), qual deles é o mais crítico no dia a dia e deve ter o maior destaque na tela (ex: ficar no topo ou ocupar a largura inteira)?