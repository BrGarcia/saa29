# Addendum — Revisão 5 do Parecer de Incorporação

> Este documento **não substitui** `opus_plano_de_incorporacao.md`. Segue o mesmo padrão das
> Revisões 2–4 (documentadas inline no cabeçalho daquele arquivo): registra o que mudou, seção por
> seção, sem reescrever o corpo de 1.455 linhas. A diferença desta vez é o **motivo** da revisão:
> as Revisões 2–4 corrigiam premissas de infraestrutura (Railway → sem provedor → VPS hipotética);
> a Revisão 5 corrige uma premissa de **conteúdo** — o parecer foi escrito sem examinar o acervo
> real, que já estava no disco.

**Data:** 2026-08-05 · **Motivada por:** investigação de planejamento desta sessão, com medição
direta de `var/Publicações/` (agora `var/publicacoes/acervo/` — D-C). Todos os números citados
abaixo têm a evidência completa em `01_achados_do_acervo.md`.

---

## O que não muda

As três decisões da espinha dorsal (§13 do parecer) **sobrevivem intactas**:

1. Índice FTS5 em arquivo SQLite dedicado, fora do Alembic e fora do backup R2.
2. Indexação offline, nunca dentro do processo web.
3. Acervo fora do repositório e fora de `data/`.

Também sobrevivem sem alteração: o modelo de dados (§6.2), a separação entre acervo descartável e
publicações avulsas preciosas (§9.1), o RBAC (§5.6), a decisão de não usar htmx/Tailwind (§5.7), a
posição sobre Caddy (§5.5), e todo o anti-escopo da §12 — com um item novo (§4 abaixo).

## Seção por seção

### §1 (Veredito executivo) e §2.2 (Verificações executadas)

O quadro de volumetria muda de **3 GB / ~12.100 PDFs (assumido do `Projeto.MD` externo)** para
**1,0 GB / 5.724 PDFs / 34 manuais (medido em disco)**. Ver `01_achados_do_acervo.md` §1. A tese
central da Revisão 4 (infraestrutura de VPS resolve a volumetria) não muda de conclusão — muda de
magnitude, para menos, o que só reforça a viabilidade.

### §5.1 (Volumetria)

Orçamento de disco recalculado: onde a Revisão 4 estimava "≈ 17–23 GB no ano 1" partindo de 3 GB de
acervo, a base real é 1 GB — o orçamento cai proporcionalmente. Não há necessidade de reabrir a
decisão de manter snapshots ZIP fora da VPS (R2) nem a de desduplicar por hash: ambas continuam
corretas, só operam sobre um número menor.

### §5.3 (Índice FTS5 fora do banco principal) e §5.4 (Indexação fora do processo web)

Ambas mantidas **sem alteração de conclusão**, mas o motivo de §5.3 muda: a Revisão 4 citava "a
matriz de CI testa PostgreSQL" como um dos dois motivos independentes. `01_achados_do_acervo.md`
§7.4 mostra que **essa matriz não existe** no CI real (`.github/workflows/ci.yml`, único job,
SQLite in-memory). A decisão continua certa pelo segundo motivo (backup R2 inflado) e por
portabilidade **declarada** em `docs/methodology/NEXT.md`, mas o parecer não pode mais citar
proteção de CI como razão — é uma alegação sem lastro no pipeline real.

### §5.9 (Licenciamento do PyMuPDF) — D-S2

**Resolvida.** O parecer deixava a escolha entre PyMuPDF (AGPL) e alternativas permissivas em
aberto, recomendando avaliar `pypdfium2` no piloto. Esta sessão decidiu por `pypdfium2`
diretamente — a análise qualitativa do texto já extraído pelo Lucene (82,6 MB, UTF-8 válido em
100% dos documentos) reduz o risco de "escolher errado sem dado": o texto do Lucene serve de
gabarito de qualidade contra o qual medir a extração de `pypdfium2`, sem depender só do julgamento
humano sobre uma amostra pequena.

### §6.1 (Estrutura de arquivos) e §6.4 (Configuração `.env.example`)

Sem alteração de estrutura. `catalog.py` ganha uma responsabilidade que o parecer original não
previa: parsear o índice Lucene (`02_formato_indice_lucene.md`), além de `fim.json`. As variáveis
`PUBLICACOES_STORAGE`/`PUBLICACOES_R2_PREFIX` do §6.4 original saem do `.env.example` do M0 — só
voltam a ser declaradas quando o M4 as usar de fato (`03_especificacao_tecnica.md` §6), para não
ter env var morta no arquivo desde o início.

### §5.12(e) e §6.3 (Rotas) — o bug do `API_PREFIXES`

**Correção de um erro do parecer, não de uma premissa.** A recomendação original de registrar
`/publicacoes/` em `API_PREFIXES` reproduziria o bug documentado no próprio código
(`main.py:44-51`, o caso do calendário): rotas HTML sob esse prefixo deixariam de redirecionar
para `/login` em 401/403. Corrigido em `03_especificacao_tecnica.md` §3: todo endpoint JSON vive
sob `/publicacoes/api/...`, e é só esse sub-prefixo que entra em `API_PREFIXES`.

### §7 (Destino de cada regra da especificação externa)

Reescrita inteira em `05_rastreabilidade_externa.md`. Resumo: RN-02, RN-03, RN-04, RN-06 mudam de
fonte (sidecar inexistente → índice Lucene ou `categorias_manuais.toml`); RN-07 deixa de ser
necessária (não há encoding ambíguo para resolver); as demais seis RN, os doze E, os sete CA e as
onze decisões em aberto mantêm destino igual ou são atualizadas por fato consumado (D-S1, D-S4
parcialmente respondidas por o acervo já estar no disco; D-S2 resolvida; D-S6 confirmada).

### §10 (Plano de execução) — M0–M5

Reordenado por decisão desta sessão (avulsas antes da integração com panes/inspeções — ver
`04_plano_de_execucao.md`) e com o escopo do M4 corrigido: deixa de ser "trazer os 3 GB" (já estão
no disco, e são 1 GB) e passa a ser o ciclo de republicação anual. Os gates de saída de cada marco
foram reescritos para citar o CI real (sem matriz Postgres, sem mypy).

### §11 (Riscos)

R1 é reclassificado uma segunda vez (o orçamento de disco cai mais um passo). R3 perde o argumento
de CI mas mantém a conclusão. R5 é encerrado (D-S2 decidida). Três riscos novos, específicos dos
achados operacionais desta sessão (`01_achados_do_acervo.md` §7): registro do prefixo de API
errado, abertura indevida do `catalog.db` via SQLAlchemy, e `var/Publicações/` entrando no git
antes da correção do `.gitignore`. Detalhados em `04_plano_de_execucao.md`, tabela de riscos, como
R20–R22.

### §12 (Anti-escopo) — item novo

Acrescentar: **"Não abrir `catalog.db` com SQLAlchemy/`create_async_engine`"** — o listener global
de backup R2 (`events.py:34-41`) escuta a classe `Session` inteira, não uma engine específica
(`01_achados_do_acervo.md` §7.3). Uso exclusivo de `sqlite3` da biblioteca padrão para esse
arquivo.

### §13 (Conclusão) e §14 (Próxima ação recomendada)

A conclusão central não muda: incorporar é viável e recomendado. O que muda é a confiança com que
se pode dizer isso — a Revisão 4 recomendava "comece pelo piloto FIM" como aposta prudente diante
de incerteza sobre o acervo completo; a Revisão 5 mostra que o acervo completo **já está
acessível e medido**, o que transforma essa recomendação de aposta prudente em decisão informada.
A ordem de "próxima ação" muda apenas na dependência: D-S2 já não bloqueia nada (resolvida), então
a ação imediata é autorizar M0+M1 (ou M0+M2, dado que a ordem entre piloto FIM e avulsas foi
decidida nesta sessão a favor das avulsas primeiro).

---

## Registro para o cabeçalho do parecer

O bloco abaixo deve ser inserido em `opus_plano_de_incorporacao.md`, no mesmo padrão das Revisões
2–4 já presentes no cabeçalho:

> **Revisão 5 — o que mudou:** investigação direta do acervo em `var/Publicações/` (hoje
> `var/publicacoes/acervo/`) mostrou que ele **já está no disco** — 34 manuais, 5.724 PDFs, 1,0 GB
> (não os ~12.100 PDFs / 3 GB assumidos do `Projeto.MD` externo) — e que **não existe nenhum
> sidecar** de metadados (`.title`, `manual_details.xml`, `manual_type.xml`, `version/*.txt`), mas
> cada manual traz um **índice Lucene legado** (`index_2.0/`) que supre título, revisão e capítulo
> para 5.719 dos 5.724 documentos. Consequências: RN-02/03/04/06/07 mudam de fonte ou deixam de
> ser necessárias (§7 reescrita em `05_rastreabilidade_externa.md`); D-S2 foi resolvida
> (`pypdfium2`, Apache-2.0); dois erros do desenho original foram corrigidos antes de virarem bug
> (`API_PREFIXES` e a abertura do `catalog.db`); e o orçamento de disco da §5.1 cai para 1/3 do
> estimado. Nenhuma das três decisões da espinha dorsal (§13) muda. Detalhes completos em
> `docs/backlog/modulo_publicacoes/01_achados_do_acervo.md` a `06_addendum_revisao_5.md`.
