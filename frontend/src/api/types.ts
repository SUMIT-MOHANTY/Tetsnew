/**
 * API Types
 *
 * TypeScript interfaces matching backend Pydantic schemas
 */

// =============================================================================
// Enums (mirroring backend)
// =============================================================================

/**
 * UserRole enum - matches backend UserRole exactly
 * Backend values: Executive, PMO_Manager, Team_Member, Admin
 */
export enum UserRole {
  EXECUTIVE = 'Executive',
  PMO_MANAGER = 'PMO_Manager',
  TEAM_MEMBER = 'Team_Member',
  ADMIN = 'Admin',
}

export enum InitiativeStatus {
  ACTIVE = 'ACTIVE',
  ON_HOLD = 'ON_HOLD',
  BLOCKED = 'BLOCKED',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
}

export enum InitiativePriority {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum MilestoneStatus {
  NOT_STARTED = 'NOT_STARTED',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  DELAYED = 'DELAYED',
  CANCELLED = 'CANCELLED',
}

export enum RiskSeverity {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum RiskStatus {
  OPEN = 'OPEN',
  MITIGATED = 'MITIGATED',
  CLOSED = 'CLOSED',
}

export enum DecisionStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  ESCALATED = 'ESCALATED',
}

export enum DependencyType {
  BLOCKS = 'BLOCKS',
  DEPENDS_ON = 'DEPENDS_ON',
  RELATES_TO = 'RELATES_TO',
}

export enum DependencyStatus {
  ACTIVE = 'ACTIVE',
  RESOLVED = 'RESOLVED',
  BLOCKED = 'BLOCKED',
}

export enum InsightType {
  RISK = 'RISK',
  OPPORTUNITY = 'OPPORTUNITY',
  TREND = 'TREND',
  ANOMALY = 'ANOMALY',
}

export enum InsightSeverity {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum InsightStatus {
  NEW = 'NEW',
  ACKNOWLEDGED = 'ACKNOWLEDGED',
  DISMISSED = 'DISMISSED',
  RESOLVED = 'RESOLVED',
}

export enum ApprovalStatus {
  PENDING = 'PENDING',
  IN_REVIEW = 'IN_REVIEW',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  ESCALATED = 'ESCALATED',
}

export enum SignalType {
  ADOPTION = 'ADOPTION',
  ENGAGEMENT = 'ENGAGEMENT',
  COMPLETION = 'COMPLETION',
  QUALITY = 'QUALITY',
}

export enum AnomalySeverity {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum AnomalyType {
  DELAY = 'DELAY',
  COST_OVERRUN = 'COST_OVERRUN',
  SCOPE_CREEP = 'SCOPE_CREEP',
  QUALITY_ISSUE = 'QUALITY_ISSUE',
  RESOURCE_SHORTAGE = 'RESOURCE_SHORTAGE',
}

export enum TrendDirection {
  IMPROVING = 'IMPROVING',
  STABLE = 'STABLE',
  DECLINING = 'DECLINING',
}

export enum BenefitStatus {
  PLANNED = 'PLANNED',
  IN_PROGRESS = 'IN_PROGRESS',
  REALIZED = 'REALIZED',
  AT_RISK = 'AT_RISK',
}

export enum BenefitType {
  FINANCIAL = 'FINANCIAL',
  OPERATIONAL = 'OPERATIONAL',
  STRATEGIC = 'STRATEGIC',
  COMPLIANCE = 'COMPLIANCE',
}

// =============================================================================
// User Types
// =============================================================================

/**
 * User interface - matches backend UserResponse schema
 */
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

/**
 * LoginRequest interface - matches backend UserLogin schema
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * LoginResponse interface - matches backend TokenResponse schema
 * Note: includes user object in response
 */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

/**
 * TokenResponse interface - alias for LoginResponse
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * UserProfileResponse interface - matches backend UserProfileResponse
 */
export interface UserProfileResponse {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department?: string;
}

/**
 * TokenRefreshRequest interface - matches backend TokenRefreshRequest
 */
export interface TokenRefreshRequest {
  refresh_token: string;
}

/**
 * TokenRefreshResponse interface - matches backend TokenRefreshResponse
 */
export interface TokenRefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * LogoutResponse interface - matches backend LogoutResponse
 */
export interface LogoutResponse {
  message: string;
  success: boolean;
}

// Legacy UserLogin interface (for backward compatibility)
export interface UserLogin {
  email: string;
  password: string;
}

// =============================================================================
// Initiative Types
// =============================================================================

export interface Initiative {
  id: string;
  code: string;
  name: string;
  description?: string;
  status: InitiativeStatus;
  priority: InitiativePriority;
  owner_id: string;
  owner?: User;
  target_start_date?: string;
  target_end_date?: string;
  actual_start_date?: string;
  actual_end_date?: string;
  budget_allocated?: number;
  budget_spent?: number;
  benefits_target?: number;
  benefits_realized?: number;
  progress_percentage: number;
  health_score?: number;
  created_at: string;
  updated_at: string;
}

export interface InitiativeCreate {
  code: string;
  name: string;
  description?: string;
  priority: InitiativePriority;
  owner_id: string;
  target_start_date?: string;
  target_end_date?: string;
  budget_allocated?: number;
  benefits_target?: number;
}

export interface InitiativeUpdate {
  name?: string;
  description?: string;
  status?: InitiativeStatus;
  priority?: InitiativePriority;
  owner_id?: string;
  target_start_date?: string;
  target_end_date?: string;
  budget_allocated?: number;
  benefits_target?: number;
}

export interface InitiativeHealth {
  initiative_id: string;
  health_score: number;
  status: 'HEALTHY' | 'AT_RISK' | 'CRITICAL';
  risk_count: number;
  open_decisions: number;
  delayed_milestones: number;
  last_assessed: string;
}

// =============================================================================
// Milestone Types
// =============================================================================

export interface Milestone {
  id: string;
  initiative_id: string;
  name: string;
  description?: string;
  status: MilestoneStatus;
  target_date: string;
  actual_date?: string;
  completion_percentage: number;
  dependencies?: string[];
  created_at: string;
  updated_at: string;
}

export interface MilestoneCreate {
  initiative_id: string;
  name: string;
  description?: string;
  target_date: string;
}

export interface MilestoneUpdate {
  name?: string;
  description?: string;
  status?: MilestoneStatus;
  target_date?: string;
  actual_date?: string;
  completion_percentage?: number;
}

// =============================================================================
// Risk Types
// =============================================================================

export interface Risk {
  id: string;
  initiative_id: string;
  title: string;
  description?: string;
  severity: RiskSeverity;
  status: RiskStatus;
  probability: number;
  impact: number;
  mitigation_plan?: string;
  owner_id?: string;
  identified_at: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface RiskCreate {
  initiative_id: string;
  title: string;
  description?: string;
  severity: RiskSeverity;
  probability: number;
  impact: number;
  mitigation_plan?: string;
  owner_id?: string;
}

export interface RiskUpdate {
  title?: string;
  description?: string;
  severity?: RiskSeverity;
  status?: RiskStatus;
  probability?: number;
  impact?: number;
  mitigation_plan?: string;
  owner_id?: string;
}

export interface RiskDashboardSummary {
  total_risks: number;
  open_risks: number;
  critical_risks: number;
  high_risks: number;
  recently_identified: number;
  recently_resolved: number;
}

// =============================================================================
// Decision Types
// =============================================================================

export interface Decision {
  id: string;
  initiative_id: string;
  title: string;
  description?: string;
  status: DecisionStatus;
  requested_by_id: string;
  requested_by?: User;
  approved_by_id?: string;
  approved_by?: User;
  requested_at: string;
  decided_at?: string;
  due_date?: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  created_at: string;
  updated_at: string;
}

export interface DecisionCreate {
  initiative_id: string;
  title: string;
  description?: string;
  due_date?: string;
  priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
}

export interface DecisionUpdate {
  title?: string;
  description?: string;
  status?: DecisionStatus;
  due_date?: string;
  priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
}

// =============================================================================
// Dependency Types
// =============================================================================

export interface Dependency {
  id: string;
  source_initiative_id: string;
  source_initiative?: Initiative;
  target_initiative_id: string;
  target_initiative?: Initiative;
  dependency_type: DependencyType;
  status: DependencyStatus;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface DependencyCreate {
  source_initiative_id: string;
  target_initiative_id: string;
  dependency_type: DependencyType;
  description?: string;
}

// =============================================================================
// Benefit Types
// =============================================================================

export interface Benefit {
  id: string;
  initiative_id: string;
  title: string;
  description?: string;
  benefit_type: BenefitType;
  status: BenefitStatus;
  target_value: number;
  realized_value?: number;
  target_date?: string;
  realized_date?: string;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// Insight Types
// =============================================================================

export interface Insight {
  id: string;
  type: InsightType;
  severity: InsightSeverity;
  status: InsightStatus;
  title: string;
  description: string;
  initiative_id?: string;
  initiative?: Initiative;
  confidence_score: number;
  evidence_data?: Record<string, unknown>;
  recommended_action?: string;
  generated_at: string;
  acknowledged_at?: string;
  dismissed_at?: string;
  resolved_at?: string;
}

export interface InsightRecommendation {
  id: string;
  insight_id: string;
  title: string;
  description: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  expected_impact?: string;
  effort_required?: 'LOW' | 'MEDIUM' | 'HIGH';
  created_at: string;
}

// =============================================================================
// Approval Types
// =============================================================================

export interface ApprovalRequest {
  id: string;
  request_type: 'AGENT_ACTION' | 'ESCALATION' | 'MANUAL';
  status: ApprovalStatus;
  title: string;
  description?: string;
  initiative_id?: string;
  initiative?: Initiative;
  requested_by_id: string;
  requested_by?: User;
  reviewed_by_id?: string;
  reviewed_by?: User;
  decided_by_id?: string;
  decided_by?: User;
  submitted_at: string;
  reviewed_at?: string;
  decided_at?: string;
  evidence_data?: Record<string, unknown>;
  agent_plan?: string;
  confidence_score?: number;
  required_roles: UserRole[];
}

export interface ApprovalDecision {
  id: string;
  request_id: string;
  decided_by_id: string;
  decided_by?: User;
  decision: 'APPROVED' | 'REJECTED';
  comment?: string;
  decided_at: string;
}

export interface ApprovalAuditEntry {
  id: string;
  request_id: string;
  actor_id: string;
  actor?: User;
  action: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

// Mock Approval Preview type for Wave 2 placeholder
export interface MockApprovalPreview {
  id: string;
  agentAction: string;
  evidenceSnippet: string;
  confidenceScore: number;
  initiativeName: string;
  submittedAt: string;
}

// =============================================================================
// Adoption & Signals Types
// =============================================================================

export interface AdoptionSignal {
  id: string;
  initiative_id: string;
  initiative?: Initiative;
  signal_type: SignalType;
  value: number;
  recorded_at: string;
  metadata?: Record<string, unknown>;
}

export interface PredictabilityScore {
  id: string;
  initiative_id: string;
  initiative?: Initiative;
  score: number;
  trend: TrendDirection;
  calculated_at: string;
  factors: {
    milestone_adherence: number;
    decision_turnaround: number;
    risk_resolution: number;
    signal_consistency: number;
  };
}

export interface Anomaly {
  id: string;
  initiative_id?: string;
  initiative?: Initiative;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  title: string;
  description: string;
  detected_at: string;
  resolved_at?: string;
  detected_by: string;
  resolution_notes?: string;
}

// =============================================================================
// Dashboard Types
// =============================================================================

export interface DashboardStats {
  total_initiatives: number;
  active_initiatives: number;
  completed_initiatives: number;
  at_risk_initiatives: number;
  blocked_initiatives: number;
  total_budget_allocated: number;
  total_budget_spent: number;
  average_health_score: number;
  open_risks: number;
  pending_decisions: number;
  recent_insights: number;
}

export interface PortfolioHealth {
  overall_score: number;
  status: 'HEALTHY' | 'AT_RISK' | 'CRITICAL';
  initiative_breakdown: {
    healthy: number;
    at_risk: number;
    critical: number;
  };
  trend: TrendDirection;
  period_start: string;
  period_end: string;
}

// =============================================================================
// API Response Types
// =============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  meta?: {
    page?: number;
    page_size?: number;
    total?: number;
    total_pages?: number;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =============================================================================
// Navigation Types
// =============================================================================

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: string;
  requiredRoles?: UserRole[];
  children?: NavItem[];
  badge?: number;
}

// =============================================================================
// Filter & Sort Types
// =============================================================================

export interface FilterParams {
  status?: InitiativeStatus[];
  priority?: InitiativePriority[];
  owner_id?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
}

export interface SortParams {
  field: string;
  direction: 'asc' | 'desc';
}

export interface PaginationParams {
  page: number;
  page_size: number;
}
