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
O calendário deve ser "inteligente" para adaptar as permissões de quem o visualiza:

*   **Usuário Comum (Mantenedor / Inspetor)**:
    *   Consegue visualizar o calendário de sua equipe/especialidade.
    *   Pode clicar no próprio calendário para **solicitar ou lançar** suas próprias indisponibilidades pessoais (ex: marcar uma consulta médica).
*   **Encarregado (Chefe de Linha / Especialidade)**:
    *   Tem visão gerencial da sua área.
    *   Pode lançar escalas, serviços, missões e férias **para qualquer militar** sob sua gestão.
*   **Administrador / Seção de Pessoal**:
    *   Visão global da organização (Mapa de Férias Master).
    *   Permissão para lançar e aprovar qualquer tipo de evento ou definir feriados fixos.

## 6. Proposta Arquitetural
Para manter a independência e alto desempenho:

1.  **Backend Agregador**: 
    Haverá um endpoint principal (ex: `GET /api/v1/calendario/eventos?start=X&end=Y`). O serviço do calendário chamará as funções de listagem dos domínios (Efetivo, Inspeções, etc.) passando as datas. Ele normalizará todos os resultados num schema padrão unificado (ex: `{ id, title, start, end, type, backgroundColor }`).
2.  **Frontend Reativo**:
    Uma biblioteca de calendário robusta (como *FullCalendar* ou *TUI Calendar*) cuidará da renderização. Contará com painéis laterais de filtros (ex: ligar/desligar visualização de inspeções, mostrar apenas militares da especialidade 'BMB').
3.  **UI de Entrada**:
    Ao invés de formulários espalhados, o usuário clica num bloco de tempo. Um seletor pergunta o que ele quer lançar:
    `[ Férias ] [ Serviço ] [ Tarefa ] [ Evento ]`. 
    Conforme a seleção, a interface injeta dinamicamente o formulário do respectivo módulo, mantendo tudo coeso para o usuário final, mas separado a nível de código.

## 7. Próximos Passos (Roadmap de Implementação)
1.  Modelar a API de agregação (`calendario/service.py`) e testar a fusão de dados em memória.
2.  Prototipar o Frontend instalando a biblioteca visual e injetando dados falsos de teste.
3.  Criar os formulários independentes no módulo de Indisponibilidades (missão, férias, dispensa) para que possam ser consumidos via modais do Calendário.
