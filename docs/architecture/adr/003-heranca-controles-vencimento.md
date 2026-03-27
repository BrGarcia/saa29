# ADR-003: Herança Automática de Controles de Vencimento

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O sistema precisa controlar vencimentos de manutenção por item físico (número de série). Cada tipo de equipamento (part number) define quais controles periódicos seus itens devem ter (TBV, RBA, CRI etc.).

O desafio: como garantir que um novo item herde automaticamente os controles definidos para seu tipo de equipamento, e que um novo controle seja propagado para todos os itens existentes?

## Decisão

Implementar **herança automática bidirecional** via triggers de service:

1. **Ao criar `ItemEquipamento`** → buscar todos os `EquipamentoControle` do equipamento e criar um `ControleVencimento` (origem=`PADRAO`) para cada um.

2. **Ao criar `EquipamentoControle`** → buscar todos os `ItemEquipamento` existentes do equipamento e criar `ControleVencimento` faltantes.

A restrição `UNIQUE(item_id, tipo_controle_id)` no banco garante idempotência.

## Alternativas Consideradas

| Alternativa | Prós | Contras |
|-------------|------|---------|
| Trigger no banco (PostgreSQL) | Automático, não depende da app | Lógica espalhada entre app e DB, difícil de testar |
| Herança no service (escolhido) | Testável, visível, sem acoplamento ao DB | Depende da disciplina dos devs de sempre usar o service |
| Calcular on-the-fly (sem tabela) | Sem dados derivados | Performance ruim em listagens, sem histórico |

## Consequências

**Positivas:**
- Lógica testável via testes unitários Python
- Auditoria: `origem` indica se o controle é herdado (`PADRAO`) ou específico (`ESPECIFICO`)
- Sem acoplamento à engine de banco

**Negativas / Trade-offs:**
- Se um item for criado diretamente no banco (bypass da app), não terá controles herdados
- Propagação em massa pode ser lenta para equipamentos com muitos itens (otimizar com `INSERT ... SELECT` em Fase 4)

## Referências
- [03_MODEL_DB.md §5 – Algoritmos de Herança](../../../03_MODEL_DB.md)
- [`app/equipamentos/service.py` – `criar_item_com_heranca()`](../../../app/equipamentos/service.py)
- [`app/equipamentos/service.py` – `propagar_controle_para_itens()`](../../../app/equipamentos/service.py)
