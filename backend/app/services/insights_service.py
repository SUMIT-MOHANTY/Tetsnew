"""
DERTOUR Insights Engine Service Module
Business logic for PI_DETECT, PI_RECOMMEND, PI_NARRATIVE, and PI_CALC workflows
"""

from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set
from uuid import uuid4
from collections import defaultdict

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Import SQLAlchemy models (not Pydantic schemas) for database operations
from app.models.insight import (
    Insight, InsightSignal, Recommendation, Narrative, KPIResult,
    InsightType, InsightSignalType, InsightSeverity, InsightStatus,
    RecommendationType, RecommendationPriority, RecommendationStatus,
    NarrativeType, NarrativeAudience, TrendDirection, ConfidenceLevel,
    KPICategory, KPIType
)
from app.models.initiative import Initiative, InitiativeStatus, InitiativePriority
from app.models.milestone import Milestone, MilestoneStatus
from app.models.dependency import Dependency, DependencyType, DependencyStatus
from app.models.risk import Risk, RiskSeverity, RiskStatus
from app.models.decision import Decision, DecisionStatus
from app.models.benefit import Benefit, BenefitStatus
from app.models.adoption import AdoptionSignal, PredictabilityScore, Anomaly
from app.core.config_loader import get_settings
from app.core.exceptions import NotFoundException, ValidationException


class DetectionService:
    """
    PI_DETECT Service - Delay & Blocker Detection
    
    Analyzes initiative/milestone status, dependencies, and dates against
    configurable thresholds to detect delays, blockers, and stalled work.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def detect_delays(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect delayed initiatives and milestones.
        
        Args:
            initiative_id: Optional initiative ID to check (None for all)
            
        Returns:
            List of delay signals with severity and root cause
        """
        delay_signals = []
        delay_tolerance = getattr(self.settings, 'DELAY_TOLERANCE_DAYS', 7)
        today = date.today()
        
        # Build query for initiatives - load milestones relationship using SQLAlchemy model
        query = select(Initiative).options(
            selectinload(Initiative.milestones)
        )
        
        if initiative_id:
            query = query.where(Initiative.id == initiative_id)
        else:
            # Only check active initiatives
            query = query.where(Initiative.status.notin_([
                InitiativeStatus.COMPLETED.value,
                InitiativeStatus.ON_HOLD.value
            ]))
        
        result = await self.db.execute(query)
        initiatives = result.scalars().all()
        
        for initiative in initiatives:
            # Check initiative-level delays
            if initiative.target_date and initiative.target_date < today:
                days_overdue = (today - initiative.target_date).days
                severity = self._calculate_delay_severity(days_overdue, delay_tolerance)
                
                delay_signals.append({
                    "initiative_id": initiative.id,
                    "signal_type": InsightSignalType.MILESTONE_SLIP.value,
                    "severity": severity,
                    "message": f"Initiative '{initiative.title}' is {days_overdue} days overdue",
                    "threshold_value": 0,
                    "actual_value": days_overdue,
                    "threshold_unit": "days",
                    "root_cause": f"Target date ({initiative.target_date}) has passed",
                    "affected_entities": [{"type": "initiative", "id": initiative.id}],
                    "confidence_score": 0.95
                })
            
            # Check milestone delays - use the relationship from SQLAlchemy Initiative model
            for milestone in initiative.milestones:
                if (milestone.due_date and milestone.due_date < today and 
                    milestone.status not in [MilestoneStatus.COMPLETED.value, MilestoneStatus.CANCELLED.value]):
                    days_overdue = (today - milestone.due_date).days
                    severity = self._calculate_delay_severity(days_overdue, delay_tolerance)
                    
                    delay_signals.append({
                        "initiative_id": initiative.id,
                        "signal_type": InsightSignalType.MILESTONE_SLIP.value,
                        "severity": severity,
                        "message": f"Milestone '{milestone.title}' is {days_overdue} days overdue",
                        "threshold_value": 0,
                        "actual_value": days_overdue,
                        "threshold_unit": "days",
                        "root_cause": f"Milestone due date ({milestone.due_date}) has passed",
                        "affected_entities": [
                            {"type": "initiative", "id": initiative.id},
                            {"type": "milestone", "id": milestone.id}
                        ],
                        "confidence_score": 0.95
                    })
        
        return delay_signals
    
    async def detect_blockers(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect blocked initiatives due to dependencies and circular dependencies.
        
        Args:
            initiative_id: Optional initiative ID to check (None for all)
            
        Returns:
            List of blocker signals with severity and root cause
        """
        blocker_signals = []
        
        # Build query for dependencies using SQLAlchemy model
        query = select(Dependency)
        
        if initiative_id:
            query = query.where(
                or_(
                    Dependency.source_initiative_id == initiative_id,
                    Dependency.target_initiative_id == initiative_id
                )
            )
        
        result = await self.db.execute(query)
        dependencies = result.scalars().all()
        
        # Build dependency graph for circular detection
        graph = defaultdict(list)
        dep_map = {}
        
        for dep in dependencies:
            graph[dep.source_initiative_id].append(dep.target_initiative_id)
            dep_map[(dep.source_initiative_id, dep.target_initiative_id)] = dep
        
        # Detect circular dependencies
        circular_paths = self._detect_circular_dependencies(graph)
        
        for path in circular_paths:
            initiative_ids_in_cycle = list(dict.fromkeys(path))  # Remove duplicates while preserving order
            initiatives_in_cycle = []
            
            for iid in initiative_ids_in_cycle:
                init = await self.db.get(Initiative, iid)
                if init:
                    initiatives_in_cycle.append({"id": iid, "title": init.title})
            
            if initiatives_in_cycle:
                blocker_signals.append({
                    "initiative_id": initiative_ids_in_cycle[0],
                    "signal_type": InsightSignalType.CIRCULAR_DEPENDENCY.value,
                    "severity": InsightSeverity.CRITICAL.value,
                    "message": f"Circular dependency detected involving {len(initiatives_in_cycle)} initiatives",
                    "threshold_value": 0,
                    "actual_value": len(initiatives_in_cycle),
                    "threshold_unit": "initiatives",
                    "root_cause": "Circular dependency chain: " + " -> ".join([i["title"] for i in initiatives_in_cycle]),
                    "affected_entities": [{"type": "initiative", "id": i["id"]} for i in initiatives_in_cycle],
                    "confidence_score": 1.0
                })
        
        # Detect blocking dependencies
        for dep in dependencies:
            if (dep.dependency_type == DependencyType.BLOCKS.value and 
                dep.status == DependencyStatus.ACTIVE.value):
                
                # Fetch target initiative separately using SQLAlchemy model
                target_initiative = await self.db.get(Initiative, dep.target_initiative_id)
                if target_initiative and target_initiative.status != InitiativeStatus.COMPLETED.value:
                    blocker_signals.append({
                        "initiative_id": dep.source_initiative_id,
                        "signal_type": InsightSignalType.DEPENDENCY_BLOCK.value,
                        "severity": InsightSeverity.HIGH.value,
                        "message": f"Blocked by incomplete initiative '{target_initiative.title}'",
                        "threshold_value": 0,
                        "actual_value": 1,
                        "threshold_unit": "blockers",
                        "root_cause": f"Depends on initiative {target_initiative.id} which is {target_initiative.status}",
                        "affected_entities": [
                            {"type": "initiative", "id": dep.source_initiative_id},
                            {"type": "initiative", "id": dep.target_initiative_id},
                            {"type": "dependency", "id": dep.id}
                        ],
                        "confidence_score": 0.9
                    })
        
        return blocker_signals
    
    async def detect_stalled_work(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect stalled initiatives with no recent updates.
        
        Args:
            initiative_id: Optional initiative ID to check (None for all)
            
        Returns:
            List of stall signals with severity and root cause
        """
        stall_signals = []
        stall_threshold_days = 14  # No updates in 14 days = stalled
        today = date.today()
        
        query = select(Initiative)
        
        if initiative_id:
            query = query.where(Initiative.id == initiative_id)
        else:
            query = query.where(Initiative.status.notin_([
                InitiativeStatus.COMPLETED.value,
                InitiativeStatus.ON_HOLD.value
            ]))
        
        result = await self.db.execute(query)
        initiatives = result.scalars().all()
        
        for initiative in initiatives:
            # Check last update time
            last_update = initiative.updated_at
            if last_update:
                days_since_update = (today - last_update.date()).days
                
                if days_since_update > stall_threshold_days:
                    severity = InsightSeverity.MEDIUM.value
                    if days_since_update > 30:
                        severity = InsightSeverity.HIGH.value
                    
                    stall_signals.append({
                        "initiative_id": initiative.id,
                        "signal_type": InsightSignalType.NO_UPDATES.value,
                        "severity": severity,
                        "message": f"Initiative '{initiative.title}' has no updates for {days_since_update} days",
                        "threshold_value": stall_threshold_days,
                        "actual_value": days_since_update,
                        "threshold_unit": "days",
                        "root_cause": f"No activity recorded since {last_update.date()}",
                        "affected_entities": [{"type": "initiative", "id": initiative.id}],
                        "confidence_score": 0.85
                    })
        
        return stall_signals
    
    async def detect_risk_escalations(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Detect risks that have escalated beyond threshold.
        
        Args:
            initiative_id: Optional initiative ID to check (None for all)
            
        Returns:
            List of risk escalation signals
        """
        escalation_signals = []
        escalation_threshold = getattr(self.settings, 'RISK_ESCALATION_THRESHOLD', 'HIGH')
        
        query = select(Risk)
        
        if initiative_id:
            query = query.where(Risk.initiative_id == initiative_id)
        
        query = query.where(Risk.status.notin_([RiskStatus.RESOLVED.value, RiskStatus.ACCEPTED.value]))
        
        result = await self.db.execute(query)
        risks = result.scalars().all()
        
        for risk in risks:
            if risk.severity in [RiskSeverity.HIGH.value, RiskSeverity.CRITICAL.value]:
                severity = InsightSeverity.HIGH.value
                if risk.severity == RiskSeverity.CRITICAL.value:
                    severity = InsightSeverity.CRITICAL.value
                
                escalation_signals.append({
                    "initiative_id": risk.initiative_id,
                    "signal_type": InsightSignalType.RISK_THRESHOLD.value,
                    "severity": severity,
                    "message": f"Risk '{risk.title}' has escalated to {risk.severity}",
                    "threshold_value": 0,
                    "actual_value": risk.probability or 0.5,
                    "threshold_unit": "probability",
                    "root_cause": risk.description or "Risk severity above threshold",
                    "affected_entities": [
                        {"type": "initiative", "id": risk.initiative_id},
                        {"type": "risk", "id": risk.id}
                    ],
                    "confidence_score": risk.probability or 0.7
                })
        
        return escalation_signals
    
    def _calculate_delay_severity(self, days_overdue: int, tolerance: int) -> str:
        """Calculate severity based on days overdue."""
        if days_overdue <= tolerance:
            return InsightSeverity.LOW.value
        elif days_overdue <= tolerance * 2:
            return InsightSeverity.MEDIUM.value
        elif days_overdue <= tolerance * 3:
            return InsightSeverity.HIGH.value
        else:
            return InsightSeverity.CRITICAL.value
    
    def _detect_circular_dependencies(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """
        Detect circular dependencies using DFS.
        
        Returns:
            List of circular paths found
        """
        circular_paths = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: str):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    circular_paths.append(cycle)
            
            path.pop()
            rec_stack.remove(node)
        
        for node in list(graph.keys()):
            if node not in visited:
                dfs(node)
        
        return circular_paths


class RecommendationService:
    """
    PI_RECOMMEND Service - AI Recommendation Generation
    
    Generates rule-based recommendations with evidence chains,
    confidence scoring, and suggested actions/tools.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def generate_recommendations(
        self,
        initiative_id: Optional[str] = None,
        insight_id: Optional[str] = None,
        max_recommendations: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on insights.
        
        Args:
            initiative_id: Optional initiative ID to focus on
            insight_id: Optional specific insight to generate recommendations for
            max_recommendations: Maximum number of recommendations to generate
            
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Build query for insights
        query = select(Insight).where(Insight.status == InsightStatus.ACTIVE.value)
        
        if insight_id:
            query = query.where(Insight.id == insight_id)
        elif initiative_id:
            query = query.where(Insight.initiative_id == initiative_id)
        
        # Order by severity and confidence
        query = query.order_by(desc(Insight.severity), desc(Insight.confidence_score))
        query = query.limit(max_recommendations * 2)  # Get more to filter
        
        result = await self.db.execute(query)
        insights = result.scalars().all()
        
        for insight in insights:
            rec = await self._generate_recommendation_for_insight(insight)
            if rec:
                recommendations.append(rec)
                
            if len(recommendations) >= max_recommendations:
                break
        
        return recommendations
    
    async def _generate_recommendation_for_insight(self, insight: Insight) -> Optional[Dict[str, Any]]:
        """Generate a recommendation for a specific insight."""
        
        # Map insight types to recommendation types
        type_mapping = {
            InsightType.DELAY.value: RecommendationType.ACCELERATE,
            InsightType.BLOCKER.value: RecommendationType.ESCALATE,
            InsightType.STALLED.value: RecommendationType.REVIEW,
            InsightType.RISK_ESCALATION.value: RecommendationType.MITIGATE_RISK,
            InsightType.BENEFIT_AT_RISK.value: RecommendationType.REALLOCATE,
            InsightType.ANOMALY.value: RecommendationType.INVESTIGATE,
            InsightType.TREND.value: RecommendationType.REVIEW
        }
        
        rec_type = type_mapping.get(insight.insight_type, RecommendationType.REVIEW)
        
        # Calculate priority based on severity
        priority_map = {
            InsightSeverity.CRITICAL.value: RecommendationPriority.CRITICAL,
            InsightSeverity.HIGH.value: RecommendationPriority.HIGH,
            InsightSeverity.MEDIUM.value: RecommendationPriority.MEDIUM,
            InsightSeverity.LOW.value: RecommendationPriority.LOW
        }
        priority = priority_map.get(insight.severity, RecommendationPriority.MEDIUM)
        
        # Build evidence data
        evidence_data = {
            "insight_id": insight.id,
            "insight_type": insight.insight_type,
            "signal_type": insight.signal_type,
            "severity": insight.severity,
            "detected_at": insight.detected_at.isoformat() if insight.detected_at else None,
            "confidence_score": insight.confidence_score
        }
        
        # Generate description based on type
        description = self._generate_recommendation_description(insight, rec_type)
        
        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(insight, rec_type)
        
        # Generate suggested tools
        suggested_tools = self._generate_suggested_tools(rec_type)
        
        return {
            "initiative_id": insight.initiative_id,
            "insight_id": insight.id,
            "recommendation_type": rec_type.value,
            "priority": priority.value,
            "title": f"{rec_type.value.replace('_', ' ').title()}: {insight.title}",
            "description": description,
            "confidence_score": insight.confidence_score * 0.95,  # Slightly lower than insight confidence
            "status": RecommendationStatus.PENDING.value,
            "estimated_impact": self._estimate_impact(insight, rec_type),
            "evidence_data": evidence_data,
            "suggested_actions": suggested_actions,
            "suggested_tools": suggested_tools
        }
    
    def _generate_recommendation_description(self, insight: Insight, rec_type: RecommendationType) -> str:
        """Generate a human-readable recommendation description."""
        
        templates = {
            RecommendationType.MITIGATE_RISK: f"Address the elevated risk '{insight.title}' to prevent project impact. Review mitigation strategies and allocate resources accordingly.",
            RecommendationType.ACCELERATE: f"Accelerate progress on '{insight.title}' to recover from delays. Consider resource reallocation or scope adjustment.",
            RecommendationType.REALLOCATE: f"Reallocate resources to address '{insight.title}'. Current distribution may not be optimal for achieving targets.",
            RecommendationType.ESCALATE: f"Escalate '{insight.title}' to appropriate stakeholders for immediate attention and resolution.",
            RecommendationType.REVIEW: f"Conduct a detailed review of '{insight.title}' to understand root causes and develop action plan.",
            RecommendationType.COMMUNICATE: f"Communicate '{insight.title}' to relevant stakeholders to ensure transparency and alignment.",
            RecommendationType.INVESTIGATE: f"Investigate '{insight.title}' to understand underlying patterns and determine appropriate response."
        }
        
        return templates.get(rec_type, f"Address '{insight.title}' based on detected insight.")
    
    def _generate_suggested_actions(self, insight: Insight, rec_type: RecommendationType) -> List[str]:
        """Generate suggested actions based on recommendation type."""
        
        actions = {
            RecommendationType.MITIGATE_RISK: [
                "Review risk mitigation plan",
                "Schedule risk review meeting",
                "Update risk register",
                "Assign risk owner if not assigned"
            ],
            RecommendationType.ACCELERATE: [
                "Identify critical path items",
                "Review resource allocation",
                "Consider parallel work streams",
                "Negotiate scope adjustments if needed"
            ],
            RecommendationType.REALLOCATE: [
                "Analyze resource utilization",
                "Identify underutilized resources",
                "Reassign tasks based on priorities",
                "Update resource plan"
            ],
            RecommendationType.ESCALATE: [
                "Prepare escalation summary",
                "Identify decision makers",
                "Schedule escalation meeting",
                "Document escalation rationale"
            ],
            RecommendationType.REVIEW: [
                "Schedule review session",
                "Gather relevant data",
                "Identify stakeholders for review",
                "Document findings and recommendations"
            ],
            RecommendationType.COMMUNICATE: [
                "Draft communication message",
                "Identify communication channels",
                "Schedule stakeholder update",
                "Update project dashboard"
            ],
            RecommendationType.INVESTIGATE: [
                "Gather detailed data",
                "Interview relevant team members",
                "Analyze historical patterns",
                "Document investigation findings"
            ]
        }
        
        return actions.get(rec_type, ["Review the insight details", "Determine appropriate action"])
    
    def _generate_suggested_tools(self, rec_type: RecommendationType) -> List[str]:
        """Generate suggested tools based on recommendation type."""
        
        tools = {
            RecommendationType.MITIGATE_RISK: ["Risk Register", "Risk Matrix", "Monte Carlo Simulation"],
            RecommendationType.ACCELERATE: ["Critical Path Analysis", "Resource Leveling", "Fast Tracking"],
            RecommendationType.REALLOCATE: ["Resource Management", "Capacity Planning", "What-if Analysis"],
            RecommendationType.ESCALATE: ["Escalation Matrix", "Stakeholder Map", "Decision Log"],
            RecommendationType.REVIEW: ["Root Cause Analysis", "Fishbone Diagram", "5 Whys"],
            RecommendationType.COMMUNICATE: ["Communication Plan", "Stakeholder Analysis", "Dashboard"],
            RecommendationType.INVESTIGATE: ["Data Analysis", "Trend Analysis", "Pattern Recognition"]
        }
        
        return tools.get(rec_type, ["Portfolio Dashboard", "Initiative Details"])
    
    def _estimate_impact(self, insight: Insight, rec_type: RecommendationType) -> str:
        """Estimate the impact of following the recommendation."""
        
        if insight.severity == InsightSeverity.CRITICAL.value:
            return "High - Critical issue requiring immediate attention to prevent significant project impact"
        elif insight.severity == InsightSeverity.HIGH.value:
            return "Medium-High - Significant issue that should be addressed to maintain project health"
        elif insight.severity == InsightSeverity.MEDIUM.value:
            return "Medium - Moderate issue that should be monitored and addressed as resources allow"
        else:
            return "Low - Minor issue that can be addressed during regular operations"


class NarrativeService:
    """
    PI_NARRATIVE Service - Narrative Generation
    
    Generates executive narratives and summaries using configurable templates
    for different audiences (Executive, PMO, Team).
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def generate_executive_narrative(
        self,
        narrative_type: NarrativeType = NarrativeType.EXECUTIVE,
        audience: NarrativeAudience = NarrativeAudience.EXECUTIVE,
        initiative_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an executive narrative for portfolio status.
        
        Args:
            narrative_type: Type of narrative to generate
            audience: Target audience for the narrative
            initiative_id: Optional specific initiative to focus on
            
        Returns:
            Generated narrative with content and metadata
        """
        # Gather portfolio data
        portfolio_data = await self._gather_portfolio_data(initiative_id)
        
        # Generate narrative based on type and audience
        if narrative_type == NarrativeType.EXECUTIVE:
            content = self._generate_executive_summary(portfolio_data, audience)
        elif narrative_type == NarrativeType.OPERATIONAL:
            content = self._generate_operational_summary(portfolio_data, audience)
        elif narrative_type == NarrativeType.EXCEPTION:
            content = self._generate_exception_report(portfolio_data, audience)
        elif narrative_type == NarrativeType.TREND:
            content = self._generate_trend_analysis(portfolio_data, audience)
        elif narrative_type == NarrativeType.FORECAST:
            content = self._generate_forecast(portfolio_data, audience)
        else:
            content = self._generate_executive_summary(portfolio_data, audience)
        
        # Calculate confidence level based on data quality
        confidence = self._calculate_narrative_confidence(portfolio_data)
        
        # Determine trend direction
        trend = self._determine_trend_direction(portfolio_data)
        
        return {
            "narrative_type": narrative_type.value,
            "audience": audience.value,
            "title": self._generate_narrative_title(narrative_type, portfolio_data),
            "content": content,
            "summary": self._generate_brief_summary(portfolio_data),
            "trend_direction": trend.value,
            "confidence_level": confidence.value,
            "portfolio_health_score": portfolio_data.get("health_score"),
            "key_highlights": self._extract_highlights(portfolio_data),
            "attention_items": self._extract_attention_items(portfolio_data),
            "kpi_snapshot": portfolio_data.get("kpis", {}),
            "evidence_refs": self._generate_evidence_refs(portfolio_data),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _gather_portfolio_data(self, initiative_id: Optional[str] = None) -> Dict[str, Any]:
        """Gather comprehensive portfolio data for narrative generation."""
        
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "initiative_id": initiative_id
        }
        
        # Get initiative counts by status
        if initiative_id:
            # Single initiative focus
            initiative = await self.db.get(Initiative, initiative_id)
            if initiative:
                data["initiative"] = {
                    "id": initiative.id,
                    "title": initiative.title,
                    "status": initiative.status,
                    "health_score": initiative.health_score,
                    "progress": await self._calculate_initiative_progress(initiative)
                }
        else:
            # Portfolio-wide
            result = await self.db.execute(
                select(Initiative.status, func.count(Initiative.id))
                .group_by(Initiative.status)
            )
            status_counts = {row[0]: row[1] for row in result.all()}
            data["initiative_counts"] = status_counts
            
            # Get overall health
            result = await self.db.execute(
                select(func.avg(Initiative.health_score))
                .where(Initiative.health_score.isnot(None))
            )
            avg_health = result.scalar()
            data["health_score"] = round(avg_health, 2) if avg_health else None
        
        # Get active insights count
        result = await self.db.execute(
            select(func.count(Insight.id))
            .where(Insight.status == InsightStatus.ACTIVE.value)
        )
        data["active_insights_count"] = result.scalar()
        
        # Get critical/high severity insights
        result = await self.db.execute(
            select(func.count(Insight.id))
            .where(
                and_(
                    Insight.status == InsightStatus.ACTIVE.value,
                    Insight.severity.in_([InsightSeverity.CRITICAL.value, InsightSeverity.HIGH.value])
                )
            )
        )
        data["critical_insights_count"] = result.scalar()
        
        # Get pending recommendations
        result = await self.db.execute(
            select(func.count(Recommendation.id))
            .where(Recommendation.status == RecommendationStatus.PENDING.value)
        )
        data["pending_recommendations_count"] = result.scalar()
        
        return data
    
    async def _calculate_initiative_progress(self, initiative: Initiative) -> float:
        """Calculate progress percentage for an initiative."""
        # Load milestones for the initiative
        result = await self.db.execute(
            select(Milestone).where(Milestone.initiative_id == initiative.id)
        )
        milestones = result.scalars().all()
        
        if not milestones:
            return 0.0
        
        completed = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED.value)
        return (completed / len(milestones)) * 100
    
    def _generate_executive_summary(self, data: Dict[str, Any], audience: NarrativeAudience) -> str:
        """Generate executive summary narrative."""
        
        if data.get("initiative"):
            # Single initiative focus
            init = data["initiative"]
            return f"""
## Initiative Status: {init['title']}

The initiative is currently **{init['status']}** with a health score of **{init['health_score'] or 'N/A'}/100**.
Progress stands at **{init['progress']:.1f}%** completion.

### Key Points
- Status: {init['status']}
- Health Score: {init['health_score'] or 'Not calculated'}
- Progress: {init['progress']:.1f}%

### Recommendations
{self._format_recommendations(data.get('pending_recommendations_count', 0))}
"""
        else:
            # Portfolio-wide
            counts = data.get("initiative_counts", {})
            total = sum(counts.values())
            health = data.get("health_score", "N/A")
            
            return f"""
## Portfolio Executive Summary

The portfolio currently contains **{total} initiatives** with an overall health score of **{health or 'N/A'}/100**.

### Initiative Distribution
{self._format_status_counts(counts)}

### Active Insights
- **{data.get('active_insights_count', 0)}** active insights
- **{data.get('critical_insights_count', 0)}** critical/high severity items requiring attention
- **{data.get('pending_recommendations_count', 0)}** pending recommendations

### Overall Assessment
{self._generate_health_assessment(health)}
"""
    
    def _generate_operational_summary(self, data: Dict[str, Any], audience: NarrativeAudience) -> str:
        """Generate operational summary narrative."""
        return self._generate_executive_summary(data, audience)  # Simplified for now
    
    def _generate_exception_report(self, data: Dict[str, Any], audience: NarrativeAudience) -> str:
        """Generate exception report narrative."""
        
        critical_count = data.get("critical_insights_count", 0)
        
        return f"""
## Exception Report

### Critical Items Requiring Immediate Attention: {critical_count}

This report highlights exceptions and deviations from expected performance.

### Active Insights Summary
- Total Active Insights: {data.get('active_insights_count', 0)}
- Critical/High Severity: {critical_count}
- Pending Recommendations: {data.get('pending_recommendations_count', 0)}

### Recommended Actions
1. Review all critical insights immediately
2. Assign owners for resolution
3. Update stakeholders on exception status
4. Implement corrective actions
"""
    
    def _generate_trend_analysis(self, data: Dict[str, Any], audience: NarrativeAudience) -> str:
        """Generate trend analysis narrative."""
        return "Trend analysis based on historical data patterns. (Detailed implementation pending)"
    
    def _generate_forecast(self, data: Dict[str, Any], audience: NarrativeAudience) -> str:
        """Generate forecast narrative."""
        return "Forecast based on current trajectory and historical patterns. (Detailed implementation pending)"
    
    def _generate_narrative_title(self, narrative_type: NarrativeType, data: Dict[str, Any]) -> str:
        """Generate a title for the narrative."""
        if data.get("initiative"):
            return f"{narrative_type.value} Report: {data['initiative']['title']}"
        return f"Portfolio {narrative_type.value} Report"
    
    def _generate_brief_summary(self, data: Dict[str, Any]) -> str:
        """Generate a brief summary."""
        if data.get("initiative"):
            init = data["initiative"]
            return f"Initiative '{init['title']}' is {init['status']} with {init['progress']:.1f}% progress."
        
        counts = data.get("initiative_counts", {})
        total = sum(counts.values())
        return f"Portfolio contains {total} initiatives with {data.get('active_insights_count', 0)} active insights."
    
    def _calculate_narrative_confidence(self, data: Dict[str, Any]) -> ConfidenceLevel:
        """Calculate confidence level based on data quality."""
        # Simple heuristic - could be more sophisticated
        if data.get("initiative") or data.get("health_score"):
            return ConfidenceLevel.HIGH
        return ConfidenceLevel.MEDIUM
    
    def _determine_trend_direction(self, data: Dict[str, Any]) -> TrendDirection:
        """Determine overall trend direction."""
        health = data.get("health_score")
        if health is None:
            return TrendDirection.STABLE
        elif health >= 80:
            return TrendDirection.IMPROVING
        elif health >= 60:
            return TrendDirection.STABLE
        else:
            return TrendDirection.DECLINING
    
    def _format_status_counts(self, counts: Dict[str, int]) -> str:
        """Format status counts for display."""
        lines = []
        for status, count in sorted(counts.items()):
            lines.append(f"- {status}: {count}")
        return "\n".join(lines) if lines else "- No initiatives found"
    
    def _format_recommendations(self, count: int) -> str:
        """Format recommendations count."""
        if count == 0:
            return "No pending recommendations."
        return f"{count} pending recommendations require attention."
    
    def _generate_health_assessment(self, health: Optional[float]) -> str:
        """Generate health assessment text."""
        if health is None:
            return "Health score not available. Please ensure initiatives have health scores calculated."
        elif health >= 80:
            return "Portfolio health is good. Continue current practices and monitor for changes."
        elif health >= 60:
            return "Portfolio health is moderate. Review at-risk initiatives and implement improvements."
        else:
            return "Portfolio health requires attention. Immediate action recommended on critical items."
    
    def _extract_highlights(self, data: Dict[str, Any]) -> List[str]:
        """Extract key highlights from data."""
        highlights = []
        
        if data.get("initiative"):
            init = data["initiative"]
            highlights.append(f"Initiative '{init['title']}' is {init['status']}")
            highlights.append(f"Progress: {init['progress']:.1f}%")
        
        counts = data.get("initiative_counts", {})
        if counts:
            total = sum(counts.values())
            highlights.append(f"Portfolio has {total} initiatives")
        
        return highlights
    
    def _extract_attention_items(self, data: Dict[str, Any]) -> List[str]:
        """Extract items requiring attention."""
        items = []
        
        critical = data.get("critical_insights_count", 0)
        if critical > 0:
            items.append(f"{critical} critical insights require immediate attention")
        
        pending = data.get("pending_recommendations_count", 0)
        if pending > 0:
            items.append(f"{pending} pending recommendations need review")
        
        health = data.get("health_score")
        if health is not None and health < 60:
            items.append(f"Portfolio health below threshold at {health:.1f}/100")
        
        return items
    
    def _generate_evidence_refs(self, data: Dict[str, Any]) -> List[str]:
        """Generate evidence references."""
        refs = []
        
        if data.get("initiative_id"):
            refs.append(f"initiative:{data['initiative_id']}")
        
        refs.append(f"timestamp:{data.get('timestamp')}")
        
        return refs


class KPIService:
    """
    PI_CALC Service - KPI Calculations
    
    Calculates benefits realization, predictability metrics,
    adoption velocity, and other portfolio KPIs.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def calculate_kpis(
        self,
        kpi_types: Optional[List[KPIType]] = None,
        initiative_id: Optional[str] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate requested KPIs.
        
        Args:
            kpi_types: List of KPI types to calculate (None for all)
            initiative_id: Optional initiative ID to calculate for
            period_start: Optional period start date
            period_end: Optional period end date
            
        Returns:
            List of calculated KPI results
        """
        results = []
        
        if kpi_types is None:
            kpi_types = list(KPIType)
        
        for kpi_type in kpi_types:
            try:
                kpi_result = await self._calculate_single_kpi(
                    kpi_type, initiative_id, period_start, period_end
                )
                if kpi_result:
                    results.append(kpi_result)
            except Exception as e:
                # Log error but continue with other KPIs
                print(f"Error calculating KPI {kpi_type.value}: {str(e)}")
                continue
        
        return results
    
    async def _calculate_single_kpi(
        self,
        kpi_type: KPIType,
        initiative_id: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date]
    ) -> Optional[Dict[str, Any]]:
        """Calculate a single KPI."""
        
        if kpi_type == KPIType.BENEFITS_REALIZATION:
            return await self._calculate_benefits_realization(initiative_id, period_start, period_end)
        elif kpi_type == KPIType.MILESTONE_HIT_RATE:
            return await self._calculate_milestone_hit_rate(initiative_id, period_start, period_end)
        elif kpi_type == KPIType.DECISION_TURNAROUND:
            return await self._calculate_decision_turnaround(initiative_id, period_start, period_end)
        elif kpi_type == KPIType.DELIVERY_CONFIDENCE:
            return await self._calculate_delivery_confidence(initiative_id)
        elif kpi_type == KPIType.ADOPTION_VELOCITY:
            return await self._calculate_adoption_velocity(initiative_id, period_start, period_end)
        elif kpi_type == KPIType.BUDGET_VARIANCE:
            return await self._calculate_budget_variance(initiative_id)
        elif kpi_type == KPIType.RISK_DENSITY:
            return await self._calculate_risk_density(initiative_id)
        else:
            return None
    
    async def _calculate_benefits_realization(
        self,
        initiative_id: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date]
    ) -> Dict[str, Any]:
        """Calculate benefits realization KPI."""
        
        query = select(Benefit)
        
        if initiative_id:
            query = query.where(Benefit.initiative_id == initiative_id)
        
        result = await self.db.execute(query)
        benefits = result.scalars().all()
        
        total_target = sum(b.target_value or 0 for b in benefits)
        total_current = sum(b.current_value or 0 for b in benefits)
        
        realization_pct = (total_current / total_target * 100) if total_target > 0 else 0
        
        return {
            "kpi_type": KPIType.BENEFITS_REALIZATION.value,
            "kpi_category": KPICategory.BENEFITS.value,
            "initiative_id": initiative_id,
            "metric_name": "Benefits Realization Rate",
            "metric_value": round(realization_pct, 2),
            "target_value": 100.0,
            "unit": "percent",
            "trend_direction": TrendDirection.IMPROVING.value if realization_pct >= 80 else TrendDirection.STABLE.value,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "calculation_method": "current_value / target_value * 100",
            "factors": {
                "total_benefits": len(benefits),
                "total_target_value": total_target,
                "total_current_value": total_current
            }
        }
    
    async def _calculate_milestone_hit_rate(
        self,
        initiative_id: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date]
    ) -> Dict[str, Any]:
        """Calculate milestone hit rate KPI."""
        
        query = select(Milestone)
        
        if initiative_id:
            query = query.where(Milestone.initiative_id == initiative_id)
        
        if period_start and period_end:
            query = query.where(
                and_(
                    Milestone.due_date >= period_start,
                    Milestone.due_date <= period_end
                )
            )
        
        result = await self.db.execute(query)
        milestones = result.scalars().all()
        
        total = len(milestones)
        completed = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED.value)
        missed = sum(1 for m in milestones if m.status == MilestoneStatus.MISSED.value)
        
        hit_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "kpi_type": KPIType.MILESTONE_HIT_RATE.value,
            "kpi_category": KPICategory.DELIVERY.value,
            "initiative_id": initiative_id,
            "metric_name": "Milestone Hit Rate",
            "metric_value": round(hit_rate, 2),
            "target_value": 90.0,
            "unit": "percent",
            "trend_direction": TrendDirection.IMPROVING.value if hit_rate >= 80 else TrendDirection.STABLE.value,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "calculation_method": "completed_milestones / total_milestones * 100",
            "factors": {
                "total_milestones": total,
                "completed_milestones": completed,
                "missed_milestones": missed
            }
        }
    
    async def _calculate_decision_turnaround(
        self,
        initiative_id: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date]
    ) -> Dict[str, Any]:
        """Calculate decision turnaround time KPI."""
        
        query = select(Decision).where(
            Decision.status.in_([DecisionStatus.APPROVED.value, DecisionStatus.REJECTED.value])
        )
        
        if initiative_id:
            query = query.where(Decision.initiative_id == initiative_id)
        
        if period_start and period_end:
            query = query.where(
                and_(
                    Decision.decided_at >= period_start,
                    Decision.decided_at <= period_end
                )
            )
        
        result = await self.db.execute(query)
        decisions = result.scalars().all()
        
        turnaround_hours = [d.turnaround_hours for d in decisions if d.turnaround_hours is not None]
        
        avg_turnaround = sum(turnaround_hours) / len(turnaround_hours) if turnaround_hours else 0
        
        return {
            "kpi_type": KPIType.DECISION_TURNAROUND.value,
            "kpi_category": KPICategory.DELIVERY.value,
            "initiative_id": initiative_id,
            "metric_name": "Average Decision Turnaround Time",
            "metric_value": round(avg_turnaround, 2),
            "target_value": 48.0,  # 48 hours target
            "unit": "hours",
            "trend_direction": TrendDirection.IMPROVING.value if avg_turnaround <= 48 else TrendDirection.DECLINING.value,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "calculation_method": "average(turnaround_hours)",
            "factors": {
                "total_decisions": len(decisions),
                "decisions_with_turnaround": len(turnaround_hours)
            }
        }
    
    async def _calculate_delivery_confidence(self, initiative_id: Optional[str]) -> Dict[str, Any]:
        """Calculate delivery confidence KPI."""
        
        query = select(Initiative)
        
        if initiative_id:
            query = query.where(Initiative.id == initiative_id)
        
        result = await self.db.execute(query)
        initiatives = result.scalars().all()
        
        total = len(initiatives)
        on_track = sum(1 for i in initiatives if i.status == InitiativeStatus.ON_TRACK.value)
        
        confidence = (on_track / total * 100) if total > 0 else 0
        
        return {
            "kpi_type": KPIType.DELIVERY_CONFIDENCE.value,
            "kpi_category": KPICategory.DELIVERY.value,
            "initiative_id": initiative_id,
            "metric_name": "Delivery Confidence",
            "metric_value": round(confidence, 2),
            "target_value": 85.0,
            "unit": "percent",
            "trend_direction": TrendDirection.IMPROVING.value if confidence >= 80 else TrendDirection.STABLE.value,
            "calculation_method": "on_track_initiatives / total_initiatives * 100",
            "factors": {
                "total_initiatives": total,
                "on_track_initiatives": on_track
            }
        }
    
    async def _calculate_adoption_velocity(
        self,
        initiative_id: Optional[str],
        period_start: Optional[date],
        period_end: Optional[date]
    ) -> Dict[str, Any]:
        """Calculate adoption velocity KPI."""
        
        query = select(AdoptionSignal)
        
        if initiative_id:
            query = query.where(AdoptionSignal.initiative_id == initiative_id)
        
        if period_start and period_end:
            query = query.where(
                and_(
                    AdoptionSignal.timestamp >= period_start,
                    AdoptionSignal.timestamp <= period_end
                )
            )
        
        result = await self.db.execute(query)
        signals = result.scalars().all()
        
        # Calculate signals per week
        if period_start and period_end:
            days = (period_end - period_start).days
            weeks = max(days / 7, 1)
        else:
            weeks = 4  # Default to 4 weeks
        
        velocity = len(signals) / weeks
        
        return {
            "kpi_type": KPIType.ADOPTION_VELOCITY.value,
            "kpi_category": KPICategory.ADOPTION.value,
            "initiative_id": initiative_id,
            "metric_name": "Adoption Velocity",
            "metric_value": round(velocity, 2),
            "target_value": 10.0,  # 10 signals per week target
            "unit": "signals_per_week",
            "trend_direction": TrendDirection.IMPROVING.value if velocity >= 8 else TrendDirection.STABLE.value,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "calculation_method": "total_signals / weeks_in_period",
            "factors": {
                "total_signals": len(signals),
                "weeks": weeks
            }
        }
    
    async def _calculate_budget_variance(self, initiative_id: Optional[str]) -> Dict[str, Any]:
        """Calculate budget variance KPI."""
        
        query = select(Initiative)
        
        if initiative_id:
            query = query.where(Initiative.id == initiative_id)
        
        result = await self.db.execute(query)
        initiatives = result.scalars().all()
        
        total_allocated = sum(i.budget_allocated or 0 for i in initiatives)
        total_spent = sum(i.budget_spent or 0 for i in initiatives)
        
        variance = total_allocated - total_spent
        variance_pct = (variance / total_allocated * 100) if total_allocated > 0 else 0
        
        return {
            "kpi_type": KPIType.BUDGET_VARIANCE.value,
            "kpi_category": KPICategory.FINANCIAL.value,
            "initiative_id": initiative_id,
            "metric_name": "Budget Variance",
            "metric_value": round(variance, 2),
            "target_value": 0.0,
            "unit": "currency",
            "trend_direction": TrendDirection.IMPROVING.value if variance >= 0 else TrendDirection.DECLINING.value,
            "calculation_method": "allocated - spent",
            "factors": {
                "total_allocated": total_allocated,
                "total_spent": total_spent,
                "variance_percentage": round(variance_pct, 2)
            }
        }
    
    async def _calculate_risk_density(self, initiative_id: Optional[str]) -> Dict[str, Any]:
        """Calculate risk density KPI."""
        
        query = select(Risk).where(
            Risk.status.notin_([RiskStatus.RESOLVED.value, RiskStatus.ACCEPTED.value])
        )
        
        if initiative_id:
            query = query.where(Risk.initiative_id == initiative_id)
        
        result = await self.db.execute(query)
        risks = result.scalars().all()
        
        # Count initiatives
        init_query = select(Initiative)
        if initiative_id:
            init_query = init_query.where(Initiative.id == initiative_id)
        
        init_result = await self.db.execute(init_query)
        initiatives = init_result.scalars().all()
        
        total_initiatives = len(initiatives)
        total_risks = len(risks)
        
        density = (total_risks / total_initiatives) if total_initiatives > 0 else 0
        
        return {
            "kpi_type": KPIType.RISK_DENSITY.value,
            "kpi_category": KPICategory.RISK.value,
            "initiative_id": initiative_id,
            "metric_name": "Risk Density",
            "metric_value": round(density, 2),
            "target_value": 2.0,  # 2 risks per initiative max
            "unit": "risks_per_initiative",
            "trend_direction": TrendDirection.IMPROVING.value if density <= 2 else TrendDirection.DECLINING.value,
            "calculation_method": "total_risks / total_initiatives",
            "factors": {
                "total_risks": total_risks,
                "total_initiatives": total_initiatives
            }
        }


class InsightsService:
    """
    Main Insights Service - Orchestrates PI_DETECT, PI_RECOMMEND, PI_NARRATIVE, and PI_CALC
    
    Provides a unified interface for all insights engine operations.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.detection_service = DetectionService(db)
        self.recommendation_service = RecommendationService(db)
        self.narrative_service = NarrativeService(db)
        self.kpi_service = KPIService(db)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Detection Operations (PI_DETECT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def detect_delays(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Detect delays in initiatives and milestones."""
        return await self.detection_service.detect_delays(initiative_id)
    
    async def detect_blockers(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Detect blockers including circular dependencies."""
        return await self.detection_service.detect_blockers(initiative_id)
    
    async def detect_stalled_work(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Detect stalled initiatives with no recent updates."""
        return await self.detection_service.detect_stalled_work(initiative_id)
    
    async def detect_risk_escalations(self, initiative_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Detect risk escalations beyond threshold."""
        return await self.detection_service.detect_risk_escalations(initiative_id)
    
    async def run_full_detection(self, initiative_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all detection algorithms and return comprehensive results.
        
        Args:
            initiative_id: Optional initiative ID to focus on
            
        Returns:
            Dictionary with all detection results
        """
        delays = await self.detect_delays(initiative_id)
        blockers = await self.detect_blockers(initiative_id)
        stalled = await self.detect_stalled_work(initiative_id)
        risks = await self.detect_risk_escalations(initiative_id)
        
        all_signals = delays + blockers + stalled + risks
        
        return {
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "initiative_id": initiative_id,
            "summary": {
                "total_signals": len(all_signals),
                "delay_signals": len(delays),
                "blocker_signals": len(blockers),
                "stall_signals": len(stalled),
                "risk_escalations": len(risks),
                "critical_count": sum(1 for s in all_signals if s.get("severity") == InsightSeverity.CRITICAL.value),
                "high_count": sum(1 for s in all_signals if s.get("severity") == InsightSeverity.HIGH.value)
            },
            "signals": {
                "delays": delays,
                "blockers": blockers,
                "stalled": stalled,
                "risk_escalations": risks
            }
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Recommendation Operations (PI_RECOMMEND)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def generate_recommendations(
        self,
        initiative_id: Optional[str] = None,
        insight_id: Optional[str] = None,
        max_recommendations: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on insights."""
        return await self.recommendation_service.generate_recommendations(
            initiative_id, insight_id, max_recommendations
        )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # Narrative Operations (PI_NARRATIVE)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def generate_executive_narrative(
        self,
        narrative_type: NarrativeType = NarrativeType.EXECUTIVE,
        audience: NarrativeAudience = NarrativeAudience.EXECUTIVE,
        initiative_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate an executive narrative."""
        return await self.narrative_service.generate_executive_narrative(
            narrative_type, audience, initiative_id
        )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # KPI Operations (PI_CALC)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def calculate_kpis(
        self,
        kpi_types: Optional[List[KPIType]] = None,
        initiative_id: Optional[str] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Calculate KPIs."""
        return await self.kpi_service.calculate_kpis(kpi_types, initiative_id, period_start, period_end)
    
    async def get_portfolio_health_summary(self) -> Dict[str, Any]:
        """Get a comprehensive portfolio health summary."""
        
        # Get initiative counts
        result = await self.db.execute(
            select(Initiative.status, func.count(Initiative.id))
            .group_by(Initiative.status)
        )
        status_counts = {row[0]: row[1] for row in result.all()}
        
        # Get average health score
        result = await self.db.execute(
            select(func.avg(Initiative.health_score))
            .where(Initiative.health_score.isnot(None))
        )
        avg_health = result.scalar()
        
        # Get active insights
        result = await self.db.execute(
            select(func.count(Insight.id))
            .where(Insight.status == InsightStatus.ACTIVE.value)
        )
        active_insights = result.scalar()
        
        # Get critical insights
        result = await self.db.execute(
            select(func.count(Insight.id))
            .where(
                and_(
                    Insight.status == InsightStatus.ACTIVE.value,
                    Insight.severity == InsightSeverity.CRITICAL.value
                )
            )
        )
        critical_insights = result.scalar()
        
        # Calculate KPIs
        kpis = await self.calculate_kpis()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "initiative_counts": status_counts,
            "average_health_score": round(avg_health, 2) if avg_health else None,
            "active_insights": active_insights,
            "critical_insights": critical_insights,
            "kpis": kpis
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Service Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_insights_service(db: AsyncSession) -> InsightsService:
    """Factory function to create an InsightsService instance."""
    return InsightsService(db)


def get_detection_service(db: AsyncSession) -> DetectionService:
    """Factory function to create a DetectionService instance."""
    return DetectionService(db)


def get_recommendation_service(db: AsyncSession) -> RecommendationService:
    """Factory function to create a RecommendationService instance."""
    return RecommendationService(db)


def get_narrative_service(db: AsyncSession) -> NarrativeService:
    """Factory function to create a NarrativeService instance."""
    return NarrativeService(db)


def get_kpi_service(db: AsyncSession) -> KPIService:
    """Factory function to create a KPIService instance."""
    return KPIService(db)
