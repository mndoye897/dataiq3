from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.services.proactive_engine import analyze_business_opportunities, get_opportunities

router = APIRouter()

@router.post("/{session_id}/analyze")
async def trigger_analysis(session_id: str, background_tasks: BackgroundTasks):
    """Lance l'analyse proactive en arrière-plan."""
    background_tasks.add_task(analyze_business_opportunities, session_id)
    return {"status": "analysis_started"}

@router.get("/{session_id}")
async def get_analysis(session_id: str):
    """Récupère les opportunités déjà analysées."""
    result = get_opportunities(session_id)
    if not result:
        # Lance l'analyse si pas encore faite
        result = await analyze_business_opportunities(session_id)
    return result
