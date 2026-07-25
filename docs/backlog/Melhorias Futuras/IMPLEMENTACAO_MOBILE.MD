# Implementação de Interface Mobile Simplificada (SAA29) — Modo Linha de Voo (Zero Fricção)

Este documento detalha as especificações técnicas e de experiência do usuário (UX) para a versão mobile do SAA29 (`/m/`), projetada especificamente para **operação ultra-rápida na linha de voo e no hangar**.

---

## 🎯 1. Objetivo Operacional

Proporcionar ao mantenedor e inspetor na linha de voo uma ferramenta de **máxima praticidade e zero atrito**, onde qualquer lançamento (pane, tarefa de checklist ou visto) possa ser realizado em **menos de 5 segundos**, sem necessidade de navegar por múltiplos menus, preencher campos burocráticos ou confirmar diálogos redundantes sob sol ou usando luvas.

---

## ⚡ 2. Princípios Norteadores: "Fricção Zero na Linha de Voo"

1. **Ação em 1 Toque (Tap-to-Action):** Da tela inicial até a conclusão de uma ação, no máximo 2 toques.
2. **Entrada "Foto & Voz Primeiro":** Eliminar digitação no teclado virtual. O mecânico tira a foto da pane ou dita o texto por áudio (Web Speech API).
3. **Presets & Chips Rápidos:** Botões de 1 clique com as panes mais comuns da rotina ("Vazamento de Óleo", "Pneu Desgastado", "Falha rádio VUHF1", "Falha MDP").
4. **Sem Modais de Confirmação Redundantes:** Lançou/Vistou = Salvo instantaneamente no banco de dados. Exibe Toast com botão "Desfazer" (Undo) de 3 segundos para eventuais enganos.
5. **Autenticação Rápida por PIN de 4 dígitos / Biometria (FaceID/Fingerprint):** Sem necessidade de digitar usuário e senha longa a cada acesso na pista.
6. **Interface Adaptável a Sol Radiante (Modo Alta Legibilidade):** Botões com alvos de toque amplos (mínimo `56px`), contraste extremo e feedback tátil (Vibration API do celular).

---

## 📱 3. Arquitetura da Solução Mobile (`/m/`)

- **Rotas Dedicadas:** Prefixadas em `/m/` (ex: `/m/`, `/m/panes`, `/m/inspecoes`, `/m/frota`).
- **PWA Instalável:** Suporte a *Progressive Web App* com manifesto e Service Worker para ícone direto na tela inicial do smartphone.
- **Modo Offline-First Temporário:** Registro de panes e checklists em `IndexedDB`/`localStorage` caso o sinal de Wi-Fi/4G oscile no hangar, sincronizando automaticamente assim que a conexão retornar.

---

## 🚀 4. Detalhamento dos Módulos Operacionais

### A. Dashboard de Frota Cockpit (`/m/`)
- **Tela Única (Single Screen):** Ao abrir o app mobile, a primeira tela exibe os *Cards das Aeronaves* agrupados pelo status (Prontas para Voo / Em Inspeção / Indisponíveis).
- **Bottom-Sheet ao Clicar na Aeronave:** Um clique no card da ANV (ex: `FAB 5701`) abre uma folha inferior instantânea com 3 grandes botões:
  1. 🔴 **Lançar Pane Rápida**
  2. 📋 **Continuar Checklist**
  3. 👁️ **Ver Health Summary (Panes Ativas & Vencimentos)**

### B. Relato Rápido de Panes ("Lançamento em 3 Segundos")
- **Pré-preenchimento Automático:** Aeronave pré-selecionada pelo card acionado; Autor definido pelo militar logado.
- **Interface de Entrada:**
  - 📷 **Botão Câmera Gigante:** Tira a foto da pane que é anexada imediatamente.
  - 🎙️ **Botão Ditado por Voz:** Transcreve a fala do mecânico para o campo de sintoma.
  - 🏷️ **Chips de Panes Recorrentes:** Seleção com 1 toque dos sintomas frequentes.
- **Botão "Salvar e Notificar":** Um toque envia o registro.

### C. Checklist de Inspeção "Passa-Passa" (Swipe & Tap)
- **Modo Execução Rápida:** Visualização de 1 item de checklist por vez em tela cheia com letras grandes.
- **Ações Rápidas:**
  - 🟢 **[ VISTO / OK ]** (Verde, 60px): Marca o item como concluído e avança automaticamente para o próximo item em 0,3s.
  - 🔴 **[ RELATAR PANE ]** (Vermelho): Abre a câmera para anexar pane diretamente vinculada ao item do checklist.
  - 🟡 **[ PNE / PENDENTE ]**: Marca o item para revisão sem travar o fluxo.

### D. Consulta de Vencimentos & Inventário por QR Code / Slot
- **Validação de Slot Físico:** Leitura de QR Code colado no painel/compartimento para exibir instantaneamente a peça que deveria estar instalada e seu vencimento.

---

## 🛠️ 5. Cronograma de Implementação Simplificado

| Fase | Funcionalidade | Foco |
| :--- | :--- | :--- |
| **Fase 1** | Shell Mobile `/m/`, PWA, Autenticação por PIN e Dashboard Cockpit | Acesso rápido em 1 toque |
| **Fase 2** | Relato Rápido de Panes (Câmera + Ditado por Voz + Chips) | Registro de pista < 5 seg |
| **Fase 3** | Checklist Digital "Passa-Passa" com Avanço Automático | Substituição de papel no hangar |
| **Fase 4** | Cache Offline (IndexedDB) e Sincronização Automática | Operação em áreas sem Wi-Fi |
