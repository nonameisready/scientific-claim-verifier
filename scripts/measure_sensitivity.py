"""Stage: measure the verifier against the frozen claim set.

    python scripts/measure_sensitivity.py

Reads `benchmark/claims_v1.jsonl`, writes `benchmark/sensitivity_v1.json`,
prints the markdown block that goes in the benchmark card. Offline: no
network, no key, no model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.sensitivity import load_labelled, report, run, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLAIM_SET = ROOT / "benchmark" / "claims_v1.jsonl"
ARTIFACT = ROOT / "benchmark" / "sensitivity_v1.json"


def main() -> int:
    records = load_labelled(CLAIM_SET)
    rows = run(records)
    summary = summarise(rows)
    ARTIFACT.write_text(json.dumps(
        {"claim_set": CLAIM_SET.name, "summary": summary, "per_claim": rows},
        indent=2, ensure_ascii=False,
    ) + "\n")
    print(report(rows, summary))
    if summary["disagreements"]:
        print("\nClaims that did not behave as labelled:")
        for d in summary["disagreements"]:
            print(f"  {d['claim_id']} ({d['label']}) -> {d['outcome']}: {d['detail'][:120]}")
    print(f"\nwrote {ARTIFACT.relative_to(ROOT)}")
    return 1 if summary["disagreements"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
