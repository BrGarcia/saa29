# Achados do `DISCO_COMPLETO` — Estrutura dos DVDs de Publicações

> **Data da investigação:** 2026-08-10 · **Ambiente:** macOS, inspeção direta do filesystem.
>
> Este documento registra a **engenharia reversa completa** da estrutura dos dois discos de
> publicações técnicas (DVD de manutenção e DVD operacional) presentes em
> `var/publicacoes/DISCO_COMPLETO/`. Até esta data, o módulo `publicacoes` conhecia apenas o
> subconjunto `Data-ALX` (34 manuais de manutenção, documentados em
> [`02_formato_indice_lucene.md`](02_formato_indice_lucene.md)). Este documento amplia o
> inventário e identifica fontes de metadados estruturados ainda não aproveitadas.
>
> **Decisão de escopo:** o módulo **incluirá** os manuais operacionais (confirmado pelo responsável
> em 2026-08-10).

---

## 1. Topologia dos discos

O DVD de publicações contém **dois programas** (dois executáveis TechData independentes), cada um
com sua própria árvore `Data/`, `Index/`, `version/`:

```
var/publicacoes/DISCO_COMPLETO/
├── Program/                    ← Disco de MANUTENÇÃO (TechData 6.5.r.0, eTechPubs PC 7.5)
│   ├── TechData.exe            ← Visualizador Windows (Delphi/Borland, 19 MB)
│   ├── Data/                   ← PDFs + metadados XML + subpasta Data-ALX/
│   ├── Index/                  ← Índice de busca proprietário do TechData (PDX + IDX)
│   ├── version/                ← Revisão de cada manual (um .txt por manual)
│   ├── collections.ini         ← Nomes das coleções de manuais (PT-BR, encoding Latin-1)
│   ├── list.lst                ← Catálogo completo de TODOS os manuais da frota (8.143 linhas)
│   ├── tab_manual_aircraft.xml ← Mapeamento manual→aeronaves (666 KB, ~todas as frotas Embraer)
│   ├── tab_aircraft_manual.xml ← Mapeamento aeronave→manuais (72 KB)
│   ├── FAMILIES.XML            ← Famílias de aeronaves (EMB-110 a KC-390)
│   └── cnfAircraft.ini         ← Configuração: Indexes=14, Quant=1 (ALX, SN 00000)
│
└── Program_Operational/        ← Disco OPERACIONAL (TechData 4.3.4, mesmo visual)
    ├── dtData.exe / dopdata.exe ← Dois executáveis (mesmo tamanho: 897 KB cada)
    ├── Data/                   ← PDFs dos mesmos manuais + 4 manuais exclusivos
    ├── Index/                  ← Mesmo formato PDX proprietário (51 pares)
    ├── version/                ← Revisão por manual (revisão ANTERIOR à do Program/)
    ├── collections.ini         ← Idêntico ao do Program/
    ├── list.lst                ← Catálogo menor (403 KB vs 456 KB do Program/)
    ├── tab_manual_aircraft.xml ← Mesmo formato, conteúdo diferente
    └── tab_aircraft_manual.xml ← Idem

```

### 1.1 Identificação da aeronave

`cnfAircraft.ini` confirma que todo o disco é da família **EMB-314 (ALX)**, SN genérico 00000:

```ini
[AIRCRAFT]
Indexes=14
Quant=1
```

`ALXapplicability_control.xml` (presente em `Program/Data/` e `Program/Data/Data-ALX/Data/`)
detalha: família `EMB-314`, código `314`, modelo `ALX`, label `EMB-314 (ALX)`, com uma única
aeronave (SN 00000) e lista de 61 manuais aplicáveis.

### 1.2 Versão do software

- **Program (manutenção):** TechData 6.5.r.0.20161107 / eTechPubs PC 7.5 r0 20191209
- **Program_Operational:** TechData 4.3.4 (mesma versão de `dtdata.ini`)
- **Último acesso registrado:** 17/10/2022 10:48:59 (campo `DATE_LAST_ACCESS` em `TechData.ini`)

---

## 2. Inventário de PDFs

### 2.1 Contagem total

| Fonte | PDFs | Tamanho |
|---|---:|---:|
| `Program/Data/` (manutenção, inclui `Data-ALX/`) | **12.117** | **2,0 GB** |
| `Program_Operational/Data/` (operacional) | **6.629** | **1,1 GB** |
| **Total no disco** | **18.746** | **3,1 GB** |

> [!IMPORTANT]
> O `01_achados_do_acervo.md` contava **5.724 PDFs / 1,0 GB** porque trabalhava apenas com
> `var/publicacoes/acervo/Manuais/` (cópia normalizada do `Data-ALX`). O disco completo tem
> **3,3× mais PDFs** e **3,1× mais volume**.

### 2.2 Estrutura de réplicas

O disco contém **múltiplas cópias** dos mesmos manuais em revisões diferentes:

| Camada | Localização | Revisão | Uso |
|---|---|---|---|
| **Data-ALX** | `Program/Data/Data-ALX/Data/<MANUAL>/` | Revisão **intermediária** (a que o `01_achados` mediu) | Índice Lucene `index_2.0/` original |
| **Program/Data raiz** | `Program/Data/<MANUAL>/` | Revisão **mais recente** (2016) | TechData lê daqui |
| **Operational/Data** | `Program_Operational/Data/<MANUAL>/` | Revisão **mais antiga** (2013–2014) | Disco operacional |

Comparação de contagem de PDFs (Program/Data raiz vs Data-ALX) para os 34 manuais compartilhados:

| Manual | Raiz | Data-ALX | Δ | Manual | Raiz | Data-ALX | Δ |
|---|---:|---:|---:|---|---:|---:|---:|
| AMM_PART2_1651 | 1.281 | 1.139 | +142 | CPM_1740 | 37 | 33 | +4 |
| CMM_EMBRAERALX | 1.070 | 1.087 | −17 | LOAP_1744 | 10 | 7 | +3 |
| AIPC_1742 | 733 | 564 | +169 | ITEM_1743 | 442 | 430 | +12 |
| FIM_1741 | 615 | 569 | +46 | SWPM_1749 | 55 | 51 | +4 |
| AMM_PART1_1651 | 550 | 423 | +127 | NDT_1745 | 172 | 181 | −9 |
| WM_1647 | 494 | 495 | −1 | CMM_VALX | 28 | 31 | −3 |
| SSM_1748 | 208 | 161 | +47 | OTFN1A29AB5_0001 | 1 | 2 | −1 |
| SRM_PART2_1747 | 180 | 148 | +32 | CPC_1739 | 16 | 16 | 0 |
| SRM_PART1_1747 | 168 | 128 | +40 | MPD_1746 | 24 | 24 | 0 |

A maioria da raiz tem **mais** PDFs (revisão mais nova = mais seções); 4 manuais têm menos
(documentos removidos entre revisões). Os 16 OTFNs menores são idênticos.

> [!WARNING]
> **O módulo precisa decidir qual revisão é a fonte canônica.** Se o operador recebeu este DVD como
> a publicação vigente, a versão mais recente (Program/Data raiz) é a autoritativa. A Data-ALX é
> uma revisão anterior empacotada junto com o índice Lucene. Recomendação: usar a **raiz** como
> fonte de PDFs e a **Data-ALX** apenas para os `index_2.0/` (metadados Lucene).

### 2.3 Manuais exclusivos do disco operacional

4 manuais existem **apenas** em `Program_Operational/Data/` (não têm equivalente em `Program/Data/`):

| Código | Descrição (do `manual_details.xml`) | PDFs | Tamanho |
|---|---|---:|---:|
| `1BS_ALX_0000` | Boletim de Serviço | 182 | 105 MB |
| `2BI_ALX_0000` | Boletim de Informação | 2 | 128 KB |
| `5NPO_ALX_0000` | Notícias para Operadores | 44 | 4,5 MB |
| `BO_314PT_0000` | Boletins Operacionais | 4 | 636 KB |

> [!NOTE]
> `BO_314PT` também existe na raiz do `Program/Data/` com 13 PDFs (revisão mais recente), mas com
> o código `BO_314PT` (sem o sufixo `_0000`). No `Program_Operational/Data/` ele aparece como
> `BO_314PT_0000`. O `manual_details.xml` registra `partnumber="0000" type="BO_314PT"`.

### 2.4 Manuais exclusivos de `Program/Data` raiz (com `index_2.0/`)

15 manuais na raiz de `Program/Data/` possuem `index_2.0/` que **não existem em Data-ALX** — são
manuais que o índice Lucene original de Data-ALX nunca conheceu:

| Código | Descrição | PDFs | index_2.0 |
|---|---|---:|:---:|
| `BO_314PT` | Boletins Operacionais | 13 | ✅ |
| `GP_5206` | Publicação Geral — Programador de Escrita Aérea | 1 | ✅ |
| `OTFN1A29AB1_0001` | Manual de Voo | 9 | ✅ |
| `OTFN1A29AB1CL_0001` | Lista Condensada de Verificações | 3 | ✅ |
| `OTFN1A29AB11_0001` | Manual Suplementar do Sistema Aviônico | 11 | ✅ |
| `OTFN1A29AB12_0001` | Manual Suplementar de Dados de Desempenho | 9 | ✅ |
| `OTFN1A29AB34_0001` | Manual de Emprego de Armamento | 8 | ✅ |
| `OTFN1A29AB34B_0001` | Tabelas Balísticas | 103 | ✅ |
| `OTFN1A29AB34CL_0001` | Lista Condensada de Verificações | 3 | ✅ |
| `OTFN1A29AB6CF_0001` | Manual de Procedimento de Voos de Recebimento | 1 | ✅ |
| `OTFN1A29AB6CL_0001` | Lista de Verificação de Voo de Recebimento | 1 | ✅ |
| `OTFN1A29ABEDA1_5148` | Manual de Voo Suplementar | 9 | ✅ |
| `OTFN1A29ABEDA11_5149` | Manual Suplementar do Sistema Aviônico | 11 | ✅ |
| `OTFN1A29ABLMEM_0001` | Lista Mestra de Equipamentos Mínimos | 1 | ✅ |
| `ITEM_1743` | Manual de Equipamentos de Apoio no Solo | 442 | ✅ (dup.) |

Todos os 15 `index_2.0/` têm o **mesmo formato Lucene 2.9/3.x** (10 arquivos: `_0.fdt`, `_0.fdx`,
`_0.fnm`, etc.) — o parser de [`02_formato_indice_lucene.md`](02_formato_indice_lucene.md) funciona
sem alteração.

> [!IMPORTANT]
> Isso sobe o total de `index_2.0/` parseáveis de **34** (Data-ALX) para **49** (34 + 15
> exclusivos da raiz, descontando o `ITEM_1743` duplicado).

---

## 3. Fontes de metadados estruturados

### 3.1 `manual_details.xml` — Nomes canônicos dos manuais ⭐

**Localização:** `Program/Data/manual_details.xml` e `Program/Data/Data-ALX/Data/manual_details.xml`

Mapeia `(type, partnumber)` → `custom-description` em português:

```xml
<manual partnumber="1741" type="FIM">
  <custom-description>Manual de Pesquisa de Panes</custom-description>
</manual>
<manual partnumber="0001" type="OTFN1A29AB39">
  <custom-description>Manual de Reparos de Danos em Combate</custom-description>
</manual>
<manual partnumber="0001" type="OTFN1A29AB1">
  <custom-description>Manual de Voo</custom-description>
</manual>
```

**Conteúdo completo** (49 entradas, cobrindo todos os manuais de ambos os discos):

| type | partnumber | custom-description |
|---|---|---|
| `1BS_ALX` | 0000 | Boletim de Serviço |
| `2BI_ALX` | 0000 | Boletim de Informação |
| `4PIL_ALX` | 0000 | Parts Information Letters |
| `5NPO_ALX` | 0000 | Notícias para Operadores |
| `AIPC` | 1742 | Catálogo Ilustrado de Peças |
| `AMM_PART1` | 1651 | SDS - Manual de Manutenção da Aeronave |
| `AMM_PART2` | 1651 | MPP - Manual de Manutenção da Aeronave |
| `SDS` | 6018 | System Description Section |
| `AMM` | 6018 | Maintenance Practices and Procedures |
| `CMM_EMBRAERALX` | 0000 | Manual de Manutenção de Componentes |
| `CMM_VALX` | 0000 | Manual de Manutenção de Componentes |
| `CPC` | 1739 | Catálogo de Produtos Consumíveis |
| `CPM` | 1740 | Manual de Prevenção de Corrosão |
| `FIM` | 1741 | Manual de Pesquisa de Panes |
| `ITEM` | 1743 | Manual de Equipamentos de Apoio no Solo |
| `LOAP` | 1744 | Lista de Publicações Aplicáveis |
| `MPD` | 1746 | Documento de Plano de Manutenção |
| `NDT` | 1745 | Manual de Inspeções Não Destrutivas |
| `OTFN1A29A21` | 0001 | Guia Mestre Para Registro de Inventário da Aeronave |
| `OTFN1A29AB3311` | 0001 | Munição Não Nuclear Informações Básicas |
| `OTFN1A29AB3312` | 0002 | Munição Não Nuclear Procedimentos de Carregamento |
| `OTFN1A29AB3312CL1` | 0001 | Check List - Metralhadora Interna Browning 0.50in |
| `OTFN1A29AB3312CL2` | 0002 | Check List - Bomba BAFG-120 e BAFG-230 |
| `OTFN1A29AB3312CL3` | 0003 | Check List - Bomba BINC – 300 |
| `OTFN1A29AB3312CL4` | 0004 | Check List - Bomba BLG – 252 |
| `OTFN1A29AB3312CL5` | 0005 | Check List - Lançadores de Foguetes LM 70/7 e LM 70/19 |
| `OTFN1A29AB3312CL6` | 0006 | Check List - Transportador de Bombas de Treinamento – SUU 20 |
| `OTFN1A29AB3312CL7` | 0007 | Check List - Casulo de Alvo Aéreo CAA |
| `OTFN1A29AB3312CL8` | 0008 | Check List - Casulo Logístico |
| `OTFN1A29AB3312CL9` | 0009 | Check List - Tanque de Combustível Subalar |
| `OTFN1A29AB39` | 0001 | Manual de Reparos de Danos em Combate |
| `OTFN1A29AB5` | 0001 | Lista De Verificações de Peso Básico e Dados de Carregamento |
| `OTFN1A29AB6LC` | 0001 | Lista De Verificações do Mecânico |
| `OTFN1A29B21` | 0002 | Guia Mestre Para Registro de Inventário da Aeronave |
| `OTFN3200A29AB4` | 0001 | Catálogo Ilustrado de Peças - AGE Omnibus |
| `SRM_PART1` | 1747 | Manual de Reparos Estruturais |
| `SRM_PART2` | 1747 | Manual de Reparos Estruturais |
| `SRMI` | 1747 | Manual de Reparos Estruturais |
| `SRM` | 1747 | Manual de Reparos Estruturais |
| `SSM` | 1748 | Manual de Diagramas Esquemáticos |
| `SWPM` | 1749 | Manual de Práticas-Padrão de Reparos em Cablagem |
| `WM` | 1647 | Manual de Diagramas de Fiação Elétrica |
| `BO_314PT` | 0000 | Boletins Operacionais |
| `GP` | 5206 | Publicação Geral - Programador de Escrita Aérea |
| `OTFN1A29AB11` | 0001 | Manual Suplementar do Sistema Aviônico |
| `OTFN1A29AB12` | 0001 | Manual Suplementar de Dados de Desempenho |
| `OTFN1A29AB1CL` | 0001 | Lista Condensada de Verificações |
| `OTFN1A29AB1` | 0001 | Manual de Voo |
| `OTFN1A29AB34B` | 0001 | Tabelas Balísticas |
| `OTFN1A29AB34CL` | 0001 | Lista Condensada de Verificações |
| `OTFN1A29AB34` | 0001 | Manual de Emprego de Armamento |
| `OTFN1A29AB6CF` | 0001 | Manual de Procedimento de Voos de Recebimento e Experiência |
| `OTFN1A29AB6CL` | 0001 | Lista de Verificação de Voo de Recebimento e Experiência |
| `OTFN1A29ABEDA11` | 5149 | Manual Suplementar do Sistema Aviônico |
| `OTFN1A29ABEDA1` | 5148 | Manual de Voo Suplementar |
| `OTFN1A29ABLMEM` | 0001 | Lista Mestra de Equipamentos Mínimos |

**Uso no módulo:** fonte canônica para popular `manuais.descricao`. Hoje essa informação
provavelmente é derivada do nome da pasta (ex: `FIM_1741` → manual desconhecido) ou do
`collections.ini` (que só cobre categorias, não manuais individuais). O XML resolve isso
definitivamente.

> [!NOTE]
> 4 entradas são aliases: `SDS`=`AMM_PART1` (partnumber 6018 vs 1651), `AMM`=`AMM_PART2`,
> `SRMI`=`SRM_PART1`, `SRM`=`SRM_PART2`. O `catalog.py` deve tratar como sinônimos.

### 3.2 `manual_type.xml` — Categorização por `catid` ⭐

**Localização:** `Program/Data/manual_type.xml` e `Program/Data/Data-ALX/Data/manual_type.xml`

Mapeia cada `typeid` para um `catid` numérico e metadados adicionais:

```xml
<type typeid="FIM" catid="3" initial_doc="" embManual="yes">
  <language>
    <shortname>FIM</shortname>
    <description></description>
    <content_type>PDF</content_type>
  </language>
</type>
```

**Tabela de categorias extraída** (engenharia reversa — os nomes das categorias vêm do
`collections.ini`):

| catid | Categoria (inferida de `collections.ini` e contexto) | Manuais |
|---:|---|---|
| 1 | Manuais de Manutenção | AMM_PART1, AMM_PART2, SDS, AMM, SWPM, OTFN1A29AB3312*, OTFN1A29AB39, OTFN1A29AB6LC |
| 2 | Diagramas e Esquemáticos | SSM, WM |
| 3 | Catálogos e Reparos | AIPC, 4PIL_ALX, CMM_EMBRAERALX, CMM_VALX, FIM, OTFN3200A29AB4, SRM_PART1, SRM_PART2, SRMI, SRM |
| 4 | Boletins de Serviço | 1BS_ALX, 2BI_ALX |
| 5 | Registros e Inventário | 5NPO_ALX, OTFN1A29AB5, OTFN1A29B21 |
| 7 | Operacional / Voo | BO_314PT, GP, OTFN1A29AB1, OTFN1A29AB1CL, OTFN1A29AB11, OTFN1A29AB12, OTFN1A29AB34, OTFN1A29AB34B, OTFN1A29AB34CL, OTFN1A29AB6CF, OTFN1A29AB6CL, OTFN1A29ABEDA1, OTFN1A29ABEDA11, OTFN1A29ABLMEM |

> [!NOTE]
> Não há `catid` 6 no XML. O `catid` 7 agrupa todos os manuais operacionais e de voo — são
> exatamente os 14 manuais exclusivos da raiz que não existiam em Data-ALX.

**Uso no módulo:** resolve a decisão em aberto **D-01** da `05_rastreabilidade_externa.md` (rótulos
de categoria). O campo `catid` é a fonte para `manuais.categoria_id` ou equivalente. O `collections.ini`
fornece os nomes amigáveis de cada coleção.

### 3.3 `ALXapplicability_control.xml` — Aplicabilidade por aeronave

**Localização:** `Program/Data/ALXapplicability_control.xml`

Define a lista de manuais aplicáveis à aeronave EMB-314 (ALX) SN 00000:

```xml
<family name="EMB-314" codprog="314" model="ALX" label="EMB-314 (ALX)"
        data-folder="" data-maint="maintenance" data-oper="operational">
  <aircraft sn="00000" ...>
    <manuals>
      <manual type="FIM" partnumber="1741"/>
      <manual type="AMM_PART1" partnumber="1651"/>
      <!-- ... 61 entradas no total -->
    </manuals>
  </aircraft>
</family>
```

**Uso no módulo:** fonte para o mapeamento `aeronave → manuais aplicáveis`, se o módulo precisar
filtrar publicações por aeronave. Também confirma `data-maint="maintenance"` e
`data-oper="operational"` como chaves de separação dos dois discos.

### 3.4 `collections.ini` — Nomes das coleções (PT-BR)

**Localização:** `Program/collections.ini` e `Program_Operational/collections.ini` (idênticos)

Formato CSV simples (encoding Latin-1), 17 linhas:

```
AIPC, Catálogo Ilustrado de Peças
AMM(Parte I), Manual de Manutenção de Aeronave - Parte I - SDS
AMM(Parte II), Manual de Manutenção de Aeronave - Parte II - MPP
CMM, Manuais de manutenção de Componentes Embraer
CPC, Catálogo de Produtos Consumíveis
CPM, Manual de Prevenção e Controle de Corrosão
FIM, Manual de Pesquisa de Panes
ITEM, Manual de Equipamento de Apoio ao Solo
LOAP, Lista de Publicações aplicáveis
MPD, Manual de Requisitos de Inspeção
NDT, Manual de Inspeção Não Destrutiva
SRM (Parte I), Manual de Identificação Estrutural
SRM (Parte II), Manual de Reparo Estrutural
SSM, Manual de Diagrama Esquemático
SWPM, Manual de Práticas Padrão de Reparos em Cablagem
WM, Manual de Diagrama de Fiação Elétrica
WUC, Manual de Códigos de Unidade de Trabalho
```

> [!NOTE]
> `WUC` aparece no `collections.ini` mas não existe como pasta no disco — é uma coleção fantasma
> (manual previsto que não foi entregue neste DVD).

### 3.5 `version/*.txt` — Revisão de cada manual

**Localização:** `Program/version/<CODIGO>.txt` e `Program_Operational/version/<CODIGO>.txt`

Formato simples, 3 linhas:

```
Rev. 11
Date: 07/25/2016
TR: 
```

**Comparação de revisões (amostra):**

| Manual | Program (manutenção) | Program_Operational |
|---|---|---|
| AMM_PART1_1651 | Rev. 14, 04/25/2016 | Rev. 08, 10/21/2013 |
| FIM_1741 | Rev. 14, 04/25/2016 | Rev. 07, 08/26/2013 |
| SRM_PART1_1747 | Rev. 11, 07/25/2016 | Rev. 6, 10/21/2013 |
| WM_1647 | Rev. 13, 06/27/2016 | Rev. 7, 08/06/2013 |
| 1BS_ALX_0000 | — (não existe) | Rev. N/A, 03/31/2014 |
| BO_314PT_0000 | — (não existe) | Rev. 00, 03/28/2014 |
| OTFN1A29AB1_0001 | Rev. 4, 05/27/2013 | Rev. 04, 05/27/2013 |

O disco de manutenção é ~3 anos mais recente (2016 vs 2013).

**Uso no módulo:** fonte para `manuais.revisao` e `manuais.data_revisao`. A revisão do Program/
(manutenção) é a vigente.

### 3.6 `tab_manual_aircraft.xml` — Catálogo geral da frota

**Localização:** `Program/tab_manual_aircraft.xml` (666 KB, ~8.143 entradas)

Mapeia cada manual para aeronaves aplicáveis, total de aplicações, se é standard, e título em inglês:

```xml
<manual code="FIM_1741">
  <aircrafts>16</aircrafts>
  <total> 1</total>
  <std> False</std>
  <title> Fault Isolation Manual</title>
</manual>
```

**Uso no módulo:** fonte alternativa de títulos em inglês. Pode complementar o
`manual_details.xml` (PT-BR) com um campo `titulo_en`.

### 3.7 `list.lst` — Catálogo de manuais da frota

**Localização:** `Program/list.lst` (8.143 linhas)

Formato: `CODIGO;Nome legível`

```
FIM_1741;Fim 1741
AMM_PART1_1651;Amm(Part I) 1651
OTFN1A29AB34B_0001;Otfn1A29Ab34B 0001
```

Cobre **todos** os manuais de **todas** as famílias Embraer (não apenas ALX). Útil como referência
cruzada, mas o `manual_details.xml` é mais preciso para o ALX.

### 3.8 `FAMILIES.XML` — Famílias de aeronaves Embraer

**Localização:** `Program/FAMILIES.XML`

46 entradas, de EMB-110 a KC-390, com `datapath` apontando para a pasta de dados de cada família:

```xml
<family description="EMB-314(ALX)" datapath="DATA-ALX" aviation="defense"/>
<family description="KC-390" datapath="Data-390EN" aviation="defense"/>
<family description="Embraer 190E2" datapath="DATA-190E2"/>
```

**Uso no módulo:** confirmação de que o disco é específico da família `DATA-ALX`. Se no futuro
outros DVDs de outras famílias forem incorporados, o `FAMILIES.XML` mapeia qual `datapath` usar.

---

## 4. O `Program/Index/` — Veredicto: sem utilidade

### 4.1 Formato

Cada manual tem:
- Um arquivo `.pdx` (PDF Index, formato Adobe Catalog):
  ```
  %PDX-3.0
  /Title(AMM_PART1_1651)
  /NumDocs 550
  /StemmingLocale(ENU)
  /Include [(../Data/AMM_PART1_1651/)]
  ```
- Uma pasta com `index.idx` (padding de bytes `0x20`) e `index1.idx` (binário proprietário,
  header `*O`, não reconhecido como Lucene, SQLite ou qualquer formato aberto)

### 4.2 Motivo da inutilidade

| Aspecto | Detalhe |
|---|---|
| Formato | Proprietário do TechData/Adobe Catalog, sem parser disponível |
| Redundância | O `index_2.0/` (Lucene) já contém `title`, `revision`, `chapter`, `filename`, `data` — tudo que o módulo precisa |
| Campos | Mesmo que fosse parseável, os `.pdx` indicam apenas titulo, contagem de docs e locale — dados já conhecidos |

**Recomendação:** ignorar completamente. Não incluir no `PUBLICACOES_ACERVO_DIR`.

### 4.3 `Program_Operational/Index/`

Mesmo formato PDX, 51 pares (vs 34 do Program/), cobrindo todos os manuais incluindo os
4 exclusivos do disco operacional. Mesmo veredicto: sem utilidade.

---

## 5. Arquivos sem utilidade para o módulo

Estes arquivos são parte do software TechData e não contêm dados aproveitáveis:

| Arquivo / Pasta | O que é |
|---|---|
| `TechData.exe`, `dtData.exe`, `dopdata.exe` | Executáveis Windows do visualizador |
| `*.dll`, `*.jar`, `java/`, `lib/` | Dependências do TechData |
| `*.swf` | Tutoriais em Flash (Adobe, obsoleto) |
| `Preferences.exe`, `Print.exe`, `About.exe` | Módulos auxiliares do TechData |
| `7z1509.exe` | 7-Zip embutido para instalação |
| `*.pfb`, `xpdfrc` | Fontes e config do visualizador de PDF |
| `TechDataFavoritesTouch/` | Favoritos do modo touch (vazio) |
| `Comments/` | Comentários do usuário no TechData (vazio) |
| `dtdata.ini`, `TechData.ini`, `TechDataWU.ini` | Configs do TechData |
| `*.pdf` (na raiz do Program/) | Manuais de instalação e guia do programa TechData |
| `releasenotes_*.html` | Changelog do eTechPubs |
| `readme.htm` | README do instalador |
| `reportStatus.rav`, `RelStatus.fr3`, `REPREVISIONMANUAL.FR3` | Templates de relatório (FastReport) |
| `MIDAS.DLL`, `JAVAMERGE.EXE`, `MESSAGE.JAR` | Componentes de atualização |
| `embraer.ico`, `logo_embraer.bmp` | Ícones |
| `start.ini`, `unins000.*` | Desinstalador |

---

## 6. Impacto no módulo — Ações para a próxima versão

### 6.1 Ações de alta prioridade

1. **Consumir `manual_details.xml` no `catalog.py`**
   - Popular `manuais.descricao` com o `custom-description` do XML
   - Parser trivial: XML puro, 49 entradas
   - Resolve: nomes hardcoded ou derivados de pasta

2. **Consumir `manual_type.xml` no `catalog.py`**
   - Popular `manuais.categoria` ou `catid` com o valor do XML
   - Fecha a decisão em aberto **D-01** da rastreabilidade

3. **Incorporar os 15 manuais com `index_2.0/` exclusivos da raiz**
   - Sobem de 34 para 49 manuais com metadados Lucene
   - O parser de `02_formato_indice_lucene.md` funciona sem alteração (mesmo formato)
   - Localização: `var/publicacoes/DISCO_COMPLETO/Program/Data/<MANUAL>/index_2.0/`

4. **Incorporar os 4 manuais operacionais exclusivos**
   - `1BS_ALX_0000` (182 PDFs), `2BI_ALX_0000` (2 PDFs), `5NPO_ALX_0000` (44 PDFs), `BO_314PT_0000` (4 PDFs)
   - Estes **não têm** `index_2.0/` — `catalog.py` cai em RN-02 nível 3 (nome do arquivo)

5. **Consumir `version/*.txt` para revisão e data do manual**
   - Parser trivial: 3 linhas por arquivo, regex `^Rev\. (.+)$` e `^Date?: (.+)$`
   - Popular `manuais.revisao` e `manuais.data_revisao`

### 6.2 Ações de média prioridade

6. **Decidir revisão canônica dos PDFs**
   - Program/Data raiz tem revisão mais recente (2016) que Data-ALX (intermediária) e
     Operational (2013)
   - Recomendação: usar Program/Data raiz como fonte de PDFs, Data-ALX só para `index_2.0/`

7. **Consumir `ALXapplicability_control.xml`**
   - Mapeamento aeronave→manuais, se o módulo precisar filtrar por matrícula

### 6.3 Ações de baixa prioridade

8. **Consumir `tab_manual_aircraft.xml` para títulos em inglês**
   - Complementar `manual_details.xml` com campo `titulo_en`

9. **Avaliar `list.lst` como referência cruzada para validação**
   - Confirmar que todos os manuais do disco estão catalogados

---

## 7. Resumo de números atualizados

| Métrica | Antes (01_achados, Data-ALX) | Agora (disco completo) | Fator |
|---|---:|---:|---:|
| PDFs (manutenção) | 5.724 | 12.117 | 2,1× |
| PDFs (operacional) | — | 6.629 | novo |
| **PDFs total** | **5.724** | **18.746** | **3,3×** |
| Tamanho | 1,0 GB | 3,1 GB | 3,1× |
| Manuais com `index_2.0/` | 34 | 49 | 1,4× |
| Manuais total (únicos) | 34 | ~53 | 1,6× |
| Fontes de metadados XML | 0 | 4 | novo |

---

## 8. Localização dos arquivos-fonte

Para referência rápida de quem for implementar:

```
# Metadados XML (parser XML padrão, sem dependências)
var/publicacoes/DISCO_COMPLETO/Program/Data/manual_details.xml
var/publicacoes/DISCO_COMPLETO/Program/Data/manual_type.xml
var/publicacoes/DISCO_COMPLETO/Program/Data/ALXapplicability_control.xml

# Revisões por manual
var/publicacoes/DISCO_COMPLETO/Program/version/*.txt
var/publicacoes/DISCO_COMPLETO/Program_Operational/version/*.txt

# Coleções (nomes PT-BR)
var/publicacoes/DISCO_COMPLETO/Program/collections.ini           # encoding: Latin-1

# Índices Lucene 2.9/3.x (parser existente em 02_formato_indice_lucene.md)
var/publicacoes/DISCO_COMPLETO/Program/Data/Data-ALX/Data/*/index_2.0/    # 34 manuais
var/publicacoes/DISCO_COMPLETO/Program/Data/*/index_2.0/                  # +15 exclusivos

# PDFs - fonte canônica (revisão mais recente)
var/publicacoes/DISCO_COMPLETO/Program/Data/*/                   # manutenção (raiz)
var/publicacoes/DISCO_COMPLETO/Program_Operational/Data/*/       # operacional (4 exclusivos)

# Catálogo geral da frota
var/publicacoes/DISCO_COMPLETO/Program/list.lst
var/publicacoes/DISCO_COMPLETO/Program/tab_manual_aircraft.xml
var/publicacoes/DISCO_COMPLETO/Program/tab_aircraft_manual.xml
var/publicacoes/DISCO_COMPLETO/Program/FAMILIES.XML
```
