"""Smoke tests for pilot table-artifact write fallback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from inequality_mechanisms.experiments.pilot import _write_table_artifact


def test_write_table_prefers_csv() -> None:
    run = MagicMock()
    csv_path = Path("/tmp/summary_table.csv")
    run.write_text.return_value = csv_path

    out = _write_table_artifact(run, "summary_table", "a,b\n")
    assert out == csv_path
    run.write_text.assert_called_once_with("summary_table", "a,b\n", suffix=".csv")


def test_write_table_falls_back_to_txt_on_permission_error() -> None:
    run = MagicMock()
    txt_path = Path("/tmp/summary_table.txt")

    def _write(name: str, text: str, *, suffix: str = ".txt") -> Path:
        if suffix == ".csv":
            raise PermissionError("blocked csv")
        return txt_path

    run.write_text.side_effect = _write
    out = _write_table_artifact(run, "summary_table", "section,x\n")
    assert out == txt_path
    assert run.write_text.call_count == 2
    assert run.write_text.call_args_list[0].kwargs["suffix"] == ".csv"
    assert run.write_text.call_args_list[1].kwargs["suffix"] == ".txt"


def test_write_table_reraises_non_permission_errors() -> None:
    run = MagicMock()
    run.write_text.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        _write_table_artifact(run, "summary_table", "a\n")
