"""Read-only JSON API for the paper-trading subscriber dashboard.

No authentication or privileged endpoints. Serve only behind deliberate routing.
"""
from fastapi import FastAPI
from .dashboard import paper_summary, public_payload
from .journal import PaperJournal

def create_dashboard_app(journal_path: str) -> FastAPI:
    app = FastAPI(title="Swayz Paper Dashboard", docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "paper-dashboard"}

    @app.get("/api/paper-summary")
    def summary():
        journal=PaperJournal(journal_path)
        try:
            return public_payload(paper_summary(journal))
        finally:
            journal.close()
    return app
