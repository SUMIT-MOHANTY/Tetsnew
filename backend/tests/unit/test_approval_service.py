"""
DERTOUR Approval Service Unit Tests
Tests for agent submission validation, evidence schema compliance, and decision state transitions
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.approval_service import ApprovalService
from app.schemas.approval import (
    AgentActionSubmit,
    EvidenceCapture,
    ApprovalDecision,
    ApprovalStatus,
    RequestType,
    Decision,
)


@pytest.fixture
def approval_service():
    """Create an approval service instance."""
    return ApprovalService()


@pytest.fixture
def valid_evidence_data():
    """Valid evidence data for testing."""
    return {
        "data_sources": ["milestone_tracker", "dependency_graph"],
        "reasoning_steps": ["Step 1: Analyze data", "Step 2: Calculate impact"],
        "alternative_considered": ["Option A: Do nothing", "Option B: Delay"],
        "risk_assessment": "Low risk - well understood change",
    }


@pytest.fixture
def valid_agent_action_data(valid_evidence_data):
    """Valid agent action submission data."""
    return {
        "plan": "Update milestone dates for initiative TEST-001",
        "evidence": valid_evidence_data,
        "confidence": 0.85,
        "tool_activity": "milestone_analyzer_v2.3 -> date_calculator",
        "request_type": RequestType.MATERIAL_ACTION,
        "initiative_id": str(uuid4()),
    }


class TestAgentActionSubmission:
    """Tests for agent action submission validation."""

    def test_validate_confidence_score_valid(self, approval_service):
        """Test that valid confidence scores are accepted."""
        # Valid confidence scores
        assert approval_service._validate_confidence(0.0) == 0.0
        assert approval_service._validate_confidence(0.5) == 0.5
        assert approval_service._validate_confidence(1.0) == 1.0
        assert approval_service._validate_confidence(0.85) == 0.85

    def test_validate_confidence_score_invalid(self, approval_service):
        """Test that invalid confidence scores are rejected."""
        # Negative confidence
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            approval_service._validate_confidence(-0.1)
        
        # Confidence > 1.0
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            approval_service._validate_confidence(1.1)

    def test_validate_evidence_schema_complete(self, approval_service, valid_evidence_data):
        """Test that complete evidence schema passes validation."""
        result = approval_service._validate_evidence_schema(valid_evidence_data)
        assert result is True

    def test_validate_evidence_schema_missing_fields(self, approval_service):
        """Test that incomplete evidence schema is rejected."""
        # Missing required fields
        incomplete_evidence = {
            "data_sources": ["source1"],
            # Missing reasoning_steps, alternative_considered, risk_assessment
        }
        
        with pytest.raises(ValueError, match="Missing required evidence field"):
            approval_service._validate_evidence_schema(incomplete_evidence)

    def test_validate_evidence_schema_empty_data_sources(self, approval_service):
        """Test that empty data_sources is rejected."""
        evidence = {
            "data_sources": [],
            "reasoning_steps": ["Step 1"],
            "alternative_considered": ["Option A"],
            "risk_assessment": "Low",
        }
        
        with pytest.raises(ValueError, match="data_sources must contain at least one source"):
            approval_service._validate_evidence_schema(evidence)

    def test_validate_evidence_schema_empty_reasoning(self, approval_service):
        """Test that empty reasoning_steps is rejected."""
        evidence = {
            "data_sources": ["source1"],
            "reasoning_steps": [],
            "alternative_considered": ["Option A"],
            "risk_assessment": "Low",
        }
        
        with pytest.raises(ValueError, match="reasoning_steps must contain at least one step"):
            approval_service._validate_evidence_schema(evidence)

    @pytest.mark.asyncio
    async def test_submit_agent_action_success(self, approval_service, valid_agent_action_data):
        """Test successful agent action submission."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        with patch.object(approval_service, '_create_audit_log', new_callable=AsyncMock):
            result = await approval_service.submit_agent_action(
                db=mock_db,
                data=AgentActionSubmit(**valid_agent_action_data),
                requester_id=str(uuid4()),
            )
            
            assert result is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()


class TestEvidenceImmutability:
    """Tests for evidence immutability enforcement."""

    def test_evidence_cannot_be_modified_after_submission(self, approval_service):
        """Test that evidence is immutable after submission."""
        original_evidence = {
            "data_sources": ["source1"],
            "reasoning_steps": ["Step 1"],
            "alternative_considered": ["Option A"],
            "risk_assessment": "Low",
        }
        
        # Attempt to modify evidence should raise error
        with pytest.raises(RuntimeError, match="Evidence is immutable after submission"):
            approval_service._validate_evidence_modification(
                original_evidence,
                {"data_sources": ["modified_source"]},
            )

    def test_evidence_hash_generation(self, approval_service, valid_evidence_data):
        """Test that evidence generates consistent hash."""
        hash1 = approval_service._generate_evidence_hash(valid_evidence_data)
        hash2 = approval_service._generate_evidence_hash(valid_evidence_data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string length

    def test_evidence_hash_changes_with_content(self, approval_service, valid_evidence_data):
        """Test that evidence hash changes when content changes."""
        hash1 = approval_service._generate_evidence_hash(valid_evidence_data)
        
        modified_evidence = valid_evidence_data.copy()
        modified_evidence["risk_assessment"] = "Modified risk"
        
        hash2 = approval_service._generate_evidence_hash(modified_evidence)
        
        assert hash1 != hash2


class TestDecisionStateTransitions:
    """Tests for approval decision state transitions."""

    def test_valid_state_transitions(self, approval_service):
        """Test valid state transitions."""
        # APP_SUBMIT -> APP_AGENT
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_SUBMIT,
            ApprovalStatus.APP_AGENT,
        ) is True
        
        # APP_AGENT -> APP_HUMAN
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_AGENT,
            ApprovalStatus.APP_HUMAN,
        ) is True
        
        # APP_HUMAN -> APP_DECIDE
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_HUMAN,
            ApprovalStatus.APP_DECIDE,
        ) is True
        
        # APP_DECIDE -> APPROVED
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_DECIDE,
            ApprovalStatus.APPROVED,
        ) is True
        
        # APP_DECIDE -> REJECTED
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_DECIDE,
            ApprovalStatus.REJECTED,
        ) is True

    def test_invalid_state_transitions(self, approval_service):
        """Test invalid state transitions are rejected."""
        # Cannot skip APP_AGENT
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_SUBMIT,
            ApprovalStatus.APP_HUMAN,
        ) is False
        
        # Cannot skip to APPROVED
        assert approval_service._is_valid_transition(
            ApprovalStatus.APP_SUBMIT,
            ApprovalStatus.APPROVED,
        ) is False
        
        # Cannot go backwards
        assert approval_service._is_valid_transition(
            ApprovalStatus.APPROVED,
            ApprovalStatus.APP_DECIDE,
        ) is False
        
        # Cannot transition from terminal states
        assert approval_service._is_valid_transition(
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
        ) is False

    @pytest.mark.asyncio
    async def test_submit_decision_approval(self, approval_service):
        """Test submitting an approval decision."""
        mock_db = AsyncMock()
        approval_id = str(uuid4())
        approver_id = str(uuid4())
        
        # Mock the approval request
        mock_approval = MagicMock()
        mock_approval.id = approval_id
        mock_approval.status = ApprovalStatus.APP_DECIDE
        mock_approval.requester_id = str(uuid4())
        
        with patch.object(approval_service, '_get_approval_request', return_value=mock_approval):
            with patch.object(approval_service, '_create_audit_log', new_callable=AsyncMock):
                result = await approval_service.submit_decision(
                    db=mock_db,
                    approval_id=approval_id,
                    decision_data=ApprovalDecision(
                        decision=Decision.APPROVED,
                        notes="Approved after review",
                    ),
                    approver_id=approver_id,
                )
                
                assert result.status == ApprovalStatus.APPROVED
                assert result.decided_at is not None
                assert result.decision_maker_id == approver_id

    @pytest.mark.asyncio
    async def test_submit_decision_rejection_requires_notes(self, approval_service):
        """Test that rejection requires notes."""
        mock_db = AsyncMock()
        approval_id = str(uuid4())
        
        with pytest.raises(ValueError, match="Notes are required for rejection"):
            await approval_service.submit_decision(
                db=mock_db,
                approval_id=approval_id,
                decision_data=ApprovalDecision(
                    decision=Decision.REJECTED,
                    notes="",  # Empty notes
                ),
                approver_id=str(uuid4()),
            )

    @pytest.mark.asyncio
    async def test_submit_decision_invalid_state(self, approval_service):
        """Test that decisions cannot be made in invalid states."""
        mock_db = AsyncMock()
        approval_id = str(uuid4())
        
        # Mock the approval request in wrong state
        mock_approval = MagicMock()
        mock_approval.id = approval_id
        mock_approval.status = ApprovalStatus.APPROVED  # Already approved
        
        with patch.object(approval_service, '_get_approval_request', return_value=mock_approval):
            with pytest.raises(ValueError, match="Invalid state transition"):
                await approval_service.submit_decision(
                    db=mock_db,
                    approval_id=approval_id,
                    decision_data=ApprovalDecision(
                        decision=Decision.REJECTED,
                        notes="Trying to reject already approved request",
                    ),
                    approver_id=str(uuid4()),
                )


class TestRoleBasedAccess:
    """Tests for role-based approval access."""

    def test_executive_can_approve_all_types(self, approval_service):
        """Test that executives can approve all request types."""
        assert approval_service._can_role_approve("EXECUTIVE", RequestType.MATERIAL_ACTION) is True
        assert approval_service._can_role_approve("EXECUTIVE", RequestType.BUDGET_CHANGE) is True
        assert approval_service._can_role_approve("EXECUTIVE", RequestType.SCOPE_CHANGE) is True

    def test_pmo_can_approve_operational(self, approval_service):
        """Test that PMO can approve operational requests."""
        assert approval_service._can_role_approve("PMO", RequestType.MATERIAL_ACTION) is True
        assert approval_service._can_role_approve("PMO", RequestType.BUDGET_CHANGE) is True
        assert approval_service._can_role_approve("PMO", RequestType.SCOPE_CHANGE) is False

    def test_team_lead_limited_approval(self, approval_service):
        """Test that team leads have limited approval rights."""
        assert approval_service._can_role_approve("TEAM_LEAD", RequestType.MATERIAL_ACTION) is True
        assert approval_service._can_role_approve("TEAM_LEAD", RequestType.BUDGET_CHANGE) is False
        assert approval_service._can_role_approve("TEAM_LEAD", RequestType.SCOPE_CHANGE) is False

    def test_team_member_cannot_approve(self, approval_service):
        """Test that team members cannot approve."""
        assert approval_service._can_role_approve("TEAM_MEMBER", RequestType.MATERIAL_ACTION) is False
        assert approval_service._can_role_approve("TEAM_MEMBER", RequestType.BUDGET_CHANGE) is False


class TestTimeoutEscalation:
    """Tests for timeout and escalation handling."""

    def test_calculate_timeout_standard(self, approval_service):
        """Test standard timeout calculation."""
        submitted_at = datetime.utcnow()
        timeout = approval_service._calculate_timeout(
            RequestType.MATERIAL_ACTION,
            submitted_at,
        )
        
        # Standard MATERIAL_ACTION timeout is 24 hours
        expected_timeout = submitted_at + timedelta(hours=24)
        assert abs((timeout - expected_timeout).total_seconds()) < 1

    def test_calculate_timeout_budget_change(self, approval_service):
        """Test budget change timeout calculation."""
        submitted_at = datetime.utcnow()
        timeout = approval_service._calculate_timeout(
            RequestType.BUDGET_CHANGE,
            submitted_at,
        )
        
        # BUDGET_CHANGE timeout is 48 hours
        expected_timeout = submitted_at + timedelta(hours=48)
        assert abs((timeout - expected_timeout).total_seconds()) < 1

    def test_calculate_timeout_scope_change(self, approval_service):
        """Test scope change timeout calculation."""
        submitted_at = datetime.utcnow()
        timeout = approval_service._calculate_timeout(
            RequestType.SCOPE_CHANGE,
            submitted_at,
        )
        
        # SCOPE_CHANGE timeout is 72 hours
        expected_timeout = submitted_at + timedelta(hours=72)
        assert abs((timeout - expected_timeout).total_seconds()) < 1

    def test_is_timed_out(self, approval_service):
        """Test timeout detection."""
        # Past timeout
        past_timeout = datetime.utcnow() - timedelta(hours=1)
        assert approval_service._is_timed_out(past_timeout) is True
        
        # Future timeout
        future_timeout = datetime.utcnow() + timedelta(hours=1)
        assert approval_service._is_timed_out(future_timeout) is False

    @pytest.mark.asyncio
    async def test_escalate_overdue_approvals(self, approval_service):
        """Test escalation of overdue approvals."""
        mock_db = AsyncMock()
        
        # Mock overdue approvals
        overdue_approval = MagicMock()
        overdue_approval.id = str(uuid4())
        overdue_approval.status = ApprovalStatus.APP_HUMAN
        overdue_approval.timeout_at = datetime.utcnow() - timedelta(hours=1)
        
        with patch.object(approval_service, '_get_overdue_approvals', return_value=[overdue_approval]):
            with patch.object(approval_service, '_create_audit_log', new_callable=AsyncMock):
                with patch.object(approval_service, '_send_escalation_notification', new_callable=AsyncMock):
                    escalated = await approval_service.escalate_overdue_approvals(mock_db)
                    
                    assert len(escalated) == 1
                    assert overdue_approval.status == ApprovalStatus.ESCALATED


class TestAuditLogging:
    """Tests for audit logging functionality."""

    @pytest.mark.asyncio
    async def test_create_audit_log_entry(self, approval_service):
        """Test audit log entry creation."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        
        await approval_service._create_audit_log(
            db=mock_db,
            entity_type="ApprovalRequest",
            entity_id=str(uuid4()),
            action="CREATE",
            actor_type="USER",
            actor_id=str(uuid4()),
            before_state=None,
            after_state={"status": "APP_SUBMIT"},
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_generate_changes_diff(self, approval_service):
        """Test generation of changes diff."""
        before = {"status": "APP_SUBMIT", "confidence": 0.5}
        after = {"status": "APP_AGENT", "confidence": 0.5}
        
        diff = approval_service._generate_changes_diff(before, after)
        
        assert "status" in diff
        assert diff["status"]["before"] == "APP_SUBMIT"
        assert diff["status"]["after"] == "APP_AGENT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
