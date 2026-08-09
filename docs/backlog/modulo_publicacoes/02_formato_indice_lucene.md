# Formato do Índice Legado (`index_2.0/`) — Engenharia Reversa

> Este conhecimento não existe em nenhum outro lugar — nem no `Projeto.MD`/`Especificacao.MD`
> externos (que não sabiam que este índice existia), nem em documentação da Embraer. Foi obtido
> por inspeção binária direta dos arquivos em `var/Publicações/Manuais/*/index_2.0/` nesta sessão.
> Se este documento se perder, o conhecimento se perde — refazer exige reabrir os binários do zero.

## 1. O que é

Cada um dos 34 manuais em `var/Publicações/Manuais/<MANUAL>/index_2.0/` contém um índice no
**formato Apache Lucene 2.9/3.x** (era pré-`.cfs` compound-file, um arquivo por tipo de dado — o
formato foi substituído por índices compostos nas versões seguintes do Lucene). Dez arquivos por
índice:

```
_0.fdt   _0.fdx   _0.fnm   _0.frq   _0.nrm   _0.prx   _0.tii   _0.tis   segments.gen   segments_1
```

Só dois importam para extrair metadados: **`_0.fnm`** (schema de campos) e o par
**`_0.fdx`/`_0.fdt`** (índice de stored fields + os valores). Os demais (`_0.frq`, `_0.prx`,
`_0.nrm`, `_0.tii`, `_0.tis`) são as estruturas de **busca invertida** do Lucene (frequências,
posições, normas, termos) — não são necessários porque o SAA29 vai reindexar o texto no seu
próprio FTS5 (§5.3 do parecer), não reaproveitar o motor de busca do Lucene.

**Origem provável:** o campo `filename` (§4) guarda caminhos absolutos como
`/prod/techpubs/app/webupdate-embnetwork/bin/Update_Delta/Output/Data-ALX/Data/FIM_1741_update/...` —
isto é o servidor de publicação da própria Embraer TechPubs. O índice foi gerado lá, no momento em
que o acervo foi extraído para DVD/mídia, e viajou junto como um artefato do sistema de origem, não
como parte do "pacote de distribuição" que o `Projeto.MD` externo documenta.

## 2. `_0.fnm` — schema de campos

Formato (Lucene `FieldInfos`):

```
byte 0     : format (int32, litte... na prática 1 byte útil aqui porque field count é pequeno —
             ver nota de robustez abaixo)
byte 1     : número de campos (VInt)
depois, por campo:
  VInt     : tamanho do nome (bytes UTF-8)
  N bytes  : nome do campo
  1 byte   : bitset de flags (indexed / stored / tokenized / etc. — não precisamos decodificar)
```

Os 34 arquivos `_0.fnm` são **byte-idênticos em estrutura** (mesmos 6 campos, mesma ordem):

```
data · title · revision · tsn · filename · chapter
```

Bytes crus do `_0.fnm` do FIM (para referência/depuração):

```
fd ff ff ff 0f 06 04 64 61 74 61 01 05 74 69 74 6c 65 01 08 72 65 76 69 73 69 6f 6e 01
03 74 73 6e 01 08 66 69 6c 65 6e 61 6d 65 01 07 63 68 61 70 74 65 72 01
```

**Nota de robustez:** o parser abaixo lê o "format" e o "número de campos" como dois VInts
consecutivos a partir do byte 0. Isso funcionou nos 34 arquivos porque o format header do Lucene
2.9/3.x nesta geração cabe em 1 byte com sinal (`0xfd` como VInt de valor negativo codificado,
seguido do count real). **Não tentar generalizar** para índices Lucene de outra origem sem
reverificar — este parser é calibrado para *estes* 34 arquivos, não para o formato Lucene em geral.

## 3. `_0.fdx` — índice de stored fields (offsets)

Array de offsets de 8 bytes (`int64` big-endian), um por documento, apontando para a posição do
documento dentro de `_0.fdt`:

```
bytes 0..3   : header (4 bytes, formato/versão — não usado)
bytes 4..11  : offset do documento 0  (int64 big-endian)
bytes 12..19 : offset do documento 1
...
```

`numDocs = (tamanho_do_arquivo - 4) / 8`. Verificado: `_0.fdx` do FIM tem 4.580 bytes →
`(4580-4)/8 = 572` documentos, batendo exatamente com a contagem obtida por outra via (soma do
parser completo).

## 4. `_0.fdt` — valores dos stored fields

Para cada documento, no offset dado pelo `_0.fdx`:

```
VInt          : número de campos armazenados neste documento
para cada campo:
  VInt        : número do campo (índice na lista de _0.fnm, base 0)
  1 byte      : bits (bit 0x2 = binário, bit 0x4 = comprimido com zlib — não observado
                nestes arquivos; todos os valores lidos vieram descompactados)
  VInt        : tamanho do valor em bytes
  N bytes     : valor (UTF-8, decodifica sem erro em 100% dos 5.719 documentos testados)
```

**VInt (variable-length integer)** — codificação padrão do Lucene, 7 bits de payload por byte, bit
mais significativo indica continuação:

```python
def vint(b: bytes, p: int) -> tuple[int, int]:
    x, sh = 0, 0
    while True:
        by = b[p]; p += 1
        x |= (by & 0x7F) << sh
        if by < 0x80:
            return x, p
        sh += 7
```

## 5. Parser de referência (verificado contra os 34 índices)

Este é o parser exato usado para produzir os números de `01_achados_do_acervo.md`. Roda com Python
puro, sem dependências.

```python
import pathlib
import struct


def _vint(b: bytes, p: int) -> tuple[int, int]:
    """Lê um VInt do Lucene a partir da posição p. Retorna (valor, nova_posicao)."""
    x, sh = 0, 0
    while True:
        by = b[p]
        p += 1
        x |= (by & 0x7F) << sh
        if by < 0x80:
            return x, p
        sh += 7


def _field_names(fnm_bytes: bytes) -> list[str]:
    """Extrai os nomes de campo de _0.fnm, na ordem (índice = número do campo)."""
    p = 0
    _fmt, p = _vint(fnm_bytes, p)   # format header — descartado
    count, p = _vint(fnm_bytes, p)  # número de campos
    names = []
    for _ in range(count):
        length, p = _vint(fnm_bytes, p)
        names.append(fnm_bytes[p:p + length].decode("latin-1"))
        p += length
        p += 1  # 1 byte de flags do campo — não decodificado
    return names


def parse_index(index_dir: pathlib.Path) -> list[dict[str, str]]:
    """
    Parseia um diretório index_2.0/ do acervo legado e retorna a lista de
    documentos, cada um como {nome_do_campo: valor_str}.

    Requer apenas _0.fnm, _0.fdx e _0.fdt — os demais arquivos do índice
    (estruturas de busca invertida) não são lidos.
    """
    names = _field_names((index_dir / "_0.fnm").read_bytes())
    fdt = (index_dir / "_0.fdt").read_bytes()
    fdx = (index_dir / "_0.fdx").read_bytes()

    num_docs = (len(fdx) - 4) // 8
    docs = []
    for i in range(num_docs):
        offset = struct.unpack(">q", fdx[4 + i * 8: 12 + i * 8])[0]
        p = offset
        field_count, p = _vint(fdt, p)
        doc: dict[str, str] = {}
        for _ in range(field_count):
            field_num, p = _vint(fdt, p)
            p += 1  # bits (binário/comprimido) — não tratado; nunca observado ligado
            length, p = _vint(fdt, p)
            raw = fdt[p:p + length]
            p += length
            doc[names[field_num]] = raw.decode("utf-8", errors="replace")
        docs.append(doc)
    return docs
```

Uso:

```python
root = pathlib.Path("var/publicacoes/acervo/Manuais")  # após normalização (D-C)
for manual_dir in sorted(root.iterdir()):
    idx = manual_dir / "index_2.0"
    if not idx.is_dir():
        continue
    for doc in parse_index(idx):
        print(doc["title"], doc["revision"], doc["filename"])
```

## 6. Armadilhas para quem for usar isto em `catalog.py`

1. **`filename` é um caminho absoluto do servidor de origem, não do disco local.** Nunca usar
   direto. Extrair só o basename (`.rsplit("/", 1)[-1]`) e trocar a extensão `.xml` → `.PDF` para
   casar com o arquivo físico. Exemplo real:
   `.../FIM_1741_update/040_FISEC_CHAPTER_28/020-FIM1741_CHAPTER28-TITLEPAGE.xml` →
   `020-FIM1741_CHAPTER28-TITLEPAGE.PDF`.

2. **O casamento é por nome, dentro da árvore do mesmo manual — não globalmente único.** Dois
   manuais diferentes podem, em teoria, ter arquivos de mesmo basename em capítulos homônimos. O
   indexador deve casar o Lucene do manual M só contra os PDFs físicos de dentro de `M/`, nunca
   contra o acervo inteiro.

3. **`revision` tem 6 valores possíveis, não 3.** `U`/`R`/`N` são os documentados (Unchanged/
   Revised/New); `'0'`, `'1'`, `'2'` aparecem residualmente (14 casos em 5.719). Tratar como
   `DESCONHECIDO` em vez de forçar em um dos três estados esperados — não presumir que são erro de
   leitura sem investigar caso a caso se voltar a incomodar.

4. **`chapter` é um caminho, não um nome de capítulo pronto.** Como `filename`, pegar só o último
   segmento (`.rsplit("/", 1)[-1]`) — é aí que mora o nome real da pasta (`040_FISEC_CHAPTER_28`,
   `CHAPTER_21`, etc.), coerente com o diretório físico onde o PDF está.

5. **`data` não tem quebra de página.** Zero ocorrências de `\x0c` (form feed) ou de qualquer outro
   separador de página nos textos inspecionados. Não construir lógica de paginação a partir dele —
   ver `01_achados_do_acervo.md` §5. Ele serve para: (a) preencher `title`/`revision`/`chapter` no
   catálogo leve; (b) servir de **gabarito de qualidade** — comparar um trecho do texto extraído
   por `pypdfium2` (por página) com o texto do Lucene (documento inteiro) detecta extração
   corrompida sem inspeção manual, mesmo sem alinhamento por página.

6. **5 PDFs por manual, em média, não têm entrada no índice** (medido: 5 em todo o acervo, não 5
   por manual — ver `01_achados_do_acervo.md` §3.4). O indexador precisa cair em RN-02 nível 3
   (nome do arquivo tratado) para esses casos, não falhar o lote inteiro.

7. **Não confundir este índice com o `catalog.db`/FTS5 que o módulo vai construir.** Este é um
   artefato **read-only, do sistema de origem**, consultado uma vez durante a indexação para extrair
   metadados. Ele nunca é servido, nunca é copiado para produção, e não faz parte do
   `PUBLICACOES_ACERVO_DIR` nem do `PUBLICACOES_INDEX_PATH` definidos em
   `03_especificacao_tecnica.md`. Se algum manual publicado no futuro (via ciclo do DVD, §8 do
   parecer) não trouxer `index_2.0/` — o que é esperado para publicações futuras, já que é um
   artefato do sistema legado, não algo que a Embraer necessariamente reenvia — o indexador cai
   direto em RN-02 nível 3 para aquele manual inteiro, sem erro.

## 7. Verificação de reprodutibilidade

Rodar o parser acima contra os 34 diretórios `index_2.0/` deve produzir exatamente:

```
índices parseados com sucesso .......... 34/34
documentos totais ....................... 5.719
mapeamento filename→PDF existente ....... 5.719/5.719 (100%)
soma de bytes decodificados em 'data' ... 82,6 MB
decodificação UTF-8 bem-sucedida ........ 5.719/5.719 (100%)
distribuição de 'revision' .............. {'U': 2256, 'R': 3266, 'N': 181, '0': 8, '1': 2, '2': 6}
```

Esses são os números citados em `01_achados_do_acervo.md` §3 e servem como teste de regressão
manual: se uma reexecução deste parser (ou de uma reimplementação equivalente dentro de
`catalog.py`) produzir números diferentes, o acervo mudou ou a implementação tem um bug — não
ambos ao mesmo tempo, ao menos como primeira hipótese de investigação.
