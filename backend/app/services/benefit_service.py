"""
DERTOUR Benefit Service Module
Service layer for benefit CRUD operations and business logic
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import uuid4

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benefit import Benefit, BenefitStatus, BenefitType
from app.schemas.benefit import (
    BenefitCreate, BenefitUpdate, BenefitResponse, BenefitListItem,
    BenefitStatusCount, BenefitTypeCount, BenefitRealizationSummary,
    InitiativeBenefitSummary, BenefitDashboardSummary
)
from app.core.exceptions import NotFoundException, ValidationException


class BenefitService:
    """
    Service class for benefit management operations.
    
    Provides CRUD operations, aggregation queries, and business logic
    for the benefit tracking domain.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # CRUD Operations
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def create(self, benefit_data: BenefitCreate, created_by: Optional[str] = None) -> BenefitResponse:
        """
        Create a new benefit.
        
        Args:
            benefit_data: Benefit creation data
            created_by: User ID of the creator
            
        Returns:
            Created benefit response
        """
        # Validate status and type
        if benefit_data.realization_status not in [s.value for s in BenefitStatus]:
            raise ValidationException(
                message=f"Invalid realization status. Must be one of: {', '.join(s.value for s in BenefitStatus)}"
            )
        
        if benefit_data.benefit_type not in [t.value for t in BenefitType]:
            raise ValidationException(
                message=f"Invalid benefit type. Must be one of: {', '.join(t.value for t in BenefitType)}"
            )
        
        # Create benefit instance
        benefit = Benefit(
            id=str(uuid4()),
            initiative_id=benefit_data.initiative_id,
            title=benefit_data.title,
            description=benefit_data.description,
            benefit_type=benefit_data.benefit_type,
            target_value=benefit_data.target_value,
            current_value=benefit_data.current_value,
            unit=benefit_data.unit,
            realization_status=benefit_data.realization_status,
            target_date=benefit_data.target_date,
        )
        
        self.db.add(benefit)
        await self.db.commit()
        await self.db.refresh(benefit)
        
        return self._to_response(benefit)
    
    async def get(self, benefit_id: str) -> BenefitResponse:
        """
        Get a benefit by ID.
        
        Args:
            benefit_id: Benefit UUID
            
        Returns:
            Benefit response
            
        Raises:
            NotFoundException: If benefit not found
        """
        result = await self.db.execute(
            select(Benefit).where(Benefit.id == benefit_id)
        )
        benefit = result.scalar_one_or_none()
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        return self._to_response(benefit)
    
    async def get_by_id(self, benefit_id: str) -> Optional[Benefit]:
        """
        Get a benefit model by ID (internal use).
        
        Args:
            benefit_id: Benefit UUID
            
        Returns:
            Benefit model or None
        """
        result = await self.db.execute(
            select(Benefit).where(Benefit.id == benefit_id)
        )
        return result.scalar_one_or_none()
    
    async def update(self, benefit_id: str, benefit_data: BenefitUpdate, updated_by: Optional[str] = None) -> BenefitResponse:
        """
        Update an existing benefit.
        
        Args:
            benefit_id: Benefit UUID
            benefit_data: Benefit update data
            updated_by: User ID of the updater
            
        Returns:
            Updated benefit response
            
        Raises:
            NotFoundException: If benefit not found
        """
        benefit = await self.get_by_id(benefit_id)
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        # Update fields if provided
        update_data = benefit_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(benefit, field) and value is not None:
                setattr(benefit, field, value)
        
        # Auto-update realized_at if status changed to REALIZED
        if benefit_data.realization_status == BenefitStatus.REALIZED.value:
            benefit.realized_at = datetime.utcnow()
            benefit.current_value = benefit.target_value
        
        await self.db.commit()
        await self.db.refresh(benefit)
        
        return self._to_response(benefit)
    
    async def delete(self, benefit_id: str) -> bool:
        """
        Delete a benefit.
        
        Args:
            benefit_id: Benefit UUID
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If benefit not found
        """
        benefit = await self.get_by_id(benefit_id)
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        await self.db.delete(benefit)
        await self.db.commit()
        
        return True
    
    async def list_by_initiative(
        self,
        initiative_id: str,
        status: Optional[str] = None,
        benefit_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        List benefits for an initiative with optional filtering.
        
        Args:
            initiative_id: Initiative UUID
            status: Optional realization status filter
            benefit_type: Optional benefit type filter
            page: Page number
            page_size: Items per page
            
        Returns:
            Paginated list of benefits
        """
        # Build query
        query = select(Benefit).where(Benefit.initiative_id == initiative_id)
        
        if status:
            query = query.where(Benefit.realization_status == status)
        
        if benefit_type:
            query = query.where(Benefit.benefit_type == benefit_type)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination - order by target_date
        query = query.order_by(desc(Benefit.target_date))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        benefits = result.scalars().all()
        
        return {
            "items": [self._to_list_item(benefit) for benefit in benefits],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    async def list_all(
        self,
        status: Optional[str] = None,
        benefit_type: Optional[str] = None,
        initiative_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        List all benefits with optional filtering.
        
        Args:
            status: Optional realization status filter
            benefit_type: Optional benefit type filter
            initiative_id: Optional initiative filter
            page: Page number
            page_size: Items per page
            
        Returns:
            Paginated list of benefits
        """
        # Build query
        query = select(Benefit)
        
        if status:
            query = query.where(Benefit.realization_status == status)
        
        if benefit_type:
            query = query.where(Benefit.benefit_type == benefit_type)
        
        if initiative_id:
            query = query.where(Benefit.initiative_id == initiative_id)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.order_by(desc(Benefit.target_date))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        benefits = result.scalars().all()
        
        return {
            "items": [self._to_list_item(benefit) for benefit in benefits],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Aggregation & Dashboard Queries
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_dashboard_summary(self) -> BenefitDashboardSummary:
        """
        Get benefit dashboard summary with counts by status and type.
        
        Returns:
            Benefit dashboard summary
        """
        # Total count
        total_result = await self.db.execute(select(func.count()).select_from(Benefit))
        total_benefits = total_result.scalar()
        
        # Count by status with value aggregation
        status_result = await self.db.execute(
            select(
                Benefit.realization_status,
                func.count(),
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
            .group_by(Benefit.realization_status)
        )
        status_counts = [
            BenefitStatusCount(
                status=row[0],
                count=row[1],
                total_target_value=row[2],
                total_current_value=row[3]
            )
            for row in status_result.all()
        ]
        
        # Count by type with value aggregation
        type_result = await self.db.execute(
            select(
                Benefit.benefit_type,
                func.count(),
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
            .group_by(Benefit.benefit_type)
        )
        type_counts = [
            BenefitTypeCount(
                benefit_type=row[0],
                count=row[1],
                total_target_value=row[2],
                total_current_value=row[3]
            )
            for row in type_result.all()
        ]
        
        # Total values
        values_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
        )
        total_target_value, total_current_value = values_result.one()
        
        # Overall realization percentage
        overall_realization_percentage = (
            (total_current_value / total_target_value * 100) if total_target_value > 0 else 0.0
        )
        
        # Count by specific statuses
        realized_count = await self._count_by_status(BenefitStatus.REALIZED.value)
        in_progress_count = await self._count_by_status(BenefitStatus.IN_PROGRESS.value)
        projected_count = await self._count_by_status(BenefitStatus.PROJECTED.value)
        at_risk_count = await self._count_by_status(BenefitStatus.AT_RISK.value)
        not_achieved_count = await self._count_by_status(BenefitStatus.NOT_ACHIEVED.value)
        
        # Overdue count
        overdue_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Benefit.realization_status != BenefitStatus.REALIZED.value,
                    Benefit.target_date < date.today()
                )
            )
        )
        overdue_count = overdue_result.scalar()
        
        return BenefitDashboardSummary(
            total_benefits=total_benefits,
            by_status=status_counts,
            by_type=type_counts,
            overall_realization_percentage=round(overall_realization_percentage, 2),
            realized_count=realized_count,
            in_progress_count=in_progress_count,
            projected_count=projected_count,
            at_risk_count=at_risk_count,
            not_achieved_count=not_achieved_count,
            overdue_count=overdue_count
        )
    
    async def get_realization_summary(self) -> BenefitRealizationSummary:
        """
        Get benefit realization summary.
        
        Returns:
            Benefit realization summary
        """
        # Total count
        total_result = await self.db.execute(select(func.count()).select_from(Benefit))
        total_benefits = total_result.scalar()
        
        # Count by status with value aggregation
        status_result = await self.db.execute(
            select(
                Benefit.realization_status,
                func.count(),
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
            .group_by(Benefit.realization_status)
        )
        status_counts = [
            BenefitStatusCount(
                status=row[0],
                count=row[1],
                total_target_value=row[2],
                total_current_value=row[3]
            )
            for row in status_result.all()
        ]
        
        # Count by type with value aggregation
        type_result = await self.db.execute(
            select(
                Benefit.benefit_type,
                func.count(),
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
            .group_by(Benefit.benefit_type)
        )
        type_counts = [
            BenefitTypeCount(
                benefit_type=row[0],
                count=row[1],
                total_target_value=row[2],
                total_current_value=row[3]
            )
            for row in type_result.all()
        ]
        
        # Total values
        values_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            )
        )
        total_target_value, total_current_value = values_result.one()
        
        # Overall realization percentage
        overall_realization_percentage = (
            (total_current_value / total_target_value * 100) if total_target_value > 0 else 0.0
        )
        
        # Count by specific statuses
        realized_count = await self._count_by_status(BenefitStatus.REALIZED.value)
        at_risk_count = await self._count_by_status(BenefitStatus.AT_RISK.value)
        not_achieved_count = await self._count_by_status(BenefitStatus.NOT_ACHIEVED.value)
        
        # Overdue count
        overdue_result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Benefit.realization_status != BenefitStatus.REALIZED.value,
                    Benefit.target_date < date.today()
                )
            )
        )
        overdue_count = overdue_result.scalar()
        
        return BenefitRealizationSummary(
            total_benefits=total_benefits,
            by_status=status_counts,
            by_type=type_counts,
            total_target_value=total_target_value,
            total_current_value=total_current_value,
            overall_realization_percentage=round(overall_realization_percentage, 2),
            realized_count=realized_count,
            at_risk_count=at_risk_count,
            not_achieved_count=not_achieved_count,
            overdue_count=overdue_count
        )
    
    async def get_initiative_summary(self, initiative_id: str) -> InitiativeBenefitSummary:
        """
        Get benefit summary for a specific initiative.
        
        Args:
            initiative_id: Initiative UUID
            
        Returns:
            Initiative benefit summary
        """
        # Get initiative title
        from app.models.initiative import Initiative
        initiative_result = await self.db.execute(
            select(Initiative.title).where(Initiative.id == initiative_id)
        )
        initiative_title = initiative_result.scalar_one_or_none() or "Unknown"
        
        # Total benefits
        total_result = await self.db.execute(
            select(func.count()).where(Benefit.initiative_id == initiative_id)
        )
        total_benefits = total_result.scalar()
        
        # Total values
        values_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Benefit.target_value), 0.0),
                func.coalesce(func.sum(Benefit.current_value), 0.0)
            ).where(Benefit.initiative_id == initiative_id)
        )
        total_target_value, total_current_value = values_result.one()
        
        # Realization percentage
        realization_percentage = (
            (total_current_value / total_target_value * 100) if total_target_value > 0 else 0.0
        )
        
        # Count by status
        realized_count = await self._count_by_status_and_initiative(BenefitStatus.REALIZED.value, initiative_id)
        in_progress_count = await self._count_by_status_and_initiative(BenefitStatus.IN_PROGRESS.value, initiative_id)
        at_risk_count = await self._count_by_status_and_initiative(BenefitStatus.AT_RISK.value, initiative_id)
        
        return InitiativeBenefitSummary(
            initiative_id=initiative_id,
            initiative_title=initiative_title,
            total_benefits=total_benefits,
            total_target_value=total_target_value,
            total_current_value=total_current_value,
            realization_percentage=round(realization_percentage, 2),
            realized_count=realized_count,
            in_progress_count=in_progress_count,
            at_risk_count=at_risk_count
        )
    
    async def realize_benefit(self, benefit_id: str, realized_at: Optional[datetime] = None) -> BenefitResponse:
        """
        Mark a benefit as fully realized.
        
        Args:
            benefit_id: Benefit UUID
            realized_at: Optional timestamp for when benefit was realized
            
        Returns:
            Updated benefit response
        """
        benefit = await self.get_by_id(benefit_id)
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        benefit.mark_realized(realized_at)
        
        await self.db.commit()
        await self.db.refresh(benefit)
        
        return self._to_response(benefit)
    
    async def mark_at_risk(self, benefit_id: str) -> BenefitResponse:
        """
        Mark a benefit as at risk.
        
        Args:
            benefit_id: Benefit UUID
            
        Returns:
            Updated benefit response
        """
        benefit = await self.get_by_id(benefit_id)
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        benefit.mark_at_risk()
        
        await self.db.commit()
        await self.db.refresh(benefit)
        
        return self._to_response(benefit)
    
    async def update_progress(self, benefit_id: str, current_value: float) -> BenefitResponse:
        """
        Update the current realization progress of a benefit.
        
        Args:
            benefit_id: Benefit UUID
            current_value: New current value
            
        Returns:
            Updated benefit response
        """
        benefit = await self.get_by_id(benefit_id)
        
        if not benefit:
            raise NotFoundException(
                resource_type="Benefit",
                resource_id=benefit_id
            )
        
        benefit.update_progress(current_value)
        
        await self.db.commit()
        await self.db.refresh(benefit)
        
        return self._to_response(benefit)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def _count_by_status(self, status: str) -> int:
        """Count benefits by status."""
        result = await self.db.execute(
            select(func.count()).where(Benefit.realization_status == status)
        )
        return result.scalar()
    
    async def _count_by_status_and_initiative(self, status: str, initiative_id: str) -> int:
        """Count benefits by status and initiative."""
        result = await self.db.execute(
            select(func.count()).where(
                and_(
                    Benefit.realization_status == status,
                    Benefit.initiative_id == initiative_id
                )
            )
        )
        return result.scalar()
    
    def _to_response(self, benefit: Benefit) -> BenefitResponse:
        """Convert Benefit model to BenefitResponse schema."""
        # Get timestamps from the model's AuditableModel base
        created_at = getattr(benefit, 'created_at', datetime.utcnow())
        updated_at = getattr(benefit, 'updated_at', datetime.utcnow())
        created_by = getattr(benefit, 'created_by', None)
        updated_by = getattr(benefit, 'updated_by', None)
        
        # Calculate computed fields from model properties
        realization_percentage = benefit.realization_percentage
        remaining_value = benefit.remaining_value
        is_realized = benefit.is_realized
        is_at_risk = benefit.is_at_risk
        is_overdue = benefit.is_overdue
        
        return BenefitResponse(
            id=benefit.id,
            initiative_id=benefit.initiative_id,
            title=benefit.title,
            description=benefit.description,
            benefit_type=benefit.benefit_type,
            target_value=benefit.target_value,
            current_value=benefit.current_value,
            unit=benefit.unit,
            realization_status=benefit.realization_status,
            target_date=benefit.target_date,
            realization_percentage=realization_percentage,
            remaining_value=remaining_value,
            is_realized=is_realized,
            is_at_risk=is_at_risk,
            is_overdue=is_overdue,
            realized_at=benefit.realized_at,
            created_by=created_by,
            updated_by=updated_by,
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def _to_list_item(self, benefit: Benefit) -> BenefitListItem:
        """Convert Benefit model to BenefitListItem schema."""
        # Get timestamp from the model's AuditableModel base
        created_at = getattr(benefit, 'created_at', datetime.utcnow())
        
        # Calculate computed field from model property
        realization_percentage = benefit.realization_percentage
        
        return BenefitListItem(
            id=benefit.id,
            initiative_id=benefit.initiative_id,
            title=benefit.title,
            benefit_type=benefit.benefit_type,
            target_value=benefit.target_value,
            current_value=benefit.current_value,
            unit=benefit.unit,
            realization_status=benefit.realization_status,
            realization_percentage=realization_percentage,
            target_date=benefit.target_date,
            created_at=created_at,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Service Factory
# ═══════════════════════════════════════════════════════════════════════════════

async def get_benefit_service(db: AsyncSession) -> BenefitService:
    """
    Factory function to create a BenefitService instance.
    
    Args:
        db: Async database session
        
    Returns:
        BenefitService instance
    """
    return BenefitService(db)
