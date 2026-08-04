# Plano de incorporacao do modulo de manuais ao SAA29

**Data da analise:** 04/08/2026  
**Escopo:** avaliar a viabilidade de incorporar ao SAA29 o projeto externo documentado em `README.md`, `Projeto.MD`, `Especificacao.MD`, `Runbook.MD`, `RAG.MD` e `prompt.md`, atualmente armazenados em `docs/backlog/manuais`.  
**Restricao desta entrega:** nenhuma implementacao foi realizada; este documento e apenas um parecer tecnico e plano de execucao.

## 1. Conclusao executiva

A incorporacao e **viavel e recomendavel**, desde que o projeto externo seja tratado como um **novo modulo do monolito SAA29**, e nao como uma segunda aplicacao embutida.

O encaixe de dominio e forte:

- O SAA29 ja e um sistema de manutencao da aeronave A-29, com modulos de panes, inspecoes, vencimentos, inventario, frota, efetivo e dashboard.
- O projeto externo resolve uma dor complementar: consulta rapida a manuais tecnicos EMB-314/A-29, com busca full-text e abertura do PDF na pagina exata.
- O SAA29 ja possui acervo parcial de FIM em `docs/fim`, com 412 arquivos, incluindo muitos PDFs e `fim.json`.
- O modulo de panes e inspecoes se beneficiaria diretamente de links para documentos tecnicos, capitulos ATA, procedimentos e paginas de referencia.

O ponto de atencao e arquitetural: a documentacao externa foi escrita para um repositorio autonomo chamado `supertucano-docs`, com `data/`, `index/catalog.db`, Caddy proprio, `/` como home, `/data/*` publico e autenticacao ainda em decisao. No SAA29, essas decisoes precisam ser adaptadas para:

- usar a autenticacao JWT/cookie e RBAC ja existentes;
- respeitar o padrao `app/modules/<modulo>/`;
- evitar conflito com o `data/` atual do SAA29, que ja e usado pelo banco/volume;
- integrar a UI ao `base.html` e ao menu do sistema;
- usar Alembic e o modelo de configuracao atual;
- tratar PDF tecnico como acervo controlado, nao como anexo comum.

Recomendacao: incorporar em fases, iniciando por um MVP somente-leitura de catalogo, indexacao e busca, com viewer protegido por login.

## 2. Documentacao analisada

Foram lidos os seguintes arquivos em `docs/backlog/manuais`:

- `README.md`: visao geral do sistema de consulta de manuais, acervo estimado, stack e roadmap.
- `Projeto.MD`: arquitetura autônoma proposta, stack, fluxo de indexacao, modelo de dados, busca FTS5, roadmap e infraestrutura.
- `Especificacao.MD`: telas, rotas, contratos de API, regras de negocio RN-01 a RN-10, casos de borda E-01 a E-12 e criterios de aceite.
- `Runbook.MD`: provisionamento, deploy, publicacao de manuais, backup, restauracao, monitoramento e seguranca.
- `RAG.MD`: evolucao futura com busca semantica, embeddings, chunks, busca hibrida e perguntas com citacoes.
- `prompt.md`: prompt de execucao do projeto autonomo, util como checklist de implementacao, mas inadequado para aplicacao direta no SAA29 sem adaptacao.

Tambem foram consultados pontos relevantes do SAA29:

- `docs/architecture/overview.md`
- `docs/architecture/Database.md`
- `docs/architecture/RBAC.md`
- `docs/backlog/00_mapa_arquitetural.md`
- `app/bootstrap/main.py`
- `app/bootstrap/database.py`
- `app/bootstrap/config/__init__.py`
- `app/bootstrap/dependencies.py`
- `app/web/pages/router.py`
- `app/web/templates/base.html`
- `app/shared/core/storage.py`
- `requirements.txt`
- `docker-compose.yml`

## 3. Estado atual do SAA29 relevante para a incorporacao

O SAA29 e um monolito modular em FastAPI com SQLAlchemy async, SQLite WAL, Alembic, Jinja2, CSS/JS estatico e autenticacao JWT via cookie/header. O padrao real de modulo e:

```text
app/modules/<modulo>/
  models.py
  schemas.py
  service.py
  router.py
```

Alguns modulos possuem servicos auxiliares especificos, como `inspecoes/pdf_service.py` e `equipamentos/xlsx_service.py`. Portanto, um modulo de manuais poderia legitimamente ter camadas extras como `catalog_service.py`, `indexer_service.py`, `search_service.py` e `viewer_service.py`, desde que mantenha a fronteira de router fino e regras no service.

Pontos importantes:

- O bootstrap registra routers explicitamente em `app/bootstrap/main.py`.
- As paginas HTML ficam em `app/web/pages/router.py` e templates em `app/web/templates`.
- Os endpoints de API usam dependencias como `CurrentUser`, `AdminRequired`, `EncarregadoOuAdmin`, `InspetorOuAdmin`.
- O menu principal esta em `app/web/templates/base.html`.
- O sistema ja tem CSP, CSRF e headers de seguranca.
- O storage atual (`LocalStorageService`/R2) foi desenhado para anexos de panes, nao para servir acervo tecnico grande.
- O `docker-compose.yml` monta `sqlite_data:/app/data`; portanto, usar `data/` como raiz dos manuais causaria ambiguidade e risco operacional.

## 4. Avaliacao de compatibilidade

| Area | Projeto externo | SAA29 atual | Parecer |
|---|---|---|---|
| Linguagem/framework | Python + FastAPI | Python + FastAPI | Compativel |
| Templates | Jinja2 + htmx/Tailwind | Jinja2 + Vanilla JS/CSS proprio | Parcialmente compativel; evitar Tailwind/htmx no MVP se nao forem necessarios |
| Banco | SQLite FTS5 em `index/catalog.db` | SQLite async principal com Alembic | Compativel, mas decidir banco unico vs indice separado |
| PDF | PyMuPDF + PDF.js | ReportLab para gerar PDFs; PDFs existentes em `docs/fim` | Compativel; exige nova dependencia PyMuPDF e assets PDF.js |
| Auth | Decisao em aberto | JWT/cookie + RBAC | Deve herdar SAA29 |
| Deploy | App + Caddy, `/data/*` estatico | Docker web unico em 8000 | Precisa adaptar; nao assumir Caddy dedicado |
| Acervo | `data/<MANUAL>/<CAPITULO>/*.PDF` | `data/` ja usado; `docs/fim` tem acervo parcial | Mudar raiz para `var/manuais/acervo` ou similar |
| UI | Home propria em `/` | `/` redireciona para `/dashboard` | Modulo deve usar `/manuais` |
| Futuro RAG | Planejado | Nao existe modulo IA operacional | Viavel como fase futura, nao MVP |

## 5. Decisao arquitetural recomendada

Criar um modulo novo chamado **`manuais`**:

```text
app/modules/manuais/
  __init__.py
  models.py
  schemas.py
  router.py
  service.py
  catalog.py
  indexer.py
  search.py
```

E templates/assets:

```text
app/web/templates/manuais/
  lista.html
  manual.html
  capitulo.html
  busca.html
  viewer.html

app/web/static/js/manuais.js
app/web/static/js/pdfjs/
app/web/static/css/manuais.css
```

Rotas sugeridas:

```text
GET  /manuais
GET  /manuais/{manual_path}
GET  /manuais/{manual_path}/{chapter}
GET  /manuais/viewer?doc={id}#page={n}
GET  /manuais/search?q=...

GET  /manuais/api/search
GET  /manuais/api/status
POST /manuais/admin/reindex
GET  /manuais/files/{path}
```

Observacao: evitar `/data/{path}` porque `data/` ja tem significado no SAA29 e porque expor acervo tecnico sem passar por autenticacao pode contrariar o modelo Zero Trust do sistema.

## 6. Banco de dados: recomendacao

Ha duas opcoes viaveis.

### Opcao A - Integrar as tabelas ao banco principal do SAA29

Criar tabelas no banco principal via Alembic:

- `manuais_catalogo`
- `manuais_documentos`
- `manuais_paginas`
- `manuais_index_status`
- `manuais_paginas_fts` como tabela virtual FTS5

Vantagens:

- Usa backup e migracoes existentes.
- Facilita RBAC, auditoria e possiveis vinculos com panes/inspecoes.
- Mantem tudo sob o mesmo ciclo de vida do SAA29.

Riscos:

- O banco principal pode crescer muito com texto extraido de milhares de PDFs.
- Escritas pesadas de indexacao competem com operacoes normais do SAA29.
- Alembic com tabela virtual FTS5 exige migracao manual cuidadosa.

### Opcao B - Indice separado em `var/manuais/index/catalog.db`

Manter o catalogo/index em SQLite proprio, derivado do acervo, usando conexao separada.

Vantagens:

- Isola carga de indexacao e crescimento.
- O indice e reconstruivel.
- Menor risco de afetar transacoes operacionais de panes, inspeções e vencimentos.

Riscos:

- Mais uma conexao/configuracao de banco.
- Backups e status precisam considerar dois bancos.
- Vínculos fortes com outros modulos ficam menos diretos.

### Parecer

Para o SAA29, a opcao mais segura e **B no MVP**, com possibilidade de migrar metadados pequenos para o banco principal depois.

Justificativa: o modulo de manuais e majoritariamente read-only e o indice e 100% derivado do acervo. Isolar o `catalog.db` reduz risco sobre o banco operacional do SAA29. Caso futuramente sejam criados favoritos, historico, citacoes em panes ou vinculos de inspecao, esses dados de usuario devem ir para o banco principal, enquanto o texto indexado permanece no banco de indice.

## 7. Diretorios e configuracao recomendados

Nao usar `data/` para os manuais dentro do SAA29.

Adicionar configuracoes futuras em `Settings`:

```text
MANUAIS_ENABLED=true
MANUAIS_DATA_DIR=var/manuais/acervo
MANUAIS_INDEX_DIR=var/manuais/index
MANUAIS_MAX_PDF_MB=150
MANUAIS_REINDEX_ON_STARTUP=false
```

Estrutura sugerida:

```text
var/
  manuais/
    acervo/
      AMM_PART1_1651/
      FIM_1741/
      version/
      manual_details.xml
      manual_type.xml
      collections.ini
    index/
      catalog.db
      catalog.db-wal
      catalog.db-shm
    logs/
      reindex.log
      merge_report.txt
```

O acervo parcial existente em `docs/fim` deve ser tratado como fonte inicial ou fixture de validacao, nao como local definitivo de runtime. `docs/` deve continuar sendo documentacao/versionamento, nao armazenamento operacional de PDFs.

## 8. Ajustes necessarios na proposta externa

### 8.1 Rotas

A proposta usa `/` como home e `/data/*` para PDF. No SAA29:

- `/` ja redireciona para `/dashboard`.
- `/dashboard` e a home operacional.
- O modulo deve viver em `/manuais`.
- APIs devem ficar em `/manuais/api/*` ou `/api/v1/manuais/*`; por consistencia com os demais modulos, a recomendacao e `/manuais/...` para API e paginas, como `panes`, `inspecoes`, `equipamentos` e `vencimentos`.

### 8.2 Autenticacao e autorizacao

Todo acesso ao modulo deve exigir usuario autenticado.

Permissoes sugeridas:

| Acao | Papeis |
|---|---|
| Consultar manuais, capitulos, PDFs e busca | MANTENEDOR, ENCARREGADO, INSPETOR, ADMINISTRADOR |
| Disparar reindexacao | ADMINISTRADOR inicialmente |
| Ver status tecnico do indice | ENCARREGADO, INSPETOR, ADMINISTRADOR |
| Publicar/remover acervo via UI | Fora do MVP; se existir depois, ADMINISTRADOR |
| Usar pergunta com IA/RAG | Piloto restrito; decisao futura |

Isso elimina a decisao D-02 da documentacao externa: no SAA29, a leitura nao deve ficar aberta.

### 8.3 UI

Nao importar uma UI autonoma. O modulo deve:

- estender `base.html`;
- adicionar item no menu principal;
- usar o mesmo padrao visual de botoes, tabelas, filtros, badges e estados vazios;
- evitar scripts inline por causa da CSP;
- colocar JS em `app/web/static/js/manuais.js`;
- manter viewer em pagina propria, com fallback se PDF.js falhar.

### 8.4 Deploy

O Runbook externo assume Caddy servindo `/data/*` diretamente. No SAA29, ha dois caminhos:

1. No MVP, servir PDFs por rota FastAPI protegida com `FileResponse`, validacao de path e suporte a range se necessario.
2. Em producao com acervo grande, revisar o reverse proxy para servir arquivos com autenticacao delegada ou links internos protegidos.

Para seguranca, nao publicar o diretorio de manuais diretamente sem controle de acesso.

### 8.5 Dependencias

Adicionar somente quando for implementar:

- `PyMuPDF` para extracao de texto;
- PDF.js como asset estatico ou pacote controlado;
- opcionalmente `watchdog` apenas na fase de reindexacao automatica.

Evitar adicionar Tailwind e htmx no SAA29 sem necessidade. O frontend atual usa CSS/JS proprio.

## 9. Pontos de integracao com modulos existentes

### Panes

Integracao natural:

- buscar automaticamente no FIM por termos da descricao da pane;
- sugerir documentos por ATA/sistema quando `sistema_subsistema` estiver preenchido;
- permitir anexar uma referencia tecnica a uma pane: manual, documento, pagina e trecho;
- futuramente registrar "fonte consultada" na conclusao da pane.

Recomendacao: nao fazer essa integracao no MVP do modulo de manuais. Primeiro entregar busca/viewer isolados.

### Inspecoes

Integracao natural:

- vincular tarefas de inspeção a procedimentos do manual;
- abrir manual em nova aba a partir de uma tarefa;
- incluir referencias no PDF de ordem/checklist.

Recomendacao: implementar apenas depois de estabilizar o catalogo e garantir URLs persistentes.

### Vencimentos e equipamentos

Integracao possivel:

- vincular part number, ATA, equipamento ou controle de vencimento a documentos tecnicos;
- usar a busca por PN/SN/ATA para consulta rapida.

Recomendacao: fase posterior, apos consolidar metadados e taxonomia.

### Dashboard

Integracao simples:

- status do indice;
- quantidade de manuais/documentos/paginas;
- ultima reindexacao;
- documentos sem texto.

Recomendacao: adicionar apenas apos o MVP do modulo.

## 10. Riscos principais

| Risco | Impacto | Mitigacao |
|---|---|---|
| Colisao do diretorio `data/` | Pode misturar banco/volume com acervo de manuais | Usar `var/manuais/acervo` e configuracao propria |
| Acervo tecnico exposto publicamente | Vazamento de documentacao sensivel | Exigir login em todas as rotas e nao expor `/data/*` aberto |
| Indexacao pesada travar SQLite principal | Degradacao de panes/inspecoes | Usar `catalog.db` separado no MVP |
| PyMuPDF bloqueando event loop | Lentidao geral | Rodar extracao em thread/processo de background |
| PDFs corrompidos ou sem texto | Falha de lote ou busca incompleta | Implementar E-01/E-02 da especificacao desde o inicio |
| Query FTS malformada | 500 ou comportamento inesperado | Sanitizar query conforme RN-10 e cobrir com testes |
| Viewer sem range request eficiente | PDFs grandes ruins no mobile | Validar PDF.js e estrategia de servir arquivos antes de producao |
| Encoding legado | Titulos quebrados | Função unica `read_text_legacy()` com UTF-8 e cp1252 |
| Duplicidade entre `docs/fim` e acervo novo | Confusao de fonte da verdade | Definir acervo runtime unico e relatorio de migracao |
| RAG antes da busca lexical estar madura | Risco operacional e respostas indevidas | Manter RAG fora do MVP e exigir citacoes obrigatorias |

## 11. Decisoes em aberto antes da implementacao

1. **Fonte inicial do acervo:** usar apenas `docs/fim`, importar o acervo externo completo, ou fazer merge dos dois?
2. **Local definitivo do acervo:** confirmar `var/manuais/acervo` ou outro caminho operacional.
3. **Banco do indice:** confirmar `catalog.db` separado no MVP.
4. **Politica de acesso:** confirmar leitura para todos os usuarios autenticados e administracao apenas para ADMINISTRADOR.
5. **Publicacao de manuais:** no MVP sera apenas por copia no filesystem e reindexacao manual?
6. **Categorias oficiais:** resolver os rotulos dos `catid` 1-7 antes da navegacao final.
7. **Uso de Caddy/reverse proxy:** decidir se producao do SAA29 continuara com Uvicorn direto no container ou se passara a usar proxy para arquivos grandes.
8. **Sensibilidade dos dados:** confirmar se os manuais podem ficar no mesmo ambiente do SAA29 e, no futuro, se podem transitar por APIs externas para RAG.

## 12. Plano recomendado de incorporacao

### Fase 0 - Preparacao e saneamento do acervo

Objetivo: definir fonte da verdade e preparar dados sem alterar a aplicacao.

Entregas:

- Definir `MANUAIS_DATA_DIR`.
- Inventariar `docs/fim` e o acervo externo completo.
- Criar relatorio de merge/deduplicacao, conforme RN-08 da especificacao externa.
- Separar acervo runtime de documentacao versionada.
- Definir convencao de backup do acervo.

Gate de saida:

- Existe uma pasta unica de acervo de manuais.
- Existe relatorio de conflitos.
- Nenhum PDF operacional depende de `docs/` como runtime.

### Fase 1 - MVP isolado do modulo

Objetivo: entregar consulta, busca e viewer dentro do SAA29, sem integracoes profundas.

Entregas:

- Modulo `app/modules/manuais`.
- Configuracoes do diretorio de acervo e indice.
- Catalogo de manuais/documentos/capitulos.
- Indexacao incremental por pagina usando PyMuPDF.
- Busca FTS5 com pagina exata, snippet e filtros basicos.
- Paginas `/manuais`, `/manuais/search` e `/manuais/viewer`.
- Endpoint `/manuais/api/status`.
- Endpoint admin `/manuais/admin/reindex`.
- Menu no `base.html`.
- Testes unitarios dos parsers, indexador, sanitizacao de busca e casos de borda principais.

Gate de saida:

- Usuario autenticado consulta o acervo.
- Busca abre PDF na pagina correta.
- PDF sem texto nao derruba indexacao.
- Query malformada nao retorna 500.

### Fase 2 - Operacao e hardening

Objetivo: tornar o modulo operavel no dia a dia.

Entregas:

- Logs de indexacao claros.
- Lock para impedir duas reindexacoes simultaneas.
- Status de progresso.
- Backup documentado do acervo e do indice.
- Validacao com acervo completo.
- Testes de desempenho basicos.
- Documentacao operacional integrada a `docs/guides` ou `docs/architecture`.

Gate de saida:

- Reindexacao completa e incremental testadas.
- Uso normal do SAA29 nao degrada durante indexacao.
- Administrador sabe publicar manual novo e diagnosticar falhas.

### Fase 3 - Integracoes com SAA29

Objetivo: transformar o modulo em ferramenta operacional conectada ao fluxo de manutencao.

Possiveis entregas:

- Campo de referencia tecnica em panes.
- Sugestoes de documentos FIM a partir de sistema ATA ou descricao.
- Links de manuais em tarefas de inspeção.
- Referencias tecnicas em PDFs de ordem/checklist.
- Indicadores do modulo no dashboard.

Gate de saida:

- As referencias sao estaveis e auditaveis.
- A integracao nao cria dependencia circular entre modulos.

### Fase 4 - RAG / busca semantica

Objetivo: evoluir com IA apenas depois de busca lexical e citacoes estarem confiaveis.

Pre-requisitos:

- MVP/v1.0 estavel.
- Golden set de perguntas reais.
- Decisao formal sobre envio de texto de manuais a API externa.
- Politica de custo e acesso.

Regras:

- Respostas sempre com citacao de manual/capitulo/pagina.
- Sem resposta quando nao houver fonte recuperada.
- LLM como localizador/assistente de consulta, nao como fonte normativa.

## 13. Criterios de aceite propostos para o modulo no SAA29

1. Dado um usuario autenticado, quando acessa `/manuais`, entao visualiza manuais agrupados por categoria ou estado vazio amigavel.
2. Dado o acervo indexado, quando pesquisa termo tecnico, entao recebe resultados com manual, capitulo, documento, pagina e snippet.
3. Dado um resultado de busca, quando clica nele, entao o viewer abre o PDF na pagina indicada.
4. Dado um PDF corrompido, quando a indexacao roda, entao o erro e logado e o lote continua.
5. Dado um PDF sem texto, quando a indexacao roda, entao o documento aparece na navegacao, mas nao participa da busca full-text.
6. Dado um usuario sem login, quando tenta acessar qualquer rota de manuais, entao e redirecionado para login ou recebe 401 JSON conforme o tipo de rota.
7. Dado um usuario nao administrador, quando tenta disparar reindexacao, entao recebe 403.
8. Dado o SAA29 em operacao, quando a reindexacao roda, entao os modulos de panes, inspeções e vencimentos continuam respondendo normalmente.

## 14. Itens que nao devem ser feitos na primeira implementacao

- Nao criar uma segunda aplicacao FastAPI dentro do repositorio.
- Nao substituir o `/dashboard` pela home de manuais.
- Nao usar `data/` como pasta de acervo no SAA29.
- Nao expor PDFs tecnicos por rota publica sem autenticacao.
- Nao introduzir Postgres, Elasticsearch, Redis, Qdrant ou outro servico externo para o MVP.
- Nao implementar RAG antes da busca lexical, viewer e citacoes estarem maduros.
- Nao migrar favoritos/comentarios do legado antes de validar o fluxo basico.
- Nao acoplar diretamente `panes`, `inspecoes` e `manuais` em uma primeira entrega.

## 15. Parecer final

O projeto externo tem maturidade documental suficiente para ser incorporado, mas o plano original deve ser **reinterpretado como especificacao funcional de um modulo SAA29**, nao seguido literalmente como scaffolding de novo repositorio.

A melhor estrategia e:

1. preservar a ideia central do projeto externo: acervo copiavel, indexacao incremental, FTS5 por pagina e viewer com pagina exata;
2. descartar as decisoes que conflitam com o SAA29: home em `/`, pasta `data/`, auth em aberto, deploy autonomo e UI independente;
3. isolar o indice tecnico em `var/manuais/index/catalog.db` no MVP;
4. proteger todo acesso via autenticacao/RBAC do SAA29;
5. entregar primeiro um modulo read-only robusto;
6. so depois integrar com panes, inspecoes, dashboard e RAG.

Com essas adaptacoes, o modulo de manuais tende a aumentar significativamente o valor operacional do SAA29, principalmente para consulta rapida de FIM/AMM/AIPC durante investigacao de panes, execucao de inspeções e tomada de decisao tecnica.
