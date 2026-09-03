# -*- coding: utf-8 -*-
# Mutable runtime state shared across viewer modules.
# `traces` is populated by the main entry (`viewer_app.run`) on each rerun.
from __future__ import annotations

# dict[trace_id -> list[span-dict]] for the currently selected trace source
traces: dict = {}
