# Plano de Implementação: Separação de Seeds e Inventário por Aeronave (Opção A)

## Objetivo

Separar as seeds de catálogo (`ModeloEquipamento`) e mapa físico (`SlotInventario`), garantir que a query de inventário de uma aeronave retorne todos os slots (incluindo vagos), e remover a seed `seed_slots.py` vazia.

Não há alteração de schema — o modelo atual está correto.

---

## Etapas

### 1. Renomear `seed_equipamentos.py` → `seed_modelos.py`

Extrair apenas a lógica de `ModeloEquipamento`. O arquivo passa a popular somente o catálogo de PNs.

```python
# scripts/seed/seed_modelos.py
MODELOS = [
    {"pn": "622-7382-101", "nome": "ADF"},
    {"pn": "622-7309-101", "nome": "DME"},
    # ... todos os PNs únicos
]

async def run(session: AsyncSession):
    for data in MODELOS:
        res = await session.execute(
            select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"])
        )
        if not res.scalar_one_or_none():
            session.add(ModeloEquipamento(
                id=uuid.uuid4(),
                part_number=data["pn"],
                nome_generico=data["nome"]
            ))
    await session.commit()
```

**Atenção:** PNs repetidos na lista atual (ex: `MB387B-01` aparece 4x para CMFD1–4, `MA902B-02` para MDP1/MDP2) devem ser deduplicados — um único `ModeloEquipamento` por PN.

---

### 2. Escrever `seed_slots.py`

Popula `SlotInventario` com o mapa físico completo. Depende de `seed_modelos.py` já ter rodado (busca o `modelo_id` pelo PN).

```python
# scripts/seed/seed_slots.py
SLOTS = [
    # CEI
    {"slot": "ADF",        "pn": "622-7382-101",    "loc": "CEI", "pos": "TEC"},
    {"slot": "DME",        "pn": "622-7309-101",    "loc": "CEI", "pos": "TEC"},
    {"slot": "TDR",        "pn": "622-9352-004",    "loc": "CEI", "pos": "TEC"},
    {"slot": "STORMSCOPE", "pn": "78-8060-6086-5",  "loc": "CEI", "pos": "CEL"},
    {"slot": "EGIR",       "pn": "34200802-80RB",   "loc": "CEI", "pos": "FC"},
    {"slot": "VOR",        "pn": "622-7194-201",    "loc": "CEI", "pos": "TEC"},
    {"slot": "MDP1",       "pn": "MA902B-02",       "loc": "CEI", "pos": "EL1"},
    {"slot": "MDP2",       "pn": "MA902B-02",       "loc": "CEI", "pos": "EL2"},
    {"slot": "ARTU",       "pn": "251-118-012-012", "loc": "CEI", "pos": "CEL"},
    {"slot": "AFDC",       "pn": "449100-02-01",    "loc": "CEI", "pos": "TEC"},
    {"slot": "VUHF1",      "pn": "6110.3001.12",    "loc": "CEI", "pos": "CEL"},
    {"slot": "VUHF2",      "pn": "6106.7006.12",    "loc": "CEI", "pos": "CEL"},
    # 1P
    {"slot": "AMPMIC-1P",  "pn": "263-000",         "loc": "1P",  "pos": "CAD"},
    {"slot": "PDU",        "pn": "4455-1000-01",    "loc": "1P",  "pos": "P1P"},
    {"slot": "UFCP",       "pn": "4456-1000-02",    "loc": "1P",  "pos": "P1P"},
    {"slot": "CHVC",       "pn": "VEC00054",        "loc": "1P",  "pos": "P1P"},
    {"slot": "CMFD1",      "pn": "MB387B-01",       "loc": "1P",  "pos": "MF1"},
    {"slot": "CMFD2",      "pn": "MB387B-01",       "loc": "1P",  "pos": "MF2"},
    {"slot": "ASP-1P",     "pn": "343-001",         "loc": "1P",  "pos": "P1P"},
    {"slot": "GPS",        "pn": "066-04031-1622",  "loc": "1P",  "pos": "CAD"},
    {"slot": "PA CONTROL", "pn": "449300-02-01",    "loc": "1P",  "pos": "TC6"},
    {"slot": "PIC/NAV",    "pn": "314-04895-403",   "loc": "1P",  "pos": "P1P"},
    {"slot": "STICKGRIP-1P","pn": "733-0402",       "loc": "1P",  "pos": "CAD"},
    {"slot": "DVR",        "pn": "MB211E-03",       "loc": "1P",  "pos": "CAD"},
    # 2P
    {"slot": "AMPMIC-2P",  "pn": "263-000",         "loc": "2P",  "pos": "CAT"},
    {"slot": "PSU",        "pn": "4458-1000-00",    "loc": "2P",  "pos": "FC"},
    {"slot": "CMFD3",      "pn": "MB387B-01",       "loc": "2P",  "pos": "MF3"},
    {"slot": "CMFD4",      "pn": "MB387B-01",       "loc": "2P",  "pos": "MF4"},
    {"slot": "ASP-2P",     "pn": "343-001",         "loc": "2P",  "pos": "P2P"},
    {"slot": "STICKGRIP-2P","pn": "733-0402",       "loc": "2P",  "pos": "CAT"},
    # CES
    {"slot": "VADR",       "pn": "174521-10-01",    "loc": "CES", "pos": "FC"},
    {"slot": "ELT",        "pn": "453-5000-710",    "loc": "CES", "pos": "FC"},
    {"slot": "BEACON",     "pn": "DK120",           "loc": "CES", "pos": "FC"},
]

async def run(session: AsyncSession):
    for data in SLOTS:
        # Busca o modelo pelo PN (deve existir após seed_modelos)
        res_mod = await session.execute(
            select(ModeloEquipamento).where(ModeloEquipamento.part_number == data["pn"])
        )
        modelo = res_mod.scalar_one_or_none()
        if not modelo:
            raise ValueError(f"ModeloEquipamento não encontrado para PN={data['pn']}. Rode seed_modelos primeiro.")

        res_slot = await session.execute(
            select(SlotInventario).where(
                SlotInventario.nome_posicao == data["slot"],
                SlotInventario.sistema == data["loc"]
            )
        )
        if not res_slot.scalar_one_or_none():
            session.add(SlotInventario(
                id=uuid.uuid4(),
                nome_posicao=data["slot"],
                sistema=data["loc"],
                posicao_xlsx=data["pos"],
                modelo_id=modelo.id,
            ))
    await session.commit()
```

---

### 3. Atualizar o runner de seeds

O runner principal (ex: `scripts/seed/run_seeds.py` ou equivalente) deve garantir a ordem de execução:

```
seed_modelos → seed_slots → seed_aeronaves → seed_inventario (xlsx)
```

Verificar o arquivo atual de orquestração e atualizar as importações.

---

### 4. Implementar query de inventário completo por aeronave

Adicionar no service de equipamentos (ou criar um service de inventário) a query que retorna todos os slots, com ou sem SN instalado:

```python
# app/modules/equipamentos/service.py (ou inventario_service.py)

async def get_inventario_aeronave(
    aeronave_id: uuid.UUID,
    session: AsyncSession
) -> list[SlotComInstalacao]:
    """
    Retorna todos os slots do template com o item atualmente instalado.
    Slots sem instalação ativa retornam com item=None.
    """
    stmt = (
        select(SlotInventario, ItemEquipamento, ModeloEquipamento)
        .join(ModeloEquipamento, SlotInventario.modelo_id == ModeloEquipamento.id)
        .outerjoin(
            Instalacao,
            and_(
                Instalacao.slot_id == SlotInventario.id,
                Instalacao.aeronave_id == aeronave_id,
                Instalacao.data_remocao.is_(None),
            )
        )
        .outerjoin(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .order_by(SlotInventario.sistema, SlotInventario.nome_posicao)
    )
    rows = await session.execute(stmt)
    return rows.all()
```

---

### 5. Adicionar endpoint de inventário por aeronave

```
GET /aeronaves/{aeronave_id}/inventario
```

Retorna a lista de todos os slots com o item instalado (ou vago). Agrupar por `sistema` (CEI, 1P, 2P, CES) para facilitar a exibição.

**Schema de resposta sugerido:**

```python
class SlotInventarioResponse(BaseModel):
    slot: str           # nome_posicao (ex: "MDP1")
    sistema: str        # localização (ex: "CEI")
    pos: str | None     # código XLSX (ex: "EL1")
    pn: str             # part number esperado
    equipamento: str    # nome genérico
    sn: str | None      # serial number instalado (None = vago)
    data_instalacao: date | None
```

---

### 6. Remover o arquivo `seed_slots.py` atual (vazio)

O arquivo `scripts/seed/seed_slots.py` existe mas está vazio (1 linha). Substituir pelo arquivo escrito na etapa 2.

---

## Ordem de execução

```
1. seed_modelos.py   → ModeloEquipamento
2. seed_slots.py     → SlotInventario (depende de 1)
3. seed_aeronaves.py → Aeronave (se existir)
4. XLSX upload       → ItemEquipamento + Instalacao (depende de 1, 2, 3)
```

## Checklist

- [x] Criar `scripts/seed/seed_modelos.py` com PNs deduplicados
- [x] Escrever `scripts/seed/seed_slots.py` com o mapa completo
- [x] Atualizar o runner de seeds com a ordem correta (`seed_modelos` → `seed_slots`)
- [x] Remover a lógica de slots de `seed_equipamentos.py` (convertido em wrapper legado)
- [x] Implementar `get_inventario_aeronave()` no service (já existia — validado)
- [x] Criar endpoint `GET /aeronaves/{aeronave_id}/inventario` (já existia — validado)
- [x] Testar query com slots vagos (LEFT JOIN) — validado pelo teste isolado
- [x] Verificar que o upload XLSX continua funcionando após a separação — `init_local.py` executado com sucesso

> **Status:** ✅ Implementação concluída em 14/05/2026. Todos os itens validados.
> Teste isolado: `scripts/test_seed_refactor.py` (pode ser removido após aprovação).

---

## 🤖 Análise e Parecer (IA)

**Data da Análise:** 14 de Maio de 2026

Após analisar o código atual e a proposta descrita neste documento, apresento o seguinte parecer:

### 1. Coerência e Viabilidade
A proposta de refatorar e separar as seeds (Etapas 1, 2, 3 e 6) é **coerente** com os princípios de responsabilidade única e arquitetura limpa, separando a definição do catálogo (Modelos/PNs) do mapa físico da aeronave (Slots). A implantação é **totalmente viável** e de baixa complexidade.

### 2. Sobreposição com o Escopo Atual (Atenção)
As **Etapas 4 e 5 já estão implementadas** no código atual do projeto:
- O endpoint `GET /inventario/{aeronave_id}` já existe em `app/modules/equipamentos/router.py`.
- O método `listar_inventario_aeronave` em `app/modules/equipamentos/service.py` já foi implementado e **já retorna todos os slots** da aeronave, inclusive os vagos, fazendo o cruzamento entre `SlotInventario` e `Instalacao` no nível da aplicação.

### 3. Conclusão
O refatoramento é válido apenas para a **organização das seeds**. As implementações da API e das lógicas de consulta (Etapas 4 e 5) não precisam ser feitas novamente, bastando validar se a refatoração das seeds não quebra o comportamento existente. Recomenda-se prosseguir com as Etapas 1, 2, 3 e 6 para melhor organização do projeto.
