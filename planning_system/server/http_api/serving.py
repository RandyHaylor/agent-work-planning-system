"""serving: uvicorn on the section's host (default 127.0.0.1) and port, TLS from tls."""
from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI

from planning_system.configuration import ConfigSection

from .tls import ensure_self_signed_cert

DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 8788


def serve(app: FastAPI, section: ConfigSection) -> None:
    cert, key = ensure_self_signed_cert(Path(section.get("cert_dir", "certs")))
    uvicorn.run(app, host=section.get("host", DEFAULT_HOST), port=int(section.get("port", DEFAULT_PORT)),
                ssl_certfile=str(cert), ssl_keyfile=str(key))
