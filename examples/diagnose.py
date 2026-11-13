"""Inspect the local AutoCAD connection; use --draw to verify drawing a LINE."""

import argparse
import logging
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", action="store_true", help="Create one LINE in the connected drawing and refresh its display.")
    args = parser.parse_args()

    log_path = Path(__file__).resolve().parents[1] / "logs" / "diagnose.log"
    log_path.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )
    logging.info("Log file: %s", log_path)
    logging.info("Python: %s", sys.executable)
    logging.info("Working directory: %s", Path.cwd())

    try:
        import acadpy

        logging.info("acadpy loaded from: %s", acadpy.__file__)
        logging.info("Connecting to AutoCAD.Application.25.1 ...")
        with acadpy.AutoCAD() as cad:
            logging.info("AutoCAD version: %s", cad._call(lambda: cad.app.Version))
            logging.info("AutoCAD window HWND: %s", cad._call(lambda: cad.app.HWND))
            logging.info("Target drawing: %s", cad.name)
            logging.info("Drawing path: %s", cad._call(lambda: cad.doc.FullName))
            logging.info("Active layout: %s", cad._call(lambda: cad.doc.GetVariable("CTAB")))
            layer = cad._call(lambda: cad.doc.ActiveLayer)
            logging.info("Active layer: %s; on=%s; frozen=%s", cad._call(lambda: layer.Name), cad._call(lambda: layer.LayerOn), cad._call(lambda: layer.Freeze))
            before = cad._call(lambda: cad.modelspace.Count)
            logging.info("ModelSpace objects before: %s", before)
            if args.draw:
                entity = cad.line((0, 0), (100, 0))
                logging.info("Created: %s; Handle=%s; layer=%s", cad._call(lambda: entity.ObjectName), cad._call(lambda: entity.Handle), cad._call(lambda: entity.Layer))
                logging.info("Start=%s; End=%s", cad._call(lambda: tuple(entity.StartPoint)), cad._call(lambda: tuple(entity.EndPoint)))
                after = cad._call(lambda: cad.modelspace.Count)
                logging.info("ModelSpace objects after: %s (change=%s)", after, after - before)
                cad._call(lambda: entity.Update())
                cad._call(lambda: cad.doc.Regen(1))
                logging.info("Display refreshed. If the line is not visible, check the target drawing, Model tab, layer visibility, and Zoom Extents.")
            else:
                logging.info("Connection check complete; no geometry created. Use --draw to create a test LINE.")
        logging.info("Finished successfully.")
        return 0
    except Exception:
        logging.exception("Diagnostic failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
