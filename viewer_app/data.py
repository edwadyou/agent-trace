# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import json
import os
import time as _time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

from viewer.normalize import canon, span_kind

from . import state
from .config import _DEFAULT_TRACE_PATHS, _migrate_record, _SDK_SCHEMA, _dbg
from .format import _estimate_cost, _format_duration_ms


@dataclass
class TraceKPI:

    n_spans: int = 0

    n_errors: int = 0

    n_llm: int = 0

    n_tool: int = 0

    n_chain: int = 0

    n_agent: int = 0

    n_prompt: int = 0

    t_in: int = 0

    t_out: int = 0

    tok_present: bool = False

    dur_ms: float = 0.0

    start_ns: int = 0

    end_ns: int = 0

    final_status: str = "UNSET"

    service_name: str = ""

    agent_names: list = field(default_factory=list)

    cost_usd: float = 0.0


def _aggregate_kpi(spans: list) -> TraceKPI:

    k = TraceKPI()

    k.n_spans = len(spans)

    if not spans:

        return k

    starts = [int(s.get("start_time", 0)) for s in spans]

    ends = [int(s.get("end_time", 0)) for s in spans]

    k.start_ns = min(starts)

    k.end_ns = max(ends)

    k.dur_ms = (k.end_ns - k.start_ns) / 1_000_000

    services: list = []

    for s in spans:

        attrs = s.get("attributes") or {}

        kind = span_kind(attrs)

        st_ = str(s.get("status", "")).upper()

        if st_ == "ERROR":

            k.n_errors += 1

        if kind == "LLM":

            k.n_llm += 1

            tin = canon(attrs, "tokens.input")

            tout = canon(attrs, "tokens.output")

            if isinstance(tin, int):

                k.t_in += tin; k.tok_present = True

            if isinstance(tout, int):

                k.t_out += tout; k.tok_present = True

            cost = _estimate_cost(s)

            if cost is not None:

                k.cost_usd += cost

        elif kind == "TOOL":

            k.n_tool += 1

        elif kind == "CHAIN":

            k.n_chain += 1

        elif kind == "AGENT":

            k.n_agent += 1

        elif kind == "PROMPT":

            k.n_prompt += 1

        sn = s.get("service_name")

        if isinstance(sn, str) and sn:

            services.append(sn)

    if services:

        k.service_name = Counter(services).most_common(1)[0][0]

    for s in spans:

        if span_kind(s.get("attributes") or {}) == "AGENT":

            nm = s.get("name")

            if nm and nm not in k.agent_names:

                k.agent_names.append(nm)

    if not k.agent_names and spans:

        roots = [s for s in spans if not s.get("parent_span_id")]

        if roots:

            rname = roots[0].get("name") or ""

            if rname:

                k.agent_names = [rname]

    statuses = {str(s.get("status", "")).upper() for s in spans}

    if "ERROR" in statuses:

        k.final_status = "ERROR"

    elif "OK" in statuses:

        k.final_status = "OK"

    else:

        k.final_status = "UNSET"

    return k


def _discover_trace_sources() -> list:

    """Return [(display_label, Path), ...] sorted by mtime desc."""

    seen = set()

    out = []

    for p in _DEFAULT_TRACE_PATHS:

        try:

            p = Path(p)

        except Exception:

            continue

        if not p or str(p) in seen:

            continue

        seen.add(str(p))

        if p.is_file():

            try:

                mtime = p.stat().st_mtime

                size = p.stat().st_size

            except OSError:

                continue

            _mtime_str = _time.strftime("%H:%M:%S", _time.localtime(mtime))

            label = f"{p}  ·  {size // 1024} KB  ·  {_mtime_str}"

            out.append((label, p))

    out.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)

    return out


def load_traces(path_str: str) -> tuple:

    traces: dict = defaultdict(list)

    dropped = 0

    p = Path(path_str)

    if not p.is_file():

        return dict(traces), dropped

    with p.open("r", encoding="utf-8-sig") as f:

        for line in f:

            line = line.strip()

            if not line:

                continue

            try:

                span = json.loads(line)

            except json.JSONDecodeError:

                dropped += 1

                continue

            # If migration fails we drop the row rather than letting an

            # un-migrated (and likely malformed) record corrupt the rest

            # of the trace with a missing schema_version / service_name.

            if _migrate_record is not None:

                try:

                    span = _migrate_record(span)

                except Exception:

                    dropped += 1

                    continue

            tid = span.get("trace_id")

            if not tid:

                dropped += 1

                continue

            traces[tid].append(span)

    return dict(traces), dropped


def _extract_error_info(span: dict) -> dict:

    out = {"status_message": "", "exception_type": "", "stack": ""}

    attrs = span.get("attributes") or {}

    status = span.get("status")

    if isinstance(status, dict):

        out["status_message"] = status.get("message") or ""

    for evt in span.get("events") or []:

        if not isinstance(evt, dict):

            continue

        if evt.get("name") == "exception":

            eattrs = evt.get("attributes") or {}

            out["exception_type"] = (

                eattrs.get("exception.type") or eattrs.get("exception_type") or ""

            )

            out["stack"] = (

                eattrs.get("exception.stacktrace")

                or eattrs.get("exception.stack_trace")

                or eattrs.get("stack_trace")

                or ""

            )

            if not out["status_message"]:

                out["status_message"] = (

                    eattrs.get("exception.message")

                    or eattrs.get("exception_message")

                    or ""

                )

    if not out["status_message"]:

        out["status_message"] = attrs.get("error.message") or attrs.get("exception.message") or ""

    if not out["stack"]:

        out["stack"] = attrs.get("error.stack") or attrs.get("exception.stacktrace") or ""

    if not out["exception_type"]:

        out["exception_type"] = attrs.get("error.type") or attrs.get("exception.type") or ""

    return out


def _latest_start(tid: str) -> int:

    return max((int(s.get("start_time", 0)) for s in state.traces.get(tid, [])), default=0)


__all__ = ['TraceKPI', '_aggregate_kpi', '_discover_trace_sources', 'load_traces', '_extract_error_info', '_latest_start']
