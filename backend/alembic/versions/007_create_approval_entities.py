"""
DERTOUR Approval Workflow & Audit Logging Migration
Revision ID: 007
Revises: 006_create_insight_signals
Create Date: 2024-01-25 10:00:00.000000

Creates approval workflow tables for human-in-the-loop AI governance:
- agent_actions: AI agent action requests with evidence capture
- approval_steps: Multi-step approval workflow with role-based routing
- audit_logs: Comprehensive audit trail with tamper detection
- notifications: User notification system for approval events
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create approval workflow tables with indexes."""
    
    # Create agent_actions table - AI agent action requests with evidence
    op.create_table(
        'agent_actions',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('plan', sa.Text, nullable=False),
        sa.Column('evidence', postgresql.JSONB, nullable=True),
        sa.Column('confidence', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('tool_activity', sa.Text, nullable=True),
        sa.Column('request_type', sa.String(50), nullable=False, server_default='MATERIAL_ACTION'),
        sa.Column('initiative_id', sa.String(36), sa.ForeignKey(
            'initiatives.id', ondelete='CASCADE'
        ), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='APP_SUBMIT', index=True),
        sa.Column('requester_id', sa.String(36), sa.ForeignKey(
            'users.id', ondelete='CASCADE'
        ), nullable=False, index=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_maker_id', sa.String(36), sa.ForeignKey(
            'users.id', ondelete='SET NULL'
        ), nullable=True, index=True),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
    )
    
    # Create indexes for agent_actions table
    op.create_index('ix_agent_actions_status', 'agent_actions', ['status'])
    op.create_index('ix_agent_actions_initiative_id', 'agent_actions', ['initiative_id'])
    op.create_index('ix_agent_actions_requester_id', 'agent_actions', ['requester_id'])
    op.create_index('ix_agent_actions_decision_maker_id', 'agent_actions', ['decision_maker_id'])
    op.create_index('ix_agent_actions_submitted_at', 'agent_actions', ['submitted_at'])
    op.create_index('ix_agent_actions_status_initiative', 'agent_actions', ['status', 'initiative_id'])
    op.create_index('ix_agent_actions_timeout_at', 'agent_actions', ['timeout_at'])
    
    # Create approval_steps table - multi-step approval workflow
    op.create_table(
        'approval_steps',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('request_id', sa.String(36), sa.ForeignKey(
            'agent_actions.id', ondelete='CASCADE'
        ), nullable=False, index=True),
        sa.Column('step_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('approver_role', sa.String(50), nullable=False),
        sa.Column('decision', sa.String(50), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('comments', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
    )
    
    # Create indexes for approval_steps table
    op.create_index('ix_approval_steps_request_id', 'approval_steps', ['request_id'])
    op.create_index('ix_approval_steps_step_order', 'approval_steps', ['step_order'])
    op.create_index('ix_approval_steps_approver_role', 'approval_steps', ['approver_role'])
    op.create_index('ix_approval_steps_decision', 'approval_steps', ['decision'])
    op.create_index('ix_approval_steps_request_order', 'approval_steps', ['request_id', 'step_order'], unique=True)
    
    # Create audit_logs table - comprehensive audit trail with tamper detection
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False, index=True),
        sa.Column('entity_id', sa.String(36), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('actor_type', sa.String(50), nullable=False, server_default='USER', index=True),
        sa.Column('actor_id', sa.String(100), nullable=False, index=True),
        sa.Column('before_state', postgresql.JSONB, nullable=True),
        sa.Column('after_state', postgresql.JSONB, nullable=True),
        sa.Column('changes_diff', postgresql.JSONB, nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('integrity_hash', sa.String(64), nullable=False),
        sa.Column('previous_hash', sa.String(64), nullable=True, index=True),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for audit_logs table
    op.create_index('ix_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_actor', 'audit_logs', ['actor_type', 'actor_id'])
    op.create_index('ix_audit_logs_performed_at', 'audit_logs', ['performed_at'])
    op.create_index('ix_audit_logs_session', 'audit_logs', ['session_id'])
    op.create_index('ix_audit_logs_integrity_chain', 'audit_logs', ['previous_hash'])
    
    # Create notifications table - user notification system
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey(
            'users.id', ondelete='CASCADE'
        ), nullable=False, index=True),
        sa.Column('notification_type', sa.String(50), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('is_read', sa.Boolean, nullable=False, server_default='false', index=True),
        sa.Column('is_dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('priority', sa.String(50), nullable=False, server_default='Medium', index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
    )
    
    # Create indexes for notifications table
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_type', 'notifications', ['notification_type'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_priority', 'notifications', ['priority'])
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    op.create_index('ix_notifications_entity', 'notifications', ['entity_type', 'entity_id'])


def downgrade() -> None:
    """Drop approval workflow tables."""
    
    # Drop notifications table indexes and table
    op.drop_index('ix_notifications_entity', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index('ix_notifications_priority', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
    
    # Drop audit_logs table indexes and table
    op.drop_index('ix_audit_logs_integrity_chain', table_name='audit_logs')
    op.drop_index('ix_audit_logs_session', table_name='audit_logs')
    op.drop_index('ix_audit_logs_performed_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    # Drop approval_steps table indexes and table
    op.drop_index('ix_approval_steps_request_order', table_name='approval_steps')
    op.drop_index('ix_approval_steps_decision', table_name='approval_steps')
    op.drop_index('ix_approval_steps_approver_role', table_name='approval_steps')
    op.drop_index('ix_approval_steps_step_order', table_name='approval_steps')
    op.drop_index('ix_approval_steps_request_id', table_name='approval_steps')
    op.drop_table('approval_steps')
    
    # Drop agent_actions table indexes and table
    op.drop_index('ix_agent_actions_timeout_at', table_name='agent_actions')
    op.drop_index('ix_agent_actions_status_initiative', table_name='agent_actions')
    op.drop_index('ix_agent_actions_submitted_at', table_name='agent_actions')
    op.drop_index('ix_agent_actions_decision_maker_id', table_name='agent_actions')
    op.drop_index('ix_agent_actions_requester_id', table_name='agent_actions')
    op.drop_index('ix_agent_actions_initiative_id', table_name='agent_actions')
    op.drop_index('ix_agent_actions_status', table_name='agent_actions')
    op.drop_table('agent_actions')
