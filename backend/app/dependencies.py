"""
DERTOUR FastAPI Dependencies
Shared FastAPI dependencies for DB session, current user, and role checks
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.core.security import verify_token
from app.core.config_loader import get_settings

# Security scheme for JWT tokens
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> dict:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Authorization credentials containing the JWT token
        
    Returns:
        dict: User data from token payload
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user data from payload
    user_data = {
        k: v for k, v in payload.items()
        if k not in ("exp", "iat", "type")
    }
    
    if not user_data.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_data


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get the current active user.
    
    Args:
        current_user: Current authenticated user data
        
    Returns:
        dict: User data
        
    Raises:
        HTTPException: If user is inactive
    """
    # Check if user is active (can be extended with database lookup)
    if current_user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact your administrator.",
        )
    
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Optional[dict]:
    """
    Get the current user if authenticated, otherwise return None.
    Useful for endpoints that work with or without authentication.
    
    Args:
        credentials: HTTP Authorization credentials containing the JWT token
        
    Returns:
        Optional[dict]: User data if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        return None
    
    return {
        k: v for k, v in payload.items()
        if k not in ("exp", "iat", "type")
    }


def require_roles(allowed_roles: list[str]):
    """
    Dependency factory to require specific roles.
    
    Args:
        allowed_roles: List of allowed role names
        
    Returns:
        Callable: Dependency function that validates user role
    """
    async def role_checker(
        current_user: dict = Depends(get_current_user),
        x_role: Optional[str] = Header(None, alias="X-Role")
    ) -> dict:
        """
        Check if the current user has one of the allowed roles.
        
        Args:
            current_user: Current authenticated user data
            x_role: Optional role header for additional validation
            
        Returns:
            dict: User data if authorized
            
        Raises:
            HTTPException: If user lacks required role
        """
        user_role = current_user.get("role", "VIEWER")
        
        # Validate against X-Role header if provided
        if x_role and x_role != user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role mismatch between token and header.",
            )
        
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}.",
            )
        
        return current_user
    
    return role_checker


# Predefined role requirements
require_admin = require_roles(["ADMIN", "EXECUTIVE"])
require_pmo = require_roles(["ADMIN", "EXECUTIVE", "PMO"])
require_team_lead = require_roles(["ADMIN", "EXECUTIVE", "PMO", "TEAM_LEAD"])
require_authenticated = require_roles(["ADMIN", "EXECUTIVE", "PMO", "TEAM_LEAD", "TEAM_MEMBER", "VIEWER"])


async def get_db_with_user(
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
) -> tuple[AsyncSession, dict]:
    """
    Get both database session and current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        tuple: (database session, current user data)
    """
    return db, current_user


# Export commonly used items
__all__ = [
    "security_scheme",
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
    "require_roles",
    "require_admin",
    "require_pmo",
    "require_team_lead",
    "require_authenticated",
    "get_db_with_user",
]
