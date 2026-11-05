"""Local operator-only supervised stop window.

No network API, daemon, AI calls or job submission. Requires an interactive
root terminal and an independent systemd recovery timer BEFORE stop release.
"""
import os
import subprocess
import sys
from pathlib import Path
from .emergency_stop import EmergencyStop

STOP_DB = "/var/lib/swayzcontrol/state/stop.db"


def restore_stop():
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    stop = EmergencyStop(STOP_DB)
    try:
        stop.stop()
    finally:
        stop.close()


def open_supervised_window(*, job_id, confirmation, watchdog_script,
                           systemd_run=subprocess.run):
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise PermissionError("Interactive root operator required")
    if not isinstance(job_id, str) or not job_id.isascii() or not 1 <= len(job_id) <= 64 or not all(x.isalnum() or x in "-_" for x in job_id):
        raise ValueError("Invalid job ID")
    if confirmation != "AUTHORISE SUPERVISED " + job_id:
        raise PermissionError("Job-specific confirmation required")
    script = Path(watchdog_script)
    if not script.is_absolute() or script.is_symlink() or not script.is_file() or script.stat().st_uid != 0 or script.stat().st_mode & 0o022:
        raise PermissionError("Protected watchdog script required")
    stop = EmergencyStop(STOP_DB)
    try:
        if not stop.is_stopped():
            raise PermissionError("Stop must start engaged")
        # The timer is scheduled before releasing the stop. Any failure
        # aborts without changing state.
        systemd_run([
            "systemd-run", "--unit", "swayz-supervised-recovery-" + job_id,
            "--on-active=120s", sys.executable, str(script), "--recover"
        ], check=True, timeout=15)
        stop.enable(owner_authorised=True)
    finally:
        stop.close()
    return {"job_id": job_id, "state": "supervised_window_open", "seconds": 120}
