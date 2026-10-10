"""Read-only JSON API for the paper-trading subscriber dashboard.

No authentication or privileged endpoints. Serve only behind deliberate routing.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from .dashboard import paper_summary, public_payload
from .journal import PaperJournal
from fastapi import HTTPException

def create_dashboard_app(journal_path: str) -> FastAPI:
    app = FastAPI(title="Swayz Paper Dashboard", docs_url=None,
                  redoc_url=None, openapi_url=None)

    dashboard_file = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"

    @app.get("/")
    def index():
        return FileResponse(dashboard_file, media_type="text/html")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "paper-dashboard"}

    @app.get("/api/paper-summary")
    def summary():
        try:
            journal=PaperJournal(journal_path)
        except (OSError, RuntimeError, __import__("sqlite3").Error):
            raise HTTPException(status_code=503, detail="Paper data unavailable")
        try:
            return public_payload(paper_summary(journal))
        finally:
            journal.close()
    return app
