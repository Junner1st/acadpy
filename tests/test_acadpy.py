"""Unit tests run without AutoCAD or pywin32."""

import math
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from acadpy import AutoCAD
from acadpy.types import point3d, vertices


@pytest.fixture
def cad(monkeypatch):
    monkeypatch.setattr("acadpy.drawing.doubles", tuple)
    instance = AutoCAD.__new__(AutoCAD)
    instance._closed = False
    instance._thread = threading.get_ident()
    instance._com_error = OSError
    instance.modelspace = Mock()
    instance.doc = SimpleNamespace(Layers=Mock())
    return instance


def test_geometry_and_return_values(cad):
    assert cad.line((0, 0), (1, 2, 3)) is cad.modelspace.AddLine.return_value
    cad.modelspace.AddLine.assert_called_once_with((0., 0., 0.), (1., 2., 3.))
    assert cad.circle((1, 2, 3), 4) is cad.modelspace.AddCircle.return_value
    cad.modelspace.AddCircle.assert_called_once_with((1., 2., 3.), 4.)
    assert cad.point((1, 2)) is cad.modelspace.AddPoint.return_value
    cad.modelspace.AddPoint.assert_called_once_with((1., 2., 0.))
    assert cad.arc((0, 0, 5), 2, -10, 90) is cad.modelspace.AddArc.return_value
    cad.modelspace.AddArc.assert_called_once_with((0., 0., 5.), 2., math.radians(350), math.pi / 2)


def test_polylines_closure_elevation_and_generators(cad):
    poly = cad.polyline(iter([(0, 0), (3, 0), (3, 2), (0, 0)]), closed=True, elevation=7)
    cad.modelspace.AddLightWeightPolyline.assert_called_once_with((0., 0., 3., 0., 3., 2.))
    assert poly.Closed is True
    assert poly.Elevation == 7
    assert poly.Normal == (0., 0., 1.)
    poly3 = cad.polyline3d([(0, 0, 0), (3, 0, 2)])
    cad.modelspace.Add3DPoly.assert_called_once_with((0., 0., 0., 3., 0., 2.))
    assert poly3.Closed is False
    rect = cad.rectangle((5, 6), (1, 2))
    assert rect is cad.modelspace.AddLightWeightPolyline.return_value
    assert rect.Closed is True
    assert cad.modelspace.AddLightWeightPolyline.call_args.args[0] == (5., 6., 1., 6., 1., 2., 5., 2.)


@pytest.mark.parametrize("point", [None, 3, (), (1,), (1, 2, 3, 4), "12", (True, 2), ("1", 2), (float("nan"), 2), (0, float("inf")), (1j, 0), (10**400, 0)])
def test_invalid_coordinates(point):
    with pytest.raises(ValueError):
        point3d(point)


@pytest.mark.parametrize("points", [((0, 0), (100, 0), (50, 80)), ((50, 80), (100, 0), (0, 0))])
def test_triangle_is_closed_and_preserves_vertices_elevation_and_layer(cad, points):
    cad.doc.Layers.Item.return_value.Name = "Triangle"
    entity = cad.triangle(*points, elevation=12, layer="Triangle")
    assert entity is cad.modelspace.AddLightWeightPolyline.return_value
    assert entity.Closed is True
    assert entity.Elevation == 12
    assert entity.Normal == (0., 0., 1.)
    assert entity.Layer == "Triangle"
    cad.modelspace.AddLightWeightPolyline.assert_called_once_with(tuple(v for p in points for v in p))


@pytest.mark.parametrize("method,args,kwargs", [
    ("line", ((0, 0), (0, 0, 0)), {}),
    ("circle", ((0, 0), 0), {}),
    ("circle", ((0, 0), -1), {}),
    ("circle", ((0, 0), True), {}),
    ("circle", ((0, 0), float("inf")), {}),
    ("arc", ((0, 0), 1, 0, 360), {}),
    ("arc", ((0, 0), 1, float("nan"), 90), {}),
    ("arc", ((0, 0), 1, 0, "90"), {}),
    ("polyline", ([(0, 0, 0), (1, 1, 0)],), {}),
    ("polyline3d", ([(0, 0), (1, 1)],), {}),
    ("polyline", (None,), {}),
    ("polyline", ([],), {}),
    ("polyline", ([(0, 0), (1, 1)],), {"closed": True}),
    ("polyline", ([(0, 0), (1, 1)],), {"closed": 1}),
    ("polyline", ([(0, 0), (0, 0), (1, 1)],), {}),
    ("polyline", ([(0, 0), (1, 1), (0, 0)],), {"closed": True}),
    ("polyline", ([(0, 0), (1, 1)],), {"elevation": float("nan")}),
    ("rectangle", ((0, 0), (0, 2)), {}),
    ("rectangle", ((0, 0, 1), (2, 2, 1)), {}),
    ("triangle", ((0, 0), (0, 0), (1, 1)), {}),
    ("triangle", ((0, 0), (1, 1), (2, 2)), {}),
    ("triangle", ((0, 0), (1, 0), (2, 0)), {}),
    ("triangle", ((0, 0, 1), (1, 0), (0, 1)), {}),
    ("triangle", ((0, 0), (1, 0), (float("nan"), 1)), {}),
    ("triangle", ((0, 0), (1, 0), (0, 1)), {"elevation": float("inf")}),
    ("point", ((0, 0),), {"layer": ""}),
    ("point", ((0, 0),), {"layer": 123}),
])
def test_invalid_arguments_never_create_entities(cad, method, args, kwargs):
    with pytest.raises(ValueError):
        getattr(cad, method)(*args, **kwargs)
    assert not cad.modelspace.mock_calls


def test_layers_validate_before_drawing_and_do_not_change_active_layer(cad):
    cad.doc.ActiveLayer = "original"
    cad.doc.Layers.Item.return_value.Name = "Demo"
    entity = cad.line((0, 0), (1, 1), layer="demo")
    assert entity.Layer == "Demo"
    assert cad.doc.ActiveLayer == "original"
    cad.doc.Layers.Item.side_effect = RuntimeError("missing layer")
    with pytest.raises(RuntimeError, match="missing layer"):
        cad.point((0, 0), layer="missing")
    cad.modelspace.AddPoint.assert_not_called()


def test_configuration_failure_removes_entity(cad):
    class Entity:
        deleted = False

        @property
        def Closed(self):
            return False

        @Closed.setter
        def Closed(self, value):
            raise RuntimeError("configuration failed")

        def Delete(self):
            self.deleted = True

    entity = Entity()
    cad.modelspace.Add3DPoly.return_value = entity
    with pytest.raises(RuntimeError, match="configuration failed"):
        cad.polyline3d([(0, 0, 0), (1, 1, 1)])
    assert entity.deleted


def test_closed_client_rejects_drawing(cad):
    cad._closed = True
    with pytest.raises(RuntimeError, match="closed"):
        cad.line((0, 0), (1, 1))
    assert not cad.modelspace.mock_calls


def test_closed_vertices_normalize_only_terminal_duplicate():
    assert vertices([(0, 0), (1, 0), (1, 1), (0, 0)], 2, True) == ((0., 0.), (1., 0.), (1., 1.))


@pytest.mark.parametrize("kwargs,expected", [
    ({"end": (20, 40)}, (20, 40, 7)),
    ({"end": (20, 40, 7)}, (20, 40, 7)),
    ({"angle": 0, "length": 10}, (10, 10, 7)),
    ({"angle": 90, "length": 10}, (0, 20, 7)),
    ({"angle": -90, "length": 10}, (0, 0, 7)),
    ({"angle": 450, "length": 10}, (0, 20, 7)),
    ({"turn": 0, "length": 10}, (0, 20, 7)),
    ({"turn": 90, "length": 10}, (-10, 10, 7)),
    ({"turn": -90, "length": 10}, (10, 10, 7)),
    ({"turn": 180, "length": 10}, (0, 0, 7)),
    ({"turn": 450, "length": 10}, (-10, 10, 7)),
])
def test_next_line_modes_use_tip_and_preserve_elevation(cad, kwargs, expected):
    previous = SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 7), EndPoint=(0, 10, 7))
    cad.doc.Layers.Item.return_value.Name = "Connected"
    entity = cad.next_line(previous, layer="Connected", **kwargs)
    assert entity is cad.modelspace.AddLine.return_value
    a, b = cad.modelspace.AddLine.call_args.args
    assert a == (0, 10, 7)
    assert b == pytest.approx(expected)
    assert entity.Layer == "Connected"
    assert previous.StartPoint == (0, 0, 7)
    assert previous.EndPoint == (0, 10, 7)


def test_next_line_chain_uses_each_returned_segment_direction(cad):
    def add_line(a, b):
        return SimpleNamespace(ObjectName="AcDbLine", StartPoint=a, EndPoint=b)

    cad.modelspace.AddLine.side_effect = add_line
    segment = cad.line((10, 20), (20, 30))
    segment = cad.next_line(segment, (30, 40))
    segment = cad.next_line(segment, angle=180, length=10)
    segment = cad.next_line(segment, turn=-90, length=10)
    assert segment.StartPoint == pytest.approx((20, 40, 0))
    assert segment.EndPoint == pytest.approx((20, 50, 0))
    assert cad.modelspace.AddLine.call_count == 4


@pytest.mark.parametrize("kwargs", [
    {}, {"length": 10}, {"angle": 90}, {"turn": 90},
    {"end": (1, 2), "angle": 0, "length": 10},
    {"end": (1, 2), "turn": 0, "length": 10},
    {"angle": 0, "turn": 0, "length": 10},
    {"end": (1, 2), "length": 10},
    {"end": (1, 2, 3)}, {"end": (0, 10)},
    {"end": (float("nan"), 0)},
    {"angle": True, "length": 10},
    {"angle": float("inf"), "length": 10},
    {"turn": float("nan"), "length": 10},
    {"turn": "90", "length": 10},
    {"angle": 90, "length": 0},
    {"turn": 90, "length": -10},
    {"angle": 90, "length": True},
    {"angle": 90, "length": float("inf")},
    {"angle": 90, "length": "10"},
])
def test_next_line_rejects_invalid_or_conflicting_arguments(cad, kwargs):
    previous = SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 7), EndPoint=(0, 10, 7))
    with pytest.raises(ValueError):
        cad.next_line(previous, **kwargs)
    assert not cad.modelspace.mock_calls


@pytest.mark.parametrize("previous", [
    None,
    SimpleNamespace(ObjectName="AcDbCircle"),
    SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 0), EndPoint=(1, 1, 1)),
    SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 0), EndPoint=(0, 0, 0)),
    SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 0), EndPoint=(0, 0, 1)),
])
def test_next_line_rejects_unsupported_previous_geometry(cad, previous):
    with pytest.raises(ValueError):
        cad.next_line(previous, end=(10, 20))
    assert not cad.modelspace.mock_calls


def test_line_can_return_entity_and_normalized_coordinate_snapshots(cad):
    a, b = [0, 0], [10, 20, 7]
    entity, start, end = cad.line(a, b, return_points=True)
    assert entity is cad.modelspace.AddLine.return_value
    assert start == (0., 0., 0.)
    assert end == (10., 20., 7.)
    a[0], b[0] = 99, 99
    assert start == (0., 0., 0.)
    assert end == (10., 20., 7.)


@pytest.mark.parametrize("kwargs,expected", [
    ({"end": (20, 40)}, (20, 40, 7)),
    ({"angle": 0, "length": 10}, (10, 10, 7)),
    ({"turn": -90, "length": 10}, (10, 10, 7)),
])
def test_next_line_can_return_new_segment_endpoints(cad, kwargs, expected):
    previous = SimpleNamespace(ObjectName="AcDbLine", StartPoint=(0, 0, 7), EndPoint=(0, 10, 7))
    cad.doc.Layers.Item.return_value.Name = "Connected"
    entity, start, end = cad.next_line(previous, return_points=True, layer="Connected", **kwargs)
    assert entity is cad.modelspace.AddLine.return_value
    assert entity.Layer == "Connected"
    assert start == (0, 10, 7)
    assert end == pytest.approx(expected)
    assert isinstance(start, tuple) and isinstance(end, tuple)


@pytest.mark.parametrize("flag", [None, 1, "yes"])
def test_return_points_requires_boolean_before_creating_line(cad, flag):
    with pytest.raises(ValueError, match="return_points"):
        cad.line((0, 0), (10, 0), return_points=flag)
    assert not cad.modelspace.mock_calls


def test_next_line_can_close_to_returned_start(cad):
    cad.modelspace.AddLine.side_effect = lambda a, b: SimpleNamespace(ObjectName="AcDbLine", StartPoint=a, EndPoint=b)
    first, origin, _ = cad.line((0, 0, 7), (10, 0, 7), return_points=True)
    second = cad.next_line(first, turn=90, length=10)
    closing, start, end = cad.next_line(second, end=origin, return_points=True)
    assert end == origin
    assert closing.EndPoint == first.StartPoint
    assert start == second.EndPoint


def test_magic_circle_example_closes_star_and_places_circles_at_five_vertices(cad, monkeypatch):
    from pathlib import Path
    import runpy

    lines = []
    def add_line(a, b):
        entity = SimpleNamespace(ObjectName="AcDbLine", StartPoint=a, EndPoint=b)
        lines.append(entity)
        return entity

    cad.modelspace.AddLine.side_effect = add_line
    cad.close = lambda: None
    monkeypatch.setattr("acadpy.AutoCAD", lambda: cad)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "examples" / "magic_circle1.py"), run_name="__main__")
    assert len(lines) == 5
    assert lines[0].StartPoint == (40, 0, 0)
    assert lines[-1].EndPoint == lines[0].StartPoint
    expected_length = 80 * math.sin(math.radians(72))
    for i, line in enumerate(lines):
        assert line.EndPoint == lines[(i + 1) % 5].StartPoint
        assert math.hypot(*line.StartPoint[:2]) == pytest.approx(40)
        assert math.dist(line.StartPoint, line.EndPoint) == pytest.approx(expected_length)
    centers = [call.args[0] for call in cad.modelspace.AddCircle.call_args_list if call.args[1] == 10]
    assert len(centers) == len(set(centers)) == 5
    for center, line in zip(centers, lines):
        assert center == pytest.approx(line.StartPoint)
