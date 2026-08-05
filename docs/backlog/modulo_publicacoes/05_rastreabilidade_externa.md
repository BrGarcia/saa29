# Rastreabilidade da Especificação Externa — Revisão 5

> Reescreve a §7 do `opus_plano_de_incorporacao.md` à luz de `01_achados_do_acervo.md`. A versão
> original (Revisão 4) dava destino a cada RN/E/CA/D **assumindo que os sidecars existiam**. Como
> `01_achados_do_acervo.md` §2 mostrou que não existem, quatro regras de negócio mudam de fonte —
> e uma (RN-07) muda de necessidade. Nada é removido da rastreabilidade: cada item continua
> presente, com o destino corrigido e o motivo ao lado.

---

## Regras de Negócio (RN)

| RN | Assunto (spec externa) | Destino Revisão 4 | Destino Revisão 5 |
|---|---|---|---|
| RN-01 | Descoberta de documentos: qualquer `*.pdf` sob a raiz, em qualquer profundidade | ✅ Mantida | ✅ **Mantida sem alteração** — confirmado no acervo real: estrutura `<MANUAL>/<CAPÍTULO_ou_SEÇÃO>/arquivo.PDF`, dois formatos de prefixo de capítulo convivendo (`CHAPTER_NN` e `040_FISEC_CHAPTER_NN`) — ver `01_achados_do_acervo.md` §1.2 |
| RN-02 | Título: `.title` → metadado PyMuPDF → nome do arquivo | ✅ Mantida — no piloto FIM não há `.title`, cai no nível 3 + `fim.json` | ♻️ **Fonte trocada.** Nível 1 deixa de ser `.title` (não existe) e passa a ser o campo `title` do **índice Lucene** quando presente (99,5% de cobertura no piloto, `01_achados_do_acervo.md` §6); nível 2 (metadado interno do PDF) fica como estava, mas via `pypdfium2` em vez de PyMuPDF (D-S2); nível 3 (nome do arquivo tratado) inalterado, cobre os 5 documentos sem entrada no Lucene (`01_achados_do_acervo.md` §3.4) |
| RN-03 | Descrição do manual: `manual_details.xml` + `collections.ini` | ✅ Mantida — relevante a partir da fase 3 | ♻️ **Sidecar inexistente.** `manual_details.xml` e `collections.ini` não existem no acervo real (achado #2). Substituída por `config/categorias_manuais.toml` mantido no repositório (`03_especificacao_tecnica.md` §2.3), com fallback para o nome de pasta tratado — mesmo espírito da RN-03 original ("nunca hardcoded no código"), fonte diferente |
| RN-04 | Categoria via `manual_type.xml` (`catid`) | ✅ Mantida, em `categorias_manuais.toml` | ♻️ **Sidecar inexistente**, mesma solução que já estava prevista (`categories.toml`/`categorias_manuais.toml`) — a Revisão 5 só confirma que essa era a saída certa, porque o `manual_type.xml` nunca existiu no acervo real, não é uma perda causada por mudança de escopo. D-01 (rótulos dos `catid`) permanece aberta, sem bloquear |
| RN-05 | Ordenação por prefixo numérico | ✅ Mantida | ✅ **Mantida** — confirmado no acervo real (`01_achados_do_acervo.md` §1.2): `010_FRONTMATTER` antes de `CHAPTER_NN`/`FISEC_CHAPTER_NN` |
| RN-06 | Revisão via `data/version/<MANUAL>.txt` | ✅ Mantida — coluna `revisao`/`revisao_data` | ♻️ **Fonte trocada.** `version/*.txt` não existe. O campo `revision` do Lucene (`U`/`R`/`N` + 3 valores residuais, `01_achados_do_acervo.md` §3.3) dá o **estado** por documento, não a data/número de revisão do manual como um todo. `revisao_data` do manual fica `NULL` até uma fonte melhor aparecer — não é regressão silenciosa, é lacuna documentada |
| RN-07 | Encoding: `.ini`/legados em cp1252, XML em UTF-8, `read_text_legacy()` com fallback | ✅ Mantida e reforçada — teste dedicado | ❌ **Deixa de ser necessária.** Não há `.ini` nem sidecar legado para ter encoding ambíguo. O índice Lucene decodifica em **UTF-8 válido em 100% dos 5.719 documentos testados** (`01_achados_do_acervo.md` §3.1). `read_text_legacy()` não precisa existir — economiza uma função e o teste dedicado que ela exigiria |
| RN-08 | Deduplicação no merge (hash + mtime, `_merge_conflicts/`) | ⏸️ Adiada para a fase do acervo completo | ⏸️ **Mantida adiada** — vira relevante em M4 (`04_plano_de_execucao.md`), quando houver uma segunda remessa para comparar contra a vigente. Não se aplica à carga inicial do acervo (não há duas cópias a mesclar, só uma árvore a indexar) |
| RN-09 | Indexação incremental, não bloqueante | ♻️ Reformulada — offline, "não bloqueia" garantido por construção | ♻️ **Mantida como estava na Revisão 4** — a indexação offline (`scripts/publicacoes/indexar.py`) por construção nunca compete com o processo web pelo único vCPU. Chave `(file_path, mtime, size)` do RN-09 original permanece útil dentro do script, para não reprocessar o que não mudou |
| RN-10 | Sanitização da query FTS | ✅ Mantida e reforçada — teste fuzz obrigatório | ✅ **Mantida sem alteração** — é a única RN que não depende de metadado nenhum, só do texto já extraído. Segurança, não housekeeping de sidecar |

**Saldo:** 4 de 10 RN mudam de fonte (RN-02, RN-03, RN-04, RN-06), 1 deixa de ser necessária
(RN-07), 5 permanecem intactas (RN-01, RN-05, RN-08, RN-09, RN-10). Nenhuma RN foi abandonada sem
substituto.

---

## Casos de Borda (E)

| E | Situação (spec externa) | Destino Revisão 4 | Destino Revisão 5 |
|---|---|---|---|
| E-01 | PDF sem camada de texto (`has_text=0`) | ✅ mantido — "medido como não-risco no piloto" | ✅ **Mantido, com escopo ampliado.** A amostra de 40 PDFs por todo o acervo (não só o FIM) confirmou 40/40 com `/Font` — E-01 é risco baixo **no acervo inteiro**, não peculiaridade do piloto (`01_achados_do_acervo.md` §4) |
| E-02 | PDF corrompido / exceção na extração | ✅ mantido — nunca aborta o lote | ✅ **Mantido sem alteração** — `pypdfium2` no lugar de PyMuPDF não muda a regra, só a biblioteca que pode lançar a exceção |
| E-03 | `.title` ausente ou malformado | ✅ mantido | ♻️ **Generalizado.** Como `.title` nunca existe (não é caso de borda, é a regra — achado #2), E-03 vira "entrada ausente no índice Lucene" — os 5 documentos de `01_achados_do_acervo.md` §3.4 são o caso real. Cai em RN-02 nível 3, como já previsto |
| E-04 | Manual fora dos XMLs → categoria "Outros" | ✅ mantido | ✅ **Mantido, e é o caso comum, não a exceção** — como não há XML nenhum, **todo** manual sem entrada em `categorias_manuais.toml` cai em `[_default]` = "Outros" até ser cadastrado (`03_especificacao_tecnica.md` §2.3) |
| E-05 | PDF solto na raiz | ✅ mantido | ✅ **Mantido sem alteração** — não observado no acervo real (todo PDF está sob um manual), mas a regra continua válida como salvaguarda |
| E-06 | Query FTS inválida → nunca 500 | ✅ mantido | ✅ **Mantido sem alteração** |
| E-07 | Busca sem resultado | ✅ mantido | ✅ **Mantido sem alteração** |
| E-08 | Documento removido → 404 amigável | ✅ mantido | ✅ **Mantido sem alteração** |
| E-09 | Reindexação concorrente → 409 | ❌ eliminado por construção | ❌ **Eliminado, confirmado.** Indexação é offline (`indexar.py` fora do processo web); não existe `POST /reindex` no MVP |
| E-10 | Acentos/espaços no caminho | ✅ mantido — reforçado por `validar_nome_arquivo_seguro` | ✅ **Mantido, e ganha um caso real de teste**: `var/Publicações/` (com cedilha) é exatamente esse cenário, encontrado no próprio processo de normalização do M0 (D-C) |
| E-11 | PDF > 100 MB no mobile | ✅ mantido — Range verificado funcionando | ✅ **Mantido sem alteração** — maior PDF observado no acervo real está bem abaixo de 100 MB (amostra: até ~5 MB por documento típico), mas a regra de Range continua válida como salvaguarda geral |
| E-12 | Acervo vazio no primeiro boot | ♻️ substituído por `PUBLICACOES_ENABLED=false` + estado vazio | ♻️ **Mantido como na Revisão 4** |

---

## Critérios de Aceite (CA)

| CA | Enunciado (resumo) | Destino Revisão 4 | Destino Revisão 5 |
|---|---|---|---|
| CA-01 | Busca abre o PDF na página exata, p95 < 300 ms | ✅ mantido — critério central | ✅ **Mantido, e agora com caminho técnico definido**: exige `pypdfium2` por página (D-S2) porque o índice Lucene **não** segmenta por página (`01_achados_do_acervo.md` §5) — a Revisão 4 não sabia disso porque não sabia que o Lucene existia |
| CA-02 | Publicar sem código | ♻️ adaptado — procedimento §5.8/§8 do parecer | ♻️ **Mantido como estava** — ciclo de publicação via `scripts/publicacoes/publicar.py` + ativação por clique (M4) |
| CA-03 | Navegação mobile, alvos ≥ 44 px | ✅ mantido — alinhado ao `/m/` existente | ✅ **Mantido sem alteração** |
| CA-04 | Diacríticos: `sangria`/`SANGRIA`/`sangría` mesmo resultado | ✅ mantido e já verificado — `remove_diacritics 2` funciona | ✅ **Mantido, com dado extra**: 690 caracteres acentuados nos títulos do FIM extraídos pelo Lucene confirmam que a fonte de metadados também preserva diacríticos, não só o FTS5 do SAA29 (`01_achados_do_acervo.md` §3.5) |
| CA-05 | Resiliência: 1 corrompido entre 100 não aborta o lote | ✅ mantido | ✅ **Mantido sem alteração** |
| CA-06 | RSS < 200 MB, home < 100 ms | ✅ restaurado como alvo literal (4 GB RAM, 2 workers) | ✅ **Mantido como estava na Revisão 4** — segue dependendo de D-04 (VPS) para ser medido de verdade em produção; localmente serve como orçamento de desenvolvimento |
| CA-07 | Estabilidade de links entre reindexações | ✅ mantido — `document_id` determinístico | ✅ **Mantido sem alteração** — `03_especificacao_tecnica.md` §2.2 (UUID v5 do caminho relativo) |

---

## Decisões em Aberto (D)

| D | Assunto | Status Revisão 4 | Status Revisão 5 |
|---|---|---|---|
| D-01 | Rótulos oficiais dos `catid` 1–7 | 🟡 continua aberta — não bloqueia | 🟡 **Continua aberta, e sem urgência nova** — como não há `manual_type.xml`, `catid` nunca vai existir como número a rotular; a decisão real é preencher `categorias_manuais.toml` manual a manual, que pode ser feito incrementalmente |
| D-02 | Acesso restrito? | ✅ RESOLVIDA — JWT + RBAC do SAA29 | ✅ **Continua resolvida**, sem mudança |
| D-03 | Migrar `Comments/` do legado | 🟡 aberta — fase 2 | 🟡 **Aberta, e sem evidência de que `Comments/` exista** — não encontrado no censo de `01_achados_do_acervo.md` §2. Provavelmente não se aplica a este acervo; verificar antes de reservar esforço na fase 2 |
| D-04 | Domínio/provedor de VPS | 🔴 reaberta na Revisão 4 | 🔴 **Continua reaberta, mas não bloqueia mais nada até o M4** — o acervo já está em disco local, `04_plano_de_execucao.md` mostra M0–M3 inteiramente executáveis sem VPS |
| D-05 | Manuais exclusivos de um dos sistemas antigos | 🟡 aberta — só na fase do acervo completo | 🟡 **Mantida aberta** — pergunta sobre o histórico de origem do acervo (dois sistemas legados mesclados), não investigada nesta sessão |
| D-S1 | Onde mora o acervo de 3 GB | reformulada — VPS de ~50 GB, disco + espelho R2 | ♻️ **Respondida por fato consumado.** O acervo (1 GB, não 3) já está em `var/publicacoes/acervo/` desde o M0 — não é mais uma escolha de arquitetura, é onde ele está. A pergunta que sobra é só sobre o **espelho R2**, que continua adiada para M4 |
| D-S2 | PyMuPDF (AGPL) vs. alternativa permissiva | aberta antes da Fase 1 | ✅ **RESOLVIDA nesta sessão** — `pypdfium2` (Apache-2.0/BSD-3), decisão do usuário registrada em `06_addendum_revisao_5.md` |
| D-S3 | Autorização para RAG por API externa | bloqueia a Fase 4 inteira | 🔒 **Mantida bloqueando o M5**, sem mudança |
| D-S4 | Escopo do acervo: só Eletrônica ou frota inteira | aberta | ♻️ **Parcialmente respondida por fato consumado** — o que está no disco é o acervo completo dos 34 manuais medidos (não só os 8 ATAs de Eletrônica que o parecer original cogitava como recorte inicial). Resta confirmar se há mais manuais fora dessa árvore em algum outro lugar (fonte física, DVD físico) |
| D-S5 | Estação de publicação: script vs. instância local | RESOLVIDA — script no `.venv` | ✅ **Continua resolvida**, sem mudança |
| D-S6 | Quem cadastra publicação avulsa | proposto `EncarregadoInspetorOuAdmin` | ✅ **Confirmada nesta sessão** (`03_especificacao_tecnica.md` §7) |
| D-S7 | Backup e recuperação da VPS testados | não bloqueia o M1 | 🟡 **Mantida — não bloqueia nada até o sistema ter dado real de produção**, sem mudança |

---

## Metas Não Funcionais (spec externa §8) — status de cada uma

| Métrica | Alvo | Aplicável antes do M4 (sem VPS)? |
|---|---|---|
| Busca p95 | < 300 ms | sim, medido localmente no M1 sobre o corpus FIM (411 docs) |
| Home/navegação p95 | < 100 ms | medido localmente, mas o alvo real depende da VPS-destino (D-04) |
| RSS do processo | < 200 MB | medido localmente como orçamento de desenvolvimento (CA-06) |
| Boot da app | < 2 s (índice existente) | aplicável desde o M1 — `catalog.db` é lido, nunca reconstruído no boot |
| Indexação completa inicial | < 60 min | **corrigido pela Revisão 5**: acervo real é 1 GB / 5.724 PDFs, não 3 GB / 12.100 — o alvo deve ser recalibrado no M4 quando `pypdfium2` estiver medido em produção (D-S2 §2.2 sugeria benchmark sobre 20 PDFs do FIM antes de comprometer o número) |
| Indexação incremental (1 manual novo) | < 2 min | aplicável a partir do M4 (ciclo de republicação) |
| Lighthouse mobile | ≥ 90/90 | aplicável desde o M1 |

## Fora de Escopo do MVP (spec externa §9) — confirmado, sem mudança

OCR, RAG/LLM, edição/anotação de PDF, impressão controlada/watermarking, sincronização offline
completa — todos permanecem fora do escopo de M0–M4, sem alteração pela Revisão 5. A única
correção é que "favoritos do MVP usam `localStorage`" **não se aplica** ao SAA29: o sistema já tem
conta de usuário real, então `publicacoes_favoritos` no banco principal é estritamente melhor e
não é trabalho extra — é o padrão do resto do sistema.
