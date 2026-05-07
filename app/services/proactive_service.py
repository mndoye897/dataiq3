import asyncio
import threading
import httpx
from datetime import datetime, timedelta
from app.services.db_loader import get_dataset, get_metadata
from app.services.gemini_service import chat_with_gemini

# ── WhatsApp via CallMeBot (gratuit) ou Twilio ──
# Store des analyses planifiées
_proactive_configs: dict[str, dict] = {}
_scheduler_running = False


ANALYSIS_PROMPTS = [
    "Identifie les 3 plus grandes opportunités de croissance du chiffre d'affaires dans ces données. Sois très concret avec des chiffres.",
    "Détecte les anomalies ou problèmes urgents qui font perdre de l'argent à l'entreprise en ce moment.",
    "Quels clients ou segments sont sur le point d'être perdus ? Donne des actions concrètes immédiates.",
    "Identifie les produits ou services les plus rentables et ceux qui drainent les ressources.",
    "Quelle est la tendance des 30 derniers jours ? Est-ce que l'entreprise est en croissance ou en déclin ?",
    "Y a-t-il des patterns inhabituels dans les données qui méritent attention immédiate du dirigeant ?",
]


def register_proactive(session_id: str, config: dict):
    """Register a session for proactive analysis."""
    _proactive_configs[session_id] = {
        **config,
        "session_id": session_id,
        "last_run": None,
        "interval_hours": config.get("interval_hours", 6),
        "whatsapp_number": config.get("whatsapp_number", ""),
        "whatsapp_method": config.get("whatsapp_method", "callmebot"),
        "callmebot_apikey": config.get("callmebot_apikey", ""),
        "twilio_sid": config.get("twilio_sid", ""),
        "twilio_token": config.get("twilio_token", ""),
        "twilio_from": config.get("twilio_from", ""),
        "company_name": config.get("company_name", "votre entreprise"),
        "active": True,
    }
    return _proactive_configs[session_id]


def list_proactive() -> list:
    return list(_proactive_configs.values())


def delete_proactive(session_id: str):
    _proactive_configs.pop(session_id, None)


async def run_proactive_analysis(session_id: str) -> dict:
    """Run AI analysis and generate WhatsApp message."""
    df = get_dataset(session_id)
    meta = get_metadata(session_id)
    config = _proactive_configs.get(session_id)
    if df is None or not config:
        return {"error": "Session introuvable"}

    # Pick a different prompt each run for variety
    import random
    prompt = random.choice(ANALYSIS_PROMPTS)

    result = await chat_with_gemini(session_id, prompt, [])

    # Build WhatsApp message — short, punchy, actionable
    now = datetime.now().strftime("%d/%m %H:%M")
    company = config.get("company_name", "votre entreprise")

    msg = f"📊 *DataIQ · {company}*\n_{now}_\n\n"
    msg += f"{result.get('answer','')}\n\n"

    insights = result.get("insights", [])
    if insights:
        msg += "*Points clés :*\n"
        for ins in insights[:3]:
            msg += f"• {ins}\n"

    sql = result.get("sql")
    if sql and sql != "null":
        msg += f"\n💡 _Requête disponible sur DataIQ_"

    msg += f"\n\n_Prochaine analyse dans {config['interval_hours']}h_"

    return {
        "message": msg,
        "analysis": result,
        "session_id": session_id
    }


async def send_whatsapp_callmebot(phone: str, apikey: str, message: str) -> bool:
    """Send WhatsApp via CallMeBot (free)."""
    try:
        import urllib.parse
        encoded = urllib.parse.quote(message)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={apikey}"
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url)
            return res.status_code == 200
    except Exception as e:
        print(f"CallMeBot error: {e}")
        return False


async def send_whatsapp_twilio(sid: str, token: str, from_number: str, to_number: str, message: str) -> bool:
    """Send WhatsApp via Twilio."""
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "From": f"whatsapp:{from_number}",
            "To": f"whatsapp:{to_number}",
            "Body": message
        }
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(url, data=data, auth=(sid, token))
            return res.status_code == 201
    except Exception as e:
        print(f"Twilio error: {e}")
        return False


async def execute_proactive(session_id: str) -> dict:
    """Run analysis and send WhatsApp."""
    config = _proactive_configs.get(session_id)
    if not config:
        return {"error": "Config introuvable"}

    try:
        result = await run_proactive_analysis(session_id)
        message = result.get("message", "")
        sent = False

        if config["whatsapp_method"] == "callmebot" and config.get("callmebot_apikey"):
            sent = await send_whatsapp_callmebot(
                config["whatsapp_number"],
                config["callmebot_apikey"],
                message
            )
        elif config["whatsapp_method"] == "twilio":
            sent = await send_whatsapp_twilio(
                config["twilio_sid"],
                config["twilio_token"],
                config["twilio_from"],
                config["whatsapp_number"],
                message
            )

        _proactive_configs[session_id]["last_run"] = datetime.now().isoformat()

        return {
            "sent": sent,
            "message": message,
            "analysis": result.get("analysis", {})
        }
    except Exception as e:
        return {"error": str(e), "sent": False}


def start_proactive_scheduler():
    """Background scheduler for proactive analysis."""
    global _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True

    def _run():
        while _scheduler_running:
            now = datetime.now()
            for session_id, config in list(_proactive_configs.items()):
                if not config.get("active"):
                    continue
                last = config.get("last_run")
                interval_h = config.get("interval_hours", 6)
                if last is None:
                    should_run = True
                else:
                    last_dt = datetime.fromisoformat(last)
                    should_run = (now - last_dt).total_seconds() >= interval_h * 3600
                if should_run:
                    asyncio.run(execute_proactive(session_id))
            import time
            time.sleep(300)  # check every 5 minutes

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
