from acadpy import AutoCAD

def main():
    with AutoCAD() as cad:
        cad.circle((0, 0), radius=50)


if __name__ == "__main__":
    main()
