"""
app/shared/core/processo.py
Checagem de liveness de processos do SO, multiplataforma.
"""

import sys


def processo_esta_ativo(pid: int) -> bool:
    """
    Verifica se um PID ainda está vivo, sem depender de sinais POSIX.

    No Windows, `os.kill(pid, 0)` não é uma checagem inócua: sinais fora do
    conjunto especial (CTRL_C_EVENT/CTRL_BREAK_EVENT/SIGTERM) são repassados
    a `TerminateProcess(handle, sig)` — ou seja, um "probe" de liveness feito
    assim mata de fato o processo saudável com exit code 0. Por isso o
    Windows usa `OpenProcess` via ctypes só para checar existência.
    """
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True

    import os

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        # Ex.: PermissionError (EPERM) — processo existe mas pertence a outro
        # usuário/uid; ainda está vivo, não é o caso de "processo morto".
        return True
