import uuid
import logging
from typing import Optional, Dict, Any, List
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .base import BaseNotificationProvider, ProviderResult

logger = logging.getLogger(__name__)


class DjangoEmailProvider(BaseNotificationProvider):
    """
    Standard Django email provider for SMTP / Console / In-memory test backend.
    """
    name: str = "DjangoEmailProvider"

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[List[Any]] = None
    ) -> ProviderResult:
        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@primesoul.edu')
            text_content = body_text or body_html
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email]
            )
            if body_html and body_html != text_content:
                msg.attach_alternative(body_html, "text/html")

            if attachments:
                for att in attachments:
                    if isinstance(att, tuple) and len(att) == 3:
                        msg.attach(*att)

            msg.send(fail_silently=False)
            msg_id = f"email-{uuid.uuid4().hex[:12]}"
            return ProviderResult(
                success=True,
                provider_message_id=msg_id,
                status="SENT"
            )
        except Exception as e:
            logger.error(f"DjangoEmailProvider failed to send email to {to_email}: {e}")
            return ProviderResult(
                success=False,
                status="FAILED",
                error_message=str(e)
            )

    def send_sms(
        self,
        to_phone: str,
        message: str,
        dlt_template_id: Optional[str] = None
    ) -> ProviderResult:
        return ProviderResult(
            success=False,
            status="FAILED",
            error_message="SMS not supported by DjangoEmailProvider"
        )

    def send_whatsapp(
        self,
        to_phone: str,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None
    ) -> ProviderResult:
        return ProviderResult(
            success=False,
            status="FAILED",
            error_message="WhatsApp not supported by DjangoEmailProvider"
        )
