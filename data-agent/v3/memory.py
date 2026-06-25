# -*- coding: utf-8 -*-
"""Conversation history manager for V3."""

from __future__ import annotations


class Memory:
    """Manages the rolling conversation history for V3's LLM context window."""

    MAX_HISTORY = 20  # keep last N exchanges for context

    def __init__(self, session_dict: dict):
        self._session = session_dict
        v3 = session_dict.setdefault("v3_summary", {})
        self._history: list[dict] = v3.setdefault("conversation_history", [])
        self._queries: list[str] = v3.setdefault("queries_run", [])

    # ── public ────────────────────────────────────────────────────────────

    @property
    def history(self) -> list[dict]:
        return self._history

    @property
    def query_count(self) -> int:
        return len(self._queries)

    def add_user(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._queries.append(content)

    def add_assistant(self, content: str, function_called: str | None = None) -> None:
        entry: dict = {"role": "assistant", "content": content}
        if function_called:
            entry["function_called"] = function_called
        self._history.append(entry)

    def recent(self, n: int | None = None) -> list[dict]:
        """Return the last *n* messages (default MAX_HISTORY)."""
        limit = n or self.MAX_HISTORY
        return self._history[-limit:]

    def limited_recent(self, n: int, max_chars: int = 60000) -> list[dict]:
        """Return up to n recent messages, trimmed to stay under max_chars.
        Starts from the most recent and drops oldest messages until total
        characters <= max_chars, but always keeps at least the last 4 messages.
        """
        # Start with the last n messages
        selected = self._history[-n:]
        # If total chars exceed limit, trim from the oldest of selected
        while len(selected) > 4:  # keep at least 4
            total_chars = sum(len(m.get("content", "")) for m in selected)
            if total_chars <= max_chars:
                break
            # Remove the oldest message in selected
            selected = selected[1:]
        # If still over limit and we have exactly 4, we could still trim further
        # but instruction says keep at least last 4, so we stop.
        return selected
