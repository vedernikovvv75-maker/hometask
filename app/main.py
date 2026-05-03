import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.requests import Request

try:
    from app.notifier import LeadNotifier, NotificationError
    from app.storage import LeadStorage, StorageUnavailableError
except ModuleNotFoundError:
    # Allows direct execution via `python app/main.py`.
    from notifier import LeadNotifier, NotificationError
    from storage import LeadStorage, StorageUnavailableError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

APP_LOG_PATH = LOGS_DIR / "app.log"
EVENTS_LOG_PATH = LOGS_DIR / "events.log"
DB_PATH = BASE_DIR / "data" / "leads.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(APP_LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger("lead_intake")


class LeadIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact: str = Field(..., min_length=1, max_length=255)
    source: str = Field(..., min_length=1, max_length=100)
    comment: str = Field(..., min_length=1, max_length=2000)


class LeadOut(BaseModel):
    status: str = Field(..., description="Always \"ok\" on success")
    lead_id: int = Field(..., description="SQLite row id of the saved lead")


storage: LeadStorage | None = None
notifier: LeadNotifier | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global storage, notifier
    try:
        notification_mode = os.getenv("NOTIFICATION_MODE", "event_log")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

        storage = LeadStorage(db_path=DB_PATH)
        notifier = LeadNotifier(
            mode=notification_mode,
            events_log_path=EVENTS_LOG_PATH,
            manager_email=os.getenv("MANAGER_EMAIL", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=smtp_port,
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=smtp_use_tls,
            from_email=os.getenv("FROM_EMAIL", ""),
        )
        if notifier.mode == "email" and not notifier.email_config_ready():
            logger.warning(
                "NOTIFICATION_MODE=email but MANAGER_EMAIL / SMTP_* / FROM_EMAIL are incomplete; "
                "falling back to event_log until SMTP is configured."
            )
            notifier.mode = "event_log"
        storage.init_db()
        logger.info("Service started with notification mode: %s", notifier.mode)
        yield
    finally:
        logger.info("Service stopped")


app = FastAPI(title="Lead Intake MVP", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    _ = request
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid request payload",
            "details": exc.errors(),
        },
    )


@app.post("/lead", response_model=LeadOut)
async def create_lead(payload: LeadIn) -> LeadOut:
    if storage is None or notifier is None:
        logger.error("Storage or notifier is not initialized")
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        lead_data = payload.model_dump()
        lead_id = storage.save_lead(lead_data)
        notifier.notify_new_lead(lead_id=lead_id, lead=lead_data)
    except StorageUnavailableError as exc:
        logger.exception("Database unavailable: %s", exc)
        raise HTTPException(status_code=500, detail="Database unavailable") from exc
    except NotificationError as exc:
        logger.exception("Notification failed: %s", exc)
        raise HTTPException(status_code=500, detail="Notification failed") from exc
    except Exception as exc:
        logger.exception("Unexpected storage error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    return LeadOut(status="ok", lead_id=lead_id)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, reload=False)
