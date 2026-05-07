from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid, asyncio
from app.services import report_service

router = APIRouter()


class SMTPConfig(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str
    password: str
    from_email: str


class ReportCreate(BaseModel):
    name: str
    session_id: str
    frequency: str  # daily | weekly | monthly
    recipients: list[str]
    questions: list[str]
    smtp_config: SMTPConfig


@router.post("/")
async def create_report(data: ReportCreate):
    report_id = str(uuid.uuid4())
    report = report_service.create_report(report_id, data.model_dump())
    return {"report_id": report_id, "report": report}


@router.get("/")
def list_reports():
    return {"reports": report_service.list_reports()}


@router.delete("/{report_id}")
def delete_report(report_id: str):
    if not report_service.delete_report(report_id):
        raise HTTPException(404, "Rapport introuvable")
    return {"deleted": True}


@router.post("/{report_id}/run-now")
async def run_now(report_id: str, background_tasks: BackgroundTasks):
    """Trigger a report immediately for testing."""
    report = report_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Rapport introuvable")
    background_tasks.add_task(report_service._execute_report, report_id)
    return {"message": "Rapport en cours de génération, email envoyé dans quelques secondes"}


@router.post("/preview")
async def preview_report(data: ReportCreate):
    """Generate report content without sending email — returns HTML."""
    content = await report_service.generate_report_content(data.session_id, data.questions)
    html = report_service.build_email_html(data.name, content)
    return {"html": html, "content": content}
