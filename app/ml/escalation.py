"""
Stage-2 escalation: run the transformer only when the fast model score is high enough.
"""


def should_escalate(p_fast: float, threshold: float = 0.5) -> tuple[bool, str]:
    """
    Return whether to invoke the transformer on the same raw text.

    Stage 1 — fast model score below `threshold`: skip transformer (low distress).
    Stage 2 — score at or above `threshold`: run transformer; its score is final.
    """
    if p_fast >= threshold:
        return True, "fast_threshold"
    return False, "none"
