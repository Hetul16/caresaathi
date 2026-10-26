// Shapes mirror docs/15-api-spec.md section 3. Keep in sync with the backend.

export type Lang = "en" | "hi" | "mr";

export type AllergyState = "listed" | "no_known_allergies" | "not_recorded";

export type SourceRef =
  | { kind: "document"; document_id: string; document_title: string; page: number; line_start?: number; quote: string }
  | { kind: "visit_segment"; visit_id: string; speaker: string; at_ms: number; quote: string }
  | { kind: "family_input"; stated_by: string; quote: string };

export interface Allergy {
  allergy_key: string;
  substance: string;
  reaction: string | null;
  severity: "mild" | "moderate" | "severe" | "unknown";
  source: SourceRef;
}

export interface OpenConflict {
  id: string;
  match: "direct" | "drug_family" | "unresolved";
  medicine: string;
  flag: string;
  doctor_question: string;
}

export type ItemKind = "medicine" | "condition" | "test" | "appointment" | "warning_sign" | "restriction" | "instruction";

export interface PlanItem {
  item_key: string;
  version: number;
  kind: ItemKind;
  title: string;
  detail?: string;                  // as written, e.g. "1-0-1, 5 days"
  schedule?: { morning: number | null; noon: number | null; evening: number | null; night: number | null };
  alert_level?: "watch" | "call_doctor_today" | "emergency";
  confirmed: boolean;
  confirmed_by?: string;
  source: SourceRef;
  date_missing?: boolean;
}

export interface PendingChange {
  id: string;
  change_type: "new" | "changed" | "stopped";
  title: string;
  before?: string;
  after?: string;
  source: SourceRef;
  requires_confirmation: boolean;
}

export interface OmissionFlag {
  id: string;
  medicine: string;
  previous_source: SourceRef;
  new_document: string;
  question: string;               // drafted question for the doctor; never a judgement
}

export interface ApprovalAction {
  id: string;
  tool: string;
  summary: string;
  requested_at: string;
  status: "awaiting_approval";
}

export interface TimelineEvent {
  id: string;
  at: string;
  actor: string;
  text: string;
  kind: "document" | "visit" | "approval" | "alert" | "card" | "plan";
}

export interface CarePlan {
  patient: { id: string; name: string; age: number; preferred_language: Lang };
  allergies: { state: AllergyState; items: Allergy[]; source_note?: string };
  open_conflicts: OpenConflict[];
  items: PlanItem[];
  pending_changes: PendingChange[];
  omissions: OmissionFlag[];
  approvals: ApprovalAction[];
  timeline: TimelineEvent[];
  last_updated_at: string;
  reference_list_reviewed: boolean;
}

export interface EmergencyCardData {
  patient: { name: string; age: number; blood_group?: string; language: Lang };
  allergies: { state: AllergyState; items: Allergy[] };
  conditions: { title: string; source: SourceRef }[];
  medicines: { title: string; detail: string; source: SourceRef }[];
  recent_changes: string;
  providers: { name: string; hospital: string; phone: string }[];
  contacts: { name: string; relation: string; phone: string }[];
  last_updated_at: string;
}
