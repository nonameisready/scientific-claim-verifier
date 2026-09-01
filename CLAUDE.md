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

- `verifier/units.py` -- dimensions over (length, mass, time, temperature),
  25 units with generous aliases, conversion into the canonical set
  (au, Msun, yr, K).
- `verifier/relations.py` -- a whitelisted AST interpreter that evaluates an
  asserted relation twice, in dimensions and in numbers, plus the named
  relation library (`kepler3`, `vis_viva`, `escape_velocity`, ...). Submitted
  text is parsed, never executed.
- `verifier/checks.py` -- seven per-claim checks and one submission-level
  check: units declared, physical bounds, dimensional consistency, numerical
  consistency, Kepler's third law, energy/angular-momentum consistency,
  limiting-case degeneration, cross-claim consistency.
- `verifier/score.py` -- per-system scoring and leaderboard ordering.
- `verifier/sensitivity.py` + `scripts/measure_sensitivity.py` -- the
  calibration stage.
- `benchmark/claims_v1.jsonl` -- **the frozen claim set**: 62 labelled claims.
  `benchmark/sensitivity_v1.json` is the frozen measurement,
  `benchmark/README.md` the card that states its limits.
- `tests/` -- 31 offline tests, no network or API key. `test_claim_set.py`
  pins the calibration itself, so a change that moves the false-fail or
  false-pass rate cannot land without the committed number moving with it.
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
- **When in doubt, decline.** A false fail costs more than a missed catch:
  one wrongly-rejected submission from a serious group ends the benchmark. A
  check that cannot distinguish a wrong claim from an unusual but legal one
  returns `None` and says why.
- **Never move a tolerance to make a label come out right.** When the frozen
  set and the verifier disagree, fix the check or document the limit. Doing
  the reverse is how a calibration becomes an advertisement.

## Three decisions made while building the claim set

Recorded because each was a choice between two defensible options, and the
reasoning is not recoverable from the diff.

6. **Three ground-truth classes, not two.** A withdrawn detection --
   PSR B1829-10's planet, Le Verrier's Vulcan -- is arithmetically flawless
   and wrong about the world. Labelling those `inconsistent` would report the
   boundary of consistency checking as a defect in the verifier; leaving them
   out of the set would hide the boundary. They are labelled
   `consistent_but_refuted`, expected to pass, and measured separately as the
   method's blind spot.

7. **Rates ship with their upper bounds.** Zero false fails in 41 correct
   claims is a false-fail rate below about 7%, not zero. `sensitivity.py`
   computes a one-sided 95% Clopper-Pearson bound for each rate so the table
   cannot overclaim by omission.

8. **Cross-claim comparison is an allowlist.** Only quantities that are
   properties of the subject are compared across claims. `radius` and `speed`
   are configuration-dependent -- one claim's perihelion distance is not
   another's mean orbital radius -- and a check that compared everything
   sharing a name would reject correct pairs for eccentric orbits. The
   failure mode of this check is a false fail, so it only compares what it
   knows is comparable.

## Next steps

1. **Get the false-pass rate measured against errors the author did not
   choose.** The seeded errors and the checks currently share an author, so
   0.0 is a floor on performance rather than an estimate of it. This is now
   the weakest claim in the repository, and it is stated as such in
   `benchmark/README.md`. Options: an adversarial set from someone else, or
   errors mined from published errata.
2. Seed the leaderboard by running available agents through the verifier.
3. Monotonicity constraints, and more known limits for `limiting_case` --
   the checks with reach left in them.
4. Write the benchmark paper. It is the artifact that makes the leaderboard
   citable.

The gate is cleared: the frozen claim set exists and the verifier's error
rates are published with their bounds. What replaces it as the gate is item 1
-- a leaderboard may be seeded before that lands, but no ranking should be
announced while the only evidence of coverage is self-graded.
