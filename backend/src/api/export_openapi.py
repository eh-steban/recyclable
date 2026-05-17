"""OpenAPI spec export entry point.

Usage (from backend/):
    ANTHROPIC_API_KEY=x DATABASE_URL=postgresql+psycopg://x \\
        uv run python -m src.api.export_openapi > openapi.json

Prints the OpenAPI 3.x specification (as JSON) to stdout.
Consumed by Phase 7 frontend codegen:
    cd frontend && npm run codegen:api

The spec is derived from the FastAPI app's route metadata and Pydantic
models; do not hand-edit the emitted JSON. To change the spec, update
the Pydantic schemas in src/api/schemas/ and re-run this script.

Both ANTHROPIC_API_KEY and DATABASE_URL must be set in the environment
(or provided as placeholders) before running this script, because the
boot check in src/main.py reads os.environ directly.
"""

import json
import os
import sys


def main() -> None:
    """Dump the OpenAPI spec to stdout.

    Sets placeholder env vars if either boot-check var is missing so
    the script can run in CI without real credentials or a DB.
    Env vars are set before importing src.main to satisfy the lifespan
    boot check (which reads os.environ directly).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "export-placeholder"
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = (
            "postgresql+psycopg://export:placeholder@localhost/export"
        )

    from src.main import app  # noqa: PLC0415 -- must import after env patch

    spec = app.openapi()
    json.dump(spec, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
