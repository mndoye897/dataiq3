import asyncio
import json
import smtplib
import threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from app.services.db_loader import get_dataset, get_metadata

# In-memory store for scheduled reports
_reports: dict[str, dict] = {}
_scheduler_running = False


def create_report(report_id: str, config: dict):
    """Register a new scheduled report."""
    _reports[report_id] = {
        **config,
        "id": report_id,
        "created_at": datetime.now().isoformat(),
        "last_run": None,
        "next_run": _compute_next_run(config["frequency"]),
        "status": "active",
        "history": []
    }
    return _reports[report_id]


def list_reports() -> list:
    return list(_reports.values())


def delete_report(report_id: str) -> bool:
    if report_id in _reports:
        del _reports[report_id]
        return True
    return False


def get_report(report_id: str) -> Optional[dict]:
    return _reports.get(report_id)


def _compute_next_run(frequency: str) -> str:
    now = datetime.now()
    if frequency == "daily":
        next_run = now.replace(hour=8, minute=0, second=0) + timedelta(days=1)
    elif frequency == "weekly":
        days_ahead = 7 - now.weekday()
        next_run = (now + timedelta(days=days_ahead)).replace(hour=8, minute=0, second=0)
    elif frequency == "monthly":
        if now.month == 12:
            next_run = now.replace(year=now.year+1, month=1, day=1, hour=8, minute=0, second=0)
        else:
            next_run = now.replace(month=now.month+1, day=1, hour=8, minute=0, second=0)
    else:
        next_run = now + timedelta(hours=1)
    return next_run.isoformat()


async def generate_report_content(session_id: str, questions: list[str]) -> dict:
    """Generate AI analysis for each question and compile into a report."""
    from app.services.gemini_service import chat_with_gemini
    from app.utils.chart_builder import build_chart_spec

    meta = get_metadata(session_id)
    if not meta:
        return {"error": "Session introuvable"}

    sections = []
    for question in questions:
        try:
            result = await chat_with_gemini(session_id, question, [])
            sections.append({
                "question": question,
                "answer": result.get("answer", ""),
                "sql": result.get("sql"),
                "insights": result.get("insights", []),
                "chart": result.get("chart"),
            })
        except Exception as e:
            sections.append({"question": question, "answer": f"Erreur: {str(e)}", "sql": None, "insights": [], "chart": None})

    return {
        "database": meta["name"],
        "rows": meta["rows"],
        "generated_at": datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "sections": sections
    }


def build_email_html(report_name: str, content: dict) -> str:
    sections_html = ""
    for i, section in enumerate(content.get("sections", [])):
        insights_html = "".join(
            f'<li style="margin:6px 0;color:#444;">{ins}</li>'
            for ins in section.get("insights", [])
        )
        sql_html = f"""
        <div style="background:#1a1a2a;border-radius:8px;padding:14px;margin-top:12px;overflow-x:auto;">
          <div style="font-family:monospace;font-size:12px;color:#a78bfa;margin-bottom:6px;letter-spacing:1px;">SQL GÉNÉRÉ</div>
          <pre style="font-family:'Courier New',monospace;font-size:12px;color:#e2e8f0;margin:0;white-space:pre-wrap;">{section.get('sql','')}</pre>
        </div>""" if section.get("sql") and section["sql"] != "null" else ""

        sections_html += f"""
        <div style="background:#fff;border:1px solid #e8e3dd;border-radius:12px;padding:24px;margin-bottom:20px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
            <div style="width:28px;height:28px;background:#0a0a0f;border-radius:7px;display:flex;align-items:center;justify-content:center;color:#c9a84c;font-weight:bold;font-size:13px;">{i+1}</div>
            <div style="font-size:14px;font-weight:600;color:#0a0a0f;">{section['question']}</div>
          </div>
          <p style="font-size:14px;color:#444;line-height:1.7;margin:0 0 12px;">{section['answer']}</p>
          {f'<ul style="margin:0 0 12px;padding-left:20px;">{insights_html}</ul>' if insights_html else ''}
          {sql_html}
        </div>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f3ef;font-family:'Outfit',Arial,sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:32px 20px;">

    <!-- Header -->
    <div style="background:#0a0a0f;border-radius:16px;padding:28px 32px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:24px;font-weight:700;color:#fff;">Data<span style="color:#c9a84c;">IQ</span></div>
        <div style="font-size:11px;color:rgba(255,255,255,0.4);letter-spacing:2px;text-transform:uppercase;margin-top:4px;">Rapport Automatique</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:13px;color:#c9a84c;font-weight:600;">{report_name}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.4);margin-top:4px;">{content['generated_at']}</div>
      </div>
    </div>

    <!-- Stats bar -->
    <div style="background:#fff;border:1px solid #e8e3dd;border-radius:12px;padding:16px 24px;margin-bottom:24px;display:flex;gap:32px;">
      <div><div style="font-size:10px;color:#6b6880;letter-spacing:1px;text-transform:uppercase;">Base</div><div style="font-size:14px;font-weight:600;color:#0a0a0f;margin-top:2px;">{content['database']}</div></div>
      <div><div style="font-size:10px;color:#6b6880;letter-spacing:1px;text-transform:uppercase;">Lignes analysées</div><div style="font-size:14px;font-weight:600;color:#0a0a0f;margin-top:2px;">{content['rows']:,}</div></div>
      <div><div style="font-size:10px;color:#6b6880;letter-spacing:1px;text-transform:uppercase;">Sections</div><div style="font-size:14px;font-weight:600;color:#0a0a0f;margin-top:2px;">{len(content['sections'])}</div></div>
    </div>

    <!-- Sections -->
    {sections_html}

    <!-- Footer -->
    <div style="text-align:center;padding:20px;font-size:11px;color:#6b6880;">
      Généré automatiquement par DataIQ Enterprise · {content['generated_at']}
    </div>
  </div>
</body>
</html>"""


def send_email(smtp_config: dict, to_emails: list[str], subject: str, html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_config["from_email"]
        msg["To"] = ", ".join(to_emails)
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            server.sendmail(smtp_config["from_email"], to_emails, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def start_scheduler():
    """Background thread that checks and runs due reports."""
    global _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True

    def _run():
        while _scheduler_running:
            now = datetime.now()
            for report_id, report in list(_reports.items()):
                if report["status"] != "active":
                    continue
                next_run = datetime.fromisoformat(report["next_run"])
                if now >= next_run:
                    asyncio.run(_execute_report(report_id))
            import time
            time.sleep(60)  # check every minute

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


async def _execute_report(report_id: str):
    report = _reports.get(report_id)
    if not report:
        return
    try:
        content = await generate_report_content(report["session_id"], report["questions"])
        html = build_email_html(report["name"], content)
        success = send_email(report["smtp_config"], report["recipients"], f"📊 {report['name']} — {datetime.now().strftime('%d/%m/%Y')}", html)
        _reports[report_id]["last_run"] = datetime.now().isoformat()
        _reports[report_id]["next_run"] = _compute_next_run(report["frequency"])
        _reports[report_id]["history"].append({"date": datetime.now().isoformat(), "status": "sent" if success else "failed"})
    except Exception as e:
        _reports[report_id]["history"].append({"date": datetime.now().isoformat(), "status": "error", "message": str(e)})
