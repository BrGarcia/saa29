# Divergência de schema em `publicacoes_upload_jobs`

| Campo | Valor |
|---|---|
| **Tipo** | Débito técnico — divergência entre models e banco |
| **Módulo** | `publicacoes` |
| **Descoberto em** | 2026-08-30, durante a implementação do SPEC-CONF-001 (módulo de inventário) |
| **Gravidade** | Baixa — não afeta comportamento; **atrapalha o `--autogenerate`** |
| **Esforço estimado** | Pequeno (uma migration), com uma armadilha (ver §5) |
| **Bloqueia** | Nada. Mas encarece toda migration futura do repositório |

---

## 1. O que é

Duas colunas de `publicacoes_upload_jobs` estão declaradas de um jeito no model e existem de outro no banco. Por causa disso, **todo** `alembic revision --autogenerate` executado neste repositório — de qualquer módulo — sai com estas duas linhas a mais:

```
INFO  [alembic.autogenerate.compare] Detected type change from VARCHAR(length=11) to
      Enum('ENVIANDO','AGUARDANDO_PROCESSAMENTO','PROCESSANDO','CONCLUIDO','FALHOU','CANCELADO',
      name='statusuploadjob') on 'publicacoes_upload_jobs.status'
INFO  [alembic.autogenerate.compare] Detected type change from VARCHAR(length=20) to
      Enum('IMEDIATO','AGENDADO', name='modoprocessamentoupload') on
      'publicacoes_upload_jobs.modo_processamento'
```

| Coluna | No banco | O model produziria |
|---|---|---|
| `status` | `VARCHAR(11)` | `VARCHAR(24)` — **alargamento** |
| `modo_processamento` | `VARCHAR(20)` | `VARCHAR(8)` — **estreitamento** |

---

## 2. Por que existe

### `status` — o enum cresceu, a coluna não

A migration `a16c12991b1b` (2026-08-08) criou a coluna com **cinco** valores:

```python
sa.Column('status', sa.Enum('ENVIANDO', 'PROCESSANDO', 'CONCLUIDO', 'FALHOU', 'CANCELADO',
                            name='statusuploadjob'), nullable=False)
```

O mais longo era `PROCESSANDO`, com 11 caracteres — daí o `VARCHAR(11)`.

Depois, `AGUARDANDO_PROCESSAMENTO` (24 caracteres) foi acrescentado ao enum Python **sem migration**. O banco ficou com a largura antiga.

### `modo_processamento` — nasceu String, virou Enum

A migration `e1a2b3c4d5f6` (2026-08-13) criou a coluna explicitamente como texto:

```python
batch_op.add_column(sa.Column('modo_processamento', sa.String(length=20),
                              nullable=False, server_default='AGENDADO', ...))
```

O model, porém, declara `Enum(ModoProcessamentoUpload)`. Como os dois valores têm 8 caracteres, o model renderiza `VARCHAR(8)` — mais estreito que o `VARCHAR(20)` que existe.

---

## 3. Por que **não** é perigoso

Três fatos verificados, não presumidos:

1. **Nenhuma restrição `CHECK` está em jogo.** No SQLAlchemy 2.0 o padrão de `Enum.create_constraint` é `False`; confirmado nesta base (`sa.Enum(StatusUploadJob).create_constraint` → `False`). O `Enum` vira apenas um `VARCHAR` — não há validação no banco, e aplicar a correção não passaria a rejeitar valor nenhum.

2. **O SQLite ignora o limite de `VARCHAR`.** Testado: uma coluna declarada `VARCHAR(11)` aceita e devolve os 24 caracteres de `AGUARDANDO_PROCESSAMENTO` intactos. Como o projeto é SQLite por regra explícita (`docs/ia/rules.ctx` RN-14), a largura declarada é documental.

3. **A validação real acontece em Python.** O enum é aplicacional; quem grava valor inválido é barrado pelo Pydantic/SQLAlchemy antes de chegar ao banco.

> Em um banco que respeitasse o limite (PostgreSQL, MySQL), o `status` truncaria ou falharia ao gravar `AGUARDANDO_PROCESSAMENTO`. Como a migração para outro SGBD é vedada por RN-14, isso é hipótese, não risco.

---

## 4. Por que importa mesmo assim

O custo não é de runtime — é de **confiança no ferramental**.

Em 2026-08-30, durante a fatia 1 do módulo de inventário, o `--autogenerate` produziu uma lista de **oito** detecções, das quais seis eram falso positivo. No meio delas estava:

```python
op.drop_table('encarregado_ciencias')
```

Um `drop_table` real, causado por outro problema (`migrations/env.py` não importava `app.modules.encarregado.models`). Como o deploy aplica migrations automaticamente — `deploy.yml:44` e `scripts/start.sh:28` rodam `alembic upgrade head` sob `set -e` —, aplicá-lo teria apagado a tabela em produção.

Foi percebido porque a lista estava sendo lida linha a linha. **Ruído em ferramenta de segurança é um problema de segurança**: quando toda execução traz falso positivo, a leitura atenta deixa de acontecer.

Quatro dos seis falsos positivos já foram eliminados (ver §7). Estes dois são os que restam.

---

## 5. A armadilha da correção

`publicacoes_upload_jobs` tem um **índice único parcial**:

```sql
CREATE UNIQUE INDEX uq_publicacoes_upload_jobs_ativo_unico
  ON publicacoes_upload_jobs (1)
  WHERE status IN ('ENVIANDO', 'AGUARDANDO_PROCESSAMENTO', 'PROCESSANDO')
```

É o padrão "singleton": índice único sobre a constante `1` com cláusula `WHERE` garante **no máximo um job ativo por vez**. É uma regra de negócio, não otimização.

Isso importa porque, no SQLite, `op.batch_alter_table` **recria a tabela**: cria uma nova, copia os dados, apaga a antiga e renomeia. Índices precisam ser recriados no processo, e o suporte do Alembic a índices parciais nesse modo é limitado.

**Perder esse índice significaria permitir dois uploads simultâneos** — uma regressão silenciosa, que só apareceria em produção sob concorrência.

Por isso a migration precisa recriar o índice explicitamente, e o teste precisa provar que ele sobreviveu. A declaração está em `app/modules/publicacoes/models.py:576-580`, com `sqlite_where` e `postgresql_where`.

---

## 6. Correção proposta

### 6.1 Migration

```python
def upgrade() -> None:
    with op.batch_alter_table('publicacoes_upload_jobs', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.VARCHAR(length=11),
            type_=sa.Enum(
                'ENVIANDO', 'AGUARDANDO_PROCESSAMENTO', 'PROCESSANDO',
                'CONCLUIDO', 'FALHOU', 'CANCELADO', name='statusuploadjob',
            ),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'modo_processamento',
            existing_type=sa.VARCHAR(length=20),
            type_=sa.Enum('IMEDIATO', 'AGENDADO', name='modoprocessamentoupload'),
            existing_nullable=False,
            existing_server_default='AGENDADO',
        )
```

**Conferir no arquivo gerado, antes de aplicar:**

- o índice `uq_publicacoes_upload_jobs_ativo_unico` continua existindo depois do `batch_alter_table`, com a cláusula `WHERE` completa (três estados);
- o `server_default='AGENDADO'` de `modo_processamento` não foi perdido — `existing_server_default` precisa estar presente;
- nenhuma detecção alheia entrou junto (o `--autogenerate` acusa o repositório inteiro, não só o módulo em foco).

### 6.2 Evitar a reincidência

A causa raiz é que **`Enum(...)` deriva a largura do maior valor no momento em que a migration é gerada**. Acrescentar um valor mais longo depois dessincroniza em silêncio — foi exatamente o que aconteceu com `status`.

A defesa é declarar a largura explicitamente, com folga:

```python
status: Mapped[StatusUploadJob] = mapped_column(
    Enum(StatusUploadJob, length=32),   # folga sobre AGUARDANDO_PROCESSAMENTO (24)
    ...
)
```

Há precedente no próprio módulo: `manuais.origem` já usa `Enum(OrigemManual, native_enum=False, length=20)`. Vale aplicar o mesmo aos dois campos aqui.

Sem isso, o próximo valor longo de enum recria este débito.

---

## 7. Contexto: os outros falsos positivos

Do levantamento de 2026-08-30, quatro já foram resolvidos (PR #3):

| Divergência | Natureza | Resolução |
|---|---|---|
| `pedidos.numero_pedido` | Unicidade declarada por `unique=True` (índice anônimo); o banco tinha também a constraint nomeada `uq_pedidos_numero_pedido` | Constraint declarada no `__table_args__`. **A unicidade nunca esteve em risco** — o índice único já a garantia sozinho |
| `manuais.origem` | `server_default` herdado de backfill, não declarado | Declarado no model |
| `modo_processamento` (server_default) | Idem | Declarado no model |
| `encarregado_ciencias` | `env.py` não importava o módulo → `drop_table` em toda migration | Import acrescentado |

Restam apenas as duas conversões de tipo tratadas neste documento.

---

## 8. Checklist de aceite

- [ ] `alembic revision --autogenerate` em uma árvore limpa não acusa **nenhuma** detecção
- [ ] `uq_publicacoes_upload_jobs_ativo_unico` existe após a migration, com os três estados na cláusula `WHERE`
- [ ] Teste automatizado provando que dois jobs ativos simultâneos são rejeitados (guarda contra a perda silenciosa do índice)
- [ ] `server_default='AGENDADO'` preservado em `modo_processamento`
- [ ] `alembic downgrade -1` **executado**, não apenas lido
- [ ] `length=` explícito nos dois campos `Enum` do model (§6.2)
- [ ] `pytest -q` e `ruff check .` verdes

## 9. O que não fazer

- **Não aplicar a migration gerada sem ler.** É a lição que originou este documento.
- **Não juntar com mudanças de outro módulo.** Foi essa mistura que quase deixou o `drop_table` passar.
- **Não "resolver" ajustando o model para `String`.** O enum no model é o que dá validação em Python; trocá-lo por texto elimina o alarme e a proteção junto.

## 10. Verificação antes de começar

A tabela estava **vazia no banco local** em 2026-08-31. O volume em produção **não foi verificado** — o acesso à VPS depende de senha interativa. Conferir antes de aplicar:

```sql
SELECT COUNT(*) FROM publicacoes_upload_jobs;
SELECT DISTINCT status FROM publicacoes_upload_jobs;
SELECT DISTINCT modo_processamento FROM publicacoes_upload_jobs;
```

Com a tabela vazia, a conversão é trivial. Com dados, confirmar que todo valor presente pertence ao enum atual antes de prosseguir.
