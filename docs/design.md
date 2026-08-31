# Benchmark design

## The claim this benchmark makes

A system that says it discovered a physical relation has made a checkable
assertion. Most evaluation of such systems asks a reader whether the claim
seems plausible. This benchmark asks arithmetic instead.

The scope is deliberately narrow. The verifier does not judge whether a claim
is interesting, novel, or important — the companion work does that, and its
own reliability study shows how hard it is. The verifier answers one question:
**is this claim internally consistent with physics it must obey?**

Narrowness is the source of the credibility. A benchmark that scores taste
inherits the disagreement of the people scoring it. A benchmark that scores
conservation laws does not.

## Scoring

Per claim, each check returns pass / fail / inapplicable.

Per system:

| Column | Definition |
| --- | --- |
| `n_claims` | claims submitted |
| `checkable_rate` | fraction on which at least one check applied |
| `consistency_pass_rate` | passes over applicable checks |
| `per_check` | the same, split by check |
| `below_checkable_floor` | `checkable_rate` under 0.5 |

Ordering: systems below the checkable floor sort last, then by
`consistency_pass_rate`, then by `checkable_rate`.

### Why inapplicable is excluded rather than passed

If inapplicable counted as a pass, the optimal submission would be a hundred
claims with no numbers in them. This is not hypothetical: the companion
Paper 3 found that broad, unanchored questions attracted near-ceiling
engagement while resolving almost nothing, and that its LLM-only baseline
named a specific object in 5% of its questions against 95–100% for the
structure-first pipelines. Vagueness scores well on any metric that does not
price it. `checkable_rate` prices it.

## What must exist before any public ranking

**A frozen claim set with known ground truth**, including published results
later shown to be wrong. Without it the verifier's own false-pass and
false-fail rates are unknown, and a verifier with an unmeasured error rate has
no standing to rank anyone. This is the same discipline the companion protocol
applied to its judge: measure the instrument before trusting its output.

Two rates to report:

- **False pass** — the verifier clears a claim that is physically wrong.
  Mostly a coverage problem: no check applied to the thing that was wrong.
- **False fail** — the verifier rejects a correct claim. Usually a units,
  tolerance, or convention problem, and far more damaging to adoption: one
  wrongly-failed submission from a serious group ends the benchmark's
  credibility.

Tolerances are part of the specification and must be frozen with the claim
set, not tuned afterwards.

## Roadmap of checks

Ordered by reach per unit of work.

1. **Dimensional consistency of a stated relation** — parse the asserted
   formula, verify both sides carry the same dimensions. Applies to every
   quantitative claim in any field.
2. **Internal numerical consistency** — do the quoted numbers actually satisfy
   the quoted formula? Catches transcription and arithmetic errors, which are
   common and cheap to detect.
3. **Sign and monotonicity constraints** — a mass that came out negative, a
   probability above one, a cross-section that grows without bound.
4. **Limiting-case degeneration** — already implemented; extend to more known
   limits.
5. **Cross-claim consistency** — do a system's own claims contradict each
   other across a submission? A system asserting two incompatible masses for
   one object has failed regardless of which is right.

## Portability beyond astronomy

The skeleton is: parse claim, extract quantities, test invariants, report
violations. Astronomy is the first test bed because the invariants are sharp
and the data is public, not because the design is astronomical.

- **Materials** — formation-energy consistency, charge balance, stoichiometry,
  thermodynamic stability against decomposition.
- **Climate** — energy budget closure, mass conservation in flux accounting.
- **Chemistry** — reaction balancing, conservation of atoms and charge.

Keep the core free of astronomy-specific assumptions so these arrive as new
check modules rather than as a rewrite.

## Relationship to the question-discovery leaderboard

The eventual goal is a second leaderboard ranking systems on future
engagement, resolution, and premise refutation — the metrics of the companion
papers. That leaderboard is blocked on its scoring reliability
(kappa = 0.17 human–human).

This verifier is a route around part of that block: where a claim is
deterministically checkable, the check replaces the judge. The two benchmarks
stay separate, but the deterministic one supplies the scoring layer the other
one lacks.
