# Planejamento: Módulo de Calendário

## 1. Visão Geral e Propósito
O Módulo de Calendário será o principal **agregador visual e interativo** do tempo e dos recursos do sistema SAA29. Sua função não é armazenar a regra de negócio de cada evento, mas sim fornecer uma interface unificada e rica onde gestores e mantenedores possam cruzar dados operacionais (inspeções) com a disponibilidade do fator humano (efetivo).

## 2. O Princípio da Modularidade
Conforme os padrões arquiteturais do projeto, este módulo servirá puramente como uma **camada de apresentação e orquestração**:
- **Módulo Calendário (App/Core)**: Responsável por renderizar a interface de tempo, fornecer os filtros, consolidar dados de múltiplos endpoints e despachar ações de criação (ex: abrir o formulário correto baseado no tipo de evento selecionado).
- **Módulo Efetivo (Indisponibilidades)**: Detém a persistência e as regras de Férias, Serviços, Consultas Médicas, Missões, Comissões, Dispensas e Voos.
- **Módulo Eventos Genéricos**: Para lançamentos administrativos (feriados, reuniões gerais, eventos do esquadrão).
- **Módulos Operacionais (Inspeções / To-Do)**: Detêm os prazos de inspeções (DPE) e tarefas.

## 3. Tipos de Visualização (Views)
A interface deverá ser dinâmica e suportar alternância rápida entre diferentes escalas de tempo:
*   **Visão Diária**: Altamente tática. Mostra detalhadamente a alocação de horas, quem está no turno, voos do dia, consultas curtas.
*   **Visão Semanal**: Foco na escala de serviço, planejamento de tarefas para a semana e acompanhamento de dispensas curtas.
*   **Visão Mensal**: Foco estratégico. Identificação rápida de dias de baixo efetivo, feriados e DPEs (Datas Previstas de Encerramento) de grandes inspeções.
*   **Visão Anual**: Macroplanejamento. Útil para o "Mapa de Férias" de todo o esquadrão, grandes paradas de frota e distribuição de missões longas.

## 4. Integração do Ecossistema
A força do módulo de calendário será sua capacidade de agregar:

| Módulo/Origem | Dados Injetados no Calendário | Ações Interativas a partir do Calendário |
| :--- | :--- | :--- |
| **Efetivo / Indisponibilidades** | Férias, Serviços, Consultas, Dispensas, Missões, Voos, Comissões. | Clicar num dia -> Criar Indisponibilidade. Sistema valida choque de escalas. |
| **Inspeções / Manutenção** | Início de Pacotes, Data Prevista de Encerramento (DPE), Voos de Teste. | Clicar para ver detalhes da inspeção; alerta visual se DPE cair em feriado. |
| **Eventos Administrativos** | Feriados, Formaturas, Paradas Gerais, Reuniões. | Adicionar evento genérico arrastando no calendário. |
| **Pedidos / To-Do List** | Prazos de tarefas pontuais ou deadlines operacionais. | Arrastar tarefa para reagendar prazo final. |

## 5. Permissões e Lançamentos (RBAC)
O sistema utiliza as roles existentes para determinar o nível de acesso e visibilidade. A regra de ouro é: **o backend nunca envia detalhes de eventos particulares para quem não tem permissão.**

| Papel (Role) | Visualização | Ações Permitidas |
| :--- | :--- | :--- |
| **Mantenedor** | Vê tudo que é público. Vê seus próprios privados. Privados de terceiros aparecem como "🔒 Particular". | Cria e edita suas próprias indisponibilidades. |
| **Encarregado** | Visão integral de todos os eventos (sem censura). | Cria e edita indisponibilidades para qualquer militar sob sua gestão. |
| **Inspetor** | Vê tudo que é público. Vê seus próprios privados. Privados de terceiros aparecem como "🔒 Particular". | Cria e edita suas próprias indisponibilidades. |
| **Administrador** | Visão integral e sem restrições. | Controle total: cria, edita e **exclui** qualquer evento. |

### Conceitos de Visibilidade
*   **Evento Público**: (Férias, Serviço, Escala) - Visível para todos.
*   **Evento Particular**: (Consulta Médica, Dispensa) - Motivo real oculto para usuários sem permissão gerencial.
*   **Trigramas**: Todo evento deve exibir o **trigrama** do militar (ex: `[ JSM ]`) para rápida identificação.

## 6. Proposta Arquitetural
Para manter a independência e alto desempenho:

1.  **Backend Agregador (Segurança em Primeiro Lugar)**: 
    *   Endpoint: `GET /api/v1/calendario/eventos`.
    *   O serviço consolida dados de múltiplos módulos e aplica a **regra de censura** antes de enviar o JSON. 
    *   Se o usuário não for Encarregado ou Admin, o `title` de eventos privados de terceiros é alterado para "Particular".
2.  **Frontend Reativo**:
    *   Biblioteca visual (FullCalendar/TUI) renderiza os blocos.
    *   Uso de cores e ícones (🌴, 🏥, 🔒) para distinguir tipos de indisponibilidade.
3.  **Interface de Lançamento Única**:
    *   O usuário clica no calendário e um seletor dinâmico abre o formulário correto do módulo de origem (Indisponibilidades ou Eventos), mantendo a integridade dos dados de cada domínio.

## 7. Próximos Passos (Roadmap)
1.  **Data Schema**: Implementar as tabelas `event_types` e `calendar_events` conforme definido no arquivo de ideias.
2.  **Service de Agregação**: Criar a lógica que busca dados de outros módulos e aplica as permissões de visibilidade.
3.  **UI Base**: Renderizar o calendário com dados mofados (mock) incluindo os trigramas.
4.  **Integração de Modais**: Conectar o clique no calendário aos formulários de lançamento.
