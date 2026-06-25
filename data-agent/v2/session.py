"""Session log — tracks every action during a v2 analysis session."""

from datetime import datetime


class SessionLog:
    """Maintains a timestamped log of all v2 session actions."""

    def __init__(self, entries: list[dict] = None):
        self.entries: list[dict] = entries if entries is not None else []
        self.start_time = datetime.now()

    def log(
        self,
        command: str,
        input_params: str = "",
        output_summary: str = "",
        export: str = "",
    ):
        """Append a new entry to the session log."""
        self.entries.append(
            {
                "time": datetime.now().strftime("%H:%M"),
                "command": command,
                "input_params": input_params,
                "output_summary": output_summary,
                "export": export,
            }
        )

    def format_entries(self) -> list[str]:
        """Return human-readable log lines."""
        lines: list[str] = []
        for e in self.entries:
            line = f"  [{e['time']}] {e['command']}"
            if e["input_params"]:
                line += f" — {e['input_params']}"
            if e["output_summary"]:
                line += f" — {e['output_summary']}"
            if e["export"]:
                line += f" → exported {e['export']}"
            lines.append(line)
        return lines

    def as_table_rows(self) -> list[dict]:
        """Return log entries as list of dicts (for DataFrame export)."""
        return list(self.entries)
