# Plano de Implementação: Card de Calendário no Dashboard

Este plano detalha as etapas para a adição de um módulo de calendário diretamente na página do dashboard central. O objetivo é fornecer uma visão rápida e integrada dos eventos e inspeções, utilizando um layout que harmonize com o estilo atual do dashboard, garantindo navegação semanal e sem alterar a lógica de funcionamento dos sistemas adjacentes.

## Premissas e Restrições
- **Isolamento Lógico:** O backend já possui as rotas necessárias em `/api/calendario`. Nenhuma alteração no backend deverá ser necessária.
- **Harmonia Visual:** Utilizar as classes CSS existentes (`glass-panel`, `dashboard-card`, `card-header`) para manter a coerência da UI.
- **Visualização Mista (Mensal/Semanal):** O layout deve ter aparência de uma grade mensal (dias em blocos), porém focado na visualização de blocos menores (ex: exibir 1 ou 2 semanas) e possuir controles para navegação (setas para semana anterior e próxima).

## Etapa 1: Adaptação Estrutural (HTML)
**Arquivo afetado:** `app/web/templates/dashboard.html`

1. **Localização do Novo Card:**
   - Adicionar o novo card na grade inferior (`.dashboard-bottom-grid`).
   - Ajustar o CSS para que essa grade comporte 3 colunas (passando para `grid-template-columns: repeat(3, 1fr)`) **ou** adicionar o calendário em uma nova linha (ex: `.dashboard-mid-grid` ocupando a largura total ou dividida com outro elemento). Recomenda-se adicionar o card na seção `.dashboard-bottom-grid` e adequar a responsividade.
2. **Estrutura do Card do Calendário:**
   - Criar uma `div` com as classes `glass-panel dashboard-card card-calendario`.
   - No `card-header`, incluir o ícone (ex: 📅), o título "Calendário" e os botões de navegação (`<` e `>`) acoplados a um rótulo do mês/semana exibido.
   - No `card-body`, inserir o contêiner vazio `<div id="mini-calendar-grid"></div>` onde a grade de dias será renderizada via JavaScript.

## Etapa 2: Estilização do Calendário (CSS)
**Arquivo afetado:** `app/web/templates/dashboard.html` (Bloco `<style>`) ou arquivo de folha de estilos correspondente.

1. **Classes do Mini Calendário:**
   - Criar classe `.calendar-grid` utilizando `display: grid` com 7 colunas (para os dias da semana).
   - Estilizar cabeçalhos dos dias da semana (Dom, Seg, Ter...).
   - Criar classes para os dias (`.calendar-day`), diferenciando o dia atual (`.day-today`) e dias fora do mês/semana em foco (`.day-muted`).
2. **Indicadores de Eventos:**
   - Criar marcações mínimas (pontos coloridos ou *badges* compactos) para indicar os eventos dentro dos blocos dos dias sem sobrecarregar o espaço disponível no card (`.event-indicator`).

## Etapa 3: Lógica e Integração de Dados (JavaScript)
**Arquivo afetado:** `static/js/dashboard.js`

1. **Gerenciamento de Estado:**
   - Adicionar variáveis de estado para rastrear a data base da visualização atual (`currentViewDate`).
2. **Funções de Renderização e Navegação:**
   - Criar a função `renderCalendarView(baseDate)` que calcula os dias da semana a serem exibidos.
   - Criar ouvintes de eventos (*event listeners*) para os botões de "Próxima Semana" e "Semana Anterior", que irão somar ou subtrair 7 dias de `currentViewDate` e chamar a re-renderização.
3. **Consumo de API:**
   - Criar função assíncrona `fetchCalendarEvents(startDate, endDate)`.
   - Chamar o endpoint já existente: `GET /api/calendario/eventos?start_date=...&end_date=...`.
   - Popular a grade do calendário, mapeando a lista de eventos retornada para os seus respectivos dias na interface.
4. **Tratamento de Carregamento (Loading):**
   - Utilizar as classes de *skeleton loading* existentes (ex: `.skeleton`) para exibir um estado de carregamento enquanto a API retorna os eventos do período selecionado.

## Resumo das Modificações Previstas
- **HTML:** Inclusão de um novo bloco `div.dashboard-card` no `dashboard.html`.
- **CSS:** Inclusão de estilos para `.calendar-grid` e `.calendar-day`.
- **JS:** Atualização do `dashboard.js` para buscar os dados via `fetch` à rota `/api/calendario/eventos` e manipular a renderização DOM da grade do calendário de forma dinâmica.
- **Nenhum arquivo de backend (`router.py`, `service.py`, `schemas.py`) sofrerá alterações.**
