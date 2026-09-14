"""Regression tests for JsonlFileExporter truncate_on_init behaviour."""
from __future__ import annotations
from pathlib import Path

from agent_monitor import jsonl_exporter
from agent_monitor.jsonl_exporter import JsonlFileExporter


def test_default_does_not_truncate(tmp_path: Path):
    "Default truncate_on_init=False preserves pre-existing content."
    f = tmp_path / "x.jsonl"
    f.write_text(chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f)
    assert f.read_text(encoding="utf-8") == chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10)


def test_explicit_truncate_clears(tmp_path: Path):
    f = tmp_path / "x.jsonl"
    f.write_text(chr(123) + chr(34) + "legacy" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f, truncate_on_init=True)
    assert f.read_text(encoding="utf-8") == ""


def test_repeat_construction_does_not_re_truncate(tmp_path: Path):
    "Two JsonlFileExporter on the same file in one process only truncate once."
    f = tmp_path / "x.jsonl"
    JsonlFileExporter(f, truncate_on_init=True)
    f.write_text(chr(123) + chr(34) + "first" + chr(34) + ": 1" + chr(125) + chr(10), encoding="utf-8")
    JsonlFileExporter(f, truncate_on_init=True)
    assert f.read_text(encoding="utf-8") == chr(123) + chr(34) + "first" + chr(34) + ": 1" + chr(125) + chr(10)


def test_registry_is_module_level():
    jsonl_exporter._TRUNCATED_FILES.add("__synthetic_path__")
    assert "__synthetic_path__" in jsonl_exporter._TRUNCATED_FILES
    jsonl_exporter._TRUNCATED_FILES.discard("__synthetic_path__")


def test_concurrent_export_never_splices_a_record(tmp_path: Path):
    """Regression: SimpleSpanProcessor exports on whichever thread ends a span,
    so a ThreadPoolExecutor fan-out calls export() concurrently. The old
    text-mode append handle let BufferedWriter flush one record in several
    chunks, and two interleaving threads spliced a record across two physical
    lines -> unparsable JSONL. Records are made larger than the 8 KiB buffer on
    purpose so a chunked write is actually exercised."""
    import concurrent.futures as cf
    import json

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    f = tmp_path / "concurrent.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlFileExporter(f)))
    tracer = provider.get_tracer("concurrency-test")

    # 16x25 with ~20 KiB records is the smallest workload that reliably
    # exposes the old bug: it lost or spliced at least one record in ~1 of 5
    # trials. Each span name is unique so a dropped record is detected even
    # when the surviving lines all still parse.
    n_threads, n_spans = 16, 25
    blob = "x" * 20000

    def work(i: int) -> None:
        for j in range(n_spans):
            with tracer.start_as_current_span("span-%d-%d" % (i, j)) as sp:
                sp.set_attribute("payload", blob)

    with cf.ThreadPoolExecutor(max_workers=n_threads) as ex:
        list(ex.map(work, range(n_threads)))
    provider.shutdown()

    raw = f.read_bytes()
    lines = [ln for ln in raw.decode("utf-8").split("\n") if ln.strip()]
    assert len(lines) == n_threads * n_spans, "records lost or spliced"

    seen = set()
    for ln in lines:
        rec = json.loads(ln)  # raises on a spliced line
        assert rec["attributes"]["payload"] == blob
        seen.add(rec["name"])
    assert seen == {"span-%d-%d" % (i, j) for i in range(n_threads) for j in range(n_spans)}
    assert b"\r" not in raw, "JSONL must be LF-only (no CRLF translation)"


def test_export_writes_each_batch_in_a_single_binary_append(tmp_path: Path, monkeypatch):
    """Deterministic guard for the fix mechanism: the serialized batch must
    reach the file in ONE binary-append write() call. Chunked or text-mode
    writes are what allowed two threads to interleave mid-record."""
    import pathlib

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    modes = []
    sizes = []
    real_open = pathlib.Path.open

    class _Recorder:
        def __init__(self, fh):
            self._fh = fh

        def write(self, data):
            sizes.append(len(data))
            return self._fh.write(data)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return self._fh.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self._fh, name)

    def spy(self, mode="r", *args, **kwargs):
        fh = real_open(self, mode, *args, **kwargs)
        if isinstance(mode, str) and ("a" in mode or "w" in mode):
            modes.append(mode)
            return _Recorder(fh)
        return fh

    monkeypatch.setattr(pathlib.Path, "open", spy)

    f = tmp_path / "batch.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlFileExporter(f)))
    tracer = provider.get_tracer("batch-test")
    for i in range(5):
        with tracer.start_as_current_span("s%d" % i):
            pass
    provider.shutdown()

    assert modes == ["ab"] * 5, modes
    assert len(sizes) == 5, "each export must be exactly one write()"
    assert all(s > 0 for s in sizes)
    assert len(f.read_text(encoding="utf-8").strip().split("\n")) == 5
