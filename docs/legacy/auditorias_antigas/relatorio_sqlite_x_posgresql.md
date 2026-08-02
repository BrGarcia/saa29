# Relatório: SQLite x PostgreSQL — Análise para o SAA29

**Data:** 2026-05-01  
**Escopo avaliado:** 20 aeronaves · 8 militares · 5 panes/dia · 3 inspeções/mês · 30 equipamentos · < 30 tarefas únicas

---

## Veredicto

**SQLite é adequado e continuará sendo por muito tempo.**

Dado o escopo operacional do SAA29, o banco de dados atual não apresenta nenhum gargalo técnico presente ou iminente que justifique uma migração.

---

## Volume Real de Dados — Projeção

| Tabela | Registros/ano (estimado) | Após 5 anos |
|--------|--------------------------|-------------|
| `panes` | ~1.825 | ~9.000 |
| `inspecoes` | ~36 | ~180 |
| `inspecao_tarefas` | ~900 (36 × 25 tarefas) | ~4.500 |
| `controle_vencimentos` | ~200 | ~1.000 |
| `token_refresh / blacklist` | ~5.000 | ~25.000 (limpeza automática) |

**Total estimado após 5 anos: < 50.000 registros.**

O SQLite suporta dezenas de milhões de registros com performance adequada. O volume do SAA29 está a anos-luz do limite prático.

---

## Por que o SQLite é adequado para este caso

| Fator | Situação do SAA29 |
|-------|-------------------|
| **Concorrência de escrita** | Baixíssima — 8 usuários, operação serial |
| **Volume de dados** | Irrisório — caberá inteiro em memória com margem |
| **WAL mode ativo** | Leituras concorrentes sem bloqueio (já configurado) |
| **Latência de rede** | Zero — banco reside no mesmo container da aplicação |
| **Backup** | Simples — arquivo único `.db`, integrado ao R2 |

---

## Quando considerar migrar para PostgreSQL

Migre quando **dois ou mais** dos seguintes cenários ocorrerem simultaneamente:

1. **Concorrência real de escrita** — múltiplos usuários enviando dados pesados em paralelo (ex: upload simultâneo de relatórios).
2. **Escalonamento horizontal** — necessidade de mais de uma instância da aplicação. SQLite é arquivo local e não pode ser compartilhado entre instâncias.
3. **Reporting analítico pesado** — queries longas e complexas (window functions, full-text search avançado) que travem a aplicação.
4. **Volume > 5 GB** — o banco começa a exigir tunning específico para manter performance aceitável.
5. **Alta disponibilidade** — necessidade de replicação, failover automático ou backups point-in-time em produção crítica.

> **Para o SAA29, nenhum desses cenários é plausível** dado o escopo atual de 20 aeronaves e 8 militares.

---

## O que já está bem implementado no projeto

O SAA29 já adota práticas que maximizam a longevidade e a performance do SQLite:

- **WAL mode** habilitado → leituras não bloqueiam escritas (verificado nos testes de arquitetura).
- **async / aiosqlite** → I/O não bloqueia o event loop da aplicação.
- **Alembic** para migrações → migrar para PostgreSQL no futuro seria relativamente simples: troca da `DATABASE_URL` e ajuste de tipos específicos do SQLite.
- **Limpeza automática de tokens expirados** → evita crescimento descontrolado das tabelas auxiliares de autenticação.
- **Backup via R2** → proteção do arquivo `.db` sem custo operacional adicional.

---

## Conclusão

O SQLite é **mais que suficiente** para o SAA29 em todo o ciclo de vida esperado do sistema. A arquitetura está preparada para uma eventual migração via Alembic caso o contexto operacional mude (ex: expansão para outra esquadrilha, operação multi-instância).

A única ação prática recomendada no momento é garantir que o backup automático do arquivo `.db` esteja sempre ativo e testado — o que já é suportado pelo projeto via integração com R2.

---

## Apêndice — Concorrência de Escrita e Uploads Simultâneos

### O que acontece quando dois usuários escrevem ao mesmo tempo

O SQLite permite **múltiplas leituras simultâneas** (garantido pelo WAL mode), mas **apenas uma escrita por vez**. Quando dois `INSERT` chegam ao mesmo milissegundo:

```
Usuario A → inicia transação → grava pane → commit (5-20ms)
Usuario B → chega durante esses 5-20ms → SQLITE_BUSY (banco ocupado)
              ↓
         Se busy_timeout > 0: aguarda e retenta automaticamente ✅
         Se busy_timeout = 0: retorna erro imediatamente ❌
```

O risco real não é o volume de dados — é essa janela de **5 a 20ms** onde o banco está bloqueado por outra escrita.

### Por que isso é irrelevante para o SAA29

Com **5 panes por dia** e **8 usuários**, a probabilidade de duas submissões coincidirem na mesma janela de 20ms é praticamente nula:

- 5 panes/dia → média de 1 a cada ~5h em horário de trabalho (8h úteis)
- Janela de colisão: 20ms de 28.800.000ms disponíveis
- **Probabilidade de colisão por dia: < 0,0001%**

Operacionalmente, isso nunca ocorrerá no SAA29.

### Uploads e anexos grandes

Uploads **não passam pelo SQLite**. O fluxo é:

```
Arquivo → FastAPI → Disco local (uploads/) ou R2
                         ↓
              SQLite recebe apenas o path (string curta)
```

Um anexo de 10MB não afeta a escrita no banco. O gargalo de um upload grande é **rede + disco**. O SQLite registra apenas o caminho ao final, de forma independente.

### Resumo de riscos

| Cenário | Risco real |
|---------|-----------|
| 2 panes enviadas simultaneamente | Quase impossível; colisão dura < 20ms |
| Anexo grande | Zero impacto no SQLite (arquivo vai para disco/R2) |
| Volume crescente | Sem problema por anos com o escopo atual |

### Precaução defensiva (sem urgência)

Confirmar se o `busy_timeout` está configurado. Se não estiver, numa colisão improvável o segundo usuário receberia um erro 500 em vez de aguardar automaticamente:

```python
PRAGMA busy_timeout = 5000  # aguarda até 5 segundos antes de falhar
```

Dado o volume do SAA29, mesmo sem `busy_timeout` isso dificilmente ocorrerá em produção — mas é uma boa prática defensiva.
