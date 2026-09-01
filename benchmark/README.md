# Claim set v1

The frozen set the verifier is calibrated against. **62 claims, each carrying a
ground-truth label.** Frozen means frozen: values, tolerances and labels do
not change once published. A correction ships as `claims_v2.jsonl`, never as
an edit to this file, because a benchmark whose answer key moves is not a
benchmark.

Regenerate the measurement with:

```bash
python scripts/measure_sensitivity.py     # writes benchmark/sensitivity_v1.json
```

## Why this file exists

A verifier whose own error rate is unmeasured has no standing to rank anyone.
Before this set there was no way to say how often the checks reject a correct
claim or clear a wrong one -- only that they worked on the examples they were
written against, which is not evidence.

## The three classes

| label | n | meaning | expected verdict |
| --- | --- | --- | --- |
| `consistent` | 41 | published values, internally consistent | pass |
| `inconsistent` | 16 | violates an invariant the verifier can test | fail |
| `consistent_but_refuted` | 5 | self-consistent arithmetic, wrong about the world | pass |

The third class is the one that makes the measurement honest. Withdrawn
detections -- PSR B1829-10's planet, Alpha Centauri B b, Gliese 581 g,
Le Verrier's Vulcan, van de Kamp's companion to Barnard's Star -- are all
perfectly Keplerian. Nothing arithmetic can reach them. Counting them as
false passes would report a boundary of the method as a defect in it;
leaving them out would hide the boundary. They are in the set, labelled, and
measured separately.

## Measured on 62 claims

| class | n | passed | failed | no check applied |
| --- | --- | --- | --- | --- |
| `consistent` | 41 | 41 | 0 | 0 |
| `inconsistent` | 16 | 0 | 16 | 0 |
| `consistent_but_refuted` | 5 | 5 | 0 | 0 |

| rate | value | 95% upper bound | reading |
| --- | --- | --- | --- |
| false fail | 0.0 | 0.0705 | correct claims rejected |
| false pass | 0.0 | 0.1707 | inconsistent claims cleared |
| detection | 1.0 | -- | inconsistent claims caught |
| attribution | 1.0 | -- | caught by the check named for them |
| blind spot | 1.0 | -- | refuted-but-consistent claims passed, as expected |

**Read the upper bounds, not the point estimates.** Zero false fails in
41 correct claims is not a false-fail rate of zero; it is a false-fail
rate below about 7%. The set is small, and saying so in the same table as the
result is the difference between a calibration and an advertisement.

## What these numbers do not establish

Three limits, stated here rather than discovered later by someone ranked
badly:

1. **The seeded errors and the checks share an author.** A false-pass rate of
   0.0 measures whether the checks catch the errors they were built to
   catch. It does not measure coverage of errors in the wild. The number that
   will matter is the one measured against errors chosen by someone else --
   real submissions, or a third-party adversarial set. Until then this is a
   floor on performance, not an estimate of it.

2. **The correct claims come from standard tabulations.** A systematic error
   shared by those tabulations is invisible to this measurement, because the
   verifier and the answer key would be wrong together.

3. **Astronomy only, and mostly two-body orbits.** 4 of the seeded errors
   are caught by the Kepler check. The materials and climate checks the design
   anticipates have no calibration at all yet, and no rate here transfers to
   them.

## Which check caught what

| check | seeded errors caught |
| --- | --- |
| `cross_claim_consistency` | 2 |
| `dimensional_consistency` | 2 |
| `energy_angular_momentum` | 3 |
| `kepler_third_law` | 4 |
| `numerical_consistency` | 4 |
| `physical_bounds` | 3 |
| `units_declared` | 2 |

Attribution is tracked because a detection for the wrong reason is not a
detection. Every seeded error names the check that should catch it, and the
artifact records whether that check is the one that fired.

## Record format

Each line is a normal submission record plus a `ground_truth` object. The
verifier never reads that object: `Claim.from_dict` drops every key it does
not consume, so the answer key cannot reach the scoring path.

```json
{
  "claim_id": "b011",
  "system": "frozen-v1",
  "claim_type": "general_relation",
  "statement": "Escape velocity at the solar surface reported as 430 km/s.",
  "quantities": {"escape_velocity": 430.0, "radius": 1.0, "total_mass": 1.0},
  "units": {"escape_velocity": "km/s", "radius": "rsun", "total_mass": "msun"},
  "tolerance": 0.05,
  "asserted_relation": "escape_velocity",
  "ground_truth": {
    "label": "inconsistent",
    "error_type": "arithmetic_error",
    "expected_check": "numerical_consistency",
    "source": "a037 with a wrong value",
    "note": "dimensionally fine and untouched by every orbital check"
  }
}
```

## Provenance

Class `consistent` values are standard tabulated parameters -- solar system
ephemeris elements, commonly quoted visual-binary orbit solutions, and
discovery or characterisation parameters for the exoplanets -- rounded to the
digits shown. They are here to calibrate a consistency checker, not as a data
release; any of them can be re-derived from public catalogues.

Class `inconsistent` claims are constructed, each by one named perturbation of
a stated source claim, so that what is wrong with each is unambiguous.

Class `consistent_but_refuted` claims restate historical detections that were
later withdrawn, refuted, or attributed to instrumental artifacts. The
`source` field names the claim and its refutation.
