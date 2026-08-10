# Backlog Item 5.1: Inconsistência de status da Aeronave sob Inspeção

## 1. Descrição do Problema
O controle de status operacional da frota de aeronaves apresentava riscos de concorrência:
1. O toggle manual de status forçava `INATIVA` mesmo que a aeronave estivesse fisicamente sob inspeção ativa.
2. A conclusão ou cancelamento de uma inspeção forçava incondicionalmente a aeronave para `DISPONIVEL`, mesmo que outra inspeção com tipo diferente estivesse ocorrendo em paralelo na mesma célula.

## 2. Plano de Implementação
1. **Guarda no toggle manual de status:** Em `app/modules/aeronaves/service.py` (função `alternar_status_aeronave`), antes de inativar, consultar se a aeronave possui alguma inspeção ativa (`ABERTA` ou `EM_ANDAMENTO`). Se sim, levantar `ValueError` bloqueando a ação.
2. **Guarda na conclusão de inspeção:** Em `app/modules/inspecoes/service.py` (funções `concluir_inspecao` e `cancelar_inspecao`), antes de setar `aeronave.status = StatusAeronave.DISPONIVEL.value`:
   - Executar query que conta outras inspeções com status em `STATUS_ATIVOS` na mesma `aeronave_id` que não sejam a inspeção atual.
   - Apenas aplicar `DISPONIVEL` se a contagem for exatamente zero.

## 3. Critérios de Aceitação
* Tentativas de marcar aeronaves como `INATIVA` via toggle manual enquanto há inspeções em andamento falham com `ValueError`.
* Se uma aeronave possui duas inspeções ativas em andamento (ex: IF-50H e IPE) e uma delas é cancelada/concluída, o status da aeronave permanece como `INSPEÇÃO`.
* Testes integrados simulam o ciclo de vida concorrente de inspeções e validam o comportamento do status final da aeronave.
