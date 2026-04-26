# ADR-003: Heranca de Controles de Vencimento no Service Layer

**Data:** 2026-03-27  
**Status:** Aceito  
**Decisores:** Equipe de desenvolvimento SAA29

---

## Contexto

O SAA29 controla vencimentos de manutencao por item fisico. Cada PN pode exigir varios tipos de controle e cada item precisa refletir esses controles sem duplicar regras de negocio em consultas ou no banco.

O problema central e manter consistencia entre:

- o catalogo de equipamentos (`ModeloEquipamento`);
- a associacao entre PN e controle (`EquipamentoControle`);
- os controles efetivos por item (`ControleVencimento`).

## Decisao

Implementar a heranca de controles **na camada de servico**, e nao por trigger de banco.

Fluxo atual:

1. Ao criar `ItemEquipamento`, o service busca os `EquipamentoControle` do respectivo `ModeloEquipamento` e cria os `ControleVencimento` correspondentes com origem `PADRAO`.
2. Ao associar um novo controle a um PN, o service propaga os registros faltantes para todos os itens existentes daquele modelo.
3. A unicidade `UNIQUE(item_id, tipo_controle_id)` impede duplicacao de controle.

## Alternativas Consideradas

| Alternativa | Pro | Contra |
|-------------|-----|--------|
| Trigger no banco | Automatizacao total | Lgica espalhada entre banco e aplicacao |
| Calculo on-the-fly | Nenhum dado derivado para manter | Piora listagens e perde historico persistido |
| Service layer (escolhido) | Testavel e explicito | Depende do uso correto das funcoes de dominio |

## Consequencias

**Positivas:**

- a regra fica visivel no codigo Python;
- os testes conseguem cobrir a propagacao;
- o historico de vencimentos pode ser consultado diretamente;
- o dominio de equipamentos permanece concentrado em `service.py`.

**Negativas / Trade-offs:**

- bypass direto no banco pode criar itens sem controles herdados;
- operacoes em massa podem ficar mais lentas do que um `INSERT ... SELECT` em trigger;
- a consistencia depende de sempre usar as funcoes do service.

## Referencias

- [`app/modules/equipamentos/service.py`](../../../app/modules/equipamentos/service.py)
- [`app/modules/equipamentos/models.py`](../../../app/modules/equipamentos/models.py)
- [`docs/architecture/Database.md`](../Database.md)
