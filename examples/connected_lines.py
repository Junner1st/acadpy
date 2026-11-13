"""Continue LINE entities using absolute XY, absolute heading, and relative turn."""

from acadpy import AutoCAD

def main():
    with AutoCAD() as cad:
        segment = cad.line((0, 0), (100, 0))
        segment = cad.next_line(segment, end=(100, 100))
        segment = cad.next_line(segment, angle=180, length=50)
        segment = cad.next_line(segment, turn=-90, length=50)
        segment = cad.next_line(segment, turn=90, length=50)


if __name__ == "__main__":
    main()
