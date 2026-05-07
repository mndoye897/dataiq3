from fastapi import APIRouter, HTTPException, Header
from app.services.db_loader import get_dataset, get_metadata
from app.services.gemini_service import chat_with_gemini
from app.utils.chart_builder import build_chart_spec
import pandas as pd

router = APIRouter()


@router.get("/{session_id}")
async def get_dashboard(session_id: str, authorization: str = Header(None)):
    df = get_dataset(session_id)
    meta = get_metadata(session_id)
    if df is None:
        raise HTTPException(404, "Session introuvable")

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()

    # ── KPI Cards ──
    kpis = []
    for col in numeric_cols[:6]:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        kpis.append({
            "label": col.replace("_", " ").title(),
            "value": round(float(s.sum()), 2),
            "avg": round(float(s.mean()), 2),
            "min": round(float(s.min()), 2),
            "max": round(float(s.max()), 2),
            "type": "numeric"
        })

    for col in cat_cols[:3]:
        kpis.append({
            "label": col.replace("_", " ").title(),
            "value": int(df[col].nunique()),
            "type": "categorical",
            "top": df[col].value_counts().head(1).index[0] if len(df[col]) > 0 else "—"
        })

    # ── Charts ──
    charts = []
    if numeric_cols and cat_cols:
        chart_data = build_chart_spec(df, cat_cols[0], numeric_cols[0], "bar")
        if chart_data:
            charts.append({
                "type": "bar",
                "title": f"{numeric_cols[0].replace('_',' ').title()} par {cat_cols[0].replace('_',' ').title()}",
                "data": chart_data
            })

    if len(numeric_cols) >= 2:
        chart_data = build_chart_spec(df, numeric_cols[0], numeric_cols[1], "scatter")
        if chart_data:
            charts.append({
                "type": "scatter",
                "title": f"Corrélation : {numeric_cols[0]} vs {numeric_cols[1]}",
                "data": chart_data
            })

    if cat_cols:
        chart_data = build_chart_spec(df, cat_cols[0], numeric_cols[0] if numeric_cols else None, "pie")
        if chart_data:
            charts.append({
                "type": "pie",
                "title": f"Répartition par {cat_cols[0].replace('_',' ').title()}",
                "data": chart_data
            })

    # ── Alerts ──
    alerts = []
    null_pct = df.isnull().mean()
    for col in null_pct[null_pct > 0.1].index:
        alerts.append({
            "type": "warning",
            "message": f"{col} : {round(null_pct[col]*100,1)}% de valeurs manquantes",
            "severity": "high" if null_pct[col] > 0.3 else "medium"
        })

    for col in numeric_cols[:5]:
        s = df[col].dropna()
        if len(s) < 10:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        outliers = ((s < q1 - 3*iqr) | (s > q3 + 3*iqr)).sum()
        if outliers > 0:
            alerts.append({
                "type": "outlier",
                "message": f"{col} : {outliers} valeurs aberrantes détectées",
                "severity": "medium"
            })

    # ── AI Summary ──
    try:
        ai = await chat_with_gemini(session_id, "Donne-moi un résumé exécutif de cette base de données en 2-3 phrases, avec les points les plus importants pour un manager.", [])
        ai_summary = ai.get("answer", "")
        ai_insights = ai.get("insights", [])
    except Exception:
        ai_summary = "Analyse IA indisponible."
        ai_insights = []

    return {
        "meta": meta,
        "kpis": kpis,
        "charts": charts,
        "alerts": alerts,
        "ai_summary": ai_summary,
        "ai_insights": ai_insights
    }
