# Scientific Claim Verifier

**A deterministic consistency check for claimed physical relations, and the
public leaderboard built on it.**

Systems that claim to have discovered something — an orbital relation, a
conservation relation, a general law — are usually evaluated by asking a
person or a model whether the claim looks right. This repository takes a
narrower and harder line: submit the claim with its numbers, and the verifier
checks whether physics permits it.

```
claim + quantities  ->  invariant checks  ->  verdicts  ->  leaderboard row
```

No rater is involved. Kepler's third law either holds to within the stated
tolerance or it does not.

## Why this exists

The companion line of work
([arXiv:2608.09968](https://arxiv.org/abs/2608.09968),
[arXiv:2608.16795](https://arxiv.org/abs/2608.16795)) scores research systems
with an LLM judge over future literature. Its own reliability study found two
independent human annotators agreeing at **kappa = 0.17** on the outcome
taxonomy — below every model–model pair measured.

That is a usable research instrument and an unusable leaderboard metric: the
system ranked last would dispute the ranking, and would be right. A benchmark
that ranks systems publicly needs scoring with no rater in it. That is what
this repository provides.

## What it checks today

| Check | Applies when | Fails when |
| --- | --- | --- |
| `units_declared` | any quantities given | a dimensional quantity has a missing or unrecognised unit |
| `kepler_third_law` | period, semi-major axis, total mass | $P^2 \neq a^3/M$ beyond tolerance |
| `energy_angular_momentum` | axis, mass, and energy or angular momentum | stated values contradict the orbit, or eccentricity is unbound |
| `limiting_case` | a limit value and a known value | the proposed relation fails to degenerate to established theory |

## Two rules that keep the table honest

**Inapplicable is not a pass.** A check that cannot run returns `None` and
leaves the denominator. Counting it as a pass would make vagueness the
winning strategy.

**`checkable_rate` sits beside every pass rate**, and systems below the floor
sort last however well they scored. A perfect score over three checkable
claims is a smaller measurement, not a better result.

## Try it

```bash
python -m pytest tests -q          # 10 offline tests, no key needed

python - <<'PY'
from verifier.score import load_claims, score_system
r = score_system(load_claims("examples/submission_example.jsonl"))
print(r["checkable_rate"], r["consistency_pass_rate"])
for f in r["failures"]:
    print(f["claim_id"], f["check"], "-", f["detail"])
PY
```

The example submission contains a correct orbit, an orbit off by an order of
magnitude, an unbound eccentricity reported as bound, and a claim too vague to
check. The verifier separates all four.

## Submission format

One JSON object per line:

```json
{
  "claim_id": "c001",
  "system": "your-agent",
  "claim_type": "orbital_relation",
  "statement": "natural-language claim",
  "quantities": {"period": 3.5247, "semi_major_axis": 0.04747, "total_mass": 1.15},
  "units": {"period": "day", "semi_major_axis": "au", "total_mass": "msun"},
  "tolerance": 0.05
}
```

## Status

Early. The checks work and are tested; the frozen claim set, the verifier's
own false-pass/false-fail rates, and the leaderboard itself are not built yet.
See [`CLAUDE.md`](CLAUDE.md) for the design decisions and
[`docs/design.md`](docs/design.md) for the benchmark specification.

A verifier whose own error rate is unmeasured has no standing to rank anyone,
so that measurement comes before any public ranking.

License: Apache-2.0.
