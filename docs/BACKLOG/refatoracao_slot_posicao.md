# Análise: Arquitetura de Slots e Inventário por Aeronave

## Contexto

Cada aeronave possui um inventário físico próprio. O inventário é composto por **slots** — posições físicas predefinidas que aceitam um equipamento de PN específico. Quando um item é instalado, o SN do equipamento é registrado naquele slot. Uma aeronave pode ter dois equipamentos do mesmo PN em slots distintos (ex: MDP1 e MDP2). O campo `pos` do slot define o código de posição daquela localização específica (mapeado na planilha XLSX).

**Premissa confirmada:** toda a frota é do mesmo tipo de aeronave. Os slots são idênticos entre aeronaves.

---

## Modelo de Dados Atual

```
ModeloEquipamento (PN — catálogo global)
    └── SlotInventario (template global de posições físicas)
            └── Instalacao (Item + Slot + Aeronave + datas)
                    └── ItemEquipamento (instância física — SN)
```

### Entidades

| Entidade | Responsabilidade | Escopo |
|---|---|---|
| `ModeloEquipamento` | Catálogo de Part Numbers (PNs) | Global |
| `SlotInventario` | Mapa físico de posições da aeronave | Global (template) |
| `ItemEquipamento` | Instância física identificada por SN | Global |
| `Instalacao` | Registro de qual SN está em qual slot de qual aeronave | Por aeronave |

### Por que os slots são globais (template)

Como toda a frota é do mesmo tipo, todas as aeronaves compartilham o mesmo layout de slots. Não faz sentido duplicar os registros de `SlotInventario` por aeronave. O que difere entre aeronaves é **qual SN está instalado** em cada slot — isso é capturado pela `Instalacao`.

---

## O que a `Instalacao` resolve

A tabela `Instalacao` conecta:
- **Item** (SN físico) → **Slot** (posição predefinida) → **Aeronave** → intervalo de datas

Com isso:
- Inventário atual de uma aeronave = todas as `Instalacao` com `data_remocao IS NULL` para aquela aeronave
- Histórico de um slot = todas as instalações naquele slot, ordenadas por data
- Rastreabilidade completa de um SN = todas as aeronaves onde foi instalado

---

## Identificação de slots vagos

Com slots como template global, um slot vago **não gera registro** na tabela `Instalacao`. Para obter o inventário completo (incluindo posições vazias), a query é:

```sql
SELECT s.*, i.numero_serie
FROM slots_inventario s
LEFT JOIN instalacoes inst
    ON inst.slot_id = s.id
    AND inst.aeronave_id = :aeronave_id
    AND inst.data_remocao IS NULL
LEFT JOIN itens_equipamento i ON i.id = inst.item_id
```

Isso retorna todos os slots com o SN instalado, ou NULL para slots vagos.

---

## Separação das Seeds

O `seed_equipamentos.py` atual popula `ModeloEquipamento` e `SlotInventario` juntos. São responsabilidades distintas com ciclos de vida diferentes:

| | `ModeloEquipamento` | `SlotInventario` |
|---|---|---|
| O que é | Catálogo de PNs | Mapa físico da aeronave |
| Quando muda | Aquisição de novo tipo de equipamento | Reconfiguração da aeronave |
| Depende de | nada | `ModeloEquipamento` |

**Separação proposta:**
- `seed_modelos.py` — popula apenas `ModeloEquipamento` (PNs)
- `seed_slots.py` — popula apenas `SlotInventario` (depende de modelos já existirem)

---

## Opção Descartada: Slots por Aeronave (Opção B)

Foi considerada a alternativa de vincular `SlotInventario` diretamente à aeronave (com `aeronave_id`), o que permitiria representar slots vagos explicitamente como registros com `item_id = NULL`.

**Razão para descarte:** a frota é homogênea (mesmo tipo). Duplicar os N slots para cada aeronave gera redundância sem ganho funcional. A query com LEFT JOIN resolve o caso dos slots vagos de forma equivalente.
