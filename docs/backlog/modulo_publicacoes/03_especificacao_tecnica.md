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
├── lista.html            # home do módulo: busca unificada nos dois acervos
├── manual.html            # capítulos → documentos de um manual
├── avulsas.html             # lista/filtros de BO/BS/NPO/BT
└── viewer.html               # PDF.js, canvas, âncora #page=N

app/web/static/js/
├── publicacoes.js
├── publicacoes_avulsas.js
├── mobile/publicacoes_mobile.js
└── pdfjs/                # vendorizado — CSP não permite CDN (docs/methodology/CSP.md)

scripts/publicacoes/
├── indexar.py            # indexação OFFLINE — extrai texto por página (pypdfium2) + enriquece
│                          # com catalog.py (Lucene). Aceita qualquer diretório de entrada:
│                          # docs/fim/ no M1, var/publicacoes/acervo/ a partir do M4.
├── publicar.py            # M4 — estação de publicação: inventário, diff por hash, extração
│                          # incremental, snapshot ZIP, relatório
└── merge_data.py            # M4 — merge de novas remessas no acervo existente (RN-08)

tests/unit/
├── test_publicacoes.py
├── test_publicacoes_catalog.py    # parser Lucene + fim.json, com fixtures reais
└── test_publicacoes_avulsas.py     # cadastro, vigência, substituição, RBAC
tests/integration/
└── test_publicacoes_busca.py
```

---

## 2. Modelo de dados

### 2.1 Banco principal (Alembic, `saa29_local.db`, dentro do ciclo de backup R2)

```python
# app/modules/publicacoes/models.py
from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, Date, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import TipoPublicacao, StatusPublicacaoAvulsa, StatusEdicao

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
| `ata_codigo` | `String(4)` nullable, FK → `sistemas_ata.codigo` opcional (reusa tabela de `panes`) | extraído do nome/capítulo quando aplicável |
| `file_key` | `String(500)` | caminho relativo ao `PUBLICACOES_ACERVO_DIR` |
| `titulo` | `String(300)` | RN-02: Lucene → nome de arquivo tratado (sem sidecar `.title`, ver `01_achados_do_acervo.md` §2) |
| `sort_order` | `Integer` | prefixo numérico do nome de arquivo (RN-05) |
| `paginas` | `Integer` nullable | preenchido na indexação |
| `has_text` | `Boolean` default `True` | E-01 |
| `revision_status` | `Enum(..., native_enum=False, length=20)` | `UNCHANGED \| REVISED \| NOVO \| DESCONHECIDO` — 6 valores do Lucene mapeados em 4 (`01_achados_do_acervo.md` §3.3) |
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
mapeia para no máximo um procedimento (é assim que `fim.json` está estruturado).

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

```python
class PublicacaoFavorito(Base):
    __tablename__ = "publicacoes_favoritos"
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manuais_documentos.id", ondelete="CASCADE"), primary_key=True, nullable=True)
    avulsa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publicacoes_avulsas.id", ondelete="CASCADE"), primary_key=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

class PublicacaoAcesso(Base):
    __tablename__ = "publicacoes_acessos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("manuais_documentos.id", ondelete="CASCADE"), index=True)
    edicao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("manuais_edicoes.id", ondelete="RESTRICT"))
    pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
```

Auditoria de acesso (RBAC.md §4: "toda ação crítica deve ser auditável"); `edicao_id` fecha a
rastreabilidade "qual revisão estava em vigor quando" (§8.6 do parecer).

### 2.2 `document_id` determinístico (CA-07)

```python
import hashlib
import uuid

def documento_id_deterministico(manual_codigo: str, file_key: str) -> uuid.UUID:
    """
    UUID v5 derivado do caminho relativo do arquivo — estável entre
    reindexações, desde que o arquivo não mude de nome/posição.
    Namespace fixo do módulo, nunca gerado aleatoriamente.
    """
    namespace = uuid.UUID("6f5a1c9e-6a3b-4b1a-9f0e-2c8d4a7b1e3f")  # constante do módulo
    return uuid.uuid5(namespace, f"{manual_codigo}/{file_key}")
```

Esse mesmo ID é usado como `document_id` em `pages` (`catalog.db`, §2.4) — o indexador grava os dois
lados de forma determinística, sem precisar de uma tabela de mapeamento intermediária.

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

### 2.4 `catalog.db` — índice de busca (SQLite dedicado, fora do Alembic)

```sql
-- gerado por scripts/publicacoes/indexar.py — NUNCA por migration Alembic
CREATE TABLE pages (
    document_id TEXT NOT NULL,   -- mesmo UUID de manuais_documentos.id, como texto
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (document_id, page_number)
);
CREATE VIRTUAL TABLE pages_fts USING fts5(
    text,
    content='pages',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
```

Aberto em runtime **apenas com `sqlite3` da biblioteca padrão**, nunca com SQLAlchemy/
`create_async_engine` — motivo em `01_achados_do_acervo.md` §7.3 (listener global de backup R2).

```python
# app/modules/publicacoes/search.py — esqueleto
import asyncio
import sqlite3
from pathlib import Path

def _abrir_catalog_ro(caminho: Path) -> sqlite3.Connection:
    uri = f"file:{caminho}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

async def buscar(query: str, *, manual: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    def _run() -> dict:
        conn = _abrir_catalog_ro(Path(get_settings().publicacoes_index_path))
        try:
            # bm25(), snippet() com <mark>, RN-10: sanitizar query antes de passar ao MATCH
            ...
        finally:
            conn.close()
    return await asyncio.to_thread(_run)
```

Precedente de `sqlite3` em modo somente-leitura já existe no repositório:
`scripts/maintenance/r2_manager.py:122` (`sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)`).

---

## 3. Rotas

Todo endpoint JSON vive sob `/publicacoes/api/...` — **um único sub-prefixo**, para que
`API_PREFIXES` registre `"/publicacoes/api/"` sem capturar as páginas HTML
(`01_achados_do_acervo.md` §7.5).

| Rota | Tipo | RBAC | Observação |
|---|---|---|---|
| `GET /publicacoes` | HTML | `CurrentUser` | home: busca unificada nos dois acervos |
| `GET /publicacoes/manuais/{manual_path}` | HTML | `CurrentUser` | capítulos |
| `GET /publicacoes/manuais/{manual_path}/{capitulo}` | HTML | `CurrentUser` | documentos |
| `GET /publicacoes/viewer/{doc_id}` | HTML | `CurrentUser` | PDF.js; âncora `#page=N` |
| `GET /publicacoes/avulsas` | HTML | `CurrentUser` | lista + filtros |
| `GET /m/publicacoes` | HTML | `CurrentUser` | atalho mobile (`mobile_router.py`) |
| `GET /publicacoes/api/busca` | JSON | `CurrentUser` | contrato preservado da `Especificacao.MD` §4 |
| `GET /publicacoes/api/fim` | JSON | `CurrentUser` | busca por mensagem de falha (`fim.json`) |
| `GET /publicacoes/api/status` | JSON | `CurrentUser` | versão do índice, contagens, `documentos_sem_texto` |
| `GET /publicacoes/api/avulsas` | JSON | `CurrentUser` | busca nos metadados |
| `POST /publicacoes/api/avulsas` | JSON | `EncarregadoInspetorOuAdmin` | cadastro |
| `PATCH /publicacoes/api/avulsas/{id}` | JSON | `EncarregadoInspetorOuAdmin` | correção / vigência |
| `DELETE /publicacoes/api/avulsas/{id}` | JSON | `AdminRequired` | soft delete |
| `POST /publicacoes/api/avulsas/{id}/anexos` | multipart | `EncarregadoInspetorOuAdmin` | limite próprio (§5) |
| `GET /publicacoes/api/edicoes` | JSON | `AdminRequired` | M4 — edições, status, diff |
| `POST /publicacoes/api/edicoes/{id}/ativar` | JSON | `AdminRequired` | M4 — troca de ponteiro |
| `POST /publicacoes/api/edicoes/{id}/reverter` | JSON | `AdminRequired` | M4 |
| `GET /publicacoes/doc/{doc_id}/pdf` | binário | `CurrentUser` | `FileResponse` com Range, `asyncio.to_thread` para o `stat()` (padrão de `panes/router.py:395`) |
| `GET /publicacoes/avulsas/{id}/anexo/{anexo_id}` | binário | `CurrentUser` | idem |

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

---

## 4. Schemas (excerto — `app/modules/publicacoes/schemas.py`)

```python
from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
import uuid

from app.shared.core.enums import TipoPublicacao, StatusPublicacaoAvulsa


class ResultadoBusca(BaseModel):
    doc_id: uuid.UUID
    title: str
    manual: dict[str, str]
    chapter: str
    page: int | None
    snippet: str
    viewer_url: str


class RespostaBusca(BaseModel):
    query: str
    total: int
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
```

---

## 6. Variáveis de ambiente

Acrescentar em `app/bootstrap/config/__init__.py` sob um novo bloco `# --- Módulo Publicações ---`
(mesmo padrão dos blocos existentes) e no `.env.example`:

```python
# app/bootstrap/config/__init__.py — novos campos em Settings
publicacoes_enabled: bool = Field(default=True, description="Liga/desliga o módulo sem remover rotas do código — registro condicional em main.py")
publicacoes_modo: str = Field(default="consulta", description="consulta | publicacao — publicacao NUNCA é o default; ver 04_plano_de_execucao.md M4")
publicacoes_acervo_dir: str = Field(default="var/publicacoes/acervo", description="Diretório dos PDFs — dev e produção (VPS com disco persistente)")
publicacoes_index_path: str = Field(default="var/publicacoes/catalog.db", description="SQLite dedicado do índice de busca — fora do DATABASE_URL")
publicacoes_categorias_path: str = Field(default="config/categorias_manuais.toml", description="Mapa estático de categoria/descrição por manual — substitui manual_type.xml ausente")
publicacoes_avulsas_max_upload_mb: float = Field(default=50.0, description="Limite de anexo das avulsas — separado de max_upload_size_mb, que é 0.5MB e não muda")
publicacoes_edicoes_retidas: int = Field(default=2, description="M4 — vigente + anterior online")
publicacoes_snapshots_retidos: int = Field(default=3, description="M4 — snapshots ZIP no R2")
```

```env
# .env.example — bloco novo, mesmo padrão dos existentes
# --- Módulo Publicações ---
PUBLICACOES_ENABLED=true
PUBLICACOES_MODO=consulta                          # consulta | publicacao (M4)
PUBLICACOES_ACERVO_DIR=var/publicacoes/acervo
PUBLICACOES_INDEX_PATH=var/publicacoes/catalog.db
PUBLICACOES_CATEGORIAS_PATH=config/categorias_manuais.toml
PUBLICACOES_AVULSAS_MAX_UPLOAD_MB=50
PUBLICACOES_EDICOES_RETIDAS=2
PUBLICACOES_SNAPSHOTS_RETIDOS=3
```

Removidos do desenho original do parecer: `PUBLICACOES_STORAGE` e `PUBLICACOES_R2_PREFIX` — o
parecer os previa para a alternativa "espelho R2 do acervo completo", que é trabalho do M4 e
depende de D-04. Ficam registrados aqui como extensão futura, não como env var declarada antes de
serem usadas (evita `extra="ignore"` mascarar um nome errado).

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
