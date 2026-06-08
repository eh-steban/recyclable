"""Tests for the lifespan boot check (_check_boot_config).

Tests call _check_boot_config() directly to exercise the
missing-key error paths without starting a full server.

Boot-check env vars are set/unset at the OS level via
monkeypatch.delenv and monkeypatch.setenv so the function reads
the actual environment, not a mutated settings object.
"""

import pytest

from src.main import _check_boot_config


def test_boot_check_raises_on_missing_anthropic_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boot check raises RuntimeError when ANTHROPIC_API_KEY is absent."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:x@localhost/db")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        _check_boot_config()


def test_boot_check_raises_on_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boot check raises RuntimeError when DATABASE_URL is absent."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _check_boot_config()


def test_boot_check_raises_on_both_keys_absent_names_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both keys are absent the error message names both keys."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        _check_boot_config()

    msg = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "DATABASE_URL" in msg


def test_boot_check_passes_when_both_keys_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boot check does not raise when both keys are non-empty."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:pw@localhost/db",
    )

    # Should not raise.
    _check_boot_config()
