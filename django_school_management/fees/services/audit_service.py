import logging
from django_school_management.fees.models import FeeAuditLog

logger = logging.getLogger(__name__)


def log_fee_event(school, action: str, model_name: str, object_id, actor=None, before_state=None, after_state=None, ip_address=None):
    """
    Appends an immutable audit event to the financial audit log.
    """
    try:
        return FeeAuditLog.objects.create(
            school=school,
            actor=actor if actor and actor.is_authenticated else None,
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            before_state=before_state or {},
            after_state=after_state or {},
            ip_address=ip_address
        )
    except Exception as e:
        logger.exception("Failed to write fee audit log: %s", e)
        return None
