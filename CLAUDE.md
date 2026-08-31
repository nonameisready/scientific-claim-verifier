# Project context for Claude Code

Read this first. It carries the decisions made before the repository had a
leaderboard, so a fresh session starts where the last one stopped.

## What this is

A **deterministic consistency verifier** for physical claims, plus the public
leaderboard built on top of it. Any system that claims to have found an
orbital relation, a conservation relation, or a general law submits its
claims; the verifier checks them against physics and reports what held.

The pitch in one line: *define the exam everyone has to sit*, rather than
ship one more system that claims to pass it.

## Why deterministic scoring is the whole point

This is the fourth project in a line by the same author (Hui Mao):

| | Paper | arXiv |
| --- | --- | --- |
| 1 | Evidence-Based Scientific Question Discovery | [2608.09968](https://arxiv.org/abs/2608.09968) |
| 2 | Historical Backtesting for Scientific Question Discovery | [2608.16795](https://arxiv.org/abs/2608.16795) |
| 3 | What Makes a Scientific Question Succeed? | under review at Information Processing & Management |

Papers 2 and 3 score systems with an LLM judge over retrieved future
literature. Paper 2's own seven-rater study found **two independent human
annotators agree at only kappa = 0.17** on that outcome taxonomy, and a
second judge in Paper 3 agrees at kappa = 0.21.

**A leaderboard cannot be built on a metric that weak.** The first system
ranked last will dispute it and will be right. That is the specific gap this
repository closes: Kepler's third law either holds to within tolerance or it
does not, and no rater is involved.

The intended sequence is therefore: build the deterministic layer here first,
and let the question-discovery leaderboard plug into it later, replacing part
of its judge dependency with checks that have no rater.

## Decisions already made -- do not relitigate

1. **Physics consistency first, question quality later.** These are two
   different benchmarks. Building both at once builds neither. The
   deterministic one comes first because it supplies the credible scoring
   layer the other one lacks.

2. **Inapplicable is not a pass.** A check that cannot run on a claim returns
   `passed=None` and is excluded from the denominator. Counting it as a pass
   would make vagueness the winning strategy -- exactly the failure mode
   Paper 3 documented, where broad questions farmed engagement without ever
   resolving.

3. **`checkable_rate` is reported beside every pass rate,** and systems below
   the floor sort last however well they scored. A high score over three
   checkable claims is a smaller measurement, not a better result.

4. **Seed the leaderboard rather than wait for submissions.** An empty
   leaderboard is a dead artifact. Paper 2 shipped four baselines with the
   protocol for this reason; do the same here before announcing anything.

5. **Astronomy is the first test bed, not the scope.** The check skeleton is
   parse claim -> extract quantities -> test invariants -> report violations.
   That transfers unchanged to materials (formation energy, charge balance,
   stoichiometry) and climate (energy budget closure). Keep the core free of
   astronomy-specific assumptions.

## What exists now

- `verifier/checks.py` -- four working checks: units declared, Kepler's third
  law, energy/angular-momentum consistency, limiting-case degeneration.
- `verifier/score.py` -- per-system scoring and leaderboard ordering.
- `tests/test_checks.py` -- 10 offline tests, no network or API key.
- `examples/submission_example.jsonl` -- a five-claim submission that
  exercises a pass, a Kepler violation, an unbound orbit, and a vague claim.

## Working conventions

Mirrors the Paper 3 repository (`nonameisready/scientific-question-outcome-prediction-indicators`):
single-script pipeline stages, offline tests that need no key, frozen
artifacts committed while raw dumps stay gitignored.

Two rules specific to this project:

- **No model in the scoring path.** If a check needs a judgement call, it does
  not belong in the verifier; put it in a separate, clearly-labelled tier.
- **Every check states its tolerance and its inapplicability condition.** A
  check that silently passes when data is missing is worse than no check.

## Next steps

1. Add checks with the widest reach per unit of work: dimensional consistency
   of a stated relation, internal numerical consistency (do the quoted numbers
   satisfy the quoted formula), and monotonicity/sign constraints.
2. Freeze a claim set drawn from published astronomy results, including known
   erroneous ones, so the verifier's own sensitivity can be measured.
3. Seed the leaderboard by running available agents through it.
4. Write the benchmark paper. It is the artifact that makes the leaderboard
   citable.

Step 2 is the gate. Without a frozen claim set with known ground truth, there
is no way to state the verifier's false-pass and false-fail rates -- and a
verifier whose own error rate is unmeasured has no standing to rank anyone.
