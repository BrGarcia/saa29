# 🚀 Plano de Implementação — Integração Hermes Agente × SAA29

> **Feature:** `feature_hermes_api`  
> **Branch proposta:** `feature/hermes-api-integration`  
> **Base:** `development`  
> **Objetivo:** Expor dados operacionais do SAA29 para consumo pelo agente Hermes via API REST Read-Only, autenticada por Service Token, com suporte a Function Calling e busca semântica (RAG) em manuais técnicos.

---

## 📐 Visão Geral da Arquitetura

```text
┌──────────────────────────────────────────────────────┐
│                     HERMES AGENTE                    │
│  (LLM + Function Calling + RAG)                      │
└────────────┬──────────────────────┬──────────────────┘
             │ HTTP/JSON            │ Embedding Query
             ▼                      ▼
┌────────────────────┐   ┌─────────────────────────┐
│  SAA29 API Gateway │   │  Vector DB (ChromaDB)    │
│  /api/hermes/v1/*  │   │  Manuais Técnicos A-29   │
│  (Read-Only)       │   └─────────────────────────┘
└────────┬───────────┘
         │ Service Token Auth
         ▼
┌────────────────────────────────────────┐
│         SAA29 — Módulos Existentes     │
│  aeronaves │ panes │ equipamentos      │
│  vencimentos │ inspecoes │ efetivo     │
└────────────────────────────────────────┘
```

### Restrições Fundamentais
- **Hermes = SOMENTE LEITURA.** Nenhum endpoint de escrita, edição, exclusão ou aprovação.
- **Zero alteração nas regras de negócio existentes.** O módulo Hermes é completamente isolado.
- **Clean Architecture.** Novo módulo `app/modules/hermes/` com seu próprio router, schemas e service.
- **Alembic** para qualquer alteração estrutural no banco.

---

## 📁 Estrutura de Arquivos Proposta

```text
app/
├── modules/
│   └── hermes/                    ← [NOVO] Módulo isolado
│       ├── __init__.py
│       ├── router.py              ← Endpoints REST /api/hermes/v1/*
│       ├── schemas.py             ← Schemas Pydantic (response-only)
│       ├── service.py             ← Queries read-only otimizadas
│       ├── auth.py                ← Autenticação por Service Token
│       ├── function_schemas.py    ← JSON Schemas para Function Calling
│       └── rag/                   ← [FASE 4] Pipeline RAG
│           ├── __init__.py
│           ├── extractor.py       ← Extração de texto de PDFs/manuais
│           ├── embedder.py        ← Geração de embeddings
│           ├── vectorstore.py     ← Interface com ChromaDB
│           └── search.py          ← Endpoint de busca semântica
├── bootstrap/
│   ├── config/__init__.py         ← [MODIFY] Adicionar configs Hermes
│   └── main.py                    ← [MODIFY] Registrar hermes_router
└── shared/
    └── core/
        └── enums.py               ← [MODIFY] Adicionar role SERVICO_HERMES (se necessário)

var/
└── vectordb/                      ← [NOVO] Persistência ChromaDB local

alembic/
└── versions/
    └── xxxx_add_hermes_token.py   ← [NOVO] Migration para tabela de tokens

docs/
└── backlog/
    └── hermes/
        ├── openapi_hermes.yaml    ← [NOVO] Spec OpenAPI dos endpoints Hermes
        └── function_calling.json  ← [NOVO] Schemas para uso do agente
```

---

## 🔹 FASE 1 — API Read-Only (Endpoints REST)

### Objetivo
Criar endpoints REST exclusivos em `/api/hermes/v1/` que exponham dados operacionais em JSON tipado e enxuto, reutilizando as services existentes com queries otimizadas.

### Endpoints Planejados

| Método | Rota | Descrição | Módulo Fonte |
|--------|------|-----------|--------------|
| `GET` | `/api/hermes/v1/aeronaves` | Lista aeronaves com status e horas | `aeronaves` |
| `GET` | `/api/hermes/v1/aeronaves/{id}` | Detalhe de uma aeronave (+ panes abertas count) | `aeronaves` |
| `GET` | `/api/hermes/v1/aeronaves/{id}/inventario` | Equipamentos instalados na aeronave | `equipamentos` |
| `GET` | `/api/hermes/v1/panes` | Lista panes com filtros (status, aeronave, período) | `panes` |
| `GET` | `/api/hermes/v1/panes/{id}` | Detalhe de uma pane (descrição, responsáveis, sistema ATA) | `panes` |
| `GET` | `/api/hermes/v1/panes/estatisticas` | Resumo: total aberta/resolvida, por aeronave, por sistema ATA | `panes` |
| `GET` | `/api/hermes/v1/vencimentos` | Controles de vencimento com status (OK/VENCENDO/VENCIDO) | `vencimentos` |
| `GET` | `/api/hermes/v1/vencimentos/alertas` | Itens VENCENDO ou VENCIDOS (alerta proativo) | `vencimentos` |
| `GET` | `/api/hermes/v1/inspecoes` | Inspeções abertas/em andamento por aeronave | `inspecoes` |
| `GET` | `/api/hermes/v1/inspecoes/{id}` | Detalhe da inspeção com checklist e progresso | `inspecoes` |
| `GET` | `/api/hermes/v1/equipamentos/busca` | Busca de equipamentos por PN, SN ou nomenclatura | `equipamentos` |
| `GET` | `/api/hermes/v1/frota/resumo` | Dashboard consolidado: aeronaves por status, panes abertas, vencimentos críticos | `dashboard` |

### Schemas Pydantic (Response-Only)

Criar schemas enxutos que exponham apenas os campos necessários para o agente, **sem dados sensíveis** (sem IDs de usuários, sem hashes, sem tokens):

```python
# app/modules/hermes/schemas.py
class HermesAeronaveResumo(BaseModel):
    matricula: str
    modelo: str
    status: str
    horas_voo_total: float
    panes_abertas: int

class HermesPaneResumo(BaseModel):
    id: UUID
    aeronave_matricula: str
    sistema_ata: str | None
    descricao_curta: str
    status: str
    data_abertura: datetime
    data_conclusao: datetime | None

class HermesVencimentoAlerta(BaseModel):
    equipamento_pn: str
    equipamento_sn: str
    aeronave_matricula: str
    tipo_controle: str
    data_limite: date | None
    horas_limite: float | None
    status: str  # OK | VENCENDO | VENCIDO
```

### Implementação

#### [NEW] `app/modules/hermes/__init__.py`
Exportação do router.

#### [NEW] `app/modules/hermes/router.py`
- Prefixo: `/api/hermes/v1`
- Tag: `Hermes`
- Todas as rotas: `methods=["GET"]` exclusivamente
- Dependency global: `HermesAuth` (Service Token — Fase 2)
- Rate limiting via `slowapi` (ex: 60 req/min)

#### [NEW] `app/modules/hermes/service.py`
- Queries SQLAlchemy read-only otimizadas com `selectinload` onde aplicável
- Sem usar `db.add()`, `db.flush()`, `db.commit()` — NUNCA
- Paginação padrão (`limit`/`offset`) em listagens

#### [MODIFY] `app/bootstrap/main.py`
- Adicionar import e registro do `hermes_router` em `_register_routers()`

### Arquivos Afetados
| Arquivo | Ação | Estimativa |
|---------|------|-----------|
| `app/modules/hermes/__init__.py` | [NEW] | ~5 linhas |
| `app/modules/hermes/router.py` | [NEW] | ~200 linhas |
| `app/modules/hermes/schemas.py` | [NEW] | ~120 linhas |
| `app/modules/hermes/service.py` | [NEW] | ~250 linhas |
| `app/bootstrap/main.py` | [MODIFY] | +3 linhas |

### Critérios de Aceite — Fase 1
- [ ] Todos os 12 endpoints retornando JSON válido com dados reais
- [ ] Nenhum endpoint aceita POST/PUT/DELETE/PATCH
- [ ] Paginação funcionando em listagens
- [ ] Queries sem N+1 (validar com `echo=True`)
- [ ] Testes via `pytest` cobrindo cada endpoint

---

## 🔹 FASE 2 — Segurança (Service Token)

### Objetivo
Implementar autenticação por Service Token exclusivo para o Hermes, completamente separado do sistema de JWT/sessão dos usuários humanos.

### Mecanismo de Autenticação

```text
┌─────────────────────────────────────────────────────┐
│  Header: Authorization: Bearer <HERMES_SERVICE_TOKEN>│
│                                                      │
│  Token: hash SHA-256 de um secret gerado pelo admin  │
│  Armazenado na tabela `hermes_tokens`                │
│  Validação: hash(token recebido) == hash no banco    │
└─────────────────────────────────────────────────────┘
```

### Modelo de Dados

```python
# Nova tabela via Alembic
class HermesServiceToken(Base):
    __tablename__ = "hermes_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)          # Ex: "hermes-prod"
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)    # SHA-256 do token
    ativo: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### Implementação

#### [NEW] `app/modules/hermes/auth.py`
```python
async def get_hermes_client(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HermesServiceToken:
    """
    Dependency que valida o Service Token do Hermes.
    Rejeita qualquer requisição sem token válido e ativo.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Service token obrigatório")

    raw_token = auth_header.removeprefix("Bearer ").strip()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    result = await db.execute(
        select(HermesServiceToken)
        .where(HermesServiceToken.token_hash == token_hash)
        .where(HermesServiceToken.ativo == True)
    )
    hermes_client = result.scalar_one_or_none()
    if not hermes_client:
        raise HTTPException(403, "Token inválido ou desativado")

    if hermes_client.expires_at and hermes_client.expires_at < datetime.now(timezone.utc):
        raise HTTPException(403, "Token expirado")

    # Atualizar last_used_at
    hermes_client.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return hermes_client
```

#### [NEW] Migration Alembic
```bash
alembic revision --autogenerate -m "add hermes_tokens table"
alembic upgrade head
```

#### [MODIFY] `app/bootstrap/config/__init__.py`
- Adicionar `hermes_rate_limit: int = 60` (req/min)
- Adicionar `hermes_token_expire_days: int = 90`

### Utilitário para Gerar Token
Criar script `scripts/generate_hermes_token.py`:
```python
# Gera um token seguro, exibe o raw (para configurar no Hermes),
# e insere o hash SHA-256 na tabela hermes_tokens.
```

### Arquivos Afetados
| Arquivo | Ação | Estimativa |
|---------|------|-----------|
| `app/modules/hermes/auth.py` | [NEW] | ~60 linhas |
| `app/modules/hermes/models.py` | [NEW] | ~30 linhas |
| `alembic/versions/xxxx_hermes_tokens.py` | [NEW] | ~40 linhas |
| `app/bootstrap/config/__init__.py` | [MODIFY] | +3 linhas |
| `scripts/generate_hermes_token.py` | [NEW] | ~50 linhas |

### Critérios de Aceite — Fase 2
- [ ] Requisição sem token → 401
- [ ] Requisição com token inválido → 403
- [ ] Requisição com token expirado → 403
- [ ] Requisição com token válido → 200 + dados
- [ ] `last_used_at` atualizado a cada requisição
- [ ] Rate limiting funcionando (429 ao exceder)
- [ ] Nenhuma rota do Hermes acessível via JWT de usuário comum

---

## 🔹 FASE 3 — Function Calling (JSON Schema)

### Objetivo
Definir JSON Schemas padronizados para cada "ferramenta" (endpoint) que o Hermes pode invocar, compatíveis com o formato OpenAI Function Calling / Anthropic Tool Use.

### Schema de Ferramentas

#### [NEW] `app/modules/hermes/function_schemas.py`

```python
HERMES_TOOLS = [
    {
        "name": "buscar_aeronaves",
        "description": "Lista aeronaves da frota A-29 com status operacional e horas de voo.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["DISPONIVEL", "INDISPONIVEL", "INSPEÇÃO", "ESTOCADA", "INATIVA"],
                    "description": "Filtrar por status operacional"
                }
            },
            "required": []
        }
    },
    {
        "name": "buscar_panes",
        "description": "Consulta panes (ocorrências de falha) com filtros por aeronave, status e período.",
        "parameters": {
            "type": "object",
            "properties": {
                "aeronave_matricula": {"type": "string", "description": "Matrícula da aeronave (ex: 5916)"},
                "status": {"type": "string", "enum": ["ABERTA", "RESOLVIDA"]},
                "sistema_ata": {"type": "string", "description": "Código ATA do sistema (ex: 24, 32)"},
                "data_inicio": {"type": "string", "format": "date"},
                "data_fim": {"type": "string", "format": "date"},
                "limit": {"type": "integer", "default": 20, "maximum": 100}
            },
            "required": []
        }
    },
    {
        "name": "buscar_vencimentos_alertas",
        "description": "Retorna equipamentos com vencimento próximo (VENCENDO) ou ultrapassado (VENCIDO).",
        "parameters": {
            "type": "object",
            "properties": {
                "aeronave_matricula": {"type": "string"},
                "status": {"type": "string", "enum": ["VENCENDO", "VENCIDO"]}
            },
            "required": []
        }
    },
    {
        "name": "buscar_inventario_aeronave",
        "description": "Lista equipamentos instalados em uma aeronave específica com status de vencimentos.",
        "parameters": {
            "type": "object",
            "properties": {
                "aeronave_matricula": {"type": "string", "description": "Matrícula da aeronave"}
            },
            "required": ["aeronave_matricula"]
        }
    },
    {
        "name": "buscar_inspecoes",
        "description": "Consulta inspeções abertas ou em andamento por aeronave.",
        "parameters": {
            "type": "object",
            "properties": {
                "aeronave_matricula": {"type": "string"},
                "status": {"type": "string", "enum": ["ABERTA", "EM_ANDAMENTO", "CONCLUIDA"]}
            },
            "required": []
        }
    },
    {
        "name": "resumo_frota",
        "description": "Dashboard consolidado da frota: aeronaves por status, total de panes abertas e vencimentos críticos.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "buscar_equipamento",
        "description": "Busca equipamentos por Part Number, Serial Number ou nomenclatura.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca (PN, SN ou nome do equipamento)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "buscar_manual_tecnico",
        "description": "Busca semântica em manuais técnicos da aeronave A-29 (RAG).",
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "description": "Pergunta em linguagem natural sobre procedimentos ou especificações técnicas"}
            },
            "required": ["pergunta"]
        }
    }
]
```

### Endpoint de Descoberta

```python
# GET /api/hermes/v1/tools
# Retorna a lista de ferramentas disponíveis para o agente
@router.get("/tools", response_model=list[dict])
async def listar_ferramentas():
    return HERMES_TOOLS
```

### Dispatcher de Ferramentas

```python
# POST /api/hermes/v1/tools/execute
# Recebe { "name": "buscar_panes", "arguments": {...} }
# Despacha para a função correta e retorna o resultado

@router.post("/tools/execute")
async def executar_ferramenta(
    payload: ToolCallRequest,
    hermes: HermesServiceToken = Depends(get_hermes_client),
    db: DBSession = ...,
):
    dispatcher = {
        "buscar_aeronaves": service.listar_aeronaves,
        "buscar_panes": service.listar_panes,
        ...
    }
    fn = dispatcher.get(payload.name)
    if not fn:
        raise HTTPException(404, f"Ferramenta '{payload.name}' não encontrada")
    return await fn(db=db, **payload.arguments)
```

> ⚠️ **Nota:** O endpoint `/tools/execute` é o único POST permitido e não altera dados — apenas despacha para queries read-only.

### Arquivos Afetados
| Arquivo | Ação | Estimativa |
|---------|------|-----------|
| `app/modules/hermes/function_schemas.py` | [NEW] | ~150 linhas |
| `app/modules/hermes/router.py` | [MODIFY] | +40 linhas |
| `app/modules/hermes/schemas.py` | [MODIFY] | +20 linhas (ToolCallRequest/Response) |

### Critérios de Aceite — Fase 3
- [ ] `GET /tools` retorna lista completa de ferramentas
- [ ] `POST /tools/execute` despacha corretamente para cada ferramenta
- [ ] Ferramentas inexistentes → 404
- [ ] Parâmetros inválidos → 422 com erro descritivo
- [ ] Nenhuma ferramenta executa operações de escrita
- [ ] JSON Schema compatível com OpenAI Function Calling format

---

## 🔹 FASE 4 — Pipeline RAG (Busca Semântica em Manuais)

### Objetivo
Permitir ao Hermes consultar manuais técnicos da aeronave A-29 via busca semântica, utilizando vetorização de documentos e um Vector Database local.

### Stack Técnica
| Componente | Tecnologia | Justificativa |
|-----------|-----------|---------------|
| Extração de Texto | `PyMuPDF` (fitz) | Rápido, suporta PDFs complexos, sem dependências nativas pesadas |
| Embedding Model | `sentence-transformers/all-MiniLM-L6-v2` | Leve (~80MB), bom para português técnico, roda local sem API |
| Vector DB | `ChromaDB` | Persistência local em SQLite, sem infra adicional, API Pythonica |
| Chunking | Sliding window (512 tokens, overlap 64) | Equilíbrio entre contexto e granularidade |

### Pipeline de Ingestão

```text
PDF Manual ──► Extração (PyMuPDF) ──► Chunking ──► Embedding ──► ChromaDB
                                        │
                                        ▼
                               Metadados: {manual, capítulo, página, ATA}
```

### Implementação

#### [NEW] `app/modules/hermes/rag/extractor.py`
- Lê PDFs da pasta `var/manuais/` (ou configurável)
- Extrai texto página a página preservando estrutura
- Identifica capítulos ATA pelo padrão de cabeçalho

#### [NEW] `app/modules/hermes/rag/embedder.py`
- Carrega modelo sentence-transformers (lazy loading)
- Gera embeddings em batch
- Normaliza vetores para cosine similarity

#### [NEW] `app/modules/hermes/rag/vectorstore.py`
- Interface com ChromaDB (persistência em `var/vectordb/`)
- Collection: `manuais_a29`
- Métodos: `ingerir_documento()`, `buscar()`, `reindexar()`

#### [NEW] `app/modules/hermes/rag/search.py`
- Endpoint `GET /api/hermes/v1/manuais/busca?q=<pergunta>`
- Retorna top-K chunks relevantes com score, fonte e página

#### [MODIFY] `app/bootstrap/config/__init__.py`
```python
# Novas configurações
hermes_manuais_dir: str = "var/manuais"
hermes_vectordb_dir: str = "var/vectordb"
hermes_embedding_model: str = "all-MiniLM-L6-v2"
hermes_rag_top_k: int = 5
```

#### Script de Ingestão
```bash
# scripts/hermes_ingest_manuais.py
# Executar manualmente ou via task agendada para re-indexar manuais
python scripts/hermes_ingest_manuais.py --dir var/manuais/ --reindex
```

### Arquivos Afetados
| Arquivo | Ação | Estimativa |
|---------|------|-----------|
| `app/modules/hermes/rag/__init__.py` | [NEW] | ~5 linhas |
| `app/modules/hermes/rag/extractor.py` | [NEW] | ~100 linhas |
| `app/modules/hermes/rag/embedder.py` | [NEW] | ~80 linhas |
| `app/modules/hermes/rag/vectorstore.py` | [NEW] | ~120 linhas |
| `app/modules/hermes/rag/search.py` | [NEW] | ~60 linhas |
| `app/modules/hermes/router.py` | [MODIFY] | +20 linhas |
| `app/bootstrap/config/__init__.py` | [MODIFY] | +4 linhas |
| `scripts/hermes_ingest_manuais.py` | [NEW] | ~80 linhas |
| `requirements.txt` | [MODIFY] | +3 deps |

### Novas Dependências
```text
chromadb>=0.4.0
sentence-transformers>=2.2.0
pymupdf>=1.23.0
```

### Critérios de Aceite — Fase 4
- [ ] Manuais PDF ingeridos e indexados com sucesso
- [ ] Busca semântica retorna chunks relevantes com score > 0.5
- [ ] Metadados (manual, página, capítulo ATA) presentes nos resultados
- [ ] Re-indexação idempotente (não duplica documentos)
- [ ] Processamento em background (não bloqueia a API)

---

## 🔹 FASE 5 — Homologação

### Objetivo
Validar a integração end-to-end com testes automatizados, cenários de falha e auditoria de logs.

### Testes de Integração

#### [NEW] `tests/test_hermes_api.py`
```python
# Cenários obrigatórios:
# 1. Autenticação
test_acesso_sem_token_retorna_401()
test_acesso_com_token_invalido_retorna_403()
test_acesso_com_token_expirado_retorna_403()
test_acesso_com_token_valido_retorna_200()

# 2. Endpoints Read-Only
test_listar_aeronaves()
test_detalhe_aeronave()
test_inventario_aeronave()
test_listar_panes_com_filtros()
test_estatisticas_panes()
test_vencimentos_alertas()
test_resumo_frota()

# 3. Segurança Negativa
test_post_em_rota_get_retorna_405()
test_tentativa_escrita_via_execute_retorna_403()
test_rate_limit_excedido_retorna_429()

# 4. Function Calling
test_listar_ferramentas()
test_executar_ferramenta_valida()
test_executar_ferramenta_inexistente_retorna_404()
test_executar_com_parametros_invalidos_retorna_422()

# 5. RAG
test_busca_semantica_retorna_resultados()
test_busca_sem_resultados_retorna_lista_vazia()

# 6. Resiliência
test_timeout_em_query_longa()
test_token_desativado_apos_autenticacao()
```

#### [NEW] `tests/conftest.py` (fixtures Hermes)
- Fixture para criar `HermesServiceToken` de teste
- Fixture para popular dados mínimos (aeronave, pane, vencimento)

### Cenários de Resiliência
| Cenário | Comportamento Esperado |
|---------|----------------------|
| Token desativado mid-session | 403 na próxima requisição |
| Query que demora >30s | 504 Gateway Timeout |
| Rate limit excedido | 429 com header `Retry-After` |
| Vector DB indisponível | 503 com mensagem descritiva |
| PDF corrompido na ingestão | Log de erro, skip e continua |

### Checklist de Homologação
- [ ] Todos os testes `pytest` passando (100%)
- [ ] Nenhum endpoint do Hermes altera dados no banco (auditoria SQL)
- [ ] Logs de interação do Hermes registrados com `logging` (sem `print`)
- [ ] Rate limiting validado com teste de carga simples
- [ ] Documentação OpenAPI atualizada e acessível em `/docs` (debug mode)
- [ ] Nenhum impacto nos fluxos existentes do SAA29 (testes de regressão)

### Arquivos Afetados
| Arquivo | Ação | Estimativa |
|---------|------|-----------|
| `tests/test_hermes_api.py` | [NEW] | ~300 linhas |
| `tests/conftest.py` | [MODIFY] | +40 linhas |

---

## 📊 Cronograma de Execução

| Fase | Descrição | Dependência | Estimativa |
|:----:|-----------|:-----------:|:----------:|
| **1** | API Read-Only (12 endpoints) | — | 2–3 sessões |
| **2** | Service Token Auth + Alembic | Fase 1 | 1–2 sessões |
| **3** | Function Calling Schemas + Dispatcher | Fase 1 + 2 | 1 sessão |
| **4** | Pipeline RAG (extração + ChromaDB) | Fase 1 + 2 | 2–3 sessões |
| **5** | Homologação (testes + resiliência) | Todas | 1–2 sessões |

---

## 🛡️ Matriz de Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|:------------:|:-------:|-----------|
| N+1 queries nos endpoints Hermes | Alta | Performance | Usar `selectinload` e queries otimizadas desde a Fase 1 |
| Vazamento de dados sensíveis | Média | Segurança | Schemas response-only sem IDs de usuário, hashes ou tokens |
| Token Service comprometido | Baixa | Crítico | Rotação periódica, expiração configurável, log de uso |
| Modelo de embedding pesado demais | Média | Infra | Usar `all-MiniLM-L6-v2` (80MB) — leve e eficiente |
| PDFs de manuais com OCR ruim | Alta | Qualidade RAG | Fallback para extraction por imagem + tesseract se necessário |

---

*Plano de Implementação — Integração Hermes Agente × SAA29 — v1.0*
