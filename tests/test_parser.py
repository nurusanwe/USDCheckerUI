"""Tests for core.parser — parameterized on parser_samples.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from usdchecker_ui.core.parser import parse_one


def _load_samples() -> list[dict]:
    here = Path(__file__).parent / "fixtures" / "parser_samples.yaml"
    with here.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("sample", _load_samples(), ids=lambda s: s["id"])
def test_parse_sample(sample: dict) -> None:
    diag = parse_one(sample["raw"], sample["severity"], sample["source"])
    assert diag.rule == sample["expected_rule"]
    assert diag.prim_path == sample["expected_prim"]
    assert diag.asset_path == sample["expected_asset"]
    assert diag.message == sample["raw"], "raw must be preserved verbatim"
    assert diag.severity == sample["severity"]


def test_unknown_fallback_preserves_raw() -> None:
    raw = "totally unparseable jibber"
    diag = parse_one(raw, "error", "errors")
    assert diag.rule == "Unknown"
    assert diag.message == raw
    assert diag.prim_path is None
    assert diag.asset_path is None
