"""Basic drawing operations; every successful call returns its COM entity."""

import math
from typing import Iterable

from .types import Point, coordinates, doubles, number, point3d, radius_value, vertices


class Drawing:
    def _create(self, factory, *, layer=None, properties=()):
        if layer is not None:
            if not isinstance(layer, str) or not layer.strip():
                raise ValueError("layer must be a nonempty existing layer name.")
            # Validate before creating geometry; never change ActiveLayer.
            target = self._call(lambda: self.doc.Layers.Item(layer))
            layer = self._call(lambda: target.Name)
        entity = self._call(factory)
        try:
            for key, value in properties:
                self._call(lambda k=key, v=value: setattr(entity, k, v))
            if layer is not None:
                self._call(lambda: setattr(entity, "Layer", layer))
        except Exception:
            try:
                self._call(entity.Delete)
            except Exception as cleanup_error:
                raise RuntimeError("Entity configuration failed and cleanup failed; inspect the target drawing.") from cleanup_error
            raise
        return entity

    def line(self, start: Point, end: Point, *, layer: str | None = None, return_points: bool = False):
        """Create a WCS line; two-coordinate inputs use Z=0.

        With return_points=True, return (entity, start_xyz, end_xyz) instead
        of only the entity. Coordinates are immutable creation-time tuples.
        """
        if not isinstance(return_points, bool):
            raise ValueError("return_points must be a bool.")
        a, b = point3d(start, "start"), point3d(end, "end")
        if a == b:
            raise ValueError("Line endpoints must be different.")
        entity = self._create(lambda: self.modelspace.AddLine(doubles(a), doubles(b)), layer=layer)
        return (entity, a, b) if return_points else entity

    def next_line(self, previous, end: Point | None = None, *, angle: float | None = None,
                  turn: float | None = None, length: float | None = None, layer: str | None = None,
                  return_points: bool = False):
        """Continue an XY line from its endpoint using exactly one input mode.

        ``end=(x,y)`` or ``(x,y,z)`` is an absolute WCS endpoint; an explicit
        Z must match previous's elevation. ``angle`` is an absolute
        WCS direction (+X=0 degrees); ``turn`` is relative to previous's
        start-to-end direction. Both angular modes require a positive length.
        Angles are counterclockwise degrees. Preserve previous's constant Z.
        Return a new LINE; previous is never modified. With return_points=True,
        return (entity, start_xyz, end_xyz) for the new segment.
        """
        if sum(value is not None for value in (end, angle, turn)) != 1:
            raise ValueError("Specify exactly one of end, angle, or turn.")
        if end is not None:
            if length is not None:
                raise ValueError("length cannot be used with an absolute end point.")
            target_coordinates = coordinates(end, (2, 3), "end")
        else:
            direction = number(angle if angle is not None else turn, "angle" if angle is not None else "turn") % 360
            distance = number(length, "length")
            if distance <= 0:
                raise ValueError("length must be greater than zero.")

        if previous is None:
            raise ValueError("previous must be an AutoCAD LINE object.")
        try:
            object_name = self._call(lambda: previous.ObjectName)
        except AttributeError as exc:
            raise ValueError("previous must be an AutoCAD LINE object.") from exc
        if object_name != "AcDbLine":
            raise ValueError("previous must be an AutoCAD LINE object.")
        start = point3d(self._call(lambda: previous.StartPoint), "previous.StartPoint")
        tip = point3d(self._call(lambda: previous.EndPoint), "previous.EndPoint")
        if start[2] != tip[2] or start[:2] == tip[:2]:
            raise ValueError("previous must be a nonzero line parallel to the WCS XY plane.")

        if end is not None:
            if len(target_coordinates) == 3 and target_coordinates[2] != tip[2]:
                raise ValueError("end Z must match the previous line's elevation.")
            target = (target_coordinates[0], target_coordinates[1], tip[2])
        else:
            if turn is not None:
                heading = math.degrees(math.atan2(tip[1] - start[1], tip[0] - start[0]))
                direction = (heading + direction) % 360
            radians = math.radians(direction)
            target = (tip[0] + distance * math.cos(radians), tip[1] + distance * math.sin(radians), tip[2])
        return self.line(tip, target, layer=layer, return_points=return_points)

    def circle(self, center: Point, radius: float, *, layer: str | None = None):
        """Create a circle parallel to WCS XY, centered at a WCS point."""
        c, r = point3d(center, "center"), radius_value(radius)
        return self._create(lambda: self.modelspace.AddCircle(doubles(c), r), layer=layer)

    def arc(self, center: Point, radius: float, start: float, end: float, *, layer: str | None = None):
        """Create a counterclockwise WCS XY arc; angles are in degrees."""
        c, r = point3d(center, "center"), radius_value(radius)
        a, b = number(start, "start") % 360, number(end, "end") % 360
        if a == b:
            raise ValueError("Arc angles must differ modulo 360; use circle() for a full circle.")
        return self._create(lambda: self.modelspace.AddArc(doubles(c), r, math.radians(a), math.radians(b)), layer=layer)

    def point(self, position: Point, *, layer: str | None = None):
        """Create a WCS point entity."""
        p = point3d(position)
        return self._create(lambda: self.modelspace.AddPoint(doubles(p)), layer=layer)

    def polyline(self, points: Iterable[Point], closed: bool = False, *, elevation: float = 0, layer: str | None = None):
        """Create an XY lightweight polyline from strictly 2D vertices.

        The normal is +WCS Z, so OCS XY equals WCS XY. Elevation is WCS Z.
        Use polyline3d() for XYZ vertices.
        """
        pts = vertices(points, 2, closed)
        z = number(elevation, "elevation")
        flat = tuple(value for p in pts for value in p)
        return self._create(
            lambda: self.modelspace.AddLightWeightPolyline(doubles(flat)), layer=layer,
            properties=(("Normal", doubles((0., 0., 1.))), ("Elevation", z), ("Closed", closed)),
        )

    def polyline3d(self, points: Iterable[Point], closed: bool = False, *, layer: str | None = None):
        """Create a true 3D polyline from strictly XYZ WCS vertices."""
        pts = vertices(points, 3, closed)
        flat = tuple(value for p in pts for value in p)
        return self._create(lambda: self.modelspace.Add3DPoly(doubles(flat)), layer=layer, properties=(("Closed", closed),))

    def triangle(self, p1: Point, p2: Point, p3: Point, *, elevation: float = 0, layer: str | None = None):
        """Create a closed XY lightweight polyline from three noncollinear 2D points."""
        a = coordinates(p1, (2,), "p1")
        b = coordinates(p2, (2,), "p2")
        c = coordinates(p3, (2,), "p3")
        if (b[0] - a[0]) * (c[1] - a[1]) == (b[1] - a[1]) * (c[0] - a[0]):
            raise ValueError("Triangle vertices must be distinct and noncollinear.")
        return self.polyline((a, b, c), closed=True, elevation=elevation, layer=layer)

    def rectangle(self, corner1: Point, corner2: Point, *, elevation: float = 0, layer: str | None = None):
        """Create a closed XY lightweight polyline from opposite 2D corners."""
        a = coordinates(corner1, (2,), "corner1")
        b = coordinates(corner2, (2,), "corner2")
        if a[0] == b[0] or a[1] == b[1]:
            raise ValueError("Rectangle width and height must be nonzero.")
        return self.polyline((a, (b[0], a[1]), b, (a[0], b[1])), closed=True, elevation=elevation, layer=layer)
