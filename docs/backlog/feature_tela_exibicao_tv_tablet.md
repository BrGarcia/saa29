# Especificação de Funcionalidade: Tela de Exibição Operacional (Dashboard TV & Tablet)

> **Status:** Proposto / Backlog  
> **Módulo:** Dashboard / Visualização Operacional Central  
> **Público-Alvo:** Equipe de Manutenção, Inspetores, Mecânicos e Encarregados de Linha de Voo / Hangar  
> **Dispositivos Alvo:** TV Full HD (1920x1080) e Tablets (Paisagem / Retrato)  

---

## 1. Visão Geral e Contexto Operacional

O objetivo desta funcionalidade é fornecer uma interface dedicada e otimizada para **exibição passiva contínua em TVs de oficina/hangar** e **consulta tática em tablets** utilizados na linha de manutenção do A-29 Super Tucano.

A tela deve consolidar o panorama operacional da frota em tempo real, permitindo rápida tomada de decisão sem exigir recarregamento manual da página nem navegação complexa.

> [!NOTE]
> **Escopo de Dispositivos:** O layout para smartphones está expressamente **fora do escopo** desta entrega e será tratado em fase posterior caso necessário.

---

## 2. Requisitos de Interface e Experiência do Usuário (UI/UX)

1. **Modo TV (Resolução Principal 1920x1080 - Full HD):**
   - Otimizado para ocupar 100% da área útil do viewport (`100vh` sem barra de rolagem global na janela).
   - Tipografia ampliada e alto contraste para garantir legibilidade à distância (mínimo de 3 a 5 metros).
   - Mecanismo de *auto-scroll* suave e contínuo para listas/tabelas que ultrapassem a altura do card.
2. **Modo Tablet (Resolução Secundária):**
   - Layout responsivo fluido adaptado para orientação horizontal (paisagem) e vertical (retrato).
   - Componentes interativos com áreas de toque adequadas (*touch-friendly*, mínimo de 44x44px).
3. **Identidade Visual e Tema:**
   - Aderência estrita ao Design System Dark Mode existente do SAA29 (`index.css`), utilizando as variáveis de cores semânticas (`--status-ok`, `--status-warning`, `--status-danger`, `--primary-color`) e superfícies translúcidas em glassmorphism.
4. **Atualização em Tempo Real (Auto-Refresh):**
   - Atualização automática dos dados a cada intervalo configurável (padrão: 30 a 60 segundos) sem piscar ou recarregar a tela inteira.
   - Indicador visual discreto do status de conexão e timestamp da última sincronização bem-sucedida.

---

## 3. Módulos e Componentes da Tela

```
+----------------------------------------------------------------------------------------------------+
|  [LOGO SAA29]  PAINEL OPERACIONAL DE MANUTENÇÃO (A-29)     16 AGO 2026  |  16:30:52 L  19:30:52 Z  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ 1. DISPONIBILIDADE DA FROTA ]                                                                   |
|  🟢 DISPONÍVEIS: 08    🟡 INSPEÇÃO: 03    🔴 EM PANE: 02    ⚪ ESTOCADAS: 01                       |
|                                                                                                    |
+--------------------------------------------------+-------------------------------------------------+
|  [ 2. PANES ABERTAS ] (Auto-Scroll)              |  [ 3. AERONAVES EM INSPEÇÃO ]                   |
|  ANV   | SISTEMA ATA     | DESCRIÇÃO DA PANE     |  ANV   | TIPO(S)       | FASE / PROGRESSO        |
|  5916  | 34 - Aviônica   | Falha no MFD esquerdo |  5902  | 300h + PS     | Em Andamento (75%)      |
|  5922  | 72 - Motor      | Indicação de óleo     |  5918  | Anual         | Aguardando Pçs (20%)    |
|                                                  |                                                 |
+--------------------------------------------------+-------------------------------------------------+
|  [ 4. ALERTAS DE VENCIMENTOS E VALIDADES ] (Filtro: [15d] [1 Mês (TV)] [3m] [6m])                  |
|  COMPONENTE / ITEM               | MATRÍCULA / LOCALIZAÇÃO       | VENCIMENTO     | STATUS         |
|  Cartucho Assento Ejetável (L1)  | A-29 (FAB 5916)               | 28/08/2026     | 🔴 VENCENDO    |
|  Transponder E-01                | Estoque Sala Rádio            | 05/09/2026     | 🟡 ATENÇÃO     |
+----------------------------------------------------------------------------------------------------+
```

### 3.1. Cabeçalho Operacional (Relógio Duplo & Indicadores)
- **Hora Local (L):** Horário corrente da base no formato `HH:MM:SS L` (ex: `16:30:52 L`).
- **Hora Zulu (Z):** Horário universal coordenado da aviação militar no formato `HH:MM:SS Z` (ex: `19:30:52 Z`).
- **Data Operacional:** Formato padrão aeronáutico (ex: `16 AGO 2026`).
- **Status do Feed:** Ponto luminoso (🟢/🔴) indicando saúde da comunicação com o backend e tempo decorrido desde a última atualização.

### 3.2. Resumo de Disponibilidade da Frota (A-29)
Indicadores visuais de alto nível sumarizando o status da frota:
- 🟢 **Disponíveis / Operacionais:** Quantidade de aeronaves liberadas para voo.
- 🟡 **Em Inspeção:** Aeronaves em manutenção preventiva programada.
- 🔴 **Em Pane / Indisponíveis:** Aeronaves retidas por manutenção corretiva.
- ⚪ **Estocadas / Inativas:** Aeronaves em preservação ou desativadas.

### 3.3. Painel de Panes Abertas
Tabela detalhada de discrepâncias e panes ativas:
- **Campos Obrigatórios:**
  - `ANV`: Matrícula da Aeronave (ex: `5916`).
  - `Sistema`: Sistema ATA afetado (ex: `24 - Elétrico`, `34 - Aviônica`).
  - `Descrição da Pane`: Resumo da avaria reportada.
  - `Data / Tempo Aberta`: Tempo decorrido desde a abertura.
- **Comportamento em TV:** Rolagem automática suave (*smooth auto-scroll*) com pausa momentânea ao atingir o topo/base.

### 3.4. Destaque: Aeronaves em Inspeção
Quadrante dedicado ao acompanhamento de inspeções ativas:
- **Campos:**
  - `ANV`: Matrícula da aeronave.
  - `Tipo de Inspeção`: Tipos combinados (ex: `50h`, `100h`, `PS`, `Anual`).
  - `Status / Fase`: Status operacional e percentual de tarefas concluídas (ex: `Em Andamento - 85%`).
  - `Previsão de Término`: Data estimada de conclusão.

### 3.5. Alertas de Vencimentos e Validades
Módulo de acompanhamento preditivo de componentes controlados por calendário:
- **Regra Padrão (TV):** Exibir automaticamente itens com vencimento nos próximos **30 dias (1 mês)** e itens já vencidos.
- **Interatividade (Tablet):** Botões seletores para alterar o horizonte temporal de previsão:
  - `15 Dias` | `1 Mês (Padrão)` | `3 Meses` | `6 Meses`.
- **Campos Obrigatórios:**
  - `Item / Componente`: Descrição e Part Number (PN).
  - `ANV / Localização`: Matrícula da aeronave onde está instalado ou indicação de "Em Estoque".
  - `Data de Vencimento`: Data limite para inspeção/substituição.
  - `Status`: Indicador de criticidade (`VENCIDO`, `VENCENDO`, `PRORROGADO`).

---

## 4. Arquitetura Técnica e Backend

### 4.1. Endpoints da API (FastAPI)

1. **`GET /api/v1/dashboard/resumo` (Ajuste no endpoint existente):**
   - Ampliar a consulta de panes para retornar todas as panes abertas com a descrição completa e sistema ATA (em vez de limitar apenas a 5 registros).
   - Incluir dados de progresso percentual nas inspeções ativas.

2. **`GET /api/v1/dashboard/vencimentos-proximos` (Novo Endpoint):**
   - **Parâmetros de Consulta (Query Params):**
     - `dias`: Inteiro (`15`, `30`, `90`, `180` - padrão `30`).
   - **Retorno:** Lista de controles de vencimento ordenados por data mais próxima, resolvendo o vínculo do item com a tabela `instalacoes` ativas para identificar a matrícula da aeronave.

### 4.2. Estratégia de Frontend (HTML5 / Vanilla JS / CSS)

- **Relógio Client-Side:**
  - Implementado em JavaScript puro com `setInterval` de 1000ms.
  - Utiliza `Date.toISOString()` / `Date.getUTCHours()` para o relógio Zulu e `Intl.DateTimeFormat` para o relógio Local, sem sobrecarregar a API com chamadas de horário.
- **Auto-Refresh Assíncrono:**
  - Polling assíncrono via `fetch()` a cada 30 segundos, atualizando o DOM apenas onde houver alterações (sem *page flicker*).
- **Controle de Auto-Scroll:**
  - Algoritmo de rolagem automática em containers com `overflow-y: hidden`, controlando `scrollTop` a uma taxa constante de pixels por frame via `requestAnimationFrame`.

---

## 5. Critérios de Aceite

- [ ] A tela abre em resolução Full HD (1920x1080) preenchendo toda a área útil sem barras de rolagem globais indesejadas.
- [ ] O cabeçalho exibe a Hora Local (`L`) e a Hora Zulu (`Z`) com atualização precisa a cada segundo.
- [ ] O resumo de disponibilidade da frota reflete os dados reais calculados pelo motor de regras do SAA29.
- [ ] A lista de panes abertas exibe todas as ocorrências ativas com rolagem suave contínua na TV.
- [ ] O painel de inspeções apresenta as aeronaves em manutenção com seus respectivos tipos e progresso.
- [ ] O painel de vencimentos lista os itens com prazo de até 1 mês por padrão e permite alternar os filtros de 15 dias, 3 meses e 6 meses no tablet.
- [ ] A interface mantém total harmonia visual com o tema Dark do sistema e alto contraste.
