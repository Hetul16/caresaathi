"""Every model-worded output goes through here: the keyword guard first, then (in live mode) a second-pass judge.
The judge fails closed: if it flags the draft or cannot decide, the family sees the safe fallback and the draft is kept for the trust panel."""
from __future__ import annotations

from ..clients.models import ModelClient, Usage
from ..safety.guard import GuardContext, GuardResult, guard_output


def guard_with_judge(client: ModelClient, text: str, ctx: GuardContext) -> tuple[GuardResult, Usage | None]:
    result = guard_output(text, ctx)
    if not result.passed:
        return result, None
    flagged, usage = client.judge_text(text)
    if flagged is False:
        return result, usage
    # flagged (True) or undecided (None): block, with the reason recorded
    blocked = guard_output(text, GuardContext(language=ctx.language, source_ids=[], source_exempt=False))     # yields the language's fallback text
    blocked.reasons = ["judge_flagged" if flagged else "judge_undecided"]
    return blocked, usage
