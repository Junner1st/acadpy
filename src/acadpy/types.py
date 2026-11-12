"""Coordinate validation and lazy pywin32 VARIANT conversion."""

import math
from numbers import Real
from typing import Iterable

Point = Iterable[float]


def number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number.")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number.")
    return result


def coordinates(point: Point, dimensions: tuple[int, ...], name: str = "point") -> tuple[float, ...]:
    try:
        values = tuple(point)
    except TypeError as exc:
        raise ValueError(f"{name} must be a coordinate sequence.") from exc
    if len(values) not in dimensions:
        expected = " or ".join(map(str, dimensions))
        raise ValueError(f"{name} must have {expected} coordinates.")
    return tuple(number(value, name) for value in values)


def point3d(point: Point, name: str = "point") -> tuple[float, float, float]:
    values = coordinates(point, (2, 3), name)
    return (values[0], values[1], values[2] if len(values) == 3 else 0.0)


def radius_value(radius: float) -> float:
    result = number(radius, "radius")
    if result <= 0:
        raise ValueError("radius must be greater than zero.")
    return result


def vertices(points: Iterable[Point], dimension: int, closed: bool) -> tuple[tuple[float, ...], ...]:
    if not isinstance(closed, bool):
        raise ValueError("closed must be a bool.")
    try:
        iterator = iter(points)
    except TypeError as exc:
        raise ValueError("points must be an iterable of coordinates.") from exc
    result = tuple(coordinates(p, (dimension,), f"points[{i}]") for i, p in enumerate(iterator))
    # Closed is represented by the COM property, not a duplicate final vertex.
    if closed and len(result) > 1 and result[-1] == result[0]:
        result = result[:-1]
    minimum = 3 if closed else 2
    if len(result) < minimum or len(set(result)) < minimum:
        raise ValueError(f"Polyline requires at least {minimum} distinct vertices.")
    if any(a == b for a, b in zip(result, result[1:])):
        raise ValueError("Polyline cannot contain consecutive duplicate vertices.")
    return result


def doubles(values: Iterable[float]):
    """Pack validated doubles as VT_ARRAY | VT_R8, without NumPy."""
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(values))
