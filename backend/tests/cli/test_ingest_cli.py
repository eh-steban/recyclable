"""CLI tests for the ingest command (src.cli.ingest).

Argument validation, jurisdiction resolution, and error-path exit codes
without a real DB or network: resolution runs against an in-memory repo
and run_ingestion is patched.
"""

import uuid
from unittest.mock import patch

import pytest

from src.cli.ingest import _select_jurisdiction, main
from src.domain.ingestion.ingestion_report import IngestionReportId
from src.domain.knowledge_base.jurisdiction import Jurisdiction
from tests.utils.builders.knowledge_base import make_jurisdiction
from tests.utils.fakes.jurisdiction_repo import MemJurisdictionRepo

_DENVER = make_jurisdiction(
    name="City and County of Denver", slug="denver-co-us"
)
_BASE_ARGV = [
    "--source",
    "https://denvergov.org/recycling",
    "--jurisdiction",
    "denver",
]


def _repo_with(*jurisdictions: Jurisdiction) -> MemJurisdictionRepo:
    repo = MemJurisdictionRepo()
    for jurisdiction in jurisdictions:
        repo.save(jurisdiction)
    return repo


class TestSelectJurisdiction:
    def test_unique_substring_match_returns_jurisdiction(self) -> None:
        result = _select_jurisdiction(_repo_with(_DENVER), "denver")
        assert result.slug == "denver-co-us"

    def test_match_is_case_insensitive(self) -> None:
        result = _select_jurisdiction(_repo_with(_DENVER), "DENVER")
        assert result.slug == "denver-co-us"

    def test_no_match_lists_available_and_exits(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _select_jurisdiction(_repo_with(_DENVER), "portland")
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "no jurisdiction matches" in err
        assert "City and County of Denver" in err

    def test_ambiguous_match_lists_candidates_and_exits(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo_with(
            make_jurisdiction(name="Denver City", slug="denver-city"),
            make_jurisdiction(name="Denver County", slug="denver-county"),
        )
        with pytest.raises(SystemExit) as exc_info:
            _select_jurisdiction(repo, "denver")
        assert exc_info.value.code != 0
        assert "matches 2 jurisdictions" in capsys.readouterr().err

    def test_empty_db_hints_to_seed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _select_jurisdiction(MemJurisdictionRepo(), "denver")
        assert exc_info.value.code != 0
        assert "seed" in capsys.readouterr().err.lower()


class TestIngestCLIArgValidation:
    def test_missing_source_arg_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--jurisdiction", "denver"])
        assert exc_info.value.code != 0

    def test_missing_jurisdiction_arg_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--source", "https://denvergov.org/recycling"])
        assert exc_info.value.code != 0


class TestIngestCLIRunIngestion:
    def test_run_ingestion_raising_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch("src.cli.ingest._resolve_jurisdiction", return_value=_DENVER),
            patch(
                "src.cli.ingest.run_ingestion",
                side_effect=RuntimeError("DB connection failed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(_BASE_ARGV)
        assert exc_info.value.code != 0
        assert "ingestion failed" in capsys.readouterr().err

    def test_happy_path_prints_report_id_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report_id = IngestionReportId(uuid.uuid4())
        with (
            patch("src.cli.ingest._resolve_jurisdiction", return_value=_DENVER),
            patch("src.cli.ingest.run_ingestion", return_value=report_id),
        ):
            main(_BASE_ARGV)
        assert str(report_id) in capsys.readouterr().out
