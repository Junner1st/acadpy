import math

from acadpy import AutoCAD


with AutoCAD() as cad:
    cad.circle((0, 0), radius=40)
    cad.circle((0, 0), radius=50)
    radius = 40
    star_start = (radius, 0)

    cad.circle((40, 0), radius=10)


    # 圓周五等分，每次跳過一個頂點：0° → 144° → 288° → 72° → 216°。
    length = 2 * radius * math.sin(math.radians(72))
    second = (
        radius * math.cos(math.radians(144)),
        radius * math.sin(math.radians(144)),
    )
    segment = cad.line(star_start, second)
    for _ in range(3):
        segment, start, end = cad.next_line(segment, turn=144, length=length, return_points=True)
        cad.circle(start, radius=10)
        
    cad.circle(end, radius=10)
    cad.next_line(segment, end=star_start)

