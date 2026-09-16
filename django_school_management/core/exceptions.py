"""
PrimeSoul Core - Domain Exceptions
Standardized exception hierarchy for PrimeSoul School ERP.
"""

class PrimeSoulERPException(Exception):
    """Base exception for all domain logic failures in PrimeSoul ERP."""
    default_message = "An unexpected error occurred in PrimeSoul School ERP."

    def __init__(self, message: str = None, code: str = None):
        super().__init__(message or self.default_message)
        self.code = code or 'ERP_GENERAL_ERROR'


class TenantIsolationError(PrimeSoulERPException):
    """Raised when cross-tenant access violation or missing tenant context is detected."""
    default_message = "Cross-tenant access prohibited. Operation aborted."

    def __init__(self, message: str = None):
        super().__init__(message, code='CROSS_TENANT_VIOLATION')


class AcademicSessionClosedError(PrimeSoulERPException):
    """Raised when an operation attempts to mutate records in an archived academic session."""
    default_message = "Cannot modify records in a closed or inactive academic year."

    def __init__(self, message: str = None):
        super().__init__(message, code='ACADEMIC_SESSION_CLOSED')


class FinancialPeriodLockedError(PrimeSoulERPException):
    """Raised when an operation attempts to alter an audited or reconciled fee receipt."""
    default_message = "Receipt or transaction has been locked post-clearance."

    def __init__(self, message: str = None):
        super().__init__(message, code='FINANCIAL_PERIOD_LOCKED')
