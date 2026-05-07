"""
Proactive Business Intelligence Engine
Analyse automatiquement les données et génère des opportunités business
sans que l'utilisateur ne pose de question.
"""
import pandas as pd
import json
from datetime import datetime
from app.services.db_loader import get_dataset, get_metadata

# Store opportunités par session
_opportunities: dict[str, dict] = {}


async def analyze_business_opportunities(session_id: str) -> dict:
    """Point d'entrée principal — analyse complète et génère les opportunités."""
    df = get_dataset(session_id)
    meta = get_metadata(session_id)
    if df is None:
        return {"error": "Pas de données"}

    opportunities = []
    warnings = []
    quick_wins = []

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    date_cols = _detect_date_columns(df)

    # ── ANALYSES STATISTIQUES ──
    opportunities += _analyze_concentration(df, numeric_cols, cat_cols)
    opportunities += _analyze_trends(df, date_cols, numeric_cols)
    opportunities += _analyze_segments(df, cat_cols, numeric_cols)
    opportunities += _analyze_correlations(df, numeric_cols)
    warnings += _analyze_data_quality(df, numeric_cols, cat_cols)
    quick_wins += _detect_quick_wins(df, numeric_cols, cat_cols)

    # ── ANALYSE IA ──
    ai_opportunities = await _ai_business_analysis(session_id, df, meta, opportunities)

    result = {
        "session_id": session_id,
        "analyzed_at": datetime.now().isoformat(),
        "database": meta["name"],
        "rows": meta["rows"],
        "opportunities": opportunities[:8],
        "warnings": warnings[:5],
        "quick_wins": quick_wins[:4],
        "ai_opportunities": ai_opportunities,
        "score": _compute_health_score(df, warnings)
    }

    _opportunities[session_id] = result
    return result


def get_opportunities(session_id: str) -> dict:
    return _opportunities.get(session_id, {})


def _detect_date_columns(df: pd.DataFrame) -> list:
    date_cols = []
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                pd.to_datetime(df[col].dropna().head(10))
                date_cols.append(col)
            except Exception:
                pass
        elif "date" in col.lower() or "time" in col.lower() or "year" in col.lower():
            date_cols.append(col)
    return date_cols


def _analyze_concentration(df, numeric_cols, cat_cols) -> list:
    """Détecte les concentrations dangereuses — règle des 80/20."""
    opps = []
    for cat in cat_cols[:4]:
        for num in numeric_cols[:3]:
            try:
                grouped = df.groupby(cat)[num].sum().sort_values(ascending=False)
                if len(grouped) < 3:
                    continue
                total = grouped.sum()
                if total <= 0:
                    continue
                top1_pct = round(grouped.iloc[0] / total * 100, 1)
                top3_pct = round(grouped.head(3).sum() / total * 100, 1)

                if top1_pct > 40:
                    opps.append({
                        "type": "risk",
                        "icon": "⚠️",
                        "title": f"Dépendance critique sur {grouped.index[0]}",
                        "description": f"{grouped.index[0]} représente {top1_pct}% de votre {num.replace('_',' ')}. Une perte de ce segment impacterait drastiquement vos revenus.",
                        "action": f"Diversifiez vers les segments {', '.join(str(x) for x in grouped.index[1:4])} qui représentent seulement {round(100-top1_pct,1)}% du total.",
                        "impact": "high",
                        "category": "risk_management"
                    })
                if top3_pct > 75 and len(grouped) > 5:
                    bottom_pct = round(grouped.tail(len(grouped)//2).sum() / total * 100, 1)
                    opps.append({
                        "type": "opportunity",
                        "icon": "📈",
                        "title": f"Potentiel inexploité dans les segments faibles",
                        "description": f"Vos 3 premiers segments {cat.replace('_',' ')} font {top3_pct}% du {num.replace('_',' ')}. La moitié inférieure de vos segments ne contribue qu'à {bottom_pct}%.",
                        "action": f"Analysez pourquoi ces segments sous-performent. Une augmentation de 20% dans ces segments = +{round(bottom_pct*0.2,1)}% de croissance globale.",
                        "impact": "medium",
                        "category": "growth"
                    })
            except Exception:
                continue
    return opps


def _analyze_trends(df, date_cols, numeric_cols) -> list:
    """Détecte les tendances temporelles."""
    opps = []
    for date_col in date_cols[:2]:
        for num_col in numeric_cols[:2]:
            try:
                temp = df[[date_col, num_col]].copy()
                temp[date_col] = pd.to_datetime(temp[date_col], errors='coerce')
                temp = temp.dropna()
                if len(temp) < 10:
                    continue
                temp = temp.sort_values(date_col)
                temp['period'] = temp[date_col].dt.to_period('M')
                monthly = temp.groupby('period')[num_col].sum()
                if len(monthly) < 3:
                    continue
                last = float(monthly.iloc[-1])
                prev = float(monthly.iloc[-2])
                avg = float(monthly.mean())
                if prev > 0:
                    growth = round((last - prev) / prev * 100, 1)
                    if growth > 20:
                        opps.append({
                            "type": "opportunity",
                            "icon": "🚀",
                            "title": f"Croissance forte détectée sur {num_col.replace('_',' ')}",
                            "description": f"+{growth}% ce mois vs le mois précédent. Cette tendance positive mérite d'être capitalisée immédiatement.",
                            "action": "Identifiez ce qui a causé cette hausse et répliquez-le sur les autres périodes ou segments.",
                            "impact": "high",
                            "category": "growth"
                        })
                    elif growth < -15:
                        opps.append({
                            "type": "alert",
                            "icon": "📉",
                            "title": f"Baisse significative sur {num_col.replace('_',' ')}",
                            "description": f"{growth}% ce mois vs le mois précédent. Sous la moyenne historique de {round(avg,2)}.",
                            "action": "Analysez les causes immédiatement. Comparez avec la même période l'année précédente.",
                            "impact": "high",
                            "category": "alert"
                        })
                if len(monthly) >= 6:
                    first_half = float(monthly.iloc[:len(monthly)//2].mean())
                    second_half = float(monthly.iloc[len(monthly)//2:].mean())
                    if first_half > 0:
                        trend = round((second_half - first_half) / first_half * 100, 1)
                        if trend > 30:
                            opps.append({
                                "type": "opportunity",
                                "icon": "📊",
                                "title": f"Tendance haussière long terme sur {num_col.replace('_',' ')}",
                                "description": f"+{trend}% sur la seconde moitié de la période analysée vs la première.",
                                "action": "Moment idéal pour augmenter les prix ou investir dans la capacité de production.",
                                "impact": "medium",
                                "category": "pricing"
                            })
            except Exception:
                continue
    return opps


def _analyze_segments(df, cat_cols, numeric_cols) -> list:
    """Identifie les segments les plus rentables et ceux à abandonner."""
    opps = []
    for cat in cat_cols[:3]:
        for num in numeric_cols[:2]:
            try:
                grouped = df.groupby(cat)[num].agg(['mean','count','sum']).round(2)
                grouped.columns = ['avg','count','total']
                grouped = grouped[grouped['count'] >= 3]
                if len(grouped) < 2:
                    continue
                overall_avg = float(df[num].mean())
                top = grouped.nlargest(1, 'avg')
                bottom = grouped.nsmallest(1, 'avg')
                top_val = float(top['avg'].iloc[0])
                bot_val = float(bottom['avg'].iloc[0])
                if overall_avg > 0 and top_val > overall_avg * 1.5:
                    opps.append({
                        "type": "opportunity",
                        "icon": "⭐",
                        "title": f"Segment premium identifié : {top.index[0]}",
                        "description": f"Le segment '{top.index[0]}' génère en moyenne {round(top_val,2)} de {num.replace('_',' ')}, soit {round(top_val/overall_avg*100-100,1)}% au-dessus de la moyenne.",
                        "action": f"Concentrez vos efforts commerciaux sur ce segment. Créez une offre premium dédiée à '{top.index[0]}'.",
                        "impact": "high",
                        "category": "sales"
                    })
                if overall_avg > 0 and bot_val < overall_avg * 0.5 and len(grouped) > 3:
                    opps.append({
                        "type": "insight",
                        "icon": "🔍",
                        "title": f"Segment sous-performant : {bottom.index[0]}",
                        "description": f"'{bottom.index[0]}' est {round(100-bot_val/overall_avg*100,1)}% sous la moyenne. Soit vous l'optimisez, soit vous réallouez ces ressources.",
                        "action": f"Analysez le coût de servir ce segment vs sa contribution. Envisagez de recentrer sur '{top.index[0]}'.",
                        "impact": "medium",
                        "category": "optimization"
                    })
            except Exception:
                continue
    return opps


def _analyze_correlations(df, numeric_cols) -> list:
    """Trouve les corrélations actionables."""
    opps = []
    if len(numeric_cols) < 2:
        return opps
    try:
        corr = df[numeric_cols[:8]].corr()
        for i, col1 in enumerate(numeric_cols[:8]):
            for col2 in numeric_cols[i+1:8]:
                val = corr.loc[col1, col2]
                if abs(val) > 0.7 and not pd.isna(val):
                    direction = "positivement" if val > 0 else "négativement"
                    opps.append({
                        "type": "insight",
                        "icon": "🔗",
                        "title": f"Corrélation forte : {col1.replace('_',' ')} ↔ {col2.replace('_',' ')}",
                        "description": f"Ces deux métriques sont {direction} corrélées (r={round(val,2)}). Agir sur l'une impacte automatiquement l'autre.",
                        "action": f"{'Augmenter' if val > 0 else 'Réduire'} {col1.replace('_',' ')} aura un impact direct sur {col2.replace('_',' ')}.",
                        "impact": "medium",
                        "category": "insight"
                    })
    except Exception:
        pass
    return opps


def _analyze_data_quality(df, numeric_cols, cat_cols) -> list:
    """Génère des alertes qualité avec impact business."""
    warnings = []
    null_pct = df.isnull().mean()
    for col in null_pct[null_pct > 0.05].index:
        pct = round(null_pct[col] * 100, 1)
        warnings.append({
            "type": "quality",
            "icon": "⚠️",
            "title": f"Données manquantes : {col.replace('_',' ')}",
            "description": f"{pct}% de valeurs manquantes dans '{col}'. Vos analyses sur cette colonne sont partielles.",
            "action": "Complétez ces données ou excluez cette colonne des analyses critiques.",
            "impact": "high" if pct > 30 else "medium"
        })
    for col in numeric_cols[:6]:
        s = df[col].dropna()
        if len(s) < 10:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        outliers = int(((s < q1 - 3*iqr) | (s > q3 + 3*iqr)).sum())
        if outliers > 0:
            warnings.append({
                "type": "outlier",
                "icon": "🔴",
                "title": f"Anomalies détectées : {col.replace('_',' ')}",
                "description": f"{outliers} valeurs aberrantes dans '{col}'. Peuvent fausser vos moyennes et décisions.",
                "action": "Vérifiez manuellement ces enregistrements — erreurs de saisie ou cas exceptionnels ?",
                "impact": "medium"
            })
    return warnings


def _detect_quick_wins(df, numeric_cols, cat_cols) -> list:
    """Actions rapides à fort impact."""
    wins = []
    null_pct = df.isnull().mean()
    high_null = null_pct[null_pct > 0.2].index.tolist()
    if high_null:
        wins.append({
            "icon": "🎯",
            "title": "Compléter les données manquantes",
            "description": f"{len(high_null)} colonne(s) avec >20% de données manquantes limitent vos analyses.",
            "effort": "Faible",
            "impact": "Fort"
        })
    if len(numeric_cols) >= 2:
        wins.append({
            "icon": "📊",
            "title": "Créer un tableau de bord hebdomadaire",
            "description": "Automatisez l'envoi des KPIs chaque lundi matin à votre équipe de direction.",
            "effort": "Faible",
            "impact": "Fort"
        })
    if cat_cols and numeric_cols:
        wins.append({
            "icon": "⭐",
            "title": f"Segmenter vos clients par {cat_cols[0].replace('_',' ')}",
            "description": "Adaptez votre offre commerciale à chaque segment pour maximiser la conversion.",
            "effort": "Moyen",
            "impact": "Très fort"
        })
    wins.append({
        "icon": "🔔",
        "title": "Mettre en place des alertes automatiques",
        "description": "Soyez notifié dès qu'un KPI dépasse un seuil critique — avant qu'il ne soit trop tard.",
        "effort": "Faible",
        "impact": "Fort"
    })
    return wins


def _compute_health_score(df, warnings) -> int:
    score = 100
    null_avg = df.isnull().mean().mean()
    score -= int(null_avg * 50)
    score -= len(warnings) * 5
    return max(0, min(100, score))


async def _ai_business_analysis(session_id: str, df: pd.DataFrame, meta: dict, stat_opps: list) -> list:
    """Demande à l'IA des opportunités business que les stats n'ont pas vues."""
    try:
        from app.services.gemini_service import chat_with_gemini
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        stats = df[numeric_cols[:5]].describe().round(2).to_markdown() if numeric_cols else ""
        stat_summary = "\n".join(f"- {o['title']}" for o in stat_opps[:5])

        prompt = f"""Tu es un consultant business expert en croissance d'entreprise.
Analyse cette base de données et identifie des opportunités concrètes pour augmenter le chiffre d'affaires.

BASE: {meta['name']} — {meta['rows']:,} lignes
COLONNES NUMÉRIQUES: {', '.join(numeric_cols[:8])}
COLONNES CATÉGORIELLES: {', '.join(cat_cols[:6])}
STATISTIQUES:
{stats}

Opportunités déjà détectées automatiquement:
{stat_summary}

Génère 3 opportunités business NOUVELLES et CONCRÈTES que les stats n'ont pas vues.
Chaque opportunité doit avoir un impact financier estimé.

Réponds UNIQUEMENT en JSON:
[
  {{
    "icon": "💡",
    "title": "Titre court et percutant",
    "description": "Description en 1-2 phrases avec chiffres si possible",
    "action": "Action concrète à faire cette semaine",
    "impact_estimate": "Estimation financière ex: +15% de CA potentiel",
    "priority": "immediate|short_term|long_term"
  }}
]"""

        result = await chat_with_gemini(session_id, prompt, [])
        raw = result.get("answer", "[]")
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return []
