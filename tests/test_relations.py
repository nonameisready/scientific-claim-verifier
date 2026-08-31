"""Offline tests for the relation-driven checks: no network, no API key, no model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.checks import (  # noqa: E402
    Claim,
    check_cross_claim_consistency,
    check_dimensional_consistency,
    check_numerical_consistency,
    check_physical_bounds,
    check_units_declared,
)


def relation_claim(rel, quantities=None, units=None, tolerance=0.05):
    return Claim(
        claim_id="t", system="s", claim_type="general_relation", statement="",
        quantities=quantities or {}, units=units or {},
        asserted_relation=rel, tolerance=tolerance,
    )


KEPLER_UNITS = {"period": "day", "semi_major_axis": "au", "total_mass": "msun"}


def test_named_relation_is_dimensionally_consistent():
    v = check_dimensional_consistency(relation_claim("kepler3", units=KEPLER_UNITS))
    assert v.passed is True


def test_wrong_exponent_is_caught_with_no_measurements_at_all():
    # The reach of dimensional analysis: the claim supplies no numbers.
    c = relation_claim(
        "period**2 = 4*pi**2 * semi_major_axis**2 / (G * total_mass)",
        units=KEPLER_UNITS,
    )
    assert check_dimensional_consistency(c).passed is False


def test_dimensional_check_declines_when_a_symbol_has_no_resolvable_dimension():
    c = relation_claim("limit_value = 2 * known_value", quantities={"limit_value": 1.0})
    assert check_dimensional_consistency(c).passed is None


def test_numerical_check_catches_an_error_no_orbital_check_can_see():
    # Escape velocity at the solar surface is 617.7 km/s, not 430.
    c = relation_claim(
        "escape_velocity",
        {"escape_velocity": 430.0, "radius": 1.0, "total_mass": 1.0},
        {"escape_velocity": "km/s", "radius": "rsun", "total_mass": "msun"},
    )
    v = check_numerical_consistency(c)
    assert v.passed is False
    assert check_dimensional_consistency(c).passed is True


def test_residual_does_not_depend_on_how_the_relation_was_rearranged():
    # A submitter must not be penalised for algebra: squaring a relation
    # doubles the raw gap between its sides, and the tolerance has to mean
    # the same thing either way.
    quantities = {"period": 19.7, "semi_major_axis": 0.14, "total_mass": 1.0}
    squared = check_numerical_consistency(
        relation_claim("period**2 = 4*pi**2 * semi_major_axis**3 / (G * total_mass)",
                       quantities, KEPLER_UNITS))
    rooted = check_numerical_consistency(
        relation_claim("period = sqrt(4*pi**2 * semi_major_axis**3 / (G * total_mass))",
                       quantities, KEPLER_UNITS))
    assert abs(squared.residual - rooted.residual) < 0.005
    assert squared.passed == rooted.passed


def test_the_same_orbit_in_different_units_gets_the_same_verdict():
    au_yr = check_numerical_consistency(relation_claim(
        "kepler3", {"period": 1.0, "semi_major_axis": 1.0, "total_mass": 1.0},
        {"period": "yr", "semi_major_axis": "au", "total_mass": "msun"}))
    km_day = check_numerical_consistency(relation_claim(
        "kepler3",
        {"period": 365.25, "semi_major_axis": 149597870.7, "total_mass": 1.98892e30},
        {"period": "day", "semi_major_axis": "km", "total_mass": "kg"}))
    assert au_yr.passed is True and km_day.passed is True
    assert abs(au_yr.residual - km_day.residual) < 0.01


def test_a_unit_alias_is_not_a_false_fail():
    c = Claim("t", "s", "orbital_relation", "",
              {"period": 3.5247, "semi_major_axis": 0.04747, "total_mass": 1.15},
              {"period": "days", "semi_major_axis": "AU", "total_mass": "Msol"})
    assert check_units_declared(c).passed is True


def test_submitted_text_is_parsed_not_executed():
    marker = Path("/tmp/scientific-claim-verifier-should-not-exist")
    c = relation_claim(f"x = __import__('os').system('touch {marker}')")
    assert check_numerical_consistency(c).passed is None
    assert check_dimensional_consistency(c).passed is None
    assert not marker.exists()


def test_bounds_catch_what_no_relation_check_touches():
    assert check_physical_bounds(Claim(
        "t", "s", "planetary_property", "", {"albedo": 1.35})).passed is False
    assert check_physical_bounds(Claim(
        "t", "s", "orbital_relation", "", {"total_mass": -1.1},
        {"total_mass": "msun"})).passed is False
    assert check_physical_bounds(Claim(
        "t", "s", "orbital_relation", "", {"eccentricity": -0.3})).passed is False


def test_bounds_are_inapplicable_when_nothing_is_bounded():
    c = Claim("t", "s", "general_relation", "", {"limit_value": -4.0, "known_value": -4.0})
    assert check_physical_bounds(c).passed is None


def test_a_system_contradicting_itself_is_caught_across_claims():
    claims = [
        Claim("x", "s", "stellar_property", "", {"total_mass": 0.89},
              {"total_mass": "msun"}, subject="Kepler-16"),
        Claim("y", "s", "stellar_property", "", {"total_mass": 1.35},
              {"total_mass": "msun"}, subject="Kepler-16"),
    ]
    verdicts = check_cross_claim_consistency(claims)
    assert len(verdicts) == 1
    assert verdicts[0].passed is False
    assert set(verdicts[0].claim_ids) == {"x", "y"}


def test_cross_claim_agreement_across_units_is_not_a_contradiction():
    claims = [
        Claim("x", "s", "stellar_property", "", {"total_mass": 1.0},
              {"total_mass": "msun"}, subject="Sun"),
        Claim("y", "s", "stellar_property", "", {"total_mass": 1.98892e30},
              {"total_mass": "kg"}, subject="Sun"),
    ]
    assert check_cross_claim_consistency(claims)[0].passed is True


def test_cross_claim_is_inapplicable_without_a_named_subject():
    claims = [
        Claim("x", "s", "stellar_property", "", {"total_mass": 0.89}, {"total_mass": "msun"}),
        Claim("y", "s", "stellar_property", "", {"total_mass": 1.35}, {"total_mass": "msun"}),
    ]
    assert check_cross_claim_consistency(claims) == []


def test_a_claim_local_quantity_is_not_read_as_a_subject_property():
    # Mercury's perihelion speed and its mean orbital speed differ by 22%.
    # Both are correct; a cross-claim check that compared them by name would
    # manufacture a contradiction out of an eccentric orbit.
    claims = [
        Claim("x", "s", "general_relation", "", {"speed": 58.98, "radius": 0.30750},
              {"speed": "km/s", "radius": "au"}, subject="Mercury"),
        Claim("y", "s", "general_relation", "", {"speed": 47.36, "radius": 0.387098},
              {"speed": "km/s", "radius": "au"}, subject="Mercury"),
    ]
    assert check_cross_claim_consistency(claims) == []
