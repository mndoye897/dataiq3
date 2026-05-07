from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.services.gemini_service import detect_anomalies
from app.services.db_loader import get_dataset, get_metadata

router = APIRouter()


@router.get("/{session_id}/anomalies")
async def anomalies(session_id: str):
    result = await detect_anomalies(session_id)
    return result


@router.get("/{session_id}/summary")
def summary(session_id: str):
    meta = get_metadata(session_id)
    df = get_dataset(session_id)
    if df is None:
        raise HTTPException(404, "Session introuvable")

    numeric = df.select_dtypes(include="number")
    cat = df.select_dtypes(include="object")

    return {
        "metadata": meta,
        "numeric_summary": numeric.describe().round(2).to_dict() if not numeric.empty else {},
        "categorical_summary": {
            col: df[col].value_counts().head(5).to_dict()
            for col in cat.columns[:10]
        },
        "correlations": numeric.corr().round(3).to_dict() if len(numeric.columns) > 1 else {},
    }


@router.get("/{session_id}/export/csv")
def export_csv(session_id: str):
    df = get_dataset(session_id)
    if df is None:
        raise HTTPException(404, "Session introuvable")
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=dataiq_export_{session_id}.csv"},
    )
