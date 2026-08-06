# Especificação Técnica — Módulo `publicacoes`

> Este documento é o nível de detalhe que torna a execução direta: modelo de dados coluna a coluna,
> rotas com assinatura, RBAC por endpoint, variáveis de ambiente, layout de arquivos. Consolida o
> desenho do `opus_plano_de_incorporacao.md` (§6) **corrigido pelos achados** de
> `01_achados_do_acervo.md` e segue as convenções obrigatórias mapeadas em
> `docs/backlog/00_mapa_arquitetural.md`.
>
> Convenção de nomenclatura do módulo (herdada do parecer §6.0, inalterada): módulo = `publicacoes`;
> acervo A (manuais do DVD) = tabelas `manuais_*`; acervo B (avulsas) = tabelas
> `publicacoes_avulsas*`; transversal = `publicacoes_favoritos`, `publicacoes_acessos`.

---

## 0.1 Correções após a implementação (M0–M4 + Fase 0)

Esta especificação foi escrita **antes** de o módulo existir. Três pontos dela deixaram de ser
verdade durante a execução. O texto original de cada seção afetada foi corrigido no lugar; esta
lista existe para que quem já conhecia o documento saiba **o que mudou** sem reler tudo.

| O que a spec dizia | O que vale hoje | Onde |
|---|---|---|
| Piloto do M1 sobre `docs/fim/`, 411 PDFs versionados no repositório | `docs/fim/` **não existe mais** — os PDFs saíram do versionamento (`chore(docs): remove o acervo de PDFs do FIM`). O conteúdo vive em `var/publicacoes/acervo/Manuais/FIM_1741/`; o repositório guarda só uma amostra de 4 arquivos em `tests/fixtures/fim/`, para o CI, e o mapa `docs/fim.json` | §1, §7 |
| Um `catalog.db` único em `PUBLICACOES_INDEX_PATH`, trocado por `os.replace()` na ativação de edição | **Um índice por edição** (`catalog.<rotulo>.db`), e a edição `VIGENTE` no banco decide qual a busca abre. Ativar é um `UPDATE`, não uma troca de arquivo | §2.4, §7 |
| `search.buscar` lê `get_settings().publicacoes_index_path` direto | `search.buscar` recebe um `Path` de quem chama; o router resolve por `service.caminho_indice_vigente(db)` | §2.4 |
| `POST /publicacoes/api/edicoes/{id}/reverter` como rota própria | **Não existe, por decisão.** Reverter é ativar a edição `ANTERIOR`, pelo mesmo `POST .../ativar` — um caminho de código, um conjunto de testes, e nenhuma dúvida sobre o que "reverter" faz quando há mais de uma edição anterior retida. A UI é que rotula o botão como "Reverter" | §3 |
| `GET /publicacoes/manuais/{manual_path}` e `.../{capitulo}` | **Implementadas** (Etapa 2 de [`09_plano_configuracoes.md`](../backlog/modulo_publicacoes/09_plano_configuracoes.md)). O parâmetro é `{codigo}` (`manuais.codigo`), não `{manual_path}` como a spec original chamava: o `path` é caminho de disco e não pertence a uma URL. `capitulo == ""` (a raiz do manual, caso do `piloto-fim`) usa o sentinela de URL `_raiz_`, porque um segmento de path vazio não roteia | §3 |

A segunda e a quarta linhas são **reversões de decisão**; a segunda está registrada no adendo do
[ADR-004](../../architecture/adr/004-modulo-publicacoes.md). A primeira e a terceira são
consequência de uma decisão externa ao módulo (tirar o acervo do git) e da própria segunda.

> **Auditoria de rotas — faça no fecho de cada marco.** A §3 abaixo é o contrato, mas nenhum gate a
> confere: os gates olham a lista de tarefas. Foi assim que duas rotas especificadas ficaram quatro
> marcos sem existir. Compare a §3 com a realidade:
>
> ```bash
> python -c "
> import app.bootstrap.main as m
> for r in sorted({(r.path, ','.join(sorted(r.methods-{'HEAD','OPTIONS'}))) for r in m.app.routes if getattr(r,'methods',None) and r.path.startswith(('/publicacoes','/m/publicacoes'))}):
>     print(r)
> "
> ```

---

## 1. Layout de arquivos

```
app/modules/publicacoes/
├── __init__.py          # docstring, como app/modules/aeronaves/__init__.py
├── models.py             # manuais_* + publicacoes_avulsas* (Alembic)
├── schemas.py             # Pydantic: XCreate / XUpdate / XOut / XListItem / FiltroX
├── service.py             # funções async module-level; db: AsyncSession como 1º parâmetro
├── search.py               # camada isolada de busca — sqlite3 puro contra catalog.db
├── catalog.py               # parser do índice Lucene (02_formato_indice_lucene.md) + fim.json
├── avulsas.py                 # regras específicas de BO/BS/NPO/BT (cadastro, vigência, substituição)
└── router.py                    # APIRouter() sem prefix/tags — main.py define

app/web/templates/publicacoes/
├── lista.html            # home do módulo: busca unificada + índice dos manuais
├── manual.html            # ⚪ capítulos de um manual — Etapa 2 do 09
├── capitulo.html           # ⚪ documentos de um capítulo — Etapa 2 do 09
│                            #   (a spec original previa um manual.html só para os
│                            #    dois níveis; são duas rotas, então são dois templates)
├── avulsas.html             # lista/filtros de BO/BS/NPO/BT
└── viewer.html               # PDF.js, canvas, âncora #page=N

app/web/static/js/
├── publicacoes.js
├── publicacoes_avulsas.js
├── mobile/publicacoes_mobile.js
└── pdfjs/                # vendorizado — CSP não permite CDN (docs/methodology/CSP.md)

scripts/publicacoes/
├── __init__.py           # OBRIGATÓRIO — o script importa de `app.*` e roda como
│                          # `python -m scripts.publicacoes.indexar`. Precedente:
│                          # scripts/__init__.py e scripts/seed/__init__.py existem
│                          # (scripts/db/ não tem, e é a exceção, não o padrão).
├── indexar.py            # indexação OFFLINE — extrai texto por página (pypdfium2) + enriquece
│                          # com catalog.py (Lucene). Aceita qualquer diretório de entrada;
│                          # o padrão é var/publicacoes/acervo/Manuais. (A entrada `docs/fim/`
│                          # do M1 não existe mais — ver §0.1.)
├── publicar.py            # M4 — estação de publicação: inventário, diff por hash, extração
│                          # incremental, snapshot ZIP, relatório
└── merge_data.py            # M4 — merge de novas remessas no acervo existente (RN-08)

tests/unit/
├── test_publicacoes.py
├── test_publicacoes_catalog.py    # parser Lucene + fim.json, com fixtures reais
└── test_publicacoes_avulsas.py     # cadastro, vigência, substituição, RBAC
tests/integration/
└── test_publicacoes_busca.py       # inclui o round-trip de UUID entre os dois bancos (§2.2.1)
tests/security/
└── test_publicacoes_xss.py         # snippet com HTML hostil na ementa (§3.1)
```

> `ruff.toml` aplica `per-file-ignores` a `scripts/**` (`E402`, `ASYNC221`, `ASYNC240`) — os
> scripts deste módulo herdam isso automaticamente, sem precisar de entrada nova. Já o código em
> `app/modules/publicacoes/` está sob as regras plenas, incluindo **`ASYNC`** (I/O bloqueante
> dentro de `async def` reprova o gate) e **`S`** (bandit — `S608` reprova SQL montado por
> f-string).

---

## 2. Modelo de dados

### 2.1 Banco principal (Alembic, `saa29_local.db`, dentro do ciclo de backup R2)

```python
# app/modules/publicacoes/models.py
from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Text, Integer, Boolean, Date, DateTime, ForeignKey, Enum, func,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import (
    TipoPublicacao, StatusPublicacaoAvulsa, StatusEdicao, RevisionStatus,
)

if TYPE_CHECKING:
    from app.modules.panes.models import SistemaAta
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario
```

#### `manuais_edicoes` — controle de versão do acervo (M4; tabela existe desde o M0 para não exigir migration extra depois)

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK | `default=uuid.uuid4` |
| `rotulo` | `String(20)` | ex. `"2027"`; `unique=True` |
| `data_publicacao` | `DateTime(timezone=True)` | quando foi publicada no SAA29 |
| `snapshot_key` | `String(255)` nullable | chave do ZIP no R2 |
| `hash_sha256` | `String(64)` | hash do snapshot inteiro |
| `status` | `Enum(StatusEdicao, native_enum=False, length=20)` | `AGUARDANDO_ATIVACAO \| VIGENTE \| ANTERIOR \| ARQUIVADA` |
| `publicado_por_id` | UUID FK → `usuarios.id`, `ondelete="RESTRICT"`, `index=True` | |
| `relatorio_diff` | `Text` nullable | markdown do relatório de diff (§8.5 do parecer) |
| `created_at`/`updated_at` | auditoria padrão | |

#### `manuais` — um manual dentro de uma edição

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK | |
| `edicao_id` | UUID FK → `manuais_edicoes.id`, `ondelete="CASCADE"`, `index=True` | |
| `codigo` | `String(40)` | ex. `"FIM_1741"`, `"AMM_PART1_1651"` — nome do diretório |
| `descricao_pt` | `String(200)` | do Lucene quando houver, senão do `codigo` tratado |
| `categoria` | `String(60)` | de `categorias_manuais.toml` (RN-04 reformulada, ver §2.3) |
| `path` | `String(255)` | caminho relativo dentro do acervo |
| `revisao` | `String(10)` nullable | |
| `revisao_data` | `Date` nullable | |
| `created_at`/`updated_at` | auditoria padrão | |

`__table_args__`: `UniqueConstraint("edicao_id", "codigo", name="uq_manuais_edicao_codigo")`.

#### `manuais_documentos` — um PDF

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK — **determinístico**, ver §2.2 | |
| `manual_id` | UUID FK → `manuais.id`, `ondelete="CASCADE"`, `index=True` | |
| `capitulo` | `String(80)` | último segmento de `chapter` (Lucene) ou do diretório físico |
| `ata_codigo` | `String(4)` nullable, `index=True` — **SEM FK** (achado B3: o acervo tem 28 capítulos ATA e `sistemas_ata` só tem 8 seedados; uma FK falharia na indexação de 20 dos 28 capítulos). Join com `sistemas_ata.codigo` feito em query, quando o código existir lá | extraído do nome/capítulo quando aplicável |
| `file_key` | `String(500)` | caminho relativo ao `PUBLICACOES_ACERVO_DIR` |
| `titulo` | `String(300)` | RN-02: Lucene → nome de arquivo tratado (sem sidecar `.title`, ver `01_achados_do_acervo.md` §2) |
| `sort_order` | `Integer` | prefixo numérico do nome de arquivo (RN-05) |
| `paginas` | `Integer` nullable | preenchido na indexação |
| `has_text` | `Boolean` default `True` | E-01 |
| `revision_status` | `Enum(RevisionStatus, native_enum=False, length=20)` | `UNCHANGED \| REVISED \| NOVO \| DESCONHECIDO` — os 6 valores do Lucene mapeados em 4 (`01_achados_do_acervo.md` §3.3): `U`→`UNCHANGED`, `R`→`REVISED`, `N`→`NOVO`, `0`/`1`/`2` e ausência→`DESCONHECIDO` |
| `hash_sha256` | `String(64)` | para dedup entre edições (§5.1 do parecer) |
| `created_at`/`updated_at` | auditoria padrão | |

`__table_args__`: `UniqueConstraint("manual_id", "file_key", name="uq_manuais_documentos_manual_file")`.

#### `manuais_fim_map` — mensagem de falha → procedimento (piloto M1)

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK | |
| `mensagem` | `String(20)` | ex. `"ADC 001"` — de `fim.json` |
| `procedimento` | `String(30)` | ex. `"34-15-00-810-801-A"` |
| `documento_id` | UUID FK → `manuais_documentos.id`, nullable, `ondelete="SET NULL"` | `NULL` quando o procedimento não tem PDF correspondente (4/253 no piloto, 0/253 no acervo completo — `01_achados_do_acervo.md` §6.1) |

`__table_args__`: `UniqueConstraint("mensagem", name="uq_manuais_fim_map_mensagem")` — uma mensagem
mapeia para no máximo um procedimento. **Verificado na revisão de pré-implementação:** as 1.377
entradas de `fim.json` têm 1.377 mensagens únicas — zero duplicatas — então a constraint é segura
contra o dado real, não só contra a suposição.

#### `publicacoes_avulsas` — BO/BS/NPO/BT

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK | |
| `tipo` | `Enum(TipoPublicacao, native_enum=False, length=10)` | `BO \| BS \| NPO \| BT \| OUTRO` |
| `numero` | `String(60)` | ex. `"BS 314-24-0021"` |
| `ano` | `Integer`, `index=True` | |
| `data_emissao` | `Date` | |
| `data_recebimento` | `Date` | a que conta para o esquadrão (§9.2 do parecer) |
| `emissor` | `String(100)` | |
| `titulo` | `String(300)` | |
| `ementa` | `Text` | **campo mais valioso** — obrigatório, comprimento mínimo (ver §5 abaixo, R15 do parecer) |
| `sistema_ata_id` | UUID FK → `sistemas_ata.id` nullable, `ondelete="RESTRICT"`, `index=True` | reusa tabela de `app.modules.panes.models` |
| `status` | `Enum(StatusPublicacaoAvulsa, native_enum=False, length=15)` | `VIGENTE \| CANCELADO \| SUBSTITUIDO` |
| `substituida_por_id` | UUID FK → `publicacoes_avulsas.id` nullable, `ondelete="SET NULL"` | autorreferente |
| `ativo` | `Boolean` default `True`, `index=True` | soft delete, padrão do resto do sistema |
| `cadastrada_por_id` | UUID FK → `usuarios.id`, `ondelete="RESTRICT"` | |
| `created_at`/`updated_at` | auditoria padrão | |

`__table_args__`: `UniqueConstraint("tipo", "numero", "ano", name="uq_publicacoes_avulsas_tipo_numero_ano")`.

#### `publicacao_avulsa_anexos`

| Coluna | Tipo | Regra |
|---|---|---|
| `id` | UUID PK | |
| `avulsa_id` | UUID FK → `publicacoes_avulsas.id`, `ondelete="CASCADE"`, `index=True` | |
| `file_key` | `String(500)` | retorno de `StorageService.upload()` |
| `nome_original` | `String(255)` | |
| `tamanho_bytes` | `Integer` | |
| `principal` | `Boolean` default `False` | qual anexo abre por padrão |
| `created_at` | auditoria | sem `updated_at` — anexo é imutável, se errado é reenviado como novo |

#### `publicacao_avulsa_aeronaves` — aplicabilidade N:N

| Coluna | Tipo |
|---|---|
| `avulsa_id` | UUID FK → `publicacoes_avulsas.id`, `ondelete="CASCADE"`, PK composta |
| `aeronave_id` | UUID FK → `aeronaves.id`, `ondelete="CASCADE"`, PK composta |

Ausência de linhas para uma `avulsa_id` = aplicável à frota inteira (§9.2 do parecer).

#### `publicacoes_favoritos` / `publicacoes_acessos` (transversais)

> **Correção da revisão de pré-implementação** (`07_revisao_pre_implementacao.md` achado B1): o
> desenho anterior usava PK composta com colunas nullable — **inválido**: coluna de PRIMARY KEY
> não pode ser nullable em SQL padrão (falha no Postgres; no SQLite "funciona" por quirk
> histórico e permite duplicatas silenciosas). Redesenhado com PK surrogate + XOR por
> CheckConstraint + duas UniqueConstraints (NULLs são distintos em UNIQUE tanto no SQLite quanto
> no Postgres, então as duplicatas reais são bloqueadas e os NULLs não conflitam).

```python
class PublicacaoFavorito(Base):
    __tablename__ = "publicacoes_favoritos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manuais_documentos.id", ondelete="CASCADE"), nullable=True)
    avulsa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publicacoes_avulsas.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        CheckConstraint(
            "(documento_id IS NULL) != (avulsa_id IS NULL)",
            name="ck_publicacoes_favoritos_alvo_unico",
        ),
        UniqueConstraint("usuario_id", "documento_id", name="uq_publicacoes_favoritos_usuario_documento"),
        UniqueConstraint("usuario_id", "avulsa_id", name="uq_publicacoes_favoritos_usuario_avulsa"),
    )

class PublicacaoAcesso(Base):
    __tablename__ = "publicacoes_acessos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    # SET NULL + snapshot do título: a auditoria precisa SOBREVIVER à remoção do documento
    # (E-08) e ao descarte de edições antigas — com CASCADE, cada reindexação que removesse
    # um documento apagaria silenciosamente o histórico de quem o consultou (achado B4).
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("manuais_documentos.id", ondelete="SET NULL"), nullable=True, index=True)
    documento_titulo: Mapped[str] = mapped_column(String(300),
        comment="Snapshot do título no momento do acesso — legível mesmo após remoção do documento")
    edicao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("manuais_edicoes.id", ondelete="RESTRICT"))
    pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
```

Auditoria de acesso (RBAC.md §4: "toda ação crítica deve ser auditável"); `edicao_id` fecha a
rastreabilidade "qual revisão estava em vigor quando" (§8.6 do parecer). Favoritos mantêm
`ondelete="CASCADE"` deliberadamente — favorito de documento removido **deve** sumir; auditoria
de documento removido **não deve**. Regra complementar: **edições nunca são hard-deletadas do
banco** — `ARQUIVADA` remove apenas artefatos de disco/R2 (PDFs, `catalog.db` da edição), nunca
as linhas de catálogo, que são minúsculas e sustentam as FKs da auditoria.

### 2.2 `document_id` determinístico (CA-07)

> **Correção da revisão de pré-implementação** (achado B2): a versão anterior derivava o UUID só
> de `manual_codigo/file_key`. Com duas edições retidas online (M4, §8.6 do parecer), o **mesmo
> arquivo existe nas duas edições** — mesma entrada → mesmo UUID → **colisão de PK** em
> `manuais_documentos` na primeira publicação anual. A edição entra no input.

```python
import uuid

# Constante do módulo — nunca gerar aleatoriamente, nunca mudar depois do primeiro índice.
_NAMESPACE_PUBLICACOES = uuid.UUID("6f5a1c9e-6a3b-4b1a-9f0e-2c8d4a7b1e3f")

def documento_id_deterministico(edicao_rotulo: str, manual_codigo: str, file_key: str) -> uuid.UUID:
    """
    UUID v5 derivado de (edição, manual, caminho relativo) — estável entre
    reindexações DA MESMA edição, distinto entre edições.
    """
    return uuid.uuid5(_NAMESPACE_PUBLICACOES, f"{edicao_rotulo}/{manual_codigo}/{file_key}")
```

Esse mesmo ID é usado como `document_id` em `pages` (`catalog.db`, §2.4) — o indexador grava os dois
lados de forma determinística, sem precisar de uma tabela de mapeamento intermediária.

**Leitura correta do CA-07 com a edição no ID.** O critério externo diz: *"link compartilhado
continua abrindo o mesmo documento após reindexação **sem mudança no arquivo**"* — reindexar a
mesma edição produz o mesmo rótulo e o mesmo ID ✅. Quando uma edição **nova** é ativada, os
links antigos continuam resolvendo — para o documento da edição antiga, que permanece online como
`ANTERIOR` (§8.6 do parecer). Isso não é violação do CA-07: é exatamente a rastreabilidade que a
manutenção aeronáutica precisa ("a pane de março seguiu o procedimento da edição vigente em
março"). A UI do viewer deve exibir o banner `REVISÃO ANTERIOR` com link para o equivalente
vigente quando houver (casamento por `manual_codigo + file_key`).

### 2.2.1 Contrato de identidade entre os dois bancos (achado B5)

**Medido nesta revisão:** o tipo `Uuid` do SQLAlchemy armazena UUIDs no SQLite como **hex de 32
caracteres SEM hífens** (`9a6a262f6c5948bc...`), enquanto `str(uuid.UUID(...))` produz a forma
canônica **COM hífens** (`9a6a262f-6c59-48bc-...`). Uma comparação de strings crua entre o que
está no `catalog.db` e o que está no banco principal **falha silenciosamente** — zero resultados,
sem erro.

Contrato obrigatório:

1. `catalog.db` grava `document_id` sempre como `str(uuid)` — forma canônica, com hífens;
2. todo código que leva um `document_id` do `catalog.db` para uma query ORM converte **antes**
   com `uuid.UUID(valor)` — o construtor aceita ambas as formas e normaliza;
3. **nunca** comparar strings de UUID entre os dois bancos sem passar por `uuid.UUID()`;
4. teste de integração obrigatório cobrindo o round-trip busca → `catalog.db` → lookup no banco
   principal (é o teste que pega esse bug se alguém violar o contrato).

### 2.3 `categorias_manuais.toml` (RN-04 reformulada)

Sem `manual_type.xml` (achado #2), a categorização vira um mapa estático mantido no repositório —
o parecer já previa isso como saída para D-01 (rótulos provisórios):

```toml
# config/categorias_manuais.toml
[AMM_PART1_1651]
categoria = "Manutenção"
descricao_pt = "AMM Parte I — Manual de Manutenção (SDS)"

[AMM_PART2_1651]
categoria = "Manutenção"
descricao_pt = "AMM Parte II — Manual de Manutenção (MPP)"

[FIM_1741]
categoria = "Manutenção"
descricao_pt = "FIM — Manual de Pesquisa de Panes"

[AIPC_1742]
categoria = "Peças"
descricao_pt = "AIPC — Catálogo Ilustrado de Peças"

# ... demais 30 manuais — ver 01_achados_do_acervo.md §1.1 para a lista completa,
# incluindo os 17 OTFN* (categoria "Ordens Técnicas")

[_default]
categoria = "Outros"
descricao_pt = "{codigo}"   # fallback E-04
```

`PUBLICACOES_CATEGORIAS_PATH` aponta para este arquivo (§4). Preenchido incrementalmente — um
manual sem entrada cai em `[_default]`, nunca quebra a indexação.

### 2.4 `catalog.<edicao>.db` — índice de busca (SQLite dedicado, fora do Alembic)

> **Duas correções da revisão de pré-implementação** (achados B6 e B7), ambas verificadas por
> execução real de SQLite nesta sessão. O esquema anterior **não conseguiria atender o contrato
> da API** (filtro por manual/capítulo era impossível) e **devolveria zero resultados
> silenciosamente** (FTS5 de conteúdo externo não se popula sozinho).
>
> **Um arquivo por edição.** O nome é `catalog.<rotulo>.db`, no diretório de
> `PUBLICACOES_INDEX_PATH` — `catalog.2026.db`, `catalog.piloto-fim.db`, lado a lado. Qual deles a
> busca abre é decidido pela edição `VIGENTE` em `manuais_edicoes`, resolvido por
> `service.caminho_indice_vigente(db)` a cada consulta. O esquema abaixo é idêntico em todos.
> Consequência prática: publicar uma edição nova **não** toca o índice da edição em vigor, e
> ativar/reverter não move arquivo nenhum. Ver §0.1 e o adendo do ADR-004.

```sql
-- gerado por scripts/publicacoes/indexar.py — NUNCA por migration Alembic

-- Cópia desnormalizada do mínimo necessário para FILTRAR e EXIBIR sem sair
-- do catalog.db. Sem ela, os filtros `manual`/`chapter` do contrato da API
-- (§3.1) são inimplementáveis: catalog.db e o banco principal são engines
-- distintas, não há JOIN entre eles (achado B6).
CREATE TABLE documents (
    document_id   TEXT PRIMARY KEY,   -- str(uuid) canônico, com hífens (§2.2.1)
    manual_codigo TEXT NOT NULL,
    capitulo      TEXT NOT NULL,
    titulo        TEXT NOT NULL,      -- evita N+1 no banco principal para montar o resultado
    categoria     TEXT NOT NULL
);
CREATE INDEX ix_documents_manual   ON documents(manual_codigo);
CREATE INDEX ix_documents_capitulo ON documents(capitulo);

CREATE TABLE pages (
    document_id TEXT NOT NULL,   -- mesmo UUID de manuais_documentos.id, como texto
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (document_id, page_number)
);
CREATE INDEX ix_pages_document ON pages(document_id);

CREATE VIRTUAL TABLE pages_fts USING fts5(
    text,
    content='pages',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
```

#### ⚠️ FTS5 de conteúdo externo NÃO se popula sozinho (achado B7)

Com `content='pages'`, o FTS5 **não indexa nada** ao inserir em `pages` — e a armadilha é que
`SELECT count(*) FROM pages_fts` **devolve o número certo** (ele lê através da tabela de
conteúdo), então um teste de fumaça ingênuo passa enquanto **toda busca retorna zero**.
Comportamento medido nesta revisão:

| Momento | `count(*) FROM pages_fts` | `MATCH 'sangria'` |
|---|---:|---:|
| Após inserir 2 páginas em `pages` | **2** ✅ (engana) | **0** 🔴 |
| Após `INSERT INTO pages_fts(pages_fts) VALUES('rebuild')` | 2 | **2** ✅ |

**Regra obrigatória:** ao final da carga, o indexador executa o rebuild e o `optimize`:

```python
conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")
conn.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
conn.commit()
```

E o teste de aceite do índice **nunca** valida por contagem — valida por busca real
(`MATCH` devolvendo linha conhecida). Contagem é exatamente a métrica que não pega este bug.

#### Query de referência (verificada)

```sql
SELECT p.document_id, p.page_number, d.manual_codigo, d.capitulo, d.titulo,
       snippet(pages_fts, 0, '<mark>', '</mark>', '…', 20) AS snippet,
       bm25(pages_fts) AS score
FROM pages_fts
JOIN pages     p ON p.rowid = pages_fts.rowid
JOIN documents d ON d.document_id = p.document_id
WHERE pages_fts MATCH ?
  AND (? IS NULL OR d.manual_codigo = ?)
ORDER BY score ASC          -- bm25() do SQLite é NEGATIVO: mais negativo = mais relevante
LIMIT ? OFFSET ?;
```

Verificado por execução: `ORDER BY bm25() ASC` coloca o mais relevante primeiro (corpus de teste
com 52 documentos: termo 4× em texto curto → `-5.5080`; termo 1× em texto longo → `-0.3785`).
Ordenar `DESC` inverteria o ranking inteiro — e passaria despercebido em qualquer teste que só
verifique "veio resultado".

**Semântica de `total` no contrato (§3.1):** é a contagem de **páginas** que casam, não de
documentos — coerente com o contrato externo, em que cada `result` é uma página. Um documento com
o termo em 3 páginas contribui 3 para `total` e gera 3 entradas em `results`.

**E-01 sai de graça:** documentos sem camada de texto simplesmente não geram linhas em `pages`,
então nunca aparecem na busca full-text — mas continuam em `documents`, logo seguem navegáveis e
visíveis no viewer, que é exatamente o comportamento que E-01 exige.

Aberto em runtime **apenas com `sqlite3` da biblioteca padrão**, nunca com SQLAlchemy/
`create_async_engine` — motivo em `01_achados_do_acervo.md` §7.3 (listener global de backup R2).

```python
# app/modules/publicacoes/search.py — esqueleto
import asyncio
import sqlite3
from pathlib import Path

def _abrir_catalog_ro(caminho: Path) -> sqlite3.Connection:
    # Conexão criada E usada dentro da mesma chamada de to_thread — sem
    # check_same_thread=False, que só serviria para compartilhar conexão
    # entre threads, exatamente o que este desenho evita.
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# `caminho` vem de fora: search.py não sabe o que é uma edição. Quem chama
# resolve com `service.caminho_indice_vigente(db)` — ver §0.1.
async def buscar(caminho: Path, query: str, *, manual: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    def _run() -> dict:
        conn = _abrir_catalog_ro(caminho)
        try:
            # bm25(), snippet() com <mark>, RN-10: sanitizar a query ANTES de
            # montar a expressão MATCH — e SEMPRE via bind parameter:
            #   conn.execute("... WHERE pages_fts MATCH ? ...", (query_sanitizada,))
            # Nunca interpolar a query do usuário em f-string SQL (ruff S608
            # está ativo em app/ e reprova; e é injeção de sintaxe FTS mesmo
            # com sanitização).
            ...
        finally:
            conn.close()
    return await asyncio.to_thread(_run)
```

Precedente de `sqlite3` em modo somente-leitura já existe no repositório:
`scripts/maintenance/r2_manager.py:122` (`sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)`).

**Por que abrir conexão por consulta (e não cachear):** além de eliminar qualquer questão de
thread-safety, é o que torna a **ativação de edição imediata** — cada edição tem seu
`catalog.<rotulo>.db` e o chamador resolve qual abrir a cada consulta, então a busca seguinte à
ativação já abre o arquivo da edição nova. Uma conexão cacheada quebraria isso silenciosamente
(continuaria servindo o índice antigo). O custo de abertura (~1 ms para um SQLite local) é
irrelevante frente ao alvo de p95 < 300 ms.

> **Revisão:** este parágrafo justificava a regra pelo `os.replace(catalog_novo.db, catalog.db)`
> previsto originalmente. Aquele mecanismo foi descartado — status no banco e arquivo em disco
> mudavam em momentos diferentes, e reverter exigia mover o arquivo de volta. Motivo completo no
> adendo do [ADR-004](../../architecture/adr/004-modulo-publicacoes.md). A regra em si continua
> valendo, e ficou **mais** necessária, não menos.

---

## 3. Rotas

Todo endpoint JSON vive sob `/publicacoes/api/...` — **um único sub-prefixo**, para que
`API_PREFIXES` registre `"/publicacoes/api/"` sem capturar as páginas HTML
(`01_achados_do_acervo.md` §7.5).

> **Legenda de situação** (conferida em 06/08/2026 — ver a auditoria em §0.1): ✅ existe ·
> ⚪ especificada e **ainda não implementada** · ⚠️ substituída por decisão registrada em §0.1.

| Rota | Tipo | RBAC | Situação | Observação |
|---|---|---|:--:|---|
| `GET /publicacoes` | HTML | `CurrentUser` | ✅ | home: busca unificada + índice "Navegar no acervo" por categoria (Etapa 2) |
| `GET /publicacoes/manuais/{codigo}` | HTML | `CurrentUser` | ✅ | capítulos — Etapa 2 do `09`, renderizada direto do `service` |
| `GET /publicacoes/manuais/{codigo}/{capitulo}` | HTML | `CurrentUser` | ✅ | documentos, paginados por `?offset=`/`?limit=` — Etapa 2 do `09`. `capitulo == ""` (raiz) usa o sentinela de URL `_raiz_` (`CAPITULO_RAIZ_SLUG`), já que um segmento de path vazio não roteia |
| `GET /publicacoes/api/manuais` | JSON | `CurrentUser` | ✅ | catálogo de manuais da edição vigente — Etapa 2 do `09` |
| `GET /publicacoes/api/manuais/{codigo}/capitulos` | JSON | `CurrentUser` | ✅ | Etapa 2 do `09` |
| `GET /publicacoes/api/manuais/{codigo}/documentos` | JSON | `CurrentUser` | ✅ | paginado, filtro opcional por `capitulo` — Etapa 2 do `09` |
| `GET /publicacoes/viewer/{doc_id}` | HTML | `CurrentUser` | ✅ | PDF.js; âncora `#page=N` |
| `GET /publicacoes/avulsas` | HTML | `CurrentUser` | ✅ | lista + filtros |
| `GET /m/publicacoes` | HTML | `CurrentUser` | ✅ | atalho mobile (`mobile_router.py`) |
| `GET /publicacoes/api/busca` | JSON | `CurrentUser` | ✅ | contrato preservado da `Especificacao.MD` §4 |
| `GET /publicacoes/api/fim` | JSON | `CurrentUser` | ✅ | busca por mensagem de falha (`fim.json`) |
| `GET /publicacoes/api/status` | JSON | `CurrentUser` | ✅ | versão do índice, contagens, `documentos_sem_texto` |
| `GET /publicacoes/api/avulsas` | JSON | `CurrentUser` | ✅ | busca nos metadados |
| `POST /publicacoes/api/avulsas` | JSON | `EncarregadoInspetorOuAdmin` | ✅ | cadastro |
| `PATCH /publicacoes/api/avulsas/{id}` | JSON | `EncarregadoInspetorOuAdmin` | ✅ | correção / vigência |
| `DELETE /publicacoes/api/avulsas/{id}` | JSON | `AdminRequired` | ✅ | soft delete |
| `POST /publicacoes/api/avulsas/{id}/anexos` | multipart | `EncarregadoInspetorOuAdmin` | ✅ | limite próprio (§5) |
| `GET /publicacoes/api/edicoes` | JSON | `AdminRequired` | ✅ | M4 — edições, status, diff |
| `POST /publicacoes/api/edicoes/{id}/ativar` | JSON | `AdminRequired` | ✅ | M4 — troca de ponteiro |
| `POST /publicacoes/api/edicoes/{id}/reverter` | JSON | `AdminRequired` | ⚠️ | **substituída**: reverter = ativar a `ANTERIOR` pelo mesmo `/ativar` (§0.1) |
| `GET /publicacoes/doc/{doc_id}/pdf` | binário | `CurrentUser` | ✅ | `FileResponse` com Range, `asyncio.to_thread` para o `stat()` (padrão de `panes/router.py:395`) |
| `GET /publicacoes/avulsas/{id}/anexo/{anexo_id}` | binário | `CurrentUser` | ✅ | idem |

**Ordem de declaração:** rotas estáticas (`/publicacoes/manuais`, `/publicacoes/avulsas`,
`/publicacoes/viewer`, `/publicacoes/doc`) sempre **antes** de qualquer rota com
`{manual_path}`/`{doc_id}` no mesmo nível, conforme convenção verificada em
`equipamentos/router.py:194-195`.

### 3.1 Contrato de `GET /publicacoes/api/busca` (preservado da `Especificacao.MD` §4)

```json
{
  "query": "sangria do compressor",
  "total": 142,
  "took_ms": 12,
  "results": [
    {
      "doc_id": "3f9a...",
      "title": "SUBJECT 75-30-00 - SANGRIA DO COMPRESSOR",
      "manual": {"path": "AMM_PART1_1651", "description": "SDS - Manual de Manutenção da Aeronave"},
      "chapter": "CHAPTER_75",
      "page": 3,
      "snippet": "...a válvula de <mark>sangria</mark> do <mark>compressor</mark> deve...",
      "viewer_url": "/publicacoes/viewer/3f9a...#page=3"
    }
  ]
}
```

Diferença deliberada em relação ao contrato externo: `doc_id` é UUID (string), não inteiro
autoincrement, porque `manuais_documentos.id` é UUID (§2.2) — o resto do contrato é idêntico.
`pdf_url` do contrato externo não é exposto — o cliente usa `viewer_url`, que já resolve para
`GET /publicacoes/doc/{doc_id}/pdf` internamente no viewer.

`400` se `q` vazio ou sintaxe FTS inválida — a sanitização (RN-10) acontece **antes** de montar a
query MATCH, nunca deixando o SQLite devolver erro de sintaxe como 500 (E-06).

#### ⚠️ O `snippet` é o único ponto do sistema que quebra a regra do `escapeHtml` (achado B8)

Todo o frontend do SAA29 passa 100% dos dados por `escapeHtml` antes de montar DOM
(`app.js:223`). O `snippet` **precisa** conter `<mark>` renderizado como HTML — mas o texto ao
redor vem de PDF e, no caso das avulsas, da **ementa digitada por usuário**. As duas saídas
ingênuas estão erradas:

| Abordagem | Resultado |
|---|---|
| `escapeHtml(snippet)` | `&lt;mark&gt;` literal na tela — realce quebrado |
| `innerHTML = snippet` com `<mark>` vindo do SQLite | 🔴 **XSS** — verificado: um `<img src=x onerror=alert(1)>` dentro do texto executa |

**Solução obrigatória — sentinela + escape + troca** (verificada por execução nesta revisão):

```sql
-- no SQL: delimitadores são caracteres de controle, não HTML
snippet(pages_fts, 0, char(2), char(3), '…', 20) AS snippet
```

```javascript
// no JS: escapa TUDO primeiro, só então converte os sentinelas em <mark>
const seguro = escapeHtml(r.snippet)
    .replaceAll('\x02', '<mark>')
    .replaceAll('\x03', '</mark>');
celula.innerHTML = seguro;   // única exceção justificada ao escapeHtml no projeto
```

Resultado medido com texto hostil: `procedimento &lt;img src=x onerror=alert(1)&gt;
<mark>sangria</mark> do compressor` — tag neutralizada, realce preservado. Um `\x02` que por
acaso existisse no PDF produziria no máximo um `<mark>` órfão, que é inofensivo.

Teste de segurança obrigatório em `tests/security/`: cadastrar avulsa cuja ementa contenha
`<img src=x onerror=...>`, buscar por um termo dela e afirmar que a resposta serializada **não
contém** `<img`.

### 3.2 Guardas de endpoint (adicionadas na revisão de pré-implementação)

| Guarda | Onde | Regra |
|---|---|---|
| **Rate limit** | `GET /publicacoes/api/busca` e `POST .../avulsas/{id}/anexos` | `@limiter.limit("30/minute")` na busca, `@limiter.limit("10/minute")` no upload (mesmo valor do upload de panes). O decorator **exige `request: Request` na assinatura** (`app/shared/core/limiter.py`; precedente em `panes/router.py:107-112`). O mapa arquitetural §7.5 aponta a escassez de rate limit como risco estrutural — este módulo não amplia o débito. Precedentes reais hoje: `auth/router.py:47,128,422` + `panes/router.py:107` |
| **Bounds de paginação** | todos os endpoints de listagem/busca | `limit: int = Query(default=20, ge=1, le=100)`, `offset: int = Query(default=0, ge=0)` — e guarda no service (`LIMITE_MAXIMO_LISTAGEM`, precedente `inspecoes/service.py:36`), porque o service também é chamado por scripts que não passam pelo Query |
| **Shadowing de `status`** | filtro de avulsas | `status_filtro: StatusPublicacaoAvulsa \| None = Query(default=None, alias="status")` — nunca nomear o parâmetro `status`, que sombreia `fastapi.status` importado no router (trap real documentado em `panes/router.py:71-75`) |
| **Timezone** | qualquer comparação de datetime com payload de API | Se surgir comparação de datetimes tz-aware lidos do banco com valores do payload, copiar o `UTCDateTime(TypeDecorator)` de `calendario/models.py:21-46` — o SQLite descarta tzinfo e a comparação naïve×aware lança `TypeError` |

---

## 4. Schemas (excerto — `app/modules/publicacoes/schemas.py`)

```python
from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
import uuid

from app.shared.core.enums import TipoPublicacao, StatusPublicacaoAvulsa


class ManualRef(BaseModel):
    """Bloco `manual` do contrato externo — modelo próprio em vez de dict solto,
    para que o response_model valide de fato e apareça no OpenAPI."""
    path: str
    description: str


class ResultadoBusca(BaseModel):
    doc_id: uuid.UUID
    title: str
    manual: ManualRef
    chapter: str
    page: int | None
    snippet: str      # contém <mark>…</mark> — ver nota de segurança abaixo
    viewer_url: str


class RespostaBusca(BaseModel):
    query: str
    total: int        # nº de PÁGINAS que casam, não de documentos (§2.4)
    took_ms: int
    results: list[ResultadoBusca]


class PublicacaoAvulsaCreate(BaseModel):
    tipo: TipoPublicacao
    numero: str = Field(..., max_length=60)
    ano: int = Field(..., ge=1990, le=2100)
    data_emissao: date
    data_recebimento: date
    emissor: str = Field(..., max_length=100)
    titulo: str = Field(..., max_length=300)
    ementa: str = Field(..., min_length=20, description="Campo mais valioso — mínimo de caracteres por ser o principal insumo de busca (R15)")
    sistema_ata_id: uuid.UUID | None = None
    aplicabilidade: list[uuid.UUID] = Field(default_factory=list)  # aeronave_id; vazio = frota inteira


class PublicacaoAvulsaUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=300)
    ementa: str | None = Field(default=None, min_length=20)
    status: StatusPublicacaoAvulsa | None = None
    substituida_por_id: uuid.UUID | None = None


class PublicacaoAvulsaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: TipoPublicacao
    numero: str
    ano: int
    data_emissao: date
    data_recebimento: date
    emissor: str
    titulo: str
    ementa: str
    status: StatusPublicacaoAvulsa
    sistema_ata_id: uuid.UUID | None
    substituida_por_id: uuid.UUID | None
    created_at: datetime


class PublicacaoAvulsaListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: TipoPublicacao
    numero: str
    ano: int
    titulo: str
    status: StatusPublicacaoAvulsa
```

Naming `XCreate`/`XUpdate`/`XOut`/`XListItem` — convenção majoritária do projeto, **não**
`XResponse` (`docs/backlog/00_mapa_arquitetural.md`, achado do agente de exploração desta sessão).

---

## 5. Enums novos — `app/shared/core/enums.py`

```python
class TipoPublicacao(str, enum.Enum):
    BO = "BO"
    BS = "BS"
    NPO = "NPO"
    BT = "BT"
    OUTRO = "OUTRO"

class StatusPublicacaoAvulsa(str, enum.Enum):
    VIGENTE = "VIGENTE"
    CANCELADO = "CANCELADO"
    SUBSTITUIDO = "SUBSTITUIDO"

class StatusEdicao(str, enum.Enum):
    AGUARDANDO_ATIVACAO = "AGUARDANDO_ATIVACAO"
    VIGENTE = "VIGENTE"
    ANTERIOR = "ANTERIOR"
    ARQUIVADA = "ARQUIVADA"

class RevisionStatus(str, enum.Enum):
    """Estado de revisão do documento, vindo do campo `revision` do índice Lucene."""
    UNCHANGED = "UNCHANGED"        # 'U' — 2.256 documentos
    REVISED = "REVISED"            # 'R' — 3.266 documentos
    NOVO = "NOVO"                  # 'N' —   181 documentos
    DESCONHECIDO = "DESCONHECIDO"  # '0'/'1'/'2' (14) + sem entrada no índice (5)
```

Os quatro enums seguem `str, enum.Enum` e são armazenados com
`Enum(X, native_enum=False, length=N)` — nunca tipo enum nativo do Postgres, mantendo a
portabilidade que o projeto já paga para ter.

---

## 6. Variáveis de ambiente

Acrescentar em `app/bootstrap/config/__init__.py` sob um novo bloco `# --- Módulo Publicações ---`
(mesmo padrão dos blocos existentes) e no `.env.example`:

```python
# app/bootstrap/config/__init__.py — novos campos em Settings
publicacoes_acervo_dir: str = Field(default="var/publicacoes/acervo", description="Diretório dos PDFs — dev e produção (VPS com disco persistente)")
publicacoes_index_path: str = Field(default="var/publicacoes/catalog.db", description="SQLite do índice de busca — fora do DATABASE_URL. Dois papéis: o DIRETÓRIO hospeda os índices por edição (catalog.<rotulo>.db, que é o que a busca abre); o arquivo em si é o índice legado, só fallback")
publicacoes_categorias_path: str = Field(default="config/categorias_manuais.toml", description="Mapa estático de categoria/descrição por manual — substitui manual_type.xml ausente")
publicacoes_avulsas_max_upload_mb: float = Field(default=50.0, description="Limite de anexo das avulsas — separado de max_upload_size_mb, que é 0.5MB e não muda")
publicacoes_edicoes_retidas: int = Field(default=2, description="M4 — vigente + anterior online")
publicacoes_snapshots_retidos: int = Field(default=3, description="M4 — snapshots ZIP no R2")
```

```env
# .env.example — bloco novo, mesmo padrão dos existentes
# --- Módulo Publicações ---
PUBLICACOES_ACERVO_DIR=var/publicacoes/acervo
PUBLICACOES_INDEX_PATH=var/publicacoes/catalog.db
PUBLICACOES_CATEGORIAS_PATH=config/categorias_manuais.toml
PUBLICACOES_AVULSAS_MAX_UPLOAD_MB=50
PUBLICACOES_EDICOES_RETIDAS=2
PUBLICACOES_SNAPSHOTS_RETIDOS=3
```

**Duas variáveis do parecer foram removidas na revisão de pré-implementação** (achados S1/S2 de
`07_revisao_pre_implementacao.md`):

- **`PUBLICACOES_ENABLED`** — a motivação original ("subir com o módulo desligado até o acervo
  estar disponível") morreu com a Revisão 5: o acervo já está no disco e o desenvolvimento é
  local. O que a flag custaria: registro condicional de rotas complica o boot e os testes (o app
  é instância de módulo criada no import), e o item de nav viraria link morto quando desligada.
  O que ela protegeria já é coberto por construção: `catalog.db` ausente → `/api/status` reporta
  índice ausente e a UI mostra estado vazio (E-12).
- **`PUBLICACOES_MODO`** — a flag guardava "rotas de ingestão" que **não existem em nenhum
  marco**: a estação de publicação é um script (`publicar.py`), e ativar/reverter são rotas
  admin que *devem* existir no servidor. Uma flag que não guarda nada é configuração morta.
  Reintroduzir apenas se o M4 algum dia criar rotas de ingestão de verdade.

Também fora (motivo inalterado desde a versão anterior): `PUBLICACOES_STORAGE` e
`PUBLICACOES_R2_PREFIX` — previstas para o espelho R2 do acervo (M4, depende de D-04); declarar
env var antes de usá-la só faz o `extra="ignore"` do Settings mascarar um nome errado.

---

## 7. RBAC — matriz consolidada

| Ação | Mant | Enc | Insp | Adm |
|---|:--:|:--:|:--:|:--:|
| Navegar catálogo / buscar / abrir PDF (ambos os acervos) | ✅ | ✅ | ✅ | ✅ |
| Ver status do índice | ✅ | ✅ | ✅ | ✅ |
| Cadastrar/editar publicação avulsa | ❌ | ✅ | ✅ | ✅ |
| Excluir publicação avulsa (soft delete) | ❌ | ❌ | ❌ | ✅ |
| Publicar/ativar/reverter edição de manuais (M4) | ❌ | ❌ | ❌ | ✅ |

Dependências: `EncarregadoInspetorOuAdmin` (já existe, `dependencies.py:159`) para cadastro/edição
de avulsas; `AdminRequired` para exclusão e para tudo do M4.

---

## 8. Referências cruzadas

- Convenções de módulo, service, router, migration: `docs/backlog/00_mapa_arquitetural.md` e os
  exemplos vivos em `app/modules/aeronaves/` (mais canônico) e `app/modules/inspecoes/` (melhor
  disciplina de `domain_exc`).
- RBAC: `docs/architecture/RBAC.md`, `app/bootstrap/dependencies.py:110-165`.
- CSP: `docs/methodology/CSP.md` — qualquer alargamento (`worker-src`, `img-src blob:`) documentado
  na mesma PR que o introduz.
- Formato do índice Lucene: `02_formato_indice_lucene.md`.
- Base factual de todos os números citados aqui: `01_achados_do_acervo.md`.
