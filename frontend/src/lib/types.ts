// Shapes mirror docs/15-api-spec.md section 3. Keep in sync with the backend.

export type Lang = "en" | "hi" | "mr";

export type AllergyState = "listed" | "no_known_allergies" | "not_recorded";

export type SourceRef =
  | { kind: "document"; document_id: string; document_title: string; page: number; line_start?: number; quote: string }
  | { kind: "visit_segment"; visit_id?: string; speaker?: string; at_ms?: number; quote: string }
  | { kind: "family_input"; stated_by?: string; quote: string };

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
  state?: "open" | "asked";
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
  patient: { id: string; name: string; age: number | null; preferred_language: Lang };
  allergies: { state: AllergyState; items: Allergy[]; source_note?: string };
  open_conflicts: OpenConflict[];
  items: PlanItem[];
  pending_changes: PendingChange[];
  omissions: OmissionFlag[];
  approvals: ApprovalAction[];
  timeline: TimelineEvent[];
  last_updated_at: string | null;
  reference_list_reviewed: boolean;
  can_approve?: boolean;           // live plans only: whether this member may confirm and approve
  duplicates?: DuplicateGroup[];
}

export interface DuplicateGroup { ingredient: string; medicines: string[]; sources: SourceRef[]; question: string }

export interface EmergencyCardData {
  patient: { name: string; age: number | null; blood_group?: string | null; language: Lang };
  allergies: { state: AllergyState; items: Allergy[] };
  conditions: { title: string; source: SourceRef }[];
  medicines: { title: string; detail: string; source: SourceRef }[];
  recent_changes: string;
  providers: { name: string; hospital: string; phone: string }[];
  contacts: { name: string; relation: string; phone: string }[];
  last_updated_at: string | null;
}

export interface CardLink { id: string; hint: string; status: "active" | "revoked" | "expired"; created_at: string; expires_at: string | null }

// ---- live-only shapes (backend read models) ----
export interface FollowUp { id: string; what: string; due_text: string; anchor_date: string | null; anchor_kind: "document" | "visit" | null; due_date: string | null;
  status: "pending" | "confirmed" | "done" | "dismissed"; acted_by: string | null; source: SourceRef; how: string }
export interface SupplyRow { id: string; medicine: string; quantity: number; unit: string; daily_units: number | null; start_date: string; estimated_run_out: string | null;
  confirmed_by: string | null; source: SourceRef | null; how: string }
export interface HistoryVersion { version: number; title: string; detail: string | null; status: string; current: boolean; at: string; confirmed_by: string | null; source: SourceRef }
export interface MedicineHistory { item_key: string; title: string; versions: HistoryVersion[] }

export interface VisitRow { id: string; status: "recording" | "processing" | "needs_review" | "completed" | "failed" | "cancelled"; origin: "recording" | "mock"; doctor_name: string | null; started_at: string; duration_ms: number | null }
export interface VisitDetail extends VisitRow {
  hospital: string | null; language_hint: string; audio_deleted: boolean; failure_note: string | null; transcript_hidden: boolean;
  speakers: { label: string; role: string; name: string | null; mapped_by: string; confirmed: boolean }[];
  segments: { id: string; seq: number; speaker: string; role: string; start_ms: number; end_ms: number; text: string }[];
  unclear: { note: string; segment_ids: string[] }[];
  changes: { id: string; change_type: string; status: string; title: string | null; quote: string }[];
  follow_ups: { what: string; due_text: string; due_date: string | null; status: string }[];
  consents: { id: string; role: string; given_by: string; granted_at: string; revoked_at: string | null }[];
}
export interface Member { id: string; user_id: string; name: string; role: string; relationship: string | null; status: string; can_approve: boolean; can_manage_members: boolean; can_view_recordings: boolean }
export interface Invite { id: string; hint: string; role: string; relationship: string | null; status: "open" | "accepted" | "revoked" | "expired"; can_approve: boolean; can_view_recordings: boolean; can_manage_members: boolean; expires_at: string }
export interface ChatReply { id: string; text: string; language: Lang; intent: string; kind: "answer" | "refusal" | "plain"; sources: SourceRef[]; passed: boolean; heard?: string }
export interface ChatLine { direction: "inbound" | "outbound"; text: string; language: string; at: string }
export interface Explanation { id: string; text: string; passed: boolean; confirmed: boolean; source: SourceRef }
export interface FridgeSheet { patient: string; language: Lang; allergy_state: AllergyState; allergies: { substance: string; reaction: string | null }[];
  medicines: { title: string; detail: string | null; when: Record<"morning" | "noon" | "evening" | "night", number>; source: string }[];
  warning_signs: { title: string; level: string }[]; doctors: { name: string; hospital: string; phone: string }[]; generated_at: string; note: string }
export interface TrustCategory { name: string; description: string; total: number; passed: number; failures: { id: string; input: string; expected: string; actual: string }[] }
export interface TrustRun { run_id: string | null; ran_at: string; git_sha: string | null; model: string; stored: boolean; total: number; passed: number; categories: TrustCategory[]; disclaimer: string }

// ---- care crew and doctor link (Stretch C) ----
export interface BriefLine { text: string; source: SourceRef | null }
export interface Brief { title: string; sections: { heading: string; lines: BriefLine[] }[]; questions: string[]; note: string }
export interface CrewStep { seq: number; tool: string; permission: "automatic" | "ask_first" | "automatic_alert" | null; status: "ran" | "awaiting_approval" | "refused" | "failed";
  why: string | null; summary: string | null; reason: string | null; action_id: string | null; action_status: string | null; approved_by: string | null; approved_at: string | null }
export interface CrewRun { id: string; goal: string; status: "running" | "done" | "failed"; error: string | null; requested_by: string | null; started_at: string;
  finished_at: string | null; brief: Brief | null; steps: CrewStep[] }
export interface DoctorMessage { id: string; direction: "to_doctor" | "from_doctor"; body: string; at: string }
export interface DoctorLink { id: string; hint: string; doctor_name: string; status: "active" | "revoked" | "expired"; expires_at: string; created_at: string; opened: number; messages: DoctorMessage[] }
export interface DoctorPage { available: true; doctor_name: string; expires_at: string; card: EmergencyCardData; thread: DoctorMessage[]; can_reply: boolean; note: string }
