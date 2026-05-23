# Implementação de Interface Mobile Simplificada (SAA29)

Este documento detalha as sugestões e especificações conceituais para a criação de uma versão mobile otimizada do SAA29, focada em uso rápido na linha de voo e hangar.

## 1. Objetivo
Proporcionar aos mantenedores e inspetores uma ferramenta ágil para coleta de dados e consulta imediata de status de aeronaves, otimizando o fluxo de trabalho onde o uso de computadores desktop é inviável.

## 2. Abordagem Arquitetural (Aprovação: [ ])
- **Tipo:** [ ] Interface Mobile Dedicada (Opção "Additive").
- **Rotas:** [ ] Implementação sob o prefixo `/m/` (ex: `/m/panes`, `/m/dashboard`).
- **Tecnologia:** [ ] Reaproveitamento integral das APIs existentes no Backend, com novos templates Jinja2 e CSS focados em dispositivos móveis.
- **PWA:** [ ] Configuração para permitir a instalação como "Web App" na tela inicial do smartphone.

## 3. Funcionalidades Sugeridas por Módulo

### A. Gestão de Panes (Relatos de Campo)
*   [ ] **Relato Rápido:** Interface simplificada para abertura de panes com campos essenciais (Aeronave, Código ATA, Sintoma).
*   [ ] **Captura de Evidência:** Uso direto da câmera do celular para anexar fotos de danos ou vazamentos instantaneamente ao relato.
*   [ ] **Assinatura de Execução:** Botão de "Concluir" com confirmação por PIN ou biometria para encerramento de tarefas de manutenção ao lado da aeronave.

### B. Status de Frota (Linha de Voo)
*   [ ] **Visão em Cards:** Visualização otimizada da frota com indicadores de cor (Verde/Amarelo/Vermelho) para disponibilidade imediata.
*   [ ] **Filtro por Localização:** Verificação rápida de quais aeronaves estão em inspeção ou estocadas.

### C. Inspeções e Checklists
*   [ ] **Checklist Digital:** Substituição das fichas de papel por checklists digitais onde o mecânico tica os itens à medida que os executa.
*   [ ] **Consultas de Padrão:** Visualização rápida de fotos e diagramas de referência para auxiliar na identificação de conformidades.

### D. Equipamentos e Inventário
*   [ ] **Validação de Slot:** Interface para confirmar se o Serial Number (SN) do equipamento instalado no slot físico condiz com o registro no sistema.
*   [ ] **Leitor de Etiquetas (Futuro):** Uso da câmera para leitura de QR Codes ou Códigos de Barras de componentes.

### E. Utilidades
*   [ ] **Guia de Ramais Dinâmico:** Lista rápida de contatos internos (Pessoas e Seções) consumida direto do banco de dados com função "Clique para Ligar".
*   [ ] **Escala de Serviço:** Consulta rápida da escala diária de funções e sobreavisos.

## 4. Princípios de UI/UX Mobile
*   [ ] **Bottom Navigation:** Barra de navegação inferior para fácil acesso com o polegar.
*   [ ] **Touch Targets:** Botões grandes para evitar cliques acidentais.
*   [ ] **Dark Mode Nativo:** Focado em economia de bateria e legibilidade.
*   [ ] **Offline First (Sincronização):** Cache básico para lidar com oscilações de sinal no hangar.

## 5. Estratégia de Implementação
1.  **Fase 1:** Template Base Mobile e Login Mobile.
2.  **Fase 2:** Módulo de Relato de Panes com Fotos.
3.  **Fase 3:** Visão de Status de Frota.
4.  **Fase 4:** Checklist de Inspeções.
