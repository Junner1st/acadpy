from acadpy import AutoCAD

def main():
    with AutoCAD() as cad:
        segment = cad.line((0, 0), (100, 0))

if __name__ == "__main__":
    main()
