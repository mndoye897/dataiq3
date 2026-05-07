import pandas as pd
import sqlalchemy
from pathlib import Path
from typing import Optional
import json

# In-memory store for loaded datasets (use Redis for production)
_datasets: dict[str, pd.DataFrame] = {}
_metadata: dict[str, dict] = {}


def load_csv(session_id: str, file_path: str) -> dict:
    df = pd.read_csv(file_path, low_memory=False)
    return _register(session_id, df, Path(file_path).name, "csv")


def load_excel(session_id: str, file_path: str) -> dict:
    df = pd.read_excel(file_path)
    return _register(session_id, df, Path(file_path).name, "excel")



def load_sql(session_id: str, connection_string: str, query: str, name: str) -> dict:
    engine = sqlalchemy.create_engine(connection_string)
    df = pd.read_sql(query, engine)
    return _register(session_id, df, name, "sql")


def _register(session_id: str, df: pd.DataFrame, name: str, source_type: str) -> dict:
    _datasets[session_id] = df

    meta = {
        "name": name,
        "source_type": source_type,
        "rows": len(df),
        "columns": len(df.columns),
        "size_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        "column_info": _column_info(df),
        "null_pct": round(df.isnull().mean().mean() * 100, 2),
        "sample": df.head(5).to_dict(orient="records"),
    }
    _metadata[session_id] = meta
    return meta


def _column_info(df: pd.DataFrame) -> list[dict]:
    info = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        col_info = {
            "name": col,
            "dtype": dtype,
            "null_count": int(df[col].isnull().sum()),
            "unique_count": int(df[col].nunique()),
        }
        if is_numeric:
            col_info["stats"] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": round(float(df[col].mean()), 2),
                "std": round(float(df[col].std()), 2),
            }
        info.append(col_info)
    return info


def get_dataset(session_id: str) -> Optional[pd.DataFrame]:
    return _datasets.get(session_id)


def get_metadata(session_id: str) -> Optional[dict]:
    return _metadata.get(session_id)


def list_sessions() -> list[str]:
    return list(_datasets.keys())
