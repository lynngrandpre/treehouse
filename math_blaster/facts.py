"""The addition fact space (1+1 .. 12+12, order-independent) plus the two
things that make each question fair to a 9-year-old: distractors that reflect
real near-miss mistakes (off-by-one, off-by-two, near-doubles, decade slips)
rather than random numbers, and a one-line strategy hint keyed to whichever
mental-math trick actually applies to that fact (doubles, near-doubles, +1,
+2, make-10, or counting on from a big addend).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

MIN_ADDEND = 1
MAX_ADDEND = 12


@dataclass(frozen=True)
class Fact:
    # a <= b -- a fact and its reverse (7+8 vs 8+7) are the same underlying
    # fact, just shown in a different order (see prompt()).
    a: int
    b: int

    @property
    def key(self) -> str:
        return f"{self.a}+{self.b}"

    @property
    def answer(self) -> int:
        return self.a + self.b

    def prompt(self, swap: bool) -> str:
        first, second = (self.b, self.a) if swap else (self.a, self.b)
        return f"{first} + {second}"


ALL_FACTS: list[Fact] = [Fact(a, b) for a in range(MIN_ADDEND, MAX_ADDEND + 1) for b in range(a, MAX_ADDEND + 1)]
FACTS_BY_KEY: dict[str, Fact] = {f.key: f for f in ALL_FACTS}


def _candidate_distractors(fact: Fact) -> set[int]:
    correct = fact.answer
    a, b = fact.a, fact.b
    candidates = {
        correct + 1,
        correct - 1,
        correct + 2,
        correct - 2,
        a + b + 10,  # decade slip -- easy to make when counting on fingers past ten
        a + b - 10,
        (a + 1) + b,  # off-by-one on one addend
        a + (b + 1),
        (a - 1) + b,
        a + (b - 1),
        2 * b,  # mistaking this for the nearby double
        2 * a,
    }
    candidates.discard(correct)
    return {c for c in candidates if c > 0}


def generate_choices(fact: Fact, rng: random.Random) -> list[int]:
    """Four wrong answers plus the correct one, shuffled into a random order.
    Distractors are drawn from real near-miss mistakes so the wrong options
    are actually tempting, not obviously silly."""
    correct = fact.answer
    pool = list(_candidate_distractors(fact))
    rng.shuffle(pool)
    chosen = pool[:4]

    # The near-miss pool can run short for facts at the edges of the range
    # (e.g. 1+1); top up with generic nearby offsets until we have four.
    offset = 3
    while len(chosen) < 4:
        for delta in (offset, -offset):
            candidate = correct + delta
            if candidate > 0 and candidate != correct and candidate not in chosen:
                chosen.append(candidate)
                if len(chosen) == 4:
                    break
        offset += 1

    choices = chosen[:4] + [correct]
    rng.shuffle(choices)
    return choices


def strategy_hint(fact: Fact) -> str:
    """A one-line mental-math trick for this fact, shown briefly after a
    wrong or slow answer -- never a lecture, just a nudge."""
    a, b = fact.a, fact.b
    if a == b:
        return f"{a} + {a} is a double = {fact.answer}!"
    if abs(a - b) == 1:
        lo = min(a, b)
        return f"{lo}+{lo}={2 * lo}, one more makes {fact.answer}!"
    if a == 1 or b == 1:
        other = b if a == 1 else a
        return f"+1 just means the next number after {other}: {fact.answer}!"
    if a == 2 or b == 2:
        other = b if a == 2 else a
        return f"+2 means count up two from {other}: {fact.answer}!"
    if a >= 10 or b >= 10:
        big, small = (a, b) if a >= b else (b, a)
        return f"Start at {big}, count up {small}: {fact.answer}!"
    ten_partner = 10 - a
    if 0 < ten_partner < b:
        remainder = b - ten_partner
        return f"Make 10: {a}+{ten_partner}=10, then +{remainder} more = {fact.answer}!"
    return f"{a} + {b} = {fact.answer}."
