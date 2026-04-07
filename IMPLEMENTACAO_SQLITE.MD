## Implementação do SQLite

### 1. Validação do escopo
- **Carga esperada:** 20 aeronaves, 6 mantenedores, e poucas operações simultâneas. O volume de inserts/updates contínuos é baixo; o SQLite aguenta essa carga desde que exista apenas um processo gravando por vez (se precisar de workers extras, coordene-os via fila/lock).
- **Consultas críticas:** o projeto usa joins simples e filtros com `ilike` em painéis, sem analytics intensivo. Como os testes já rodaram com `sqlite+aiosqlite` e passem no modo in-memory (`venv/bin/python -m pytest -q`), a camada de domínio não depende de recursos exclusivos de PostgreSQL.
- **Limitadores do SQLite:** não há suporte a `parallel writes`. Ative `PRAGMA journal_mode=WAL` se quiser reduzir bloqueios de leitura, mas mantenha o padrão single writer. Ferramentas de backup e réplica precisam ser manuais (copiar `.db`, script de dump/restauração ou `VACUUM INTO`).

### 2. Ajustar ambiente e configurações
1. **`.env` e templates:** defina `DATABASE_URL=sqlite+aiosqlite:///./saa29_local.db` para instalações locais/monousuário. Deixe a validação em `app/config.py` como fallback para desenvolvimento (`validate_db_url`).
2. **Fixed paths:** garanta que `uploads`, `logs` e o `.db` estejam dentro de diretórios com permissões do usuário responsável; o SQLite precisa de acesso exclusivo à pasta onde grava o arquivo.
3. **Colation/LIKE:** revise consultas com `.ilike()` e compare strings com acentos. No SQLite padrão, `LIKE` é case-insensitive apenas para ASCII; para manter a sensibilidade completa, você pode estender o PRAGMA `case_sensitive_like=OFF` ou implementar `func.lower` no filtro.
4. **Scripts auxiliares:** atualize `scripts/run_app.py`, `scripts/list_efetivo.py` e qualquer outro script que estabelece `DATABASE_URL` para detectar `sqlite` quando necessário (já há heurística nesse scripts, mantenha e documente).

### 3. Tornar as migrations compatíveis
1. **Defaults de timestamp:** o `server_default=sa.text('now()')` (ex.: `migrations/versions/20260328_1156_d6a790b729ac_initial_schema.py`) falha no SQLite. Substitua por `func.now()` nos modelos ou use `Column(..., default=func.now())` e gere migrações que removam o `server_default` problemático.
2. **Batch mode:** para qualquer `op.alter_column` (ex.: `migrations/versions/20260330_1730_fc37a9cf5271_add_ativo_to_usuarios.py`), utilize:
   ```python
   with op.batch_alter_table("usuarios") as batch:
       batch.alter_column(... )
   ```
   Assim o Alembic recria a tabela temporária e aplica as alterações com compatibilidade SQLite.
3. **SQL cru:** funções como `op.execute("UPDATE usuarios SET ativo = TRUE")` devem ser refatoradas para rodar antes do `batch` (ex.: inserir via `batch.add_column` com `server_default="1"` e remover depois) ou usar `op.get_bind().execute(text(...))` dentro do bloco batch.
4. **`env.py` com render_as_batch:** detecte `sqlite` em `settings.database_url` e configure `context.configure(render_as_batch=True, target_metadata=..., compare_type=True)` antes de `run_migrations_online`. Isso garante que `BatchOperations` sejam geradas automaticamente quando necessário.
5. **Regenerar migrations:** após ajustar os modelos, rode `venv/bin/alembic revision --autogenerate -m "sqlite compatibility"` e revise o script para garantir que ele use `batch` e não reintroduza SQL inválido.

### 4. Ajustes de runtime específicos
1. **Foreign keys:** registre em `app/database.py` um listener sincronizado:
   ```python
   from sqlalchemy import event

   @event.listens_for(create_async_engine(...).sync_engine, "connect")
   def _enable_foreign_keys(dbapi_connection, connection_record):
       cursor = dbapi_connection.cursor()
       cursor.execute("PRAGMA foreign_keys=ON")
       cursor.close()
   ```
   Isso garante integridade referencial no SQLite, que não habilita FKs por padrão.
2. **Frota padrão:** repense `_ensure_default_aeronaves` (parte crucial de `app/main.py`) para rodar mesmo em SQLite, caso a operação de escrita seja necessária; ou documente que a frota deve ser povoada manualmente quando usar o arquivo local.
3. **Seed/local dev:** os scripts de seed (`scripts/seed.py`, `scripts/list_efetivo.py`, etc.) devem detectar o `DATABASE_URL` SQLite (como já fazem) e funcionar com o arquivo local; revise-os para usar `sqlite` em ambientes dev e documente esse comportamento.

### 5. Checklist de verificação
- `venv/bin/python -m pytest -q` continua passando em SQLite após as mudanças.
- `PYTHONPATH=. DATABASE_URL=sqlite+aiosqlite:////tmp/saa29_sqlite_mig.db venv/bin/alembic upgrade head` executa todas as migrations sem erro e cria o arquivo `/tmp/saa29_sqlite_mig.db`.
- Examine o `.db` com `sqlite3` (`sqlite3 ./saa29_local.db ".schema"`) para confirmar índices/FKs esperados.
- Teste o comportamento de busca com `ilike` inclusive com strings acentuadas para validar o collation/`case_sensitive_like`.
- Ao iniciar o app (`venv/bin/python -m uvicorn app.main:app`), confirme que `_ensure_default_aeronaves` não falha no SQLite (caso precise manter a frota automática).

### 6. Operação pós-implantação
1. **Backups:** crie/automatize scripts que copiem o `.db` e guardem versões (ex.: `cp saa29_local.db backups/saa29_$(date +%F_%H-%M).db`); documente como restaurar copiando de volta e rodando `venv/bin/alembic upgrade head`.
2. **Carga real:** com o número de mantenedores reais, faça testes de load leves (20–40 requisições simultâneas) para medir latência de escrita; se perceber bloqueios ou rejects, considere habilitar `journal_mode=WAL` temporariamente.
3. **Critério de rollback:** mantenha um plano para voltar ao PostgreSQL se o volume crescer (ex.: mais de 2 writes/segundo ou múltiplos processos); documente esse gatilho e os passos para migrar o `.db` para um server PostgreSQL (usar `pgloader`, exportar dados via `alembic revision --autogenerate`, etc.).
