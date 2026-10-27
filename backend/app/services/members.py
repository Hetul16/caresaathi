"""Family members and invitations (S7). Who may confirm, approve, manage and hear recordings is decided here and nowhere else.

An invitation is a random code shown once; only its hash is stored. Accepting runs inside one SECURITY DEFINER function so a new
member can join without any broad access to the members table. Removing or demoting the last manager is refused."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..security import hash_token, new_token
from .audit import timeline, write_audit
from .errors import ServiceError


def create_invite(s: Session, *, patient_id: UUID, user_id: UUID, member_role: str, relationship_label: str | None, can_approve: bool,
                  can_view_recordings: bool, can_manage_members: bool, expires_in_days: int) -> dict[str, Any]:
    code = new_token(18)
    expires = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    iid = s.execute(text("""
        INSERT INTO member_invites (patient_id, code_hash, code_hint, member_role, relationship_label, can_approve, can_manage_members,
                                    can_view_recordings, created_by, expires_at)
        VALUES (:p, :h, :hint, CAST(:r AS member_role), :l, :a, :m, :v, :u, :e) RETURNING id"""),
        {"p": patient_id, "h": hash_token(code), "hint": code[-4:], "r": member_role, "l": relationship_label, "a": can_approve,
         "m": can_manage_members, "v": can_view_recordings, "u": user_id, "e": expires}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="member.invited", entity_type="member_invite", entity_id=iid,
                after={"role": member_role, "can_approve": can_approve, "can_view_recordings": can_view_recordings, "can_manage_members": can_manage_members})
    return {"id": str(iid), "url": f"{get_settings().public_base_url.rstrip('/')}/join/{code}", "hint": code[-4:], "expires_at": expires.isoformat()}


def list_invites(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows = s.execute(text("""SELECT id, code_hint, member_role, relationship_label, can_approve, can_view_recordings, can_manage_members, expires_at,
                                    accepted_at, revoked_at, created_at FROM member_invites WHERE patient_id = :p ORDER BY created_at DESC"""),
                     {"p": patient_id}).mappings().all()
    out = []
    for r in rows:
        st = "accepted" if r["accepted_at"] else "revoked" if r["revoked_at"] else "expired" if r["expires_at"] <= now else "open"
        out.append({"id": str(r["id"]), "hint": r["code_hint"], "role": r["member_role"], "relationship": r["relationship_label"], "status": st,
                    "can_approve": r["can_approve"], "can_view_recordings": r["can_view_recordings"], "can_manage_members": r["can_manage_members"],
                    "expires_at": r["expires_at"].isoformat(), "created_at": r["created_at"].isoformat()})
    return out


def revoke_invite(s: Session, *, invite_id: UUID, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id, accepted_at FROM member_invites WHERE id = :i FOR UPDATE"), {"i": invite_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    if row["accepted_at"] is None:
        s.execute(text("UPDATE member_invites SET revoked_at = coalesce(revoked_at, now()) WHERE id = :i"), {"i": invite_id})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action="member.invite_revoked", entity_type="member_invite", entity_id=invite_id)
    return {"id": str(invite_id), "status": "revoked"}


def accept_invite(s: Session, *, code: str, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT r_patient_id, r_outcome FROM app_accept_invite(:h, :u)"), {"h": hash_token(code[:200]), "u": user_id}).first()
    if row is None or row[1] == "unavailable" or row[0] is None:
        raise ServiceError(404, "invite-unavailable", "This invitation is not available. It may have expired or been withdrawn.")
    return {"patient_id": str(row[0]), "status": row[1]}


def list_members(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT fm.id, fm.user_id, u.display_name, fm.member_role, fm.relationship_label, fm.status, fm.can_approve, fm.can_manage_members, fm.can_view_recordings
        FROM family_members fm JOIN users u ON u.id = fm.user_id WHERE fm.patient_id = :p AND fm.status <> 'removed' ORDER BY fm.created_at"""),
        {"p": patient_id}).mappings().all()
    return [{"id": str(r["id"]), "user_id": str(r["user_id"]), "name": r["display_name"], "role": r["member_role"], "relationship": r["relationship_label"],
             "status": r["status"], "can_approve": r["can_approve"], "can_manage_members": r["can_manage_members"],
             "can_view_recordings": r["can_view_recordings"]} for r in rows]


def _managers(s: Session, patient_id: UUID) -> int:
    return s.execute(text("SELECT count(*) FROM family_members WHERE patient_id = :p AND status = 'active' AND can_manage_members"), {"p": patient_id}).scalar_one()


def update_member(s: Session, *, member_id: UUID, user_id: UUID, can_approve: bool | None, can_view_recordings: bool | None,
                  can_manage_members: bool | None, remove: bool) -> dict[str, Any]:
    m = s.execute(text("SELECT id, patient_id, can_manage_members, status FROM family_members WHERE id = :i FOR UPDATE"), {"i": member_id}).mappings().first()
    if m is None:
        raise ServiceError(404, "not-found", "Not found")
    loses_manage = remove or can_manage_members is False
    if loses_manage and m["can_manage_members"] and _managers(s, m["patient_id"]) <= 1:
        raise ServiceError(409, "last-manager", "There must always be one person who can manage the family")
    if remove:
        s.execute(text("UPDATE family_members SET status = 'removed' WHERE id = :i"), {"i": member_id})
        action = "member.removed"
    else:
        s.execute(text("""UPDATE family_members SET can_approve = coalesce(:a, can_approve), can_view_recordings = coalesce(:v, can_view_recordings),
                                                    can_manage_members = coalesce(:m, can_manage_members) WHERE id = :i"""),
                  {"a": can_approve, "v": can_view_recordings, "m": can_manage_members, "i": member_id})
        action = "member.permissions_changed"
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=m["patient_id"], action=action, entity_type="family_member", entity_id=member_id,
                after={"can_approve": can_approve, "can_view_recordings": can_view_recordings, "can_manage_members": can_manage_members})
    timeline(s, patient_id=m["patient_id"], event_type="member_changed", actor_type="user", actor_id=user_id,
             summary="A family member was removed" if remove else "A family member's permissions were changed", entity_type="family_member", entity_id=member_id)
    return {"id": str(member_id), "status": "removed" if remove else "active"}
