# Achados do Acervo Real — Módulo `publicacoes`

> **Base factual da Revisão 5** do `opus_plano_de_incorporacao.md`. Todo número aqui foi **medido**
> nesta investigação — comando ou script ao lado de cada afirmação. Nenhum número foi herdado da
> `Especificacao.MD`/`Projeto.MD` externas sem reverificação.
>
> **Data da medição:** 2026-08-04/05 · **Ambiente:** `.venv` local, Python 3.13, sem dependências
> além da biblioteca padrão (nenhuma lib de PDF foi necessária para produzir estes números).

---

## 1. O acervo já está no disco

`var/Publicações/Manuais/` (nome original, com acento — ver §7 sobre normalização) contém:

```
find var/Publicações -type f -iname "*.PDF" | wc -l   → 5724
du -sh var/Publicações                                  → 1004M (1,0 GB)
find var/Publicações -type d -mindepth 2 -maxdepth 2 \
  -not -name "index_2.0" | wc -l                        → 34 manuais
```

O parecer original (Revisão 4, §1 e §5.1) trabalha com **3 GB / ~12.100 PDFs**, número herdado do
`Projeto.MD` externo para o acervo **completo da frota**. O que está fisicamente no disco do SAA29
hoje é um recorte real e bem maior que o piloto FIM, mas **1/3 do volume assumido**:

| Item | Parecer Revisão 4 (assumido) | Medido nesta investigação |
|---|---:|---:|
| PDFs | ~12.100 | **5.724** |
| Tamanho | ~3 GB | **1,0 GB** |
| Manuais | não especificado | **34** |
| Páginas (estimado por amostra, §4) | não especificado | **~57.000** |

### 1.1 Censo por manual

`for d in Manuais/*/; do n=$(find "$d" -iname "*.pdf" | wc -l); s=$(du -sm "$d"); done` — ordenado
por contagem de PDFs:

| Manual | PDFs | Tamanho | Manual | PDFs | Tamanho |
|---|---:|---:|---|---:|---:|
| AMM_PART2_1651 | 1.148 | 191 MB | SWPM_1749 | 51 | 8 MB |
| CMM_EMBRAERALX | 1.012 | 90 MB | CPM_1740 | 33 | 2 MB |
| FIM_1741 | 573 | 22 MB | CMM_VALX | 31 | 100 MB |
| AIPC_1742 | 565 | 174 MB | MPD_1746 | 25 | 5 MB |
| WM_1647 | 493 | 154 MB | CPC_1739 | 16 | 2 MB |
| ITEM_1743 | 433 | 23 MB | OTFN1A29AB39_0001 | 12 | 41 MB |
| AMM_PART1_1651 | 422 | 72 MB | OTFN1A29AB6LC_0001 | 9 | 3 MB |
| SSM_1748 | 275 | 29 MB | OTFN1A29B21_0002 | 8 | 2 MB |
| NDT_1745 | 181 | 19 MB | OTFN1A29A21_0001 | 8 | 2 MB |
| SRM_PART2_1747 | 148 | 17 MB | OTFN1A29AB3311_0001 | 7 | 2 MB |
| SRM_PART1_1747 | 129 | 42 MB | LOAP_1744 | 7 | 1 MB |
| OTFN3200A29AB4_0001 | 83 | 9 MB | OTFN1A29AB3312_0002 | 6 | 4 MB |
| | | | 9 variantes `OTFN1A29AB3312CL*` | 5–6 cada | 1 MB cada |
| | | | OTFN1A29AB5_0001 | 2 | 2 MB |

Os 17 `OTFN*` são Ordens Técnicas (boletins de modificação numerados), não manuais no sentido do
`Projeto.MD`. Ficam no mesmo acervo A (§6.2 do parecer) porque compartilham origem (TechPubs
Embraer), estrutura de diretório e ausência de sidecar — mas valem menção separada em
`03_especificacao_tecnica.md` §2 para a categorização (`manual_type`/`catid`, D-01).

### 1.2 Estrutura de diretório

Confirma RN-01 e RN-05 da `Especificacao.MD`: `<MANUAL>/<SEÇÃO_OU_CAPÍTULO>/arquivo.PDF`, com
prefixo numérico de 3 dígitos que dá a ordenação natural (`010_FRONTMATTER` antes de
`CHAPTER_21`/`040_FISEC_CHAPTER_21`). Exemplo (`AMM_PART1_1651`):

```
010_FRONTMATTER, CHAPTER_21 .. CHAPTER_36, CHAPTER_42, CHAPTER_50 .. CHAPTER_57,
CHAPTER_61, CHAPTER_71 .. CHAPTER_80, CHAPTER_85, CHAPTER_92, CHAPTER_93
```

`FIM_1741` usa o prefixo `040_FISEC_CHAPTER_NN` em vez de `CHAPTER_NN` — os dois formatos convivem
no acervo e o indexador (`03_especificacao_tecnica.md` §4) precisa reconhecer ambos, extraindo o
número de capítulo por regex, não por posição fixa na string.

---

## 2. Não existe nenhum sidecar — e isso derruba RN-02/03/04/06/07 como estavam escritas

Censo completo de extensões em toda a árvore:

```
find var/Publicações -type f | sed 's/.*\.//' | tr A-Z a-z | sort | uniq -c
   5724 pdf
     34 tis / tii / prx / nrm / gen / fnm / frq / fdx / fdt / segments_1   (10 × 34 = 340)
```

**Zero** `.title`, **zero** `.xml`, **zero** `.ini`, **zero** `version/*.txt`. O `Projeto.MD` e a
`Especificacao.MD` externos assumem que a Embraer TechPubs entrega, ao lado de cada manual:

| Sidecar assumido | RN que depende dele | Presente no acervo real? |
|---|---|---|
| `NOME.title` (3 linhas: aviso, título, status de revisão) | RN-02 | ❌ Não |
| `manual_details.xml` | RN-03 | ❌ Não |
| `manual_type.xml` (`catid`) | RN-04 | ❌ Não |
| `version/<MANUAL>.txt` | RN-06 | ❌ Não |
| — (encoding declarado nos sidecars) | RN-07 | Sem objeto — não há sidecar para ter encoding |

Isso não é uma lacuna pequena: são **quatro das dez regras de negócio** do documento externo sem
insumo algum no acervo que o SAA29 realmente tem. Os parsers de `catalog.py` previstos no parecer
(§6.1) não teriam o que ler.

## 3. Mas há um índice legado — e ele resolve o problema inteiro

Cada um dos 34 manuais carrega um diretório `index_2.0/` com 10 arquivos: `_0.fdt`, `_0.fdx`,
`_0.fnm`, `_0.frq`, `_0.nrm`, `_0.prx`, `_0.tii`, `_0.tis`, `segments.gen`, `segments_1`. É o
formato de índice do **Apache Lucene 2.9/3.x** (pré-`.cfs`, arquivos separados por tipo) — um
motor de busca full-text que rodava por trás do sistema legado que gerou este acervo (provavelmente
o software de apresentação da própria Embraer TechPubs, dado que o campo `filename` guarda um
caminho absoluto do servidor de origem — ver `02_formato_indice_lucene.md` §3).

**O formato binário completo (VInt, layout de offsets, esquema de campos, parser de referência)
está documentado em `02_formato_indice_lucene.md`.** Aqui ficam só os números.

### 3.1 Cobertura

```python
# parser de referência: ver 02_formato_indice_lucene.md
docs = soma de todos os documentos parseados nos 34 index_2.0/
```

| Métrica | Valor |
|---|---:|
| Índices parseados com sucesso | **34/34** |
| Documentos no índice (soma) | **5.719** |
| PDFs no disco | 5.724 |
| PDFs **sem** entrada no índice | **5** (ver §3.4) |
| Mapeamento `filename`→PDF existente | **5.719/5.719 (100%)** |
| Texto extraído total (campo `data`, soma) | **82,6 MB** |
| Média de texto por documento | 14.443 caracteres |
| Documento com mais texto | 4.578.360 caracteres (um índice/sumário) |
| Decodificação UTF-8 bem-sucedida | **5.719/5.719 (100%)** |

### 3.2 Campos disponíveis (schema único nos 34 índices)

`data, title, revision, tsn, filename, chapter` — os seis campos são **idênticos** em todos os 34
índices (verificado: `len({tuple(names) for names in todos_os_indices}) == 1`). Ou seja, é seguro
escrever **um único parser** para o acervo inteiro, sem tratamento por manual.

| Campo | Papel | Resolve qual RN? |
|---|---|---|
| `title` | Título humano, em português, já com o código do subject/procedimento | RN-02 |
| `revision` | Estado da revisão: `U` (unchanged), `R` (revised), `N` (novo), + 4 valores numéricos residuais | RN-06 (parcial — não dá data, só estado) |
| `chapter` | Caminho do diretório de origem no servidor TechPubs — o último segmento é o nome da pasta de capítulo | RN-05 (confirma agrupamento) |
| `filename` | Caminho absoluto **do servidor de origem** (não do disco local) — usar só o **basename**, trocando `.xml`→`.PDF` | Chave de junção com o PDF físico |
| `data` | Texto completo do documento (não segmentado por página) | Insumo de busca — mas não de número de página (ver §5) |
| `tsn` | Sempre `"20"` na amostra inspecionada — provavelmente um código de template/schema da TechPubs, sem uso aparente para o SAA29 | Nenhum — ignorar |

### 3.3 Distribuição de `revision`

```
{'U': 2256, 'R': 3266, 'N': 181, '0': 8, '1': 2, '2': 6}
```

`U`/`R`/`N` (Unchanged/Revised/New) somam 5.703 dos 5.719 (99,7%) — os seis restantes com valores
numéricos (`'0'`, `'1'`, `'2'`) são resíduo do sistema de origem e devem cair em `revision_status`
como `DESCONHECIDO`/`N/A` em vez de forçar um dos três estados esperados.

### 3.4 Os 5 PDFs sem entrada no índice

```
AIPC1742_24-00-14.PDF
AIPC1742_24-00-25.PDF
FIM1741_95-10-00-810-802-A-.PDF
MPP1651_34-56-01-02-1-B.PDF
MPP1651_34-56-01-02-1_BR.PDF
```

Padrão consistente com **E-03** da `Especificacao.MD` (metadado ausente) — cai no fallback RN-02
nível 3 (nome do arquivo tratado). Nenhum caso de manual inteiro sem índice.

### 3.5 Qualidade dos títulos (amostra qualitativa)

```
'amm part i-1651 - 31-40-00 - sistema gerador de alarmes e indicações'
'aipc-1742 - 32-11-05 - cartucho de mola do trem de pouso principal'
'fim-1741 - 28-26-00-810-802-a - falha do sistema de transferência de combustível'
'ssm-1748 - 28-41-80-101 - sistema elétrico de indicação de quantidade - diagrama'
```

Título já vem em português, minúsculo, com o código do subject/procedimento embutido — melhor
insumo de busca do que o nome de arquivo cru. Contagem de caracteres acentuados nos títulos do
FIM: 690 em 572 documentos — confirma que a extração preserva diacríticos (relevante para CA-04,
§5 abaixo).

---

## 4. Camada de texto e integridade dos PDFs — verificado no acervo completo, não só no FIM

Amostra aleatória de 40 PDFs (`random.seed(29)`) por toda a árvore de 5.724 arquivos:

| Verificação | Resultado |
|---|---|
| Contém `/Font` (born-digital, camada de texto real) | **40/40** |
| Contém `/Encrypt` | **0/40** |
| Contém marcador de imagem (`/Image`/`/DCTDecode`) | 38/40 — diagramas/fotos embutidos, **não** invalida a camada de texto |
| Páginas somadas na amostra | 405 (**10,1 páginas/documento em média**) |

**Consequência:** o achado do parecer original — "PDFs do FIM são born-digital, zero imagens,
camada de texto 100%" (§2.2 da Revisão 4) — **generaliza para o acervo inteiro**, não é peculiaridade
do FIM. **E-01 (`has_text = 0`) é risco baixo em todo o acervo**, não apenas "não-risco no piloto"
como a Revisão 4 registrava com cautela.

Extrapolando a média de 10,1 páginas/documento para os 5.724 PDFs: **≈ 57.800 páginas** no acervo
completo — é a base do "~57.000 páginas" citado na §1.

---

## 5. O que o índice Lucene **não** dá: número de página

O campo `data` é o texto do documento **inteiro em um bloco**, sem marcador de página. Não há
`\x0c` (form feed) nem separador equivalente:

```python
t = maior_documento_do_FIM["data"]  # 110.766 caracteres
t.count("\x0c")            # 0
t.count("\n")               # 0
```

**CA-01** da `Especificacao.MD` ("busca abre o PDF direto na página do trecho") **não pode ser
atendido só com o Lucene**. Isso é a base da decisão D-S2 (§6 abaixo): a extração por página
precisa vir de uma biblioteca de leitura de PDF de verdade, rodando sobre os PDFs físicos — o
Lucene entra como **fonte de metadados** (`title`, `revision`, `chapter`) e como **gabarito de
qualidade** (comparar o texto extraído pela nova biblioteca com o texto já validado do Lucene
detecta falha de extração sem depender de inspeção manual).

---

## 6. `docs/fim/` (o piloto) enriquecido pelo Lucene do `FIM_1741`

```python
lucene = parse(root/"FIM_1741"/"index_2.0")      # 572 docs
fimdir = docs/fim/*.PDF                            # 411 arquivos
hit = [f for f in fimdir if f.name.upper() in {chave_lucene}]
```

| Métrica | Valor |
|---|---:|
| PDFs em `docs/fim/` | 411 |
| ...com metadado do Lucene do `FIM_1741` | **409 (99,5%)** |
| ...sem metadado | 2: `Código de Panes.PDF` (fora do padrão de nome) e `FIM1741_95-10-00-810-802-A-.PDF` (o mesmo arquivo já listado em §3.4 — consistência cruzada confirmada) |

Ou seja: **o piloto FIM ganha título em português, capítulo e estado de revisão de graça**, ainda
que rode isolado sobre `docs/fim/` e nunca toque o acervo completo em `var/publicacoes/`. O
indexador (`indexar.py`) deve tratar o enriquecimento por Lucene como **opcional** — presente
quando o `index_2.0/` do manual correspondente existir ao lado do diretório de PDFs, ausente sem
quebrar nada quando não existir (ex.: se alguém rodar o indexador só sobre `docs/fim/` sem copiar
o `index_2.0` do FIM junto).

### 6.1 Cobertura `fim.json` → PDF, com os dois universos

```
fim.json: 1.377 mensagens de falha → 253 procedimentos únicos
```

| Universo | Procedimentos com PDF | Cobertura |
|---|---:|---:|
| `docs/fim/` (piloto, 411 arquivos) | 249/253 | 98,4% |
| `var/publicacoes/` acervo completo (573 PDFs do `FIM_1741`) | **253/253** | **100%** |

Os 4 procedimentos que faltam no piloto existem no acervo completo — confirma que o recorte de
`docs/fim/` é uma amostra representativa, não um universo com lacuna própria.

Capítulos ATA presentes em `docs/fim/`: `21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
36, 42, 52, 61, 71, 73, 74, 76, 77, 79, 93, 94, 95, 97` — **28 capítulos**, todos os 8 códigos
seedados em `scripts/seed/seed_sistemas_ata.py` (22, 23, 27, 31, 34, 42, 94, 97) estão presentes.

---

## 7. Achados operacionais (não sobre o conteúdo, sobre como manuseá-lo com segurança)

### 7.1 `var/Publicações/` não está protegido pelo `.gitignore`

```
git check-ignore "var/Publicações/Manuais/FIM_1741"   → sai com código 1 (não ignorado)
```

`.gitignore:50-53` cobre `var/logs/`, `var/db`, `var/uploads/`, `var/tmp/` — nenhum padrão bate com
`var/Publicações/`. `git status` já mostra a pasta como `??` (untracked). **1,0 GB está a um `git
add -A` de distância de entrar no histórico do repositório.** Correção obrigatória no M0, antes de
qualquer outro commit tocar a árvore `var/`.

### 7.2 Acentuação e maiúsculas no caminho

`Publicações` (com cedilha e ç) atravessa: Docker (`COPY`/volumes), `.gitignore` (regras com
acento são frágeis em diferentes locales de shell), `rsync` (comportamento de normalização Unicode
difere entre HFS+/APFS do macOS e ext4/NTFS), e o roundtrip Windows↔Linux do WSL/CI. Nenhum desses
é um bloqueador absoluto, mas somados são risco evitável sem custo. Normalização recomendada em
`06_addendum_revisao_5.md` D-C: `var/publicacoes/acervo/`.

### 7.3 O ciclo de backup R2 escuta a classe `Session` inteira, não uma engine específica

```python
# app/bootstrap/events.py:34-41
if current_settings.storage_backend.lower() == "r2" and current_settings.r2_bucket_name:
    sa_event.listen(Session, "after_commit", tasks.mark_db_dirty)
```

O listener é registrado na classe `sqlalchemy.orm.Session`, não em um `sessionmaker` específico.
Qualquer `Session` SQLAlchemy que commitar no processo — inclusive uma aberta contra um segundo
arquivo SQLite — dispara `mark_db_dirty()`, que agenda um backup do arquivo apontado por
`DATABASE_URL` (não do arquivo que de fato mudou). Um `catalog.db` aberto via SQLAlchemy geraria
backups espúrios do banco principal a cada reindexação, sem nunca fazer backup do próprio índice.
**Consequência:** `catalog.db` tem que ser aberto com `sqlite3` da biblioteca padrão (como já faz
`scripts/maintenance/r2_manager.py:122`, inclusive em modo `?mode=ro&uri=true`), nunca com
`create_async_engine`/`Session`.

**No ambiente local, `storage_backend=r2` e `r2_bucket_name` já estão configurados no `.env`** —
o gate não é hipotético, o listener está ativo hoje.

### 7.4 CI real vs. CI assumido pelo parecer

```
.github/workflows/ci.yml (47 linhas): 1 job, ubuntu-latest, Python 3.12
  env: DATABASE_URL=sqlite+aiosqlite:///:memory:  (só isso — sem matriz)
  steps: ruff check .  →  pytest --cov=app --cov-report=term-missing
```

Não há matriz `[sqlite, postgres]` (removida no commit `4b3e619`), não há `mypy` em lugar nenhum
do repositório (nem `mypy.ini`, nem `[tool.mypy]`, nem no `requirements-dev.txt`), e não há
`--cov-fail-under` — cobertura é reportada, não é gate. Os "gates de saída" do M0/M1 do parecer
Revisão 4 (§10) citam "as duas pontas da matriz de CI (SQLite e Postgres)" e "`ruff` + `mypy`" —
ambos precisam ser reescritos em `04_plano_de_execucao.md` para refletir o CI real. A decisão de
manter o FTS5 fora do Alembic **continua certa** — o motivo passa a ser exclusivamente
portabilidade declarada (`docs/methodology/NEXT.md`), não proteção de CI.

### 7.5 Prefixo de API e o bug do calendário, de novo

```python
# app/shared/core/exceptions.py:81
is_api = any(path.startswith(p) for p in api_prefixes)
```

O parecer (§5.12-e) recomenda registrar `/publicacoes/` inteiro em `API_PREFIXES`. Como o teste é
`startswith`, isso captura **todas** as rotas do módulo — inclusive as páginas HTML
(`/publicacoes`, `/publicacoes/manuais/...`, `/publicacoes/viewer/...`). Um 401/403 nessas rotas
devolveria JSON em vez de redirecionar para `/login`, quebrando a navegação normal do módulo. É o
mesmo bug que o comentário em `main.py:44-51` documenta ter acontecido de fato com
`/api/v1/calendario`. **Correção:** registrar só `/publicacoes/api/` em `API_PREFIXES` — ver
`03_especificacao_tecnica.md` §3 para o desenho de rotas que torna isso possível (todo endpoint
JSON sob um único sub-prefixo comum).

---

## 8. Resumo executivo dos achados

| # | Achado | Impacto no parecer |
|---|---|---|
| 1 | Acervo já no disco: 5.724 PDFs / 1,0 GB / 34 manuais | Orçamento de disco (§5.1) recalculado para 1/3 do assumido |
| 2 | Zero sidecars — RN-02/03/04/06/07 sem insumo previsto | `catalog.py` precisa de fonte de dados diferente |
| 3 | Índice Lucene legado presente em todos os 34 manuais, 100% mapeado, 82,6 MB de texto | Substitui os sidecars — RN-02/03/06 resolvidas, RN-04/07 mudam de forma |
| 4 | Texto sem segmentação por página | CA-01 exige extração própria por página (D-S2) |
| 5 | Camada de texto 40/40 na amostra do acervo inteiro | E-01 é risco baixo geral, não só no FIM |
| 6 | `docs/fim/` 99,5% enriquecível pelo Lucene do FIM_1741; cobertura `fim.json` 98,4%→100% conforme o universo | Piloto validado com metadados reais, não fallback pobre |
| 7 | `var/Publicações/` fora do `.gitignore` | Correção obrigatória e urgente no M0 |
| 8 | CI real: sem matriz Postgres, sem mypy | Gates de M0/M1 precisam ser reescritos |
| 9 | `API_PREFIXES` com `startswith` quebra se registrado como `/publicacoes/` | Registrar só `/publicacoes/api/` |
| 10 | Listener de backup R2 na classe `Session` global | `catalog.db` deve usar `sqlite3` puro, nunca SQLAlchemy |
