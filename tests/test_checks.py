"""Offline tests: no network, no API key, no model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.checks import (  # noqa: E402
    Claim,
    check_energy_angular_momentum,
    check_kepler_third_law,
    check_limiting_case,
    check_units_declared,
)
from verifier.score import leaderboard, score_system  # noqa: E402


def orbital(**q):
    units = {"period": "day", "semi_major_axis": "au", "total_mass": "msun"}
    return Claim(
        claim_id="t", system="s", claim_type="orbital_relation",
        statement="", quantities=q,
        units={k: v for k, v in units.items() if k in q},
    )


def test_kepler_passes_on_a_real_system():
    # HD 209458 b: 3.5247 d, 0.04747 au, 1.15 Msun total.
    v = check_kepler_third_law(orbital(period=3.5247, semi_major_axis=0.04747, total_mass=1.15))
    assert v.passed is True
    assert v.residual < 0.05


def test_kepler_catches_an_impossible_orbit():
    # 40 days at 0.05 au around 1 Msun is off by an order of magnitude.
    v = check_kepler_third_law(orbital(period=40.0, semi_major_axis=0.05, total_mass=1.0))
    assert v.passed is False
    assert v.residual > 1.0


def test_kepler_is_inapplicable_without_all_three_quantities():
    v = check_kepler_third_law(orbital(period=3.5, semi_major_axis=0.047))
    assert v.passed is None


def test_unbound_eccentricity_fails():
    c = orbital(semi_major_axis=1.0, total_mass=1.0)
    c.quantities.update({"eccentricity": 1.4, "specific_energy": -19.7})
    assert check_energy_angular_momentum(c).passed is False


def test_energy_matches_a_circular_orbit():
    c = orbital(semi_major_axis=1.0, total_mass=1.0)
    c.quantities.update({"eccentricity": 0.0, "specific_energy": -4 * 3.141592653589793**2 / 2})
    assert check_energy_angular_momentum(c).passed is True


def test_dimensionless_quantities_do_not_count_as_missing_units():
    c = orbital(semi_major_axis=1.0, total_mass=1.0)
    c.quantities["eccentricity"] = 0.1
    assert check_units_declared(c).passed is True


def test_unknown_unit_is_flagged():
    c = orbital(period=3.5, semi_major_axis=0.047, total_mass=1.0)
    c.units["period"] = "fortnight"
    assert check_units_declared(c).passed is False


def test_limiting_case_requires_degeneration():
    c = Claim("t", "s", "general_relation", "", {"limit_value": 20.0, "known_value": 9.8})
    assert check_limiting_case(c).passed is False


def test_vague_claim_is_uncheckable_not_passing():
    r = score_system([Claim("t", "s", "orbital_relation", "orbit looks fine")])
    assert r["checkable_rate"] == 0.0
    assert r["below_checkable_floor"] is True
    assert r["consistency_pass_rate"] is None


def test_vague_system_sorts_below_a_checkable_one():
    good = [orbital(period=3.5247, semi_major_axis=0.04747, total_mass=1.15)]
    vague = [Claim("v", "vague", "orbital_relation", "consistent with expectations")]
    rows = leaderboard({"vague": vague, "grounded": good})
    assert rows[0]["system"] == "grounded"
