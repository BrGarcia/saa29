# docs/ia

obj: contexto rapido para IA
src_of_truth: docs/architecture/, docs/development/, docs/security/, docs/requirements/
rule: este diretorio resume; nao substitui a documentacao oficial

## Ordem sugerida de leitura

0. `docs/ia/contex.md` -> resumo geral do projeto
1. `docs/ia/roadmap_resumido.md` -> o que precisa ser feito agora
2. `docs/ia/resumo_arquitetura.md` -> stack, camadas e estrutura tecnica
3. `docs/ia/resumo_seguranca.md` -> se a tarefa envolver seguranca, auth, csrf, uploads ou logs
4. `docs/ia/resumo_desenvolvimento.md` -> se a tarefa envolver setup, testes, migrations ou fluxo local
5. `docs/ia/mapa_repositorio.md` -> se precisar localizar arquivos e pastas
6. `docs/ia/glossario.md` -> se houver termos ou siglas do dominio
7. `docs/ia/prompts_base.md` -> se a IA precisar de instrucoes operacionais

## Regra de atualizacao

Ao finalizar uma implementacao, atualizar:
- a documentacao oficial relacionada ao tema
- `docs/ia/contex.md`
- `docs/ia/roadmap_resumido.md`

use:
- ler antes de tarefas de analise, refatoracao, testes e organizacao
- manter arquivos curtos e atualizados
- evitar duplicar textos longos de outras docs

contents:
- resumo_arquitetura.md
- resumo_desenvolvimento.md
- resumo_seguranca.md
- mapa_repositorio.md
- glossario.md
- prompts_base.md
- roadmap_resumido.md
