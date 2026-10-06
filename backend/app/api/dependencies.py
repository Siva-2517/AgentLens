"""API dependencies for dependency injection."""

from typing import Optional

from fastapi import Header, HTTPException, status

from app.services.auth import auth_service


async def verify_api_key(
    authorization: Optional[str] = Header(None),
) -> str:
    """Verify API key from Authorization header.

    Args:
        authorization: Authorization header value.

    Returns:
        API key if valid.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = authorization[7:].strip()  # Remove "Bearer " prefix and whitespace

    if not api_key or not auth_service.validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key


async def get_project_name(
    x_agentlens_project: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract project name from header.

    Args:
        x_agentlens_project: Project name header.

    Returns:
        Project name if valid, None otherwise.
    """
    if not x_agentlens_project:
        return None

    return auth_service.extract_project_name(x_agentlens_project)
