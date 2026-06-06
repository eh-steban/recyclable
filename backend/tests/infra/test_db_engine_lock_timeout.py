"""The shared test Engine enforces a lock_timeout on every connection.

With ``NullPool`` a contended lock can no longer wait forever on a
lingering pooled connection, but a genuinely blocked statement could still
hang the suite. The ``lock_timeout`` bounds that wait so the statement
fails fast with a clear error. This asserts the timeout is actually in
effect on a live session -- the value the server reports, not the engine
config -- so the test fails if the connect-time option is dropped or
silently ignored.
"""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


@pytest.mark.integration
def test_session_enforces_lock_timeout(db_engine: Engine) -> None:
    """A session from db_engine reports a non-zero, bounded lock_timeout."""
    with Session(db_engine) as session:
        reported = session.execute(
            text("SELECT current_setting('lock_timeout')")
        ).scalar_one()

    assert reported == "5s", (
        f"expected the connection to enforce lock_timeout=5s, but the "
        f"server reports {reported!r}; '0' means the timeout was dropped "
        f"and a contended lock would hang the suite"
    )
