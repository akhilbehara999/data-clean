# -*- coding: utf-8 -*-
"""Code exporter — generates pandas code snippets for any V3 operation."""

from __future__ import annotations


def export_eda_code(filename: str) -> str:
    return f'''```python
import pandas as pd

df = pd.read_csv("{filename}")
print(df.describe())
print(df.info())
print(df.dtypes.value_counts())

# Categorical columns
for col in df.select_dtypes(include="object").columns:
    print(f"\\n{{col}}:")
    print(df[col].value_counts().head(5))

# Correlation matrix
print(df.select_dtypes(include="number").corr())
```'''


def export_relationships_code(filename: str) -> str:
    return f'''```python
import pandas as pd
import numpy as np

df = pd.read_csv("{filename}")
num_cols = df.select_dtypes(include="number").columns.tolist()
corr = df[num_cols].corr()

# Strong correlations
for i, c1 in enumerate(num_cols):
    for j, c2 in enumerate(num_cols):
        if i < j and abs(corr.loc[c1, c2]) > 0.3:
            print(f"{{c1}} ↔ {{c2}}  r = {{corr.loc[c1, c2]:.2f}}")
```'''


def export_insights_code(filename: str) -> str:
    return f'''```python
import pandas as pd
import numpy as np

df = pd.read_csv("{filename}")
num_cols = df.select_dtypes(include="number").columns

for col in num_cols:
    s = df[col].dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    outliers = s[(s < q1 - 1.5*iqr) | (s > q3 + 1.5*iqr)]
    if len(outliers):
        print(f"{{col}}: {{len(outliers)}} outlier(s)")
    if abs(s.skew()) > 1:
        print(f"{{col}}: skewed (skew={{s.skew():.2f}})")
```'''


def export_column_code(col: str, filename: str) -> str:
    return f'''```python
import pandas as pd

df = pd.read_csv("{filename}")
s = df["{col}"].dropna()
print(s.describe())
print(s.value_counts().head(10))
```'''


def export_pivot_code(row: str, val: str, agg: str, filename: str) -> str:
    return f'''```python
import pandas as pd

df = pd.read_csv("{filename}")
pivot = df.groupby("{row}")[["{val}"]].agg("{agg}")
print(pivot)
```'''


def export_generic_code(filename: str) -> str:
    return f'''```python
import pandas as pd

df = pd.read_csv("{filename}")
print(df.head())
print(df.describe())
```'''


def get_code_for_operation(op: str | None, filename: str, **kwargs) -> str:
    """Return code snippet for the last or requested operation."""
    dispatch = {
        "eda":           lambda: export_eda_code(filename),
        "relationships": lambda: export_relationships_code(filename),
        "insights":      lambda: export_insights_code(filename),
        "column_detail": lambda: export_column_code(kwargs.get("col", "column"), filename),
        "pivot":         lambda: export_pivot_code(
                             kwargs.get("row", "col"), kwargs.get("val", "val"),
                             kwargs.get("agg", "mean"), filename),
    }
    fn = dispatch.get(op)
    if fn:
        return f"Here's the pandas code for that operation:\n\n{fn()}"
    return f"Here's a starter template:\n\n{export_generic_code(filename)}"
