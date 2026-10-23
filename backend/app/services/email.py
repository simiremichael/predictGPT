"""Gmail SMTP email sender powered by FastAPI-Mail."""
from __future__ import annotations

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from core.config import get_settings


async def send_email(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.gmail_username or not settings.gmail_app_password:
        raise RuntimeError("GMAIL_USERNAME and GMAIL_APP_PASSWORD must be configured")

    sender = settings.gmail_from_email or settings.gmail_username
    connection = ConnectionConfig(
        MAIL_USERNAME=settings.gmail_username,
        MAIL_PASSWORD=settings.gmail_app_password,
        MAIL_FROM=sender,
        MAIL_PORT=587,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.plain,
    )
    await FastMail(connection).send_message(message)
