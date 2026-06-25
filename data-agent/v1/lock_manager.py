import os
import json
import datetime
import time

WEBLOCK_PATH = os.path.join("sessions", "weblock.json")
HEARTBEAT_INTERVAL = 20
LOCK_TIMEOUT = 90

def _read_weblock() -> dict:
    if os.path.exists(WEBLOCK_PATH):
        try:
            with open(WEBLOCK_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"locked": False, "last_heartbeat": None}

def _write_weblock(data: dict):
    os.makedirs(os.path.dirname(WEBLOCK_PATH), exist_ok=True)
    with open(WEBLOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def is_locked() -> bool:
    lock = _read_weblock()
    if not lock.get("locked"):
        return False
    if lock.get("last_heartbeat") is None:
        return False
    try:
        age = (datetime.datetime.now() - datetime.datetime.fromisoformat(lock["last_heartbeat"])).total_seconds()
        if age > LOCK_TIMEOUT:
            # terminal crashed or was force-closed — auto-release
            _write_weblock({"locked": False, "last_heartbeat": None})
            return False
    except Exception:
        return False
    return True

def acquire_lock():
    now_str = datetime.datetime.now().isoformat()
    _write_weblock({"locked": True, "last_heartbeat": now_str})

def release_lock():
    _write_weblock({"locked": False, "last_heartbeat": None})

def update_heartbeat():
    now_str = datetime.datetime.now().isoformat()
    _write_weblock({"locked": True, "last_heartbeat": now_str})
