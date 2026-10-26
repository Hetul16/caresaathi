// Synthetic data only (docs/17-synthetic-data-plan.md). "Ramesh Kulkarni" is a fictional patient.
// Used until the API is wired; the shapes are the real API shapes.
import type { CarePlan, EmergencyCardData, SourceRef } from "./types";

const dischargeSrc = (line: number, quote: string): SourceRef => ({
  kind: "document",
  document_id: "doc-discharge-01",
  document_title: "Discharge summary, City Hospital",
  page: 1,
  line_start: line,
  quote,
});

const rxSrc = (line: number, quote: string): SourceRef => ({
  kind: "document",
  document_id: "doc-rx-02",
  document_title: "Prescription, Dr. Joshi",
  page: 1,
  line_start: line,
  quote,
});

export const mockPlan: CarePlan = {
  patient: { id: "p-ramesh", name: "Ramesh Kulkarni", age: 74, preferred_language: "hi" },
  reference_list_reviewed: false,
  allergies: {
    state: "listed",
    items: [
      {
        allergy_key: "al-1",
        substance: "Penicillin",
        reaction: "Skin rash",
        severity: "moderate",
        source: dischargeSrc(9, "Allergic to penicillin (rash)"),
      },
    ],
  },
  open_conflicts: [
    {
      id: "c-1",
      match: "drug_family",
      medicine: "Amoxicillin 500 mg",
      flag: "Possible conflict between the listed penicillin allergy and Amoxicillin. This is a match in our reference list, not a medical judgement.",
      doctor_question: "Dr. Joshi, the discharge summary lists a penicillin allergy and the new prescription has Amoxicillin 500 mg. Could you confirm whether this is intended?",
    },
  ],
  items: [
    {
      item_key: "m-1", version: 1, kind: "medicine", title: "Metformin 500 mg", detail: "1-0-1 · after food",
      schedule: { morning: 1, noon: 0, evening: 1, night: null }, confirmed: true, confirmed_by: "Priya (daughter)",
      source: dischargeSrc(14, "Tab Metformin 500 mg 1-0-1 after food"),
    },
    {
      item_key: "m-2", version: 1, kind: "medicine", title: "Amlodipine 5 mg", detail: "1-0-0 · morning",
      schedule: { morning: 1, noon: 0, evening: 0, night: null }, confirmed: true, confirmed_by: "Priya (daughter)",
      source: dischargeSrc(15, "Tab Amlodipine 5 mg 1-0-0"),
    },
    {
      item_key: "m-3", version: 2, kind: "medicine", title: "Amoxicillin 500 mg", detail: "1-0-1 · 5 days",
      schedule: { morning: 1, noon: 0, evening: 1, night: null }, confirmed: false,
      source: rxSrc(3, "Tab Amoxicillin 500 mg 1-0-1 x 5 days"),
    },
    {
      item_key: "t-1", version: 1, kind: "test", title: "HbA1c blood test", detail: "Repeat in 3 months",
      confirmed: false, source: dischargeSrc(22, "Repeat HbA1c after 3 months"),
    },
    {
      item_key: "a-1", version: 1, kind: "appointment", title: "Follow-up with Dr. Joshi", detail: "In two weeks",
      confirmed: false, date_missing: true, source: dischargeSrc(24, "Come back for review in two weeks"),
    },
    {
      item_key: "w-1", version: 1, kind: "warning_sign", title: "Chest pain or breathlessness", alert_level: "emergency",
      confirmed: true, confirmed_by: "Priya (daughter)",
      source: dischargeSrc(27, "Go to the emergency immediately if chest pain or breathlessness"),
    },
    {
      item_key: "w-2", version: 1, kind: "warning_sign", title: "Fever that does not settle", alert_level: "call_doctor_today",
      confirmed: true, confirmed_by: "Priya (daughter)",
      source: dischargeSrc(28, "Contact your doctor if fever persists beyond two days"),
    },
    {
      item_key: "w-3", version: 1, kind: "warning_sign", title: "Swelling in the feet", alert_level: "watch",
      confirmed: true, confirmed_by: "Priya (daughter)",
      source: dischargeSrc(29, "Keep an eye on any swelling in the feet"),
    },
    {
      item_key: "r-1", version: 1, kind: "restriction", title: "Low-sugar diet", detail: "Avoid sweets and sugary drinks",
      confirmed: true, confirmed_by: "Priya (daughter)", source: dischargeSrc(19, "Avoid sweets and sugary drinks"),
    },
  ],
  pending_changes: [
    {
      id: "pc-1", change_type: "changed", title: "Metformin 500 mg",
      before: "1-0-1", after: "1-1-1", requires_confirmation: true,
      source: { kind: "visit_segment", visit_id: "v-1", speaker: "Doctor", at_ms: 192000, quote: "Take the Metformin three times a day from now on, after food." },
    },
    {
      id: "pc-2", change_type: "new", title: "Atorvastatin 10 mg",
      after: "0-0-1 · night", requires_confirmation: true,
      source: { kind: "visit_segment", visit_id: "v-1", speaker: "Doctor", at_ms: 231000, quote: "I am adding Atorvastatin 10 at night." },
    },
  ],
  omissions: [
    {
      id: "o-1", medicine: "Aspirin 75 mg",
      previous_source: rxSrc(5, "Tab Aspirin 75 mg 0-1-0"),
      new_document: "Discharge summary, City Hospital",
      question: "Dr. Joshi, Aspirin 75 mg was on the earlier prescription and is not on the new discharge summary. Is it meant to continue, or was it left out? We are only asking; we are not suggesting either.",
    },
  ],
  approvals: [
    { id: "ac-1", tool: "message_doctor_draft", summary: "Send the penicillin question to Dr. Joshi's clinic", requested_at: "2026-10-28T09:12:00Z", status: "awaiting_approval" },
    { id: "ac-2", tool: "send_family_message", summary: "Tell Anil (son) about the changed Metformin timing", requested_at: "2026-10-28T09:14:00Z", status: "awaiting_approval" },
  ],
  timeline: [
    { id: "e1", at: "2026-10-28T09:12:00Z", actor: "CareSaathi", text: "Possible penicillin conflict found on the new prescription. Question for the doctor drafted.", kind: "alert" },
    { id: "e2", at: "2026-10-28T08:40:00Z", actor: "Priya", text: "Uploaded Prescription, Dr. Joshi", kind: "document" },
    { id: "e3", at: "2026-10-27T17:05:00Z", actor: "CareSaathi", text: "Recorded visit with Dr. Joshi. 2 changes waiting for confirmation.", kind: "visit" },
    { id: "e4", at: "2026-10-27T11:20:00Z", actor: "Priya", text: "Confirmed 5 items from the discharge summary", kind: "approval" },
    { id: "e5", at: "2026-10-27T10:58:00Z", actor: "Priya", text: "Uploaded Discharge summary, City Hospital", kind: "document" },
  ],
  last_updated_at: "2026-10-28T09:12:00Z",
};

export const mockCard: EmergencyCardData = {
  patient: { name: "Ramesh Kulkarni", age: 74, blood_group: "B+", language: "hi" },
  allergies: mockPlan.allergies,
  conditions: [
    { title: "Type 2 diabetes", source: dischargeSrc(11, "Known case of type 2 diabetes mellitus") },
    { title: "Hypertension", source: dischargeSrc(12, "Hypertension") },
  ],
  medicines: [
    { title: "Metformin 500 mg", detail: "1-0-1, after food", source: dischargeSrc(14, "Tab Metformin 500 mg 1-0-1 after food") },
    { title: "Amlodipine 5 mg", detail: "1-0-0", source: dischargeSrc(15, "Tab Amlodipine 5 mg 1-0-0") },
  ],
  recent_changes: "Amoxicillin 500 mg was added on the 28th by prescription. A change to Metformin is waiting for family confirmation.",
  providers: [{ name: "Dr. Joshi", hospital: "City Hospital, Pune", phone: "+91 20 5550 0142" }],
  contacts: [
    { name: "Priya Kulkarni", relation: "Daughter", phone: "+91 98765 43210" },
    { name: "Anil Kulkarni", relation: "Son", phone: "+91 98765 43211" },
  ],
  last_updated_at: "2026-10-28T09:12:00Z",
};
