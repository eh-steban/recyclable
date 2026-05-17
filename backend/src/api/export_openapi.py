"""OpenAPI spec export entry point.

Usage (from backend/):
    uv run python -m src.api.export_openapi > openapi.json

Prints the OpenAPI 3.x specification (as JSON) to stdout.
Consumed by Phase 7 frontend codegen:
    cd frontend && npm run codegen:api

The spec is derived from the FastAPI app's route metadata and Pydantic
models; do not hand-edit the emitted JSON. To change the spec, update
the Pydantic schemas in src/api/schemas/ and re-run this script.
"""

import json
import os
import sys


def main() -> None:
    """Dump the OpenAPI spec to stdout."""
    # Export requires a non-empty ANTHROPIC_API_KEY to pass the boot
    # check lifespan. Provide a dummy if not set so the script can run
    # in CI without real credentials.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "export-placeholder"

    # Import after patching env so the Settings object (already instantiated
    # in config.py at module-load time) isn't the issue -- we patch the
    # settings attribute directly and then import the app.
    from src.config import settings  # noqa: PLC0415, I001 -- must import after env patch

    if not settings.anthropic_api_key:
        settings.anthropic_api_key = "export-placeholder"  # type: ignore[misc]

    from src.main import app  # noqa: PLC0415 -- must import after env patch

    spec = app.openapi()
    json.dump(spec, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
