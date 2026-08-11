# Plano de Correção: Bug de Mapeamento de Inventário (Slots)

> **Bug ID:** BUG-INV-01  
> **Status:** Aguardando Autorização  
> **Relacionado a:** docs/backlog/bug_inventorio.md, docs/legacy/inventario.md

## 1. Análise de Causas Raiz

Após análise dos modelos (`app/modules/equipamentos/models.py`) e do script de carga inicial (`scripts/seed/seed_equipamentos.py`), identificamos as seguintes causas:

1.  **Colapso de Slots no Seed**: O script de seed utiliza o campo `posicao` como identificador único para criar registros na tabela `slots_inventario`. Como vários equipamentos compartilham o mesmo nome de posição no dicionário de sementes (ex: "CMFD", "MDP"), o sistema acaba criando apenas um slot para múltiplas posições físicas, resultando na perda de distinção entre CMFD1, CMFD2, etc.
2.  **Sobrecarga do campo 'Sistema'**: O campo `sistema` no modelo `SlotInventario` está sendo usado para armazenar a Localização (1P, 2P, CEI), mas a lógica de exibição no frontend não está preparada para separar "O que é o equipamento" de "Onde ele está".
3.  **Ausência de Identidade Própria para Slots**: Atualmente, o sistema trata o Slot quase como um atributo do Equipamento, quando na verdade o Slot é uma entidade da Aeronave que *recebe* um equipamento.
4.  **Inconsistência com a Documentação Legada**: Os dados no `seed_equipamentos.py` não refletem fielmente a tabela contida em `docs/legacy/inventario.md`.

## 2. Plano de Ação Proposto

O objetivo é transformar o inventário em um mapa fiel da aeronave, onde cada linha representa uma posição física (Slot) fixa.

### Fase 1: Ajustes de Dados (Seed)
- **Refatorar o Dicionário de Sementes**: Atualizar `scripts/seed/seed_equipamentos.py` para seguir rigorosamente a lista de `docs/legacy/inventario.md`.
    - Ex: Mudar `{"posicao": "CMFD", ...}` para `{"posicao": "CMFD1", "localizacao": "1P", "equipamento": "CMFD", ...}`.
- **Lógica de Criação**: Ajustar o loop de seed para garantir que cada Slot seja criado de forma única baseada na combinação `Localização + Nome da Posição`.

### Fase 2: Ajustes de Modelo e API
- **Modelagem**: Verificar se o campo `sistema` em `SlotInventario` é suficiente ou se devemos renomeá-lo explicitamente para `localizacao` via migration (ou apenas ajustar o uso semântico).
- **Service/Router**: Atualizar o serviço de inventário (`app/modules/equipamentos/service.py`) para incluir os campos de localização e nome do slot na resposta da API.

### Fase 3: Interface (Frontend)
- **Tabela de Inventário**: Atualizar `app/web/templates/inventario.html` e `app/web/static/js/inventario.js` para refletir as colunas exatas:
    - **Loc** (Localização: 1P, 2P, CEI, CES)
    - **Slot** (Posição: MDP1, CMFD1, etc.)
    - **P/N** (Part Number)
    - **S/N (SILOMS)** (Número de série registrado no sistema)
    - **Atualização/Trigrama** (Responsável pela última ação no slot)
    - **S/N (REAL)** (Campo para conferência/sincronismo)
    - **Anv Ant.** (Aeronave de origem/anterior do item)

## 3. Impactos e Riscos
- **Migração de Dados**: Como o banco local será resetado conforme o fluxo de desenvolvimento atual, não há risco de perda de dados críticos de produção neste momento.
- **Testes**: Será necessário validar se a lógica de "Ajuste de S/N (Sincronismo)" continua funcionando após a separação dos slots.

---
**Aguardando autorização para iniciar a implementação.**
