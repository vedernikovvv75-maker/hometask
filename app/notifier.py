import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


class NotificationError(Exception):
    pass


class LeadNotifier:
    def __init__(
        self,
        mode: str,
        events_log_path: Path,
        manager_email: str = "",
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_username: str = "",
        smtp_password: str = "",
        smtp_use_tls: bool = True,
        from_email: str = "",
    ):
        self.mode = mode.lower().strip()
        self.events_log_path = events_log_path
        self.manager_email = manager_email
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.from_email = from_email

        self.events_log_path.parent.mkdir(parents=True, exist_ok=True)

    def email_config_ready(self) -> bool:
        required = [
            self.manager_email,
            self.smtp_host,
            self.smtp_username,
            self.smtp_password,
            self.from_email,
        ]
        return all(required)

    def notify_new_lead(self, lead_id: int, lead: dict) -> None:
        if self.mode == "fail":
            raise NotificationError(
                "NOTIFICATION_MODE=fail: notification skipped on purpose "
                "(no email, no event log line for this notify call)"
            )

        if self.mode == "email":
            self._send_email(lead_id=lead_id, lead=lead)
            return

        # Default mode is event log for maximum local reliability.
        self._append_event(f"New lead saved: {lead_id}")

    def _append_event(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.events_log_path.open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} | {message}\n")

    def _send_email(self, lead_id: int, lead: dict) -> None:
        if not self.email_config_ready():
            raise NotificationError(
                "Email mode selected, but SMTP or email settings are incomplete"
            )

        message = EmailMessage()
        message["Subject"] = f"Новая заявка #{lead_id}"
        message["From"] = self.from_email
        message["To"] = self.manager_email
        message.set_content(
            "Получена новая заявка:\n"
            f"id: {lead_id}\n"
            f"name: {lead.get('name', '')}\n"
            f"contact: {lead.get('contact', '')}\n"
            f"source: {lead.get('source', '')}\n"
            f"comment: {lead.get('comment', '')}\n"
        )

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
        except Exception as exc:
            raise NotificationError(str(exc)) from exc
