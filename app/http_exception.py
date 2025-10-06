from fastapi import HTTPException, status
from fastapi.responses import ORJSONResponse
from loguru import logger
from starlette.requests import Request


async def http_error_handler(request: Request, exc: HTTPException) -> ORJSONResponse:
    logger.error(exc.detail)
    print(f"HTTP Exception: {exc.detail} - Status Code: {exc.status_code}")
    return ORJSONResponse({"message": exc.detail}, status_code=exc.status_code)


class CredentialsInvalidException(HTTPException):
    """
    Exception raised when credentials provided by the user are invalid.
    """

    def __init__(self, detail: str = "Invalid credentials provided."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidPasswordException(HTTPException):
    """
    Exception raised when the password provided by the user is invalid.
    """

    def __init__(self, detail: str = "Invalid password provided."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class ResourceNotFoundException(HTTPException):
    """
    Exception raised when a requested resource is not found.
    """

    def __init__(self, detail: str = "Resource not found."):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ResourceConflictException(HTTPException):
    """
    Exception raised when there is a conflict with the requested resource.
    """

    def __init__(self, detail: str = "Resource Conflict."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class OperationNotAllowedException(HTTPException):
    """
    Exception raised when the requested operation cannot be performed like when an item cannot be deleted since its associated with other items.
    """

    def __init__(self, detail: str = "Requested Operation cannot be performed."):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class InternalServerErrorException(HTTPException):
    """
    Exception raised when an internal server error occurs.
    """

    def __init__(self, detail: str = "Internal Server Error."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


class BadRequestException(HTTPException):
    """
    Exception raised when the client's request is malformed.
    """

    def __init__(self, detail: str = "Bad request."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class ForbiddenException(HTTPException):
    """
    Exception raised when the server understands the request but refuses to authorize it.
    """

    def __init__(self, detail: str = "Forbidden."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class InvalidSubscription(HTTPException):
    """
    Exception raised when the subscription is not found or is invalid.
    """

    def __init__(self, detail: str = "Invalid Subscription."):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
        )


class UnknownDeviceException(HTTPException):
    """
    Exception raised when the user tries to loggen in from unknown device.
    """

    def __init__(
        self,
        detail="Unknown or unsecured device.",
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class AlreadyVerifiedException(HTTPException):
    """
    Exception raised when the user tries to verify an already verified email.
    """

    def __init__(
        self,
        detail="Email is already verified.",
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

class ValidationException(HTTPException):
    """
    Exception raised when the input data does not pass validation checks.
    """

    def __init__(self, detail: str = "Validation error."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )

class DuplicateKeyException(HTTPException):
    """
    Exception raised when a duplicate key error occurs.
    """

    def __init__(self, detail: str = "Entry with given key/name already exists."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ServiceUnavailableException(HTTPException):
    """
    Exception raised when a service is unavailable.
    """

    def __init__(self, detail: str = "Service is unavailable."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )