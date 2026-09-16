import uuid
from typing import Optional, Dict, Any, List
from .base import BaseNotificationProvider, ProviderResult


class MockNotificationProvider(BaseNotificationProvider):
    """
    In-memory mock notification provider for testing and development environments.
    """
    name: str = "MockProvider"

    sent_emails: List[Dict[str, Any]] = []
    sent_sms: List[Dict[str, Any]] = []
    sent_whatsapp: List[Dict[str, Any]] = []
    should_fail: bool = False
    failure_reason: str = "Simulated delivery network failure"

    @classmethod
    def reset(cls):
        """Clears sent history and resets mock failure toggles."""
        cls.sent_emails = []
        cls.sent_sms = []
        cls.sent_whatsapp = []
        cls.should_fail = False
        cls.failure_reason = "Simulated delivery network failure"

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[List[Any]] = None
    ) -> ProviderResult:
        if self.should_fail:
            return ProviderResult(
                success=False,
                status="FAILED",
                error_message=self.failure_reason
            )

        msg_id = f"mock-email-{uuid.uuid4().hex[:10]}"
        record = {
            "id": msg_id,
            "to_email": to_email,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text or body_html,
            "attachments": attachments or []
        }
        self.sent_emails.append(record)
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            status="DELIVERED",
            raw_response=record
        )

    def send_sms(
        self,
        to_phone: str,
        message: str,
        dlt_template_id: Optional[str] = None
    ) -> ProviderResult:
        if self.should_fail:
            return ProviderResult(
                success=False,
                status="FAILED",
                error_message=self.failure_reason
            )

        msg_id = f"mock-sms-{uuid.uuid4().hex[:10]}"
        record = {
            "id": msg_id,
            "to_phone": to_phone,
            "message": message,
            "dlt_template_id": dlt_template_id
        }
        self.sent_sms.append(record)
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            status="DELIVERED",
            raw_response=record
        )

    def send_whatsapp(
        self,
        to_phone: str,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None
    ) -> ProviderResult:
        if self.should_fail:
            return ProviderResult(
                success=False,
                status="FAILED",
                error_message=self.failure_reason
            )

        msg_id = f"mock-wa-{uuid.uuid4().hex[:10]}"
        record = {
            "id": msg_id,
            "to_phone": to_phone,
            "template_code": template_code,
            "variables": variables or {},
            "body": body or ""
        }
        self.sent_whatsapp.append(record)
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            status="DELIVERED",
            raw_response=record
        )
