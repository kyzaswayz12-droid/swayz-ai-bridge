"""Independent emergency-stop restoration command for systemd ExecStopPost.

This command only ENGAGES the stop. It cannot release it, execute Docker,
sign jobs, make provider calls or change GitHub. Run as a separate root-owned
systemd process even if the supervised worker crashes.
"""
import os
from .emergency_stop import EmergencyStop

STOP_DB = "/var/lib/swayzcontrol/state/stop.db"

def main():
    if os.geteuid() != 0:
        raise PermissionError("Root stop-restoration authority required")
    stop = EmergencyStop(STOP_DB)
    try:
        stop.stop()
        if not stop.is_stopped():
            raise PermissionError("Stop restoration not confirmed")
    finally:
        stop.close()
    print("SWAYZ_EMERGENCY_STOP_ENGAGED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
