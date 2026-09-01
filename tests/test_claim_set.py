"""The frozen claim set is the verifier's calibration, so it is tested too.

These tests pin two different things. The integrity tests say the set is
well formed. The behaviour test says the verifier still does to it what the
committed sensitivity artifact says it did -- so a change that quietly moves
the false-fail or false-pass rate cannot land without the number moving with
it, in the same commit, where a reviewer can see it.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.sensitivity import LABELS, load_labelled, run, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLAIM_SET = ROOT / "benchmark" / "claims_v1.jsonl"
ARTIFACT = ROOT / "benchmark" / "sensitivity_v1.json"

RECORDS = load_labelled(CLAIM_SET)
ROWS = run(RECORDS)


def test_claim_ids_are_unique():
    ids = [r["claim_id"] for r in RECORDS]
    assert len(ids) == len(set(ids))


def test_every_claim_carries_a_label_and_a_source():
    for record in RECORDS:
        truth = record["ground_truth"]
        assert truth["label"] in LABELS, record["claim_id"]
        assert truth["source"], record["claim_id"]


def test_every_seeded_error_names_the_check_that_should_catch_it():
    for record in RECORDS:
        truth = record["ground_truth"]
        if truth["label"] == "inconsistent":
            assert truth["expected_check"], record["claim_id"]
            assert truth["error_type"], record["claim_id"]


def test_the_set_covers_every_check():
    applied = {check for row in ROWS for check in row["checks_applied"]}
    from verifier.checks import CHECKS, SUBMISSION_CHECKS

    expected = {
        fn.__name__.removeprefix("check_") for fn in CHECKS + SUBMISSION_CHECKS
    }
    assert expected <= applied, f"never exercised: {sorted(expected - applied)}"


def test_every_claim_behaves_as_labelled():
    off = [(r["claim_id"], r["label"], r["outcome"], r["detail"]) for r in ROWS
           if not r["as_expected"]]
    assert not off, off


def test_no_correct_claim_is_caught_by_a_cross_claim_contradiction():
    # A contradiction implicates every claim in its group, so an accidental
    # collision between two correct claims would show up here as a false fail
    # attributed to a claim that is not wrong.
    for row in ROWS:
        if "cross_claim_consistency" in row["checks_failed"]:
            assert row["label"] == "inconsistent", row["claim_id"]


def test_committed_sensitivity_artifact_matches_a_fresh_run():
    committed = json.loads(ARTIFACT.read_text())
    assert committed["summary"] == summarise(ROWS), (
        "benchmark/sensitivity_v1.json is stale: "
        "run python scripts/measure_sensitivity.py and commit the result"
    )
