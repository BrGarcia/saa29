"""
scripts/seed/seed_inspecoes.py
Popula dados de tipos de inspeção, templates de tarefas e instâncias de inspeções ativas para a frota.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes.models import TipoInspecao, TarefaTemplate
from app.modules.inspecoes.service import abrir_inspecao
from app.modules.inspecoes.schemas import InspecaoCreate
from app.shared.core.enums import StatusInspecao

FROTA_ALVO = ["5902", "5905", "5906", "5912", "5914"]

async def run(session: AsyncSession):
    print(f"🚀 [Inspeções] Populando Tipos, Templates e Instâncias de Inspeção...")

    # 1. Obter usuário (admin ou qualquer um para autoria)
    res_user = await session.execute(select(Usuario).limit(1))
    admin_user = res_user.scalars().first()
    if not admin_user:
        print("   ! Nenhum usuário encontrado. Pulando seed de inspeções.")
        return

    # 2. Criar Tipos de Inspeção se não existirem
    tipos_data = [
        {"codigo": "BFT", "nome": "Before Flight - Pré Voo", "descricao": "Inspeção antes do primeiro voo do dia"},
        {"codigo": "PFI", "nome": "Post Flight Inspection - Pós Voo", "descricao": "Inspeção após o último voo"},
        {"codigo": "50H", "nome": "Inspeção de 50 Horas", "descricao": "Inspeção periódica de fase 50h"}
    ]

    tipos_dict = {}
    for tdata in tipos_data:
        res = await session.execute(select(TipoInspecao).where(TipoInspecao.codigo == tdata["codigo"]))
        tipo = res.scalar_one_or_none()
        if not tipo:
            tipo = TipoInspecao(**tdata)
            session.add(tipo)
            await session.flush()
        tipos_dict[tdata["codigo"]] = tipo

    # 3. Criar Tarefas Templates (20 tarefas distintas)
    # BFT: 7 tarefas
    tarefas_bft = [
        (1, "Inspeção Externa Geral", "Verificar ausência de danos na fuselagem", "Fuselagem", True),
        (2, "Verificação de Pneus", "Checar pressão e desgaste dos pneus do trem principal e nariz", "Trem de Pouso", True),
        (3, "Fluidos Hidráulicos", "Checar nível do reservatório principal e freios", "Hidráulico", True),
        (4, "Nível de Óleo", "Checar nível de óleo do motor PT6", "Motor", True),
        (5, "Tubo de Pitot e Estática", "Remover capas e verificar desobstrução", "Aviônicos", True),
        (6, "Cockpit Geral", "Verificar assentos, cintos e desobstrução dos comandos", "Cabine", True),
        (7, "Teste de Bateria", "Ligar bateria e checar voltagem mínima de 24V", "Elétrica", True)
    ]
    
    # PFI: 6 tarefas
    tarefas_pfi = [
        (1, "Instalação de Capas e Pinos", "Colocar pinos de segurança e capas de pitot/AOA", "Geral", True),
        (2, "Inspeção Pós Voo Motor", "Verificar vazamentos de óleo pós corte", "Motor", True),
        (3, "Superfícies de Controle", "Verificar dobradiças e atuadores", "Fuselagem", True),
        (4, "Freios", "Verificar temperatura e desgaste de pastilhas", "Trem de Pouso", True),
        (5, "Canopy", "Limpar e inspecionar trincas", "Cabine", False),
        (6, "Bateria", "Desligar e verificar disjuntores abertos", "Elétrica", True)
    ]

    # 50H: 7 tarefas
    tarefas_50h = [
        (1, "Lubrificação do Trem de Pouso", "Graxa nas articulações conforme manual", "Trem de Pouso", True),
        (2, "Filtro de Óleo", "Remover, inspecionar e limpar filtro de tela", "Motor", True),
        (3, "Bateria Principal", "Remoção para teste de capacidade em bancada", "Elétrica", True),
        (4, "Extintor de Incêndio", "Verificar pressão do manômetro e validade", "Emergência", True),
        (5, "Assento Ejetável", "Inspeção visual dos cartuchos e pinos de segurança", "Cabine", True),
        (6, "Filtro do Ar Condicionado", "Inspecionar e limpar filtro ECS", "Pneumático", False),
        (7, "Teste Operacional de Luzes", "Testar Landing/Taxi/Nav/Anti-Collision", "Elétrica", True)
    ]

    def _add_tarefas(tipo_obj, tarefas_list):
        for t in tarefas_list:
            session.add(TarefaTemplate(
                tipo_inspecao_id=tipo_obj.id,
                ordem=t[0],
                titulo=t[1],
                descricao_padrao=t[2],
                sistema=t[3],
                obrigatoria=t[4]
            ))

    # Verifica se já temos tarefas cadastradas
    res_tarefas = await session.execute(select(TarefaTemplate))
    if not res_tarefas.scalars().first():
        _add_tarefas(tipos_dict["BFT"], tarefas_bft)
        _add_tarefas(tipos_dict["PFI"], tarefas_pfi)
        _add_tarefas(tipos_dict["50H"], tarefas_50h)
        await session.flush()
        print("   + 20 Tarefas Template adicionadas.")

    # 4. Criar Inspeções para 5 Aeronaves (se não existirem)
    res_acft = await session.execute(select(Aeronave).where(Aeronave.matricula.in_(FROTA_ALVO)))
    aeronaves_alvo = res_acft.scalars().all()

    inspecoes_criadas = 0
    for acft in aeronaves_alvo:
        # Pula se a aeronave já estiver em inspeção ou outro status não disponível (para não bugar testes/seeds repetidos)
        if acft.status != "DISPONIVEL":
            continue
            
        # Determina o pacote de inspeção dependendo da aeronave
        tipos_ids = []
        if acft.matricula in ["5902", "5905"]:
            tipos_ids = [tipos_dict["BFT"].id]
        elif acft.matricula in ["5906", "5912"]:
            tipos_ids = [tipos_dict["PFI"].id]
        else: # 5914
            tipos_ids = [tipos_dict["50H"].id, tipos_dict["BFT"].id] # Multiplos tipos!

        dados = InspecaoCreate(
            aeronave_id=acft.id,
            tipos_inspecao_ids=tipos_ids,
            observacoes=f"Inspeção automática de seed (Seed ID: {uuid.uuid4().hex[:6]})"
        )
        
        try:
            await abrir_inspecao(session, dados, admin_user.id)
            inspecoes_criadas += 1
        except Exception as e:
            print(f"   ! Falha ao abrir inspeção para {acft.matricula}: {e}")

    await session.flush()
    if inspecoes_criadas > 0:
        print(f"   + {inspecoes_criadas} inspeções ativas abertas nas aeronaves.")
