"""
PrimeSoul Core - API Conventions & Response Helpers
Standard JSON response envelopes and pagination classes for PrimeSoul REST endpoints.
"""
from typing import Any, Optional, Dict
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for PrimeSoul ERP APIs.
    Default page size: 25 items; max: 100 items.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def api_success(
    data: Any = None,
    message: str = "Operation completed successfully.",
    meta: Optional[Dict[str, Any]] = None,
    http_status: int = status.HTTP_200_OK
) -> Response:
    """
    Standard envelope for successful REST API operations.
    """
    payload = {
        'status': 'success',
        'message': message,
        'data': data if data is not None else {},
    }
    if meta:
        payload['meta'] = meta
    return Response(payload, status=http_status)


def api_error(
    message: str = "An error occurred while processing the request.",
    errors: Any = None,
    code: str = "ERROR",
    http_status: int = status.HTTP_400_BAD_REQUEST
) -> Response:
    """
    Standard envelope for API errors and validation failures.
    """
    payload = {
        'status': 'error',
        'code': code,
        'message': message,
        'errors': errors if errors is not None else [],
    }
    return Response(payload, status=http_status)
