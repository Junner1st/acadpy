from acadpy import AutoCAD


def main():
    with AutoCAD() as cad:
        cad.line((0, 0, 0), (100, 100, 50))
        cad.circle((0, 0, 0), radius=50)
        cad.arc((150, 0, 0), radius=50, start=0, end=90)
        cad.point((10, 20, 30))
        cad.rectangle((200, 0), (300, 50))
        cad.triangle((200, 100), (300, 100), (250, 180))
        cad.polyline([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True)
        cad.polyline3d([(0, 150, 0), (50, 150, 50), (50, 200, 20)])


if __name__ == "__main__":
    main()
