"""
scripts/seed/seed_tarefas.py
Popula o catálogo global de tarefas (TarefaCatalogo) e fornece helpers para vinculação.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.inspecoes.models import TarefaCatalogo, TarefaTemplate, TipoInspecao

# Catálogo Global de Tarefas: (título, descrição, sistema)
CATALOGO_RAW = [
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

# Mapeamento de quais tarefas (do catálogo) compõem cada template
TEMPLATES_CONFIG = {
    "Y": [
        ("Inspeção Externa Geral", True),
        ("Cockpit Geral", True),
        ("Superfícies de Controle", True),
    ],
    "A": [
        ("Nível de Óleo do Motor", True),
        ("Fluidos Hidráulicos", True),
        ("Verificação de Pneus", True),
    ],
    "C": [
        ("Lubrificação do Trem de Pouso", True),
        ("Filtro de Óleo 50H", True),
        ("Assento Ejetável", True),
        ("Filtro do Ar Condicionado", False),
    ],
    # Fallback para os códigos antigos se necessário, ou apenas os novos
    "BFT": [("Inspeção Externa Geral", True)],
    "PFI": [("Instalação de Capas e Pinos", True)],
    "50H": [("Lubrificação do Trem de Pouso", True)],
}

# Expandindo para os ciclos acumulados (mesmas tarefas por enquanto)
for i in range(2, 5): TEMPLATES_CONFIG[f"{i}Y"] = TEMPLATES_CONFIG["Y"]
for i in range(2, 6): TEMPLATES_CONFIG[f"{i}A"] = TEMPLATES_CONFIG["A"]
for i in range(2, 4): TEMPLATES_CONFIG[f"{i}C"] = TEMPLATES_CONFIG["C"]

async def run(session: AsyncSession):
    """Popula o Catálogo Global e vincula templates se os tipos existirem."""
    print("🚀 [Tarefas] Populando Catálogo e Templates...")
    
    # 1. Catálogo
    res_cat = await session.execute(select(TarefaCatalogo).limit(1))
    if res_cat.scalar_one_or_none() is None:
        for titulo, descricao, sistema in CATALOGO_RAW:
            tc = TarefaCatalogo(titulo=titulo, descricao=descricao, sistema=sistema)
            session.add(tc)
        await session.flush()
        print(f"   + {len(CATALOGO_RAW)} tarefas no catálogo.")

    # 2. Templates (Vincular aos tipos que já foram criados pelo seed_inspecoes)
    res_tipos = await session.execute(select(TipoInspecao))
    tipos_dict = {t.codigo: t for t in res_tipos.scalars().all()}

    for codigo, config in TEMPLATES_CONFIG.items():
        tipo_obj = tipos_dict.get(codigo)
        if tipo_obj:
            await vincular_tarefas_ao_tipo(session, tipo_obj, config)
    
    print("   + Templates processados.")

async def get_catalogo_map(session: AsyncSession) -> dict[str, TarefaCatalogo]:
    """Retorna um dicionário {titulo: objeto} do catálogo."""
    res = await session.execute(select(TarefaCatalogo))
    return {tc.titulo: tc for tc in res.scalars().all()}

async def vincular_tarefas_ao_tipo(session: AsyncSession, tipo_obj: TipoInspecao, config: list[tuple[str, bool]]):
    """Vincula tarefas do catálogo a um tipo específico (Template)."""
    catalogo = await get_catalogo_map(session)
    
    # Verifica se já existem templates para este tipo
    res_tmpl = await session.execute(
        select(TarefaTemplate).where(TarefaTemplate.tipo_inspecao_id == tipo_obj.id).limit(1)
    )
    if res_tmpl.scalar_one_or_none():
        return # Já vinculado

    for i, (titulo, obrig) in enumerate(config, start=1):
        tc = catalogo.get(titulo)
        if tc:
            session.add(TarefaTemplate(
                tipo_inspecao_id=tipo_obj.id,
                tarefa_catalogo_id=tc.id,
                ordem=i,
                obrigatoria=obrig,
            ))
    await session.flush()
