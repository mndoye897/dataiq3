import pandas as pd
from typing import Optional


def build_chart_spec(df: pd.DataFrame, x_col: Optional[str], y_col: Optional[str], chart_type: str) -> dict:
    """Converts a DataFrame slice into a chart-ready dict for the frontend."""
    try:
        if chart_type == "bar":
            return _bar(df, x_col, y_col)
        elif chart_type == "line":
            return _line(df, x_col, y_col)
        elif chart_type == "pie":
            return _pie(df, x_col, y_col)
        elif chart_type == "scatter":
            return _scatter(df, x_col, y_col)
        else:
            return {}
    except Exception as e:
        return {"error": str(e)}


def _bar(df, x_col, y_col):
    if not x_col or not y_col:
        return {}
    grouped = df.groupby(x_col)[y_col].sum().sort_values(ascending=False).head(15)
    return {
        "labels": grouped.index.astype(str).tolist(),
        "values": [round(v, 2) for v in grouped.values.tolist()],
    }


def _line(df, x_col, y_col):
    if not x_col or not y_col:
        return {}
    # Try to parse dates
    try:
        df = df.copy()
        df[x_col] = pd.to_datetime(df[x_col])
        grouped = df.groupby(df[x_col].dt.to_period("M"))[y_col].sum()
        return {
            "labels": grouped.index.astype(str).tolist(),
            "values": [round(v, 2) for v in grouped.values.tolist()],
        }
    except Exception:
        grouped = df.groupby(x_col)[y_col].sum().head(20)
        return {
            "labels": grouped.index.astype(str).tolist(),
            "values": [round(v, 2) for v in grouped.values.tolist()],
        }


def _pie(df, x_col, y_col):
    if not x_col or not y_col:
        return {}
    grouped = df.groupby(x_col)[y_col].sum().sort_values(ascending=False).head(8)
    return {
        "labels": grouped.index.astype(str).tolist(),
        "values": [round(v, 2) for v in grouped.values.tolist()],
    }


def _scatter(df, x_col, y_col):
    if not x_col or not y_col:
        return {}
    sample = df[[x_col, y_col]].dropna().sample(min(500, len(df)))
    return {
        "x": [round(float(v), 4) for v in sample[x_col].tolist()],
        "y": [round(float(v), 4) for v in sample[y_col].tolist()],
    }
