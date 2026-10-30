import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def notify_upload_complete(recipient_email: str, user_id: int, uploaded_count: int) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    sender_email = os.getenv("SMTP_FROM_EMAIL")
    if not smtp_host or not sender_email:
        logger.error("Upload notification email is not configured; SMTP_HOST and SMTP_FROM_EMAIL are required")
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL must be configured to send upload notifications")

    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    if bool(username) != bool(password):
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must either both be configured or both be omitted")

    message = EmailMessage()
    message["Subject"] = "Your document upload is complete"
    message["From"] = sender_email
    message["To"] = recipient_email
    message.set_content(
        f"Hello,\n\nYour upload is complete. {uploaded_count} document(s) were uploaded.\n"
    )

    try:
        with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            if os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}:
                smtp.starttls(context=ssl.create_default_context())
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("Upload notification email delivery failed for user_id=%s", user_id)
        raise

    logger.info("Upload notification email sent for user_id=%s", user_id)