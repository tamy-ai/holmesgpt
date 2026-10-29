"""What Holmes can read to enrich a ticket, and that every HTTP reader stays read-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def _toolsets() -> dict[str, Any]:
    return yaml.safe_load(CONFIG.read_text())["toolsets"]


def _http_toolsets() -> dict[str, Any]:
    return {name: ts for name, ts in _toolsets().items() if (ts or {}).get("type") == "http"}


def test_every_http_reader_only_reads() -> None:
    for name, toolset in _http_toolsets().items():
        for endpoint in toolset["config"]["endpoints"]:
            assert endpoint["methods"] == ["GET"], name


def test_holmes_reads_the_glitchtip_error_and_its_latest_event() -> None:
    glitchtip = _http_toolsets()["glitchtip"]
    paths = glitchtip["config"]["endpoints"][0]["paths"]

    assert glitchtip["enabled"] is True
    assert "/api/0/organizations/tamy/issues/" in paths
    assert "/api/0/issues/*/events/latest/" in paths
    assert glitchtip["config"]["endpoints"][0]["auth"]["type"] == "bearer"


def test_holmes_reads_the_alert_rule_and_its_history() -> None:
    paths = _http_toolsets()["grafana-alerts"]["config"]["endpoints"][0]["paths"]

    assert "/api/v1/provisioning/alert-rules/*" in paths
    assert "/api/annotations" in paths


def test_holmes_reads_what_changed_between_two_releases() -> None:
    paths = _http_toolsets()["github-releases"]["config"]["endpoints"][0]["paths"]

    assert "/repos/tamy-ai/tamy-assistant/compare/*" in paths
    assert "/repos/tamy-ai/tamy-assistant/tags" in paths


def test_holmes_reads_traces_through_the_grafana_tempo_datasource() -> None:
    tempo = _toolsets()["grafana/tempo"]

    assert tempo["enabled"] is True
    assert tempo["config"]["grafana_datasource_uid"] == "tempo"
