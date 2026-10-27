"""The in-app chat (S9). It reads back what is in the care plan; it does not advise.

Replies are assembled by code from stored data, with the source of every line, then checked by the output guard. A question that
asks for advice (is it safe, should I stop, what dose, can I take it with ...) or tries to instruct the assistant gets a plain
refusal that points to the doctor or pharmacist. Nothing here calls a model: a model may later reword replies, but never decide them."""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.guard import FALLBACK, GuardContext, detect_language, guard_output
from ..safety.injection import looks_like_injection
from ..safety.text import normalize_text
from .audit import write_audit
from .explain import digits_of, store_output
from .readmodel import item_detail, source_of

LANGS = ("en", "hi", "mr")

# A question that asks for a judgement or an instruction is never answered, in any language. Checked before everything else.
ADVICE = (
    "safe", "unsafe", "is it ok", "is it okay", "okay to", "ok to", "should i", "shall i", "can i take", "can i stop", "can i skip", "may i",
    "stop taking", "stop the", "skip", "double", "increase", "decrease", "reduce", "lower the", "raise the", "dose of", "how much", "how many",
    "side effect", "interact", "together with", "with alcohol", "with milk", "pregnan", "diagnos", "what is wrong", "do i have", "cure", "treat",
    "substitute", "alternative", "instead of", "replace", "better than", "overdose", "hospital", "emergency room", "go to the er",
    "सुरक्षित", "बंद कर", "छोड़", "खुराक", "मात्रा", "लेना चाहिए", "ले सकता", "ले सकती", "साइड इफ", "बदल", "अस्पताल", "जगह",
    "थांबव", "घ्यावी", "घेऊ शकतो", "घेऊ शकते", "डोस", "सुरक्षित आहे", "दवाखान्यात", "रुग्णालय",
    # romanised Hindi
    "kya main", "le sakta", "le sakti", "band kar", "chhod", "khuraak", "kitni goli", "surakshit", "hospital jaun", "dose badha", "dose kam",
)
INTENTS: dict[str, tuple[str, ...]] = {
    "medicines": ("medicine", "tablet", "pill", "dawai", "dawa", "davai", "what do i take", "what to take", "schedule", "my medicines",
                  "दवा", "दवाई", "औषध", "गोळी", "गोलियां", "गोळ्या"),
    "followups": ("appointment", "follow up", "follow-up", "review", "next visit", "when is", "checkup", "check-up", "kab", "अपॉइंटमेंट", "कब",
                  "फॉलो", "भेट", "पुन्हा", "जांच", "तपासणी"),
    "allergy": ("allerg", "एलर्जी", "ऍलर्जी", "अलर्जी", "allergy"),
    "warnings": ("warning", "danger sign", "when to worry", "red flag", "खतरे के", "चेतावनी", "धोक्याची", "सावधानी"),
    "changes": ("what changed", "who changed", "history", "what's new", "whats new", "recent", "क्या बदला", "बदलाव", "काय बदलले"),
}

T: dict[str, dict[str, str]] = {
    "en": {
        "meds_intro": "Your family has confirmed these medicines. This is what your documents say:",
        "meds_none": "Your family has not confirmed any medicine yet, so there is nothing to read out. They can confirm them in the app.",
        "meds_held": "{n} medicine(s) are being checked with the doctor, so they are not listed here.",
        "meds_waiting": "{n} more medicine(s) are waiting for your family to confirm them.",
        "fu_intro": "These follow-ups have been confirmed by your family:",
        "fu_none": "No follow-up has been confirmed yet.",
        "fu_nodate": "no date could be worked out, please ask the doctor",
        "al_listed": "The allergies written in your documents:",
        "al_none": "Your documents say there are no known allergies.",
        "al_unknown": "No allergy is recorded. That does not mean there are none. Please ask the doctor.",
        "warn_intro": "Warning signs written in your own documents, copied word for word:",
        "warn_none": "No warning signs have been written down yet in your documents.",
        "warn_outro": "I cannot judge how serious anything is. If you are worried, please contact your doctor.",
        "chg_intro": "The latest changes to the plan:",
        "chg_none": "Nothing has changed yet.",
        "refuse": "I can only read back what is in your care plan, so I cannot answer that. Please ask the doctor or pharmacist.",
        "refuse_hostile": "I can only read back what is in your care plan. Please ask the doctor or pharmacist.",
        "unknown": "I did not understand. You can ask about your medicines, follow-ups, allergies or warning signs.",
    },
    "hi": {
        "meds_intro": "आपके परिवार ने ये दवाइयाँ पक्की की हैं। आपके दस्तावेज़ों में यही लिखा है:",
        "meds_none": "आपके परिवार ने अभी कोई दवा पक्की नहीं की है, इसलिए पढ़कर सुनाने को कुछ नहीं है। वे ऐप में उन्हें पक्का कर सकते हैं।",
        "meds_held": "{n} दवा की जाँच डॉक्टर से हो रही है, इसलिए वह यहाँ नहीं है।",
        "meds_waiting": "{n} और दवा आपके परिवार की पुष्टि का इंतज़ार कर रही है।",
        "fu_intro": "आपके परिवार ने ये अगली मुलाक़ातें पक्की की हैं:",
        "fu_none": "अभी कोई अगली मुलाक़ात पक्की नहीं हुई है।",
        "fu_nodate": "तारीख़ नहीं निकल सकी, कृपया डॉक्टर से पूछें",
        "al_listed": "आपके दस्तावेज़ों में लिखी एलर्जी:",
        "al_none": "आपके दस्तावेज़ों में लिखा है कि कोई ज्ञात एलर्जी नहीं है।",
        "al_unknown": "कोई एलर्जी दर्ज नहीं है। इसका मतलब यह नहीं कि एलर्जी नहीं है। कृपया डॉक्टर से पूछें।",
        "warn_intro": "आपके अपने दस्तावेज़ों में लिखे चेतावनी के संकेत, जैसे के तैसे:",
        "warn_none": "आपके दस्तावेज़ों में अभी कोई चेतावनी का संकेत नहीं लिखा है।",
        "warn_outro": "मैं यह नहीं बता सकता कि कुछ कितना गंभीर है। अगर आप चिंतित हैं तो कृपया अपने डॉक्टर से संपर्क करें।",
        "chg_intro": "योजना में हाल के बदलाव:",
        "chg_none": "अभी कुछ नहीं बदला है।",
        "refuse": "मैं केवल वही पढ़कर सुना सकता हूँ जो आपकी देखभाल योजना में है, इसलिए इसका जवाब नहीं दे सकता। कृपया डॉक्टर या फार्मासिस्ट से पूछें।",
        "refuse_hostile": "मैं केवल वही पढ़कर सुना सकता हूँ जो आपकी देखभाल योजना में है। कृपया डॉक्टर या फार्मासिस्ट से पूछें।",
        "unknown": "मैं समझ नहीं पाया। आप अपनी दवाइयों, अगली मुलाक़ात, एलर्जी या चेतावनी के संकेतों के बारे में पूछ सकते हैं।",
    },
    "mr": {
        "meds_intro": "तुमच्या कुटुंबाने ही औषधे पक्की केली आहेत. तुमच्या कागदपत्रांत हेच लिहिले आहे:",
        "meds_none": "तुमच्या कुटुंबाने अजून कोणतेही औषध पक्के केलेले नाही, त्यामुळे वाचून दाखवण्यासाठी काही नाही. ते अॅपमध्ये पक्के करू शकतात.",
        "meds_held": "{n} औषधाची डॉक्टरांकडे तपासणी सुरू आहे, म्हणून ते येथे नाही.",
        "meds_waiting": "आणखी {n} औषध तुमच्या कुटुंबाच्या पुष्टीची वाट पाहत आहे.",
        "fu_intro": "तुमच्या कुटुंबाने या पुढच्या भेटी पक्क्या केल्या आहेत:",
        "fu_none": "अजून कोणतीही पुढची भेट पक्की झालेली नाही.",
        "fu_nodate": "तारीख काढता आली नाही, कृपया डॉक्टरांना विचारा",
        "al_listed": "तुमच्या कागदपत्रांत लिहिलेली ऍलर्जी:",
        "al_none": "तुमच्या कागदपत्रांत लिहिले आहे की कोणतीही ज्ञात ऍलर्जी नाही.",
        "al_unknown": "कोणतीही ऍलर्जी नोंदलेली नाही. याचा अर्थ ऍलर्जी नाही असा नाही. कृपया डॉक्टरांना विचारा.",
        "warn_intro": "तुमच्या स्वतःच्या कागदपत्रांत लिहिलेली धोक्याची चिन्हे, जशीच्या तशी:",
        "warn_none": "तुमच्या कागदपत्रांत अजून कोणतेही धोक्याचे चिन्ह लिहिलेले नाही.",
        "warn_outro": "काही किती गंभीर आहे हे मी सांगू शकत नाही. तुम्हाला काळजी वाटत असेल तर कृपया तुमच्या डॉक्टरांशी संपर्क करा.",
        "chg_intro": "योजनेतील अलीकडचे बदल:",
        "chg_none": "अजून काहीही बदलले नाही.",
        "refuse": "तुमच्या देखभाल योजनेत जे आहे तेच मी वाचून दाखवू शकतो, त्यामुळे याचे उत्तर देऊ शकत नाही. कृपया डॉक्टर किंवा फार्मासिस्टला विचारा.",
        "refuse_hostile": "तुमच्या देखभाल योजनेत जे आहे तेच मी वाचून दाखवू शकतो. कृपया डॉक्टर किंवा फार्मासिस्टला विचारा.",
        "unknown": "मला समजले नाही. तुम्ही तुमची औषधे, पुढची भेट, ऍलर्जी किंवा धोक्याची चिन्हे याबद्दल विचारू शकता.",
    },
}


# "do i have ..." is a diagnosis question ("do I have diabetes?") unless it is plainly about the recorded allergies.
_SOFT_ADVICE = ("do i have",)


def classify(message: str) -> str:
    if looks_like_injection(message):
        return "hostile"
    n = normalize_text(message)
    hits = [k for k in ADVICE if normalize_text(k) in n]
    allergy_words = any(normalize_text(w) in n for w in INTENTS["allergy"])
    if hits and not (allergy_words and all(h in _SOFT_ADVICE for h in hits)):
        return "advice"
    for intent, words in INTENTS.items():
        if any(normalize_text(w) in n for w in words):
            return intent
    return "unknown"


def _src_rows(s: Session, ids: list[UUID]) -> list[dict]:
    if not ids:
        return []
    rows = s.execute(text("""SELECT sr.id, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
                                    coalesce(d.original_filename, d.doc_type::text) AS doc_title
                             FROM source_refs sr LEFT JOIN documents d ON d.id = sr.document_id WHERE sr.id = ANY(:ids)"""), {"ids": ids}).mappings().all()
    by_id = {r["id"]: source_of(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def _cite(src: dict) -> str:
    if src["kind"] == "document":
        return f"{src['document_title']}, p.{src['page']}" + (f" line {src['line_start']}" if src.get("line_start") else "")
    return "the doctor's words"


def _medicines(s: Session, patient_id: UUID) -> tuple[list[dict], int, int]:
    rows = s.execute(text("""
        SELECT c.title, c.details, c.source_ref_id, c.confirmed_by IS NOT NULL AS confirmed,
               EXISTS (SELECT 1 FROM allergy_conflicts ac WHERE ac.care_plan_item_id = c.id AND ac.status = 'open') AS held
        FROM care_plan_items c WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine' ORDER BY c.title"""), {"p": patient_id}).mappings().all()
    ok = [r for r in rows if r["confirmed"] and not r["held"]]
    return ok, sum(1 for r in rows if r["confirmed"] and r["held"]), sum(1 for r in rows if not r["confirmed"])


def answer(s: Session, *, patient_id: UUID, user_id: UUID | None, message: str, language: str, request_note: str = "chat") -> dict[str, Any]:
    lang = language if language in LANGS else "en"
    intent = classify(message)
    tx = T[lang]
    lines: list[str] = []
    ids: list[UUID] = []
    kind = "answer"

    if intent in ("advice", "hostile"):
        kind = "refusal"
        lines = [tx["refuse_hostile"] if intent == "hostile" else tx["refuse"]]
    elif intent == "medicines":
        meds, held, waiting = _medicines(s, patient_id)
        if not meds:
            lines = [tx["meds_none"]]
        else:
            lines = [tx["meds_intro"]]
            srcs = _src_rows(s, [m["source_ref_id"] for m in meds])
            for m, src in zip(meds, srcs):
                lines.append(f"• {m['title']}" + (f", {item_detail(m['details'] or {})}" if item_detail(m["details"] or {}) else "") + f" ({_cite(src)})")
            ids = [m["source_ref_id"] for m in meds]
        if held:
            lines.append(tx["meds_held"].format(n=held))
        if waiting and meds:
            lines.append(tx["meds_waiting"].format(n=waiting))
    elif intent == "followups":
        rows = s.execute(text("""SELECT f.what, f.due_date, f.anchor_date, f.due_text, f.source_ref_id FROM follow_ups f
                                 WHERE f.patient_id = :p AND f.status = 'confirmed' ORDER BY f.due_date NULLS LAST"""), {"p": patient_id}).mappings().all()
        if not rows:
            lines = [tx["fu_none"]]
        else:
            lines = [tx["fu_intro"]]
            for r in rows:
                when = f"{r['due_date']:%d %b %Y}" if r["due_date"] else tx["fu_nodate"]
                lines.append(f"• {r['what']}: {when}")
            ids = [r["source_ref_id"] for r in rows]
    elif intent == "allergy":
        state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id = :p"), {"p": patient_id}).scalar_one()
        if state == "listed":
            rows = s.execute(text("SELECT substance, reaction, source_ref_id FROM allergies WHERE patient_id = :p AND is_current AND active"), {"p": patient_id}).mappings().all()
            lines = [tx["al_listed"]] + [f"• {r['substance']}" + (f" ({r['reaction']})" if r["reaction"] else "") for r in rows]
            ids = [r["source_ref_id"] for r in rows]
        elif state == "no_known_allergies":
            sid = s.execute(text("SELECT source_ref_id FROM allergy_status WHERE patient_id = :p"), {"p": patient_id}).scalar()
            lines, ids = [tx["al_none"]], ([sid] if sid else [])
        else:
            lines = [tx["al_unknown"]]
    elif intent == "warnings":
        rows = s.execute(text("""SELECT c.title, c.source_ref_id FROM care_plan_items c WHERE c.patient_id = :p AND c.is_current AND c.status = 'active'
                                 AND c.kind = 'warning_sign' ORDER BY c.alert_level DESC"""), {"p": patient_id}).mappings().all()
        if not rows:
            lines = [tx["warn_none"]]
        else:
            quotes = {r["source_ref_id"]: q for r, q in zip(rows, [x["quote"] for x in _src_rows(s, [r["source_ref_id"] for r in rows])])}
            lines = [tx["warn_intro"]] + [f"• “{quotes.get(r['source_ref_id'], r['title'])}”" for r in rows] + [tx["warn_outro"]]
            ids = [r["source_ref_id"] for r in rows]
    elif intent == "changes":
        rows = s.execute(text("""SELECT summary, occurred_at FROM timeline_events WHERE patient_id = :p AND event_type IN
                                 ('item_confirmed','change_confirmed','change_rejected','document_processed','visit_processed','follow_up_confirmed')
                                 ORDER BY occurred_at DESC LIMIT 5"""), {"p": patient_id}).mappings().all()
        lines = [tx["chg_intro"]] + [f"• {r['occurred_at']:%d %b}: {r['summary']}" for r in rows] if rows else [tx["chg_none"]]
    else:
        kind = "plain"
        lines = [tx["unknown"]]

    reply = "\n".join(lines)
    src_list = _src_rows(s, ids)
    exempt = not ids
    ctx = GuardContext(language=lang, source_ids=[str(i) for i in ids], source_exempt=exempt, stored_numbers=digits_of(reply))
    result = guard_output(reply, ctx)
    if lang != "en" and detect_language(reply) != lang:
        result.text = FALLBACK[lang]
    out_id = store_output(s, patient_id=patient_id, output_type="chat_reply", language=lang, shown=result.text, draft=reply,
                          status="pass" if result.passed else "blocked", reasons=result.reasons, source_ref_ids=ids, source_exempt=exempt)

    conv = s.execute(text("""INSERT INTO conversations (patient_id, channel, external_id) VALUES (:p, 'in_app', :e)
                             ON CONFLICT (patient_id, channel, external_id) DO UPDATE SET external_id = EXCLUDED.external_id RETURNING id"""),
                     {"p": patient_id, "e": str(user_id) if user_id else "device"}).scalar_one()
    s.execute(text("""INSERT INTO messages (patient_id, conversation_id, direction, sender_user_id, body, language)
                      VALUES (:p, :c, 'inbound', :u, :b, CAST(:l AS lang_code))"""), {"p": patient_id, "c": conv, "u": user_id, "b": message[:2000], "l": detect_language(message)})
    s.execute(text("""INSERT INTO messages (patient_id, conversation_id, direction, body, language, output_id)
                      VALUES (:p, :c, 'outbound', :b, CAST(:l AS lang_code), :o)"""), {"p": patient_id, "c": conv, "b": result.text, "l": lang, "o": out_id})
    write_audit(s, actor_type="user" if user_id else "device", actor_id=user_id, patient_id=patient_id, action="chat.answered", entity_type="generated_output",
                entity_id=out_id, after={"intent": intent, "kind": kind})
    return {"id": str(out_id), "text": result.text, "language": lang, "intent": intent, "kind": kind, "sources": src_list, "passed": result.passed}


def history(s: Session, patient_id: UUID, user_id: UUID, limit: int = 40) -> list[dict]:
    rows = s.execute(text("""SELECT m.direction, m.body, m.language, m.created_at FROM messages m JOIN conversations c ON c.id = m.conversation_id
                             WHERE m.patient_id = :p AND c.external_id = :e ORDER BY m.created_at DESC, m.direction DESC LIMIT :n"""),
                     {"p": patient_id, "e": str(user_id), "n": limit}).mappings().all()
    return [{"direction": r["direction"], "text": r["body"], "language": r["language"], "at": r["created_at"].isoformat()} for r in reversed(rows)]
