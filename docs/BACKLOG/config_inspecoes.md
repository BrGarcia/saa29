DOCUMENTO TÉCNICO – MÓDULO DE INSPEÇÕES (VERSÃO SIMPLIFICADA)

OBJETIVO
Este documento descreve a implementação do módulo de inspeções com foco em simplicidade, clareza operacional e baixo acoplamento. O modelo foi projetado para atender o fluxo real de manutenção, evitando complexidade desnecessária.

---------------------------------------------------------------------

1. CONCEITO GERAL

O sistema de inspeções é baseado em três pilares:

1) Tipos de inspeção (ex: Y, 2Y, A, 4A)
2) Catálogo de tarefas reutilizáveis
3) Execução de inspeções com checklist gerado automaticamente

Uma inspeção real pode conter múltiplos tipos simultaneamente, e o sistema deve consolidar todas as tarefas envolvidas, removendo duplicações.

---------------------------------------------------------------------

2. FILOSOFIA DE DESIGN

- Simplicidade acima de tudo
- Evitar excesso de botões e telas
- Separação clara entre CONFIGURAÇÃO e EXECUÇÃO
- Reutilização máxima de dados (catálogo de tarefas)
- Histórico imutável (snapshot na execução)

---------------------------------------------------------------------

3. ESTRUTURA DE CONFIGURAÇÃO

A configuração do sistema será baseada em apenas dois blocos:

-----------------------------------
3.1 TIPOS DE INSPEÇÃO

Botões disponíveis:
- Criar Tipo de Inspeção
- Editar Tipo de Inspeção

Funcionalidades dentro de "Editar Tipo":
- Editar nome, código e descrição
- Adicionar tarefas ao tipo
- Remover tarefas do tipo
- Reordenar tarefas (campo "ordem")
- Inativar tipo de inspeção

IMPORTANTE:
- Não excluir tipos em uso
- Utilizar "inativar" como padrão

-----------------------------------
3.2 TAREFAS

Botões disponíveis:
- Criar Tarefa
- Editar Tarefa

Funcionalidades dentro de "Editar Tarefa":
- Editar nome
- Editar descrição
- Editar referência técnica
- Inativar tarefa

IMPORTANTE:
- Alterações no catálogo NÃO devem afetar inspeções já executadas

---------------------------------------------------------------------

4. MODELO DE DADOS (RESUMO)

TABELAS PRINCIPAIS:

- tipos_inspecao
- tarefas_inspecao
- tipos_inspecao_tarefas (associação N:N)
- inspecao_eventos
- inspecao_evento_tipos
- inspecao_tarefas

REGRAS IMPORTANTES:

- UNIQUE(tipo_inspecao_id, tarefa_id)
- tarefas devem possuir campo "ordem"
- tarefas podem ser obrigatórias ou não

---------------------------------------------------------------------

5. GERAÇÃO DE INSPEÇÃO

Ao criar uma nova inspeção:

Entrada:
- aeronave
- tipos de inspeção (ex: Y + A)

Processo:
1. Buscar tarefas de cada tipo
2. Unificar todas as tarefas
3. Remover duplicadas (por tarefa_id)
4. Criar registros em inspecao_tarefas
5. Copiar descrição (snapshot)

Saída:
- checklist único consolidado

---------------------------------------------------------------------

6. EXECUÇÃO DA INSPEÇÃO

Cada tarefa possui:

- status: PENDENTE / EM_EXECUCAO / CONCLUIDA
- observação
- executada_por_id
- executada_em

Ao concluir:
- registrar usuário
- registrar data/hora

Interface deve exibir:
- trigrama do militar
- data/hora da execução

Formato visual sugerido:
[ABC] 27/04/2026 14:32

---------------------------------------------------------------------

7. TAREFAS MANUAIS

O sistema deve permitir:

- adicionar tarefas fora do catálogo
- origem = MANUAL
- tarefa_id = NULL

Essas tarefas coexistem com as de template.

---------------------------------------------------------------------

8. INTEGRAÇÃO COM PANES

Se uma tarefa identificar falha:

- pode gerar uma pane
- vincular via campo pane_id

Não misturar lógica de inspeção com lógica de pane.

---------------------------------------------------------------------

9. STATUS DA AERONAVE

Durante inspeção:
- status = INSPEÇÃO

Após conclusão:
- retornar para DISPONIVEL ou INDISPONIVEL

---------------------------------------------------------------------

10. DECISÕES IMPORTANTES

1) NÃO usar exclusão física como padrão
→ usar "inativação"

2) NÃO usar JSON para tarefas
→ manter estrutura relacional

3) SEM versionamento neste momento
→ manter modelo simples

4) SNAPSHOT obrigatório
→ garante histórico consistente

5) DEDUPLICAÇÃO obrigatória
→ evitar tarefas repetidas

6) ORDEM das tarefas é essencial
→ melhora usabilidade

---------------------------------------------------------------------

11. O QUE FOI INTENCIONALMENTE EVITADO

- workflows complexos
- múltiplos níveis de aprovação
- versionamento de inspeções
- regras excessivas de negócio
- telas complexas

Objetivo: sistema rápido, direto e operacional.

---------------------------------------------------------------------

12. RESUMO FINAL

Configuração:
- 2 entidades (Tipos e Tarefas)
- 2 botões para cada

Execução:
- inspeção com múltiplos tipos
- tarefas consolidadas automaticamente
- baixa individual com rastreabilidade

Resultado:
- sistema simples
- fácil de usar
- tecnicamente consistente
- preparado para evolução futura

---------------------------------------------------------------------
FIM DO DOCUMENTO