"""Detects lines in a document or transcript that try to instruct the assistant (prompt injection).

A document is data. The model is told so, but the real defence is in code: a line that looks like an instruction to
CareSaathi is dropped before anything is stored, counted, and shown to a person. It never becomes a plan item, a warning
sign, a tool call or an approval. The list is deliberately small and conservative: it must not fire on ordinary medical
wording ("ignore minor nausea", "do not skip doses")."""
from __future__ import annotations

import re

from .text import normalize_text

_PATTERNS = tuple(re.compile(p) for p in (
    r"\b(?:ignore|disregard|forget|override)\b.{0,30}\b(?:rules|instructions|guidelines|system prompt|safety)\b",
    r"\b(?:system prompt|developer message|your instructions|as an ai)\b",
    r"\byou are (?:now )?(?:an? )?(?:ai|assistant|chatbot|doctor|pharmacist)\b",
    r"\b(?:pretend|act) (?:to be|as)\b",
    r"\b(?:say|tell|state|claim|report|inform|confirm)\b.{0,50}\b(?:safe|harmless|no risk|risk[- ]free)\b",
    r"\b(?:share|send|forward|post|email|whatsapp|message)\b.{0,40}\b(?:emergency card|card link|the link|this link|everyone|all contacts)\b",
    r"\b(?:mark|set|label)\b.{0,30}\b(?:as safe|safe)\b",
    # Hindi and Marathi
    r"(?:निर्देश|नियम|सूचना).{0,20}(?:अनदेखा|नज़रअंदाज|दुर्लक्ष)",
    r"(?:सुरक्षित|सुरक्षित).{0,20}(?:बताएं|बताओ|सांगा)",
))


def looks_like_injection(text: str) -> bool:
    t = normalize_text(text)
    return bool(t) and any(p.search(t) for p in _PATTERNS)
