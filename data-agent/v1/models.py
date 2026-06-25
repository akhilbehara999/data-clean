"""Data models for inspection findings and cleaning actions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    """Represents a single data quality issue found during inspection."""
    column: str
    issue_type: str
    severity: str  # 'critical', 'moderate', 'minor', 'outlier'
    description: str
    count: int = 0
    percentage: float = 0.0
    examples: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class CleaningAction:
    """Represents a single proposed cleaning operation."""
    step: int
    description: str
    action_type: str
    params: dict = field(default_factory=dict)
    affected_count: int = 0


@dataclass
class InspectionReport:
    """Complete inspection report for a data file."""
    filename: str
    rows: int
    columns: int
    file_size: str
    critical: list[Finding] = field(default_factory=list)
    moderate: list[Finding] = field(default_factory=list)
    minor: list[Finding] = field(default_factory=list)
    outliers: list[Finding] = field(default_factory=list)
    clean_columns: list[str] = field(default_factory=list)
    cleaning_actions: list[CleaningAction] = field(default_factory=list)
    output_path: str = ""

    @property
    def has_issues(self) -> bool:
        return bool(self.critical or self.moderate or self.minor or self.outliers)

    @property
    def total_issues(self) -> int:
        return len(self.critical) + len(self.moderate) + len(self.minor) + len(self.outliers)
