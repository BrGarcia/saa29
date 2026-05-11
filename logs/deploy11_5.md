WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
[notice] A new release of pip is available: 25.0.1 -> 26.1.1
[notice] To update, run: pip install --upgrade pip
🔄 Restaurando banco de dados do Cloudflare R2...
Tentando baixar banco de dados do R2...
Restore efetuado com sucesso. Banco de dados sincronizado.
🔄 Rodando migrações (Alembic)...
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade c4d5e6f7a8b9 -> d1e2f3a4b5c6, Calendario auditoria 10.2 e 10.5 - private_color e soft-delete
🔧 Inicializando banco de dados (Bootstrap)...
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/app/scripts/db/init_db.py", line 115, in init_db
    await seed_inspecoes.run(session)
Traceback (most recent call last):
🚀 [Aeronaves] Verificando frota de 22 aeronaves...
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
🚀 [Equipamentos] Garantindo catálogo de 33 PNs e Slots...
       ^^
✅ Seed de equipamentos e slots concluído.
  File "/app/scripts/db/init_db.py", line 127, in <module>
NameError: name 'os' is not defined. Did you forget to import 'os'?
🚀 [Sistemas ATA] Garantindo catálogo de Sistemas ATA...
    asyncio.run(init_db())
Garantindo usuários essenciais...
✅ Seed de Sistemas ATA concluído.
           ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/asyncio/runners.py", line 195, in run
🚀 [Inspeções] Configurando Tipos de Inspeção...
    return runner.run(main)
  File "/usr/local/lib/python3.12/asyncio/runners.py", line 118, in run
  File "/app/scripts/seed/seed_inspecoes.py", line 168, in run
   > Simulação: horas_voo=3500.0, início_operação=2020-01-01, referência=2026-05-11
    return self._loop.run_until_complete(task)
    await seed_tarefas.run(session)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/scripts/seed/seed_tarefas.py", line 67, in run
    if os.getenv("APP_ENV", "development").lower() == "production":
  File "/usr/local/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete
AuthService: Senha do admin atualizada para coincidir com as configurações.
⏭️ Criação de usuários de teste desabilitada.