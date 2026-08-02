"""
app/bootstrap/tasks.py
Gerenciamento de tarefas em segundo plano e backups (R2).
"""

import os
import sys
import logging
import asyncio
from typing import Optional

from app.bootstrap.config import get_settings

# --- Estado Global para Backups ---
_db_dirty: bool = False          # True quando há escrita não salva no R2
_backup_task: Optional[asyncio.Task] = None  # asyncio.Task do debounce em andamento
_BACKUP_DEBOUNCE_SECONDS = 120   # aguarda 2 min após última escrita antes de enviar
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Define o event loop principal para agendamento de tarefas."""
    global _main_loop
    _main_loop = loop


def mark_db_dirty(*args, **kwargs) -> None:
    """Chamado pelo SQLAlchemy after_commit. Agenda o backup com debounce."""
    global _db_dirty
    _db_dirty = True
    _schedule_debounced_backup()


def _schedule_debounced_backup() -> None:
    """Cancela qualquer backup pendente e agenda um novo após DEBOUNCE segundos (thread-safe)."""
    global _main_loop

    if _main_loop is None or _main_loop.is_closed():
        return

    def _schedule():
        global _backup_task
        if _backup_task and not _backup_task.done():
            _backup_task.cancel()
        _backup_task = _main_loop.create_task(_debounced_backup())

    _main_loop.call_soon_threadsafe(_schedule)


async def _debounced_backup() -> None:
    """Aguarda o debounce e executa o backup se o banco estiver sujo."""
    global _db_dirty

    try:
        await asyncio.sleep(_BACKUP_DEBOUNCE_SECONDS)
        if _db_dirty:
            await run_r2_backup()
            _db_dirty = False
    except asyncio.CancelledError:
        pass  # Nova escrita chegou — será reagendado pelo próximo commit


async def run_r2_backup() -> None:
    """Executa backup assíncrono do banco SQLite para o Cloudflare R2."""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "scripts/maintenance/r2_manager.py", "backup",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Add timeout to avoid hanging indefinitely
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            if process.returncode == 0:
                logging.info("[R2 Backup] %s", stdout.decode().strip())
            else:
                logging.warning("[R2 Backup] Falha: %s", stderr.decode().strip())
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            logging.error("[R2 Backup] Timeout após 60 segundos.")
    except Exception as exc:
        logging.error("[R2 Backup] Erro inesperado: %s", exc)


async def token_cleanup_task() -> None:
    """Executa a limpeza de tokens expirados a cada hora."""
    from app.bootstrap.database import get_session_factory
    from app.modules.auth.service import limpar_tokens_expirados
    
    while True:
        try:
            async with get_session_factory()() as session:
                await limpar_tokens_expirados(session)
                await session.commit()
            logging.info("[Token Cleanup] Limpeza de tokens executada com sucesso.")
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logging.error("[Token Cleanup] Erro na limpeza: %s", exc)
        await asyncio.sleep(3600)  # Roda a cada 1 hora


async def anexos_travados_cleanup_task() -> None:
    """Marca anexos presos em 'processando' há mais de 30min como ERRO.

    Mitigação mínima para a falta de durabilidade do BackgroundTasks do
    FastAPI (relatorio_panes_service.md, item #5): sem isso, um anexo cuja
    task de processamento não rodou (reinício/crash do processo) fica
    eternamente como "processando" e trava a UI.
    """
    from app.bootstrap.database import get_session_factory
    from app.modules.panes.service import limpar_anexos_processando_antigos

    while True:
        try:
            async with get_session_factory()() as session:
                quantidade = await limpar_anexos_processando_antigos(session)
                await session.commit()
            if quantidade:
                logging.warning(
                    "[Anexos Travados] %d anexo(s) preso(s) em 'processando' marcado(s) como ERRO.",
                    quantidade,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logging.error("[Anexos Travados] Erro na limpeza: %s", exc)
        await asyncio.sleep(900)  # Roda a cada 15 minutos


def is_db_dirty() -> bool:
    """Retorna se há alterações pendentes de backup."""
    return _db_dirty

def get_backup_debounce_seconds() -> int:
    """Retorna o tempo de debounce configurado."""
    return _BACKUP_DEBOUNCE_SECONDS
