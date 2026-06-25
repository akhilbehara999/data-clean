# -*- coding: utf-8 -*-
"""Intent parser — maps natural language queries to V2 function calls."""

from __future__ import annotations
import re


# ── Intent categories ────────────────────────────────────────────────────────

class Intent:
    DATA_QUERY   = "data_query"
    EXPLANATION  = "explanation"
    REPORT       = "report"
    CODE         = "code"
    AMBIGUOUS    = "ambiguous"
    GENERAL      = "general"


# ── Keyword → v2 function mapping ────────────────────────────────────────────

_QUERY_PATTERNS: list[tuple[list[str], str, str]] = [
    # (keywords, v2_function, description)
    (["eda", "profile", "describe", "summary of data", "summarize", "overview"],
     "eda", "Exploratory Data Analysis"),

    (["relationship", "correlation", "redundant", "correlat"],
     "relationships", "Relationship Detection"),

    (["geographic", "geo breakdown", "by region", "by city", "by state", "by country", "location"],
     "geographic", "Geographic Analysis"),

    (["pivot", "group by", "groupby", "breakdown by", "by category", "aggregate"],
     "pivot", "Pivot Table"),

    (["compare", "comparison", "versus", " vs ", "difference between", "differ"],
     "comparative", "Comparative Analysis"),

    (["insight", "anomal", "unusual", "weird", "pattern", "outlier", "important"],
     "insights", "Insight Engine"),
]

_EXPLANATION_KEYWORDS = [
    "why", "what does", "explain", "interpret", "meaning",
    "tell me about", "what is", "understand",
]

_REPORT_KEYWORDS = [
    "report", "write up", "summary for", "send to my manager",
    "export report", "generate report", "document",
]

_CODE_KEYWORDS = [
    "show me the code", "pandas code", "how would i",
    "python code", "code for", "script", "show code",
]

_GENERAL_KEYWORDS = [
    "hello", "hi", "hey", "thanks", "thank you", "what can you do",
    "who are you", "help me", "good morning", "good evening",
]


# ── Column matching ──────────────────────────────────────────────────────────

def _find_column_ref(query: str, columns: list[str]) -> str | None:
    """Return the best-matching column name from the query, or None."""
    q = query.lower()
    # Exact substring match (longest first to avoid partial)
    sorted_cols = sorted(columns, key=len, reverse=True)
    for col in sorted_cols:
        if col.lower() in q:
            return col
    return None


def _extract_top_n(query: str) -> int | None:
    """Extract 'top N' from a query."""
    m = re.search(r"\btop\s+(\d+)\b", query.lower())
    return int(m.group(1)) if m else None


# ── Public API ───────────────────────────────────────────────────────────────

class ParsedIntent:
    """Structured result from intent parsing."""

    def __init__(
        self,
        category: str,
        v2_function: str | None = None,
        description: str = "",
        column_ref: str | None = None,
        top_n: int | None = None,
        raw_query: str = "",
    ):
        self.category = category
        self.v2_function = v2_function
        self.description = description
        self.column_ref = column_ref
        self.top_n = top_n
        self.raw_query = raw_query

    def __repr__(self):
        return (f"ParsedIntent(category={self.category!r}, "
                f"v2_function={self.v2_function!r}, "
                f"column={self.column_ref!r})")


def parse_intent(query: str, columns: list[str]) -> ParsedIntent:
    """Classify a user query into an intent category and optional v2 function."""
    q = query.lower().strip()

    # 1 — Code request (check first, it's very specific)
    if any(kw in q for kw in _CODE_KEYWORDS):
        return ParsedIntent(Intent.CODE, raw_query=query,
                            description="Code generation request")

    # 2 — Report request
    if any(kw in q for kw in _REPORT_KEYWORDS):
        return ParsedIntent(Intent.REPORT, v2_function="report",
                            raw_query=query, description="Report generation")

    # 3 — Data query (match v2 functions)
    for keywords, func, desc in _QUERY_PATTERNS:
        if any(kw in q for kw in keywords):
            col = _find_column_ref(query, columns)
            top_n = _extract_top_n(query)
            return ParsedIntent(Intent.DATA_QUERY, v2_function=func,
                                description=desc, column_ref=col,
                                top_n=top_n, raw_query=query)

    # 4 — Explanation
    if any(kw in q for kw in _EXPLANATION_KEYWORDS):
        col = _find_column_ref(query, columns)
        return ParsedIntent(Intent.EXPLANATION, raw_query=query,
                            column_ref=col, description="Explanation request")

    # 5 — General chat
    if any(kw in q for kw in _GENERAL_KEYWORDS):
        return ParsedIntent(Intent.GENERAL, raw_query=query,
                            description="General conversation")

    # 6 — Check if user is asking about a specific column
    col = _find_column_ref(query, columns)
    if col:
        return ParsedIntent(Intent.DATA_QUERY, v2_function="column_detail",
                            column_ref=col, raw_query=query,
                            description=f"Column detail for '{col}'")

    # 7 — Ambiguous
    return ParsedIntent(Intent.AMBIGUOUS, raw_query=query,
                        description="Unclear intent")
