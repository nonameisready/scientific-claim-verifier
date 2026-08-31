"""Deterministic consistency checks for claimed physical relations.

Every check here returns a verdict computed from numbers, not judged by a
model. That is the point: the outcome labels in the question-discovery line
of work reach only kappa = 0.21 between two judges, which is too weak to rank
systems against. A check that either holds or does not hold has no rater.

A check returns a `Verdict`. `passed=None` means the check does not apply to
this claim (missing quantities, wrong claim type) and must not be scored as
either a pass or a failure -- conflating "inapplicable" with "failed" is the
easiest way to make a leaderboard lie.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Dimensions are exponent vectors over (length, mass, time).
DIMENSIONS: dict[str, tuple[int, int, int]] = {
    "au": (1, 0, 0),
    "m": (1, 0, 0),
    "km": (1, 0, 0),
    "msun": (0, 1, 0),
    "kg": (0, 1, 0),
    "day": (0, 0, 1),
    "yr": (0, 0, 1),
    "s": (0, 0, 1),
}

# Conversions into the solar system unit set (au, msun, yr) that Kepler's
# third law is cleanest in.
TO_AU = {"au": 1.0, "km": 6.684587e-9, "m": 6.684587e-12}
TO_MSUN = {"msun": 1.0, "kg": 5.02785e-31}
TO_YR = {"yr": 1.0, "day": 1.0 / 365.25, "s": 1.0 / 3.15576e7}


@dataclass
class Verdict:
    check: str
    passed: bool | None
    detail: str
    residual: float | None = None
    tolerance: float | None = None


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


def _convert(claim: Claim, key: str, table: dict[str, float]) -> float | None:
    if key not in claim.quantities:
        return None
    unit = (claim.units.get(key) or "").lower()
    factor = table.get(unit)
    if factor is None:
        return None
    return float(claim.quantities[key]) * factor


# Quantities that carry no unit label: either dimensionless by definition, or
# derived quantities whose units are fixed by the unit set the check works in
# (au, msun, yr). Flagging these as "missing units" would fail claims that are
# in fact fully specified.
UNITLESS = frozenset({
    "eccentricity",
    "specific_energy",
    "specific_angular_momentum",
    "limit_value",
    "known_value",
})


def check_units_declared(claim: Claim) -> Verdict:
    """Every dimensional quantity carries a unit drawn from the known table.

    A claim whose units cannot be resolved is not wrong; it is unscoreable,
    and saying so is more useful than guessing at what was meant.
    """
    if not claim.quantities:
        return Verdict("units_declared", None, "no quantities supplied")
    missing = [
        k for k in claim.quantities
        if k not in UNITLESS and not claim.units.get(k)
    ]
    unknown = [
        k for k, u in claim.units.items() if u and u.lower() not in DIMENSIONS
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
    """P^2 = a^3 / M in (yr, au, msun), within the claim's tolerance.

    Applies to any claim supplying a period, a semi-major axis, and a total
    mass, whatever the claim says about them.
    """
    p = _convert(claim, "period", TO_YR)
    a = _convert(claim, "semi_major_axis", TO_AU)
    m = _convert(claim, "total_mass", TO_MSUN)
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
    for (au, msun, yr).
    """
    a = _convert(claim, "semi_major_axis", TO_AU)
    m = _convert(claim, "total_mass", TO_MSUN)
    e = claim.quantities.get("eccentricity")
    eps = claim.quantities.get("specific_energy")
    h = claim.quantities.get("specific_angular_momentum")
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


CHECKS = (
    check_units_declared,
    check_kepler_third_law,
    check_energy_angular_momentum,
    check_limiting_case,
)


def verify(claim: Claim) -> list[Verdict]:
    return [check(claim) for check in CHECKS]
