"""Small helpers for error messages."""
from __future__ import annotations

import difflib
from collections.abc import Iterable


def did_you_mean(name: object, candidates: Iterable[object]) -> str:
    """` Did you mean 'X'?` for the closest candidate, or an empty string.

    A difference in capital letters is the commonest mistake, so it is
    checked first and the comparison ignores case.
    """
    options = [str(c) for c in candidates]
    by_lower: dict[str, str] = {}
    for option in options:
        by_lower.setdefault(option.lower(), option)
    probe = str(name).lower()
    same = by_lower.get(probe)
    if same is not None and same != str(name):
        return f" Did you mean {same!r}?"
    close = difflib.get_close_matches(probe, list(by_lower), n=1, cutoff=0.6)
    return f" Did you mean {by_lower[close[0]]!r}?" if close else ""
