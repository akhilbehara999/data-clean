# -*- coding: utf-8 -*-
"""
Base specialist interface — Feature 7.

All specialist classes subclass BaseSpecialist and implement:
  applicable_rules(df, column_types) → list[str]  (names of applicable rules)
  run(df)                            → list[Finding]
  format_findings(findings)          → str  (Rich markup / Markdown)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Finding:
    """A single specialist finding."""
    rule_name: str
    description: str             # Human-readable, specific (references actual values)
    severity: str = "medium"     # "high" | "medium" | "low"
    affected_rows: int = 0
    columns_involved: list[str] = field(default_factory=list)
    sample_values: list = field(default_factory=list)


class BaseSpecialist:
    """Abstract base class for all domain specialists."""

    name: str = "base"
    domain: str = "general"
    required_column_hints: list[str] = []  # optional — column name keywords to look for

    def applicable_rules(self, df: pd.DataFrame, column_types: dict) -> list[str]:
        """
        Return names of rules that are applicable given this dataset's columns.
        Subclasses override this.
        """
        return []

    def run(self, df: pd.DataFrame) -> list[Finding]:
        """
        Execute all applicable rules and return a list of Findings.
        Subclasses override this.
        """
        return []

    def format_findings(self, findings: list[Finding]) -> str:
        """
        Format findings as Rich-markup / Markdown string.
        Shows a [Specialist] header, N patterns, and an export offer.
        """
        if not findings:
            return (
                f"[bold cyan][{self.name.capitalize()} specialist][/bold cyan] "
                f"No significant patterns found with the available columns."
            )

        lines = [
            f"[bold cyan][{self.name.capitalize()} specialist][/bold cyan] "
            f"Found [bold]{len(findings)}[/bold] pattern(s) worth flagging:",
            "",
        ]
        for f in findings:
            icon = "🚨" if f.severity == "high" else ("⚠" if f.severity == "medium" else "ℹ")
            lines.append(f"  {icon} {f.description}")
            if f.affected_rows:
                lines.append(f"     [dim]Affected rows: {f.affected_rows:,}[/dim]")
        lines += [
            "",
            "[dim]These are statistical patterns, not confirmed findings —"
            " recommend manual review.[/dim]",
            "[dim]I can export the flagged rows for investigation — type /export.[/dim]",
        ]
        return "\n".join(lines)

    def check_required_columns(self, df: pd.DataFrame) -> list[str]:
        """
        Return a list of missing-column warning strings.
        Called before run() to surface column gaps to user.
        """
        return []

    def _find_col(self, df: pd.DataFrame, keywords: list[str]) -> Optional[str]:
        """Find first column whose name contains any of the keywords."""
        for col in df.columns:
            if any(kw in col.lower() for kw in keywords):
                return col
        return None

    def _find_cols(self, df: pd.DataFrame, keywords: list[str]) -> list[str]:
        """Find all columns whose names contain any of the keywords."""
        return [col for col in df.columns if any(kw in col.lower() for kw in keywords)]
