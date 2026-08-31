"""Deterministic consistency checks for claimed physical relations.

Every check here returns a verdict computed from numbers, not judged by a
model. That is the point: the outcome labels in the question-discovery line
of work reach only kappa = 0.21 between two judges, which is too weak to rank
systems against. A check that either holds or does not hold has no rater.

A check returns a `Verdict`. `passed=None` means the check does not apply to
this claim (missing quantities, wrong claim type) and must not be scored as
either a pass or a failure -- conflating "inapplicable" with "failed" is the
easiest way to make a leaderboard lie.

Every check states its tolerance and its inapplicability condition in its
docstring. Where a check cannot tell a wrong claim from an unusual but legal
one, it declines: a false fail costs the benchmark more than a missed catch,
because one wrongly-rejected submission from a serious group ends it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields

from .relations import (
    RelationError,
    eval_dims,
    eval_value,
    fmt,
    free_symbols,
    linearising_exponent,
    parse_relation,
    resolve_relation,
)
from .units import (
    DIMENSIONS,
    LENGTH,
    MASS,
    OPAQUE,
    TIME,
    UNITLESS,
    normalise_unit,
    quantity_dims,
    quantity_factor,
)

__all__ = [
    "Claim", "Verdict", "CHECKS", "SUBMISSION_CHECKS", "DIMENSIONS", "UNITLESS",
    "check_units_declared", "check_kepler_third_law",
    "check_energy_angular_momentum", "check_limiting_case",
    "check_dimensional_consistency", "check_numerical_consistency",
    "check_physical_bounds", "check_cross_claim_consistency",
    "BOUNDS", "SUBJECT_INVARIANTS",
    "verify", "verify_submission",
]


@dataclass
class Verdict:
    check: str
    passed: bool | None
    detail: str
    residual: float | None = None
    tolerance: float | None = None
    claim_ids: tuple[str, ...] | None = None


@dataclass
class Claim:
    claim_id: str
    system: str
    claim_type: str
    statement: str
    quantities: dict[str, float] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    asserted_relation: str | None = None
    tolerance: float = 0.05
    subject: str | None = None

    @classmethod
    def from_dict(cls, record: dict) -> "Claim":
        """Build a claim, ignoring keys the verifier does not consume.

        Submissions carry provenance and ground-truth annotations the checks
        have no business reading. Dropping them here rather than rejecting the
        line keeps the format forgiving without letting anything extra reach
        the scoring path.
        """
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in record.items() if k in known})


def _canonical(claim: Claim, key: str, expected=None) -> float | None:
    """A quantity in the canonical set (au, Msun, yr, K), or None.

    None means unscoreable: the quantity is absent, its unit is unrecognised,
    or its unit has the wrong dimensions for what the check needs.
    """
    if key not in claim.quantities:
        return None
    value = claim.quantities[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    unit = claim.units.get(key)
    dims = quantity_dims(key, unit)
    if dims is None or (expected is not None and dims != expected):
        return None
    factor = quantity_factor(key, unit)
    return None if factor is None else float(value) * factor


def check_units_declared(claim: Claim) -> Verdict:
    """Every dimensional quantity carries a unit drawn from the known table.

    Inapplicable when the claim supplies no quantities. A claim whose units
    cannot be resolved is not wrong; it is unscoreable, and saying so is more
    useful than guessing at what was meant.
    """
    if not claim.quantities:
        return Verdict("units_declared", None, "no quantities supplied")
    missing = [
        k for k in claim.quantities
        if k not in UNITLESS and not claim.units.get(k)
    ]
    unknown = [
        k for k, u in claim.units.items() if u and normalise_unit(u) is None
    ]
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing units for {sorted(missing)}")
        if unknown:
            parts.append(f"unrecognised units for {sorted(unknown)}")
        return Verdict("units_declared", False, "; ".join(parts))
    return Verdict("units_declared", True, f"{len(claim.quantities)} quantities resolved")


def check_kepler_third_law(claim: Claim) -> Verdict:
    """P^2 = a^3 / M in (yr, au, Msun), within the claim's tolerance.

    Applies to any claim supplying a period, a semi-major axis, and a total
    mass in units of the right dimensions, whatever the claim says about them.
    Inapplicable when any of the three is absent or unconvertible.
    """
    p = _canonical(claim, "period", TIME)
    a = _canonical(claim, "semi_major_axis", LENGTH)
    m = _canonical(claim, "total_mass", MASS)
    if p is None or a is None or m is None:
        return Verdict(
            "kepler_third_law", None,
            "needs period, semi_major_axis and total_mass in known units",
        )
    if a <= 0 or m <= 0 or p <= 0:
        return Verdict("kepler_third_law", False, "non-positive quantity")

    expected_p = math.sqrt(a**3 / m)
    residual = abs(p - expected_p) / expected_p
    ok = residual <= claim.tolerance
    return Verdict(
        "kepler_third_law", ok,
        f"P={p:.6g} yr vs {expected_p:.6g} yr implied by a={a:.6g} au, M={m:.6g} Msun",
        residual=residual, tolerance=claim.tolerance,
    )


def check_energy_angular_momentum(claim: Claim) -> Verdict:
    """Specific orbital energy and angular momentum agree with (a, e, M).

    eps = -G M / 2a  and  h = sqrt(G M a (1 - e^2)), in units where G = 4 pi^2
    for (au, Msun, yr). Inapplicable without a semi-major axis, a total mass,
    and at least one of the two derived quantities.
    """
    a = _canonical(claim, "semi_major_axis", LENGTH)
    m = _canonical(claim, "total_mass", MASS)
    e = claim.quantities.get("eccentricity")
    eps = _canonical(claim, "specific_energy")
    h = _canonical(claim, "specific_angular_momentum")
    if a is None or m is None or (eps is None and h is None):
        return Verdict(
            "energy_angular_momentum", None,
            "needs semi_major_axis, total_mass and at least one of "
            "specific_energy / specific_angular_momentum",
        )
    if e is not None and not (0.0 <= e < 1.0):
        return Verdict(
            "energy_angular_momentum", False,
            f"eccentricity {e} outside [0, 1) for a bound orbit",
        )

    g = 4.0 * math.pi**2
    worst, notes = 0.0, []
    if eps is not None:
        expected = -g * m / (2.0 * a)
        r = abs(eps - expected) / abs(expected)
        worst = max(worst, r)
        notes.append(f"energy {eps:.6g} vs {expected:.6g}")
    if h is not None:
        ecc = 0.0 if e is None else e
        expected = math.sqrt(g * m * a * (1.0 - ecc**2))
        r = abs(h - expected) / abs(expected)
        worst = max(worst, r)
        notes.append(f"angular momentum {h:.6g} vs {expected:.6g}")

    return Verdict(
        "energy_angular_momentum", worst <= claim.tolerance, "; ".join(notes),
        residual=worst, tolerance=claim.tolerance,
    )


def check_limiting_case(claim: Claim) -> Verdict:
    """A claimed general relation must reduce to the known one in its limit.

    The claim supplies `limit_value` (what the relation gives at the limit)
    and `known_value` (what established theory gives there). A proposal that
    does not degenerate correctly is wrong regardless of how well it fits.
    Inapplicable when either value is absent.
    """
    lim = claim.quantities.get("limit_value")
    known = claim.quantities.get("known_value")
    if lim is None or known is None:
        return Verdict(
            "limiting_case", None,
            "needs limit_value and known_value to test degeneration",
        )
    if known == 0:
        residual = abs(lim)
    else:
        residual = abs(lim - known) / abs(known)
    return Verdict(
        "limiting_case", residual <= claim.tolerance,
        f"limit {lim:.6g} vs known {known:.6g}",
        residual=residual, tolerance=claim.tolerance,
    )


def check_dimensional_consistency(claim: Claim) -> Verdict:
    """Both sides of the asserted relation carry the same dimensions.

    The widest-reach check in the suite: it needs no measurements at all, only
    the stated law, and it applies to any quantitative claim in any field. A
    relation whose sides differ dimensionally is wrong before any data is
    consulted.

    Tolerance: none, the comparison is exact. Inapplicable when the claim
    asserts no relation, when the relation lies outside the supported grammar,
    or when any symbol's dimensions cannot be resolved -- declining is
    correct there, because guessing a dimension would manufacture false fails.
    """
    source = resolve_relation(claim.asserted_relation)
    if source is None:
        return Verdict(
            "dimensional_consistency", None,
            "no asserted_relation stating an equation or naming a known one",
        )
    try:
        lhs, rhs = parse_relation(source)
        symbols = free_symbols(source)
    except RelationError as exc:
        return Verdict("dimensional_consistency", None, f"relation not evaluable: {exc}")

    env, unresolved = {}, []
    for name in symbols:
        # Dimensions come from the unit label or the quantity name, never from
        # a value: a claim may state its law and its symbols' units without
        # quoting a single measurement, and this check still applies.
        dims = None if name in OPAQUE else quantity_dims(name, claim.units.get(name))
        if dims is None:
            unresolved.append(name)
        else:
            env[name] = dims
    if unresolved:
        return Verdict(
            "dimensional_consistency", None,
            f"cannot resolve dimensions of {sorted(unresolved)}",
        )

    try:
        left, right = eval_dims(lhs, env), eval_dims(rhs, env)
    except RelationError as exc:
        return Verdict(
            "dimensional_consistency", False,
            f"relation is dimensionally inconsistent: {exc}",
        )
    if left != right:
        return Verdict(
            "dimensional_consistency", False,
            f"left side is {fmt(left)}, right side is {fmt(right)}",
        )
    return Verdict("dimensional_consistency", True, f"both sides are {fmt(left)}")


def check_numerical_consistency(claim: Claim) -> Verdict:
    """The quoted numbers satisfy the relation the claim quotes them for.

    Catches transcription and arithmetic errors -- a digit dropped, a value
    carried over in the wrong unit -- which are common and cheap to detect.
    Evaluated in the canonical set (au, Msun, yr, K) where G = 4 pi^2, so a
    claim in days and kilometres is held to the same arithmetic as one in
    years and au.

    Tolerance: the claim's own, on the relative gap between the two sides,
    scaled by the larger side. Inapplicable when no relation is asserted, when
    it lies outside the supported grammar, or when any symbol it names is
    absent from the claim or carries an unusable unit.
    """
    source = resolve_relation(claim.asserted_relation)
    if source is None:
        return Verdict(
            "numerical_consistency", None,
            "no asserted_relation stating an equation or naming a known one",
        )
    try:
        lhs, rhs = parse_relation(source)
        symbols = free_symbols(source)
    except RelationError as exc:
        return Verdict("numerical_consistency", None, f"relation not evaluable: {exc}")

    env, unresolved = {}, []
    for name in symbols:
        value = _canonical(claim, name)
        if value is None:
            unresolved.append(name)
        else:
            env[name] = value
    if unresolved:
        return Verdict(
            "numerical_consistency", None,
            f"claim does not supply usable values for {sorted(unresolved)}",
        )

    try:
        left, right = eval_value(lhs, env), eval_value(rhs, env)
    except RelationError as exc:
        return Verdict("numerical_consistency", None, f"relation not evaluable: {exc}")

    scale = max(abs(left), abs(right))
    gap = 0.0 if scale == 0.0 else abs(left - right) / scale
    # Divided so that the tolerance means the same thing whether the submitter
    # wrote P**2 = a**3/(G M) or P = sqrt(a**3/(G M)).
    exponent = linearising_exponent(lhs, rhs)
    residual = gap / exponent
    note = "" if exponent == 1.0 else f", gap {gap:.4g} over exponent {exponent:g}"
    return Verdict(
        "numerical_consistency", residual <= claim.tolerance,
        f"{source}: left={left:.6g}, right={right:.6g}{note}",
        residual=residual, tolerance=claim.tolerance,
    )


# Domain constraints that hold for the quantity whatever the claim asserts
# about it, as (low, high, low_is_strict, high_is_strict). Only quantities
# whose bound is a matter of definition rather than of convention appear
# here: a negative mass or an eccentricity below zero is not an unusual
# result, it is an impossible one.
POSITIVE = (0.0, None, True, False)
NON_NEGATIVE = (0.0, None, False, False)
UNIT_INTERVAL = (0.0, 1.0, False, False)

BOUNDS: dict[str, tuple[float, float | None, bool, bool]] = {
    "period": POSITIVE,
    "semi_major_axis": POSITIVE,
    "orbital_radius": POSITIVE,
    "radius": POSITIVE,
    "distance": POSITIVE,
    "mass": POSITIVE,
    "total_mass": POSITIVE,
    "stellar_mass": POSITIVE,
    "planet_mass": POSITIVE,
    "temperature": POSITIVE,
    "luminosity": POSITIVE,
    "density": POSITIVE,
    "speed": NON_NEGATIVE,
    "escape_velocity": NON_NEGATIVE,
    "eccentricity": NON_NEGATIVE,
    "albedo": UNIT_INTERVAL,
    "probability": UNIT_INTERVAL,
}


def check_physical_bounds(claim: Claim) -> Verdict:
    """Quantities stay inside the range their definition permits.

    A negative mass, an eccentricity below zero, an albedo above one: errors
    that survive every relation check because they never enter one. Bounds are
    tested on the canonical value where the unit resolves and on the quoted
    value otherwise; every unit in the table has a positive scale, so the
    comparison is the same either way.

    Tolerance: none, the bounds are exact. Inapplicable when the claim
    supplies no quantity this table constrains.
    """
    constrained = [k for k in claim.quantities if k in BOUNDS]
    if not constrained:
        return Verdict(
            "physical_bounds", None,
            "no quantity with a definitional bound was supplied",
        )
    violations = []
    for key in sorted(constrained):
        value = _canonical(claim, key)
        if value is None:
            raw = claim.quantities[key]
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                continue
            value = float(raw)
        low, high, low_strict, high_strict = BOUNDS[key]
        if value < low or (low_strict and value == low):
            violations.append(f"{key}={value:.6g} must be {'>' if low_strict else '>='} {low:g}")
        elif high is not None and (value > high or (high_strict and value == high)):
            violations.append(f"{key}={value:.6g} must be {'<' if high_strict else '<='} {high:g}")
    if violations:
        return Verdict("physical_bounds", False, "; ".join(violations))
    return Verdict(
        "physical_bounds", True,
        f"{len(constrained)} bounded quantities within range",
    )


# Quantities that are properties of the subject itself, so two claims naming
# the same subject are asserting the same thing about it and must agree. The
# comparison is an allowlist rather than a denylist because the failure mode
# here is a false fail: `radius` and `speed` are configuration-dependent --
# one claim's perihelion distance is not another's mean orbital radius, and
# for an eccentric orbit the two differ by far more than any tolerance --
# so a check that compared everything named alike would reject correct pairs.
SUBJECT_INVARIANTS = frozenset({
    "period",
    "semi_major_axis",
    "eccentricity",
    "total_mass",
    "stellar_mass",
    "planet_mass",
    "mass",
    "distance",
    "luminosity",
    "specific_energy",
    "specific_angular_momentum",
})


def check_cross_claim_consistency(claims: list[Claim]) -> list[Verdict]:
    """A system's own claims must not contradict each other.

    Two claims naming the same `subject` and quoting the same quantity must
    agree, in canonical units, within the tighter of their tolerances. A
    system asserting two incompatible masses for one object has failed
    regardless of which value is right, and no single-claim check can see it.

    One verdict per (subject, quantity) group with at least two claims;
    inapplicable -- an empty list -- when no such group exists. Only
    quantities in `SUBJECT_INVARIANTS` are compared, so a claim-local value
    is never read as an assertion about the subject.
    """
    groups: dict[tuple[str, str], list[tuple[str, float, float]]] = {}
    for claim in claims:
        if not claim.subject:
            continue
        subject = claim.subject.strip().lower()
        for key in claim.quantities:
            if key not in SUBJECT_INVARIANTS:
                continue
            value = _canonical(claim, key)
            if value is None:
                continue
            groups.setdefault((subject, key), []).append(
                (claim.claim_id, value, claim.tolerance)
            )

    verdicts = []
    for (subject, key), entries in sorted(groups.items()):
        if len(entries) < 2:
            continue
        values = [v for _, v, _ in entries]
        ids = tuple(cid for cid, _, _ in entries)
        tolerance = min(t for _, _, t in entries)
        spread = max(values) - min(values)
        scale = max(abs(v) for v in values)
        residual = spread / scale if scale else 0.0
        verdicts.append(Verdict(
            "cross_claim_consistency", residual <= tolerance,
            f"{subject}: {key} quoted as {[round(v, 6) for v in values]} "
            f"(canonical units) across {list(ids)}",
            residual=residual, tolerance=tolerance, claim_ids=ids,
        ))
    return verdicts


CHECKS = (
    check_units_declared,
    check_physical_bounds,
    check_dimensional_consistency,
    check_numerical_consistency,
    check_kepler_third_law,
    check_energy_angular_momentum,
    check_limiting_case,
)

SUBMISSION_CHECKS = (check_cross_claim_consistency,)


def verify(claim: Claim) -> list[Verdict]:
    return [check(claim) for check in CHECKS]


def verify_submission(claims: list[Claim]) -> list[Verdict]:
    """Checks that read a whole submission rather than one claim at a time."""
    return [v for check in SUBMISSION_CHECKS for v in check(claims)]
