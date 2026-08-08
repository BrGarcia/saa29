# 🛠️ Plano de Implementação — Módulo Central de Pedidos (`app/modules/pedidos/`)

> **Documento de Orientação Técnica para a Equipe de Desenvolvimento**
> **Versão:** 1.0  
> **Data:** 2026-08-08  
> **Baseado em:** `feature_controle_pedidos.md` (v1.3), `relatorio_v2.md` e `mockup_pedidos.html`  
> **Status:** 🟢 Aprovado para Execução  
> **Objetivo:** Fornecer um roteiro passo a passo detalhado, com trechos de código, contratos de API, schemas, regras de negócio e estratégia de testes para a construção do novo módulo **Central de Pedidos**.

---

## 1. Visão Geral da Arquitetura & Decisões de Design

O módulo **Central de Pedidos** gerencia o **ciclo administrativo e logístico** das solicitações de peças e equipamentos para as aeronaves da frota A-29.

### Principais Diretrizes Arquiteturais:
1. **Separação Rígida entre Pedido e Inventário (RN-12 / RN-14):**
   - Marcar um pedido como `ATENDIDO` é uma **ação administrativa/logística**.
   - O atendimento **não cria** registros na tabela `instalacoes` e **não altera** fisicamente o inventário. A baixa da pendência do slot ocorre **exclusivamente** quando o usuário registrar a instalação física no módulo de Inventário (`app/modules/equipamentos/`).
2. **Conformidade com a Stack do SAA29:**
   - **Backend:** FastAPI com endpoints assíncronos (`AsyncSession`, SQLAlchemy 2.0 com `Mapped[]` e `mapped_column()`).
   - **Persistência:** SQLite via `aiosqlite` (regra estrita do projeto: não adicionar PostgreSQL/outros SGBDs). Migrações via Alembic com suporte a `render_as_batch=True`.
   - **Segurança & RBAC:** Injeção da dependência anotada `EncarregadoInspetorOuAdmin` de `app/bootstrap/dependencies.py`. Registro obrigatório em `app/bootstrap/main.py` (`include_router` + lista `API_PREFIXES`).
   - **Front-end:** Template Jinja2 (`app/web/templates/pedidos.html`), JavaScript vanilla externo (`app/web/static/js/pedidos.js`) em conformidade estrita com CSP (`script-src 'self'`, sem scripts ou eventos inline), utilizando utilitários globais de `app.js` (`apiFetch`, `escapeHtml`).

---

## 2. Estrutura de Arquivos a Criar e Modificar

```text
app/modules/pedidos/
├── __init__.py                  # Expõe o APIRouter do módulo sem prefixo
├── models.py                    # Modelo ORM Pedido (SQLAlchemy 2.0)
├── schemas.py                   # Contratos Pydantic v2 (Create, Update, Cancelar, Out, Filtros)
├── service.py                   # Regras de negócio assíncronas e queries comjoins
└── router.py                    # Endpoints da API REST

app/web/
├── templates/pedidos.html       # Template HTML Jinja2 (estende base.html)
└── static/js/pedidos.js         # Lógica do front-end (fetch, manipulação DOM, modais)

migrations/versions/
└── YYYYMMDD_HHMM_<rev>_add_pedidos_table.py   # Migração Alembic da tabela pedidos

tests/
├── unit/test_pedidos_service.py     # Testes unitários do service e regras de negócio
└── integration/test_pedidos_router.py # Testes de integração das rotas e RBAC

Modificações em Arquivos Existentes:
├── app/shared/core/enums.py          # Inclusão dos enums StatusPedido, TipoPedido, OrigemPedido
├── app/bootstrap/main.py             # Registro do router (/pedidos) + inclusão em API_PREFIXES
├── app/web/pages/router.py           # Rota da página GET /pedidos
├── app/web/templates/base.html       # Adição do link /pedidos com ícone SVG no #admin-nav
└── app/web/static/css/index.css      # Adição dos estilos de botão .btn-pedido e variáveis
```

---

## 3. Roteiro Passo a Passo de Implementação

---

### FASE 1: Modelo de Dados, Enums e Migração Alembic

#### 1.1 Atualizar `app/shared/core/enums.py`
Adicionar os três novos enums do módulo `pedidos`:

```python
class StatusPedido(str, enum.Enum):
    PENDENTE = "PENDENTE"
    ATENDIDO = "ATENDIDO"
    CANCELADO = "CANCELADO"

class TipoPedido(str, enum.Enum):
    NORMAL = "NORMAL"
    EMERGENCIA = "EMERGENCIA"

class OrigemPedido(str, enum.Enum):
    SLOT_VAZIO = "SLOT_VAZIO"
    VENCIMENTO = "VENCIMENTO"
    MANUAL = "MANUAL"
```

#### 1.2 Criar `app/modules/pedidos/models.py`
Implementar a entidade `Pedido` com mapeamento explícito de relacionamentos e FKs:

```python
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.bootstrap.database import Base
from app.shared.core.enums import OrigemPedido, StatusPedido, TipoPedido

class Pedido(Base):
    """Modelo de persistência relacional do ciclo de vida dos pedidos."""
    __tablename__ = "pedidos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    numero_pedido: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    origem: Mapped[str] = mapped_column(String(20), nullable=False, default=OrigemPedido.MANUAL.value)
    slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("slots_inventario.id", ondelete="SET NULL"), nullable=True, index=True
    )
    controle_vencimento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("controle_vencimentos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("itens_equipamento.id", ondelete="SET NULL"), nullable=True
    )
    modelo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="SET NULL"), nullable=True
    )
    part_number_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nome_equipamento_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_pedido: Mapped[str] = mapped_column(String(20), nullable=False, default=TipoPedido.NORMAL.value)
    numero_emergencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusPedido.PENDENTE.value, index=True)
    observacao: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    data_pedido: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    data_atendimento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_cancelamento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    solicitante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    atendido_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    cancelado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relacionamentos com carregamento tardio/opcional
    aeronave: Mapped["Aeronave"] = relationship()
    slot: Mapped["SlotInventario | None"] = relationship()
    controle_vencimento: Mapped["ControleVencimento | None"] = relationship()
    item: Mapped["ItemEquipamento | None"] = relationship()
    modelo: Mapped["ModeloEquipamento | None"] = relationship()
    solicitante: Mapped["Usuario"] = relationship(foreign_keys=[solicitante_id])
    atendido_por: Mapped["Usuario | None"] = relationship(foreign_keys=[atendido_por_id])
    cancelado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[cancelado_por_id])
```

#### 1.3 Gerar e Executar Migração Alembic
Executar o comando de autogeração e revisar o arquivo gerado em `migrations/versions/`:

```bash
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add_pedidos_table"
.venv\Scripts\python.exe -m alembic upgrade head
```

---

### FASE 2: Schemas Pydantic (`app/modules/pedidos/schemas.py`)

Criar os schemas de entrada, saída, filtros e validação:

```python
import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.shared.core.enums import OrigemPedido, StatusPedido, TipoPedido

class PedidoCreate(BaseModel):
    aeronave_id: uuid.UUID
    origem: OrigemPedido = OrigemPedido.MANUAL
    slot_id: uuid.UUID | None = None
    controle_vencimento_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    modelo_id: uuid.UUID | None = None
    part_number_snapshot: str | None = Field(None, max_length=50)
    nome_equipamento_snapshot: str | None = Field(None, max_length=100)
    numero_pedido: str | None = Field(None, max_length=50)
    tipo_pedido: TipoPedido = TipoPedido.NORMAL
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int = Field(default=1, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _validar_regras_emergencia_e_origem(self) -> "PedidoCreate":
        # RN-03 / RN-04
        if self.tipo_pedido == TipoPedido.EMERGENCIA and not self.numero_emergencia:
            raise ValueError("O número de emergência é obrigatório para pedidos com tipo EMERGENCIA.")
        if self.tipo_pedido == TipoPedido.NORMAL:
            self.numero_emergencia = None
        
        # RN-08: Validação de identificação do equipamento no pedido genérico
        if self.origem == OrigemPedido.MANUAL and not (self.modelo_id or self.part_number_snapshot or self.nome_equipamento_snapshot):
            raise ValueError("Pedido de origem MANUAL exige modelo_id ou snapshot do Part Number / Nome.")
        return self

class PedidoUpdate(BaseModel):
    slot_id: uuid.UUID | None = None
    controle_vencimento_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    modelo_id: uuid.UUID | None = None
    part_number_snapshot: str | None = Field(None, max_length=50)
    nome_equipamento_snapshot: str | None = Field(None, max_length=100)
    tipo_pedido: TipoPedido | None = None
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int | None = Field(None, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _validar_emergencia_update(self) -> "PedidoUpdate":
        if self.tipo_pedido == TipoPedido.EMERGENCIA and not self.numero_emergencia:
            raise ValueError("O número de emergência é obrigatório ao alterar tipo para EMERGENCIA.")
        return self

class PedidoCancelar(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)  # RN-13

class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_pedido: str
    aeronave_id: uuid.UUID
    origem: str
    slot_id: uuid.UUID | None
    controle_vencimento_id: uuid.UUID | None
    item_id: uuid.UUID | None
    modelo_id: uuid.UUID | None
    part_number_snapshot: str | None
    nome_equipamento_snapshot: str | None
    tipo_pedido: str
    numero_emergencia: str | None
    quantidade: int
    status: str
    observacao: str | None
    data_pedido: date
    data_atendimento: datetime | None
    data_cancelamento: datetime | None
    motivo_cancelamento: str | None
    
    aeronave_matricula: str
    equipamento_nome: str | None
    part_number: str | None
    slot_nome: str | None
    
    solicitante_id: uuid.UUID
    solicitante_trigrama: str | None
    atendido_por_trigrama: str | None
    cancelado_por_trigrama: str | None
    
    ativo: bool
    created_at: datetime
    updated_at: datetime | None

class PendenciaSlotOut(BaseModel):
    slot_id: uuid.UUID
    nome_posicao: str
    part_number: str
    nome_generico: str
    modelo_id: uuid.UUID

class ItemVencidoOut(BaseModel):
    controle_vencimento_id: uuid.UUID
    item_id: uuid.UUID
    part_number: str
    nome_generico: str
    serial_number: str
    tipo_controle_nome: str
    data_vencimento: date | None
```

---

### FASE 3: Camada de Serviços Assíncrona (`app/modules/pedidos/service.py`)

Implementar as regras de negócio e consultas ao banco em funções `async def`:

#### Principais Funcionalidades do `service.py`:
1. **`gerar_numero_pedido(db: AsyncSession) -> str`**:
   Gera sequencial no formato `P-YYYY-XXXX` baseado nos registros do ano corrente.
2. **`listar_pendencias_slots(db: AsyncSession, aeronave_id: uuid.UUID)`**:
   Busca slots da aeronave sem instalação ativa (`data_remocao IS NULL`).
3. **`listar_itens_vencidos(db: AsyncSession, aeronave_id: uuid.UUID)`**:
   Busca itens com `controle_vencimentos.status = 'VENCIDO'` instalados na aeronave.
4. **`criar_pedido(db: AsyncSession, data: PedidoCreate, current_user: Usuario) -> Pedido`**:
   - RN-01: Valida se a aeronave existe.
   - RN-09: Verifica se já existe pedido `PENDENTE` ativo para `(aeronave_id, slot_id)` ou `(controle_vencimento_id)`. Caso exista, lança `ConflitoNegocioError` (HTTP 409).
   - Popula snapshots de PN e Nome do Equipamento a partir do slot/modelo.
   - Trata colisão de `numero_pedido` com `ConflitoNegocioError` em bloco `try/except IntegrityError`.
5. **`atender_pedido(db: AsyncSession, pedido_id: uuid.UUID, current_user: Usuario) -> Pedido`**:
   - RN-10 / RN-11: Exige que o status atual seja `PENDENTE`. Caso contrário, lança `ConflitoNegocioError` (HTTP 409).
   - RN-12: Atualiza `status = 'ATENDIDO'`, `data_atendimento = datetime.now(timezone.utc)`, `atendido_por_id = current_user.id`. **Não executa instalação no inventário.**
6. **`cancelar_pedido(db: AsyncSession, pedido_id: uuid.UUID, motivo: str, current_user: Usuario) -> Pedido`**:
   - RN-11: Exige status `PENDENTE`.
   - RN-13: Registra `status = 'CANCELADO'`, `motivo_cancelamento`, `data_cancelamento`, `cancelado_por_id`.
7. **`excluir_pedido` e `restaurar_pedido`**:
   - Realiza soft delete (`ativo = False`) e restauração.

---

### FASE 4: API REST Router (`app/modules/pedidos/router.py`)

Criar as rotas garantindo a **ordenação correta de precedência** (rotas literais antes do parâmetro dinâmico `/{id: uuid.UUID}`):

```python
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.bootstrap.dependencies import DBSession, CurrentUser, EncarregadoInspetorOuAdmin
from app.modules.pedidos import schemas, service
from app.shared.core import exceptions as domain_exc

router = APIRouter()

# ------------------------------------------------------------------ #
#  Rotas Literais (Devem vir ANTES de /{id})
# ------------------------------------------------------------------ #

@router.get("/", response_model=list[schemas.PedidoOut])
async def listar_pedidos(
    db: DBSession,
    current_user: CurrentUser,
    status_filtro: str | None = Query(None, alias="status"),
    tipo_pedido: str | None = Query(None),
    origem: str | None = Query(None),
    aeronave_id: uuid.UUID | None = Query(None),
    texto: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return await service.listar_pedidos(
        db, status_filtro=status_filtro, tipo_pedido=tipo_pedido, origem=origem,
        aeronave_id=aeronave_id, texto=texto, skip=skip, limit=limit
    )

@router.get("/pendencias/{aeronave_id}", response_model=list[schemas.PendenciaSlotOut])
async def listar_pendencias_slots(
    aeronave_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    return await service.listar_pendencias_slots(db, aeronave_id)

@router.get("/vencidos/{aeronave_id}", response_model=list[schemas.ItemVencidoOut])
async def listar_itens_vencidos(
    aeronave_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    return await service.listar_itens_vencidos(db, aeronave_id)

@router.get("/export")
async def exportar_pedidos(
    db: DBSession,
    current_user: CurrentUser,
    format_type: str = Query("csv", alias="format", pattern="^(csv|xlsx)$"),
):
    # Padrão de exportação idêntico a /inspecoes/export
    content, filename, media_type = await service.exportar_pedidos(db, format_type)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# ------------------------------------------------------------------ #
#  Rotas Dinâmicas por UUID
# ------------------------------------------------------------------ #

@router.post("/", response_model=schemas.PedidoOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(
    data: schemas.PedidoCreate,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    try:
        return await service.criar_pedido(db, data, current_user=user)
    except domain_exc.ConflitoNegocioError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

@router.get("/{id}", response_model=schemas.PedidoOut)
async def obter_pedido(
    id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    pedido = await service.obter_pedido_por_id(db, id)
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")
    return pedido

@router.put("/{id}", response_model=schemas.PedidoOut)
async def atualizar_pedido(
    id: uuid.UUID,
    data: schemas.PedidoUpdate,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    try:
        return await service.atualizar_pedido(db, id, data, current_user=user)
    except domain_exc.ConflitoNegocioError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

@router.post("/{id}/atender", response_model=schemas.PedidoOut)
async def atender_pedido(
    id: uuid.UUID,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    try:
        return await service.atender_pedido(db, id, current_user=user)
    except domain_exc.ConflitoNegocioError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

@router.post("/{id}/cancelar", response_model=schemas.PedidoOut)
async def cancelar_pedido(
    id: uuid.UUID,
    data: schemas.PedidoCancelar,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    try:
        return await service.cancelar_pedido(db, id, data.motivo, current_user=user)
    except domain_exc.ConflitoNegocioError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_pedido(
    id: uuid.UUID,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    await service.excluir_pedido(db, id, current_user=user)
    return None

@router.post("/{id}/restaurar", response_model=schemas.PedidoOut)
async def restaurar_pedido(
    id: uuid.UUID,
    db: DBSession,
    user: EncarregadoInspetorOuAdmin,
):
    return await service.restaurar_pedido(db, id, current_user=user)
```

#### Registros no Bootstrap (`app/bootstrap/main.py`)
1. Importar `pedidos_router` e registrar o endpoint:
   ```python
   from app.modules.pedidos.router import router as pedidos_router
   app.include_router(pedidos_router, prefix="/pedidos", tags=["Pedidos"])
   ```
2. Adicionar `"/pedidos"` à lista `API_PREFIXES` (linha ~50 do `main.py`).

---

### FASE 5: Interface Web Front-end & CSP Hardening

#### 5.1 Rota da Página HTML (`app/web/pages/router.py`)
Adicionar a rota web da Central de Pedidos:

```python
@router.get("/pedidos", response_class=HTMLResponse, include_in_schema=False)
async def pedidos_page(
    request: Request,
    _: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse("pedidos.html", {"request": request})
```

#### 5.2 Link no Menu Navegação (`app/web/templates/base.html`)
Inserir o link no `#admin-nav` entre Vencimentos e Calendário:

```html
<a href="/pedidos" class="btn-icon" aria-label="Pedidos" title="Central de Pedidos"
   style="width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); text-decoration: none; color: var(--text-secondary); {% if request.url.path == '/pedidos' %}background: rgba(231, 76, 60, 0.15); color: #e74c3c;{% endif %}">
    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
</a>
```

#### 5.3 Estilização (`app/web/static/css/index.css`)
Adicionar as variáveis e classes de botão do módulo de Pedidos:

```css
:root {
    --pedido-color: #e74c3c;
}

.btn-pedido {
    background-color: var(--pedido-color);
    color: #ffffff;
    border: none;
}
.btn-pedido:hover {
    background-color: #c0392b;
}
.btn-outline-pedido {
    background-color: transparent;
    color: var(--pedido-color);
    border: 1px solid var(--pedido-color);
}
.btn-outline-pedido:hover {
    background-color: rgba(231, 76, 60, 0.1);
}
```

#### 5.4 Template Jinja2 (`app/web/templates/pedidos.html`)
Portar a estrutura do mockup `docs/backlog/modulo_pedidos/mockup_pedidos.html` estendendo `base.html`.
- **Regra CSP:** Remover qualquer bloco `<script>` inline ou eventos HTML (`onclick`).
- Vincular o script externo via `<script src="/static/js/pedidos.js"></script>` no bloco de scripts.

#### 5.5 Script JavaScript (`app/web/static/js/pedidos.js`)
Implementar o JS client-side:
- Inicialização via `document.addEventListener("DOMContentLoaded", ...)`
- Utilizar `window.apiFetch` e `window.escapeHtml` globais de `app.js`.
- Renderizar contadores nos 4 cards de resumo (Total, Pendentes, Atendidos, Emergências).
- Renderizar a tabela de pedidos com tratamento de XSS via `escapeHtml()`.
- Controlar exibição dinâmica do campo `Nº Emergência` ao alternar a opção do select `Tipo` (espelhando a regra do backend).
- Manipular modais de criação, edição e cancelamento.

---

### FASE 6: Suíte de Testes Automatizados (TDD & Regressão)

Criar os testes automatizados em `tests/unit/test_pedidos_service.py` e `tests/integration/test_pedidos_router.py`:

#### Cenários Mínimos Obrigatórios de Teste (Mínimo 15 testes):
1. `test_criar_pedido_normal_sucesso`: Criar pedido `NORMAL` e verificar geração automática de `numero_pedido`.
2. `test_criar_pedido_emergencia_sem_numero_falha`: Garantir erro de validação (HTTP 422/ValueError) se `numero_emergencia` for omitido.
3. `test_criar_pedido_normal_limpa_numero_emergencia`: Garantir que `numero_emergencia` é forçado a `None` para `NORMAL`.
4. `test_impedir_duplicidade_pedido_pendente_mesmo_slot`: Criar 2º pedido `PENDENTE` para o mesmo slot/aeronave e verificar retorno HTTP 409 (RN-09).
5. `test_atender_pedido_sucesso_administrativo`: Marcar pedido como `ATENDIDO` e verificar registro de `data_atendimento` e `atendido_por_id` **sem criar** registro em `instalacoes`.
6. `test_atender_pedido_ja_atendido_falha_409`: Tentar atender pedido que não está `PENDENTE` (RN-11).
7. `test_cancelar_pedido_exige_motivo`: Tentar cancelar sem motivo e verificar erro de validação.
8. `test_cancelar_pedido_sucesso`: Cancelar pedido `PENDENTE` informando motivo e verificar estado `CANCELADO`.
9. `test_editar_pedido_somente_quando_pendente`: Tentar editar pedido `ATENDIDO` ou `CANCELADO` e verificar rejeição HTTP 409.
10. `test_rbac_mantenedor_nao_pode_criar_pedido`: Garantir retorno HTTP 403 quando perfil `MANTENEDOR` tenta `POST /pedidos`.
11. `test_rbac_encarregado_inspetor_admin_podem_criar`: Garantir criação permitida para `ENCARREGADO`, `INSPETOR` e `ADMINISTRADOR`.
12. `test_listar_pendencias_slots_aeronave`: Verificar consulta de slots vazios integrados ao módulo de equipamentos.
13. `test_listar_itens_vencidos_aeronave`: Verificar consulta de itens vencidos integrados ao módulo de vencimentos.
14. `test_soft_delete_e_restauracao`: Verificar exclusão lógica (`ativo=False`) e rota `/restaurar`.
15. `test_exportacao_pedidos_csv_e_xlsx`: Verificar respostas e headers do endpoint `/export`.

---

## 4. Matriz de Riscos & Cuidados de Segurança

| Risco Identificado | Mitigação Obrigatória no Código |
|---|---|
| **Violação de CSP `script-src 'self'`** | **Zero scripts inline.** Todo o código JS deve residir exclusivamente em `app/web/static/js/pedidos.js`. Nenhum evento `onclick` no HTML. |
| **Vulnerabilidade de XSS na lista** | Reutilização da função `escapeHtml()` de `app.js` na interpolação de todas as strings dinâmicas (ex.: observações, snapshots). Proibido `innerHTML` direto com dados da API. |
| **Concorrência/Race Condition em Pedidos Duplicados** | Validação assíncrona com trava lógica no `service.py` (RN-09) e tratamento de `IntegrityError` com `ConflitoNegocioError` (HTTP 409). |
| **Bypass de Regra de Negócio de Emergência via API** | Regras de obrigatoriedade de `numero_emergencia` aplicadas no schema Pydantic via `@model_validator(mode="after")`, impedindo bypass via cliente REST. |
| **Redirecionamento Incorreto em Erros 401/403 da API** | Inclusão obrigatória de `"/pedidos"` na lista `API_PREFIXES` de `app/bootstrap/main.py`. |
| **Tentativa de Migração de Banco de Dados** | Manutenção estrita do uso do SQLite com `aiosqlite`. Rejeitar qualquer proposta de inclusão de PostgreSQL/outros SGBDs. |

---

## 5. Critérios de Aceite para Conclusão da Feature

- [ ] Migração Alembic da tabela `pedidos` aplicada e testada sem erros em SQLite.
- [ ] Módulo `app/modules/pedidos/` completamente estruturado (`models.py`, `schemas.py`, `service.py`, `router.py`).
- [ ] Endpoints da API REST registrados em `app/bootstrap/main.py` e incluídos em `API_PREFIXES`.
- [ ] Rota web `/pedidos` e link no menu de navegação `#admin-nav` funcionando.
- [ ] Visual do front-end fidedigno ao mockup `mockup_pedidos.html`, com suporte a Light/Dark mode e zero alertas de CSP no console do navegador.
- [ ] Validações server-side de emergência, duplicidade (RN-09) e transições de estado (RN-11) operantes retornando HTTP 409/422.
- [ ] RBAC testado (apenas `ENCARREGADO`, `INSPETOR` e `ADMINISTRADOR` podem criar/mutar; `MANTENEDOR` tem acesso somente leitura).
- [ ] Suíte de no mínimo 15 novos testes automatizados passando 100% verde.
