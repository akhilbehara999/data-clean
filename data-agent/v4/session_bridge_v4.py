# -*- coding: utf-8 -*-
"""
v4 Session Bridge — extends v3's session_bridge with v4 switch support.
Initialises v4 session keys and handles /switch → v4.
"""

from __future__ import annotations

import os
import pandas as pd
from typing import Optional


def init_v4_session_keys(session_dict: dict) -> dict:
    """
    Add v4-specific top-level keys to a session dict if not present.
    Called on any session load (v1-v4) so v4 features always have a
    home in the session object.
    """
    defaults = {
        "project_memory": {},
        "scheduled_reports": [],
        "watchdog_config": {},
        "simulation_log": [],
        "specialist_findings": [],
        "custom_rules": {"triggered": []},
        "calculation_log": [],
    }
    for key, default in defaults.items():
        if key not in session_dict:
            session_dict[key] = default
    return session_dict


def save_and_switch_to_v4(session_dict: dict, df: Optional[pd.DataFrame] = None) -> None:
    """Set active_version = 'v4' and persist the session."""
    from v1 import session_manager
    session_dict["active_version"] = "v4"
    session_manager.save_session(session_dict, df)


def save_and_switch_to_v2(session_dict: dict, df: Optional[pd.DataFrame] = None) -> None:
    """Set active_version = 'v2' and persist."""
    from v1 import session_manager
    session_dict["active_version"] = "v2"
    session_manager.save_session(session_dict, df)


def save_and_switch_to_v3(session_dict: dict, df: Optional[pd.DataFrame] = None) -> None:
    """Set active_version = 'v3' and persist."""
    from v1 import session_manager
    session_dict["active_version"] = "v3"
    session_manager.save_session(session_dict, df)


def autosave(session_dict: dict, df: Optional[pd.DataFrame] = None) -> None:
    """Silently persist session + optional dataframe."""
    from v1 import session_manager
    session_manager.save_session(session_dict, df)
