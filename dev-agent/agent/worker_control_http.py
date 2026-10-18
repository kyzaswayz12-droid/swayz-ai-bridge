"""Opt-in worker control HTTP application factory.

TLS termination and private binding are deployment responsibilities.
Never deploy this app on a public listener or without verified TLS.
"""
from fastapi import FastAPI, Header, HTTPException, Request
from .worker_control_service import WorkerControlService


def create_control_app(service: WorkerControlService):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/control")
    async def control(request: Request, x_swayz_signature: str = Header(default="")):
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(415, "Unsupported media type")
        if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > 1024:
            raise HTTPException(413, "Request too large")
        raw = await request.body()
        if len(raw) > 1024:
            raise HTTPException(413, "Request too large")
        try:
            return service.handle(raw, x_swayz_signature)
        except (PermissionError, ValueError):
            raise HTTPException(403, "Control request rejected")
        except Exception:
            raise HTTPException(503, "Control service unavailable")

    return app
