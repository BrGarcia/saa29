# SAA29 – Manual do Usuário e Operação

## 1. Introdução e Propósito do Projeto
O **SAA29 (Sistema de Gestão de Panes – Eletrônica A-29)** foi desenvolvido para centralizar, simplificar e dar transparência à gestão da manutenção de aviônicos da frota A-29. O foco principal é garantir que a informação sobre o estado das aeronaves e componentes flua sem ruídos entre quem executa a manutenção e quem a gerencia.

### Princípios do Sistema
*   **Simplicidade:** Interfaces diretas para ações rápidas no pátio ou oficina.
*   **Transparência:** Todos os níveis veem o mesmo estado atual da frota.
*   **Rastreabilidade:** Cada ação (abertura de pane, instalação de rádio, conclusão de inspeção) é registrada com autor e data.

---

## 2. Visão Geral dos Módulos

### 📊 Dashboard
É a sala de situação. Apresenta um resumo em tempo real:
*   **Status da Frota:** Quantas aeronaves estão disponíveis, em inspeção ou indisponíveis.
*   **Panes Ativas:** Lista rápida do que precisa de atenção imediata.
*   **Calendário:** Prazos de inspeções (DPE) e indisponibilidades de pessoal.

### ✈️ Frota (Aeronaves)
Gerenciamento central das células. Aqui se altera o status operacional da aeronave (Ex: DISPONÍVEL para INDISPONÍVEL).

### 🛠️ Panes
Onde o trabalho começa. Uma "Pane" é qualquer discrepância eletrônica encontrada.
*   Registro de descrição, sistema afetado (ATA) e anexos (fotos da falha).
*   Histórico de quem trabalhou e como a pane foi resolvida.

### 📦 Inventário e Equipamentos
Controle de "quem está onde". Permite instalar e remover componentes (S/N) de slots específicos das aeronaves, mantendo o histórico de movimentação de material.

### ⏳ Vencimentos
Monitoramento automático de prazos de calibração, inspeções de itens e limites de vida (TLV/CRI). O sistema avisa visualmente quando um item está próximo do vencimento.

### 📅 Inspeções
Gestão de revisões programadas (Fases Y, A, C). Inclui lista de tarefas obrigatórias que devem ser marcadas como concluídas para que a aeronave retorne ao status disponível.

---

## 3. Papéis e Responsabilidades

O sistema adapta-se ao seu nível de acesso. Veja o que é esperado de cada perfil:

### 🔧 Mantenedor
*   **O que faz:** Abre panes ao identificar falhas, registra a execução de tarefas de inspeção, instala/remove equipamentos e resolve panes.
*   **O que é esperado:** Registro fiel e detalhado das ações realizadas. Fotos de boa qualidade em panes facilitam o diagnóstico.
*   **O que não pode fazer:** Alterar configurações do sistema, gerenciar o efetivo ou apagar registros de terceiros.

### 🛡️ Inspetor
*   **O que faz:** Vistoria o trabalho realizado pelos mantenedores. Tem poder de validar ou reabrir tarefas e panes.
*   **O que é esperado:** Rigor na conferência. O Inspetor é a última barreira de segurança antes da aeronave voar.
*   **O que não pode fazer:** O Inspetor **não deve** ser o mesmo que executou a tarefa (segregação de funções).

### 📋 Encarregado
*   **O que faz:** Gerencia a prioridade das panes, aloca o pessoal e decide o status operacional da frota.
*   **O que é esperado:** Visão sistêmica. Manter o dashboard limpo e as prioridades claras para a equipe.
*   **O que não pode fazer:** Embora tenha permissões amplas, não deve atropelar o fluxo de inspeção sem a devida validação técnica.

### ⚙️ Administrador
*   **O que faz:** Configura o sistema, cadastra novos usuários, gerencia a frota e o catálogo de equipamentos.
*   **O que é esperado:** Manutenção da integridade dos dados e suporte aos usuários.

---

## 4. Guia de Referência Rápida (Passo a Passo)

### Para o Mantenedor: "Encontrei uma falha na aeronave"
1.  Acesse **Panes** > **Nova Pane**.
2.  Selecione a **Aeronave**, o **Sistema (ATA)** e descreva a falha.
3.  **Anexe uma foto** se possível. Clique em **Salvar**.
4.  Ao consertar, vá na pane e clique em **Resolver**, descrevendo a ação corretiva.

### Para o Encarregado: "Preciso saber quais aviões voam amanhã"
1.  Olhe o **Dashboard** no card **Status da Frota**.
2.  Aeronaves em **Verde (Disponível)** estão prontas.
3.  Aeronaves em **Laranja (Inspeção)**: clique para ver a data de conclusão prevista (DPE) no calendário.

### Para o Inspetor: "Preciso liberar uma aeronave que saiu de inspeção"
1.  Vá em **Inspeções** > Selecione a inspeção da aeronave.
2.  Confira se todas as tarefas estão **Concluídas**.
3.  Verifique se não há panes **Abertas** impeditivas para aquela aeronave.
4.  Clique em **Concluir Inspeção**. O status da aeronave voltará automaticamente para **Disponível**.

### Para Todos: "Vou sair de férias/licença"
1.  Acesse o módulo **Efetivo** (ou seu Perfil).
2.  Clique em **Registrar Indisponibilidade**.
3.  Selecione o motivo e o período. Isso aparecerá no calendário para o Encarregado planejar as equipes.

---

**Lembre-se:** Se não está no SAA29, não aconteceu. A transparência no registro é o que garante a segurança de voo de todos.
