# -*- coding: utf-8 -*-
"""Thin launcher for the agent-monitor viewer.

The actual implementation lives in the ``viewer_app`` package (split out of
the original single-file ``viewer.py``).  Keep this file as the entry point so
``streamlit run viewer.py`` keeps working unchanged.
"""
from __future__ import annotations

from viewer_app import run

run()
