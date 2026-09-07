"""
Domain exceptions. Views/serializers ko DB errors nahi dikhte -
service layer meaningful error uthata hai, ek handler use HTTP me map karta hai.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "domain_error"

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context


class PermissionDenied(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class InvalidTransition(DomainError):
    code = "invalid_transition"


class BudgetExceeded(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "budget_exceeded"


def domain_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, **exc.context}},
            status=exc.status_code,
        )
    return drf_exception_handler(exc, context)
