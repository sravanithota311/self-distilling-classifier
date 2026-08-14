"""Simple, honest drift signals.

Two complementary views:
  * agreement drift  — did the student suddenly fall behind the teacher?
    (a drop vs the recent rolling average = the stream moved under us)
  * vocabulary drift — how much of this batch's language is new?
    (new topics show up as unseen tokens)
"""
from __future__ import annotations

import re


def rolling_mean(values: list[float], window: int) -> float | None:
    recent = values[-window:]
    return sum(recent) / len(recent) if recent else None


def agreement_drift(current: float, history: list[float], window: int) -> float:
    """How far below the recent average is this run? Positive = worse."""
    baseline = rolling_mean(history, window)
    if baseline is None:
        return 0.0
    return round(baseline - current, 4)


_TOKEN = re.compile(r"[a-z]{3,}")


def _tokens(texts: list[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        out.update(_TOKEN.findall(t.lower()))
    return out


def vocabulary_drift(new_texts: list[str], known_texts: list[str]) -> float:
    """Fraction of this batch's vocabulary that is new vs everything seen before."""
    new_vocab = _tokens(new_texts)
    if not new_vocab:
        return 0.0
    known = _tokens(known_texts)
    unseen = new_vocab - known
    return round(len(unseen) / len(new_vocab), 4)
