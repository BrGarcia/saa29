"""
scripts/seed/seed_inspecoes.py
Popula dados de tipos de inspeção, catálogo de tarefas, templates e
instâncias de inspeções ativas para a frota.

Estrutura atual (desacoplada):
    TarefaCatalogo  → catálogo global de tarefas
    TarefaTemplate  → vínculo N:N entre TipoInspecao e TarefaCatalogo
    Inspecao        → instância de inspeção para uma aeronave
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes.models import TipoInspecao, TarefaCatalogo, TarefaTemplate
from app.modules.inspecoes.service import abrir_inspecao
from app.modules.inspecoes.schemas import InspecaoCreate

FROTA_ALVO = ["5902", "5905", "5906", "5912", "5914"]


async def run(session: AsyncSession):
    print("🚀 [Inspeções] Populando Tipos, Templates e Instâncias de Inspeção...")

    # 1. Obter usuário admin para autoria
    res_user = await session.execute(select(Usuario).limit(1))
    admin_user = res_user.scalars().first()
    if not admin_user:
        print("   ! Nenhum usuário encontrado. Pulando seed de inspeções.")
        return

    # 2. Criar Tipos de Inspeção se não existirem
    tipos_data = [
        {"codigo": "BFT", "nome": "Before Flight - Pré Voo",       "descricao": "Inspeção antes do primeiro voo do dia"},
        {"codigo": "PFI", "nome": "Post Flight - Pós Voo",          "descricao": "Inspeção após o último voo"},
        {"codigo": "50H", "nome": "Inspeção de 50 Horas",           "descricao": "Inspeção periódica de fase 50h"},
    ]

    tipos_dict: dict[str, TipoInspecao] = {}
    for tdata in tipos_data:
        res = await session.execute(
            select(TipoInspecao).where(TipoInspecao.codigo == tdata["codigo"])
        )
        tipo = res.scalar_one_or_none()
        if not tipo:
            tipo = TipoInspecao(**tdata)
            session.add(tipo)
            await session.flush()
        tipos_dict[tdata["codigo"]] = tipo

    # 3. Criar Catálogo Global de Tarefas (se ainda não houver nenhuma)
    res_cat = await session.execute(select(TarefaCatalogo).limit(1))
    catalogo_vazio = res_cat.scalar_one_or_none() is None

    # Definição do catálogo: (título, descrição, sistema)
    catalogo_raw = [
        # BFT
        ("Inspeção Externa Geral",        "Verificar ausência de danos na fuselagem",            "Fuselagem"),
        ("Verificação de Pneus",          "Checar pressão e desgaste dos pneus",                 "Trem de Pouso"),
        ("Fluidos Hidráulicos",           "Checar nível do reservatório principal e freios",      "Hidráulico"),
        ("Nível de Óleo do Motor",        "Checar nível de óleo do motor PT6",                   "Motor"),
        ("Tubo de Pitot e Estática",      "Remover capas e verificar desobstrução",              "Aviônicos"),
        ("Cockpit Geral",                 "Verificar assentos, cintos e comandos",               "Cabine"),
        ("Teste de Bateria (BFT)",        "Ligar bateria e checar voltagem mínima de 24V",       "Elétrica"),
        # PFI
        ("Instalação de Capas e Pinos",   "Colocar pinos de segurança e capas de pitot/AOA",    "Geral"),
        ("Inspeção Motor Pós Voo",        "Verificar vazamentos de óleo pós corte",              "Motor"),
        ("Superfícies de Controle",       "Verificar dobradiças e atuadores",                   "Fuselagem"),
        ("Freios Pós Voo",                "Verificar temperatura e desgaste de pastilhas",       "Trem de Pouso"),
        ("Canopy",                        "Limpar e inspecionar trincas",                        "Cabine"),
        ("Bateria Pós Voo",               "Desligar e verificar disjuntores abertos",            "Elétrica"),
        # 50H
        ("Lubrificação do Trem de Pouso", "Graxa nas articulações conforme manual",              "Trem de Pouso"),
        ("Filtro de Óleo 50H",            "Remover, inspecionar e limpar filtro de tela",        "Motor"),
        ("Bateria Principal 50H",         "Remoção para teste de capacidade em bancada",         "Elétrica"),
        ("Extintor de Incêndio",          "Verificar pressão do manômetro e validade",           "Emergência"),
        ("Assento Ejetável",              "Inspeção visual dos cartuchos e pinos",               "Cabine"),
        ("Filtro do Ar Condicionado",     "Inspecionar e limpar filtro ECS",                    "Pneumático"),
        ("Teste Operacional de Luzes",    "Testar Landing/Taxi/Nav/Anti-Collision",              "Elétrica"),
    ]

    catalogo_por_titulo: dict[str, TarefaCatalogo] = {}

    if catalogo_vazio:
        for titulo, descricao, sistema in catalogo_raw:
            tc = TarefaCatalogo(titulo=titulo, descricao=descricao, sistema=sistema)
            session.add(tc)
            catalogo_por_titulo[titulo] = tc
        await session.flush()
        print(f"   + {len(catalogo_raw)} Tarefas adicionadas ao Catálogo Global.")
    else:
        # Já existe catálogo — apenas carrega para referenciar nos templates
        res_all = await session.execute(select(TarefaCatalogo))
        for tc in res_all.scalars().all():
            catalogo_por_titulo[tc.titulo] = tc

    # 4. Vincular Tarefas ao Template de cada Tipo (se ainda não houver vínculos)
    res_tmpl = await session.execute(select(TarefaTemplate).limit(1))
    templates_vazios = res_tmpl.scalar_one_or_none() is None

    if templates_vazios:
        # BFT: tarefas 0-6 do catálogo_raw (índices 0 a 6), obrigatórias todas
        bft_tarefas = [
            ("Inspeção Externa Geral",    True),
            ("Verificação de Pneus",      True),
            ("Fluidos Hidráulicos",       True),
            ("Nível de Óleo do Motor",    True),
            ("Tubo de Pitot e Estática",  True),
            ("Cockpit Geral",             True),
            ("Teste de Bateria (BFT)",    True),
        ]
        # PFI: índices 7-12
        pfi_tarefas = [
            ("Instalação de Capas e Pinos", True),
            ("Inspeção Motor Pós Voo",      True),
            ("Superfícies de Controle",     True),
            ("Freios Pós Voo",              True),
            ("Canopy",                      False),
            ("Bateria Pós Voo",             True),
        ]
        # 50H: índices 13-19
        h50_tarefas = [
            ("Lubrificação do Trem de Pouso", True),
            ("Filtro de Óleo 50H",            True),
            ("Bateria Principal 50H",          True),
            ("Extintor de Incêndio",           True),
            ("Assento Ejetável",               True),
            ("Filtro do Ar Condicionado",      False),
            ("Teste Operacional de Luzes",     True),
        ]

        def _vincular(tipo_obj: TipoInspecao, lista: list[tuple[str, bool]]) -> None:
            for i, (titulo, obrig) in enumerate(lista, start=1):
                tc = catalogo_por_titulo.get(titulo)
                if tc:
                    session.add(TarefaTemplate(
                        tipo_inspecao_id=tipo_obj.id,
                        tarefa_catalogo_id=tc.id,
                        ordem=i,
                        obrigatoria=obrig,
                    ))

        _vincular(tipos_dict["BFT"], bft_tarefas)
        _vincular(tipos_dict["PFI"], pfi_tarefas)
        _vincular(tipos_dict["50H"], h50_tarefas)
        await session.flush()
        print("   + Templates vinculados: BFT (7 tarefas), PFI (6), 50H (7).")

    # 5. Abrir Inspeções para aeronaves alvo (se disponíveis)
    res_acft = await session.execute(
        select(Aeronave).where(Aeronave.matricula.in_(FROTA_ALVO))
    )
    aeronaves_alvo = res_acft.scalars().all()

    inspecoes_criadas = 0
    for acft in aeronaves_alvo:
        if acft.status != "DISPONIVEL":
            continue  # já em inspeção ou outro status

        if acft.matricula in ["5902", "5905"]:
            tipos_ids = [tipos_dict["BFT"].id]
        elif acft.matricula in ["5906", "5912"]:
            tipos_ids = [tipos_dict["PFI"].id]
        else:  # 5914
            tipos_ids = [tipos_dict["50H"].id, tipos_dict["BFT"].id]

        dados = InspecaoCreate(
            aeronave_id=acft.id,
            tipos_inspecao_ids=tipos_ids,
            observacoes=f"Inspeção automática de seed ({uuid.uuid4().hex[:6]})",
        )
        try:
            await abrir_inspecao(session, dados, admin_user.id)
            inspecoes_criadas += 1
        except Exception as e:
            print(f"   ! Falha ao abrir inspeção para {acft.matricula}: {e}")

    await session.flush()
    if inspecoes_criadas > 0:
        print(f"   + {inspecoes_criadas} inspeções ativas abertas nas aeronaves.")
