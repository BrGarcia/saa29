# Lista de Bugs - Módulo de Inspeções

## [RESOLVIDO] BUG 01: Erro 422 ao acessar “Catálogo Global de Tarefas”
**Data:** 2026-05-01  
**Causa:** Conflito de rotas onde a rota dinâmica `/{inspecao_id}` capturava o path `/tarefas-catalogo`.  
**Correção:** Reorganização do `router.py` garantindo que rotas estáticas sejam declaradas antes das dinâmicas. Limpeza de cache de bytecode (`__pycache__`) realizada.

---

## [RESOLVIDO] BUG 02: Erro MissingGreenlet ao ativar tarefa no Catálogo
**Data:** 2026-05-01  
**Causa:** Acesso ao campo `updated_at` (onupdate) após `flush` sem `refresh` em contexto assíncrono. O SQLAlchemy tentava fazer lazy load do valor gerado pelo DB fora de um contexto compatível.  
**Correção:** Inclusão de `await db.refresh(obj)` após chamadas de `flush` no `service.py` para todos os modelos com campos de auditoria temporal.

---