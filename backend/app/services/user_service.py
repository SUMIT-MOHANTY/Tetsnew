"""
DERTOUR User Service Module
Service layer for user CRUD operations with password hashing
"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserFilterParams
from app.core.security import get_password_hash, verify_password


class UserService:
    """
    Service class for user management operations.
    
    Handles CRUD operations, authentication, and user-related business logic.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the user service.
        
        Args:
            db: Async SQLAlchemy session
        """
        self.db = db
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            User instance if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address.
        
        Args:
            email: The user's email address
            
        Returns:
            User instance if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()
    
    async def get_by_email_with_password(self, email: str) -> Optional[User]:
        """
        Get a user by email including password hash (for authentication).
        
        Args:
            email: The user's email address
            
        Returns:
            User instance if found, None otherwise
        """
        # Same as get_by_email - password is always loaded
        return await self.get_by_email(email)
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            email: The user's email address
            password: The plain text password
            
        Returns:
            User instance if authentication succeeds, None otherwise
        """
        user = await self.get_by_email_with_password(email)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        # User model has 'hashed_password' field - verify against the stored hash
        if not verify_password(password, user.hashed_password):
            return None
        
        # Update last login timestamp
        user.last_login_at = datetime.utcnow()
        await self.db.commit()
        
        return user
    
    async def create(self, user_data: UserCreate) -> User:
        """
        Create a new user.
        
        Args:
            user_data: User creation data including password
            
        Returns:
            Created User instance
            
        Raises:
            ValueError: If email already exists
        """
        # Check if email already exists
        existing = await self.get_by_email(user_data.email)
        if existing:
            raise ValueError(f"User with email '{user_data.email}' already exists")
        
        # Hash the password - UserCreate has 'password' field
        hashed_password = get_password_hash(user_data.password)
        
        # Create user instance - User model has 'hashed_password' field
        user = User(
            email=user_data.email.lower().strip(),
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role.value,
            is_active=user_data.is_active,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def update(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        """
        Update an existing user.
        
        Args:
            user_id: The user's UUID
            user_data: User update data (all fields optional)
            
        Returns:
            Updated User instance if found, None otherwise
            
        Raises:
            ValueError: If email already exists by another user
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        # Update email if provided
        if user_data.email is not None:
            # Check if email is already used by another user
            existing = await self.get_by_email(user_data.email)
            if existing and existing.id != user_id:
                raise ValueError(f"Email '{user_data.email}' is already in use")
            user.email = user_data.email.lower().strip()
        
        # Update full_name if provided
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        
        # Update role if provided
        if user_data.role is not None:
            user.role = user_data.role.value
        
        # Update is_active if provided
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        
        # Update password if provided - UserUpdate has 'password' field, User model has 'hashed_password'
        if user_data.password is not None:
            user.hashed_password = get_password_hash(user_data.password)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def delete(self, user_id: str) -> bool:
        """
        Delete a user by ID.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            True if user was deleted, False if not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        await self.db.delete(user)
        await self.db.commit()
        
        return True
    
    async def list_users(
        self,
        filters: Optional[UserFilterParams] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[User], int]:
        """
        List users with optional filtering and pagination.
        
        Args:
            filters: Optional filter parameters
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of users, total count)
        """
        # Build base query
        query = select(User)
        count_query = select(func.count(User.id))
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            # Filter by role
            if filters.role is not None:
                conditions.append(User.role == filters.role.value)
            
            # Filter by active status
            if filters.is_active is not None:
                conditions.append(User.is_active == filters.is_active)
            
            # Search in email and full_name
            if filters.search:
                search_term = f"%{filters.search}%"
                conditions.append(
                    or_(
                        User.email.ilike(search_term),
                        User.full_name.ilike(search_term)
                    )
                )
            
            # Apply conditions to queries
            if conditions:
                where_clause = and_(*conditions)
                query = query.where(where_clause)
                count_query = count_query.where(where_clause)
        
        # Get total count
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        # Apply pagination and execute query
        query = query.offset(skip).limit(limit)
        query = query.order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return list(users), total
    
    async def count_users(self) -> int:
        """
        Get total count of users.
        
        Returns:
            Total number of users
        """
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar()
    
    async def count_active_users(self) -> int:
        """
        Get count of active users.
        
        Returns:
            Number of active users
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        return result.scalar()
    
    async def count_by_role(self, role: UserRole) -> int:
        """
        Get count of users with a specific role.
        
        Args:
            role: The role to count
            
        Returns:
            Number of users with the specified role
        """
        result = await self.db.execute(
            select(func.count(User.id)).where(User.role == role.value)
        )
        return result.scalar()
    
    async def deactivate_user(self, user_id: str) -> Optional[User]:
        """
        Deactivate a user account.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Updated User instance if found, None otherwise
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        user.is_active = False
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def activate_user(self, user_id: str) -> Optional[User]:
        """
        Activate a user account.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            Updated User instance if found, None otherwise
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        user.is_active = True
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> bool:
        """
        Change a user's password.
        
        Args:
            user_id: The user's UUID
            current_password: The current password for verification
            new_password: The new password to set
            
        Returns:
            True if password was changed, False if current password is incorrect
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        # Verify current password - User model has 'hashed_password' field
        if not verify_password(current_password, user.hashed_password):
            return False
        
        # Set new password - User model has 'hashed_password' field
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        
        return True


# Factory function for dependency injection
def get_user_service(db: AsyncSession) -> UserService:
    """
    Factory function to create a UserService instance.
    
    Args:
        db: Async SQLAlchemy session
        
    Returns:
        UserService instance
    """
    return UserService(db)


# Export commonly used items
__all__ = [
    "UserService",
    "get_user_service",
]
