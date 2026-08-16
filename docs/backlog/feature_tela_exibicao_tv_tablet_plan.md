# 📋 Plano de Implementação — Painel Operacional TV/Tablet

> **Versão:** 1.0
> **Data:** 2026-08-16
> **Referência:** `docs/backlog/feature_tela_exibicao_tv_tablet.md` (revisada contra o código em 2026-08-16)
> **Status:** 🟢 Pronto para execução
> **Escopo deste documento:** passo a passo técnico para implementar o painel de exibição contínua (TV de hangar / tablet), ancorado nos padrões reais já existentes no repositório. As páginas `mobile/base_mobile.html` e `publicacoes_viewer.js` (tela cheia) são as referências de estilo mais próximas; o módulo `dashboard` existente é a referência de service 100% leitura.

> ⚠️ **Nota de coordenação:** este plano toca arquivos **compartilhados** com o restante do sistema
> (`app/shared/core/enums.py`, `app/shared/core/helpers.py`, `app/bootstrap/dependencies.py`,
> `app/bootstrap/main.py`, `app/web/pages/router.py`, `app/web/static/js/auth_check.js`,
> `app/web/templates/efetivo.html`, `tests/conftest.py`). Revisar o §17 (Riscos) antes de abrir PR.

---

## 0. Visão do que será construído

Ao final deste plano, o sistema terá:

- Uma nova função de usuário `DISPLAY`, de permissão mínima, com acesso **negado por padrão** a todo o
  sistema e liberado explicitamente apenas para o painel operacional.
- Um endpoint novo, `GET /dashboard/painel`, que não altera o contrato nem os testes do
  `GET /dashboard/resumo` existente.
- Uma página `/tv`, fora do layout padrão do sistema, com relógio duplo (Local/Zulu), auto-scroll,
  auto-refresh sem flicker e sessão persistente (silent refresh) para ficar ligada 24/7.
- Dois defeitos pré-existentes corrigidos e centralizados em `app/shared/core/helpers.py`, em vez de o painel
  novo virar mais uma cópia da mesma regra: o cálculo de status da frota, hoje reimplementado em 4 lugares
  (RISCO-02 de `docs/backlog/revisor/concluido/achados_dashboard.md`), e a leitura de status de vencimento
  pela coluna obsoleta (`dashboard/service.py:106-121` hoje ignora a regra já documentada em
  `vencimentos/service.py:34-51`).

Nenhuma tabela nova é criada — sem migração Alembic. O painel é 100% agregação de leitura, no mesmo espírito
do módulo `dashboard` existente (`docs/backlog/00_mapa_arquitetural.md` §3: "não tem `models.py` — é 100%
agregação").

---

## 1. Mapa de arquivos

| Arquivo | Ação | Observação |
|---|---|---|
| `app/shared/core/enums.py` | **editar** | + `DISPLAY` em `TipoPapel` |
| `app/modules/auth/roles.py` | **editar** | + constante `DISPLAY`, incluir em `ALL_FUNCTIONS` |
| `app/shared/core/helpers.py` | **editar** | + `resolver_status_frota`, `calcular_status_vencimento`, `contar_tarefas_por_inspecao` |
| `app/modules/dashboard/service.py` | **editar** | `get_frota_summary`/`get_vencimentos_summary` passam a usar os helpers movidos |
| `app/modules/vencimentos/service.py` | **editar** | `calcular_status_vencimento` vira reexport do helper (compatibilidade) |
| `app/modules/inspecoes/service.py` | **editar** | `contar_tarefas_por_inspecao` vira reexport do helper (compatibilidade) |
| `app/bootstrap/dependencies.py` | **editar** | deny-by-default para `DISPLAY` em `get_current_user`; nova `get_current_user_painel`/`CurrentUserPainel` |
| `app/modules/auth/router.py` | **editar** | `/auth/me` e `/auth/logout` passam a usar `CurrentUserPainel` |
| `app/modules/dashboard/schemas.py` | **editar** | + `PainelPane`, `PainelInspecao`, `PainelVencimento`, `PainelResumo` |
| `app/modules/dashboard/router.py` | **editar** | + `GET /painel` |
| `app/web/pages/router.py` | **editar** | + rota de página `/tv` |
| `app/web/templates/tv.html` | criar | página standalone (não estende `base.html`) |
| `app/web/static/css/tv.css` | criar | 4ª folha do projeto, ao lado de `mobile.css`/`publicacoes.css` |
| `app/web/static/js/tv.js` | criar | relógio, polling, silent refresh, auto-scroll, fullscreen |
| `app/web/static/js/auth_check.js` | **editar** | `hasPermission` não deve conceder acesso implícito de MANTENEDOR para `DISPLAY` |
| `app/web/templates/efetivo.html` | **editar** | `<option value="DISPLAY">` nos dois selects de função |
| `app/modules/auth/service.py` | **editar** | usuário `display` na seed de desenvolvimento (`enable_test_users`) |
| `tests/conftest.py` | **editar** | + fixtures `dados_usuario_display`, `usuario_display_e_token` |
| `tests/unit/test_painel_operacional.py` | criar | testes do endpoint, da página e do RBAC |

**Ordem recomendada de execução:** 1→2→3→…→16 (cada etapa abaixo segue essa ordem). Os helpers compartilhados
(etapas 3-5) vêm antes do endpoint novo (etapa 8) porque o service do painel já nasce usando a versão
corrigida, em vez de herdar os dois defeitos do dashboard atual.

---

## 2. Etapa 1 — Papel `DISPLAY` (`app/shared/core/enums.py`, `app/modules/auth/roles.py`)

Sem migração: `usuarios.funcao` é `String(50)` livre, sem CHECK nem enum de banco
(`app/modules/auth/models.py:50-54`) — acrescentar o valor é só código.

```python
# app/shared/core/enums.py — dentro de TipoPapel
class TipoPapel(str, enum.Enum):
    """
    Papel/função de um usuário responsável por uma pane.
    Perfis do sistema (v2.1):
        - MANTENEDOR: execução de manutenção
        - ENCARREGADO: gestão operacional (+ permissões do mantenedor)
        - INSPETOR: fiscalização e validação (não executa)
        - ADMINISTRADOR: gestão total do sistema (+ cadastro de aeronaves e efetivo)
        - DISPLAY: permissão mínima — autentica dispositivos de exibição (TV/tablet
          de hangar), sem acesso a nenhum módulo além do painel operacional
    """
    MANTENEDOR = "MANTENEDOR"
    ENCARREGADO = "ENCARREGADO"
    INSPETOR = "INSPETOR"
    ADMINISTRADOR = "ADMINISTRADOR"
    DISPLAY = "DISPLAY"
```

```python
# app/modules/auth/roles.py
DISPLAY = "DISPLAY"

ALL_FUNCTIONS: frozenset[str] = frozenset(
    {MANTENEDOR, INSPETOR, ENCARREGADO, ADMINISTRADOR, DISPLAY}
)
```

**Pontos críticos (não pular):**
- Não incluir `DISPLAY` em `PRIVILEGED_FUNCTIONS` nem `ADMIN_FUNCTIONS` — a regra deste papel é exatamente o
  oposto de privilégio.
- O arquivo `roles.py` declara no próprio docstring: "Adicionar novos papéis APENAS aqui" — não repetir a
  string literal `"DISPLAY"` em outro lugar do backend, sempre importar a constante.

---

## 3. Etapa 2 — Helper: status de frota derivado (`app/shared/core/helpers.py`)

`app/modules/dashboard/service.py:263-284` já calcula o status "verdadeiro" de cada aeronave (inspeção ativa
→ `INSPEÇÃO`; pane aberta e não isenta → `INDISPONIVEL`) — é a **quarta** cópia dessa regra no sistema
(RISCO-02, `docs/backlog/revisor/concluido/achados_dashboard.md`). Extrair a parte pura (sem I/O) para
`helpers.py`, para que o novo service do painel reutilize em vez de copiar de novo:

```python
# app/shared/core/helpers.py — nova função, mesmo arquivo dos demais helpers de DRY
def resolver_status_frota(
    status_cadastrado: str,
    aeronave_id: uuid.UUID,
    inspecoes_ativas: set[str],
    panes_ativas: set[str],
) -> str:
    """Deriva o status operacional de uma aeronave a partir do status
    cadastrado + inspeções/panes ativas.

    Hierarquia (RISCO-02 / achados_dashboard.md):
        1. Inspeção ativa                                  -> "INSPEÇÃO"
        2. Pane aberta E status não isento                  -> "INDISPONIVEL"
           (isentos: INSPEÇÃO, INATIVA, ESTOCADA)
        3. Caso contrário                                    -> status_cadastrado
    """
    ac_id_str = str(aeronave_id)
    if ac_id_str in inspecoes_ativas:
        return "INSPEÇÃO"
    if ac_id_str in panes_ativas and status_cadastrado not in ["INSPEÇÃO", "INATIVA", "ESTOCADA"]:
        return "INDISPONIVEL"
    return status_cadastrado
```

Em seguida, `dashboard/service.get_frota_summary` (`dashboard/service.py:263-276`) passa a chamar o helper em
vez de reimplementar o `if/elif` inline — as duas queries de IDs ativos (`q_insp`, `q_panes`) continuam no
service, só a decisão final muda de lugar.

**Pontos críticos:**
- Função **pura** (recebe os sets já resolvidos, não faz query) — mantém `dashboard/service.py` como único
  ponto de acesso ao ORM do módulo, sem violar "não chama services de outros módulos"
  (`dashboard/service.py:5-10`): o helper mora em `shared/core`, terreno neutro, não em outro módulo.
- Não remover o comentário `BUG-01` original de `dashboard/service.py` — vira parte do histórico do helper
  novo (o `str(id_)` em ambos os sets continua necessário, é o que o BUG-01 documentava).

---

## 4. Etapa 3 — Helper: status de vencimento sempre derivado (`app/shared/core/helpers.py`)

`vencimentos/service.py:34-51` já documenta a regra: a coluna `ControleVencimento.status` só guarda o valor
da última execução, "não é recalculada pela simples passagem do tempo" — mas `dashboard/service.py:106-121`
(`get_vencimentos_summary`) ainda agrupa direto por essa coluna. Mover a função pura para o helper
compartilhado e fazer `vencimentos/service.py` reexportar (compatibilidade com os ~11 endpoints que já a
importam de lá):

```python
# app/shared/core/helpers.py
def calcular_status_vencimento(data_vencimento: date | None, hoje: date | None = None) -> str:
    """Deriva o status OK/VENCENDO/VENCIDO a partir da data de vencimento.
    Ver docstring original em vencimentos/service.py (histórico) — mesma regra,
    apenas realocada para ser compartilhável entre módulos.
    """
    if hoje is None:
        hoje = date.today()
    if data_vencimento is None:
        return StatusVencimento.VENCIDO.value
    if data_vencimento < hoje:
        return StatusVencimento.VENCIDO.value
    if (data_vencimento - hoje).days <= 30:
        return StatusVencimento.VENCENDO.value
    return StatusVencimento.OK.value
```

```python
# app/modules/vencimentos/service.py — substitui a definição original
from app.shared.core.helpers import calcular_status_vencimento  # noqa: F401 (reexport)
```

Corrigir `dashboard/service.get_vencimentos_summary` para derivar em vez de agrupar pela coluna crua:

```python
async def get_vencimentos_summary(db: AsyncSession) -> VencimentosSummary:
    """Contagem de vencimentos por status — sempre derivado, nunca lido da
    coluna persistida (mesma regra do painel, ver §3.5 da spec)."""
    hoje = date.today()
    q = (
        select(ControleVencimento)
        .options(selectinload(ControleVencimento.prorrogacoes))
    )
    rows = (await db.execute(q)).scalars().all()

    contagens = {"OK": 0, "VENCENDO": 0, "VENCIDO": 0, "PRORROGADO": 0}
    for venc in rows:
        status = calcular_status_vencimento(venc.data_vencimento, hoje)
        prorrogacao_ativa = next((p for p in venc.prorrogacoes if p.ativo), None)
        if prorrogacao_ativa:
            status = "VENCIDO" if hoje > prorrogacao_ativa.data_nova_vencimento else "PRORROGADO"
        contagens[status] = contagens.get(status, 0) + 1

    return VencimentosSummary(**{k.lower(): v for k, v in contagens.items()})
```

**Pontos críticos:**
- Isso muda o **resultado** do `/dashboard/resumo` atual (não o contrato/schema, que continua igual) — rodar
  a suíte completa de `tests/unit/test_dashboard.py` depois desta etapa, não só os testes novos.
- `import date` de `datetime` já é usado em `dashboard/service.py`? Não — hoje o módulo só importa
  `datetime, time, timezone`; acrescentar `from datetime import date` no topo.

---

## 5. Etapa 4 — Helper: contagem de tarefas de inspeção (`app/shared/core/helpers.py`)

`inspecoes/service.contar_tarefas_por_inspecao` (`inspecoes/service.py:400+`) já resolve exatamente o que o
painel precisa — progresso em lote, sem N+1. Em vez de o `dashboard/service.py` importar
`app.modules.inspecoes.service` (o que violaria o princípio "não chama services de outros módulos",
`dashboard/service.py:5-10`), mover a função para o helper compartilhado e reexportar de `inspecoes/service.py`:

```python
# app/shared/core/helpers.py
async def contar_tarefas_por_inspecao(
    db: AsyncSession, inspecao_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Mapa inspecao_id -> (total_tarefas, tarefas_concluidas), via agregação
    no banco — evita N+1 ao calcular progresso de várias inspeções de uma vez."""
    # corpo idêntico ao de inspecoes/service.py:400+, apenas realocado
    ...
```

```python
# app/modules/inspecoes/service.py — substitui a definição original
from app.shared.core.helpers import contar_tarefas_por_inspecao  # noqa: F401 (reexport)
```

---

## 6. Etapa 5 — Deny-by-default para `DISPLAY` (`app/bootstrap/dependencies.py`)

Hoje `CurrentUser` (usada em ~111 pontos do sistema) só exige "autenticado" — qualquer função tem acesso de
leitura a praticamente todos os módulos. Em vez de tocar os 111 pontos, extrair a resolução do token e negar
`DISPLAY` numa única função central; endpoints que **devem** aceitar `DISPLAY` passam a usar uma dependency
nova e explícita.

```python
# app/bootstrap/dependencies.py

async def _resolver_usuario_do_token(
    token: str,
    db: AsyncSession,
) -> Usuario:
    """Decodifica o JWT, valida blacklist e retorna o usuário — sem nenhuma
    checagem de papel. Corpo idêntico ao antigo get_current_user; extraído
    para ser reaproveitado tanto pela via padrão (nega DISPLAY) quanto pela
    via do painel (aceita todos)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from app.modules.auth.security import decodificar_token
        payload = decodificar_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        username: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if username is None or jti is None:
            raise credentials_exception

        from sqlalchemy import select
        from app.modules.auth.models import TokenBlacklist
        result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
        if result.scalar_one_or_none() is not None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    from app.modules.auth.service import buscar_por_username
    usuario = await buscar_por_username(db, username)
    if usuario is None or not usuario.ativo:
        raise credentials_exception
    return usuario


async def get_current_user(
    token: Annotated[str, Depends(get_token_from_request)],
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """Dependency padrão — nega acesso à função DISPLAY. Usada pelos ~111
    endpoints/páginas existentes: nenhum precisa mudar de assinatura."""
    usuario = await _resolver_usuario_do_token(token, db)
    if usuario.funcao == roles.DISPLAY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Função DISPLAY não tem acesso a este recurso.",
        )
    return usuario


async def get_current_user_painel(
    token: Annotated[str, Depends(get_token_from_request)],
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    """Aceita qualquer usuário autenticado, incluindo DISPLAY. Uso restrito às
    rotas do painel operacional (GET /dashboard/painel, GET /tv, /auth/me,
    /auth/logout) — nunca usar em rotas de escrita ou de outros módulos."""
    return await _resolver_usuario_do_token(token, db)


CurrentUserPainel = Annotated[Usuario, Depends(get_current_user_painel)]
```

`require_role(...)` não precisa mudar: `ensure_role` (`dependencies.py:115-124`) já faz comparação exata
(`usuario.funcao not in roles`), então `AdminRequired`/`EncarregadoRequired`/etc. já excluem `DISPLAY`
automaticamente — só o `CurrentUser` "aberto" precisava do ajuste.

**Pontos críticos (não pular):**
- Aplicar a checagem de `DISPLAY` em `get_current_user`, **não** em `get_token_from_request` — este último
  não tem acesso ao usuário resolvido, só ao token cru.
- `app/modules/auth/router.py` — trocar a assinatura de `me` (linha 372) e `logout` (linha 315) de
  `CurrentUser` para `CurrentUserPainel`. Nenhum outro endpoint de `auth/router.py` muda.
- `POST /auth/refresh` (`auth/router.py:126`) não usa `CurrentUser` — já funciona para `DISPLAY` sem alteração.
- Testar explicitamente que um usuário `DISPLAY` recebe `403` em rotas como `/panes`, `/aeronaves`,
  `/configuracoes` — não basta testar que `/dashboard/painel` retorna `200`.

---

## 7. Etapa 6 — Schemas do painel (`app/modules/dashboard/schemas.py`)

Acrescentar ao final do arquivo, sem alterar nenhum schema existente:

```python
class PainelPane(BaseModel):
    """Pane aberta para o painel de exibição — sem limite de registros,
    diferente de PaneCritica (usada pelo /dashboard/resumo)."""
    id: str
    matricula: str
    sistema_ata: str | None = None   # "código - descrição", ex: "34 - Aviônica"
    descricao: str
    data_abertura: str               # ISO 8601


class PainelInspecao(BaseModel):
    """Inspeção ativa com progresso — sem limite de registros."""
    inspecao_id: str
    matricula: str
    tipos: list[str] = []
    status: str
    progresso_percentual: int = 0
    data_fim_prevista: str | None = None


class PainelVencimento(BaseModel):
    """Um controle de vencimento dentro do horizonte solicitado."""
    vencimento_id: str
    item_descricao: str        # nome_generico do ModeloEquipamento
    part_number: str
    numero_serie: str | None = None
    localizacao: str           # matrícula da aeronave ou "Em Estoque"
    data_vencimento: str | None = None
    dias_restantes: int | None = None
    status: str                # OK | VENCENDO | VENCIDO | PRORROGADO (sempre derivado)
    prorrogado: bool = False


class PainelResumo(BaseModel):
    """Schema raiz do endpoint GET /dashboard/painel."""
    panes: list[PainelPane] = []
    inspecoes: list[PainelInspecao] = []
    vencimentos: list[PainelVencimento] = []
    frota: FrotaSummary = FrotaSummary()
    horizonte_dias: int = 30
    gerado_em: str = ""   # ISO 8601 — timestamp do servidor no momento da consulta
```

---

## 8. Etapa 7 — Service do painel (`app/modules/dashboard/service.py`)

```python
async def get_panes_painel(db: AsyncSession) -> list[PainelPane]:
    """Todas as panes abertas — sem LIMIT, diferente de get_panes_summary."""
    q = (
        select(Pane)
        .where(Pane.status == "ABERTA", Pane.ativo == True)  # noqa: E712
        .order_by(Pane.data_abertura.asc())
        .options(selectinload(Pane.aeronave), selectinload(Pane.sistema_ata))
    )
    rows = (await db.execute(q)).scalars().all()
    return [
        PainelPane(
            id=str(p.id),
            matricula=p.aeronave.matricula if p.aeronave else "—",
            sistema_ata=(
                f"{p.sistema_ata.codigo} - {p.sistema_ata.descricao}" if p.sistema_ata else None
            ),
            descricao=p.descricao,
            data_abertura=p.data_abertura.isoformat(),
        )
        for p in rows
    ]


async def get_inspecoes_painel(db: AsyncSession) -> list[PainelInspecao]:
    """Todas as inspeções ativas com progresso — sem LIMIT, sem N+1."""
    q = (
        select(Inspecao)
        .where(Inspecao.status.in_(["ABERTA", "EM_ANDAMENTO"]))
        .order_by(Inspecao.data_abertura.asc())
        .options(selectinload(Inspecao.aeronave), selectinload(Inspecao.tipos_aplicados))
    )
    rows = (await db.execute(q)).scalars().all()

    progresso_map = await contar_tarefas_por_inspecao(db, [insp.id for insp in rows])

    resultado = []
    for insp in rows:
        total, concluidas = progresso_map.get(insp.id, (0, 0))
        percentual = round((concluidas / total) * 100) if total else 0
        resultado.append(
            PainelInspecao(
                inspecao_id=str(insp.id),
                matricula=insp.aeronave.matricula if insp.aeronave else "—",
                tipos=[t.codigo for t in (insp.tipos_aplicados or [])],
                status=insp.status,
                progresso_percentual=percentual,
                data_fim_prevista=insp.data_fim_prevista.isoformat() if insp.data_fim_prevista else None,
            )
        )
    return resultado


async def get_vencimentos_painel(db: AsyncSession, dias: int) -> list[PainelVencimento]:
    """Vencimentos dentro do horizonte (dias) ou já vencidos, status sempre
    derivado. Resolve a instalação ativa (data_remocao IS NULL) para achar a
    matrícula, ou marca 'Em Estoque'."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    q = (
        select(ControleVencimento)
        .where(
            (ControleVencimento.data_vencimento.is_(None))
            | (ControleVencimento.data_vencimento <= limite)
        )
        .options(
            selectinload(ControleVencimento.prorrogacoes),
            selectinload(ControleVencimento.item).selectinload(ItemEquipamento.modelo),
            selectinload(ControleVencimento.item)
            .selectinload(ItemEquipamento.instalacoes)
            .selectinload(Instalacao.aeronave),
        )
    )
    rows = (await db.execute(q)).scalars().all()

    resultado = []
    for venc in rows:
        status = calcular_status_vencimento(venc.data_vencimento, hoje)
        prorrogado = False
        prorrogacao_ativa = next((p for p in venc.prorrogacoes if p.ativo), None)
        if prorrogacao_ativa:
            prorrogado = True
            status = "VENCIDO" if hoje > prorrogacao_ativa.data_nova_vencimento else "PRORROGADO"

        item = venc.item
        instalacao_ativa = (
            next((i for i in item.instalacoes if i.data_remocao is None), None) if item else None
        )
        localizacao = (
            instalacao_ativa.aeronave.matricula
            if instalacao_ativa and instalacao_ativa.aeronave
            else "Em Estoque"
        )

        resultado.append(
            PainelVencimento(
                vencimento_id=str(venc.id),
                item_descricao=item.modelo.nome_generico if item and item.modelo else "—",
                part_number=item.modelo.part_number if item and item.modelo else "—",
                numero_serie=item.numero_serie if item else None,
                localizacao=localizacao,
                data_vencimento=venc.data_vencimento.isoformat() if venc.data_vencimento else None,
                dias_restantes=(venc.data_vencimento - hoje).days if venc.data_vencimento else None,
                status=status,
                prorrogado=prorrogado,
            )
        )

    # Ordenado em Python (não via NULLS FIRST no SQL) — vencimento ausente
    # primeiro, depois cronológico. Evita depender de suporte a NULLS FIRST
    # no SQLite.
    resultado.sort(key=lambda v: (v.data_vencimento is not None, v.data_vencimento or ""))
    return resultado


async def get_painel(db: AsyncSession, dias: int = 30) -> PainelResumo:
    """Orquestrador do painel de exibição TV/Tablet — GET /dashboard/painel."""
    panes = await get_panes_painel(db)
    inspecoes = await get_inspecoes_painel(db)
    vencimentos = await get_vencimentos_painel(db, dias)
    frota = await get_frota_summary(db)  # já existente, agora usando resolver_status_frota

    return PainelResumo(
        panes=panes,
        inspecoes=inspecoes,
        vencimentos=vencimentos,
        frota=frota,
        horizonte_dias=dias,
        gerado_em=datetime.now(timezone.utc).isoformat(),
    )
```

**Pontos críticos:**
- Acrescentar aos imports do topo: `from datetime import date, timedelta` e
  `from app.shared.core.helpers import resolver_status_frota, calcular_status_vencimento, contar_tarefas_por_inspecao`.
- `resultado.sort(...)`: strings ISO 8601 (`YYYY-MM-DD`) comparam corretamente por ordem lexicográfica — mesmo
  truque já usado em `get_movimentacoes_recentes` (`dashboard/service.py:220-224`).
- Nenhuma destas três funções tem `LIMIT` — é intencional (painel de exibição total, diferente do resumo do
  dashboard comum). Se a frota crescer muito, reavaliar paginação; fora de escopo desta entrega.

---

## 9. Etapa 8 — Router (`app/modules/dashboard/router.py`)

```python
from typing import Literal
from app.bootstrap.dependencies import DBSession, CurrentUserPainel
from app.modules.dashboard.schemas import PainelResumo

@router.get(
    "/painel",
    response_model=PainelResumo,
    status_code=status.HTTP_200_OK,
    summary="Painel Operacional TV/Tablet",
    description=(
        "Retorna o consolidado completo (sem limite de registros) para exibição "
        "contínua em TV de hangar ou tablet: todas as panes abertas, inspeções "
        "ativas com progresso, vencimentos dentro do horizonte solicitado, e "
        "status da frota. Acessível também ao perfil DISPLAY."
    ),
)
async def get_painel_operacional(
    db: DBSession,
    _: CurrentUserPainel,
    dias: Literal[15, 30, 90, 180] = 30,
) -> PainelResumo:
    return await service.get_painel(db, dias)
```

**Pontos críticos:**
- `Literal[15, 30, 90, 180]` faz o FastAPI devolver `422` automaticamente para qualquer outro valor — não
  precisa validação manual no router (thin controller).
- Router continua sem tocar o ORM diretamente — só chama `service.get_painel`.

---

## 10. Etapa 9 — Página `/tv` (`app/web/pages/router.py`)

```python
@router.get("/tv", response_class=HTMLResponse, include_in_schema=False)
async def tv_page(request: Request, _=Depends(get_current_user_painel)):
    """Painel Operacional TV/Tablet — exibição contínua, acessível também ao
    perfil DISPLAY (feature_tela_exibicao_tv_tablet.md)."""
    return templates.TemplateResponse("tv.html", {"request": request})
```

Import a acrescentar no topo do arquivo: `get_current_user_painel` de `app.bootstrap.dependencies`
(já importa `get_current_user`, `AdminRequired`, `DBSession` — mesmo padrão).

Posicionar a rota como estática antes de qualquer rota paramétrica no mesmo nível (não há colisão real aqui,
mas mantém o padrão do projeto — `equipamentos/router.py:194-195`, replicado em `pages/router.py:142-145`).

---

## 11. Etapa 10 — Template (`app/web/templates/tv.html`)

**Standalone — não estende `base.html`.** Segue o padrão de `mobile/base_mobile.html`: HTML próprio, sem o
cabeçalho/menu de navegação do sistema (a TV não navega, só exibe).

```jinja
<!DOCTYPE html>
<html lang="pt-BR" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0F172A">
    {% if request and request.state and request.state.csrf_token %}
    <meta name="csrf-token" content="{{ request.state.csrf_token }}">
    {% endif %}
    <title>SAA29 — Painel Operacional</title>
    <link rel="stylesheet" href="/static/css/index.css">
    <link rel="stylesheet" href="/static/css/tv.css">
</head>
<body class="tv-body">
    <div id="tv-shell" class="tv-shell">
        <!-- cabeçalho, grades de panes/inspeções/vencimentos — ver mockup da spec §3 -->
    </div>

    <script src="/static/js/app.js"></script>
    <script src="/static/js/tv.js"></script>
</body>
</html>
```

**Pontos críticos:**
- `data-theme="dark"` fixo no `<html>` — não depender do toggle salvo em `localStorage` por `app.js`, que só
  se aplica às páginas que estendem `base.html`.
- `app.js` continua sendo carregado (fornece `apiFetch`, `escapeHtml`, `showToast`) — só `auth_check.js` fica
  de fora, porque a TV não tem menu nem elementos `data-role` a esconder.

---

## 12. Etapa 11 — CSS (`app/web/static/css/tv.css`)

4ª folha de estilo do projeto — mesmo padrão de `mobile.css`/`publicacoes.css`: token block próprio + escopo
por classe de `body`.

```css
:root {
    --tv-gap: 1.5rem;
    --tv-font-scale: clamp(1rem, 1.2vw, 1.4rem);
}

body.tv-body {
    height: 100dvh;
    overflow: hidden;
    display: grid;
    grid-template-rows: auto auto 1fr auto;
    gap: var(--tv-gap);
    padding: var(--tv-gap);
    font-size: var(--tv-font-scale);
    background: var(--bg-primary);
    color: var(--text-primary);
}

.tv-scroll-container {
    overflow-y: hidden;   /* scrollTop controlado via JS, não pelo usuário */
}

/* Tela cheia — mesmo padrão de publicacoes.css (.pub-viewer-shell:fullscreen) */
.tv-shell:fullscreen {
    padding: 2rem;
}
```

Reaproveitar diretamente as classes já existentes de `index.css`: `.glass-panel` para os cards,
`--status-ok/warning/danger/prorrogado/incompleta` (+ seus pares `-bg`) para os badges de status.

---

## 13. Etapa 12 — JavaScript (`app/web/static/js/tv.js`)

IIFE `(function () { "use strict"; ... })();`, handlers só via `addEventListener` — a CSP do projeto
(`script-src 'self'`, `app/shared/middleware/security.py:33-51`) não executa `onclick` inline nem
`<script>` solto no HTML.

```javascript
(function () {
    "use strict";

    const REFRESH_DADOS_MS = 30 * 1000;
    const REFRESH_SESSAO_MS = 10 * 60 * 1000;  // bem antes dos 15 min de validade do access token

    let horizonteDias = 30;
    let ultimaAssinatura = null;

    function atualizarRelogio() {
        const agora = new Date();
        document.getElementById("tv-hora-local").textContent =
            new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(agora) + " L";
        const hh = String(agora.getUTCHours()).padStart(2, "0");
        const mm = String(agora.getUTCMinutes()).padStart(2, "0");
        const ss = String(agora.getUTCSeconds()).padStart(2, "0");
        document.getElementById("tv-hora-zulu").textContent = `${hh}:${mm}:${ss} Z`;
    }

    async function carregarPainel() {
        try {
            const dados = await fetch(`/dashboard/painel?dias=${horizonteDias}`, { credentials: "same-origin" })
                .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });

            // Render diferencial: só remonta o DOM do card se o conteúdo mudou
            // — evita o "innerHTML completo a cada ciclo" do dashboard.js atual.
            const assinatura = JSON.stringify(dados);
            if (assinatura !== ultimaAssinatura) {
                renderPanes(dados.panes);
                renderInspecoes(dados.inspecoes);
                renderVencimentos(dados.vencimentos);
                renderFrota(dados.frota);
                ultimaAssinatura = assinatura;
            }
            marcarConexaoOk();
        } catch (erro) {
            // Falha transitória: mostra o indicador, NÃO desloga (diferente de
            // apiFetch/clearAuth em app.js — aqui é intencional).
            marcarConexaoPerdida();
        }
    }

    async function renovarSessao() {
        try {
            await fetch("/auth/refresh", { method: "POST", credentials: "same-origin" });
        } catch (erro) {
            // Também não desloga em falha de rede — só tenta de novo no próximo ciclo.
        }
    }

    function iniciarAutoScroll(container) {
        let direcao = 1;
        let pausadoAte = 0;
        function passo(timestamp) {
            if (timestamp > pausadoAte) {
                container.scrollTop += direcao * 0.5;
                const noFim = container.scrollTop + container.clientHeight >= container.scrollHeight - 1;
                const noTopo = container.scrollTop <= 0;
                if (noFim || noTopo) {
                    direcao *= -1;
                    pausadoAte = timestamp + 3000;  // pausa de 3s nas pontas
                }
            }
            requestAnimationFrame(passo);
        }
        requestAnimationFrame(passo);
    }

    document.addEventListener("DOMContentLoaded", () => {
        atualizarRelogio();
        setInterval(atualizarRelogio, 1000);

        carregarPainel();
        setInterval(carregarPainel, REFRESH_DADOS_MS);
        setInterval(renovarSessao, REFRESH_SESSAO_MS);

        document.querySelectorAll(".tv-scroll-container").forEach(iniciarAutoScroll);

        document.querySelectorAll("[data-horizonte]").forEach((btn) => {
            btn.addEventListener("click", () => {
                horizonteDias = Number(btn.dataset.horizonte);
                ultimaAssinatura = null;  // força re-render mesmo se os dados não mudaram
                carregarPainel();
            });
        });

        const btnFullscreen = document.getElementById("tv-btn-fullscreen");
        if (btnFullscreen) {
            btnFullscreen.addEventListener("click", async () => {
                try {
                    if (!document.fullscreenElement) {
                        await document.getElementById("tv-shell").requestFullscreen();
                    } else {
                        await document.exitFullscreen();
                    }
                } catch (erro) { /* navegador recusou — sem tratamento especial */ }
            });
        }
    });
})();
```

**Pontos críticos (não pular):**
- **Não usar `apiFetch` de `app.js` para `/dashboard/painel`** — `apiFetch` chama `clearAuth()` em qualquer
  `401` (`app.js:184-188`), o que redireciona a TV para `/login` numa falha transitória de rede/deploy. O
  `fetch` direto acima trata a falha como "sem conexão", não como logout.
- Todo texto vindo do backend (descrição de pane, item de vencimento, etc.) passa por `escapeHtml` (global de
  `app.js`) antes de `innerHTML` — mesma regra do resto do sistema.
- `renovarSessao` chama `/auth/refresh` **direto por `fetch`**, também sem passar por `apiFetch`, pelo mesmo
  motivo acima.
- A comparação de assinatura por `JSON.stringify` é suficiente para o volume de dados do painel (algumas
  dezenas de linhas); não otimizar prematuramente com diff por campo.

---

## 14. Etapa 13 — Guarda de UI e cadastro (`auth_check.js`, `efetivo.html`, seed de dev)

`app/web/static/js/auth_check.js:99` hoje devolve `true` para **qualquer** usuário logado quando a role
exigida é `MANTENEDOR` — isso vazaria acesso de UI (não de API, que já está protegida pela Etapa 5) para
`DISPLAY` em qualquer página que ele conseguisse abrir por engano. Travar explicitamente:

```javascript
// window.hasPermission, início da função — antes das checagens existentes
if (funcao === 'DISPLAY') return false;
```

`app/web/templates/efetivo.html:77-80,133-136` — acrescentar a opção nos dois `<select>` de função (criação e
edição de usuário):

```html
<option value="DISPLAY">DISPLAY</option>
```

`app/modules/auth/service.py:380-384` — acrescentar à lista `usuarios_teste` da seed de desenvolvimento
(`enable_test_users`), para haver um usuário `display` pronto em ambiente local:

```python
("display", roles.DISPLAY, "Painel TV Hangar", "—"),
```

---

## 15. Etapa 14 — Testes

### `tests/conftest.py` — fixtures novas (mesmo molde de `usuario_mantenedor_e_token`)

```python
@pytest.fixture
def dados_usuario_display() -> dict:
    return {
        "nome": "Painel TV Hangar",
        "posto": "—",
        "especialidade": None,
        "funcao": "DISPLAY",
        "ramal": None,
        "username": "display.hangar",
        "password": "senha_display_000",
    }


@pytest_asyncio.fixture
async def usuario_display_e_token(db: AsyncSession, dados_usuario_display: dict) -> dict:
    """Cria um usuário DISPLAY autenticado para testes de RBAC."""
    usuario = Usuario(
        nome=dados_usuario_display["nome"],
        posto=dados_usuario_display["posto"],
        especialidade=dados_usuario_display["especialidade"],
        funcao=dados_usuario_display["funcao"],
        ramal=dados_usuario_display["ramal"],
        username=dados_usuario_display["username"],
        senha_hash=hash_senha(dados_usuario_display["password"]),
    )
    db.add(usuario)
    await db.flush()
    token = criar_token(dados={"sub": usuario.username})
    return {"usuario": usuario, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
```

### `tests/unit/test_painel_operacional.py`

Usar `AsyncClient`/`ASGITransport` (`client`, `client_autenticado` de `tests/conftest.py`), nunca `TestClient`.
**Sempre filtrar por matrícula única gerada no teste** — `tests/architecture/test_performance_audit.py` faz
`db.commit()` e polui o banco em memória compartilhado entre todos os testes da suíte
(`test_dashboard.py:460-467`); nunca assertar sobre contagem total/global.

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | `GET /dashboard/painel` com `client_autenticado` (ADMINISTRADOR) | 200, chaves `panes/inspecoes/vencimentos/frota/horizonte_dias/gerado_em` |
| 2 | `GET /dashboard/painel` com `usuario_display_e_token["headers"]` | 200 |
| 3 | `GET /dashboard/painel` sem token | 401 |
| 4 | `GET /dashboard/painel?dias=45` (fora de `{15,30,90,180}`) | 422 |
| 5 | `usuario_display_e_token` em `GET /panes`, `GET /aeronaves`, `GET /configuracoes`, `GET /dashboard/resumo` | 403 em cada uma |
| 6 | `usuario_display_e_token` em `GET /tv` | 200 |
| 7 | `usuario_display_e_token` em `POST /auth/refresh` | 200, cookies renovados |
| 8 | Pane aberta sem `sistema_ata_id` | `sistema_ata is None` no payload, sem erro 500 |
| 9 | Pane aberta com `sistema_ata` cadastrado | `sistema_ata == "{codigo} - {descricao}"` |
| 10 | Inspeção com 4 tarefas, 3 concluídas | `progresso_percentual == 75` |
| 11 | Vencimento com prorrogação ativa cuja nova data já passou | `status == "VENCIDO"`, `prorrogado == True` |
| 12 | Vencimento com prorrogação ativa cuja nova data não passou | `status == "PRORROGADO"` |
| 13 | Vencimento com `data_vencimento` há 40 dias no passado, `dias=30` | aparece na lista (já vencido, fora do horizonte não exclui vencidos) |
| 14 | `dashboard/service.get_vencimentos_summary` (resumo atual) após a Etapa 3 | contagem bate com status derivado, não com a coluna crua |
| 15 | Aeronave com pane aberta e status cadastrado `DISPONIVEL` | `resolver_status_frota(...) == "INDISPONIVEL"` |
| 16 | Aeronave com inspeção ativa E pane aberta | `resolver_status_frota(...) == "INSPEÇÃO"` (inspeção tem prioridade) |

---

## 16. Verificação end-to-end

```bash
pytest tests/unit/test_painel_operacional.py -v
pytest -q                          # suíte completa — nenhum teste de dashboard/vencimentos/inspeções pode quebrar
ruff check app/modules/dashboard/ app/shared/core/ app/bootstrap/dependencies.py app/web/static/js/tv.js
python scripts/run_app.py          # sobe a aplicação para smoke manual
```

**Smoke manual:**
1. Login como ADMINISTRADOR → criar usuário `display` com função `DISPLAY` em `/efetivo`.
2. Logout → login como `display` → `/tv` renderiza; tentar acessar `/dashboard`, `/panes`, `/configuracoes`
   diretamente pela URL → 403/redirecionamento, nenhum dado vaza.
3. Janela em 1920x1080 (ou emulação DevTools) — sem barra de rolagem global; relógio L/Z avançando a cada
   segundo; auto-scroll do card de panes rolando e pausando nas pontas.
4. DevTools → Network → bloquear `/dashboard/painel` temporariamente → indicador de "sem conexão" aparece;
   desbloquear → sincroniza sozinho, sem recarregar a página nem redirecionar para `/login`.
5. Deixar a aba aberta por **mais de 20 minutos** (além dos 15 min de validade do access token) e confirmar
   que os dados continuam atualizando — a sessão não caiu.
6. Abrir em um tablet (ou emulação de viewport paisagem/retrato): os botões `15d/1m/3m/6m` trocam o horizonte
   e a lista de vencimentos re-renderiza.
7. Console do DevTools: nenhuma violação de CSP ao longo de todo o fluxo acima.

---

## 17. Riscos e armadilhas conhecidas

| # | Risco | Mitigação |
|---|---|---|
| R1 | `DISPLAY` herdar acesso amplo — hoje ~111 pontos só exigem "autenticado" (`CurrentUser`) | Deny-by-default dentro do próprio `get_current_user` (Etapa 5); testes de `403` explícitos por rota (caso 5 da tabela de testes) |
| R2 | `hasPermission` (`auth_check.js:99`) liberar UI de MANTENEDOR para `DISPLAY` caso ele abra outra página por engano | Guarda explícita no início da função (Etapa 13) |
| R3 | `clearAuth()`/redirecionamento em falha de rede transitória derrubar a TV de madrugada | `tv.js` usa `fetch` direto, não `apiFetch`, para `/dashboard/painel` e `/auth/refresh` (Etapa 13) |
| R4 | Progresso das inspeções gerar N+1 ao computar por aeronave | `contar_tarefas_por_inspecao` em lote, movido para `shared/core/helpers.py` (Etapa 4) |
| R5 | Mover `calcular_status_vencimento` quebrar os ~11 endpoints que já importam de `vencimentos/service.py` | Reexport (`from app.shared.core.helpers import ...`) mantém o caminho de import antigo funcionando; suíte completa como gate |
| R6 | Corrigir `get_vencimentos_summary` (Etapa 3) mudar a contagem que `tests/unit/test_dashboard.py` já asserta | Rodar a suíte completa do dashboard depois da Etapa 3, antes de prosseguir; ajustar fixtures de teste se algum caso assumia o comportamento antigo (incorreto) |
| R7 | Poluição do banco em memória entre testes (`test_performance_audit.py` faz `db.commit()`) falsear os testes novos | Nunca assertar total/contagem global — sempre filtrar pela matrícula/UUID único criado no próprio teste |
| R8 | `resolver_status_frota` e `calcular_status_vencimento` divergirem silenciosamente entre o dashboard antigo e o painel novo se alguém editar só um dos dois no futuro | Um único helper compartilhado em `shared/core/helpers.py`, os dois services chamam a mesma função — não há mais onde divergir |

---

## 18. Checklist de aceite (espelha a spec §5)

- [ ] Tela `/tv` preenche 100% do viewport (`100dvh`) sem barra de rolagem global.
- [ ] Relógio Local (`L`) e Zulu (`Z`) atualizam a cada segundo, com data no formato `16 AGO 2026`.
- [ ] Resumo de frota reflete os seis status reais (`DISPONIVEL/OPERACIONAL/INDISPONIVEL/INSPEÇÃO/ESTOCADA/INATIVA`), agrupados nos quatro indicadores.
- [ ] Lista de panes abertas sem limite de 5, com sistema ATA no formato `código - descrição` quando disponível.
- [ ] Lista de inspeções ativas sem limite de 5, com progresso percentual calculado sem N+1.
- [ ] Lista de vencimentos com status sempre derivado (nunca a coluna persistida), filtro padrão 30 dias, botões `15d/1m/3m/6m` funcionais no tablet.
- [ ] Tema forçado em Dark independentemente da preferência salva do usuário logado.
- [ ] Usuário `DISPLAY` acessa `/tv` e `GET /dashboard/painel`; recebe `403` em qualquer outra rota.
- [ ] Sessão da TV sobrevive a mais de 15 minutos via silent refresh, sem novo login.
- [ ] Falha de rede transitória mostra indicador de "sem conexão" e se recupera sozinha, sem deslogar.
- [ ] `pytest -q` verde (suíte completa, sem regressão em `dashboard`/`vencimentos`/`inspeções`).
- [ ] `ruff check` limpo nos arquivos tocados.
- [ ] Nenhuma violação de CSP no console do navegador.
