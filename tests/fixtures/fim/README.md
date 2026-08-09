# Amostra mínima do FIM para os testes

Quatro PDFs reais do FIM 1741, **copiados do acervo** — 172 KB no total.

## Por que existem

O acervo de manuais (~1 GB, `var/publicacoes/acervo/`) nunca entra no
repositório (ADR-004). Mas o módulo `publicacoes` só é testável de verdade com
PDF de verdade: a extração por página, o FTS5 e o ranqueamento BM25 não têm
como ser exercitados por um arquivo sintético sem virar teste de mentira.

Esta pasta é a exceção deliberada no `.gitignore` (`!tests/fixtures/fim/*.PDF`)
que mantém a busca full-text coberta em pipeline.

## Procedência — importa

Estes arquivos vêm de `var/publicacoes/acervo/Manuais/FIM_1741/`, **não** da
antiga pasta `docs/fim/` que o repositório versionava até
`chore(docs): remove o acervo de PDFs do FIM do versionamento`.

Não é detalhe: as duas cópias **não eram os mesmos arquivos**. As de `docs/fim/`
eram ~15% maiores (revisão diferente) — os testes vinham exercitando bytes que
a produção não indexa. Ao trocar a fonte para o acervo, isso foi corrigido.

| Arquivo | Origem no acervo |
|---|---|
| `FIM1741_21-26-00-810-801-A-.PDF` | `FIM_1741/040_FISEC_CHAPTER_21/` |
| `FIM1741_36-11-00-810-801-A-.PDF` | `FIM_1741/040_FISEC_CHAPTER_36/` |
| `FIM1741_36-21-00-810-801-A-.PDF` | `FIM_1741/040_FISEC_CHAPTER_36/` |
| `FIM1741_36-21-00-810-802-A-.PDF` | `FIM_1741/040_FISEC_CHAPTER_36/` |

## Por que estes quatro

- Os três de ATA 21/36 tratam de **sangria de ar do motor** — o termo do CA-04,
  usado como consulta em quase todo teste de busca.
- `36-21-00-810-802-A` é o único da amostra com mensagem no `fim.json`
  (`EICAS1 055` / `EICAS2 055`), necessário para os testes de FIM por ATA e de
  favoritos.

## Para atualizar

Recopie do acervo e rode a suíte. Se um teste passar a falhar, o motivo
provavelmente é revisão nova do manual com texto diferente — o teste é que
precisa de ajuste, não o PDF.

O mapa completo de mensagens (1.377 pares) segue em `docs/fim.json`, versionado
à parte por ser texto.
