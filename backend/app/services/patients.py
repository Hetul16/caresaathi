"""Creating a patient and their first member. One path for the API and the demo seed."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import write_audit


def create_patient(s: Session, *, user_id: UUID, full_name: str, date_of_birth=None, sex: str | None = None, language: str = "en",
                   relationship_label: str | None = None, request_id: str | None = None) -> UUID:
    pid = uuid4()
    # Insert without RETURNING: the SELECT policy only passes once the member row exists.
    s.execute(text("""INSERT INTO patients (id, full_name, date_of_birth, sex, preferred_language, created_by)
                      VALUES (:i, :n, :d, :s, CAST(:l AS pref_lang), :u)"""),
              {"i": pid, "n": full_name.strip(), "d": date_of_birth, "s": sex, "l": language, "u": user_id})
    s.execute(text("""INSERT INTO family_members (patient_id, user_id, member_role, relationship_label, status,
                                                  can_approve, can_manage_members, can_view_recordings, notify_urgent)
                      VALUES (:p, :u, 'child', :r, 'active', true, true, true, true)"""),
              {"p": pid, "u": user_id, "r": relationship_label})
    s.execute(text("INSERT INTO allergy_status (patient_id) VALUES (:p)"), {"p": pid})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=pid, action="patient.created", entity_type="patient",
                entity_id=pid, request_id=request_id)
    return pid
