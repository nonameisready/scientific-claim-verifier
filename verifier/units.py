"""Units, dimensions, and conversion into the benchmark's canonical set.

Dimensions are exponent vectors over (length, mass, time, temperature). The
canonical set is (au, Msun, yr, K): every dimensional quantity is converted
into it before any check evaluates a relation, so a claim quoted in days and
kilometres is checked against the same arithmetic as one quoted in years and
astronomical units.

Units live here rather than in `checks` because the check skeleton is meant to
carry over to materials and climate unchanged. A new field arrives as new
rows in these tables plus a new check module, not as a rewrite.

Alias coverage is deliberately generous. A submission rejected because it
wrote `days` instead of `day` is a false fail, and false fails are the failure
mode that ends a benchmark's credibility.
"""

from __future__ import annotations

Dims = tuple[int, int, int, int]

NONE: Dims = (0, 0, 0, 0)
LENGTH: Dims = (1, 0, 0, 0)
MASS: Dims = (0, 1, 0, 0)
TIME: Dims = (0, 0, 1, 0)
TEMPERATURE: Dims = (0, 0, 0, 1)
SPEED: Dims = (1, 0, -1, 0)

# unit -> (dimensions, multiplier into the canonical set)
UNITS: dict[str, tuple[Dims, float]] = {
    # length -> au
    "au": (LENGTH, 1.0),
    "km": (LENGTH, 6.684587e-9),
    "m": (LENGTH, 6.684587e-12),
    "rsun": (LENGTH, 4.650468e-3),
    "rjup": (LENGTH, 4.778945e-4),
    "rearth": (LENGTH, 4.258750e-5),
    "pc": (LENGTH, 206264.806),
    "ly": (LENGTH, 63241.077),
    # mass -> Msun
    "msun": (MASS, 1.0),
    "mjup": (MASS, 9.543900e-4),
    "mearth": (MASS, 3.002700e-6),
    "kg": (MASS, 5.02785e-31),
    # time -> yr
    "yr": (TIME, 1.0),
    "day": (TIME, 1.0 / 365.25),
    "hr": (TIME, 1.0 / (365.25 * 24.0)),
    "min": (TIME, 1.0 / (365.25 * 1440.0)),
    "s": (TIME, 1.0 / 3.15576e7),
    "myr": (TIME, 1.0e6),
    "gyr": (TIME, 1.0e9),
    # temperature -> K
    "k": (TEMPERATURE, 1.0),
    # speed -> au/yr
    "au/yr": (SPEED, 1.0),
    "km/s": (SPEED, 0.2109495),
    "m/s": (SPEED, 2.109495e-4),
    # angles and pure numbers
    "rad": (NONE, 1.0),
    "dimensionless": (NONE, 1.0),
}

ALIASES: dict[str, str] = {
    "a.u.": "au", "astronomical_unit": "au", "astronomical units": "au",
    "kilometre": "km", "kilometer": "km", "kilometres": "km", "kilometers": "km",
    "metre": "m", "meter": "m", "metres": "m", "meters": "m",
    "r_sun": "rsun", "rsol": "rsun", "solar_radius": "rsun", "r_jup": "rjup",
    "r_earth": "rearth", "parsec": "pc", "parsecs": "pc", "lightyear": "ly",
    "m_sun": "msun", "msol": "msun", "solar_mass": "msun", "solar masses": "msun",
    "m_jup": "mjup", "mjupiter": "mjup", "m_earth": "mearth", "mearths": "mearth",
    "kilogram": "kg", "kilograms": "kg",
    "year": "yr", "years": "yr", "julian_year": "yr", "a": "yr",
    "d": "day", "days": "day", "hour": "hr", "hours": "hr", "h": "hr",
    "minute": "min", "minutes": "min",
    "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "kelvin": "k", "kelvins": "k",
    "kms": "km/s", "km s^-1": "km/s", "km/sec": "km/s", "ms": "m/s",
    "radian": "rad", "radians": "rad", "none": "dimensionless", "1": "dimensionless",
}

# Quantities whose dimensions are fixed by the quantity name rather than by a
# unit label: dimensionless by definition, or derived quantities the benchmark
# states in the canonical set. Requiring a unit label for these would fail
# claims that are in fact fully specified.
DERIVED_DIMENSIONS: dict[str, Dims] = {
    "eccentricity": NONE,
    "albedo": NONE,
    "probability": NONE,
    "mass_ratio": NONE,
    "specific_energy": (2, 0, -2, 0),
    "specific_angular_momentum": (2, 0, -1, 0),
}

# Quantities the benchmark accepts without a unit label but whose dimensions
# it cannot know, so dimensional checks decline rather than guess.
OPAQUE = frozenset({"limit_value", "known_value"})

UNITLESS = frozenset(DERIVED_DIMENSIONS) | OPAQUE

# Retained for callers that only need the set of recognised unit tokens.
DIMENSIONS: dict[str, Dims] = {name: dims for name, (dims, _) in UNITS.items()}


def normalise_unit(unit: str | None) -> str | None:
    """Canonical spelling of a unit token, or None if unrecognised."""
    if unit is None:
        return None
    token = str(unit).strip().lower()
    token = ALIASES.get(token, token)
    return token if token in UNITS else None


def unit_info(unit: str | None) -> tuple[Dims, float] | None:
    token = normalise_unit(unit)
    return UNITS[token] if token else None


def to_canonical(value: float, unit: str | None, expected: Dims | None = None) -> float | None:
    """Value in canonical units, or None if the unit is unusable here.

    `expected` guards against a quantity supplied with a unit of the wrong
    dimension -- a semi-major axis in days is not a short orbit, it is an
    unscoreable claim.
    """
    info = unit_info(unit)
    if info is None:
        return None
    dims, factor = info
    if expected is not None and dims != expected:
        return None
    return float(value) * factor


def quantity_dims(name: str, unit: str | None) -> Dims | None:
    """Dimensions of a named quantity, from its unit or from its name."""
    info = unit_info(unit)
    if info is not None:
        return info[0]
    if name in DERIVED_DIMENSIONS:
        return DERIVED_DIMENSIONS[name]
    return None


def quantity_factor(name: str, unit: str | None) -> float | None:
    """Multiplier taking a named quantity into the canonical set."""
    info = unit_info(unit)
    if info is not None:
        return info[1]
    if name in DERIVED_DIMENSIONS:
        return 1.0
    return None
