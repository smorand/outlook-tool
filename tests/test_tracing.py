"""Tests for the tracing module."""

import json
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SpanExportResult

from tracing import JSONLFileExporter, configure_tracing, trace_span


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    """Reset global tracer provider between tests."""
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]


@pytest.fixture
def otel_log(tmp_path: Path) -> Path:
    """Return path for OTel JSONL log file."""
    return tmp_path / "test-otel.log"


def test_configure_tracing_creates_provider(tmp_path: Path) -> None:
    """Test that configure_tracing returns a valid provider."""
    provider = configure_tracing(app_name="test", log_dir=tmp_path)
    assert provider is not None
    provider.shutdown()


def test_trace_span_writes_jsonl(tmp_path: Path) -> None:
    """Test that trace_span produces JSONL output."""
    provider = configure_tracing(app_name="test", log_dir=tmp_path)

    with trace_span("test.operation", attributes={"key": "value"}) as span:
        assert span is not None

    provider.shutdown()

    otel_log = tmp_path / "test-otel.log"
    assert otel_log.exists()

    lines = otel_log.read_text().strip().splitlines()
    assert len(lines) >= 1

    record = json.loads(lines[0])
    assert record["name"] == "test.operation"
    assert record["attributes"]["key"] == "value"
    assert record["status"] == "UNSET"


def test_trace_span_records_exception(tmp_path: Path) -> None:
    """Test that exceptions are recorded in spans."""
    provider = configure_tracing(app_name="test_err", log_dir=tmp_path)

    with pytest.raises(ValueError, match="test error"), trace_span("test.error"):
        raise ValueError("test error")

    provider.shutdown()

    otel_log = tmp_path / "test_err-otel.log"
    record = json.loads(otel_log.read_text().strip().splitlines()[0])
    assert record["status"] == "ERROR"
    assert any(e["name"] == "exception" for e in record.get("events", []))


def test_jsonl_exporter_creates_file(otel_log: Path) -> None:
    """Test that JSONLFileExporter creates the log file on first write."""
    exporter = JSONLFileExporter(otel_log)
    assert not otel_log.exists()
    result = exporter.export([])
    assert result == SpanExportResult.SUCCESS
    exporter.shutdown()
