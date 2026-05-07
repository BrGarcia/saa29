"""
app/bootstrap/events.py
Gerenciamento de eventos de ciclo de vida (Lifespan) da aplicação.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from app.bootstrap.config import get_settings
from app.bootstrap import tasks, seed

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerenciador de ciclo de vida da aplicação.
    - startup: inicializar conexões, registrar listener de backup, criar uploads/
    - shutdown: backup final (se houver dados não salvos) + fechar conexões
    """
    # 1. Configurar loop para as tarefas de background
    tasks.set_main_loop(asyncio.get_running_loop())
    
    current_settings = get_settings()

    # 2. Startup: Criar diretórios de infraestrutura
    os.makedirs(current_settings.upload_dir, exist_ok=True)
    
    # 3. Seed: Garantir dados básicos (Frota Padrão)
    await seed.ensure_default_aeronaves()

    # 4. Configurar Event-Driven Backup (R2)
    if current_settings.storage_backend.lower() == "r2" and current_settings.r2_bucket_name:
        from sqlalchemy import event as sa_event
        from sqlalchemy.orm import Session
        sa_event.listen(Session, "after_commit", tasks.mark_db_dirty)
        logging.info(
            "[R2 Backup] Backup orientado a eventos ativo (debounce: %ds).", 
            tasks.get_backup_debounce_seconds()
        )

    # 5. Iniciar Tarefas em Segundo Plano
    cleanup_task = asyncio.create_task(tasks.token_cleanup_task())

    yield

    # 6. Shutdown: Cancelar tasks de background
    cleanup_task.cancel()

    # 7. Shutdown: Backup final se houver dados não persistidos no R2
    if tasks.is_db_dirty() and current_settings.storage_backend.lower() == "r2" and current_settings.r2_bucket_name:
        logging.info("[R2 Backup] Shutdown com dados não salvos — executando backup final...")
        await tasks.run_r2_backup()

    # 8. Shutdown: Fechar engine de banco de dados
    from app.bootstrap.database import dispose_engine
    await dispose_engine()
