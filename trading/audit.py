"""Read-only audit verification for simulated trade journals."""
import hashlib
import json
from .journal import PaperJournal

def journal_fingerprint(journal: PaperJournal) -> dict:
    """Hash canonical journal events for later reconciliation.

    A hash is not a digital signature and does not establish that events are true.
    """
    events=journal.events()
    canonical=json.dumps(events,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return {
        "event_count":len(events),
        "sha256":hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "mode":"PAPER_SIMULATION",
    }
