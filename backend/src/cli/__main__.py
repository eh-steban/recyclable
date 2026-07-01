"""Entry point for ``python -m src.cli <subcommand>``.

Supported subcommands:

- ``seed``    -- load a YAML seed dataset into Postgres
- ``verify``  -- re-parse fixtures and run acceptance queries (read-only)
- ``ingest``  -- fetch a source URL and extract candidate recycling rules
"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        usage = (
            "Usage: python -m src.cli <subcommand> [options]\n"
            "\n"
            "Subcommands:\n"
            "  seed    -- load a YAML seed dataset into Postgres\n"
            "  verify  -- re-parse fixtures and run acceptance queries\n"
            "  ingest  -- fetch a URL and extract candidate recycling rules\n"
        )
        print(usage, file=sys.stderr)
        sys.exit(1)

    subcommand = sys.argv[1]
    # Shift argv so the subcommand module sees a clean argument list.
    sys.argv = [f"src.cli.{subcommand}", *sys.argv[2:]]

    if subcommand == "seed":
        from src.cli.seed import main as seed_main  # noqa: PLC0415

        seed_main()
    elif subcommand == "verify":
        from src.cli.verify import main as verify_main  # noqa: PLC0415

        verify_main()
    elif subcommand == "ingest":
        from src.cli.ingest import main as ingest_main  # noqa: PLC0415

        ingest_main()
    else:
        print(f"Unknown subcommand: '{subcommand}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
