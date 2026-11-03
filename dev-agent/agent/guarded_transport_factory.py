"""Bind a fixed transport to a server-selected persistent stop database.

No job payload can supply the control DB path through this factory.
The factory does not run Docker or change any control state.
"""
from .persistent_stop_guard import PersistentStopGuard
from .fixed_docker_transport import FixedDockerTransport
from .worker_lifecycle import WorkerLifecycle


def build_guarded_transport(plan: WorkerLifecycle, *, server_control_db: str):
    guard = PersistentStopGuard(server_control_db)
    # Check now and again immediately before the run command.
    guard.require_running()
    return FixedDockerTransport(plan, require_running=guard.require_running)
