"""Offline control-service core. No network listener or Docker access.

The API adapter must enforce TLS and call the authenticator before dispatch.
"""
from .control_authentication import ControlAuthenticator
from .emergency_stop import EmergencyStop
from .worker_journal import WorkerJournal


class WorkerControlService:
    def __init__(self, replay_path, stop_path, journal_path, key):
        self.auth = ControlAuthenticator(replay_path, key)
        self.stop = EmergencyStop(stop_path)
        self.journal = WorkerJournal(journal_path)

    def handle(self, raw, signature, *, now=None):
        request = self.auth.verify(raw, signature, now=now)
        action = request["action"]
        if action == "stop":
            self.stop.stop()
            return {"action": "stop", "stopped": True}
        if action == "status":
            return {"action": "status", "stopped": self.stop.is_stopped(),
                    "worker_health": "not_verified"}
        if action == "job_status":
            record = self.journal.status(request["job_id"])
            return {"action": "job_status", "job_id": request["job_id"],
                    "state": record[0] if record else "not_found"}
        raise PermissionError("Unsupported control operation")

    def close(self):
        self.journal.close()
        self.stop.close()
        self.auth.close()
