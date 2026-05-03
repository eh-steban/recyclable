"""FastAPI application for operator/admin endpoints."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Recyclable Backend", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
