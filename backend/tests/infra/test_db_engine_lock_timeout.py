"""The shared test Engine enforces a lock_timeout on every connection.

Asserts the server-reported value, not the engine config, so the test
catches a connect-time option that was dropped or silently ignored.
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
