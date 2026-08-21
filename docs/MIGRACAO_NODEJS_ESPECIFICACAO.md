# Especificação Técnica de Migração: SAA29 (Python → Node.js)

> **Documento de Handoff Técnico para Equipe de Desenvolvimento**
> **Sistema:** SAA29 – Sistema de Gestão de Panes e Manutenção Aeronáutica (A-29 Super Tucano)
> **Versão:** 2.0
> **Data de Emissão:** 21/08/2026 (substitui a v1.0 de 13/08/2026)
> **Objetivo:** Guiar a migração do SAA29 para Node.js, viabilizando hospedagem
> compartilhada (custo muito inferior ao de uma VPS). O caminho é incremental:
> **MVP de Panes → núcleo do produto (panes, inspeções, vencimentos) → extras opcionais**.
> O núcleo são 12.268 das 20.044 linhas a portar e entrega 100% do que o sistema se
> propõe a fazer; `publicacoes` e os demais módulos são qualidade de vida e podem ficar
> fora do escopo (§2.4).

---

## 0. O que mudou da v1.0 para a v2.0

A v1.0 foi escrita a partir de uma leitura de alto nível do repositório. A v2.0 foi
escrita depois de **conferir cada afirmação contra o código e contra o banco local**
(`saa29_local.db`, 21/08/2026). Vinte afirmações foram corrigidas; três delas eram
bloqueantes. Uma (E-02, o plano de hospedagem) foi verificada e **confirmada como
correta** na v1.0.

Além da errata, a v2.0 muda a **estrutura** do plano: a v1.0 propunha migrar o sistema
inteiro em 5 fases. A v2.0 recorta um **MVP de módulo único (Panes)** como Etapa 1,
porque o levantamento mostrou que o módulo de Publicações — sozinho — consome 3,5 GB
de acervo e 295 MB de índice, o que inviabiliza qualquer plano de hospedagem
compartilhada se for tratado como parte do mesmo pacote.

### 0.1. Errata da v1.0

| # | Afirmação da v1.0 | Realidade verificada | Severidade |
| :-- | :--- | :--- | :--- |
| **E-01** | *"O módulo de autenticação Node.js DEVE utilizar o pacote `bcrypt` ou `bcryptjs` nativo para garantir que usuários existentes continuem logando"* | **Falso.** O hash gravado não é `bcrypt(senha)`, é `bcrypt(base64(sha256(senha)))` — ver `app/modules/auth/security.py:24-38` (`_preparar_senha`). Um `bcrypt.compare(senha, hash)` direto **falha para 100% dos usuários**. | 🔴 **Bloqueante** |
| **E-02** | *"tier Unlimited da Hostinger"* como alvo de hospedagem | ✅ **Confirmado — a v1.0 estava certa.** O plano **Unlimited** do portfólio brasileiro lista Node.js entre os recursos ("Crie com: AI Builder / WordPress / **Node.js**"), com 50 GB NVMe e CDN incluso. É o mesmo tier que o portfólio internacional chama de *Business* (3 GB RAM, 2 vCPU, 50 GB). Confirmar RAM e vCPU em hPanel → Resources Usage. | ✅ Verificado |
| **E-03** | *"11 módulos bem definidos em `app/modules/`"* | São **12**. A v1.0 omitiu `dashboard/` (2 rotas: `/dashboard/resumo`, `/dashboard/frota`). | 🟠 Escopo |
| **E-04** | *"~1,3 MB de banco SQLite pré-populado"* | `saa29_local.db` = **7,4 MB**. Além dele: `var/publicacoes/catalog.19maio26.db` = **295 MB** (índice de busca), `catalog.2026.db` = 155 MB, e o acervo de PDFs = **3,5 GB em 40.178 arquivos**. | 🔴 **Bloqueante (premissa)** |
| **E-05** | *"Perfis: Administrador, Encarregado, Mantenedor/Técnico e **Leitor**"* | Os papéis reais são `MANTENEDOR`, `INSPETOR`, `ENCARREGADO`, `ADMINISTRADOR` (`app/modules/auth/roles.py`). **Não existe "Leitor"**; existe `INSPETOR`, que a v1.0 não menciona. | 🟠 RBAC |
| **E-06** | `panes (id, aeronave_id, ata_id, descricao_pane, acao_corretiva, status, data_abertura, …)` | Colunas reais: `id, aeronave_id, status, sistema_ata_id, descricao, data_abertura, data_conclusao, observacao_conclusao, comentarios, ativo, criado_por_id, concluido_por_id, created_at, updated_at`. Nenhuma coluna `ata_id`, `descricao_pane` ou `acao_corretiva` existe. | 🟠 Schema |
| **E-07** | `anexos (id, pane_id, caminho_arquivo, tipo_mime, data_upload)` | Reais: `id, pane_id, caminho_arquivo, tipo, created_at` — onde `tipo` é `IMAGEM`/`DOCUMENTO`, não um MIME. | 🟠 Schema |
| **E-08** | `usuarios (id, nome, email, senha_hash, perfil, ativo, …)` | Reais: `id, nome, posto, especialidade, funcao, ramal, trigrama, username, senha_hash, ativo, failed_login_attempts, locked_until, created_at, updated_at`. **Não há coluna `email`**; o login é por `username` e o papel está em `funcao`. | 🟠 Schema |
| **E-09** | *"O Prisma pode fazer `db pull` no banco existente sem alterar colunas ou dados"* | Verdadeiro **estruturalmente**, falso **semanticamente**. UUIDs são `CHAR(32)` hex **sem hífen**; `DATETIME` é TEXT `'YYYY-MM-DD HH:MM:SS'` (naive, sem timezone); `BOOLEAN` é INTEGER 0/1. O conector SQLite do Prisma grava `DateTime` como inteiro de milissegundos — misturar os dois formatos na mesma coluna corrompe datas em silêncio. Ver §6. | 🔴 **Alto** |
| **E-10** | *"Zero alteração no banco físico"* | O app abre o SQLite com `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` e `busy_timeout=15000` (`app/bootstrap/database.py:47-64`). WAL exige disco **local** com trava de arquivo confiável — premissa a validar no host antes de qualquer coisa (Fase 0). | 🟠 Infra |
| **E-11** | Tabela de stack lista 9 dependências | Faltam: `slowapi` (rate limiting), `fastapi-csrf-protect` (CSRF), `Pillow` + `pillow-heif` + `imgdiet` (pipeline HEIC→WebP de anexos), `openpyxl` (export XLSX), `reportlab` (PDF), `boto3` (Cloudflare R2). Cada uma precisa de equivalente Node — ver §5. | 🟠 Estimativa |
| **E-12** | *"`file-type` é JS puro (elimina dependência de C/libmagic no SO)"* | Correto para *sniffing* de MIME, mas **não substitui `pillow-heif`**. A allowlist de upload aceita `image/heic` e `image/heif` (`app/shared/core/file_validators.py:18-24`) — foto de iPhone. O `sharp` **pré-compilado não decodifica HEIC** (licença libheif/x265); habilitar exige compilar libvips do zero, o que hospedagem compartilhada não permite. Ver §5.3. | 🔴 **Alto** |
| **E-13** | *"Fase 1: Setup & Introspecção do Banco"* | O roteiro começa escrevendo código antes de provar que o host aguenta. Falta uma **Fase 0 de spike de viabilidade** no ambiente real. Ver §10. | 🟠 Processo |
| **E-14** | Não menciona processos de background | `app/bootstrap/tasks.py` mantém **3 loops `asyncio` infinitos** (limpeza de tokens 1h, anexos travados 15min, processamento noturno 15min) e dispara **subprocessos** via `asyncio.create_subprocess_exec` (backup R2 e worker de PDF). Nada disso sobrevive a um processo que a hospedagem pode reiniciar ou suspender a qualquer momento. Ver §3.1. | 🔴 **Bloqueante** |
| **E-15** | *"~95% dos HTMLs e arquivos JavaScript estáticos de `static/js/` poderão ser reutilizados sem alteração"* | Mistura duas coisas de risco muito diferente. **JS estático: ~100% reutilizável** (é vanilla e fala só com a API por `fetch`). **Templates: alto reaproveitamento, mas não automático** — 26 `extends`, 82 `block`, 25 `if`, 4 `for`, 2 `include`; Nunjucks cobre tudo isso **exceto** os filtros `\|min` e `\|max` (existem no Jinja2, não no Nunjucks). Ponto a favor não citado na v1.0: **`url_for` aparece 0 vezes** nos templates — todas as URLs são literais, o que elimina a maior fonte de atrito Jinja→Nunjucks. | 🟡 Expectativa |
| **E-16** | *"templates em `app/templates/`, JS em `static/js/`"* | Caminhos reais: **`app/web/templates/`** e **`app/web/static/js/`**. A pasta `static/` da raiz está **vazia** e `templates/` da raiz contém só um resíduo. Seguir a v1.0 ao pé da letra aponta o Nunjucks para diretórios errados. | 🟡 Setup |
| **E-17** | *"Os anexos e fotos de panes ficam gravados no diretório `uploads/`"* | O diretório configurado é **`var/uploads`** (`upload_dir`). A pasta `uploads/` da raiz é legado. Além disso, `storage_backend` já suporta `local \| r2`: a integração com R2 **já existe** (`app/shared/core/storage.py`), não é algo "a integrar". | 🟡 Setup |
| **E-18** | Não trata proxy reverso / TLS terminado fora do app | Em hospedagem compartilhada o Node fica **atrás de um proxy**. Sem `trust proxy`, o rate limiting por IP passa a contar todo mundo como o mesmo cliente e os cookies `Secure` ficam incoerentes. Ver §12.4. | 🟠 Segurança |
| **E-19** | *"Leitura de PDF: `pdf-parse` ou `pdfjs-dist`"* | Só relevante para Publicações — **fora do MVP**. Quando chegar a vez: `pdf-parse` está sem manutenção ativa; usar `pdfjs-dist` (build *legacy*, Node) para extração página a página. | 🟢 Baixo |
| **E-20** | Não menciona a interface móvel | Existe um **frontend mobile separado**: `app/web/pages/mobile_router.py` (7 rotas), `app/web/templates/mobile/` (7 templates), `app/web/static/js/mobile/`, mais PWA (`static/sw.js`, `static/manifest.json`). Escopo adicional não contabilizado. | 🟠 Escopo |
| **E-21** | Não menciona a suíte de testes nem o Alembic | Existem **720 testes** em 61 arquivos e **41 migrações Alembic**. A suíte é o principal ativo de paridade da migração (§11); as migrações precisam de decisão explícita de destino (§6.6). | 🟠 Processo |

### 0.2. O que a v1.0 acertou (mantido sem alteração)

- **176 rotas HTTP** — conferido: 148 nos módulos de domínio + 28 nas páginas.
- **38 tabelas de negócio + `alembic_version`** — conferido: 39 tabelas, 0 views.
- Contagens de dados: 22 aeronaves, 26 modelos de equipamento, 33 slots, 726 itens,
  726 instalações, 39 templates de tarefa, 16 tipos de inspeção, 66 controles de
  vencimento — todas conferidas no banco.
- A escolha de **Nunjucks** como motor de template — a análise de E-15 confirma que
  é a decisão certa, pelas razões certas.
- A escolha de **Express** sobre Fastify, por compatibilidade com o *wrapper* de
  hospedagem compartilhada.

---

## 1. Premissa de hospedagem: leia antes de tudo

O objetivo declarado é sair de VPS para uma hospedagem simples com suporte a Node.js.
Isso é viável — **mas não no plano citado na v1.0**, e não com o sistema inteiro.

### 1.1. O plano atende — com ressalvas de custo, não de recurso

O plano **Unlimited** (portfólio brasileiro) lista Node.js entre os recursos, junto com
50 GB de armazenamento NVMe, CDN e backups diários. É o mesmo tier que o portfólio
internacional chama de *Business*. Versões de Node suportadas: **18.x, 20.x, 22.x, 24.x**.

| Plano | RAM | vCPU | Armazenamento | Node.js |
| :--- | :--- | :--- | :--- | :--- |
| Premium | 2 GB | 1 | 20 GB | ❌ |
| **Unlimited (BR) / Business (intl.)** | **3 GB** | **2** | **50 GB** | ✅ |
| Cloud Startup | 4 GB | 4 | 100 GB | ✅ |

**A ressalva é econômica, não técnica.** O preço promocional (R$ 13,99/mês em contrato
de 48 meses, R$ 671,52 no total) **renova a R$ 64,99/mês** — acima da renovação do VPS
KVM 1 (R$ 59,99/mês). A economia existe apenas dentro da janela promocional de 4 anos
(entre R$ 770 e R$ 1.490 no período) e **se inverte depois dela**.

> **Ação (dono do projeto):** confirmar RAM, vCPU, limite de *inodes* e de processos
> simultâneos em **hPanel → Websites → Dashboard → Hosting plan → Resources Usage** antes
> da Fase 0 — esses números não constam da página comercial. Um `node_modules` típico já
> consome dezenas de milhares de arquivos, além dos 40.178 do acervo.

### 1.2. Com o núcleo do produto, o plano sobra

O núcleo do SAA29 é **panes, inspeções e vencimentos** (§2.4). Publicações é extra e
**pode ficar fora do escopo da migração**. Isso muda completamente o dimensionamento:

| Ativo | Tamanho | Arquivos | No núcleo? | Cabe? |
| :--- | ---: | ---: | :--- | :--- |
| `saa29_local.db` (dados de negócio) | 7,1 MB | 1 | ✅ Sim | ✅ |
| `var/uploads` (anexos de panes) | 1,3 MB | ~1.400 | ✅ Sim | ✅ |
| **Subtotal do núcleo** | **8,4 MB** | ~1.400 | | **0,02% dos 50 GB** |
| `var/publicacoes/acervo` (PDFs) | 3,5 GB | 40.178 | 🟢 Extra | ⚠️ Cabe, mas pressiona *inodes* |
| `var/publicacoes/catalog.*.db` (índices) | 450 MB | 3 | 🟢 Extra | ✅ Somente-leitura |
| Indexação de PDF (13.077 docs) | — | — | 🟢 Extra | ❌ CPU longa + subprocessos |
| Jobs de upload de edição | — | — | 🟢 Extra | ❌ Depende de processo vivo e PID |

**8,4 MB.** O plano oferece 50 GB. Sem Publicações, não há sequer discussão de
dimensionamento — e cada um dos problemas de infraestrutura marcados com ❌ neste
documento pertence exclusivamente ao módulo de Publicações.

Se Publicações for retomado depois, ele é migrável em modo leitura, movendo a indexação
para um procedimento offline (§15.3). Mas isso é uma decisão separada, para depois, e
não condiciona nada do que vem antes.

### 1.3. Portabilidade deliberada

A especificação evita amarrar a arquitetura à Hostinger. Todas as decisões abaixo
valem igualmente para qualquer hospedagem da mesma classe (cPanel + Passenger, LiteSpeed,
ou PaaS de baixo custo). O critério é: **nada pode depender de o processo estar sempre
vivo, nem de compilar código nativo no servidor.**

---

## 2. Retrato verificado do sistema atual

### 2.1. Números

| Métrica | Valor |
| :--- | :--- |
| Linguagem / framework | Python 3.12 · FastAPI 0.115.6 (Uvicorn/Gunicorn) |
| Módulos de domínio | **12** (`app/modules/`) |
| Rotas HTTP | **176** (148 API + 28 páginas HTML) |
| Tabelas de negócio | **38** (+ `alembic_version`) |
| Migrações Alembic | **41** (revisão atual: `2676d7fdd987`) |
| Testes automatizados | **720** em 61 arquivos |
| Templates Jinja2 | 26 (14 desktop + 7 mobile + parciais) |
| JS estático | 28 arquivos (fora o PDF.js vendorizado) |
| Papéis (RBAC) | `MANTENEDOR`, `INSPETOR`, `ENCARREGADO`, `ADMINISTRADOR` |

### 2.2. Rotas por módulo

| Módulo | Rotas | No MVP? |
| :--- | ---: | :--- |
| `publicacoes` | 33 | ❌ Fase 3+ |
| `inspecoes` | 26 | ❌ Fase 2 |
| `equipamentos` | 17 | ❌ Fase 2 |
| **`panes`** | **14** | ✅ **MVP** |
| `vencimentos` | 12 | ❌ Fase 2 |
| **`auth`** | **11** | ✅ **MVP** |
| `pedidos` | 10 | ❌ Fase 2 |
| `calendario` | 8 | ❌ Fase 2 |
| **`aeronaves`** | **5** | ✅ **MVP** |
| `efetivo` | 4 | ❌ Fase 2 |
| `encarregado` | 3 | ❌ Fase 2 |
| `dashboard` | 2 | ⚠️ Opcional no MVP (§4.6) |
| Páginas (`app/web/pages/`) | 21 desktop + 7 mobile | ✅ 5 delas no MVP |

### 2.3. Estrutura real de pastas

```
app/
├── bootstrap/          # Factory FastAPI, config, lifespan, tarefas de background, seed
│   ├── main.py         # create_app(): middlewares, routers, static mount
│   ├── config/         # pydantic-settings (Settings) + config de imagem
│   ├── database.py     # engine async + PRAGMAs SQLite
│   ├── events.py       # lifespan: cria dirs, registra backup R2, sobe 3 tasks
│   └── tasks.py        # loops infinitos + subprocessos  ← ver §3.1
├── modules/            # 12 módulos: router.py / service.py / models.py / schemas.py
├── shared/
│   ├── core/           # enums, exceptions, file_validators, limiter, storage
│   ├── middleware/     # csrf.py, security.py
│   ├── services/image/ # converter.py (HEIC → JPG/PNG via pillow-heif)
│   └── exporter.py     # CSV/XLSX com neutralização de fórmula (anti CSV-injection)
└── web/
    ├── pages/          # router.py (desktop) + mobile_router.py
    ├── templates/      # Jinja2 (desktop, mobile/, panes/, inspecoes/, publicacoes/)
    └── static/         # css/, js/, js/mobile/, js/pdfjs/, sw.js, manifest.json
```

### 2.4. Núcleo do produto × extras

**Definição do dono do projeto:** o SAA29 existe para controlar **panes, inspeções e
vencimentos**. Todo o resto foi adição de qualidade de vida e **não é fundamental** —
pode ficar para segundo plano ou nunca entrar no escopo da migração.

Essa distinção reordena o projeto inteiro e é a razão de a §1.2 ter sido reescrita.

O grafo de dependências (medido pelos imports reais entre módulos) determina o que o
núcleo obrigatoriamente arrasta junto:

```
        auth ──────────┐
                       ▼
    aeronaves ◄────► inspecoes ◄──── panes
        ▲              │  ▲            │
        │              │  └────────────┘
        └──────────────┼──────────┐
                       ▼          ▼
             equipamentos ◄──► vencimentos
                        (ciclo mútuo)
```

- `panes` → `aeronaves`, `auth`, `inspecoes`
- `inspecoes` → `aeronaves`, `auth`, **`equipamentos`**, `panes`, **`vencimentos`**
- `vencimentos` → `aeronaves`, `auth`, **`equipamentos`**
- `equipamentos` → `aeronaves`, `auth`, **`vencimentos`** ← ciclo
- `aeronaves` → `inspecoes` (`STATUS_ATIVOS`)

⚠️ **`equipamentos` e `vencimentos` têm dependência mútua** (`equipamentos` importa
`vencimentos.service.criar_controles_para_item`; `vencimentos` importa quatro modelos de
`equipamentos`). **Não podem ser migrados em sequência — são uma unidade.**

Logo, `equipamentos` e `aeronaves` entram no núcleo por arrasto, não por escolha:

| | Módulos | LOC | Rotas |
| :--- | :--- | ---: | ---: |
| 🔴 **Núcleo** | `auth`, `aeronaves`, `equipamentos`, `panes`, `inspecoes`, `vencimentos` + infra | **12.268** | **85** |
| 🟢 **Extras** | `publicacoes` (4.780), `pedidos` (808), `calendario` (762), `encarregado` (636), `dashboard` (608), `efetivo` (182) + PWA mobile | **7.776** | **61** |
| | **Total** | **20.044** | **146** |

**O núcleo é 61% do código e entrega 100% do produto.** `publicacoes` sozinho é 24% da
superfície de migração — e é a origem de praticamente todos os problemas de
infraestrutura levantados no §3.

> Um item do núcleo que a v1.0 e as primeiras versões da v2.0 subestimaram:
> `inspecoes/pdf_service.py` são **892 LOC de geração de relatório em PDF** com
> `reportlab`. Não é extra — é parte do fluxo de inspeção, e o equivalente Node
> (`pdfkit`) entra no núcleo (§5.1).

### 2.5. Superfície real de migração (LOC)

O dado mais importante para estimativa, e o que mais separa este projeto de uma
reescrita: **metade do código não precisa ser escrita.**

| Categoria | LOC | Esforço |
| :--- | ---: | :--- |
| Módulos de domínio (12) | 16.930 | 🔴 Portar |
| Infra (`shared/` + `bootstrap/` + `web/pages/`) | 3.114 | 🔴 Portar |
| **Subtotal a portar** | **20.044** | |
| JavaScript estático (fora o PDF.js vendorizado) | 12.293 | ✅ Reaproveitado sem alteração |
| Templates HTML | 5.443 | ✅ Reaproveitado (só filtros `min`/`max` — E-15) |
| CSS | 2.604 | ✅ Reaproveitado sem alteração |
| **Subtotal reaproveitado** | **20.340** | |

Por módulo, em ordem de custo:

| Módulo | LOC | Rotas | | Módulo | LOC | Rotas |
| :--- | ---: | ---: | :-- | :--- | ---: | ---: |
| `publicacoes` | 4.780 | 34 | | `pedidos` | 808 | 10 |
| `inspecoes` | 2.589 | 26 | | `calendario` | 762 | 8 |
| **`panes`** | **1.858** | **14** | | `encarregado` | 636 | 3 |
| `equipamentos` | 1.732 | 17 | | `dashboard` | 608 | 2 |
| **`auth`** | **1.367** | **11** | | **`aeronaves`** | **493** | **5** |
| `vencimentos` | 1.115 | 12 | | `efetivo` | 182 | 4 |

Em negrito, o escopo do MVP: **6.832 LOC contando a infra — 34% da superfície de
migração.**

---

## 3. Incompatibilidades entre a arquitetura atual e hospedagem compartilhada

Esta seção não existia na v1.0 e é a razão de o MVP ser recortado como está.

### 3.1. 🔴 Processos de background e subprocessos (E-14)

O que o sistema faz hoje, em `app/bootstrap/events.py` e `app/bootstrap/tasks.py`:

| Mecanismo | O que faz | Por que quebra |
| :--- | :--- | :--- |
| `token_cleanup_task()` | `while True` a cada 1h: apaga tokens expirados | Se o processo dorme/reinicia, nunca roda |
| `anexos_travados_cleanup_task()` | `while True` a cada 15min: marca anexos presos em `processando` como ERRO | Idem — e este é o *safety net* que impede a UI de travar |
| `processamento_noturno_task()` | `while True` a cada 15min: dispara jobs de PDF na hora configurada | Idem |
| `sa_event.listen(Session, "after_commit", mark_db_dirty)` + debounce de 120 s | Backup do SQLite para o R2 depois da última escrita | O debounce depende de o processo continuar vivo por 2 minutos após o commit |
| `asyncio.create_subprocess_exec(sys.executable, "scripts/…/r2_manager.py")` | Backup R2 | Hospedagem compartilhada normalmente proíbe/limita processos filhos |
| `service.disparar_worker_processamento()` | Worker de indexação de PDF | Idem, e é longo demais |
| `recuperar_jobs_upload_interrompidos()` no startup | Marca jobs órfãos como FALHOU | Depende de `processo_esta_ativo(pid)`, que não faz sentido fora de um host dedicado |

**Regra da v2.0:** *nenhum comportamento correto do sistema pode depender de um timer
em processo.* Todo trabalho periódico vira uma **rota HTTP idempotente e autenticada
por segredo**, acionada por **cron do painel** (`curl -fsS -H "X-Cron-Key: …" https://…/internal/cron/<job>`).
Se o cron falhar, o próximo tick corrige — nunca há estado só na memória.

No MVP isso reduz a exatamente **dois** jobs:

| Job | Rota | Frequência sugerida |
| :--- | :--- | :--- |
| Limpeza de tokens expirados | `POST /internal/cron/limpar-tokens` | 1×/hora |
| Anexos presos em `processando` > 30 min | `POST /internal/cron/anexos-travados` | 4×/hora |

### 3.2. 🔴 Processamento de imagem HEIC (E-12)

O upload de anexo aceita `image/heic` e `image/heif` — é o formato padrão de foto do
iPhone, e o caso de uso é literalmente "mantenedor fotografa a pane no hangar". Hoje o
pipeline é `pillow-heif` (decode) → `imgdiet` (compressão WebP com PSNR alvo 40) →
grava `.webp`.

Em Node, `sharp` é o equivalente natural de `Pillow` — **mas os binários pré-compilados
do `sharp` não decodificam HEIC**, por causa da licença da libheif/x265. Habilitar
exige compilar libvips com libheif/libde265/x265 no servidor, o que hospedagem
compartilhada não permite. Opções, em ordem de preferência para o MVP:

1. **Converter no cliente (recomendado).** O navegador/PWA converte HEIC→JPEG antes do
   upload (WASM, ex.: `heic2any`, ou `canvas` quando o Safari já decodifica nativamente).
   O servidor passa a aceitar só `image/jpeg`, `image/png` e `application/pdf`.
   Vantagem extra: economiza banda e CPU do plano compartilhado.
2. **Decodificar em WASM no servidor** (`libheif-js`). Funciona sem compilação nativa,
   mas custa CPU e memória — recurso escasso no plano.
3. **Rejeitar HEIC com mensagem clara.** Aceitável só como paliativo, porque degrada o
   fluxo principal do usuário de campo.

> **Decisão pendente do dono do produto.** A recomendação é a opção 1, com a opção 3
> como fallback de erro (mensagem "converta a foto para JPEG"), nunca como
> comportamento padrão.

### 3.3. 🟠 SQLite em disco compartilhado (E-10)

O app usa `journal_mode=WAL`. WAL depende de memória compartilhada entre processos
(`-shm`) e de trava de arquivo POSIX confiável — garantido em disco local, **não**
garantido em armazenamento de rede. Além disso, se o *wrapper* de hospedagem subir
mais de um processo Node, dois processos passam a escrever no mesmo arquivo.

Mitigação no MVP:

- Rodar **um processo único** (sem `cluster`). O volume do sistema (dezenas de usuários,
  10 panes registradas) não justifica paralelismo.
- Manter `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=15000`,
  `synchronous=NORMAL` — **paridade exata com o Python** (`app/bootstrap/database.py`).
- **Fase 0 valida isso empiricamente** antes de qualquer código de negócio (§10).
- Fallback caso WAL se mostre instável no host: `journal_mode=DELETE` (mais lento,
  aceitável neste volume) ou migração para MySQL, que o plano já inclui (§6.7).

### 3.4. 🟠 Rate limiting e IP do cliente (E-18)

`slowapi` hoje guarda contadores **em memória** — `5/minute` no login, `20/minute` no
refresh, `10/minute` no export de panes. Dois efeitos em hospedagem compartilhada:

- O contador zera a cada reinício do processo, enfraquecendo a proteção de login.
- Sem `app.set('trust proxy', 1)`, todo request chega com o IP do proxy e **um único
  cliente abusivo derruba o acesso de todos**.

No MVP: `express-rate-limit` com `trust proxy` configurado, contadores em memória
(paridade com hoje) **mais** o bloqueio de conta em banco, que é o controle que
realmente importa e já é persistente: 5 tentativas → `locked_until` = agora + 15 min
(`app/modules/auth/service.py:26-89`).

### 3.5. Resumo da matriz

| Recurso atual | Status em hospedagem compartilhada | Ação |
| :--- | :--- | :--- |
| Loops `asyncio` de background | ❌ Não sobrevive | Vira cron HTTP (§3.1) |
| Subprocessos (`create_subprocess_exec`) | ❌ Restrito | Só existem em Publicações e no backup R2 — ambos saem (§3.1) |
| Indexação de PDF (13.077 docs) | ❌ CPU longa | 🟢 Extra — fora do escopo (§2.4) |
| Acervo de 3,5 GB / 40 mil arquivos | ⚠️ Inodes / uso justo | 🟢 Extra — fora do escopo (§2.4) |
| Geração de PDF de inspeção (`reportlab`, 892 LOC) | ✅ Sob demanda, curta | 🔴 Núcleo — `pdfkit` (§5.1) |
| `python-magic` / libmagic | ✅ Substituível | `file-type` (JS puro) |
| `pillow-heif` (HEIC) | ❌ Sem binário viável | Converter no cliente (§3.2) |
| `Pillow` / `imgdiet` (resize + WebP) | ✅ | `sharp` (binário pré-compilado, sem HEIC) |
| `openpyxl` (XLSX) | ✅ | `exceljs` |
| `reportlab` (PDF) | ✅ | Fora do MVP (`pdfkit` quando precisar) |
| `boto3` (R2) | ✅ | `@aws-sdk/client-s3` |
| SQLite + WAL | ⚠️ Validar | Fase 0 (§10) |
| Rate limit em memória | ⚠️ Degradado | `express-rate-limit` + lockout em banco |
| WebSocket / SSE | n/a | Não usado hoje — manter assim |

---

## 4. Etapa 1 — MVP do módulo Panes

### 4.1. Objetivo do MVP

Colocar em produção, na hospedagem compartilhada, uma versão do SAA29 que permita:

1. Login, logout e renovação de sessão com **as senhas que já existem no banco**.
2. Consultar, filtrar, exportar, abrir, editar e concluir **panes**.
3. Anexar e baixar fotos/PDFs de pane.
4. Atribuir responsáveis a uma pane.
5. Ver a frota (leitura) e o status operacional das aeronaves, sincronizado pelas panes.
6. Administrar usuários (criar, editar, trocar senha, desativar).

Tudo o mais fica fora. O MVP é a prova de que a plataforma serve — não uma entrega
parcial de todos os módulos.

### 4.2. Escopo fechado

**Dentro:**

| Área | Conteúdo |
| :--- | :--- |
| Módulos | `auth` (11 rotas), `aeronaves` (5 rotas), `panes` (14 rotas) |
| Páginas | `/login`, `/panes`, `/panes/{id}/detalhes`, `/frota`, `/` → redirect |
| Tabelas | `usuarios`, `token_refresh`, `token_blacklist`, `aeronaves`, `sistemas_ata`, `panes`, `anexos`, `pane_responsaveis` **+ `inspecoes` somente-leitura** (§4.4) |
| Segurança | JWT em cookie HttpOnly, refresh com rotação, CSRF *double submit*, cabeçalhos de segurança, lockout de conta, rate limit |
| Infra | Storage local ou R2, export CSV/XLSX, 2 jobs de cron HTTP |

**Fora (explicitamente):**

`equipamentos`, `vencimentos`, `inspecoes` (CRUD/UI), `publicacoes`, `pedidos`,
`efetivo`, `encarregado`, `calendario`, `dashboard` (opcional — §4.6), interface
mobile/PWA (§4.7), integração FIM na tela de pane (§4.6), export PDF.

### 4.3. Panes **não** é um módulo isolado — mapa de dependências

Este é o achado mais importante para o planejamento do MVP, e a v1.0 não o registra.

```
panes
 ├─ usuarios        (FK criado_por_id, concluido_por_id, pane_responsaveis.usuario_id)
 ├─ aeronaves       (FK aeronave_id — e ESCRITA: sincronizar_status_aeronave)
 ├─ sistemas_ata    (FK sistema_ata_id, nullable)
 ├─ anexos          (1:N, cascade)
 ├─ pane_responsaveis (1:N, cascade, unique (pane_id, usuario_id))
 ├─ storage         (LocalStorageService | R2StorageService)
 ├─ exporter        (CSV/XLSX com neutralização de fórmula)
 ├─ image pipeline  (HEIC→JPG, resize, WebP)  ← §3.2
 └─ inspecoes  ⚠️  LEITURA em sincronizar_status_aeronave
```

O frontend de panes (`panes_lista.js`, `panes_detalhe.js`) consome, além de `/panes/*`:
`/aeronaves/`, `/aeronaves/{id}`, `/auth/usuarios`, `/auth/refresh`, `/auth/logout` e —
opcionalmente — `/publicacoes/api/fim*`.

### 4.4. Decisão obrigatória: a dependência de `inspecoes`

`app/modules/panes/service.py:110-166` (`sincronizar_status_aeronave`) implementa a
regra de status da frota, com esta precedência:

1. Existe inspeção ativa → `INSPEÇÃO`
2. Senão, existe pane aberta → `INDISPONIVEL` (a menos que a aeronave esteja `INATIVA`/`ESTOCADA`)
3. Senão → `DISPONIVEL` (se estava `INDISPONIVEL`/`INSPEÇÃO`)

Ou seja: **o MVP de Panes escreve no status da aeronave lendo a tabela `inspecoes`.**

| Opção | Como | Consequência |
| :--- | :--- | :--- |
| **A — Incluir `inspecoes` como somente-leitura** ✅ **recomendada** | Mapear a tabela no schema Node, sem rota nem UI; a regra fica idêntica | +1 tabela, 0 rota, 0 tela. Regra preservada byte a byte |
| B — Remover o passo 1 da regra | Ignorar inspeções no MVP | 🔴 **Bug de dados.** Aeronave em inspeção com pane resolvida volta para `DISPONIVEL` indevidamente. Inaceitável se o MVP escrever no banco de produção |
| C — MVP em banco separado, sem histórico | Piloto isolado | Só válido se não houver intenção de reconciliar dados depois. Descarta o "zero data loss" |

> **Decisão v2.0: opção A.** O MVP mapeia `inspecoes` (colunas `id`, `aeronave_id`,
> `status`) exclusivamente para a consulta `EXISTS` da regra. `STATUS_ATIVOS` deve ser
> copiado de `app/modules/inspecoes/service.py` — não reinventado.

### 4.5. Inventário de rotas do MVP (30 API + 5 páginas)

**Autenticação — `/auth` (11)**

| Método | Rota | Papel exigido | Observações |
| :--- | :--- | :--- | :--- |
| POST | `/auth/login` | público | `5/minute`; form-data; seta `saa29_token` e `saa29_refresh_token` |
| POST | `/auth/refresh` | cookie de refresh | `20/minute`; rotaciona o refresh |
| POST | `/auth/logout` | autenticado | Revoga refresh + blacklist do access; apaga cookies |
| GET | `/auth/me` | autenticado | Usado pelo shell do frontend |
| GET | `/auth/usuarios` | autenticado | Popula o seletor de responsáveis |
| POST | `/auth/usuarios` | ADMINISTRADOR | |
| PUT | `/auth/usuarios/senha` | autenticado | Própria senha |
| PUT | `/auth/usuarios/{id}/senha` | ADMINISTRADOR | `5/minute` |
| PUT | `/auth/usuarios/{id}` | ADMINISTRADOR | |
| DELETE | `/auth/usuarios/{id}` | ADMINISTRADOR | Soft delete (`ativo=false`) |
| POST | `/auth/usuarios/{id}/restaurar` | ADMINISTRADOR | |

**Aeronaves — `/aeronaves` (5)**

| Método | Rota | Papel |
| :--- | :--- | :--- |
| GET | `/aeronaves/` | autenticado |
| POST | `/aeronaves/` | ADMINISTRADOR |
| GET | `/aeronaves/{id}` | autenticado |
| PUT | `/aeronaves/{id}` | ADMINISTRADOR |
| POST | `/aeronaves/{id}/toggle-status` | ENCARREGADO / ADMINISTRADOR |

**Panes — `/panes` (14)**

| Método | Rota | Papel | Observações |
| :--- | :--- | :--- | :--- |
| GET | `/panes/sistemas` | autenticado | Lookup de sistemas ATA |
| POST | `/panes/` | autenticado | Status inicial `ABERTA`; dispara `sincronizar_status_aeronave` |
| GET | `/panes/` | autenticado | Filtros: `texto`, `status`, `aeronave_id`, `data_inicio`, `data_fim`, `excluidas`, `skip`, `limit` |
| GET | `/panes/export` | autenticado | `10/minute`; CSV e XLSX |
| GET | `/panes/{id}` | autenticado | |
| PUT | `/panes/{id}` | ver RBAC | |
| POST | `/panes/{id}/concluir` | ExecucaoPermitida | Grava `concluido_por_id`, `data_conclusao`, ressincroniza aeronave |
| POST | `/panes/{id}/anexos` | MANTENEDOR, ENCARREGADO, INSPETOR, ADMINISTRADOR | Valida MIME por magic bytes; processamento assíncrono |
| GET | `/panes/{id}/anexos` | autenticado | |
| DELETE | `/panes/{id}/anexos/{anexo_id}` | ENCARREGADO / ADMINISTRADOR | Remove registro + arquivo |
| GET | `/panes/{id}/anexos/{anexo_id}/download` | autenticado | 409 se `processando`/`ERRO`; 302 para URL assinada no modo R2 |
| POST | `/panes/{id}/responsaveis` | ExecucaoPermitida | |
| DELETE | `/panes/{id}` | ver RBAC | Soft delete (`ativo=false`) |
| POST | `/panes/{id}/restaurar` | ver RBAC | |

**Páginas HTML (5)**

| Rota | Template | Observação |
| :--- | :--- | :--- |
| `GET /` | — | **Muda no MVP:** redireciona para `/panes`, não `/dashboard` |
| `GET /login` | `login.html` | |
| `GET /panes` | `panes/lista.html` | |
| `GET /panes/{id}/detalhes` | `panes/detalhe.html` | |
| `GET /frota` | `aeronaves.html` | Somente leitura no MVP |

**Cron interno (2)** — §3.1: `POST /internal/cron/limpar-tokens`,
`POST /internal/cron/anexos-travados`. Protegidas por header `X-Cron-Key`, comparado
com `crypto.timingSafeEqual`, e recusadas se `CRON_KEY` não estiver definida.

### 4.6. Recortes na UI do MVP

Três ajustes de frontend que precisam ser feitos de propósito, não descobertos em produção:

1. **`base.html` tem 10 links de navegação** (`/dashboard`, `/encarregado`, `/panes`,
   `/pedidos`, `/inspecoes`, `/inventario`, `/vencimentos`, `/calendario`, `/frota`,
   `/publicacoes`, `/configuracoes`). No MVP sobram **`/panes` e `/frota`**. Recomendação:
   controlar por uma variável de contexto (`modulos_ativos`) em vez de apagar o HTML,
   para que a Fase 2 seja reversível com uma linha de config.
2. **`panes_detalhe.js` chama `/publicacoes/api/fim/por-ata/{ata}` e `/publicacoes/api/fim?…`**
   (sugestão de procedimento FIM a partir do código ATA). Sem o módulo de Publicações,
   esse bloco precisa de *feature flag* e degradação silenciosa — não pode virar erro
   de console nem seção quebrada na tela.
3. **`/dashboard`** fica de fora por padrão. `dashboard/resumo` e `dashboard/frota`
   agregam dados de vencimentos e inspeções que não existem no MVP; incluí-los exigiria
   arrastar mais dois módulos.

### 4.7. Não-objetivos explícitos do MVP

- Interface mobile / PWA (`mobile_router.py`, `templates/mobile/`, `sw.js`,
  `manifest.json`). É um segundo frontend completo — merece etapa própria.
- Export em PDF (`reportlab`).
- Backup automático do SQLite para R2 (o MVP usa backup por cron, §12.5).
- Swagger/OpenAPI público (hoje só existe com `APP_DEBUG=true`).
- Qualquer alteração de regra de negócio. **Migração é tradução, não refatoração.**

---

## 5. Stack alvo revisada

### 5.1. Tabela corrigida

| Camada / Recurso | Stack atual (Python) | Alvo Node.js | Observação |
| :--- | :--- | :--- | :--- |
| Linguagem | Python 3.12 | **Node.js 20 LTS ou 22 LTS + TypeScript** | Fixar a versão no host antes de começar. Evitar 24.x até confirmar estabilidade dos binários pré-compilados |
| Framework web | FastAPI 0.115.6 | **Express 5** | Suporte universal em *wrappers* de hospedagem compartilhada |
| Template | Jinja2 3.1.5 | **Nunjucks** | Registrar filtros `min` e `max` manualmente (E-15). `url_for` não é usado |
| ORM / acesso a dados | SQLAlchemy 2.0 (async) | **Drizzle ORM + `better-sqlite3`** | Ver §5.2 — recomendação mudou em relação à v1.0 |
| Migrações | Alembic (41 revisões) | **Nenhuma no MVP** | O banco já existe; ver §6.6 |
| Banco | SQLite (WAL) | SQLite (mesmo arquivo) | Validar em Fase 0 (§3.3) |
| Validação | Pydantic 2.10 | **Zod** | Paridade de mensagens de erro é requisito (§7.3) |
| Config | pydantic-settings | **Zod + `dotenv`** | Falhar no boot se faltar variável obrigatória, como hoje |
| Senha | `passlib[bcrypt]` **+ pré-hash SHA-256** | **`bcryptjs` + pré-hash idêntico** | 🔴 Ver §6.1. Não é opcional |
| JWT | `python-jose` HS256 | **`jsonwebtoken`** | Mesmos claims: `sub`, `exp`, `iat`, `jti`, `type` |
| CSRF | `fastapi-csrf-protect` | **`csrf-csrf`** (double submit) | Cookie `fastapi-csrf-token`, header `X-CSRF-Token` — nomes **não podem mudar** (§7.2) |
| Rate limit | `slowapi` | **`express-rate-limit`** | Com `trust proxy` (§3.4) |
| Cabeçalhos de segurança | middleware próprio | **`helmet`** + ajustes | Copiar a CSP atual de `app/shared/middleware/security.py`, não inventar outra |
| Upload | `python-multipart` | **`multer`** (memória, com limite) | Limite de `MAX_UPLOAD_SIZE_MB` aplicado **antes** de ler o corpo inteiro |
| Detecção de MIME | `python-magic` (libmagic) | **`file-type`** | JS puro; mantém o fallback por magic bytes |
| Imagem: HEIC | `pillow-heif` | ⚠️ **sem equivalente viável** | Converter no cliente (§3.2) |
| Imagem: resize/WebP | `Pillow` + `imgdiet` | **`sharp`** | Binários pré-compilados; manter `MAX_WIDTH=1654`, `MAX_HEIGHT=2339`, `MIN_SIZE_SKIP=200000` |
| Export XLSX | `openpyxl` | **`exceljs`** | Manter a neutralização de fórmula (§7.4) |
| Export PDF | `reportlab` (892 LOC em `inspecoes/pdf_service.py`) | **`pdfkit`** | Fora do MVP, mas **dentro do núcleo** — entra com `inspecoes` (§2.4) |
| Object storage | `boto3` | **`@aws-sdk/client-s3`** | R2 é compatível com S3; presigned URLs iguais |
| Leitura de PDF | `pypdfium2` | `pdfjs-dist` (legacy) | Fora do MVP |
| Testes | pytest + httpx | **`node:test` + `supertest`** | Ou Vitest, se a equipe preferir |

### 5.2. Por que Drizzle em vez de Prisma (mudança em relação à v1.0)

A v1.0 recomendava Prisma. A v2.0 recomenda **Drizzle**, por três motivos concretos
deste projeto:

1. **Controle de codec de coluna (decisivo).** O problema E-09 — UUID sem hífen e
   `DATETIME` como texto naive — se resolve com um *custom type* de ~10 linhas no
   Drizzle, aplicado uma vez e válido em todo o código. No Prisma, o mapeamento de
   tipos do conector SQLite não é extensível: a saída prática seria declarar todas as
   colunas de data como `String` e converter à mão em cada consulta, perdendo justamente
   a tipagem que motiva usar Prisma.
2. **Sem *query engine* binário.** O Prisma distribui um motor nativo por
   plataforma/OpenSSL e precisa de `prisma generate` no build. Em hospedagem
   compartilhada isso é uma superfície de falha a mais (tamanho do pacote, ABI, download
   em build). Drizzle é TypeScript puro sobre o driver.
3. **SQL previsível.** A migração precisa reproduzir consultas específicas —
   `EXISTS` em vez de `COUNT` na sincronização de status, subquery de *ranking* na
   listagem, extração de ano por dialeto (`_get_year_func`). Drizzle deixa escrever
   isso literalmente.

Se a equipe já tiver domínio de Prisma e quiser mantê-lo, é aceitável — **desde que**
todas as colunas `DATETIME` sejam mapeadas como `String` e a conversão fique isolada
numa camada de repositório. Registrar como ADR.

Driver: `better-sqlite3` (síncrono, com binários pré-compilados para linux-x64).
**Validar a instalação em Fase 0.** Fallback sem compilação nativa: `node:sqlite`
(embutido no Node 22+), ao custo de escrever a camada de acesso à mão.

### 5.3. Dependências que exigem decisão antes de codificar

| Item | Decisão necessária | Responsável |
| :--- | :--- | :--- |
| HEIC (§3.2) | Cliente, WASM ou rejeitar | Dono do produto |
| `better-sqlite3` | Instala no host? (Fase 0) | Dev |
| SQLite vs MySQL (§6.7) | Depende do resultado da Fase 0 | Dev + dono |
| Dados da FAB em hospedagem compartilhada de terceiros | Aprovação formal de quem responde pela informação | Dono do projeto |

> A última linha não é detalhe técnico. Sair de uma VPS controlada para hospedagem
> compartilhada muda o perímetro de quem tem acesso físico e lógico aos dados de
> manutenção da frota. É uma decisão de quem responde pela informação, não da equipe
> de desenvolvimento — mas precisa estar registrada antes do *go-live*, não depois.

---

## 6. Armadilhas de paridade de dados

Esta é a seção que mais separa a v2.0 da v1.0. Cada item abaixo já causou, ou causaria,
falha silenciosa.

### 6.1. 🔴 O hash de senha não é bcrypt puro (E-01)

`app/modules/auth/security.py`:

```python
def _preparar_senha(senha_plana: str) -> str:
    """Pré-hash SHA-256 + base64 para contornar o limite de 72 bytes do bcrypt."""
    senha_bytes = senha_plana.encode("utf-8")
    hash_sha256 = hashlib.sha256(senha_bytes).digest()
    return base64.b64encode(hash_sha256).decode("utf-8")

def hash_senha(senha_plana: str) -> str:
    return _pwd_context.hash(_preparar_senha(senha_plana))   # bcrypt

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return _pwd_context.verify(_preparar_senha(senha_plana), senha_hash)
```

Equivalente Node **obrigatório** — mesma função para verificar *e* para gerar, senão
senhas novas ficam incompatíveis com o Python caso haja rollback:

```ts
import { createHash } from "node:crypto";
import bcrypt from "bcryptjs";

/** Espelha app/modules/auth/security.py:_preparar_senha — NÃO ALTERAR. */
function prepararSenha(senhaPlana: string): string {
  return createHash("sha256").update(senhaPlana, "utf8").digest("base64");
}

export const hashSenha = (s: string) => bcrypt.hash(prepararSenha(s), 12);
export const verificarSenha = (s: string, hash: string) =>
  bcrypt.compare(prepararSenha(s), hash);
```

**Teste de aceitação obrigatório (Fase 2):** o hash real do admin em produção
(`$2b$12$zAV971r4aSIe8Rq7QzYjdef7Uu.ud9vB.jHjVvfH4IyAkVd7/r4HO`) deve validar contra a
senha conhecida usando o código Node. Sem esse teste passando, a fase não fecha.
Custo de fator 12: ~200-300 ms por login — relevante no CPU limitado do plano, e a razão
de o rate limit de `5/minute` no login ter que ser preservado.

### 6.2. 🔴 UUID é `CHAR(32)` hex sem hífen (E-09)

O SQLAlchemy grava UUID em SQLite como 32 caracteres hex sem separadores:

```
banco:    fc289b4a45cb4a30a717a583b6a84999
API/JSON: fc289b4a-45cb-4a30-a717-a583b6a84999
```

O frontend (`panes_lista.js`, `panes_detalhe.js`) monta URLs com a forma **com hífen**,
porque é isso que o Pydantic serializa. Portanto a camada Node precisa de conversão nas
duas pontas:

```ts
import { customType } from "drizzle-orm/sqlite-core";

export const uuidCol = customType<{ data: string; driverData: string }>({
  dataType: () => "CHAR(32)",
  toDriver: (v) => v.replace(/-/g, "").toLowerCase(),   // API → banco
  fromDriver: (v) =>                                     // banco → API
    `${v.slice(0,8)}-${v.slice(8,12)}-${v.slice(12,16)}-${v.slice(16,20)}-${v.slice(20)}`,
});
```

Geração de novos IDs: `crypto.randomUUID()` e gravar sem hífen. Nunca deixar as duas
formas coexistirem na mesma coluna — uma comparação `=` falha em silêncio e o registro
some da listagem.

### 6.3. 🔴 `DATETIME` é texto naive, não epoch (E-09)

Formato gravado: `'2026-08-10 13:17:06'` — espaço como separador, **sem `T`, sem `Z`,
sem offset**, em UTC por convenção. `DATE` (ex.: `aeronaves.data_inicio_operacao`) é
`'2020-01-01'`.

Isso importa porque o conector SQLite do Prisma grava `DateTime` como **inteiro de
milissegundos desde a época**. Se qualquer escrita passar por esse caminho, a coluna
passa a ter duas representações e toda ordenação e filtro por data quebra — sem erro,
com resultado errado.

```ts
export const dtCol = customType<{ data: Date; driverData: string }>({
  dataType: () => "DATETIME",
  toDriver: (d) => d.toISOString().slice(0, 19).replace("T", " "),  // 2026-08-10 13:17:06
  fromDriver: (s) => new Date(s.replace(" ", "T") + "Z"),           // interpreta como UTC
});
```

Detalhes que precisam de teste próprio:

- Ordenação `ORDER BY data_abertura DESC` é **lexicográfica** neste formato — funciona
  corretamente, mas só porque o formato é de largura fixa. Não trocar por ISO com offset.
- Comparações de filtro (`data_inicio`, `data_fim` em `GET /panes/`) precisam ser
  formatadas do mesmo jeito antes de ir para o SQL.
- `_get_year_func` em `app/modules/panes/service.py:32` faz extração de ano por dialeto.
  Em SQLite é `strftime('%Y', coluna)` — reproduzir literalmente.

### 6.4. 🟠 `BOOLEAN` é INTEGER 0/1

`panes.ativo`, `usuarios.ativo`, `sistemas_ata.ativo`. Drizzle:
`integer("ativo", { mode: "boolean" })`. Cuidado com `ativo IS TRUE` — em SQLite,
escrever `= 1`.

### 6.5. 🟠 Valores de enum com acento

`StatusAeronave.INSPECAO` tem **valor** `"INSPEÇÃO"` (com cedilha e til), assim como
`TipoIndisponibilidade.SERVICO` = `"SERVIÇO"`. Esses são os bytes gravados na coluna.
Regras:

- Toda a cadeia precisa ser UTF-8 fim a fim: arquivos `.ts` em UTF-8, conexão SQLite em
  UTF-8, resposta HTTP com `charset=utf-8`.
- `sincronizar_status_aeronave` compara contra **as duas** grafias (`"INSPECAO"` e
  `"INSPEÇÃO"`) por causa de dados legados — ver `service.py:163`. **Preservar a
  comparação dupla.** Remover "por limpeza" reintroduz o bug de aeronave presa em
  inspeção.

### 6.6. PRAGMAs e Alembic

Abrir a conexão exatamente como o Python (`app/bootstrap/database.py:47-64`):

```ts
db.pragma("foreign_keys = ON");
db.pragma("journal_mode = WAL");
db.pragma("synchronous = NORMAL");
db.pragma("busy_timeout = 15000");
```

`foreign_keys = ON` não é opcional: `anexos` e `pane_responsaveis` dependem de
`ON DELETE CASCADE`, e `panes` depende de `ON DELETE RESTRICT` para não perder histórico.

**Alembic:** as 41 migrações **não** são portadas. A tabela `alembic_version` fica no
banco, intocada (revisão `2676d7fdd987`), como marcador de compatibilidade caso seja
preciso voltar ao Python. Novas mudanças de schema, quando houver, passam a usar
`drizzle-kit`. Registrar isso como ADR — é uma decisão irreversível na prática.

### 6.7. Plano B: MySQL

Se a Fase 0 mostrar que o SQLite não é confiável no host (§3.3), o plano inclui MySQL.
Nesse caso:

- `CHAR(32)` continua funcionando para UUID sem hífen — sem mudança de código.
- `DATETIME` do MySQL guarda `'YYYY-MM-DD HH:MM:SS'` — **mesmo formato**, o codec de
  §6.3 continua valendo.
- `BOOLEAN` vira `TINYINT(1)` — mesmo 0/1.
- Migração de dados: exportar tabela a tabela do SQLite, sem transformação de valores.
- Custo estimado: +1 semana. Ganho: elimina toda a classe de risco de trava de arquivo.

---

## 7. Contratos que não podem mudar

Como o frontend é reaproveitado inteiro, **o servidor Node é que tem que se encaixar
nele** — não o contrário. Qualquer divergência abaixo quebra a UI sem erro de servidor.

### 7.1. Cookies e sessão

| Nome | Conteúdo | Flags |
| :--- | :--- | :--- |
| `saa29_token` | JWT de acesso, 15 min | `HttpOnly`, `SameSite=Lax`, `Secure` se `FORCE_SECURE_COOKIES` |
| `saa29_refresh_token` | JWT de refresh, 7 dias | `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` idem |
| `fastapi-csrf-token` | Token CSRF assinado | `SameSite=Lax`, `Secure` idem |

O `Path=/` do refresh é histórico e proposital (comentário em `router.py`): sem ele o
navegador não enviava o cookie e a revogação no logout não acontecia. **Não "corrigir".**

O access token é aceito por **duas** vias: header `Authorization: Bearer` (Swagger/API) e
cookie `saa29_token` (web) — nessa ordem de precedência
(`app/bootstrap/dependencies.py:41-56`).

### 7.2. CSRF

- Cookie **`fastapi-csrf-token`** (nome mantido apesar do framework mudar — mudar o nome
  desloga todo mundo e quebra o JS).
- Header **`X-CSRF-Token`** nas requisições mutantes.
- Métodos protegidos: `POST`, `PUT`, `PATCH`, `DELETE`. **Sem isenção para
  `/auth/login` e `/auth/logout`** — a isenção foi deliberadamente removida do Python
  (comentário em `csrf.py`), e o `login.js` já lê o token da `<meta name="csrf-token">`
  renderizada no `base.html`. Reintroduzir a isenção reabre CSRF de login.
- Falha → **403** com `{"detail": "Erro de segurança (CSRF). Recarregue a página."}`.
- O token é injetado em `request.state.csrf_token` e consumido pelo template. Em
  Nunjucks: `res.locals.csrfToken`, exposto no `base.html`.
- Otimização a preservar: **não gerar token para `/static/*`**.

### 7.3. Formato de erro

FastAPI responde `{"detail": "..."}`, com `422` para erro de validação. O frontend lê
`detail` diretamente. O Express precisa de um *error handler* que produza o mesmo
envelope, incluindo o `422` do Zod.

Regra crítica de roteamento de erro (`app/bootstrap/main.py:57-76`): um 401/403 em rota
de **página** redireciona para `/login`; em rota de **API** devolve JSON. A discriminação
é por prefixo. No MVP a lista é `["/auth/", "/aeronaves/", "/panes/", "/internal/"]`.
Manter **uma única** lista, no mesmo arquivo do registro de rotas — a duplicação dessa
lista já causou bug em produção duas vezes (calendário e publicações).

### 7.4. Comportamentos de segurança a portar literalmente

| Comportamento | Origem | Por quê |
| :--- | :--- | :--- |
| Neutralização de fórmula no CSV/XLSX | `app/shared/exporter.py:_neutralizar_formula` | CSV injection. Prefixa `'` quando a célula começa com `= + - @ \t \r`. **Números não são neutralizados** — a checagem é por tipo, antes de virar string |
| Lockout de conta | `auth/service.py:26-89` | 5 tentativas → 15 min. Persistente em banco |
| Validação de MIME por magic bytes | `shared/core/file_validators.py` | Extensão e conteúdo têm que bater. Allowlist: `image/jpeg`, `image/png`, `application/pdf` (+ HEIC/HEIF conforme §3.2) |
| Leitura com limite antes de bufferizar | `ler_upload_com_limite` | Impede exaustão de memória por upload grande — crítico com 3 GB de RAM |
| Blacklist de `jti` no logout | `token_blacklist` | Access token revogado antes de expirar |
| Rejeitar refresh token usado como access | `dependencies.py:80-84` | `payload.type` tem que ser `"access"` |
| Cabeçalhos de segurança / CSP | `shared/middleware/security.py` | Copiar a CSP existente. Ela já acomoda o PDF.js vendorizado |
| `.mjs` → `text/javascript` | `main.py:_mount_static` | Módulos ES são rejeitados pelo navegador com MIME errado |

---

## 8. Esquema do MVP

Nove tabelas de 38. Nenhuma renomeada, nenhuma coluna alterada.

```ts
// db/schema.ts  (Drizzle + SQLite)
import { sqliteTable, text, integer, real, index, uniqueIndex } from "drizzle-orm/sqlite-core";
import { uuidCol, dtCol } from "./types";  // §6.2 e §6.3

export const usuarios = sqliteTable("usuarios", {
  id:            uuidCol("id").primaryKey(),
  nome:          text("nome", { length: 150 }).notNull(),
  posto:         text("posto", { length: 30 }).notNull(),
  especialidade: text("especialidade", { length: 50 }),
  funcao:        text("funcao", { length: 50 }).notNull(),   // MANTENEDOR|INSPETOR|ENCARREGADO|ADMINISTRADOR
  ramal:         text("ramal", { length: 20 }),
  trigrama:      text("trigrama", { length: 3 }),
  username:      text("username", { length: 50 }).notNull(),
  senhaHash:     text("senha_hash", { length: 255 }).notNull(),
  ativo:         integer("ativo", { mode: "boolean" }).notNull(),
  failedLoginAttempts: integer("failed_login_attempts").notNull(),
  lockedUntil:   dtCol("locked_until"),
  createdAt:     dtCol("created_at").notNull(),
  updatedAt:     dtCol("updated_at"),
}, (t) => ({
  ixUsername: uniqueIndex("ix_usuarios_username").on(t.username),
  ixAtivo:    index("ix_usuarios_ativo").on(t.ativo),
}));

export const aeronaves = sqliteTable("aeronaves", {
  id:            uuidCol("id").primaryKey(),
  partNumber:    text("part_number", { length: 50 }),
  serialNumber:  text("serial_number", { length: 50 }).notNull(),
  matricula:     text("matricula", { length: 20 }).notNull(),
  modelo:        text("modelo", { length: 50 }).notNull(),
  status:        text("status", { length: 20 }).notNull(),   // atenção: "INSPEÇÃO" com acento — §6.5
  statusAnteriorInativacao: text("status_anterior_inativacao", { length: 20 }),
  horasVooTotal: real("horas_voo_total").notNull(),
  dataInicioOperacao: text("data_inicio_operacao").notNull(),  // DATE 'YYYY-MM-DD'
  horasAtualizadasEm: dtCol("horas_atualizadas_em"),
  createdAt:     dtCol("created_at").notNull(),
  updatedAt:     dtCol("updated_at"),
}, (t) => ({
  ixMatricula: uniqueIndex("ix_aeronaves_matricula").on(t.matricula),
  ixSerial:    uniqueIndex("ix_aeronaves_serial_number").on(t.serialNumber),
}));

export const sistemasAta = sqliteTable("sistemas_ata", {
  id:        uuidCol("id").primaryKey(),
  codigo:    text("codigo", { length: 10 }).notNull(),
  descricao: text("descricao", { length: 100 }).notNull(),
  ativo:     integer("ativo", { mode: "boolean" }).notNull(),
}, (t) => ({ ixCodigo: uniqueIndex("ix_sistemas_ata_codigo").on(t.codigo) }));

export const panes = sqliteTable("panes", {
  id:           uuidCol("id").primaryKey(),
  aeronaveId:   uuidCol("aeronave_id").notNull().references(() => aeronaves.id, { onDelete: "restrict" }),
  status:       text("status", { length: 20 }).notNull(),        // ABERTA | RESOLVIDA
  sistemaAtaId: uuidCol("sistema_ata_id").references(() => sistemasAta.id, { onDelete: "restrict" }),
  descricao:    text("descricao").notNull(),
  dataAbertura: dtCol("data_abertura").notNull(),
  dataConclusao: dtCol("data_conclusao"),
  observacaoConclusao: text("observacao_conclusao"),
  comentarios:  text("comentarios"),
  ativo:        integer("ativo", { mode: "boolean" }).notNull(),  // soft delete
  criadoPorId:  uuidCol("criado_por_id").notNull().references(() => usuarios.id, { onDelete: "restrict" }),
  concluidoPorId: uuidCol("concluido_por_id").references(() => usuarios.id, { onDelete: "restrict" }),
  createdAt:    dtCol("created_at").notNull(),
  updatedAt:    dtCol("updated_at"),
}, (t) => ({
  ixAtivo:    index("ix_panes_ativo").on(t.ativo),
  ixStatus:   index("ix_panes_status").on(t.status),
  ixAeronave: index("ix_panes_aeronave_id").on(t.aeronaveId),
  ixAta:      index("ix_panes_sistema_ata_id").on(t.sistemaAtaId),
}));

export const anexos = sqliteTable("anexos", {
  id:             uuidCol("id").primaryKey(),
  paneId:         uuidCol("pane_id").notNull().references(() => panes.id, { onDelete: "cascade" }),
  caminhoArquivo: text("caminho_arquivo", { length: 500 }).notNull(),  // ou "processando" / "ERRO"
  tipo:           text("tipo", { length: 20 }).notNull(),              // IMAGEM | DOCUMENTO
  createdAt:      dtCol("created_at").notNull(),
}, (t) => ({ ixPane: index("ix_anexos_pane_id").on(t.paneId) }));

export const paneResponsaveis = sqliteTable("pane_responsaveis", {
  id:        uuidCol("id").primaryKey(),
  paneId:    uuidCol("pane_id").notNull().references(() => panes.id, { onDelete: "cascade" }),
  usuarioId: uuidCol("usuario_id").notNull().references(() => usuarios.id, { onDelete: "restrict" }),
  papel:     text("papel", { length: 30 }).notNull(),
  createdAt: dtCol("created_at").notNull(),
}, (t) => ({
  uq:     uniqueIndex("uq_pane_responsavel_pane_usuario").on(t.paneId, t.usuarioId),
  ixPane: index("ix_pane_responsaveis_pane_id").on(t.paneId),
}));

export const tokenRefresh = sqliteTable("token_refresh", {
  id:         uuidCol("id").primaryKey(),
  usuarioId:  uuidCol("usuario_id").notNull().references(() => usuarios.id, { onDelete: "cascade" }),
  jti:        text("jti", { length: 36 }).notNull(),
  expiraEm:   dtCol("expira_em").notNull(),
  criadoEm:   dtCol("criado_em").notNull(),
  revogadoEm: dtCol("revogado_em"),
}, (t) => ({
  ixJti:     uniqueIndex("ix_token_refresh_jti").on(t.jti),
  ixUsuario: index("ix_token_refresh_usuario_id").on(t.usuarioId),
}));

export const tokenBlacklist = sqliteTable("token_blacklist", {
  jti:      text("jti", { length: 36 }).primaryKey(),
  expiraEm: dtCol("expira_em").notNull(),
  criadoEm: dtCol("criado_em").notNull(),
}, (t) => ({ ixJti: index("ix_token_blacklist_jti").on(t.jti) }));

// SOMENTE LEITURA — §4.4. Sem rota, sem UI. Existe só para sincronizar_status_aeronave.
export const inspecoes = sqliteTable("inspecoes", {
  id:         uuidCol("id").primaryKey(),
  aeronaveId: uuidCol("aeronave_id").notNull(),
  status:     text("status", { length: 20 }).notNull(),
});
```

> `jti` é `VARCHAR(36)` — UUID **com** hífen, ao contrário das chaves primárias.
> A inconsistência é do banco atual e precisa ser preservada como está.

---

## 9. Estrutura de pastas proposta (Node)

Espelha os limites de módulo do Python, para que a Fase 2 seja "adicionar pastas",
não "reorganizar".

```
saa29-node/
├── app.js                    # entry file exigido pelo painel (§12.1) — só faz require('./dist/server.js')
├── package.json
├── tsconfig.json
├── src/
│   ├── server.ts             # createApp(): middlewares, rotas, static — espelha bootstrap/main.py
│   ├── config/
│   │   └── index.ts          # Zod sobre process.env; falha no boot se faltar variável
│   ├── db/
│   │   ├── index.ts          # better-sqlite3 + PRAGMAs (§6.6)
│   │   ├── schema.ts         # §8
│   │   └── types.ts          # uuidCol, dtCol (§6.2, §6.3)
│   ├── modules/
│   │   ├── auth/             # router.ts · service.ts · security.ts · schemas.ts
│   │   ├── aeronaves/
│   │   └── panes/
│   ├── shared/
│   │   ├── middleware/       # csrf.ts · security-headers.ts · rate-limit.ts · error-handler.ts
│   │   ├── storage/          # local.ts · r2.ts (mesma interface de shared/core/storage.py)
│   │   ├── file-validators.ts
│   │   ├── image.ts          # sharp: resize + WebP
│   │   └── exporter.ts       # CSV/XLSX + neutralização de fórmula
│   ├── web/
│   │   ├── pages.ts          # rotas HTML
│   │   └── deps.ts           # requireAuth, requireRole, ExecucaoPermitida
│   └── internal/
│       └── cron.ts           # §3.1
├── templates/                # cópia de app/web/templates/  (só o subconjunto do MVP)
├── public/                   # cópia de app/web/static/     (servido em /static)
├── var/
│   ├── db/saa29.db           # fora de public/ — §12.3
│   └── uploads/
└── tests/
```

**Regra de layout:** nada dentro de `var/` pode ser alcançável por URL. O
`saa29_local.db` **não** pode ficar em `public_html/` acessível — é o erro mais comum
em hospedagem compartilhada e expõe o banco inteiro por download direto (§12.3).

---

## 10. Roteiro por fases

Cada fase tem **critério de saída objetivo**. Fase sem critério atendido não avança.

As estimativas assumem **um desenvolvedor com assistência de IA**, trabalhando sobre
uma implementação de referência que roda ao lado. Não são estimativas de reescrita:
não há descoberta de requisito, modelagem de schema nem trabalho de UX neste projeto —
metade do código (20.340 linhas de HTML, JS e CSS) é reaproveitada sem alteração
(§2.4).

### 10.0. 🔴 Regra de sequência: testes antes do código

**Nas Fases 2, 3 e 4, a suíte de testes daquele escopo é portada ANTES da implementação.**
Não é preciosismo de processo — é o que torna a tradução rápida segura.

O motivo está medido em §13.1: existem **118 referências a bugs, riscos e achados de
auditoria numerados** nos comentários do código Python. São correções que já custaram
depuração, e **várias delas parecem redundância ou código morto para quem lê o arquivo
de fora**. O caso canônico é a comparação dupla `"INSPECAO"` / `"INSPEÇÃO"` em
`sincronizar_status_aeronave`: parece duplicação, é a correção do bug de aeronave presa
em inspeção para sempre.

Uma tradução veloz — humana ou assistida por IA — vai "limpar" algumas dessas correções.
Com a suíte no lugar primeiro, a regressão aparece no mesmo dia e custa minutos. Sem ela,
vira um bug silencioso em produção, descoberto meses depois, e cada um desses custa mais
do que a velocidade economizou.

> **Critério operacional:** nenhuma fase de implementação começa com a suíte
> correspondente vermelha por ausência de teste. Teste vermelho por falta de código é o
> estado esperado; teste inexistente não é.

### Fase 0 — Spike de viabilidade no host real  ⏱ 1–2 dias  🔴 **bloqueante**

Não escrever uma linha de lógica de negócio antes disto. Publicar um Express mínimo
no plano contratado e responder, com evidência:

| # | Pergunta | Como medir | Critério |
| :-- | :--- | :--- | :--- |
| 0.1 | Qual versão de Node está disponível? | `process.version` numa rota | ≥ 20 LTS |
| 0.2 | `better-sqlite3` instala? | `npm ci` no host + `require` | Instala sem compilar do zero |
| 0.3 | Escrita em disco persiste entre reinícios? | Gravar arquivo, reiniciar pelo painel, ler | Persiste |
| 0.4 | SQLite em WAL funciona? | Abrir com os 4 PRAGMAs, 200 escritas concorrentes | Sem `SQLITE_BUSY`, sem corrupção |
| 0.5 | O processo é suspenso quando ocioso? | `setInterval` gravando timestamp; medir buracos em 2 h | Documentar o comportamento observado |
| 0.6 | Quanto custa um *cold start*? | Cronometrar o primeiro request após ociosidade | < 3 s |
| 0.7 | Cron do painel funciona? | Job de 5 min chamando `/internal/cron/ping` | Dispara na hora |
| 0.8 | Qual o limite de inodes e quanto já foi usado? | hPanel → Resources Usage, antes e depois de `npm ci` | Sobra ≥ 50% |
| 0.9 | Quanta RAM o processo pode usar? | Alocar progressivamente até falhar | Registrar o teto |
| 0.10 | O IP real do cliente chega? | Logar `req.ip` com `trust proxy` | IP público correto, não o do proxy |
| 0.11 | HTTPS chega ao app ou termina no proxy? | Logar `X-Forwarded-Proto` | Documentar para `Secure` cookies |

**Saída:** um relatório de uma página. Se 0.2 falhar → `node:sqlite`. Se 0.4 falhar →
`journal_mode=DELETE` ou MySQL (§6.7). Se 0.3 falhar → **a hospedagem não serve**;
reavaliar o plano antes de gastar semanas de desenvolvimento.

### Fase 1 — Fundação  ⏱ 3–5 dias

- Projeto TypeScript + Express 5 + Nunjucks apontando para `templates/` e `public/`.
- Camada de banco: `better-sqlite3` + Drizzle, com `uuidCol`/`dtCol` (§6.2, §6.3) e os
  4 PRAGMAs.
- Config por Zod, com falha no boot se faltar variável.
- Middlewares: helmet (CSP copiada), CSRF (`csrf-csrf`), rate limit, `trust proxy`,
  error handler com envelope `{"detail": …}` e a lista única de prefixos de API (§7.3).
- Filtros `min` e `max` registrados no Nunjucks; `base.html` renderizando com
  `modulos_ativos`.

**Saída:** `/login` renderiza igual ao atual, com CSS e JS carregando de `/static`, e um
teste de round-trip prova que ler e escrever um `DATETIME` e um UUID no banco real
devolve exatamente os mesmos bytes.

### Fase 2 — Autenticação  ⏱ 4–6 dias

- **Primeiro (§10.0):** portar `tests/security/test_auth_achados_revisor.py` (8),
  `test_csrf.py` (5) e `test_login_csrf.py` (2).
- `_preparar_senha` portado (§6.1) — **o primeiro teste a ficar verde**.
- 11 rotas de `/auth`; cookies com nomes e flags exatos (§7.1).
- Refresh com rotação, blacklist de `jti`, lockout de conta.
- `requireAuth` / `requireRole` espelhando `dependencies.py`.

**Saída:** o admin de produção loga com a senha atual; `/auth/me` responde; o refresh
rotaciona; o logout revoga; 6 tentativas erradas bloqueiam por 15 min.

### Fase 3 — Aeronaves + Panes (núcleo)  ⏱ 8–12 dias

- **Primeiro (§10.0):** portar `tests/unit/test_panes*.py` (4 arquivos),
  `tests/security/test_panes_achados_revisor.py` e `test_exporter_injection.py` (8).
  É o maior investimento de teste do MVP e o que protege `service.py` — 952 linhas, o
  arquivo mais denso do escopo, com 16 referências a `relatorio_panes_service.md`.
- 5 rotas de `/aeronaves` + 14 de `/panes`.
- `sincronizar_status_aeronave` com a leitura de `inspecoes` (§4.4) e a comparação
  dupla `"INSPECAO"`/`"INSPEÇÃO"` (§6.5).
- Listagem com todos os filtros, paginação e a subquery de ranking.
- Export CSV/XLSX com neutralização de fórmula (§7.4).

**Saída:** `panes_lista.js` e `panes_detalhe.js` funcionam **sem uma linha alterada**,
contra o banco real, exceto o bloco FIM com feature flag (§4.6).

### Fase 4 — Anexos e armazenamento  ⏱ 4–6 dias

- **Primeiro (§10.0):** portar os testes de upload e validação de MIME.
- `multer` em memória com limite aplicado antes de bufferizar.
- Validação de MIME por magic bytes (`file-type`) + coerência com a extensão.
- Pipeline `sharp`: resize 1654×2339, WebP, pular arquivos < 200 KB.
- Decisão de HEIC implementada (§3.2).
- Storage local **e** R2 atrás da mesma interface; download com 302 para URL assinada
  no modo R2 e 409 para anexo em `processando`/`ERRO`.
- Duas rotas de cron (§3.1) + jobs configurados no painel.

**Saída:** upload de JPEG, PNG e PDF; download autenticado; anexo travado é reciclado
pelo cron em até 15 min.

### Fase 5 — Paridade, carga e cutover  ⏱ 5–8 dias

- Suíte de paridade verde (§11).
- Teste de carga proporcional ao uso real (20–30 usuários simultâneos), medindo
  latência de login (bcrypt custa caro no plano) e memória.
- Backup automatizado (§12.5) testado com **restauração de verdade**, não só geração.
- Runbook de rollback escrito e ensaiado.

**Saída:** critérios de aceite de §14 todos atendidos.

### 10.6. Totais

| Escopo | LOC Python a portar | Rotas | Estimativa | Acumulado |
| :--- | ---: | ---: | :--- | :--- |
| **Etapa 1 — MVP** (auth + aeronaves + panes + infra) | 6.832 | 30 | **5 a 7 semanas** | ~1,5 mês |
| **Etapa 2 — completa o núcleo** (equipamentos + vencimentos, depois inspecoes) | 5.436 | 55 | **4 a 6 semanas** | **2,5 a 3,5 meses** |
| 🔴 **Núcleo do produto — entrega 100% do que o SAA29 se propõe a fazer** | **12.268** | **85** | | |
| 🟢 Etapa 3 — extras, opcional (pedidos, calendário, encarregado, dashboard, efetivo) | 2.996 | 27 | 2 a 3 semanas | |
| 🟢 Etapa 4 — `publicacoes`, opcional | 4.780 | 34 | 3 a 4 semanas | |
| 🟢 PWA mobile, opcional | — | 7 | 1 a 2 semanas | |
| | **20.044** | **146** | | **4 a 5 meses** |

**A linha que importa é a do núcleo: 2,5 a 3,5 meses para o produto inteiro e útil.**
Os 1,5 a 2 meses restantes são qualidade de vida, e podem nunca ser gastos.

A Fase 0 pode invalidar o plano inteiro — é por isso que vem primeiro e é curta.

> **Sobre a natureza da estimativa.** Estes números descrevem *tradução*, não
> *reescrita*, e por isso são baixos para o tamanho aparente do sistema: a lógica de
> negócio já está consolidada e depurada, o frontend inteiro é reaproveitado, o schema
> já existe, e há uma implementação de referência executável para comparar lado a lado
> (§11.1c). O fator que pode estourar o prazo não é volume de código — é retrabalho por
> regressão silenciosa, que é exatamente o que a regra de §10.0 existe para conter.

---

## 11. Estratégia de testes e paridade

Existem 720 testes em Python. Eles são a especificação executável do comportamento —
é o ativo mais valioso da migração e a v1.0 não os menciona.

**Eles não são a etapa de validação no fim; são o primeiro entregável de cada fase**
(§10.0). A suíte é o que permite traduzir rápido: é o oráculo que transforma uma
regressão silenciosa — o risco R-15, o único que cresce com a velocidade — em um teste
vermelho no mesmo dia.

### 11.1. Três camadas

**a) Testes de paridade de dados (os mais importantes).** Rodam contra uma **cópia** do
`saa29_local.db` e verificam que o Node lê e escreve exatamente como o Python:

- Hash de senha real → valida com `verificarSenha`.
- UUID `fc289b4a45cb4a30a717a583b6a84999` ↔ `fc289b4a-45cb-4a30-a717-a583b6a84999`.
- `DATETIME` gravado pelo Node é relido pelo Python e vice-versa, sem deriva.
- `sincronizar_status_aeronave`: matriz completa de 6 estados × {com/sem pane} ×
  {com/sem inspeção}.
- Neutralização de fórmula: `=HYPERLINK(...)` vira `'=HYPERLINK(...)`, mas `-5` continua `-5`.

**b) Testes de contrato HTTP.** Portar os arquivos de panes e auth (o subconjunto do MVP):

| Arquivo Python | Testes | Prioridade |
| :--- | ---: | :--- |
| `tests/unit/test_panes*.py` (4 arquivos) | — | 🔴 Obrigatório |
| `tests/security/test_panes_achados_revisor.py` | — | 🔴 Obrigatório |
| `tests/security/test_auth_achados_revisor.py` | 8 | 🔴 Obrigatório |
| `tests/security/test_csrf.py` | 5 | 🔴 Obrigatório |
| `tests/security/test_login_csrf.py` | 2 | 🔴 Obrigatório |
| `tests/security/test_exporter_injection.py` | 8 | 🔴 Obrigatório |

**c) Comparação lado a lado (*golden tests*).** Durante as Fases 3 e 4, subir Python e
Node contra cópias do mesmo banco e comparar as respostas JSON campo a campo para o
mesmo request. É o jeito mais barato de achar divergência de serialização — formato de
data, UUID com/sem hífen, ordenação, casas decimais.

### 11.2. Regra de ouro

> Se um teste Python passa e o equivalente Node falha, **o Node está errado** — mesmo
> que o comportamento do Node pareça mais correto. Divergências que pareçam melhorias
> viram issue para depois do cutover, não mudança durante a migração.

---

## 12. Deploy e operação

### 12.1. Entry file

O painel pede um arquivo de entrada. Manter um `app.js` fino na raiz:

```js
// app.js — carregado pelo gestor de aplicações do painel
require("./dist/server.js");
```

O TypeScript é compilado **localmente ou no CI**, e o `dist/` é publicado. Não depender
de compilar no host: é lento, consome a CPU do plano e falha em ambiente restrito.

### 12.2. Variáveis de ambiente

Mínimo do MVP (todas validadas por Zod no boot; sem *defaults* inseguros):

```
NODE_ENV=production
APP_SECRET_KEY=<32+ bytes aleatórios — mesmo valor do Python se houver sessão a preservar>
DATABASE_PATH=/home/<user>/saa29/var/db/saa29.db
UPLOAD_DIR=/home/<user>/saa29/var/uploads
MAX_UPLOAD_SIZE_MB=10
JWT_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
FORCE_SECURE_COOKIES=true
ALLOWED_HOSTS=saa29.exemplo.mil.br
ALLOWED_ORIGINS=https://saa29.exemplo.mil.br
STORAGE_BACKEND=local            # local | r2
CRON_KEY=<32+ bytes aleatórios>
MODULOS_ATIVOS=panes,frota
```

Atenção a `ALLOWED_ORIGINS`: o código Python tem um fallback que troca `"*"` por
origens de localhost e só registra um *warning*, porque `"*"` é incompatível com
`allow_credentials=true` (`main.py:131-147`). No Node, **falhar no boot** em vez de
degradar em silêncio.

### 12.3. Layout no servidor

```
/home/<user>/
├── saa29/                  # FORA do document root
│   ├── app.js  dist/  node_modules/  templates/  public/
│   └── var/
│       ├── db/saa29.db     # ❗ nunca acessível por URL
│       └── uploads/        # servido só via /panes/{id}/anexos/{id}/download
└── public_html/            # apenas o que o painel exigir
```

Anexos **não** são servidos como estáticos: o download passa pela rota autenticada, que
é o comportamento atual e não deve ser "simplificado".

### 12.4. Proxy

```ts
app.set("trust proxy", 1);   // um único proxy à frente
```

Sem isso: `req.ip` vira o IP do proxy, o rate limit vira global e o lockout por IP
perde sentido. Confirmar o número de saltos com o resultado de 0.10/0.11 da Fase 0.

### 12.5. Backup

O backup por *listener* + debounce de 120 s (§3.1) não sobrevive. Substituir por cron:

```
0 */6 * * *  cd ~/saa29 && node scripts/backup.js
```

O script faz `VACUUM INTO` (cópia consistente do SQLite, segura com WAL ativo),
comprime, envia para o R2 e mantém as N cópias mais recentes.

> **Restauração testada é requisito de aceite (§14).** Backup que nunca foi restaurado
> é uma suposição, não um backup.

### 12.6. Logs

Sem `journalctl` nem Docker. `pino` escrevendo em `var/logs/` com rotação por tamanho
(o limite de disco é do plano inteiro) e uma rota `/internal/health` para monitoramento
externo — que também mantém o processo aquecido, se a Fase 0 mostrar suspensão por
ociosidade (item 0.5).

---

## 13. Riscos

| ID | Risco | Prob. | Impacto | Mitigação |
| :--- | :--- | :--- | :--- | :--- |
| R-01 | Custo se inverte na renovação: R$ 64,99/mês contra R$ 59,99/mês do VPS | **Certa** | Alto — anula a justificativa do projeto | Decidir com o horizonte de 4 anos em mente (§1.1); reavaliar antes da renovação |
| R-02 | Login falha por causa do pré-hash (E-01) | Alta se ignorado | Bloqueante | §6.1 + teste de aceite na Fase 2 |
| R-03 | Datas corrompidas por divergência de formato (E-09) | Alta | Alto — perda silenciosa | `dtCol` (§6.3) + teste de round-trip na Fase 1 |
| R-04 | SQLite/WAL instável no host | Média | Alto | Fase 0 item 0.4; fallback MySQL (§6.7) |
| R-05 | Processo suspenso por ociosidade quebra jobs | Média | Médio | Cron HTTP (§3.1) + health check externo |
| R-06 | HEIC deixa de funcionar (E-12) | Alta | Médio — atinge o usuário de campo | Conversão no cliente (§3.2) |
| R-07 | `better-sqlite3` não instala | Baixa | Médio | `node:sqlite` (Node 22+) |
| R-08 | Limite de inodes estourado por `node_modules` | Média | Médio | Medir na Fase 0 (0.8); publicar `dist/` sem devDependencies |
| R-09 | Latência do bcrypt fator 12 no CPU do plano | Média | Médio | Medir na Fase 5; manter rate limit; não baixar o fator sem invalidar hashes |
| R-10 | Divergência silenciosa de contrato quebra o frontend | Média | Alto | Golden tests (§11.1c) |
| R-11 | Escopo escorrega para "só mais um módulo" | **Alta** | Alto | §4.2 é contrato; módulo novo = nova etapa, com sua própria estimativa |
| R-12 | Publicações puxado para dentro do MVP | Média | Alto — 33 rotas a mais | §1.2 e §15 |
| R-13 | Dados da FAB em hospedagem compartilhada sem aprovação formal | Média | Alto | Registrar aprovação antes do go-live (§5.3) |
| R-14 | Rollback impossível porque o banco divergiu | Média | Alto | O Node **não** altera schema no MVP; `alembic_version` intocada (§6.6); backup antes do cutover |
| R-15 | Correção antiga descartada como "limpeza" durante a tradução | **Alta** | Alto — regressão silenciosa | §13.1 + regra de testes-primeiro (§10.0) |

### 13.1. O risco específico da tradução rápida (R-15)

Este é o único risco que **cresce** com a velocidade, e por isso merece número próprio.

O código Python não é um rascunho: já passou por auditorias e ciclos de depuração.
Contagem nos comentários de `app/`:

```
118 referências a bugs, riscos e achados numerados
    16×  relatorio_panes_service.md      13×  RISCO-05
    11×  BUG-03        11×  BUG-01        8×  ADR-004
     7×  BUG-02         6×  RISCO-03      4×  AUD-17 …

1.176 linhas de comentário explicativo
       csrf.py: 38% do arquivo  ·  auth/service.py: 12%  ·  panes/service.py: 8%
```

O problema não é o volume — é que **parte dessas correções parece defeito para quem lê
o arquivo isolado**. Exemplos reais, todos com o comentário explicando ao lado:

| Parece | É |
| :--- | :--- |
| Comparação duplicada `"INSPECAO"` / `"INSPEÇÃO"` | Correção do bug de aeronave presa em inspeção para sempre (§6.5) |
| `Path="/"` redundante só no cookie de refresh | Sem ele o navegador não envia o cookie e o logout não revoga (§7.1) |
| Parâmetro `status_filtro` com nome esquisito e `alias="status"` | Evita sombrear `fastapi.status` importado no mesmo módulo (RISCO-11) |
| Falta de isenção de CSRF em `/auth/login` | Isenção foi removida de propósito — reintroduzi-la abre CSRF de login (§7.2) |
| Lista de prefixos de API duplicando o registro de rotas | Duplicá-la de fato já causou dois bugs em produção (§7.3) |
| Pré-hash SHA-256 antes do bcrypt | Contorna o limite de 72 bytes do bcrypt — remover invalida todas as senhas (§6.1) |

**Mitigação:** a regra de §10.0 (testes antes do código) mais a leitura obrigatória do
arquivo Python de referência antes de portar cada área (Apêndice B). Ao encontrar código
que pareça redundante, a presunção correta é que **há um motivo documentado logo acima** —
não que seja sobra.

---

## 14. Critérios de aceite do MVP

Verificáveis, na ordem em que devem ser demonstrados:

1. ✅ Relatório da Fase 0 entregue, com os 11 itens respondidos com evidência.
2. ✅ Todo usuário existente loga com a senha atual, sem *reset*.
3. ✅ `panes_lista.js`, `panes_detalhe.js` e `app.js` (frontend) rodam **sem alteração**,
   exceto a flag do bloco FIM.
4. ✅ As 30 rotas de API do MVP respondem com o mesmo status, o mesmo envelope de erro e
   o mesmo formato de campo do FastAPI.
5. ✅ Round-trip Python → Node → Python de uma pane com data, UUID e booleano não altera
   nenhum byte no banco.
6. ✅ `sincronizar_status_aeronave` reproduz a matriz completa de estados, inclusive o
   caso "inspeção concluída com pane aberta".
7. ✅ CSRF bloqueia POST sem header; sessão sobrevive a reinício do processo.
8. ✅ 6 tentativas de login erradas bloqueiam a conta por 15 minutos, e o bloqueio
   persiste a um reinício.
9. ✅ Upload, listagem, download autenticado e exclusão de anexo funcionam para JPEG,
   PNG e PDF.
10. ✅ Export XLSX abre no Excel com `=HYPERLINK(...)` neutralizado e `-5` intacto.
11. ✅ Os dois jobs de cron rodam no painel e são idempotentes (rodar duas vezes seguidas
    não muda o resultado).
12. ✅ Backup gerado **e restaurado** com sucesso num ambiente limpo.
13. ✅ Sob 25 usuários simultâneos: p95 de resposta < 1,5 s e memória estável abaixo do
    teto medido em 0.9.
14. ✅ Runbook de rollback para o Python ensaiado de ponta a ponta.

---

## 15. Depois do MVP

### 15.1. Etapa 2 — completar o núcleo  ⏱ 4 a 6 semanas  🔴 **é aqui que o produto fica pronto**

Ao fim desta etapa o SAA29 em Node faz **tudo o que o SAA29 se propõe a fazer**: panes,
inspeções e vencimentos (§2.4). O que vier depois é opcional.

Estimativas assumem a fundação da Etapa 1 concluída — framework, middleware, camada de
banco e infraestrutura de teste já pagos.

| Ordem | Módulo(s) | LOC | Rotas | Estimativa |
| :-- | :--- | ---: | ---: | :--- |
| 1 | **`equipamentos` + `vencimentos` — juntos, obrigatoriamente** | 2.847 | 29 | 2–3 semanas |
| 2 | `inspecoes` — promove a tabela já mapeada de somente-leitura (§4.4) para CRUD completo | 2.589 | 26 | 2–3 semanas |

**Ordem 1 não é negociável, e a palavra "juntos" é literal.** `equipamentos` e
`vencimentos` têm dependência mútua (§2.4): `equipamentos.service` chama
`vencimentos.service.criar_controles_para_item`, e `vencimentos` importa quatro modelos
de `equipamentos`. Tentar migrar um antes do outro produz um módulo que não compila sem
*stub*, e o *stub* vira dívida imediata.

Pontos de atenção:

- A matemática de vencimento (horas de voo / calendário / ciclos, prorrogações,
  histórico de execução) é a lógica mais intrincada do núcleo — 66 controles ativos,
  5 tipos de controle. É o principal candidato a *golden test* (§11.1c).
- `inspecoes` traz **892 LOC de geração de PDF** com `reportlab` → `pdfkit` (§5.1).
  Orçar isso separado: relatório em PDF é trabalho de layout, não de tradução de lógica,
  e é a parte da Etapa 2 que menos se beneficia de assistência de IA.
- `inspecoes` importa `panes.service.sincronizar_status_aeronave`. Como a Etapa 1 já
  portou essa função, a integração é direta — foi o motivo de a decisão D-02 mapear
  `inspecoes` desde o MVP.

### 15.2. Etapa 3 — extras  ⏱ 2 a 3 semanas  🟢 **opcional**

`pedidos` (808 LOC, 10 rotas), `calendario` (762, 8), `encarregado` (636, 3),
`dashboard` (608, 2), `efetivo` (182, 4). Majoritariamente CRUD sobre padrões já
estabelecidos. `dashboard` depende de vencimentos e inspeções, por isso entra depois
deles.

Frontend mobile / PWA (7 rotas + 7 templates + JS próprio): 1 a 2 semanas.

**Nenhum destes bloqueia o uso do sistema.** Podem ser migrados um a um, conforme a
necessidade aparecer, ou nunca.

### 15.3. Etapa 4 — Publicações  🟢 **opcional, e possivelmente nunca**

Publicações **não é um módulo a migrar; é uma decisão de arquitetura** — e, sendo extra
(§2.4), é uma decisão que pode simplesmente não ser tomada. Números: 4.780 LOC, 34 rotas,
3,5 GB de PDF em 40.178 arquivos, índice de busca de 450 MB, 13.077 documentos indexados,
indexação por `pypdfium2` com CPU de longa duração, jobs de upload com multipart e
recuperação de processo interrompido.

Existe um quarto caminho que as versões anteriores deste documento não consideravam,
e que hoje é o mais provável: **manter Publicações no sistema Python atual,
indefinidamente.** O módulo é autocontido do ponto de vista do usuário (consulta de
manual), roda bem onde está, e é o único que justificaria manter infraestrutura extra.
Migrá-lo é opcional em um sentido forte — não "adiado", mas possivelmente desnecessário.

A parte de **leitura** (consultar manual, buscar texto, abrir o visualizador) roda sem
problema na hospedagem: os índices `catalog.*.db` já são abertos somente-leitura com
`sqlite3` puro, e o acervo cabe nos 50 GB com o CDN à frente. O que não roda é a
**ingestão**. Três caminhos:

| Caminho | Como | Prós | Contras |
| :--- | :--- | :--- | :--- |
| **A — Não migrar** ✅ *provável* | Publicações continua no Python atual, no endereço atual | Custo zero; nenhum dos problemas do §3 entra no projeto | Dois sistemas visíveis para o usuário |
| **B — Índice offline** | Acervo e índice vão para a hospedagem; a indexação roda na máquina do operador e o `catalog.<rotulo>.db` é enviado pronto | Sistema único; leitura 100% preservada | 3–4 semanas; publicar edição vira procedimento manual |
| **C — Híbrido** | Acervo e índice na VPS/R2; o app consulta por API | Mantém o upload automatizado | Mantém uma VPS — anula a economia |

Se o objetivo for sistema único, o caminho é **B**, ao custo de 3 a 4 semanas mais a
construção do procedimento offline de indexação que substitui os jobs de upload. Se o
objetivo for custo e simplicidade, **A** resolve melhor.

Decidir depois de o núcleo estar em produção — não antes.

---

## Apêndice A — Registro de decisões desta versão

| # | Decisão | Justificativa | Seção |
| :-- | :--- | :--- | :--- |
| D-01 | MVP restrito a Panes + Auth + Aeronaves | Publicações inviabiliza hospedagem compartilhada; Panes é o núcleo do produto | §1.2, §4 |
| D-02 | `inspecoes` entra como tabela somente-leitura | Preserva a regra de status da frota sem arrastar 26 rotas | §4.4 |
| D-03 | Drizzle em vez de Prisma | Controle de codec de coluna e ausência de motor binário | §5.2 |
| D-04 | Todo trabalho periódico vira cron HTTP | Processo não é confiável em hospedagem compartilhada | §3.1 |
| D-05 | Alembic não é portado; `alembic_version` fica intocada | Preserva rollback para o Python | §6.6 |
| D-06 | Conversão de HEIC sai do servidor | `sharp` pré-compilado não decodifica HEIC | §3.2 |
| D-07 | Fase 0 obrigatória antes de qualquer código | Evita descobrir inviabilidade depois de semanas | §10 |
| D-08 | Nomes de cookie e header preservados | Frontend é reaproveitado sem alteração | §7.1, §7.2 |
| D-09 | Um processo único, sem cluster | Segurança de escrita no SQLite; volume não exige paralelismo | §3.3 |
| D-10 | Migração é tradução, não refatoração | Divergência "melhorada" vira issue pós-cutover | §11.2 |
| D-11 | Testes portados antes do código, nas Fases 2–4 | 118 correções documentadas no código parecem redundância para quem lê de fora; a suíte é o que permite traduzir rápido sem regredir | §10.0, §13.1 |
| D-12 | Escopo do projeto é o **núcleo** (panes, inspeções, vencimentos); o resto é opcional | Definição do dono do projeto. Reduz a migração de 20.044 para 12.268 LOC e remove todos os problemas de infraestrutura, que pertencem a `publicacoes` | §2.4, §1.2 |
| D-13 | `equipamentos` e `vencimentos` migram como uma unidade | Dependência mútua real entre os dois módulos — migrar em sequência exige *stub* | §2.4, §15.1 |
| D-14 | `publicacoes` pode nunca ser migrado | É extra, é 24% da superfície, e é a origem de todo o atrito com hospedagem compartilhada | §15.3 |

## Apêndice B — Arquivos-fonte de referência

Ao portar cada área, ler o arquivo Python correspondente **antes** de escrever o Node:

| Área | Arquivos |
| :--- | :--- |
| Hash de senha e JWT | `app/modules/auth/security.py` |
| Login, lockout, refresh | `app/modules/auth/service.py`, `app/modules/auth/router.py` |
| Papéis e permissões | `app/modules/auth/roles.py`, `app/bootstrap/dependencies.py` |
| Regras de pane | `app/modules/panes/service.py` (952 linhas — a mais densa do MVP) |
| Rotas de pane | `app/modules/panes/router.py` |
| Status da frota | `app/modules/panes/service.py:110-166` |
| Validação de upload | `app/shared/core/file_validators.py` |
| Storage local/R2 | `app/shared/core/storage.py` |
| Pipeline de imagem | `app/shared/services/image/converter.py`, `app/bootstrap/config/image.py` |
| Export CSV/XLSX | `app/shared/exporter.py` |
| CSRF | `app/shared/middleware/csrf.py` |
| Cabeçalhos / CSP | `app/shared/middleware/security.py` |
| PRAGMAs de banco | `app/bootstrap/database.py` |
| Roteamento de erro 401/403 | `app/bootstrap/main.py:57-76`, `app/shared/core/exceptions.py` |
| Configuração | `app/bootstrap/config/__init__.py`, `.env.example` |

---

*Fim da especificação — v2.0, 21/08/2026.*
*Toda afirmação factual sobre o sistema atual foi conferida contra o código e o banco
nesta data. Ao atualizar este documento, reconferir — números de rota, contagem de
tabela e caminho de arquivo mudam.*
