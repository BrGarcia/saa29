# Plano de Implementação: Correções de Auditoria SAA29

Este plano detalha as etapas para corrigir as falhas identificadas no `RELATORIO_COMPLETO.MD`, focando em Performance, Arquitetura e Segurança.

## Fase 1: Performance e Otimização de Queries (N+1)
- [x] **Otimizar Listagens de Inventário:** Revisar `app/equipamentos/service.py` e adicionar `.options(selectinload(...))` em todas as consultas que iteram sobre relacionamentos de `Instalacao`, `ItemEquipamento` e `SlotInventario`.
- [x] **Paginação no Histórico:** Implementar paginação (limit/offset) no endpoint `/inventario/historico` para evitar degradação de performance com o crescimento do banco.
- [x] **Configuração WAL no SQLite:** Ajustar `app/database.py` para garantir que `journal_mode=WAL` seja aplicado em todas as conexões, melhorando a concorrência de leitura/escrita.

## Fase 2: Refatoração Arquitetural (SOLID)
- [ ] **Desacoplar Ajuste de Inventário:** Quebrar a função `ajustar_inventario_item` em `app/equipamentos/service.py`. Criar um validador de regras de negócio separado.
- [ ] **Implementar Exceções de Domínio:** Criar `app/core/exceptions.py` e substituir o uso genérico de `ValueError` por exceções tipadas (ex: `EntidadeNaoEncontradaError`, `ConflitoInventarioError`).
- [ ] **Global Exception Handler:** Configurar um handler no FastAPI (`app/main.py`) para traduzir exceções de domínio em respostas HTTP (404, 409, 400) de forma automática.

## Fase 3: Redução de Duplicação e Qualidade
- [ ] **Base Repository / Helper de Queries:** Extrair lógicas repetitivas de busca de usuário e aeronave para funções utilitárias compartilhadas ou um padrão Repository simples.
- [ ] **Refinar `_ensure_default_aeronaves`:** Corrigir a inserção em loop no `app/main.py` para usar um único comando `INSERT` ou gerenciar transações de forma mais eficiente fora do loop.

## Fase 4: Validação e Testes
- [ ] **Testes de Integração de Fluxo Crítico:** Criar testes para validar que a otimização das queries não quebrou os relacionamentos.
- [ ] **Verificação de Regressão:** Validar se as novas exceções de domínio estão sendo convertidas corretamente para JSON no frontend.
