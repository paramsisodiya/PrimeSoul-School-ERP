from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class ProviderResult:
    """
    Standard result returned by any notification provider.
    """
    success: bool
    provider_message_id: str = ""
    status: str = "SENT"  # 'SENT', 'DELIVERED', 'FAILED'
    error_message: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


class BaseNotificationProvider(ABC):
    """
    Provider abstraction interface for multi-channel communication dispatch.
    """
    name: str = "BaseProvider"

    @abstractmethod
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[List[Any]] = None
    ) -> ProviderResult:
        """Dispatches an email notification."""
        pass

    @abstractmethod
    def send_sms(
        self,
        to_phone: str,
        message: str,
        dlt_template_id: Optional[str] = None
    ) -> ProviderResult:
        """Dispatches an SMS notification."""
        pass

    @abstractmethod
    def send_whatsapp(
        self,
        to_phone: str,
        template_code: str,
        variables: Optional[Dict[str, Any]] = None,
        body: Optional[str] = None
    ) -> ProviderResult:
        """Dispatches a WhatsApp message notification."""
        pass
