## Pane Pendente

**Status atual:** resolvida em `2026-04-29` e registrada em `docs/bugs/bugs.md`.

### Relato observado

Ao tentar visualizar os detalhes de uma pane excluída na página `Intervenção de Pane`, aparecem as mensagens:

- `Pane não encontrada.`
- `Falha ao recuperar informações da Pane.`

No console do navegador:

```text
GET /panes/<pane_id> 404 (Not Found)
Error: Pane não encontrada.
```

Contudo, se a pane for restaurada pelo botão `RESTAURAR`, a visualização volta a funcionar normalmente.

---

### Verificação técnica

A pane foi confirmada no fluxo atual do sistema.

- A página HTML de detalhes sempre é renderizada para qualquer `pane_id` em `app/web/pages/router.py`.
- Ao carregar a tela, o frontend executa `GET /panes/${PANE_ID}` em `app/web/static/js/panes_detalhe.js`.
- O endpoint `GET /panes/{pane_id}` chama `service.buscar_pane(db, pane_id)` sem pedir inclusão de inativas, em `app/modules/panes/router.py`.
- No service, `buscar_pane(..., incluir_inativos=False)` aplica por padrão `Pane.ativo == True`, em `app/modules/panes/service.py`.

Ou seja: a rota da página aceita abrir a tela de detalhes de uma pane excluída, mas a API de dados da própria tela recusa essa mesma pane por estar inativa.

---

### Causa provável

Há uma inconsistência entre a camada de página e a camada de API:

- o frontend permite navegar até `/panes/{pane_id}/detalhes` mesmo quando a pane está excluída;
- porém o backend de detalhamento trata panes excluídas como inexistentes, porque o soft delete filtra `ativo == True` por padrão.

Por isso o comportamento só “volta ao normal” após restaurar a pane: ao restaurar, ela passa novamente no filtro padrão do `buscar_pane()`.

---

### Como resolver

Sem implementar agora, a correção recomendada é uma destas:

1. Permitir que o endpoint de detalhamento busque panes inativas quando o objetivo for apenas visualização.
2. Alternativamente, adicionar um parâmetro explícito de consulta, como `incluir_inativos=true`, usado somente na tela de detalhes.
3. No frontend, ao detectar que a pane está excluída, renderizar a tela em modo somente leitura:
   - sem concluir
   - sem editar
   - sem anexar
   - com indicação visual de que a pane está na lixeira

---

### Melhor abordagem

A abordagem mais coerente parece ser:

- permitir visualização de panes excluídas no endpoint de detalhe;
- manter bloqueadas as ações de alteração para panes inativas.

Assim o sistema preserva rastreabilidade e consulta histórica, sem reabrir fluxo operacional em registro excluído.

---

### Impacto esperado da correção

- elimina o `404` indevido ao abrir detalhes de pane excluída;
- mantém consistência com o botão `RESTAURAR` e com a existência real do registro;
- melhora a usabilidade da lixeira de panes;
- preserva a regra de soft delete sem esconder histórico.

---

*Verificado e documentado em: 2026-04-29*
