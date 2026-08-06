# Runbook — Módulo `publicacoes` (acervo de manuais)

> Adaptado de `docs/backlog/manuais/Runbook.MD` (projeto externo que originou a ideia) §2/§3/§4/§6.2/§7,
> para a arquitetura real do SAA29: monolito FastAPI único, sem docker-compose/Caddy separados, acervo
> no mesmo disco da aplicação (`03_especificacao_tecnica.md` §6, D-04).
>
> **Este documento tem lacunas deliberadas, marcadas com 🔒 D-04.** A decisão de qual VPS hospeda o
> SAA29 ainda está aberta (`05_rastreabilidade_externa.md`) — as seções que dependem dela (endereço,
> usuário SSH, caminho exato) usam placeholders. O CICLO em si (publicar → revisar → ativar →
> transferir) não depende de qual VPS for escolhida, e é isso que este runbook fixa agora.

---

## 1. Visão geral do ciclo

```
[Estação de publicação/dev]                         [VPS de produção 🔒 D-04]
        │                                                     │
        │  1. python -m scripts.publicacoes.publicar          │
        │     (indexa, gera relatório de diff, snapshot R2)   │
        │                                                      │
        │  2. Revisão humana do relatório de diff              │
        │     (var/publicacoes/relatorios/relatorio_*.md)      │
        │                                                      │
        │  3. rsync/SSH do acervo — NUNCA HTTP (§5.11 do        │
        │     parecer original; D-D)                    ─────► │
        │                                                      │
        │                                    4. Ativar a edição (card em
        │                                       /configuracoes, M4 tarefa 4)
        │                                                      │
        │                                    5. Conferir /publicacoes/api/status
```

A estação de publicação (onde `publicar.py` roda) e a VPS de produção **não precisam ser a mesma
máquina** — o script só precisa de acesso de leitura ao acervo e de escrita no banco principal (via
`DATABASE_URL`). Rodar localmente contra um banco de homologação, revisar, e só então transferir para
produção é o fluxo recomendado.

---

## 2. Publicar uma edição nova (operação mais frequente)

```bash
# 1. Se houver uma remessa nova (mídia/DVD) para mesclar no acervo existente:
python -m scripts.publicacoes.merge_data \
    --origem var/publicacoes/acervo/Manuais \
    --remessa /caminho/da/midia/nova \
    --executar   # sem esta flag, só relata (padrão seguro)

# Revisar var/publicacoes/acervo/Manuais/merge_report.txt — TODO conflito
# resolvido automaticamente (mtime mais recente vence) fica registrado ali,
# com o lado preterido preservado em _merge_conflicts/ para conferência.

# 2. Publicar (inventário, diff, reindexação, snapshot, upload R2):
python -m scripts.publicacoes.publicar --edicao 2027

# Ou, para só ver o diff sem tocar em nada (seguro para rodar a qualquer
# momento, inclusive contra produção, para saber "o que mudaria"):
python -m scripts.publicacoes.publicar --edicao 2027 --dry-run
```

**O que `publicar.py` faz e não faz:**
- Cria a edição nova no banco como `AGUARDANDO_ATIVACAO` — a edição existe e é consultável por
  quem souber o `document_id`, mas **não aparece como vigente** na busca até ser ativada.
- Reindexa o acervo inteiro (não é literalmente incremental — ver a nota de limitação conhecida
  no topo de `scripts/publicacoes/publicar.py`), o que no acervo medido (34 manuais, 5.724 PDFs)
  levou **~150s** nesta sessão.
- Gera `var/publicacoes/relatorios/relatorio_publicacao_<edicao>.md` e grava o mesmo texto em
  `manuais_edicoes.relatorio_diff` — **é este relatório que alguém lê antes de decidir ativar**.
- Envia um snapshot ZIP do acervo ao R2 (pulável com `--pular-upload`) e poda snapshots além de
  `PUBLICACOES_SNAPSHOTS_RETIDOS` (padrão: 3).
- **Nunca ativa a edição.** Ativar é uma ação humana explícita (tarefa 4, card em
  `/configuracoes` — 🔒 pendente de implementação, ver `08_status_de_implementacao.md`).

### Checklist de validação antes de ativar

1. Ler o relatório de diff — os números de "novos"/"alterados"/"removidos" batem com o que era
   esperado da remessa?
2. `GET /publicacoes/api/status` — `documentos_sem_texto` não deu um salto inesperado (indicaria
   PDFs escaneados sem OCR entrando no acervo).
3. Abrir 2–3 documentos ao acaso da edição nova pelo `document_id` e confirmar que renderizam.

---

## 3. Transferência para a VPS — rsync/SSH, nunca HTTP

Decisão D-D (`01_achados_do_acervo.md` §7, reafirmada no parecer §5.11): o acervo nunca trafega por
HTTP entre a estação de publicação e a VPS — só SSH/rsync, com verificação de hash na chegada.

```bash
# 🔒 D-04: substituir usuário@host e caminho pelos reais, quando definidos.
rsync -avz --checksum \
    var/publicacoes/acervo/ \
    deploy@<host-da-vps>:/srv/saa29/var/publicacoes/acervo/

# Verificação de hash na chegada (--checksum acima já compara conteúdo, não
# só mtime/tamanho — mas para uma confirmação explícita pós-transferência):
ssh deploy@<host-da-vps> 'sha256sum -c' < <(find var/publicacoes/acervo -type f -name "*.PDF" -exec sha256sum {} \;)
```

Depois da transferência, rodar `python -m scripts.publicacoes.publicar --edicao <mesma-edicao> --pular-upload`
**na VPS**, apontando `DATABASE_URL` para o banco de produção — o inventário vai bater 1:1 com o que
já foi indexado na estação de publicação (mesmos hashes), então a reindexação na VPS é rápida e só
confirma consistência, não redescobre nada.

---

## 4. Backup e retenção

| Dado | Perda | Estratégia |
|---|---|---|
| `var/publicacoes/acervo/` (PDFs) | **Grave** — é o acervo | A estação de publicação já é a cópia-mestre; snapshots ZIP no R2 (`publicar.py`) são a segunda cópia |
| `var/publicacoes/catalog.db` | Leve — **reconstruível** por reindexação (~150s no acervo medido) | Não precisa de backup dedicado |
| Banco principal (`manuais`, `manuais_documentos`, …) | Médio — perde o catálogo e a auditoria de acesso, mas o acervo em si sobrevive | Já coberto pelo backup R2 orientado a evento do banco principal (`app/bootstrap/tasks.py`), fora do escopo deste módulo |
| Snapshots R2 | Leve — é a segunda cópia, não a única | Retenção de `PUBLICACOES_SNAPSHOTS_RETIDOS` (padrão 3) já podada automaticamente por `publicar.py` |

**Princípio herdado do runbook externo:** a VPS é descartável. Tudo nela é reconstruível a partir de
repositório git + cópia-mestre do acervo (na estação de publicação, ou no snapshot R2 mais recente)
+ este runbook.

### Restauração completa (VPS nova, do zero) 🔒 D-04

Passos que **não** dependem da VPS escolhida:
1. Deploy da aplicação (fora do escopo deste runbook — ver guia de deploy geral do SAA29, quando
   existir).
2. `rsync` do acervo da estação de publicação (seção 3) — ou baixar o snapshot ZIP mais recente do
   R2 se a estação de publicação não estiver disponível.
3. `python -m scripts.publicacoes.publicar --edicao <rotulo-vigente-conhecido> --pular-upload` para
   reconstruir o catálogo e o `catalog.db`.
4. Ativar a edição restaurada (tarefa 4).

Passos que dependem de D-04 (provisionamento, systemd/docker, proxy reverso, DNS) ficam para o guia
de deploy geral da aplicação — não duplicados aqui.

---

## 5. Monitoramento

`GET /publicacoes/api/status` é o painel de saúde do módulo — sem autenticação especial além da
sessão normal (`CurrentUser`), pensado para ser chamado por humano ou por um script de checagem
simples:

```bash
curl -s -H "Authorization: Bearer $TOKEN" https://<host>/publicacoes/api/status | python3 -m json.tool
```

Campos a observar:
- `indice_disponivel`: `false` é normal só antes da primeira publicação — depois disso, `false`
  indica `catalog.db` ausente ou corrompido, investigar imediatamente.
- `documentos_sem_texto`: crescimento inesperado indica remessa com PDFs escaneados sem OCR
  (M4 tarefa 8) — decidir se vale investir em pipeline de OCR quando esse número for relevante.

---

## 6. Diagnóstico rápido

| Sintoma | Causa provável | Ação |
|---|---|---|
| Busca sempre devolve zero resultados, sem erro | `catalog.db` sem `rebuild` do FTS5 (achado B7) — não deveria acontecer via `publicar.py`/`indexar.py`, que já fazem isso, mas pode acontecer se alguém copiar um `catalog.db` parcial manualmente | Rodar `python -m scripts.publicacoes.indexar` de novo sobre o mesmo diretório — idempotente |
| `GET /publicacoes/api/busca?...&ata=NN` dá 400 "termo inválido" mas a busca sem `ata` funciona | `catalog.db` local antigo, sem a coluna `ata_codigo` (adicionada no M3) | Reindexar — `python -m scripts.publicacoes.indexar` |
| Link de documento de uma pane/inspeção não abre nada | Documento removido do acervo entre edições (RN-09) — o link tinha o `document_id` da edição antiga | Esperado quando a edição mudou; a UI do viewer mostra "REVISÃO ANTERIOR" com link para o equivalente vigente quando existir |
| `publicar.py` falha no upload R2 | Variáveis `R2_*` incompletas ou bucket sem permissão | O script já loga isso como aviso e segue sem abortar o restante (indexação/relatório continuam válidos) |
