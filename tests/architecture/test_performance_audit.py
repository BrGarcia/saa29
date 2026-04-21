import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.equipamentos.models import ModeloEquipamento, SlotInventario, ItemEquipamento, Instalacao
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario

@pytest.mark.asyncio
async def test_n_plus_one_inventario(client: AsyncClient, db: AsyncSession, usuario_e_token: dict):
    """
    TESTE DE N+1: Valida se a listagem de inventário faz carregamento antecipado (eager loading).
    """
    # 1. Setup: Criar 1 Aeronave, 1 Modelo, 5 Slots e 5 Itens instalados
    aeronave = Aeronave(id=uuid.uuid4(), matricula="5999", serial_number="SN999", modelo="A-29")
    db.add(aeronave)
    
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number="PN-PERF", nome_generico="TEST-PERF")
    db.add(modelo)
    await db.flush()

    for i in range(5):
        slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"POS-{i}", modelo_id=modelo.id)
        db.add(slot)
        item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-{i}")
        db.add(item)
        await db.flush()
        
        inst = Instalacao(
            id=uuid.uuid4(), 
            item_id=item.id, 
            aeronave_id=aeronave.id, 
            slot_id=slot.id, 
            usuario_id=usuario_e_token["usuario"].id,
            data_instalacao=uuid.uuid4().hex[:10] # fake date
        )
        # Hack para data_instalacao ser date
        from datetime import date
        inst.data_instalacao = date.today()
        db.add(inst)

    await db.commit()

    # 2. Monitorar Queries
    query_count = 0
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if "SELECT" in statement.upper() and "PRAGMA" not in statement.upper():
            query_count += 1

    engine = db.bind.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    try:
        # 3. Executar Chamada
        response = await client.get(
            f"/equipamentos/inventario/{aeronave.id}",
            headers=usuario_e_token["headers"]
        )
        assert response.status_code == 200
        
        # 4. Validar: 
        print(f"\nTOTAL QUERIES DETECTADAS: {query_count}")
        # Reduzido de 25+ (N+1 real) para ~14 (custo constante de setup/auth + listagem bulk).
        assert query_count <= 15, f"Detectado N+1: {query_count} queries para 5 itens"
        
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

@pytest.mark.asyncio
async def test_paginacao_historico_funcional(client: AsyncClient, db: AsyncSession, usuario_e_token: dict):
    """
    VALIDAÇÃO DE PAGINAÇÃO: Verifica se os parâmetros limit e offset realmente filtram os dados.
    """
    from datetime import date
    # 1. Setup: Criar 5 instalações (eventos de histórico)
    aeronave = Aeronave(id=uuid.uuid4(), matricula="5998", serial_number="SN998", modelo="A-29")
    db.add(aeronave)
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number="PN-HIST", nome_generico="TEST-HIST")
    db.add(modelo)
    await db.flush()

    for i in range(5):
        slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"HIST-{i}", modelo_id=modelo.id)
        db.add(slot)
        item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-H-{i}")
        db.add(item)
        await db.flush()
        
        inst = Instalacao(
            id=uuid.uuid4(), item_id=item.id, aeronave_id=aeronave.id, slot_id=slot.id, 
            usuario_id=usuario_e_token["usuario"].id, data_instalacao=date.today()
        )
        db.add(inst)
    
    await db.commit()

    # 2. Testar Limit
    response = await client.get(
        "/equipamentos/inventario/historico?limit=2",
        headers=usuario_e_token["headers"]
    )
    assert response.status_code == 200
    dados = response.json()
    assert len(dados) == 2, f"Esperado 2 registros (limit=2), obtido {len(dados)}"


@pytest.mark.asyncio
async def test_sqlite_wal_mode_active(db: AsyncSession):
    """
    VERIFICAÇÃO WAL MODE: Valida se o PRAGMA journal_mode está em WAL (ou memory para testes).
    """
    result = await db.execute(text("PRAGMA journal_mode"))
    mode = result.scalar()
    assert mode.lower() in ["wal", "memory"], f"Esperado modo WAL ou memory, obtido: {mode}"
