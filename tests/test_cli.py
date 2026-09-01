from __future__ import annotations

import json
from pathlib import Path

import pytest

from reportforge import cli, engine


@pytest.fixture
def isolated_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


@pytest.mark.parametrize(
    "payload",
    [
        '{"value": "42", "label": "Signal"}',
        '["not-an-object"]',
        '[{"value": "42"}]',
    ],
)
def test_cli_rejects_invalid_metric_shape_without_traceback(
    isolated_cli: Path,
    capsys: pytest.CaptureFixture[str],
    payload: str,
) -> None:
    exit_code = cli.main(
        [
            "new",
            "invalid-metrics",
            "--template",
            "modern",
            "--kpis",
            payload,
        ]
    )

    captured = capsys.readouterr()
    response = json.loads(captured.err)
    assert exit_code == 1
    assert response["ok"] is False
    assert "list of objects" in response["error"]
    assert not (isolated_cli / "invalid-metrics").exists()


def test_cli_scaffolds_studio_with_generic_visual_options(
    isolated_cli: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "new",
            "studio-cli",
            "--template",
            "studio",
            "--organization",
            "North Studio",
            "--eyebrow",
            "Annual Review",
            "--title-layout",
            "compact",
            "--accent",
            "#0f766e",
            "--metrics",
            '[{"value":"42","label":"Responses"}]',
            "--formats",
            "html",
        ]
    )

    captured = capsys.readouterr()
    response = json.loads(captured.out)
    assert exit_code == 0
    assert response["ok"] is True
    source = Path(response["source"]).read_text()
    front_matter = __import__("yaml").safe_load(source.split("---", 2)[1])
    assert front_matter["organization"] == "North Studio"
    assert front_matter["eyebrow"] == "Annual Review"
    assert front_matter["title-layout"] == "compact"
    assert front_matter["accent"] == "#0f766e"
    assert front_matter["metrics"] == [{"value": "42", "label": "Responses"}]
