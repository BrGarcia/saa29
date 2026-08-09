import sys
import os
import subprocess

if __name__ == "__main__":
    print("WARNING: scripts/backup_r2.py is deprecated. Redirecting to scripts/maintenance/r2_manager.py")
    sys.stdout.flush()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    r2_manager_path = os.path.join(current_dir, "maintenance", "r2_manager.py")
    
    cmd = [sys.executable, r2_manager_path]
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        cmd.append("restore")
    else:
        cmd.append("backup")
    # noqa S603: argv totalmente controlado (sys.executable + caminho derivado
    # de __file__ + literal "backup"/"restore"), sem shell e sem entrada externa.
    sys.exit(subprocess.call(cmd))  # noqa: S603
