"""Explicit worker-control server entrypoint.

No listener starts on import. Deployment requires operator opt-in, private
binding, TLS and a protected service account without Docker group access.
"""
import os
from .worker_control_runtime import load_control_runtime_config
from .worker_control_service import WorkerControlService
from .worker_control_http import create_control_app


def main():
    config = load_control_runtime_config(os.environ)
    import uvicorn
    service = WorkerControlService(
        config.replay_db, config.stop_db, config.journal_db, config.auth_key)
    app = create_control_app(service)
    try:
        uvicorn.run(app, host=config.bind_host, port=config.port,
                    ssl_certfile=config.tls_cert, ssl_keyfile=config.tls_key,
                    proxy_headers=False, access_log=False)
    finally:
        service.close()


if __name__ == "__main__":
    main()
