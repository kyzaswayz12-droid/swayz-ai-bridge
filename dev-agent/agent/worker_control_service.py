"""Offline control-service core. No network listener or Docker access.

The API adapter must enforce TLS and call the authenticator before dispatch.
"""
from .control_authentication import ControlAuthenticator
from .emergency_stop import EmergencyStop
from .worker_journal import WorkerJournal


class WorkerControlService:
    def __init__(self, replay_path, stop_path, journal_path, key, *, task_db=None, job_db=None):
        self.auth = ControlAuthenticator(replay_path, key)
        self.stop = EmergencyStop(stop_path)
        self.journal = WorkerJournal(journal_path)
        self.task_db = task_db
        self.job_db = job_db
        self.stop_path = stop_path

    def handle(self, raw, signature, *, now=None):
        request = self.auth.verify(raw, signature, now=now)
        action = request["action"]
        if action == "stop":
            self.stop.stop()
            return {"action": "stop", "stopped": True}
        if action == "status":
            return {"action": "status", "stopped": self.stop.is_stopped(),
                    "worker_health": "not_verified"}
        if action == "develop":
            if not self.task_db or not self.job_db:
                raise PermissionError("Development intake not configured")
            from datetime import datetime, timezone
            from .development_task_intake import submit_verified_task
            job_id = submit_verified_task(
                db_path=self.task_db, job_db=self.job_db,
                control_db=self.stop_path, job_id=request["job_id"],
                task=request["task"], now=datetime.now(timezone.utc))
            return {"action": "develop", "job_id": job_id, "state": "queued"}
        if action == "job_status":
            record = self.journal.status(request["job_id"])
            return {"action": "job_status", "job_id": request["job_id"],
                    "state": record[0] if record else "not_found"}
        raise PermissionError("Unsupported control operation")

    def close(self):
        self.journal.close()
        self.stop.close()
        self.auth.close()
