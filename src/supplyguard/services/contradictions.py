import re

from supplyguard.domain.models import Citation


def detect(citations: list[Citation]) -> list[str]:
    """Flag likely policy conflicts when the same monetary subject has multiple values."""
    amounts: dict[str, set[str]] = {}
    for c in citations:
        for amount in re.findall(r"(?:USD|\$)\s?[\d,]+", c.excerpt, flags=re.IGNORECASE):
            subject = "approval threshold" if "approv" in c.excerpt.lower() else "monetary rule"
            amounts.setdefault(subject, set()).add(amount.upper().replace(" ", ""))
    return [f"Potential contradiction: {subject} has values {sorted(values)} across evidence."
            for subject, values in amounts.items() if len(values) > 1]

