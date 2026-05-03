"""Entry point for ``python -m app.cli <subcommand>``.

Supported subcommands:

- ``seed``   -- load a YAML seed dataset into Postgres
- ``verify`` -- re-parse fixtures and run acceptance queries (read-only)
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        usage = (
            "Usage: python -m app.cli <subcommand> [options]\n"
            "\n"
            "Subcommands:\n"
            "  seed    -- load a YAML seed dataset into Postgres\n"
            "  verify  -- re-parse fixtures and run acceptance queries\n"
        )
        print(usage, file=sys.stderr)
        sys.exit(1)

    subcommand = sys.argv[1]
    # Shift argv so the subcommand module sees a clean argument list.
    sys.argv = [f"app.cli.{subcommand}", *sys.argv[2:]]

    if subcommand == "seed":
        from app.cli.seed import main as seed_main  # noqa: PLC0415

        seed_main()
    elif subcommand == "verify":
        from app.cli.verify import main as verify_main  # noqa: PLC0415

        verify_main()
    else:
        print(f"Unknown subcommand: '{subcommand}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
