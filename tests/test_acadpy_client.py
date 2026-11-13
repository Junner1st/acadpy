import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from acadpy import AutoCAD, AutoCADConnectionError
from acadpy.types import doubles


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult


@pytest.fixture
def com(monkeypatch):
    pythoncom = SimpleNamespace(VT_ARRAY=8192, VT_R8=5)
    initialize, uninitialize = Mock(), Mock()
    initialize.return_value = uninitialize
    monkeypatch.setattr("acadpy.client._initialize_com", initialize)
    doc = SimpleNamespace(Name="target.dwg", ModelSpace=Mock())
    app = SimpleNamespace(ActiveDocument=doc, Documents=Mock())
    client = ModuleType("win32com.client")
    client.GetActiveObject = Mock(return_value=app)
    client.VARIANT = Mock(side_effect=lambda kind, values: (kind, values))
    win32com = ModuleType("win32com")
    win32com.client = client
    for name, module in {"pythoncom": pythoncom, "pywintypes": SimpleNamespace(com_error=ComError), "win32com": win32com, "win32com.client": client}.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr("acadpy.client.time.sleep", Mock())
    return SimpleNamespace(pythoncom=pythoncom, client=client, app=app, doc=doc, initialize=initialize, uninitialize=uninitialize)


def test_attach_binds_once_and_close_is_idempotent(com):
    with AutoCAD() as cad:
        com.client.GetActiveObject.assert_called_once_with("AutoCAD.Application.25.1")
        com.initialize.assert_called_once_with()
        assert cad.doc is com.doc
        assert cad.modelspace is com.doc.ModelSpace
        com.app.ActiveDocument = SimpleNamespace(Name="other.dwg")
        assert cad.doc is com.doc
    cad.close()
    com.uninitialize.assert_called_once()
    com.doc.ModelSpace.Close.assert_not_called()
    assert cad.app is cad.doc is cad.modelspace is None


def test_named_document(com):
    com.app.Documents.Item.return_value = com.doc
    with AutoCAD(document="target.dwg") as cad:
        assert cad.name == "target.dwg"
    com.app.Documents.Item.assert_called_once_with("target.dwg")


def test_not_running_has_clear_error_and_balances_com(com):
    com.client.GetActiveObject.side_effect = ComError(-2147221021)
    with pytest.raises(AutoCADConnectionError, match="Open AutoCAD 2026"):
        AutoCAD()
    com.uninitialize.assert_called_once()


def test_no_document_balances_com(com):
    com.app.ActiveDocument = None
    with pytest.raises(AutoCADConnectionError, match="target drawing"):
        AutoCAD()
    com.uninitialize.assert_called_once()


def test_context_exception_releases_com(com):
    with pytest.raises(ValueError):
        with AutoCAD():
            raise ValueError("user error")
    com.uninitialize.assert_called_once()


def test_only_rejected_calls_are_retried(com):
    with AutoCAD() as cad:
        action = Mock(side_effect=[ComError(-2147418111), ComError(-2147417846), "done"])
        assert cad._call(action) == "done"
        assert action.call_count == 3
        failure = Mock(side_effect=ComError(-1))
        with pytest.raises(ComError):
            cad._call(failure)
        assert failure.call_count == 1
        busy = Mock(side_effect=ComError(-2147418111))
        with pytest.raises(ComError):
            cad._call(busy)
        assert busy.call_count == 25
        discovery = Mock(side_effect=[AttributeError("busy lookup"), "ready"])
        assert cad._call(discovery) == "ready"


def test_variant_is_double_array(com):
    assert doubles([1., 2., 3.]) == (8197, (1., 2., 3.))


def test_nested_clients_do_not_close_each_other(com):
    with AutoCAD() as outer:
        with AutoCAD():
            pass
        assert outer._call(lambda: outer.doc.Name) == "target.dwg"
        assert com.uninitialize.call_count == 1
    assert com.initialize.call_count == com.uninitialize.call_count == 2


def test_wrong_thread_does_not_release_or_draw(com, monkeypatch):
    with AutoCAD() as cad:
        with monkeypatch.context() as context:
            context.setattr("acadpy.client.threading.get_ident", lambda: -1)
            with pytest.raises(RuntimeError, match="thread"):
                cad.close()
            with pytest.raises(RuntimeError, match="thread"):
                cad.point((0, 0))
            com.uninitialize.assert_not_called()


def test_apartment_initialization_failure_is_clear(com):
    com.initialize.side_effect = OSError("different apartment")
    with pytest.raises(AutoCADConnectionError, match="STA thread"):
        AutoCAD()
    com.uninitialize.assert_not_called()
