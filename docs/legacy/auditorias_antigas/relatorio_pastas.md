# Relatorio de Organizacao de Pastas

Este relatorio e apenas uma sugestao estrutural. Nenhuma logica, codigo ou comportamento do sistema foi alterado.

## Diagnostico rapido

- A raiz do projeto esta concentrando codigo, documentacao, bancos locais, logs, relatorios e arquivos operacionais.
- Existem artefatos locais e sensiveis misturados ao repositorio, como `.env`, `.env.backup`, `.db`, `.db.bak`, `uploads/` e logs.
- A pasta `app/` ja possui uma base boa por dominio, mas `templates/` e `static/` ainda estao separados da camada web.
- `docs/` concentra tanto documentacao tecnica quanto grande volume de arquivos PDF de referencia.
- Ha pastas auxiliares pouco definidas ou temporarias, como `scratch/`, `data/` e `claude/`.

## Organizacao sugerida

```text
SAA29/
+- app/
|  +- bootstrap/        # entrada, config, database, dependencies
|  +- shared/           # core, middleware, utilitarios comuns
|  +- modules/
|  |  +- auth/
|  |  +- aeronaves/
|  |  +- equipamentos/
|  |  \- panes/
|  \- web/
|     +- pages/
|     +- templates/
|     \- static/
+- tests/
|  +- unit/
|  +- integration/
|  +- security/
|  \- architecture/
+- scripts/
|  +- dev/
|  +- db/
|  +- seed/
|  \- maintenance/
+- docs/
|  +- ia/
|  +- architecture/
|  +- development/
|  +- requirements/
|  +- security/
|  +- reference/
|  |  \- fim/
|  \- archive/
+- data/
|  +- fixtures/
|  +- seeds/
|  \- samples/
+- var/                 # ignorado no git
|  +- logs/
|  +- uploads/
|  +- db/
|  \- tmp/
+- infra/               # opcional, se a camada operacional crescer
|  +- docker/
|  \- deploy/
\- README.md
```

## Ganhos esperados

- Reducao da poluicao na raiz, facilitando navegacao e onboarding.
- Separacao clara entre codigo-fonte, documentacao, dados e arquivos de execucao.
- Menor risco de versionar acidentalmente arquivos sensiveis ou temporarios.
- Melhor previsibilidade para testes, scripts de manutencao e deploy.
- Estrutura mais segura para uploads e bancos locais, mantendo esses itens fora do fluxo principal do codigo.

## Prioridades recomendadas

1. Tirar da raiz tudo que for artefato local: logs, bancos SQLite, uploads e arquivos temporarios.
2. Consolidar a camada web dentro de `app/web/` para aproximar `pages`, `templates` e `static`.
3. Reorganizar `scripts/` por finalidade: banco, seed, desenvolvimento e manutencao.
4. Mover os PDFs e materiais de referencia pesada de `docs/fim/` para `docs/reference/fim/`.
5. Revisar o versionamento de `.env.backup`, bancos locais, logs e conteudo de `uploads/`.

## Pontos de seguranca

- `uploads/` nao deve permanecer misturado ao codigo versionado.
- Arquivos como `.env.backup`, `.db`, `.db.bak` e logs devem ficar fora da raiz e preferencialmente fora do Git.
- Pastas temporarias como `scratch/` devem ser tratadas como area local de trabalho e nao como parte da estrutura principal.
- Se `data/` ou `claude/` tiverem funcao permanente, vale documentar claramente; caso contrario, remover ou isolar.

## Documentos Em `docs/`

Para entendimento do projeto, eu separaria assim:

- Manter como essenciais:
  - `docs/README.md`
  - `docs/architecture/overview.md`
  - `docs/architecture/03_MODEL_DB.md`
  - `docs/architecture/adr/*.md`
  - `docs/api/referencia-api.md`
  - `docs/development/guia-desenvolvimento.md`
  - `docs/development/guia-testes.md`
  - `docs/development/migracao_postgresql.md`
  - `docs/SECURITY.md`

- Manter como apoio, mas nao essencial para entender o codigo:
  - `docs/CONTRIBUTING.md`
  - `docs/CODE_OF_CONDUCT.md`
  - `docs/ROADMAP.md`
  - `docs/CHANGELOG.md`
  - `docs/NEXT.md`
  - `docs/implementacao_*.md`
  - `docs/tdd_inventario.md`
  - `docs/archives/*`

- Candidatos para arquivo externo ou limpeza futura, se nao houver uso pratico:
  - `docs/fim/*.PDF`
  - `docs/inventario.txt`
  - materiais muito antigos ou duplicados em `docs/archives/`

Observacao: `CODE_OF_CONDUCT.md` e `CONTRIBUTING.md` nao ajudam diretamente a entender a logica do sistema, mas eu nao apagaria se o repositorio continuar colaborativo. O melhor destino para eles, se a meta for simplificar, e mantelos como documentos de governanca em vez de espalhados pela raiz.

## Pasta `docs/ia/`

Criar uma pasta `docs/ia/` e uma boa ideia, desde que ela seja tratada como camada de apoio para IA e nao como fonte principal da documentacao.

- O que colocar:
  - resumo de arquitetura
  - resumo de regras de negocio
  - resumo de stack e fluxo de desenvolvimento
  - prompts-base ou instrucoes curtas para agentes IA
  - mapa de arquivos mais importantes

- O que nao colocar:
  - documentacao completa duplicada
  - copias integrais de arquivos ja existentes
  - informacoes sensiveis
  - instrucoes que possam ficar obsoletas sem revisao

- Forma recomendada:
  - manter os documentos oficiais em `docs/architecture/`, `docs/development/`, `docs/security/` e `docs/requirements/`
  - criar em `docs/ia/` apenas versoes resumidas e operacionais
  - indicar no inicio de cada arquivo que ele e derivado e que a referencia real esta na documentacao oficial

Se o objetivo for economizar tokens, essa abordagem e melhor do que jogar tudo em um unico `codex.md`. Um conjunto pequeno de arquivos resumidos, por assunto, tende a funcionar melhor do que um documento unico muito grande.
