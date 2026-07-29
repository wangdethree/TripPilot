export type TaskStatus =
  | "COLLECTING_REQUIREMENTS"
  | "AWAITING_CONFIRMATION"
  | "PLANNING"
  | "REPLANNING"
  | "COMPLETED"
  | "PARTIAL"
  | "NEEDS_USER_INPUT"
  | "FAILED"
  | "CANCELLED";

export interface TaskView {
  status: TaskStatus;
  workflow_step: string | null;
  request_summary: Record<string, unknown>;
  missing_fields: string[];
  assumptions: string[];
  unresolved_constraints: unknown[];
  attempt_number: number;
  resource_usage: Record<string, unknown>;
  result_available: boolean;
  next_actions: string[];
  updated_at: string;
  row_version: number;
}

export interface ConstraintResult {
  constraint_id: string;
  category: string;
  severity: "HARD" | "SOFT";
  status: "PASS" | "WARNING" | "FAIL" | "UNKNOWN";
  message: string;
}

export interface TimelineItem {
  item_id: string;
  item_type: "ACTIVITY" | "TRANSIT" | "MEAL" | "REST";
  start_time: string;
  end_time: string;
  title: string;
  description: string;
  reason: string;
  estimated_cost: {
    amount: string | null;
    confidence: string;
  };
  warnings: string[];
}

export interface DayPlan {
  date: string;
  theme: string;
  timeline_items: TimelineItem[];
  daily_warnings: string[];
}

export interface TripPlan {
  version: number;
  status: "COMPLETED" | "PARTIAL";
  request_snapshot: {
    destination_city: string;
    traveler_count: number;
    interests: string[];
  };
  days: DayPlan[];
  budget_summary: {
    known_total: string;
    estimated_total: string;
    budget_scope_total: string;
    remaining_budget: string;
    reserve: string;
    unknown_items: unknown[];
  };
  constraint_results: ConstraintResult[];
  assumptions: string[];
  sources: Array<{
    source_id: string;
    provider: string;
    title: string;
    freshness_status: string;
  }>;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    suggested_actions: string[];
  };
  trace_id: string;
}
