// Shapes mirror docs/15-api-spec.md section 3. Keep in sync with the backend.

export type Lang = "en" | "hi" | "mr";

export type AllergyState = "listed" | "no_known_allergies" | "not_recorded";

export type SourceRef =
  | { kind: "document"; document_id: string; document_title: string; page: number; line_start?: number; quote: string }
  | { kind: "visit_segment"; visit_id?: string; speaker?: string; at_ms?: number; quote: string }
  | { kind: "family_input"; stated_by?: string; quote: string }
  | { kind: "doctor_message"; quote: string };

export interface Allergy {
  allergy_key: string;
  substance: string;
  reaction: string | null;
  severity: "mild" | "moderate" | "severe" | "unknown";
  source: SourceRef;
}

export interface FamilyBasis { confirmed: boolean; atc_code: string | null; atc_group: string | null; atc_name: string | null;
  family: string; text: string; source: string | null; checked_on: string | null }

export interface OpenConflict {
  id: string;
  match: "direct" | "drug_family" | "unresolved";
  medicine: string;
  flag: string;
  basis?: FamilyBasis | null;       // why a family match was made: the WHO ATC group, stated by code
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
  reference_check?: { source: string; caveat: string; checked_on: string; memberships_checked?: number; confirmed_by_atc?: number; not_confirmed?: number } | null;
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
export interface DoctorMessage { id: string; direction: "to_doctor" | "from_doctor"; body: string; at: string; read?: boolean }
export interface DoctorLink { id: string; hint: string; doctor_name: string; status: "active" | "revoked" | "expired"; expires_at: string; created_at: string; opened: number; messages: DoctorMessage[] }
export interface DoctorPage { available: true; doctor_name: string; expires_at: string; card: EmergencyCardData; thread: DoctorMessage[]; can_reply: boolean; note: string }

// ---- label check (C4) ----
export interface LabelProduct { brand: string | null; ingredients: { name: string; strength: string | null }[]; form?: string | null; expiry?: string | null; batch?: string | null;
  verdict: "matches" | "different_strength" | "not_in_plan" | "could_not_read"; text: string; question: string | null;
  plan_item: { title: string; detail: string; source: SourceRef } | null; allergy: { ingredient: string; match: string; text: string; allergy?: string; source?: SourceRef }[] }
export interface LabelResult { products: LabelProduct[]; printed_lines: string[]; dropped_unprinted: number; note: string }

// ---- outcomes board (C6) ----
export interface OutcomeAnswer { text: string; answered_by: string; source_kind: "doctor_message" | "family_note"; recorded_by: string; recorded_at: string }
export interface OutcomeItem { kind: "allergy_conflict" | "reconciliation_flag"; id: string; title: string; label: string; question: string;
  status: "open" | "seen" | "asked" | "answered" | "closed_without_answer"; raised_at: string; days_open: number; answer: OutcomeAnswer | null }
export interface OutcomesBoard {
  summary: { raised: number; answered: number; waiting: number; closed_without_answer: number; oldest_waiting_days: number | null; average_days_to_answer: number | null };
  items: OutcomeItem[]; follow_ups: { total: number; waiting_for_confirmation: number; confirmed: number; done: number };
  doctor_thread: { questions_sent: number; replies_received: number; replies_not_yet_used: number };
  usable_replies: { id: string; doctor_name: string; body: string; at: string }[]; note: string }

// ---- live model report (Trust page) ----
export interface LiveCase { id?: string; text?: string; ok: boolean; expected?: string[]; got?: string[]; result?: string; error?: string; note?: string; seconds?: number;
  amlodipine_change?: boolean; chest_pain_warning?: boolean; follow_up?: boolean; invented_medicine_change?: boolean }
export interface LiveSection { title: string; what: string; passed: number; total: number; cases: LiveCase[] }
export interface SpeechRate { wer: number | null; cer: number | null }
export interface SpeechCase { id: string; ok: boolean; reference: string; plain?: { heard: string; word_errors: number; words: number }; hint?: { heard: string; word_errors: number; words: number } }
export interface SpeechData { generated_at: string; model: string; dataset: string; what: string; cost_usd: number;
  languages: Record<string, { language: string; clips: number; failed: number; without_language_hint: SpeechRate; with_language_hint: SpeechRate; cases: SpeechCase[] }> }
export interface LiveData { speech?: SpeechData; generated_at: string; reader_model: string; cost_usd: number; minutes: number; sections: Record<string, LiveSection>;
  history: { generated_at: string; sections: Record<string, [number, number]> }[]; not_measured: string[] }
export type LiveReport = ({ available: true } & LiveData) | { available: false };

// ---- two-reader check (A5) ----
export interface SecondReading { title: string | null; strength: string | null; frequency: string | null; duration: number | null; quantity: number | null; quote: string | null; page: number | null; line: number | null }
export interface SecondRead { id: string; medicine: string; document: string; differs_in: string[]; reading_a: SecondReading | null; reading_b: SecondReading | null;
  chosen: "a" | "b" | "neither" | null; chosen_by: string | null; chosen_at: string | null }

// ---- daily check-ins (C7) ----
export interface TodayItem { item_key: string; title: string; units: number; status: "later" | "due" | "not_marked" | "taken" | "not_taken"; marked_by: string | null; marked_at: string | null; how: string }
export interface TodaySlot { slot: "morning" | "noon" | "evening" | "night"; label: string; time: string; items: TodayItem[] }
export interface TodayView { date: string; now: string; slots: TodaySlot[]; summary: { taken: number; not_taken: number; due: number; not_marked: number; later: number };
  checkin: { pain: number | null; note: string | null; at: string } | null; last_activity: string | null; note: string }
export interface WellbeingHistory { days: number; days_with_entry: number; entries: { date: string; pain: number | null; note: string | null; by: string }[]; note: string }

// ---- family tasks (C8) ----
export interface CareTask { id: string; title: string; due_date: string | null; status: "open" | "done"; assigned_to: string | null; created_by: string; done_by: string | null; overdue: boolean; done_at: string | null }

// ---- medicine timeline ----
export interface TimelineRow { item_key: string; title: string; detail: string | null; confirmed: boolean; prescriber: string; doc_date: string | null;
  start: string | null; end: string | null; open_end: boolean; how: string; allergy: { match: string; flag: string } | null; source: SourceRef }
export interface TimelineOverlap { ingredient: string; medicines: string[]; keys: string[]; dated: boolean; question: string;
  spots: { a: string; b: string; start: string; end: string | null }[] }
export interface MedicineTimeline { today: string; window: { start: string; end: string }; rows: TimelineRow[]; overlaps: TimelineOverlap[]; note: string }
