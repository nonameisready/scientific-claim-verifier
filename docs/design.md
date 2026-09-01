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
| `consistency_pass_rate` | passes over applicable check instances |
| `claim_pass_rate` | checkable claims with no failing check |
| `per_check` | the same, split by check |
| `below_checkable_floor` | `checkable_rate` under 0.5 |

Two pass rates are reported because they weight differently. Checks overlap on
purpose -- a claim citing `kepler3` is tested both by the dedicated Kepler
check and by the general numbers-versus-formula check -- so
`consistency_pass_rate`, which is over check instances, counts a richly
specified claim more than a thin one. `claim_pass_rate` is over claims and
does not move when two checks happen to test the same physics. A gap between
them says the failures are concentrated in a few heavily-checked claims.

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

## Calibration: the verifier's own error rates

**A frozen claim set with known ground truth** had to exist before any public
ranking, including published results later shown to be wrong. Without it the
verifier's own false-pass and false-fail rates are unknown, and a verifier
with an unmeasured error rate has no standing to rank anyone. This is the same
discipline the companion protocol applied to its judge: measure the instrument
before trusting its output.

It exists: `benchmark/claims_v1.jsonl`, 62 labelled claims, measured by
`scripts/measure_sensitivity.py` into `benchmark/sensitivity_v1.json`. Results
and their limits are in `benchmark/README.md`.

Three rates, because two are not enough:

- **False pass** — the verifier clears a claim that is internally
  inconsistent. A coverage problem: some check is missing, not wrong.
- **False fail** — the verifier rejects a correct claim. Usually a units,
  tolerance, or convention problem, and far more damaging to adoption: one
  wrongly-failed submission from a serious group ends the benchmark's
  credibility. Every design choice that trades a catch for a decline is made
  in this direction on purpose.
- **Blind spot** — the verifier passes a claim that is arithmetically
  self-consistent and wrong about the world. This is not an error rate. A
  withdrawn detection whose orbit is perfectly Keplerian cannot be reached by
  any consistency check, however many are added; counting it as a false pass
  would report the boundary of the method as a defect in it, and dropping such
  claims from the set would hide the boundary. They are labelled
  `consistent_but_refuted`, expected to pass, and measured separately.

The point estimates are published with one-sided 95% upper bounds. Zero false
fails in 41 correct claims is a false-fail rate below about 7%, not a
false-fail rate of zero, and the table says so.

Tolerances are part of the specification and are frozen with the claim set,
not tuned afterwards. When a claim's label and the verifier's verdict
disagreed during construction, the resolution was to fix the check or to
document the limit -- never to move a tolerance until the label came out
right. One check changed as a result: the residual of a numerical relation is
now divided by the exponent of a lone quantity on either side, because
`P**2 = a**3/(G M)` and `P = sqrt(a**3/(G M))` are the same claim and were
being held to different tolerances.

A claim set is frozen once. Corrections ship as `claims_v2.jsonl`.

## The checks

Ordered by reach per unit of work. The first five are implemented.

1. **Dimensional consistency of a stated relation** — parse the asserted
   formula, verify both sides carry the same dimensions. Applies to every
   quantitative claim in any field, and needs no measurements at all: a law
   written with the wrong exponent is refutable from the law alone.
2. **Internal numerical consistency** — do the quoted numbers actually satisfy
   the quoted formula? Catches transcription and arithmetic errors, which are
   common and cheap to detect. Evaluated in the canonical unit set, so a claim
   in days and kilometres meets the same arithmetic as one in years and au.
3. **Sign and bound constraints** — a mass that came out negative, an
   eccentricity below zero, an albedo above one. Only bounds that follow from
   a quantity's definition are enforced; a bound that is a matter of
   convention would generate false fails.
4. **Limiting-case degeneration** — extend to more known limits.
5. **Cross-claim consistency** — do a system's own claims contradict each
   other across a submission? A system asserting two incompatible masses for
   one object has failed regardless of which is right. Compared over an
   allowlist of subject invariants rather than every shared quantity name:
   one claim's perihelion distance is not another's mean orbital radius, and
   for an eccentric orbit a name-matching check would reject a correct pair.
6. **Monotonicity constraints** — a cross-section that grows without bound, a
   fitted relation that reverses sign outside its data. Not yet implemented.

### How a relation is checked twice

A claim may state its relation literally (`period**2 = 4*pi**2 *
semi_major_axis**3 / (G * total_mass)`) or cite one the benchmark names
(`kepler3`, `vis_viva`, `specific_energy`, `escape_velocity`, …). The same
string drives both the dimensional and the numerical check, so a relation
cannot pass one by being written differently for the other. Library relations
carry G explicitly, which makes them dimensionally complete while still
reducing to the familiar form in canonical units where G = 4π².

Submitted relations are parsed over a whitelisted subset of the expression
grammar and evaluated by an interpreter over that AST. Nothing calls `eval` on
submitted text, and a relation outside the supported grammar is declined as
inapplicable rather than failed.

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
