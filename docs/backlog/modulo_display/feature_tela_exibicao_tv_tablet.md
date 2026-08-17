# Especificação de Funcionalidade: Tela de Exibição Operacional (Dashboard TV & Tablet)

> **Status:** Proposto / Backlog — revisado contra o código em 2026-08-16  
> **Módulo:** Dashboard / Visualização Operacional Central  
> **Público-Alvo:** Equipe de Manutenção, Inspetores, Mecânicos e Encarregados de Linha de Voo / Hangar; e uma nova função `DISPLAY` para o próprio dispositivo (ver §4.3)  
> **Dispositivos Alvo:** TV Full HD (1920x1080) e Tablets (Paisagem / Retrato)  
> **Plano de Implementação:** [feature_tela_exibicao_tv_tablet_plan.md](feature_tela_exibicao_tv_tablet_plan.md)

---

## 1. Visão Geral e Contexto Operacional

O objetivo desta funcionalidade é fornecer uma interface dedicada e otimizada para **exibição passiva contínua em TVs de oficina/hangar** e **consulta tática em tablets** utilizados na linha de manutenção do A-29 Super Tucano.

A tela deve consolidar o panorama operacional da frota em tempo real, permitindo rápida tomada de decisão sem exigir recarregamento manual da página nem navegação complexa.

> [!NOTE]
> **Escopo de Dispositivos:** O layout para smartphones está expressamente **fora do escopo** desta entrega e será tratado em fase posterior caso necessário.

---

## 2. Requisitos de Interface e Experiência do Usuário (UI/UX)

1. **Modo TV (Resolução Principal 1920x1080 - Full HD):**
   - Otimizado para ocupar 100% da área útil do viewport (`100dvh` sem barra de rolagem global na janela — `dvh` em vez de `vh` para não ser cortado pela chrome do navegador/player usado na TV).
   - Tipografia ampliada e alto contraste para garantir legibilidade à distância (mínimo de 3 a 5 metros).
   - Mecanismo de *auto-scroll* suave e contínuo para listas/tabelas que ultrapassem a altura do card.
2. **Modo Tablet (Resolução Secundária):**
   - Layout responsivo fluido adaptado para orientação horizontal (paisagem) e vertical (retrato).
   - Componentes interativos com áreas de toque adequadas (*touch-friendly*, mínimo de 56x56px — mesmo padrão já usado em `mobile.css` via `--mobile-touch-target`, superior ao mínimo de 44x44px do WCAG).
3. **Identidade Visual e Tema:**
   - Aderência ao Design System existente do SAA29 (`index.css`), utilizando as variáveis de cores semânticas já disponíveis (`--status-ok`, `--status-warning`, `--status-danger`, `--status-prorrogado`, `--status-incompleta`, `--primary-color`) e superfícies translúcidas em glassmorphism (`.glass-panel`).
   - **Atenção:** o tema Dark **não é o padrão do sistema** — `base.html` carrega `data-theme="light"` e o dark é um opt-in alternável pelo usuário (`app.js`). Como a tela precisa permanecer sempre escura para leitura à distância, a página deve forçar `data-theme="dark"` na raiz do próprio documento, independente da preferência salva de quem logou o dispositivo.
4. **Atualização em Tempo Real (Auto-Refresh):**
   - Atualização automática dos dados a cada intervalo configurável (padrão: 30 a 60 segundos) sem piscar ou recarregar a tela inteira. O dashboard atual (`dashboard.js`) atualiza a cada 5 minutos com `innerHTML` completo a cada ciclo — este requisito é funcionalidade nova, não um ajuste de intervalo.
   - Indicador visual discreto do status de conexão e timestamp da última sincronização bem-sucedida.

---

## 3. Módulos e Componentes da Tela

```
+----------------------------------------------------------------------------------------------------+
|  [LOGO SAA29]  PAINEL OPERACIONAL DE MANUTENÇÃO (A-29)     16 AGO 2026  |  16:30:52 L  19:30:52 Z  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ 1. DISPONIBILIDADE DA FROTA ]                                                                   |
|  🟢 DISPONÍVEIS: 08    🟡 INSPEÇÃO: 03    🔴 INDISPONÍVEIS: 02    ⚪ ESTOCADAS: 01                  |
|                                                                                                    |
+--------------------------------------------------+-------------------------------------------------+
|  [ 2. PANES ABERTAS ] (Auto-Scroll)              |  [ 3. AERONAVES EM INSPEÇÃO ]                   |
|  ANV   | SISTEMA ATA     | DESCRIÇÃO DA PANE     |  ANV   | TIPO(S)       | FASE / PROGRESSO        |
|  5916  | 34 - Aviônica   | Falha no MFD esquerdo |  5902  | IF-100H       | Em Andamento (75%)      |
|  5922  | 72 - Motor      | Indicação de óleo     |  5918  | IPG           | Aberta (20%)            |
|                                                  |                                                 |
+--------------------------------------------------+-------------------------------------------------+
|  [ 4. ALERTAS DE VENCIMENTOS E VALIDADES ] (Filtro: [15d] [1 Mês (TV)] [3m] [6m])                  |
|  COMPONENTE / ITEM               | MATRÍCULA / LOCALIZAÇÃO       | VENCIMENTO     | STATUS         |
|  Cartucho Assento Ejetável (L1)  | A-29 (FAB 5916)               | 28/08/2026     | 🔴 VENCIDO     |
|  Transponder E-01                | Estoque Sala Rádio            | 05/09/2026     | 🟡 VENCENDO    |
+----------------------------------------------------------------------------------------------------+
```

### 3.1. Cabeçalho Operacional (Relógio Duplo & Indicadores)
- **Hora Local (L):** Horário corrente da base no formato `HH:MM:SS L` (ex: `16:30:52 L`).
- **Hora Zulu (Z):** Horário universal coordenado da aviação militar no formato `HH:MM:SS Z` (ex: `19:30:52 Z`).
- **Data Operacional:** Formato padrão aeronáutico (ex: `16 AGO 2026`).
- **Status do Feed:** Ponto luminoso (🟢/🔴) indicando saúde da comunicação com o backend e tempo decorrido desde a última atualização.

### 3.2. Resumo de Disponibilidade da Frota (A-29)
Indicadores visuais de alto nível sumarizando o status da frota. O sistema já expõe seis status reais
(`DISPONIVEL`, `OPERACIONAL`, `INDISPONIVEL`, `INSPEÇÃO`, `ESTOCADA`, `INATIVA` — `StatusAeronave`), calculados
dinamicamente e não lidos direto da coluna: uma aeronave com inspeção ativa aparece como `INSPEÇÃO` mesmo que
seu status de cadastro seja outro, e uma com pane aberta aparece como `INDISPONIVEL` (salvo se já estiver em
inspeção/estocada/inativa). O painel deve agrupar essas seis categorias nos quatro indicadores visuais abaixo:
- 🟢 **Disponíveis / Operacionais:** soma de `DISPONIVEL` + `OPERACIONAL`.
- 🟡 **Em Inspeção:** aeronaves com o status derivado `INSPEÇÃO` (nota: o valor leva o acento — comparações de
  string precisam usar o literal exato).
- 🔴 **Indisponíveis:** aeronaves com o status derivado `INDISPONIVEL` (retidas por pane aberta ou por outro
  motivo cadastral). Não existe um status "EM PANE" separado no sistema.
- ⚪ **Estocadas / Inativas:** soma de `ESTOCADA` + `INATIVA`.

### 3.3. Painel de Panes Abertas
Tabela detalhada de discrepâncias e panes ativas:
- **Campos Obrigatórios:**
  - `ANV`: Matrícula da Aeronave (ex: `5916`).
  - `Sistema`: Sistema ATA afetado, no formato `código - descrição` (ex: `24 - Elétrico`, `34 - Aviônica`). O
    vínculo com o sistema ATA é opcional no cadastro da pane — quando ausente, exibir a descrição da pane
    truncada como já faz o card de resumo atual, em vez de deixar a coluna vazia.
  - `Descrição da Pane`: Resumo da avaria reportada.
  - `Data / Tempo Aberta`: Tempo decorrido desde a abertura.
- **Comportamento em TV:** Rolagem automática suave (*smooth auto-scroll*) com pausa momentânea ao atingir o topo/base.

### 3.4. Destaque: Aeronaves em Inspeção
Quadrante dedicado ao acompanhamento de inspeções ativas:
- **Campos:**
  - `ANV`: Matrícula da aeronave.
  - `Tipo de Inspeção`: Código(s) do tipo aplicado (ex: `IF-50H`, `IF-100H`, `IPG`, `IPE`).
  - `Status / Fase`: Status operacional (`ABERTA` ou `EM_ANDAMENTO` — não existe fase intermediária como
    "Aguardando Peças") e percentual de tarefas concluídas (ex: `EM_ANDAMENTO - 85%`).
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
- **Importante — status sempre calculado, nunca lido direto do banco:** a coluna `status` de
  `ControleVencimento` grava apenas o valor do momento da última execução e **não é recalculada pela simples
  passagem do tempo**. Todo ponto de leitura deve derivar o status exibido a partir da data de vencimento
  (`VENCIDO` se já passou; `VENCENDO` se faltam até 30 dias; `OK` caso contrário) e da prorrogação ativa mais
  recente (se houver uma e a nova data ainda não passou, o status vira `PRORROGADO`). O endpoint atual de
  resumo do dashboard ainda comete esse erro — corrigir junto com esta entrega (ver plano de implementação).

---

## 4. Arquitetura Técnica e Backend

### 4.1. Endpoints da API (FastAPI)

O dashboard existente vive sob o prefixo **`/dashboard`**, sem versionamento `/api/v1/` (esse padrão é
exceção reservada aos módulos `calendario` e `encarregado`). O endpoint atual, `GET /dashboard/resumo`, é
consumido pelo dashboard web comum e já tem testes e contrato fechados — em vez de ampliá-lo, esta
funcionalidade adiciona um endpoint próprio, para não arriscar quebrar o consumidor existente:

1. **`GET /dashboard/painel` (Novo Endpoint):**
   - Retorna todas as panes abertas (sem o limite de 5 registros do resumo atual), com descrição completa e
     sistema ATA no formato `código - descrição`.
   - Retorna todas as inspeções ativas com o percentual de tarefas concluídas por inspeção (calculado em lote,
     sem consulta por aeronave, para não gerar N+1 queries).
   - Retorna a lista de vencimentos dentro do horizonte selecionado, com status sempre derivado (nunca a
     coluna persistida — ver §3.5).
   - **Parâmetros de Consulta (Query Params):**
     - `dias`: Inteiro (`15`, `30`, `90`, `180` — padrão `30`), usado para filtrar a lista de vencimentos.
   - Resolve o vínculo de cada controle de vencimento com a tabela `instalacoes` (instalação ativa =
     `data_remocao IS NULL`) para identificar a matrícula da aeronave, ou marca "Em Estoque" quando não há
     instalação ativa.

### 4.2. Estratégia de Frontend (HTML5 / Vanilla JS / CSS)

- **Página dedicada:** `/tv`, com template e JS próprios (`tv.html` / `tv.js`), fora do layout padrão do
  sistema (sem o cabeçalho/menu de navegação de `base.html`) — o mesmo padrão já usado por `mobile/base_mobile.html`
  para uma superfície de tela cheia dedicada.
- **Relógio Client-Side:**
  - Implementado em JavaScript puro com `setInterval` de 1000ms.
  - Utiliza `Date.toISOString()` / `Date.getUTCHours()` para o relógio Zulu e `Intl.DateTimeFormat` para o relógio Local, sem sobrecarregar a API com chamadas de horário.
- **Auto-Refresh Assíncrono:**
  - Polling assíncrono via `fetch()` a cada 30 segundos, atualizando o DOM apenas onde houver alterações (sem *page flicker*).
- **Controle de Auto-Scroll:**
  - Algoritmo de rolagem automática em containers com `overflow-y: hidden`, controlando `scrollTop` a uma taxa constante de pixels por frame via `requestAnimationFrame`.
- **Restrição de CSP:** a política de segurança do sistema (`script-src 'self'`) proíbe `<script>` inline e
  atributos `onclick` — toda a lógica precisa viver em `/static/js/tv.js`, com handlers registrados via
  `addEventListener`, seguindo o padrão já usado nas demais páginas do sistema.

### 4.3. Sessão e Controle de Acesso (RBAC & Persistência)

A TV do hangar fica ligada continuamente, mas o token de acesso (JWT) do sistema expira em **15 minutos**, e
qualquer resposta `401` da API hoje encerra a sessão no cliente (`clearAuth()`). Sem tratamento dedicado, a
tela pararia de atualizar a cada 15 minutos.

- **Nova função de usuário `DISPLAY`:** perfil de permissão mínima, criado especificamente para autenticar o
  dispositivo/TV. Só pode acessar `GET /dashboard/painel`, a própria página `/tv`, e as rotas básicas de
  sessão (`/auth/me`, `/auth/logout`, `/auth/refresh`) — nenhuma rota de escrita ou de outros módulos
  (panes, inspeções, equipamentos, configurações etc.).
  - **Trava de segurança:** por padrão, hoje qualquer usuário autenticado (`CurrentUser`) tem acesso de leitura
    a praticamente todos os módulos do sistema. A introdução da função `DISPLAY` exige que o backend passe a
    negar por padrão para esse perfil, liberando apenas as rotas explicitamente permitidas — em vez de herdar
    o acesso amplo que as demais funções têm hoje.
- **Persistência de sessão (silent refresh):** a página `/tv` deve chamar `POST /auth/refresh`
  periodicamente (antes dos 15 minutos de validade do access token). Como o refresh token roda em rotação a
  cada chamada, a sessão da TV se renova indefinidamente sem exigir novo login, respeitando a janela de 7 dias
  do refresh token a cada ciclo.
- **Falha de rede não deve derrubar a sessão:** uma falha transitória de conectividade não pode ser tratada
  como sessão expirada — a tela deve exibir o indicador de "sem conexão" (já previsto em §2.4) e tentar
  novamente, sem redirecionar para o login.
- **Proteção CSRF:** aplicável apenas se a página `/tv` chegar a expor alguma ação de escrita (não previsto
  nesta especificação — a tela é somente leitura).

---

## 5. Critérios de Aceite

- [ ] A tela abre em resolução Full HD (1920x1080) preenchendo toda a área útil sem barras de rolagem globais indesejadas.
- [ ] O cabeçalho exibe a Hora Local (`L`) e a Hora Zulu (`Z`) com atualização precisa a cada segundo.
- [ ] O resumo de disponibilidade da frota reflete os seis status reais calculados pelo motor de regras do SAA29 (`DISPONIVEL`, `OPERACIONAL`, `INDISPONIVEL`, `INSPEÇÃO`, `ESTOCADA`, `INATIVA`), agrupados nos quatro indicadores visuais.
- [ ] A lista de panes abertas exibe todas as ocorrências ativas (sem limite de 5) com rolagem suave contínua na TV.
- [ ] O painel de inspeções apresenta as aeronaves em manutenção com seus respectivos tipos e progresso percentual, sem gerar consultas N+1 no backend.
- [ ] O painel de vencimentos lista os itens com prazo de até 1 mês por padrão, com status sempre derivado da data de vencimento (nunca da coluna persistida), e permite alternar os filtros de 15 dias, 3 meses e 6 meses no tablet.
- [ ] A interface força o tema Dark independentemente da preferência salva do usuário logado, mantendo alto contraste.
- [ ] Um usuário com a função `DISPLAY` consegue acessar `/tv` e `GET /dashboard/painel`, e recebe `403` em qualquer outra rota do sistema.
- [ ] A sessão da TV permanece ativa indefinidamente (renovação automática via `/auth/refresh`), sem exigir novo login após os 15 minutos de validade do access token.
- [ ] Uma falha temporária de rede exibe o indicador de "sem conexão" e se recupera sozinha, sem derrubar a sessão nem exigir recarregar a página.
