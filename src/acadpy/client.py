"""Attach to AutoCAD without launching, saving, or closing any drawings."""

import time
import threading

from .drawing import Drawing


class AutoCADConnectionError(RuntimeError):
    """AutoCAD or its target document cannot be accessed."""


def _initialize_com():
    """Acquire one native COM count, including when pywin32 already initialized.

    pywin32 suppresses repeated initialization on its main thread; using its
    CoUninitialize per client would disconnect other clients on that thread.
    Native ole32 calls have balanced reference counts and add no dependency.
    """
    import ctypes

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    ole32.CoInitializeEx.restype = ctypes.HRESULT
    ole32.CoUninitialize.argtypes = ()
    ole32.CoUninitialize.restype = None
    ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    return ole32.CoUninitialize


class AutoCAD(Drawing):
    """Bind to the current document of an already running AutoCAD 2027.

    Use on the creating thread. ``close()`` releases this client's COM references;
    it does not close AutoCAD or the document. Prefer use as a context manager.
    """

    def __init__(self, document: str | None = None):
        self._closed = True
        try:
            import pythoncom
            import pywintypes
            import win32com.client
        except ImportError as exc:
            raise AutoCADConnectionError("acadpy requires Windows and pywin32. Install with python -m pip install -e .") from exc

        self._com_error = pywintypes.com_error
        self._thread = threading.get_ident()
        try:
            self._uninitialize = _initialize_com()
        except OSError as exc:
            raise AutoCADConnectionError("Cannot initialize COM. Use acadpy on an STA thread.") from exc
        self._closed = False
        try:
            # AutoCAD 2027 registers the major-version ProgID (.26).
            self.app = win32com.client.GetActiveObject("AutoCAD.Application.26")
        except (pywintypes.com_error, OSError) as exc:
            self.close()
            raise AutoCADConnectionError("Cannot attach to AutoCAD 2027. Open AutoCAD 2027 and a drawing first; acadpy never launches AutoCAD.") from exc
        try:
            self.doc = self._call(lambda: self.app.ActiveDocument if document is None else self.app.Documents.Item(document))
            self.modelspace = self._call(lambda: self.doc.ModelSpace)
            self.name = self._call(lambda: self.doc.Name)
        except Exception as exc:
            self.close()
            raise AutoCADConnectionError("Cannot access the target drawing. Open it and wait until AutoCAD is ready.") from exc

    def _call(self, action):
        if self._closed:
            raise RuntimeError("This AutoCAD client is closed.")
        self._check_thread()
        for attempt in range(25):
            try:
                return action()
            except self._com_error as exc:
                # Retry only explicit COM call rejection, never arbitrary failures.
                if exc.hresult not in (-2147418111, -2147417846) or attempt == 24:
                    raise
                time.sleep(0.2)
            except AttributeError:
                # Dynamic dispatch hides a rejected GetIDsOfNames as an
                # AttributeError while AutoCAD switches/opens/closes drawings.
                if attempt == 24:
                    raise
                time.sleep(0.2)

    def close(self):
        """Release COM on the calling thread; never save or close a drawing."""
        if not self._closed:
            self._check_thread()
            self.modelspace = self.doc = self.app = None
            self._closed = True
            self._uninitialize()

    def _check_thread(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError("Use and close AutoCAD on the thread that created it.")

    def __enter__(self):
        if self._closed:
            raise RuntimeError("This AutoCAD client is closed.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
