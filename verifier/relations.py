"""Parse an asserted relation and evaluate it twice: in dimensions, in numbers.

A system that states a relation has stated something checkable twice over.
Both sides of `P^2 = 4 pi^2 a^3 / (G M)` must carry the same dimensions --
a test that needs no data at all -- and the numbers quoted alongside it must
actually satisfy it. The first catches a malformed law, the second catches
the transcription and arithmetic errors that are the commonest way for an
otherwise correct claim to be wrong.

The same source string drives both, so a relation cannot pass one check by
being written differently for the other.

Evaluation is over a whitelisted subset of Python's expression grammar via
`ast`; nothing here calls `eval` on submitted text. Relations are evaluated in
the canonical unit set (au, Msun, yr, K), where G = 4 pi^2.
"""

from __future__ import annotations

import ast
import math
from fractions import Fraction

from .units import NONE, Dims

DimsF = tuple[Fraction, Fraction, Fraction, Fraction]


class RelationError(Exception):
    """The relation cannot be evaluated as written."""


class DimensionMismatch(RelationError):
    """Two operands were combined that do not carry the same dimensions."""


class UnknownSymbol(RelationError):
    """The relation names something the claim does not supply."""


# Values are in the canonical set: au, Msun, yr.
CONSTANT_VALUES: dict[str, float] = {
    "pi": math.pi,
    "G": 4.0 * math.pi**2,
    "c": 63241.077,
}
CONSTANT_DIMS: dict[str, Dims] = {
    "pi": NONE,
    "G": (3, -1, -2, 0),
    "c": (1, 0, -1, 0),
}

_NUMERIC_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "log": math.log, "log10": math.log10,
    "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
}
# Functions whose argument and result must both be dimensionless.
_DIMLESS_FUNCS = frozenset({"log", "log10", "exp", "sin", "cos", "tan"})

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call,
    ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
)

# Relations the benchmark names, so a claim may cite one instead of spelling
# it out. Each is written dimensionally complete -- G carried explicitly --
# so that the same string passes the dimensional check and, in canonical
# units where G = 4 pi^2, reproduces the familiar form.
RELATION_LIBRARY: dict[str, str] = {
    "kepler3": "period**2 = 4*pi**2 * semi_major_axis**3 / (G * total_mass)",
    "vis_viva": "speed**2 = G * total_mass * (2/radius - 1/semi_major_axis)",
    "specific_energy": "specific_energy = -G * total_mass / (2 * semi_major_axis)",
    "specific_angular_momentum":
        "specific_angular_momentum = "
        "sqrt(G * total_mass * semi_major_axis * (1 - eccentricity**2))",
    "escape_velocity": "escape_velocity**2 = 2 * G * total_mass / radius",
    "circular_speed": "speed**2 = G * total_mass / radius",
}


def resolve_relation(text: str | None) -> str | None:
    """The relation source: a library name, a literal equation, or None."""
    if not text:
        return None
    key = text.strip()
    if key in RELATION_LIBRARY:
        return RELATION_LIBRARY[key]
    return key if "=" in key else None


def _validate(node: ast.AST) -> None:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if not isinstance(sub.func, ast.Name) or sub.func.id not in _NUMERIC_FUNCS:
                raise RelationError("only sqrt/abs/log/log10/exp/sin/cos/tan may be called")
            if len(sub.args) != 1 or sub.keywords:
                raise RelationError(f"{ast.unparse(sub.func)} takes exactly one argument")
            continue
        if isinstance(sub, ast.Constant):
            if not isinstance(sub.value, (int, float)) or isinstance(sub.value, bool):
                raise RelationError("only numeric literals are allowed")
            continue
        if not isinstance(sub, _ALLOWED_NODES):
            raise RelationError(f"unsupported syntax: {type(sub).__name__}")


def parse_relation(text: str) -> tuple[ast.expr, ast.expr]:
    """Split `lhs = rhs` and parse both sides into validated expressions."""
    normalised = text.replace("==", "=").replace("^", "**")
    parts = normalised.split("=")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise RelationError("a relation must have exactly one '=' with both sides present")
    sides = []
    for part in parts:
        try:
            tree = ast.parse(part.strip(), mode="eval")
        except SyntaxError as exc:
            raise RelationError(f"cannot parse '{part.strip()}': {exc.msg}") from exc
        _validate(tree)
        sides.append(tree.body)
    return sides[0], sides[1]


def _collect(node: ast.expr, names: set[str]) -> None:
    """Names read as quantities, not descending into a call's function name."""
    if isinstance(node, ast.Name):
        if node.id not in CONSTANT_VALUES:
            names.add(node.id)
        return
    if isinstance(node, ast.Call):
        for arg in node.args:
            _collect(arg, names)
        return
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            _collect(child, names)


def free_symbols(text: str) -> set[str]:
    """Names the relation reads from the claim; constants and functions excluded."""
    lhs, rhs = parse_relation(text)
    names: set[str] = set()
    _collect(lhs, names)
    _collect(rhs, names)
    return names


def _as_exponent(node: ast.expr) -> Fraction:
    """A power's exponent must be a pure number for dimensions to be defined."""
    try:
        value = eval_value(node, {})
    except UnknownSymbol as exc:
        raise RelationError("exponent must be a constant, not a quantity") from exc
    return Fraction(value).limit_denominator(64)


def eval_dims(node: ast.expr, env: dict[str, Dims]) -> DimsF:
    """Dimensions of an expression, raising on any inconsistent combination."""
    if isinstance(node, ast.Constant):
        return _f(NONE)
    if isinstance(node, ast.Name):
        if node.id in CONSTANT_DIMS:
            return _f(CONSTANT_DIMS[node.id])
        if node.id not in env:
            raise UnknownSymbol(node.id)
        return _f(env[node.id])
    if isinstance(node, ast.UnaryOp):
        return eval_dims(node.operand, env)
    if isinstance(node, ast.Call):
        name = node.func.id  # type: ignore[union-attr]
        inner = eval_dims(node.args[0], env)
        if name == "sqrt":
            return tuple(d / 2 for d in inner)  # type: ignore[return-value]
        if name == "abs":
            return inner
        if inner != _f(NONE):
            raise DimensionMismatch(f"{name}() needs a dimensionless argument, got {fmt(inner)}")
        return _f(NONE)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, (ast.Add, ast.Sub)):
            left, right = eval_dims(node.left, env), eval_dims(node.right, env)
            if left != right:
                raise DimensionMismatch(f"cannot add {fmt(left)} to {fmt(right)}")
            return left
        if isinstance(node.op, ast.Mult):
            left, right = eval_dims(node.left, env), eval_dims(node.right, env)
            return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]
        if isinstance(node.op, ast.Div):
            left, right = eval_dims(node.left, env), eval_dims(node.right, env)
            return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]
        if isinstance(node.op, ast.Pow):
            base = eval_dims(node.left, env)
            power = _as_exponent(node.right)
            return tuple(d * power for d in base)  # type: ignore[return-value]
    raise RelationError(f"unsupported syntax: {type(node).__name__}")


def eval_value(node: ast.expr, env: dict[str, float]) -> float:
    """Numeric value of an expression over canonical-unit quantities."""
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in CONSTANT_VALUES:
            return CONSTANT_VALUES[node.id]
        if node.id not in env:
            raise UnknownSymbol(node.id)
        return float(env[node.id])
    if isinstance(node, ast.UnaryOp):
        value = eval_value(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Call):
        name = node.func.id  # type: ignore[union-attr]
        try:
            return float(_NUMERIC_FUNCS[name](eval_value(node.args[0], env)))
        except (ValueError, OverflowError) as exc:
            raise RelationError(f"{name}() undefined for the quoted value: {exc}") from exc
    if isinstance(node, ast.BinOp):
        left, right = eval_value(node.left, env), eval_value(node.right, env)
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
        except ZeroDivisionError as exc:
            raise RelationError("division by zero in the quoted relation") from exc
        except (OverflowError, ValueError) as exc:
            raise RelationError(f"relation is not evaluable at the quoted values: {exc}") from exc
    raise RelationError(f"unsupported syntax: {type(node).__name__}")


def linearising_exponent(lhs: ast.expr, rhs: ast.expr) -> float:
    """The power a lone quantity is raised to on one side of the relation.

    The gap between the two sides of a relation is not invariant under
    rearranging it: writing `P**2 = a**3/(G M)` inflates a 3% error in P into
    a 6% gap, while writing `P = sqrt(a**3/(G M))` leaves it at 3%. Holding
    both forms to the same tolerance means a submitter is penalised for
    algebra rather than for physics, which is a false-fail generator.

    Where one side is a single quantity raised to a power n, a relative error
    d in that quantity moves the side by n*d to first order, so dividing the
    gap by n recovers a residual that means the same thing whichever way the
    relation was written. Returns 1.0 when neither side has that form, which
    leaves the raw gap in place.
    """
    for side in (lhs, rhs):
        if isinstance(side, ast.Name) and side.id not in CONSTANT_VALUES:
            return 1.0
        if (
            isinstance(side, ast.BinOp)
            and isinstance(side.op, ast.Pow)
            and isinstance(side.left, ast.Name)
            and side.left.id not in CONSTANT_VALUES
        ):
            try:
                power = abs(float(_as_exponent(side.right)))
            except RelationError:
                continue
            if power > 0:
                return power
    return 1.0


def _f(dims: Dims) -> DimsF:
    return tuple(Fraction(d) for d in dims)  # type: ignore[return-value]


def fmt(dims: DimsF) -> str:
    """Dimensions as a readable exponent product, e.g. `L^3 M^-1 T^-2`."""
    parts = [
        f"{sym}^{exp}" if exp != 1 else sym
        for sym, exp in zip(("L", "M", "T", "K"), dims)
        if exp != 0
    ]
    return " ".join(parts) if parts else "dimensionless"
