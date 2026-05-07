import os
from groq import Groq
import pandas as pd
import json
from app.services.db_loader import get_dataset, get_metadata
from app.utils.chart_builder import build_chart_spec

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"


def build_context(session_id: str) -> str:
    meta = get_metadata(session_id)
    if not meta:
        return "Aucune base de données chargée."
    df = get_dataset(session_id)
    sample_str = df.head(3).to_markdown() if df is not None else ""
    col_summary = "\n".join(
        f"  - {c['name']} ({c['dtype']}, {c['unique_count']} valeurs uniques)"
        for c in meta["column_info"][:15]
    )
    return f"""
BASE DE DONNÉES: {meta['name']} ({meta['source_type'].upper()})
STATISTIQUES: {meta['rows']:,} lignes, {meta['columns']} colonnes, {meta['size_mb']} MB, {meta['null_pct']}% nulls
COLONNES:
{col_summary}
ÉCHANTILLON (3 premières lignes):
{sample_str}
"""


async def chat_with_gemini(session_id: str, user_message: str, history: list[dict]) -> dict:
    context = build_context(session_id)

    history_text = ""
    for msg in history[-6:]:
        role = "Utilisateur" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""Tu es DataIQ, un expert en analyse de données pour entreprises.
Tu as accès à cette base de données:

{context}

Historique:
{history_text}

QUESTION: {user_message}

Réponds UNIQUEMENT en JSON valide:
{{
  "answer": "Réponse claire en français",
  "sql": "SELECT ... ou null",
  "chart": {{
    "type": "bar",
    "title": "Titre du graphique",
    "x_column": "nom_colonne_x",
    "y_column": "nom_colonne_y",
    "description": "Description"
  }},
  "insights": ["insight 1", "insight 2"],
  "follow_up_questions": ["question 1", "question 2"]
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "answer": raw,
            "sql": None,
            "chart": None,
            "insights": [],
            "follow_up_questions": []
        }

    if result.get("chart") and result["chart"].get("type") and result["chart"]["type"] != "null":
        df = get_dataset(session_id)
        if df is not None:
            result["chart"]["data"] = build_chart_spec(
                df,
                result["chart"].get("x_column"),
                result["chart"].get("y_column"),
                result["chart"]["type"]
            )
    return result


async def detect_anomalies(session_id: str) -> dict:
    df = get_dataset(session_id)
    meta = get_metadata(session_id)
    if df is None:
        return {"error": "Pas de données chargées"}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    stats_summary = df[numeric_cols].describe().to_markdown() if numeric_cols else "Aucune colonne numérique"

    prompt = f"""Analyse ces statistiques et détecte les anomalies.
BASE: {meta['name']} — {meta['rows']:,} lignes
{stats_summary}

Réponds UNIQUEMENT en JSON valide:
{{
  "anomalies": [
    {{"colonne": "...", "type": "outlier", "description": "...", "severity": "high"}}
  ],
  "data_quality_score": 85,
  "recommendations": ["recommandation 1", "recommandation 2"]
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return {"raw": raw}
