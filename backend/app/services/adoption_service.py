"""
DERTOUR Adoption Service Module
Service layer for adoption signal tracking, predictability scoring, and anomaly detection
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import uuid4

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adoption import (
    AdoptionSignal, 
    PredictabilityScore, 
    Anomaly,
    SignalType,
    TrendDirection,
    AnomalySeverity,
    AnomalyType
)
from app.models.initiative import Initiative


class AdoptionService:
    """
    Service for adoption measurement operations.
    
    Handles signal aggregation, predictability scoring, trend analysis,
    and anomaly detection for change management metrics.
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
    
    # ==========================================================================
    # Signal Operations
    # ==========================================================================
    
    async def create_signal(
        self,
        initiative_id: str,
        signal_type: str,
        value: float,
        timestamp: datetime,
        metadata_json: Optional[Dict[str, Any]] = None,
        trend_direction: Optional[str] = None,
        source_system: Optional[str] = None,
        notes: Optional[str] = None,
        recorded_by: Optional[str] = None
    ) -> AdoptionSignal:
        """
        Create a new adoption signal.
        
        Args:
            initiative_id: UUID of the initiative
            signal_type: Type of signal (Usage|Sentiment|Training_Completion|Support_Ticket|Custom)
            value: Numeric value of the signal
            timestamp: When the signal was recorded
            metadata_json: Additional metadata
            trend_direction: Trend direction (Improving|Stable|Declining)
            source_system: External system source
            notes: Optional notes
            recorded_by: User ID who recorded
            
        Returns:
            Created AdoptionSignal
        """
        signal = AdoptionSignal(
            id=str(uuid4()),
            initiative_id=initiative_id,
            signal_type=signal_type,
            value=float(value),
            timestamp=timestamp,
            metadata_json=metadata_json or {},
            trend_direction=trend_direction,
            source_system=source_system,
            notes=notes,
            recorded_by=recorded_by,
            anomaly_flag=False,
            created_by=recorded_by,
            updated_by=recorded_by
        )
        
        self.db.add(signal)
        await self.db.commit()
        await self.db.refresh(signal)
        
        # Recalculate predictability score after adding new signal
        await self.calculate_predictability_score(initiative_id, recorded_by)
        
        # Check for anomalies in the new signal
        await self._check_signal_for_anomaly(signal)
        
        return signal
    
    async def get_signals_by_initiative(
        self,
        initiative_id: str,
        signal_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AdoptionSignal], int]:
        """
        Get adoption signals for an initiative with optional filtering.
        
        Args:
            initiative_id: UUID of the initiative
            signal_type: Optional filter by signal type
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Tuple of (signals list, total count)
        """
        # Build query
        query = select(AdoptionSignal).where(
            AdoptionSignal.initiative_id == initiative_id
        )
        
        if signal_type:
            query = query.where(AdoptionSignal.signal_type == signal_type)
        
        if start_date:
            query = query.where(AdoptionSignal.timestamp >= start_date)
        
        if end_date:
            query = query.where(AdoptionSignal.timestamp <= end_date)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(desc(AdoptionSignal.timestamp))
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        signals = result.scalars().all()
        
        return list(signals), total
    
    async def get_signal_by_id(self, signal_id: str) -> Optional[AdoptionSignal]:
        """Get a signal by its ID."""
        result = await self.db.execute(
            select(AdoptionSignal).where(AdoptionSignal.id == signal_id)
        )
        return result.scalar_one_or_none()
    
    async def update_signal(
        self,
        signal_id: str,
        value: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        trend_direction: Optional[str] = None,
        anomaly_flag: Optional[bool] = None,
        notes: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> Optional[AdoptionSignal]:
        """
        Update an existing adoption signal.
        
        Args:
            signal_id: UUID of the signal to update
            value: New value
            timestamp: New timestamp
            metadata_json: New metadata
            trend_direction: New trend direction
            anomaly_flag: New anomaly flag
            notes: New notes
            updated_by: User making the update
            
        Returns:
            Updated signal or None if not found
        """
        signal = await self.get_signal_by_id(signal_id)
        if not signal:
            return None
        
        if value is not None:
            signal.value = float(value)
        if timestamp is not None:
            signal.timestamp = timestamp
        if metadata_json is not None:
            signal.metadata_json = metadata_json
        if trend_direction is not None:
            signal.trend_direction = trend_direction
        if anomaly_flag is not None:
            signal.anomaly_flag = anomaly_flag
        if notes is not None:
            signal.notes = notes
        
        signal.updated_by = updated_by
        signal.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(signal)
        
        # Recalculate predictability if value changed
        if value is not None:
            await self.calculate_predictability_score(signal.initiative_id, updated_by)
        
        return signal
    
    async def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal by ID."""
        signal = await self.get_signal_by_id(signal_id)
        if not signal:
            return False
        
        initiative_id = signal.initiative_id
        
        await self.db.delete(signal)
        await self.db.commit()
        
        # Recalculate predictability after deletion
        await self.calculate_predictability_score(initiative_id, None)
        
        return True
    
    # ==========================================================================
    # Predictability Scoring
    # ==========================================================================
    
    async def calculate_predictability_score(
        self,
        initiative_id: str,
        calculated_by: Optional[str] = None
    ) -> Optional[PredictabilityScore]:
        """
        Calculate predictability score for an initiative.
        
        Formula: 100 - (coefficient_of_variation * 100), clamped 0-100
        where coefficient_of_variation = std_dev / mean
        
        Args:
            initiative_id: UUID of the initiative
            calculated_by: User who triggered calculation
            
        Returns:
            PredictabilityScore record or None if insufficient data
        """
        # Get recent signals (last 90 days)
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        result = await self.db.execute(
            select(AdoptionSignal)
            .where(
                and_(
                    AdoptionSignal.initiative_id == initiative_id,
                    AdoptionSignal.timestamp >= cutoff_date
                )
            )
            .order_by(AdoptionSignal.timestamp)
        )
        signals = result.scalars().all()
        
        if len(signals) < 3:
            # Not enough data for meaningful calculation
            return None
        
        values = [s.value for s in signals]
        
        # Calculate statistics
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        
        # Calculate coefficient of variation
        if mean == 0:
            cv = 0.0
        else:
            cv = std_dev / abs(mean)
        
        # Calculate predictability score: 100 - (CV * 100)
        score = 100 - (cv * 100)
        score = max(0.0, min(100.0, score))  # Clamp to 0-100
        
        # Determine trend direction
        trend = self._calculate_trend_direction(values)
        
        # Get signal types used
        signal_types = list(set(s.signal_type for s in signals))
        
        # Count anomalies
        anomaly_count = sum(1 for s in signals if s.anomaly_flag)
        
        # Calculate time span
        time_span = (signals[-1].timestamp - signals[0].timestamp).days if len(signals) > 1 else 0
        
        # Create factors JSON
        factors = {
            "signal_count": len(signals),
            "time_span_days": time_span,
            "signal_types": signal_types,
            "variance_contribution": std_dev ** 2,
            "outlier_count": anomaly_count,
            "mean": mean,
            "std_dev": std_dev,
            "coefficient_of_variation": cv,
            "trend_direction": trend
        }
        
        # Create predictability score record
        predictability = PredictabilityScore(
            id=str(uuid4()),
            initiative_id=initiative_id,
            score=score,
            factors=factors,
            calculated_at=datetime.utcnow(),
            signal_count=len(signals),
            rolling_mean=mean,
            rolling_std=std_dev,
            coefficient_of_variation=cv,
            created_by=calculated_by,
            updated_by=calculated_by
        )
        
        self.db.add(predictability)
        
        # Update initiative with latest score
        await self.db.execute(
            select(Initiative).where(Initiative.id == initiative_id)
        )
        initiative_result = await self.db.execute(
            select(Initiative).where(Initiative.id == initiative_id)
        )
        initiative = initiative_result.scalar_one_or_none()
        
        if initiative:
            # Note: Initiative model uses health_score, not predictability_score
            # Store predictability data in a custom field or use existing fields
            initiative.health_score = score  # Using health_score as the field
            # Calculate adoption velocity (signals per week)
            if time_span > 0:
                initiative.adoption_velocity = (len(signals) / time_span) * 7
        
        await self.db.commit()
        await self.db.refresh(predictability)
        
        return predictability
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """
        Calculate trend direction from a series of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Trend direction string
        """
        if len(values) < 3:
            return TrendDirection.STABLE.value
        
        # Simple linear regression on last 5 points (or all if less)
        recent = values[-5:] if len(values) >= 5 else values
        n = len(recent)
        
        if n < 2:
            return TrendDirection.STABLE.value
        
        # Calculate slope
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n
        
        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return TrendDirection.STABLE.value
        
        slope = numerator / denominator
        
        # Determine trend based on slope magnitude
        threshold = abs(y_mean) * 0.05 if y_mean != 0 else 0.5
        
        if slope > threshold:
            return TrendDirection.IMPROVING.value
        elif slope < -threshold:
            return TrendDirection.DECLINING.value
        else:
            return TrendDirection.STABLE.value
    
    async def get_predictability_score(
        self,
        initiative_id: str
    ) -> Optional[PredictabilityScore]:
        """
        Get the most recent predictability score for an initiative.
        
        Args:
            initiative_id: UUID of the initiative
            
        Returns:
            Most recent PredictabilityScore or None
        """
        result = await self.db.execute(
            select(PredictabilityScore)
            .where(PredictabilityScore.initiative_id == initiative_id)
            .order_by(desc(PredictabilityScore.calculated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_predictability_history(
        self,
        initiative_id: str,
        limit: int = 30
    ) -> List[PredictabilityScore]:
        """
        Get historical predictability scores for an initiative.
        
        Args:
            initiative_id: UUID of the initiative
            limit: Maximum number of records to return
            
        Returns:
            List of PredictabilityScore records
        """
        result = await self.db.execute(
            select(PredictabilityScore)
            .where(PredictabilityScore.initiative_id == initiative_id)
            .order_by(desc(PredictabilityScore.calculated_at))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    # ==========================================================================
    # Trend Analysis
    # ==========================================================================
    
    async def get_trend_analysis(
        self,
        initiative_id: str,
        signal_type: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get trend analysis for an initiative's adoption signals.
        
        Args:
            initiative_id: UUID of the initiative
            signal_type: Optional filter by signal type
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend analysis data
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(AdoptionSignal).where(
            and_(
                AdoptionSignal.initiative_id == initiative_id,
                AdoptionSignal.timestamp >= start_date
            )
        )
        
        if signal_type:
            query = query.where(AdoptionSignal.signal_type == signal_type)
        
        query = query.order_by(AdoptionSignal.timestamp)
        
        result = await self.db.execute(query)
        signals = result.scalars().all()
        
        if not signals:
            return {
                "initiative_id": initiative_id,
                "signal_type": signal_type,
                "period_start": start_date,
                "period_end": datetime.utcnow(),
                "overall_trend": TrendDirection.STABLE.value,
                "data_points": [],
                "statistics": {
                    "mean": 0.0,
                    "median": 0.0,
                    "std_dev": 0.0,
                    "min_value": 0.0,
                    "max_value": 0.0,
                    "slope": None,
                    "r_squared": None
                },
                "anomaly_count": 0
            }
        
        values = [s.value for s in signals]
        
        # Calculate statistics
        mean = statistics.mean(values)
        median = statistics.median(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        min_val = min(values)
        max_val = max(values)
        
        # Calculate linear regression
        slope, r_squared = self._calculate_linear_regression(values)
        
        # Determine overall trend
        overall_trend = self._calculate_trend_direction(values)
        
        # Count anomalies
        anomaly_count = sum(1 for s in signals if s.anomaly_flag)
        
        # Build data points
        data_points = [
            {
                "timestamp": s.timestamp,
                "value": s.value,
                "signal_type": s.signal_type,
                "trend_direction": s.trend_direction,
                "anomaly_flag": s.anomaly_flag
            }
            for s in signals
        ]
        
        return {
            "initiative_id": initiative_id,
            "signal_type": signal_type,
            "period_start": start_date,
            "period_end": datetime.utcnow(),
            "overall_trend": overall_trend,
            "data_points": data_points,
            "statistics": {
                "mean": mean,
                "median": median,
                "std_dev": std_dev,
                "min_value": min_val,
                "max_value": max_val,
                "slope": slope,
                "r_squared": r_squared
            },
            "anomaly_count": anomaly_count
        }
    
    def _calculate_linear_regression(
        self,
        values: List[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate linear regression slope and R-squared.
        
        Args:
            values: List of y values (x is index)
            
        Returns:
            Tuple of (slope, r_squared)
        """
        n = len(values)
        if n < 2:
            return None, None
        
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        # Calculate slope
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0, None
        
        slope = numerator / denominator
        
        # Calculate R-squared
        ss_res = sum((values[i] - (y_mean + slope * (x[i] - x_mean))) ** 2 for i in range(n))
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        
        if ss_tot == 0:
            r_squared = 1.0 if ss_res == 0 else 0.0
        else:
            r_squared = 1 - (ss_res / ss_tot)
        
        return slope, r_squared
    
    # ==========================================================================
    # Anomaly Detection
    # ==========================================================================
    
    async def _check_signal_for_anomaly(self, signal: AdoptionSignal) -> Optional[Anomaly]:
        """
        Check if a signal is anomalous and create an anomaly record if so.
        
        Uses Z-score method: values beyond 2.5 standard deviations are anomalous.
        
        Args:
            signal: The signal to check
            
        Returns:
            Created Anomaly if detected, None otherwise
        """
        # Get historical signals of the same type for this initiative
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        result = await self.db.execute(
            select(AdoptionSignal)
            .where(
                and_(
                    AdoptionSignal.initiative_id == signal.initiative_id,
                    AdoptionSignal.signal_type == signal.signal_type,
                    AdoptionSignal.timestamp >= cutoff_date,
                    AdoptionSignal.id != signal.id
                )
            )
        )
        historical = result.scalars().all()
        
        if len(historical) < 5:
            # Not enough historical data
            return None
        
        values = [s.value for s in historical]
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        
        if std_dev == 0:
            return None
        
        # Calculate Z-score
        z_score = (signal.value - mean) / std_dev
        
        # Check if anomalous (beyond 2.5 standard deviations)
        if abs(z_score) < 2.5:
            return None
        
        # Determine anomaly type and severity
        is_high = signal.value > mean
        
        if signal.signal_type == "Usage":
            anomaly_type = AnomalyType.USAGE_SPIKE if is_high else AnomalyType.USAGE_DROP
        elif signal.signal_type == "Sentiment":
            anomaly_type = AnomalyType.SENTIMENT_DECLINE if not is_high else AnomalyType.CUSTOM
        elif signal.signal_type == "Training_Completion":
            anomaly_type = AnomalyType.TRAINING_STALL if not is_high else AnomalyType.CUSTOM
        elif signal.signal_type == "Support_Ticket":
            anomaly_type = AnomalyType.SUPPORT_TICKET_SURGE if is_high else AnomalyType.CUSTOM
        else:
            anomaly_type = AnomalyType.CUSTOM
        
        # Determine severity based on Z-score
        if abs(z_score) >= 4.0:
            severity = AnomalySeverity.CRITICAL
        elif abs(z_score) >= 3.0:
            severity = AnomalySeverity.HIGH
        elif abs(z_score) >= 2.5:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        
        # Create anomaly description
        direction = "spike" if is_high else "drop"
        description = f"{signal.signal_type} {direction} detected: {signal.value:.2f} " \
                     f"(expected: {mean:.2f} ± {std_dev:.2f}, Z-score: {z_score:.2f})"
        
        # Create anomaly record
        anomaly = Anomaly(
            id=str(uuid4()),
            initiative_id=signal.initiative_id,
            signal_id=signal.id,
            anomaly_type=anomaly_type.value,
            severity=severity.value,
            description=description,
            z_score=z_score,
            expected_value=mean,
            actual_value=signal.value,
            detected_at=datetime.utcnow(),
            created_by="system",
            updated_by="system"
        )
        
        # Update signal's anomaly flag
        signal.anomaly_flag = True
        
        self.db.add(anomaly)
        await self.db.commit()
        await self.db.refresh(anomaly)
        
        return anomaly
    
    async def get_anomalies(
        self,
        initiative_id: Optional[str] = None,
        severity: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Anomaly], int]:
        """
        Get anomalies with optional filtering.
        
        Args:
            initiative_id: Filter by initiative
            severity: Filter by severity
            anomaly_type: Filter by type
            is_resolved: Filter by resolution status
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (anomalies list, total count)
        """
        query = select(Anomaly)
        
        if initiative_id:
            query = query.where(Anomaly.initiative_id == initiative_id)
        
        if severity:
            query = query.where(Anomaly.severity == severity)
        
        if anomaly_type:
            query = query.where(Anomaly.anomaly_type == anomaly_type)
        
        if is_resolved is not None:
            if is_resolved:
                query = query.where(Anomaly.resolved_at.isnot(None))
            else:
                query = query.where(Anomaly.resolved_at.is_(None))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(desc(Anomaly.detected_at))
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        anomalies = result.scalars().all()
        
        return list(anomalies), total
    
    async def get_anomaly_by_id(self, anomaly_id: str) -> Optional[Anomaly]:
        """Get an anomaly by its ID."""
        result = await self.db.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        )
        return result.scalar_one_or_none()
    
    async def resolve_anomaly(
        self,
        anomaly_id: str,
        resolution_notes: Optional[str] = None,
        resolved_by: Optional[str] = None
    ) -> Optional[Anomaly]:
        """
        Mark an anomaly as resolved.
        
        Args:
            anomaly_id: UUID of the anomaly
            resolution_notes: Notes about the resolution
            resolved_by: User ID who resolved
            
        Returns:
            Updated anomaly or None if not found
        """
        anomaly = await self.get_anomaly_by_id(anomaly_id)
        if not anomaly:
            return None
        
        anomaly.resolved_at = datetime.utcnow()
        anomaly.resolution_notes = resolution_notes
        anomaly.resolved_by = resolved_by
        anomaly.updated_by = resolved_by
        anomaly.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(anomaly)
        
        return anomaly
    
    # ==========================================================================
    # Dashboard & Summary
    # ==========================================================================
    
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get adoption dashboard summary data.
        
        Returns:
            Dictionary with dashboard metrics
        """
        # Total signals
        signals_result = await self.db.execute(select(func.count()).select_from(AdoptionSignal))
        total_signals = signals_result.scalar() or 0
        
        # Total anomalies
        anomalies_result = await self.db.execute(select(func.count()).select_from(Anomaly))
        total_anomalies = anomalies_result.scalar() or 0
        
        # Unresolved anomalies
        unresolved_result = await self.db.execute(
            select(func.count()).select_from(Anomaly).where(Anomaly.resolved_at.is_(None))
        )
        unresolved_anomalies = unresolved_result.scalar() or 0
        
        # Average predictability score
        avg_score_result = await self.db.execute(
            select(func.avg(PredictabilityScore.score))
            .select_from(PredictabilityScore)
            .where(
                PredictabilityScore.calculated_at == (
                    select(func.max(PredictabilityScore.calculated_at))
                    .where(PredictabilityScore.initiative_id == PredictabilityScore.initiative_id)
                    .correlate(PredictabilityScore)
                )
            )
        )
        avg_predictability = avg_score_result.scalar()
        
        # Initiatives tracked (with signals)
        initiatives_result = await self.db.execute(
            select(func.count(func.distinct(AdoptionSignal.initiative_id)))
            .select_from(AdoptionSignal)
        )
        initiatives_tracked = initiatives_result.scalar() or 0
        
        # Recent signals (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_result = await self.db.execute(
            select(AdoptionSignal)
            .where(AdoptionSignal.timestamp >= recent_cutoff)
            .order_by(desc(AdoptionSignal.timestamp))
            .limit(10)
        )
        recent_signals = list(recent_result.scalars().all())
        
        # Top unresolved anomalies
        top_anomalies_result = await self.db.execute(
            select(Anomaly)
            .where(Anomaly.resolved_at.is_(None))
            .order_by(
                desc(Anomaly.severity),
                desc(Anomaly.detected_at)
            )
            .limit(10)
        )
        top_anomalies = list(top_anomalies_result.scalars().all())
        
        # Initiative summaries
        initiative_ids_result = await self.db.execute(
            select(func.distinct(AdoptionSignal.initiative_id))
            .select_from(AdoptionSignal)
        )
        initiative_ids = [row[0] for row in initiative_ids_result.all()]
        
        initiative_summaries = []
        for iid in initiative_ids[:10]:  # Limit to 10
            summary = await self.get_initiative_adoption_summary(iid)
            if summary:
                initiative_summaries.append(summary)
        
        return {
            "total_signals": total_signals,
            "total_anomalies": total_anomalies,
            "unresolved_anomalies": unresolved_anomalies,
            "avg_predictability_score": round(avg_predictability, 2) if avg_predictability else None,
            "initiatives_tracked": initiatives_tracked,
            "recent_signals": recent_signals,
            "top_anomalies": top_anomalies,
            "initiative_summaries": initiative_summaries
        }
    
    async def get_initiative_adoption_summary(
        self,
        initiative_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get adoption summary for a specific initiative.
        
        Args:
            initiative_id: UUID of the initiative
            
        Returns:
            Dictionary with adoption summary or None
        """
        # Get initiative
        initiative_result = await self.db.execute(
            select(Initiative).where(Initiative.id == initiative_id)
        )
        initiative = initiative_result.scalar_one_or_none()
        
        if not initiative:
            return None
        
        # Get signal count
        signal_count_result = await self.db.execute(
            select(func.count()).select_from(AdoptionSignal)
            .where(AdoptionSignal.initiative_id == initiative_id)
        )
        signal_count = signal_count_result.scalar() or 0
        
        # Get latest signal timestamp
        latest_signal_result = await self.db.execute(
            select(AdoptionSignal.timestamp)
            .where(AdoptionSignal.initiative_id == initiative_id)
            .order_by(desc(AdoptionSignal.timestamp))
            .limit(1)
        )
        latest_signal_row = latest_signal_result.first()
        latest_signal_at = latest_signal_row[0] if latest_signal_row else None
        
        # Get open anomalies count
        open_anomalies_result = await self.db.execute(
            select(func.count()).select_from(Anomaly)
            .where(
                and_(
                    Anomaly.initiative_id == initiative_id,
                    Anomaly.resolved_at.is_(None)
                )
            )
        )
        open_anomalies = open_anomalies_result.scalar() or 0
        
        # Get signal summaries by type
        signal_types_result = await self.db.execute(
            select(
                AdoptionSignal.signal_type,
                func.count().label('count'),
                func.avg(AdoptionSignal.value).label('avg_value')
            )
            .where(AdoptionSignal.initiative_id == initiative_id)
            .group_by(AdoptionSignal.signal_type)
        )
        
        signal_summaries = []
        for row in signal_types_result.all():
            signal_type, count, avg_value = row
            
            # Get latest value for this type
            latest_result = await self.db.execute(
                select(AdoptionSignal.value, AdoptionSignal.trend_direction)
                .where(
                    and_(
                        AdoptionSignal.initiative_id == initiative_id,
                        AdoptionSignal.signal_type == signal_type
                    )
                )
                .order_by(desc(AdoptionSignal.timestamp))
                .limit(1)
            )
            latest_row = latest_result.first()
            latest_value = latest_row[0] if latest_row else None
            trend = latest_row[1] if latest_row else None
            
            signal_summaries.append({
                "signal_type": signal_type,
                "count": count,
                "avg_value": round(avg_value, 2) if avg_value else 0.0,
                "latest_value": latest_value,
                "trend": trend
            })
        
        return {
            "initiative_id": initiative_id,
            "initiative_title": initiative.title,
            "predictability_score": initiative.predictability_score,
            "adoption_velocity": initiative.adoption_velocity,
            "signal_count": signal_count,
            "latest_signal_at": latest_signal_at,
            "open_anomalies": open_anomalies,
            "signal_summaries": signal_summaries
        }
    
    async def get_signal_type_distribution(
        self,
        initiative_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of signals by type.
        
        Args:
            initiative_id: Optional filter by initiative
            
        Returns:
            List of signal type distributions
        """
        query = select(
            AdoptionSignal.signal_type,
            func.count().label('count'),
            func.avg(AdoptionSignal.value).label('avg_value')
        ).group_by(AdoptionSignal.signal_type)
        
        if initiative_id:
            query = query.where(AdoptionSignal.initiative_id == initiative_id)
        
        result = await self.db.execute(query)
        
        return [
            {
                "signal_type": row[0],
                "count": row[1],
                "avg_value": round(row[2], 2) if row[2] else 0.0
            }
            for row in result.all()
        ]
    
    # ==========================================================================
    # Batch Operations
    # ==========================================================================
    
    async def batch_create_signals(
        self,
        signals_data: List[Dict[str, Any]],
        recorded_by: Optional[str] = None
    ) -> List[AdoptionSignal]:
        """
        Create multiple signals in a batch.
        
        Args:
            signals_data: List of signal data dictionaries
            recorded_by: User ID who recorded
            
        Returns:
            List of created AdoptionSignal records
        """
        created_signals = []
        
        for data in signals_data:
            signal = AdoptionSignal(
                id=str(uuid4()),
                initiative_id=data["initiative_id"],
                signal_type=data["signal_type"],
                value=float(data["value"]),
                timestamp=data.get("timestamp", datetime.utcnow()),
                metadata_json=data.get("metadata_json", {}),
                trend_direction=data.get("trend_direction"),
                source_system=data.get("source_system"),
                notes=data.get("notes"),
                recorded_by=recorded_by,
                anomaly_flag=False,
                created_by=recorded_by,
                updated_by=recorded_by
            )
            self.db.add(signal)
            created_signals.append(signal)
        
        await self.db.commit()
        
        # Refresh all signals
        for signal in created_signals:
            await self.db.refresh(signal)
        
        # Recalculate predictability for affected initiatives
        initiative_ids = set(s.initiative_id for s in created_signals)
        for iid in initiative_ids:
            await self.calculate_predictability_score(iid, recorded_by)
        
        return created_signals
    
    async def recalculate_all_predictability_scores(
        self,
        calculated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Recalculate predictability scores for all initiatives with signals.
        
        Args:
            calculated_by: User who triggered recalculation
            
        Returns:
            Dictionary with recalculation results
        """
        # Get all initiative IDs with signals
        result = await self.db.execute(
            select(func.distinct(AdoptionSignal.initiative_id))
            .select_from(AdoptionSignal)
        )
        initiative_ids = [row[0] for row in result.all()]
        
        success_count = 0
        failed_count = 0
        
        for iid in initiative_ids:
            try:
                score = await self.calculate_predictability_score(iid, calculated_by)
                if score:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
        
        return {
            "total_initiatives": len(initiative_ids),
            "success_count": success_count,
            "failed_count": failed_count
        }


# Singleton instance
_adoption_service: Optional[AdoptionService] = None


def get_adoption_service(db: AsyncSession) -> AdoptionService:
    """
    Get or create the adoption service.
    
    Args:
        db: Database session
        
    Returns:
        AdoptionService instance
    """
    return AdoptionService(db)
