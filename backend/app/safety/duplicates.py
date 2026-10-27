"""Duplicate-ingredient detector (A8). Two listed medicines that share an ingredient are shown with both sources and a
question for the doctor or pharmacist. It never says either one should be stopped, and never calls anything an overdose."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DupItem:
    key: str                          # item identity (versions of one item share it)
    title: str
    ingredients: frozenset[str]       # normalized ingredient names


@dataclass(frozen=True)
class DupGroup:
    ingredient: str
    items: tuple[DupItem, ...] = field(default_factory=tuple)


def find_duplicates(items: list[DupItem]) -> list[DupGroup]:
    by_ing: dict[str, dict[str, DupItem]] = {}
    for it in items:
        for ing in it.ingredients:
            by_ing.setdefault(ing, {}).setdefault(it.key, it)
    return [DupGroup(ing, tuple(group.values())) for ing, group in sorted(by_ing.items()) if len(group) > 1]


def duplicate_question(g: DupGroup) -> str:
    names = " and ".join(i.title for i in g.items) if len(g.items) == 2 else ", ".join(i.title for i in g.items[:-1]) + " and " + g.items[-1].title
    return (f"{names} both list {g.ingredient}. Could the doctor or pharmacist confirm whether both are meant to be taken? "
            "We are only asking.")
