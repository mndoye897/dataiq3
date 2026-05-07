from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.gemini_service import chat_with_gemini

router = APIRouter()

# Simple in-memory conversation history (use Redis/DB for production)
_histories: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    sql: str | None
    chart: dict | None
    insights: list[str]
    follow_up_questions: list[str]


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.session_id not in _histories:
        _histories[req.session_id] = []

    history = _histories[req.session_id]

    result = await chat_with_gemini(req.session_id, req.message, history)

    # Save to history
    history.append({"role": "user", "content": req.message})
    history.append({"role": "model", "content": result.get("answer", "")})

    return ChatResponse(
        answer=result.get("answer", ""),
        sql=result.get("sql"),
        chart=result.get("chart"),
        insights=result.get("insights", []),
        follow_up_questions=result.get("follow_up_questions", []),
    )


@router.delete("/{session_id}/history")
def clear_history(session_id: str):
    _histories.pop(session_id, None)
    return {"cleared": True}
