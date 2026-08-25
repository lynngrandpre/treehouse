"""The spaced-repetition brain, kept entirely separate from the arcade
presentation in game.py. Per-fact stats (attempts, accuracy, speed, which
wrong answer gets picked repeatedly) drive a priority score that decides
which facts need practice; mastered facts fall in priority but drift back up
if they go unpracticed for a while, so nothing learned is forgotten for good.

Progress is the first thing in this codebase that persists across sessions
-- everywhere else, every game starts fresh. It's saved as plain JSON next to
this file, load()ed once when a session starts and save()d once when it ends.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .facts import ALL_FACTS, Fact

DATA_DIR = Path(__file__).resolve().parent / "data"
PROGRESS_PATH = DATA_DIR / "progress.json"

FAST_MS = 3000  # correct answers at or under this are "fast"
SLOW_MS = 7000  # correct answers over this count as slow, not yet fluent
MASTERY_STREAK_TARGET = 4  # consecutive fast+correct answers needed to call a fact mastered
STALE_DAYS = 14  # mastered facts unpracticed this long become due for review again


@dataclass
class FactStats:
    attempts: int = 0
    correct: int = 0
    incorrect: int = 0
    total_correct_ms: int = 0
    fast_streak: int = 0  # consecutive fast+correct answers, right now
    last_practiced: str | None = None  # ISO timestamp
    wrong_answer_counts: dict[str, int] = field(default_factory=dict)  # str(answer) -> times chosen

    @property
    def avg_correct_ms(self) -> float:
        return self.total_correct_ms / self.correct if self.correct else 0.0

    @property
    def mastered(self) -> bool:
        return self.fast_streak >= MASTERY_STREAK_TARGET

    def _stale(self, now: datetime) -> bool:
        if not self.last_practiced:
            return False
        return (now - datetime.fromisoformat(self.last_practiced)).days >= STALE_DAYS

    def status(self, now: datetime) -> str:
        """green/yellow/red/new -- drives both question selection and the
        end-of-session summary."""
        if self.attempts == 0:
            return "new"
        if self.mastered and not self._stale(now):
            return "green"
        if self.incorrect > 0 and self.fast_streak == 0:
            return "red"
        if self.correct and self.avg_correct_ms > SLOW_MS:
            return "yellow"
        if self.correct == 0:
            return "red"
        return "yellow"

    def priority(self, now: datetime) -> float:
        """Higher means "needs practice more urgently." Never-seen and
        struggling facts rank high; solidly mastered facts rank at (or near)
        zero unless they've gone stale."""
        if self.mastered and not self._stale(now):
            return 0.0
        if self.attempts == 0:
            return 5.0
        score = 10.0 - self.fast_streak * 2.0 + self.incorrect * 3.0
        if self.correct and self.avg_correct_ms > SLOW_MS:
            score += 2.0
        if self._stale(now):
            score += 1.0
        return max(score, 0.1)

    def likely_misconception(self) -> int | None:
        """The wrong answer this kid keeps picking for this fact, if a
        pattern has actually shown up (not just a one-off slip)."""
        if not self.wrong_answer_counts:
            return None
        answer, count = max(self.wrong_answer_counts.items(), key=lambda kv: kv[1])
        return int(answer) if count >= 2 else None

    def record(self, correct: bool, response_ms: int, chosen_answer: int, now: datetime) -> None:
        self.attempts += 1
        self.last_practiced = now.isoformat()
        if correct:
            self.correct += 1
            self.total_correct_ms += response_ms
            self.fast_streak = self.fast_streak + 1 if response_ms <= FAST_MS else 0
        else:
            self.incorrect += 1
            self.fast_streak = 0
            key = str(chosen_answer)
            self.wrong_answer_counts[key] = self.wrong_answer_counts.get(key, 0) + 1


_FACT_STATS_FIELDS = set(FactStats.__dataclass_fields__)


@dataclass
class Meta:
    best_streak: int = 0
    sessions_played: int = 0


_META_FIELDS = set(Meta.__dataclass_fields__)


@dataclass
class Progress:
    facts: dict[str, FactStats]
    meta: Meta

    @classmethod
    def load(cls) -> Progress:
        raw: dict = {}
        if PROGRESS_PATH.exists():
            try:
                raw = json.loads(PROGRESS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                raw = {}

        raw_facts = raw.get("facts", {})
        facts = {}
        for fact in ALL_FACTS:
            stats_raw = raw_facts.get(fact.key, {})
            facts[fact.key] = FactStats(**{k: v for k, v in stats_raw.items() if k in _FACT_STATS_FIELDS})

        meta_raw = raw.get("meta", {})
        meta = Meta(**{k: v for k, v in meta_raw.items() if k in _META_FIELDS})

        return cls(facts=facts, meta=meta)

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": asdict(self.meta),
            "facts": {key: asdict(stats) for key, stats in self.facts.items()},
        }
        PROGRESS_PATH.write_text(json.dumps(payload, indent=2))

    def stats_for(self, fact: Fact) -> FactStats:
        return self.facts[fact.key]

    def status_for(self, fact: Fact, now: datetime) -> str:
        return self.stats_for(fact).status(now)

    def target_facts(self, count: int, now: datetime, rng: random.Random) -> list[Fact]:
        """The facts most in need of practice right now -- these get folded
        into this session more often than everything else."""
        ranked = sorted(ALL_FACTS, key=lambda f: self.stats_for(f).priority(now), reverse=True)
        top_pool = ranked[: count * 3]  # keep some day-to-day variety among near-ties
        rng.shuffle(top_pool)
        return top_pool[:count]

    def known_facts(self, now: datetime, rng: random.Random) -> list[Fact]:
        """Facts this kid can already answer -- used for the easy warm-up and
        the confidence-building boss round."""
        known = [f for f in ALL_FACTS if self.status_for(f, now) in ("green", "yellow")]
        if len(known) < 5:
            known = list(ALL_FACTS)
        return known
