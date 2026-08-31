"""Turn per-claim verdicts into the leaderboard row for a system.

Two rules keep the table honest.

Inapplicable checks are excluded from the denominator rather than counted as
passes. A system that ships claims too thin to check should not out-rank one
whose claims are rich enough to be wrong.

`checkable_rate` is therefore reported alongside the pass rates, and a
submission below the floor is flagged. Without it, emitting vague claims is
the dominant strategy -- the same failure mode the question-discovery work
found when broad questions farmed engagement.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from .checks import Claim, Verdict, verify

CHECKABLE_FLOOR = 0.5


def load_claims(path: Path) -> list[Claim]:
    claims = []
    for line in Path(path).open():
        line = line.strip()
        if line:
            claims.append(Claim(**json.loads(line)))
    return claims


def score_system(claims: list[Claim]) -> dict:
    per_check: dict[str, list[bool]] = defaultdict(list)
    applicable, total = 0, 0
    failures = []

    for claim in claims:
        verdicts = verify(claim)
        any_applicable = False
        for v in verdicts:
            if v.passed is None:
                continue
            any_applicable = True
            per_check[v.check].append(v.passed)
            if not v.passed:
                failures.append({"claim_id": claim.claim_id, **asdict(v)})
        total += 1
        applicable += int(any_applicable)

    def rate(values: list[bool]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    all_results = [r for results in per_check.values() for r in results]
    checkable = round(applicable / total, 4) if total else 0.0
    return {
        "n_claims": total,
        "n_checkable": applicable,
        "checkable_rate": checkable,
        "below_checkable_floor": checkable < CHECKABLE_FLOOR,
        "consistency_pass_rate": rate(all_results),
        "per_check": {k: {"n": len(v), "pass_rate": rate(v)} for k, v in sorted(per_check.items())},
        "failures": failures,
    }


def leaderboard(submissions: dict[str, list[Claim]]) -> list[dict]:
    """One row per system, ordered by consistency then by checkable rate.

    Systems below the checkable floor sort last whatever their pass rate: a
    high score over a handful of checkable claims is not a better result, it
    is a smaller measurement.
    """
    rows = []
    for system, claims in submissions.items():
        row = {"system": system, **score_system(claims)}
        row.pop("failures", None)
        rows.append(row)
    return sorted(
        rows,
        key=lambda r: (
            r["below_checkable_floor"],
            -(r["consistency_pass_rate"] or 0.0),
            -r["checkable_rate"],
        ),
    )
