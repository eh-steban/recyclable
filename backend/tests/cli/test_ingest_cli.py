"""CLI tests for the ingest command (src.cli.ingest).

Verifies argument validation and error-path exit codes without a real DB
or network: run_ingestion is monkeypatched in all tests.

Covers:
- Invalid --jurisdiction-id exits nonzero
- Missing required args exits nonzero (argparse handles this)
- run_ingestion raising exits nonzero and prints error to stderr
- Happy path: run_ingestion called, report ID printed, exit 0
"""

import uuid
from unittest.mock import patch

import pytest

from src.cli.ingest import main
from src.domain.ingestion.ingestion_report import IngestionReportId

_VALID_UUID = str(uuid.uuid4())
_BASE_ARGV = [
    "--source",
    "https://denvergov.org/recycling",
    "--jurisdiction-id",
    _VALID_UUID,
    "--jurisdiction-name",
    "Denver, CO",
]


class TestIngestCLIArgValidation:
    def test_invalid_jurisdiction_id_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-UUID --jurisdiction-id prints an error and exits 1."""
        argv = [
            "--source",
            "https://denvergov.org/recycling",
            "--jurisdiction-id",
            "not-a-uuid",
            "--jurisdiction-name",
            "Denver, CO",
        ]
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "not a valid UUID" in captured.err

    def test_missing_source_arg_exits_nonzero(self) -> None:
        """Missing --source causes argparse to exit nonzero."""
        argv = [
            "--jurisdiction-id",
            _VALID_UUID,
            "--jurisdiction-name",
            "Denver, CO",
        ]
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0

    def test_missing_jurisdiction_id_exits_nonzero(self) -> None:
        """Missing --jurisdiction-id causes argparse to exit nonzero."""
        argv = [
            "--source",
            "https://denvergov.org/recycling",
            "--jurisdiction-name",
            "Denver, CO",
        ]
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0

    def test_missing_jurisdiction_name_exits_nonzero(self) -> None:
        """Missing --jurisdiction-name causes argparse to exit nonzero."""
        argv = [
            "--source",
            "https://denvergov.org/recycling",
            "--jurisdiction-id",
            _VALID_UUID,
        ]
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0


class TestIngestCLIRunIngestion:
    def test_run_ingestion_raising_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """run_ingestion raising prints error to stderr and exits 1."""
        with (
            patch(
                "src.cli.ingest.run_ingestion",
                side_effect=RuntimeError("DB connection failed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(_BASE_ARGV)
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "ingestion failed" in captured.err

    def test_happy_path_prints_report_id_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful run prints the report ID and exits 0."""
        report_id = IngestionReportId(uuid.uuid4())
        with patch(
            "src.cli.ingest.run_ingestion",
            return_value=report_id,
        ):
            main(_BASE_ARGV)
        captured = capsys.readouterr()
        assert str(report_id) in captured.out
