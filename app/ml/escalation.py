import re
import random

# Negation cues that trigger DistilBERT escalation
NEGATION_CUES = {
    "not",
    "never",
    "don't",
    "doesn't",
    "didn't",
    "won't",
    "can't",
    "cannot",
    "no",
    "nobody",
    "nothing",
    "nowhere",
    "nor",
    "neither",
    "hardly",
    "barely",
    "scarcely",
    "dont",
    "cant",
    "wont",
    "doesnt",
    "didnt",  # common no-apostrophe forms
}


def has_negation(text: str) -> bool:
    """Return True if any negation cue is found in the text."""
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(tokens & NEGATION_CUES)


def should_escalate(
    text: str,
    p_fast: float,
    uncertainty_band: float = 0.25,
    audit_rate: float = 0.10,
) -> tuple[bool, str]:
    """
    Dual-trigger escalation logic — OR across three triggers.

    Returns (escalate: bool, reason: str)

    Trigger 1 — Uncertainty  : fast model confidence is ambiguous
    Trigger 2 — Negation     : linguistic negation cues detected
    Trigger 3 — Random audit : 10% of confident predictions audited
    """
    # Trigger 1 — uncertainty band
    if abs(p_fast - 0.5) < uncertainty_band:
        return True, "uncertainty"

    # Trigger 2 — negation detected in raw text
    if has_negation(text):
        return True, "negation"

    # Trigger 3 — random quality audit
    if random.random() < audit_rate:
        return True, "audit"

    return False, "none"
