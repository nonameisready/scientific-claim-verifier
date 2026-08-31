"""Measure the verifier against a claim set whose answers are already known.

A verifier with an unmeasured error rate has no standing to rank anyone. This
module runs the checks over `benchmark/claims_v1.jsonl`, where every claim
carries a ground-truth label, and reports the two rates that decide whether
the leaderboard can be published:

- **false fail** -- a correct claim the verifier rejects. The rate that
  matters most, because one wrongly-rejected submission from a serious group
  ends the benchmark's credibility.
- **false pass** -- an internally inconsistent claim the verifier clears. A
  coverage gap: some check is missing, not wrong.

A third class is measured separately and deliberately excluded from both
rates. Some claims are arithmetically self-consistent and still wrong about
the world -- withdrawn detections, refuted signals, objects that do not
exist. No consistency check can reach them, by construction rather than by
oversight. Counting them as false passes would misreport a boundary of the
method as a defect in it; leaving them out of the set entirely would hide the
boundary. They are labelled `consistent_but_refuted`, the verifier is
expected to pass them, and the rate at which it does is published as the
method's blind spot.

`expected_check` records which check should catch each seeded error, so a
detection that happens for the wrong reason is visible rather than counted as
a success.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from .checks import Claim, verify, verify_submission

CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
REFUTED = "consistent_but_refuted"
LABELS = (CONSISTENT, INCONSISTENT, REFUTED)

# What the verifier is expected to do with each class.
EXPECTED_OUTCOME = {CONSISTENT: "pass", INCONSISTENT: "fail", REFUTED: "pass"}


def load_labelled(path: Path) -> list[dict]:
    """Read the frozen claim set with its ground-truth annotations intact."""
    records = []
    for line in Path(path).open():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        label = record.get("ground_truth", {}).get("label")
        if label not in LABELS:
            raise ValueError(f"{record.get('claim_id')}: unknown label {label!r}")
        records.append(record)
    return records


def run(records: list[dict]) -> list[dict]:
    """One outcome row per claim: what the verifier did and what caught it.

    Submission-level verdicts are attributed to every claim in their conflict
    group, so a contradiction between two claims marks both.
    """
    claims = [Claim.from_dict(r) for r in records]
    verdicts: dict[str, list] = {c.claim_id: verify(c) for c in claims}
    for v in verify_submission(claims):
        for cid in v.claim_ids or ():
            verdicts[cid].append(v)

    rows = []
    for record, claim in zip(records, claims):
        applied = [v for v in verdicts[claim.claim_id] if v.passed is not None]
        failed = [v for v in applied if not v.passed]
        outcome = "unchecked" if not applied else ("fail" if failed else "pass")
        truth = record["ground_truth"]
        rows.append({
            "claim_id": claim.claim_id,
            "label": truth["label"],
            "error_type": truth.get("error_type"),
            "expected_check": truth.get("expected_check"),
            "outcome": outcome,
            "as_expected": outcome == EXPECTED_OUTCOME[truth["label"]],
            "n_applied": len(applied),
            "checks_applied": sorted(v.check for v in applied),
            "checks_failed": sorted(v.check for v in failed),
            "expected_check_fired": (
                truth.get("expected_check") in {v.check for v in failed}
                if truth.get("expected_check") else None
            ),
            "detail": "; ".join(f"{v.check}: {v.detail}" for v in failed),
        })
    return rows


def _upper_bound(observed: int, n: int, alpha: float = 0.05) -> float | None:
    """One-sided 95% Clopper-Pearson upper bound on a rate.

    Reported beside every rate because the frozen set is small. Zero failures
    in 41 correct claims is not a false-fail rate of zero; it is a false-fail
    rate below about seven percent, and a benchmark that states the first
    while meaning the second has started overclaiming at the first table it
    prints.
    """
    if n <= 0:
        return None
    if observed >= n:
        return 1.0

    def cdf(p: float) -> float:
        return sum(
            math.comb(n, k) * p**k * (1.0 - p) ** (n - k)
            for k in range(observed + 1)
        )

    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if cdf(mid) > alpha:
            low = mid
        else:
            high = mid
    return round((low + high) / 2.0, 4)


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def summarise(rows: list[dict]) -> dict:
    by_label: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_label[row["label"]][row["outcome"]] += 1

    correct = by_label[CONSISTENT]
    wrong = by_label[INCONSISTENT]
    refuted = by_label[REFUTED]
    scored_correct = correct["pass"] + correct["fail"]

    seeded = [r for r in rows if r["label"] == INCONSISTENT and r["expected_check"]]
    attribution = sum(1 for r in seeded if r["expected_check_fired"])

    caught_by: Counter = Counter()
    for row in rows:
        if row["label"] == INCONSISTENT:
            for check in row["checks_failed"]:
                caught_by[check] += 1

    return {
        "n_claims": len(rows),
        "counts": {label: dict(by_label[label]) for label in LABELS},
        "false_fail_rate": _rate(correct["fail"], scored_correct),
        "false_fail_upper_95": _upper_bound(correct["fail"], scored_correct),
        "false_pass_rate": _rate(wrong["pass"], sum(wrong.values())),
        "false_pass_upper_95": _upper_bound(wrong["pass"], sum(wrong.values())),
        "detection_rate": _rate(wrong["fail"], sum(wrong.values())),
        "unchecked_rate": _rate(
            sum(by_label[l]["unchecked"] for l in LABELS), len(rows)
        ),
        "expected_check_attribution": _rate(attribution, len(seeded)),
        "blind_spot_rate": _rate(refuted["pass"], sum(refuted.values())),
        "caught_by_check": dict(sorted(caught_by.items())),
        "disagreements": [
            {k: r[k] for k in ("claim_id", "label", "outcome", "checks_failed", "detail")}
            for r in rows if not r["as_expected"]
        ],
    }


def report(rows: list[dict], summary: dict) -> str:
    """The summary as a markdown block, for pasting into the benchmark card."""
    counts = summary["counts"]
    lines = [
        "| class | n | verifier passed | verifier failed | no check applied |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label in LABELS:
        c = counts[label]
        total = sum(c.values())
        lines.append(
            f"| `{label}` | {total} | {c.get('pass', 0)} | "
            f"{c.get('fail', 0)} | {c.get('unchecked', 0)} |"
        )
    lines += [
        "",
        f"- false fail rate: **{summary['false_fail_rate']}** "
        f"(correct claims the verifier rejected), "
        f"95% upper bound {summary['false_fail_upper_95']}",
        f"- false pass rate: **{summary['false_pass_rate']}** "
        f"(inconsistent claims the verifier cleared), "
        f"95% upper bound {summary['false_pass_upper_95']}",
        f"- detection rate: **{summary['detection_rate']}** "
        "(inconsistent claims the verifier caught)",
        f"- attribution: **{summary['expected_check_attribution']}** "
        "(seeded errors caught by the check named for them)",
        f"- blind spot: **{summary['blind_spot_rate']}** of self-consistent but "
        "refuted claims pass, as expected — the measured limit of the method",
    ]
    return "\n".join(lines)
