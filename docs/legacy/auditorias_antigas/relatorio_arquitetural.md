# Relatório de Consistência Arquitetural - SAA29

**Data:** 26/04/2026  
**Status:** Análise de Sincronização (Código vs. Documentação)

---

## 1. Inconsistências de Status (Enums)

Foram detectadas divergências entre as definições no arquivo `app/shared/core/enums.py` e as expectativas no `Database.md` e nos comentários dos modelos.

### 1.1 Status de Aeronave (`StatusAeronave`)
*   **Status**: ✅ **CONCLUÍDO**
*   **Observação**: O status foi alterado de `OPERACIONAL` para `DISPONIVEL` em todo o código-fonte (Enums, Models, Services, Schemas e Frontend). Os status finais são: `DISPONIVEL`, `INDISPONIVEL`, `INSPEÇÃO`, `ESTOCADA` e `INATIVA`.

### 1.2 Status de Vencimento (`StatusVencimento`)
*   **Status**: ✅ **CONCLUÍDO**
*   **Novos Status**: `OK`, `VENCENDO`, `VENCIDO`, `PRORROGADO`.
*   **Decisão de Design**: Os status `PENDENTE` e `FALTANTE` serão removidos.
*   **Lógica de Prorrogação**: Se um controle estiver `VENCIDO` ou `VENCENDO`, mas possuir uma `ProrrogacaoVencimento` ativa vinculada, o status exibido deve ser `PRORROGADO`.
*   **Lógica de Exibição (Grid)**: O termo "Desinstalado" não será um status de banco, mas sim uma sinalização da interface quando um `SlotInventario` de uma aeronave não possuir uma `Instalacao` ativa.

---

## 2. Relação de Equipamentos e Vencimentos - ✅ **VERIFICADO E IMPLEMENTADO**

A estrutura segue a hierarquia de manutenção aeronáutica:

1.  **Catálogo (ModeloEquipamento)**: Define o PN e as regras de periodicidade (Ex: ELT vence a cada 12 meses).
2.  **Slot (SlotInventario)**: Define o lugar na aeronave (Ex: Posição do ELT no CES).
3.  **Item (ItemEquipamento)**: É a peça física (SN). Os vencimentos (`ControleVencimento`) são vinculados aqui.
4.  **Instalação**: O vínculo temporal. 
    *   Se `Instalacao` ativa -> Mostra status do `ControleVencimento` do Item.
    *   Se sem `Instalacao` -> Mostra "Desinstalado" na posição da aeronave.

---

## 3. Quebras de Importação (Regressão) - ✅ **CORRIGIDO**

A extração do módulo de `vencimentos` foi estabilizada.

### 3.1 Script `scripts/seed/seed_vencimentos.py` - ✅ **FIXED**
### 3.2 Script `scripts/seed/seed_inventario.py` - ✅ **FIXED**

---

## 4. Modularização DDD (Plano de Reorganização) - ✅ **CONCLUÍDO**

O plano mestre detalhado em `docs/legacy/reorganizacao_arquitetural.md` foi integralmente executado.

### 4.1 Extração de Vencimentos (Phase 1)
*   **Status**: ✅ Concluído
*   **Ações**: Modelos, Serviços e Routers movidos de `equipamentos` para `vencimentos`. Scripts de seed corrigidos e importações globais atualizadas.

### 4.2 Módulo de Efetivo (Phase 2)
*   **Status**: ✅ Concluído
*   **Ações**: Criado módulo `app/modules/efetivo/` com suporte a registros de `Indisponibilidade` (Férias, Dispensa, etc.), permitindo futuramente a alocação inteligente de equipes.

### 4.3 Padronização e Roteamento (Phase 3)
*   **Status**: ✅ Concluído
*   **Ações**: Todos os routers registrados no `app/bootstrap/main.py`. Importações explícitas de modelos adicionadas para garantir integridade do SQLAlchemy Registry.

---

## 5. Recomendações de Curto Prazo - ✅ **CONCLUÍDO**

1.  **Ajustar Enums**: Sincronizado `StatusAeronave` e `StatusVencimento` no `enums.py`. ✅
2.  **Remover Acentos**: Ajustado o padrão de nomes. *Observação: O acento em `"INSPEÇÃO"` foi mantido por decisão operacional (uso prático do hangar).* ✅
3.  **Atualizar Models**: Comentários e valores default da classe `Aeronave` e `ControleVencimento` foram atualizados. ✅
