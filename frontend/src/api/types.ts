// ─── Dashboard ───────────────────────────────────────────────────────────────
export interface TopExceptionType {
  exception_type: string;
  count: number;
}

export interface DashboardKPI {
  total_transactions: number;
  healthy_count: number;
  exception_count: number;
  open_exceptions: number;
  auto_resolved_exceptions: number;
  total_financial_exposure: string;
  exception_rate_pct: number;
  top_exception_types: TopExceptionType[];
}

// ─── Benchmark ───────────────────────────────────────────────────────────────
export interface PerTypeStat {
  exception_type: string;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number;
  recall: number;
  f1_score: number;
}

export interface BenchmarkResult {
  total_records: number;
  healthy_count: number;
  exception_count: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  match_rate_pct: number;
  total_financial_value: string;
  total_financial_exposure: string;
  open_exceptions: number;
  auto_resolved_exceptions: number;
  approved_exceptions: number;
  rejected_exceptions: number;
  throughput_records_per_sec: number;
  duration_seconds: number;
  per_type_stats: PerTypeStat[];
}

// ─── Exceptions ──────────────────────────────────────────────────────────────
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type ExceptionStatus = 'open' | 'auto_resolved' | 'approved' | 'rejected' | 'escalated';

export interface ExceptionListItem {
  exception_id: string;
  transaction_id: string;
  exception_type: string;
  severity: Severity;
  financial_exposure: string;
  status: ExceptionStatus;
  detected_at: string;
  ground_truth_type: string | null;
}

export interface ExceptionDetail extends ExceptionListItem {
  control_evidence: Record<string, unknown>;
  investigations: Investigation[];
}

// ─── Lifecycle Trace ─────────────────────────────────────────────────────────
export type StageStatus = 'VALID' | 'WARNING' | 'BREAK' | 'MISSING';

export interface LifecycleStage {
  stage: string;
  status: StageStatus;
  amount: string | null;
  timestamp: string | null;
  notes: string | null;
  raw_ids: string[];
}

export interface LifecycleTrace {
  transaction_id: string;
  stages: LifecycleStage[];
  overall_status: StageStatus;
  exception_type: string | null;
  financial_exposure: string;
  traced_at: string;
}

// ─── Investigation ───────────────────────────────────────────────────────────
export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  result_summary: string;
}

export interface InvestigationData {
  investigation_id: string;
  exception_id: string;
  transaction_id: string;
  agent_provider: string;
  root_cause: string;
  explanation: string;
  recommended_action: string;
  confidence: number;
  confidence_band: 'high_confidence' | 'requires_verification' | 'insufficient_evidence';
  impact_summary: string;
  requires_human_review: boolean;
  missing_evidence: string[];
  tool_calls: ToolCall[];
  lifecycle_trace: LifecycleTrace | null;
  financial_exposure: string;
  created_at: string;
  // Raw evidence dict — present when the backend includes it
  evidence?: Record<string, unknown>;
}

export interface Investigation {
  investigation_id: string;
  exception_id: string;
  transaction_id: string;
  agent_provider: string;
  root_cause: string;
  explanation: string;
  recommended_action: string;
  confidence: number;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface InvestigateResponse {
  investigation: InvestigationData;
  requires_human_review: boolean;
  missing_evidence: string[];
  lifecycle_trace: LifecycleTrace | null;
}

// ─── Controller ──────────────────────────────────────────────────────────────
export type ControllerAction = 'approve' | 'reject' | 'escalate';

export interface ActionResponse {
  exception_id: string;
  action: string;
  previous_status: string;
  new_status: string;
  actor: string;
  notes: string | null;
  actioned_at: string;
}

// ─── Verification ────────────────────────────────────────────────────────────
export interface VerificationResult {
  exception_id: string;
  transaction_id: string;
  before_exception_type: string | null;
  after_exception_type: string | null;
  before_exposure: string;
  after_exposure: string;
  verification_status: 'resolved' | 'improved' | 'persists';
  control_result_summary: Record<string, unknown>;
  verified_at: string;
}

// ─── Audit ───────────────────────────────────────────────────────────────────
export interface AuditLogEntry {
  audit_id: string;
  transaction_id: string | null;
  exception_id: string | null;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  message: string;
  created_at: string;
}
