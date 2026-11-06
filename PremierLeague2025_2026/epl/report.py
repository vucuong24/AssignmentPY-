"""Markdown table formatting shared by the report generator."""
from __future__ import annotations

import pandas as pd


def markdown_table(df: pd.DataFrame) -> str:
    def format_value(value):
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:,.3f}".rstrip("0").rstrip(".")
        return str(value).replace("|", "/").replace("\n", " ")
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "| " + " | ".join(["---"] * len(df.columns)) + " |"]
    lines.extend("| " + " | ".join(format_value(value) for value in row) + " |" for row in df.itertuples(index=False, name=None))
    return "\n".join(lines)
