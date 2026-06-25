# -*- coding: utf-8 -*-
"""Session bridge — reads/writes session.json and handles version switching."""

from __future__ import annotations

import os
import pandas as pd


def save_and_switch_to_v2(session_dict: dict, df: pd.DataFrame):
    """Persist state and set version to V2 for the launcher loop."""
    from v1 import session_manager

    session_dict["active_version"] = "v2"
    session_manager.save_session(session_dict, df)


def save_and_switch_to_v3(session_dict: dict, df: pd.DataFrame):
    """Persist state and set version to V3 for the launcher loop."""
    from v1 import session_manager

    session_dict["active_version"] = "v3"
    session_manager.save_session(session_dict, df)


def autosave(session_dict: dict, df: pd.DataFrame | None = None):
    """Silently persist session.json (and pickle if df provided)."""
    from v1 import session_manager
    session_manager.save_session(session_dict, df)
def save_and_switch_to_v4(session_dict: dict, df=None):
    """Persist state and set version to V4 for the launcher loop."""
    from v1 import session_manager

    session_dict["active_version"] = "v4"
    session_manager.save_session(session_dict, df)
