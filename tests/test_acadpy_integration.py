"""Opt in with ACADPY_INTEGRATION=1; never save or edit an existing drawing."""

import math
import os
from pathlib import Path
import runpy

import pytest

from acadpy import AutoCAD
from acadpy.types import doubles

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("ACADPY_INTEGRATION") != "1", reason="Set ACADPY_INTEGRATION=1 to use a running AutoCAD 2027."),
]


@pytest.fixture
def cad():
    with AutoCAD() as connection:
        original = connection.doc
        restore_original = connection._call(lambda: original.Activate)
        original_count = connection._call(lambda: original.ModelSpace.Count)
        test_doc = connection._call(lambda: connection.app.Documents.Add())
        try:
            with AutoCAD(document=connection._call(lambda: test_doc.Name)) as drawing:
                yield drawing
        finally:
            try:
                connection._call(lambda: test_doc.Close(False))
            finally:
                connection._call(restore_original)
        assert connection._call(lambda: original.ModelSpace.Count) == original_count


def test_real_entities_coordinates_and_layer(cad):
    assert str(cad.app.Version).startswith("26.0")
    cad.doc.Layers.Add("ACADPY_TEST")
    old_layer = cad.doc.ActiveLayer.Name
    line = cad.line((0, 0, 0), (100, 100, 50), layer="ACADPY_TEST")
    assert line.ObjectName == "AcDbLine"
    assert tuple(line.StartPoint) == pytest.approx((0, 0, 0))
    assert tuple(line.EndPoint) == pytest.approx((100, 100, 50))
    assert line.Layer == "ACADPY_TEST"
    assert cad.doc.ActiveLayer.Name == old_layer
    circle = cad.circle((5, 6, 7), radius=50)
    assert circle.ObjectName == "AcDbCircle"
    assert tuple(circle.Center) == pytest.approx((5, 6, 7))
    assert circle.Radius == pytest.approx(50)
    arc = cad.arc((10, 20, 30), 25, start=350, end=10)
    assert arc.ObjectName == "AcDbArc"
    assert tuple(arc.Center) == pytest.approx((10, 20, 30))
    assert arc.Radius == pytest.approx(25)
    assert arc.StartAngle == pytest.approx(math.radians(350))
    assert arc.EndAngle == pytest.approx(math.radians(10))
    point = cad.point((10, 20, 30))
    assert point.ObjectName == "AcDbPoint"
    assert tuple(point.Coordinates) == pytest.approx((10, 20, 30))
    rect = cad.rectangle((0, 0), (100, 50), elevation=3)
    assert rect.ObjectName == "AcDbPolyline"
    assert rect.Closed
    assert tuple(rect.Coordinates) == pytest.approx((0, 0, 100, 0, 100, 50, 0, 50))
    assert rect.Elevation == pytest.approx(3)
    poly = cad.polyline([(0, 0), (50, 0), (50, 50), (0, 0)], closed=True)
    assert poly.ObjectName == "AcDbPolyline"
    assert poly.Closed
    assert tuple(poly.Coordinates) == pytest.approx((0, 0, 50, 0, 50, 50))
    poly3 = cad.polyline3d([(0, 0, 0), (50, 0, 50), (50, 50, 20)], layer="ACADPY_TEST")
    assert poly3.ObjectName == "AcDb3dPolyline"
    assert not poly3.Closed
    assert poly3.Layer == "ACADPY_TEST"
    assert tuple(poly3.Coordinates) == pytest.approx((0, 0, 0, 50, 0, 50, 50, 50, 20))
    closed3 = cad.polyline3d([(0, 0, 0), (50, 0, 50), (50, 50, 20)], closed=True)
    assert closed3.Closed
    assert cad.modelspace.Count == 8


def test_wcs_xy_ignores_current_ucs_and_elevation(cad):
    ucs = cad.doc.UserCoordinateSystems.Add(doubles((10., 20., 30.)), doubles((10., 21., 30.)), doubles((10., 20., 31.)), "ACADPY_UCS")
    cad.doc.ActiveUCS = ucs
    cad.doc.SetVariable("ELEVATION", 42.)
    poly = cad.polyline([(0, 0), (10, 0), (10, 10)])
    assert not poly.Closed
    assert poly.Elevation == pytest.approx(0)
    assert tuple(poly.Normal) == pytest.approx((0, 0, 1))
    for i, expected in enumerate([(0, 0, 0), (10, 0, 0), (10, 10, 0)]):
        xy = poly.Coordinate(i)
        wcs = cad.doc.Utility.TranslateCoordinates(doubles((*xy, poly.Elevation)), 4, 0, False, doubles(poly.Normal))
        assert tuple(wcs) == pytest.approx(expected)
    line = cad.line((0, 0), (1, 2, 3))
    assert tuple(line.EndPoint) == pytest.approx((1, 2, 3))


def test_target_does_not_follow_active_document(cad):
    other = cad._call(lambda: cad.app.Documents.Add())
    try:
        count = cad.modelspace.Count
        cad.point((1, 2, 3))
        assert cad.modelspace.Count == count + 1
        assert other.ModelSpace.Count == 0
    finally:
        cad._call(lambda: other.Close(False))
        cad._call(lambda: cad.doc.Activate())


def test_bad_parameters_and_missing_layer_do_not_create_geometry(cad):
    before = cad.modelspace.Count
    with pytest.raises(ValueError):
        cad.circle((0, 0), -1)
    with pytest.raises(ValueError):
        cad.polyline([(0, 0, 0), (1, 1, 1)])
    import pywintypes
    with pytest.raises(pywintypes.com_error):
        cad.point((0, 0), layer="ACADPY_MISSING")
    assert cad.modelspace.Count == before


def test_basic_example_as_single_script(cad):
    example = Path(__file__).resolve().parents[1] / "examples" / "basic.py"
    runpy.run_path(str(example), run_name="__main__")
    assert cad.modelspace.Count == 8


def test_triangle_coordinates_elevation_and_layer(cad):
    cad.doc.Layers.Add("ACADPY_TRIANGLE")
    triangle = cad.triangle((0, 0), (100, 0), (50, 80), elevation=7, layer="ACADPY_TRIANGLE")
    assert triangle.ObjectName == "AcDbPolyline"
    assert triangle.Closed
    assert tuple(triangle.Coordinates) == pytest.approx((0, 0, 100, 0, 50, 80))
    assert triangle.Elevation == pytest.approx(7)
    assert tuple(triangle.Normal) == pytest.approx((0, 0, 1))
    assert triangle.Layer == "ACADPY_TRIANGLE"


def test_connected_line_modes_in_wcs(cad):
    cad.doc.Layers.Add("ACADPY_LINES")
    ucs = cad.doc.UserCoordinateSystems.Add(doubles((10., 20., 30.)), doubles((10., 21., 30.)), doubles((10., 20., 31.)), "ACADPY_LINES_UCS")
    cad.doc.ActiveUCS = ucs
    first = cad.line((0, 0, 7), (100, 0, 7))
    xy = cad.next_line(first, end=(100, 100), layer="ACADPY_LINES")
    polar = cad.next_line(xy, angle=180, length=50, layer="ACADPY_LINES")
    relative = cad.next_line(polar, turn=-90, length=50, layer="ACADPY_LINES")
    for entity, start, end in [
        (xy, (100, 0, 7), (100, 100, 7)),
        (polar, (100, 100, 7), (50, 100, 7)),
        (relative, (50, 100, 7), (50, 150, 7)),
    ]:
        assert entity.ObjectName == "AcDbLine"
        assert tuple(entity.StartPoint) == pytest.approx(start)
        assert tuple(entity.EndPoint) == pytest.approx(end)
        assert entity.Length == pytest.approx(math.dist(start, end))
        assert entity.Layer == "ACADPY_LINES"
    assert tuple(first.StartPoint) == pytest.approx((0, 0, 7))
    assert tuple(first.EndPoint) == pytest.approx((100, 0, 7))
    before = cad.modelspace.Count
    with pytest.raises(ValueError):
        cad.next_line(relative, angle=90, turn=90, length=50)
    assert cad.modelspace.Count == before


def test_connected_lines_example_as_single_script(cad):
    example = Path(__file__).resolve().parents[1] / "examples" / "connected_lines.py"
    runpy.run_path(str(example), run_name="__main__")
    assert cad.modelspace.Count == 5


def test_line_coordinate_returns_match_real_entities(cad):
    entity, start, end = cad.line((10, 20, 7), (30, 20, 7), return_points=True)
    assert start == pytest.approx(tuple(entity.StartPoint))
    assert end == pytest.approx(tuple(entity.EndPoint))
    origin = start
    for kwargs in ({"end": (40, 30)}, {"angle": 90, "length": 10}, {"turn": -90, "length": 10}, {"end": origin}):
        entity, start, end = cad.next_line(entity, return_points=True, **kwargs)
        assert start == pytest.approx(tuple(entity.StartPoint))
        assert end == pytest.approx(tuple(entity.EndPoint))
    assert end == origin
