"""
DERTOUR Base Models Module
SQLAlchemy 2.0 DeclarativeBase with timestamp mixins and JSON serialization helpers
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """
    SQLAlchemy 2.0 DeclarativeBase with async support.
    
    All models should inherit from this base class.
    Provides JSON serialization capabilities for API responses.
    """
    
    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude: List of attribute names to exclude from the result
            
        Returns:
            Dictionary representation of the model
        """
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
                
            value = getattr(self, column.name)
            
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            
            result[column.name] = value
            
        return result
    
    def to_json(self, exclude: Optional[List[str]] = None, indent: Optional[int] = None) -> str:
        """
        Convert model instance to JSON string.
        
        Args:
            exclude: List of attribute names to exclude from the result
            indent: JSON indentation level for pretty printing
            
        Returns:
            JSON string representation of the model
        """
        return json.dumps(self.to_dict(exclude=exclude), indent=indent, default=str)
    
    def __repr__(self) -> str:
        """String representation of the model instance."""
        columns = [f"{col.name}={getattr(self, col.name)!r}" for col in self.__table__.columns]
        return f"<{self.__class__.__name__}({', '.join(columns)})>"


class TimestampMixin:
    """
    Mixin class that adds created_at and updated_at timestamp columns.
    
    Automatically tracks when records are created and last modified.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when the record was last updated"
    )


class UUIDMixin:
    """
    Mixin class that adds a UUID primary key column.
    
    Uses UUID v4 for globally unique identifiers.
    """
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique identifier (UUID v4)"
    )


class SoftDeleteMixin:
    """
    Mixin class that adds soft delete functionality.
    
    Records are marked as deleted rather than physically removed.
    """
    
    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Soft delete flag - True if record is logically deleted"
    )
    
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the record was soft deleted"
    )


class AuditMixin(TimestampMixin):
    """
    Mixin class that adds comprehensive audit tracking.
    
    Combines timestamp tracking with created_by and updated_by fields.
    """
    
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="User ID who created this record"
    )
    
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="User ID who last updated this record"
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Abstract base model combining UUID primary key and timestamp tracking.
    
    Most models should inherit from this class for consistent
    primary key and timestamp behavior.
    """
    
    __abstract__ = True
    
    def __init__(self, **kwargs):
        """Initialize with automatic UUID generation if not provided."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid4())
        super().__init__(**kwargs)


class AuditableModel(Base, UUIDMixin, AuditMixin):
    """
    Abstract base model with full audit trail support.
    
    Includes UUID primary key, timestamps, and user tracking.
    Use for models requiring complete audit history.
    """
    
    __abstract__ = True


# Export commonly used items
__all__ = [
    "Base",
    "BaseModel",
    "AuditableModel",
    "TimestampMixin",
    "UUIDMixin",
    "SoftDeleteMixin",
    "AuditMixin",
]
