"""Draw a regular {18,5} star inscribed in a circle of radius 40."""

import math

from acadpy import AutoCAD


def main():
    radius = 40
    count = 18
    step = 5

    # 圓心 (0, 0)，從 (40, 0) 起步；每次沿圓周前進 5/18 圈（100°）。
    # 18 與 5 互質，因此會經過全部 18 個頂點，再回到起點。
    points = []
    for i in range(count):
        angle = math.radians(360 * ((i * step) % count) / count)
        points.append((radius * math.cos(angle), radius * math.sin(angle)))

    with AutoCAD() as cad:
        cad.circle((0, 0), radius=radius)
        segment = cad.line(points[0], points[1])
        for point in points[2:]:
            segment = cad.next_line(segment, end=point)
        cad.next_line(segment, end=points[0])


if __name__ == "__main__":
    main()
