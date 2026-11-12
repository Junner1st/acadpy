# acadpy

輕量 Python AutoCAD 繪圖函式庫，透過 `pywin32` 直接呼叫 ActiveX API。這個套件會自動連接已開啟的 Windows AutoCAD 2027，並且繪圖。

## 安裝

在專案根目錄執行（Python 3.10 以上）：

```powershell
uv venv --seed --python 3.12
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

`pyproject.toml` 是標準 setuptools 套件設定，供 pip 安裝與建置使用。

## 使用

先開啟 AutoCAD 2027 與要繪圖的圖檔，再執行：

```python
from acadpy import AutoCAD

with AutoCAD() as cad:
    line = cad.line((0, 0, 0), (100, 100, 50))
    cad.circle((0, 0, 0), radius=50)
    cad.arc((0, 0, 0), radius=50, start=0, end=90)
    cad.point((10, 20, 30))
    cad.rectangle((0, 0), (100, 50))
    cad.triangle((0, 0), (100, 0), (50, 80))
    cad.polyline([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True)
    cad.polyline3d([(0, 0, 0), (50, 0, 50), (50, 50, 20)])
    line.Color = 1
```

亦可直接使用 `cad = AutoCAD()`，結束時呼叫 `cad.close()` 釋放 COM。`close()` 不會關閉 AutoCAD 或圖檔。請在建立連線的同一執行緒操作並釋放連線，且在使用回傳的 COM 物件期間保持連線開啟。

完整範例：`python examples/basic.py`。範例會在目前圖檔新增八個物件。

## API

所有繪圖方法皆回傳新建立的 AutoCAD COM 物件，並可使用 `layer="既有圖層名稱"`。未指定圖層時使用目前圖層；指定圖層不存在會失敗，不會自動新增圖層或改變 ActiveLayer。可由 `cad.doc.Layers.Add("Demo")` 自行建立圖層。

| 方法 | 輸入及建立物件 |
| --- | --- |
| `line(start, end, *, layer=None, return_points=False)` | WCS 起終點，`AcDbLine` |
| `next_line(previous, end=None, *, angle=None, turn=None, length=None, layer=None, return_points=False)` | 從上一條 LINE 的終點連續畫下一段 `AcDbLine` |
| `circle(center, radius, *, layer=None)` | WCS 圓心、正半徑，`AcDbCircle` |
| `arc(center, radius, start, end, *, layer=None)` | **度數**起終角，逆時針，`AcDbArc` |
| `point(position, *, layer=None)` | WCS 座標，`AcDbPoint` |
| `rectangle(corner1, corner2, *, elevation=0, layer=None)` | 兩個二維對角點，封閉 `AcDbPolyline` |
| `triangle(p1, p2, p3, *, elevation=0, layer=None)` | 三個不共線的二維頂點，封閉 `AcDbPolyline` |
| `polyline(points, closed=False, *, elevation=0, layer=None)` | 嚴格二維頂點，`AcDbPolyline`（LWPOLYLINE） |
| `polyline3d(points, closed=False, *, layer=None)` | 嚴格三維 WCS 頂點，`AcDb3dPolyline` |

`line`、`circle`、`arc`、`point` 的座標可為 `(x, y)` 或 `(x, y, z)`，二維輸入補 Z=0。圓與圓弧平行於 WCS XY；角度以 +X 為零度，正規化到 `[0, 360)`，例如 350→10 會跨越零度。起終角相同（模 360）會報錯；整圓請用 `circle()`。

`polyline()`、`rectangle()` 與 `triangle()` 明確設定 Normal=(0,0,1) 與 Elevation，讓 OCS XY 等於 WCS XY，不受目前 UCS 或圖面 ELEVATION 影響。`triangle()` 建立三角形外框，頂點可以順時針或逆時針排列，重複或共線會拋出 `ValueError`。任意 XYZ 頂點須用 `polyline3d()`，不會默默捨棄 Z。第一版不提供任意法向量的平面折線。

開放折線至少兩個不同頂點，封閉折線至少三個不同頂點；`closed` 必須是布林值。封閉時可重複首點作為末點，函式會移除該重複點並設定 `Closed=True`。拒絕相鄰重複頂點、非有限數值、非正半徑、零長線與零面積矩形。這是基本幾何驗證，不檢查折線自交。

`AutoCAD(document=None)` 固定綁定連線時的 ActiveDocument；亦可傳入已開啟圖檔名稱 `AutoCAD(document="Drawing1.dwg")`。後續手動切換作用中圖檔不會改變繪圖目標。`cad.app`、`cad.doc`、`cad.modelspace` 可存取底層物件。連線失敗拋出 `AutoCADConnectionError`，參數錯誤拋出 `ValueError`，AutoCAD 執行錯誤保留原始 COM 例外。多個 AutoCAD 2027 程序時，COM 會使用 ROT 中先找到的實例；需要確定目標時請保留單一程序。

`line()` 與 `next_line()` 可指定 `return_points=True`，同時取得物件與新線段的起終點：

```python
segment, start, end = cad.line((0, 0), (100, 0), return_points=True)
# start == (0.0, 0.0, 0.0)，end == (100.0, 0.0, 0.0)
segment, start, end = cad.next_line(segment, turn=90, length=50, return_points=True)
# start == (100.0, 0.0, 0.0)，end 約為 (100.0, 50.0, 0.0)
```

`start`、`end` 為建立時的 WCS `(x, y, z)` tuple；後續修改物件不會更新這些座標。連續畫線時將解包後的 `segment` 傳入下一次呼叫。省略此選項仍只回傳物件。

## 二維連續畫線

`next_line()` 從指定 LINE 的終點繼續畫，回傳新 LINE。將回傳值傳給下一次呼叫即可連續畫線，每一段都是獨立物件：

```python
with AutoCAD() as cad:
    segment = cad.line((0, 0), (100, 0))
    segment = cad.next_line(segment, end=(100, 100))       # 絕對 XY 端點
    segment = cad.next_line(segment, angle=180, length=50) # 絕對方向：向左
    segment = cad.next_line(segment, turn=-90, length=50)  # 相對右轉 90 度
```

三種模式每次只能擇一：

| 輸入 | 意義 |
| --- | --- |
| `end=(x, y)` | 下一個端點的絕對 WCS XY，不搭配 `length` |
| `angle=角度, length=線長` | 以目前終點為起點，依 WCS 絕對方向與線長計算下一端點；0° 向右、90° 向上 |
| `turn=轉角, length=線長` | 以前一段「起點→終點」的方向為基準旋轉，並依線長計算下一端點 |

角度皆為度數，正值逆時針、負值順時針，允許超過一圈。`turn=0` 直行、`turn=90` 左轉、`turn=-90` 右轉；轉角指行進方向的變化，不是多邊形內角。角度模式的線長必須大於零。

前一段須為平行 WCS XY 的非零 LINE，新線沿用它的 Z 高度；`end` 接受 `(x, y)` 或同高度的 `(x, y, z)`，可直接使用 `return_points=True` 回傳的座標。若指定 Z 不同則報錯，不會默默捨棄 Z。三種模式均不受目前 UCS 或 AutoCAD 角度顯示設定影響。`layer` 和其他繪圖方法相同，省略時使用目前圖層。完整範例：`python examples/connected_lines.py`。

## 測試

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q

# 實機測試：先開啟 AutoCAD 2027；新增獨立測試圖檔，結束時不儲存並還原原作用中圖檔
$env:ACADPY_INTEGRATION = "1"
python -m pytest tests/test_acadpy_integration.py -q
Remove-Item Env:ACADPY_INTEGRATION
```

預設跳過實機測試。單元測試不需 AutoCAD，涵蓋參數驗證、COM 呼叫、圖層與連線生命週期；實機測試比對物件類型、座標、半徑、角度、封閉性與圖層。

## ActiveX 參考

- [Application](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-ActiveX-Reference/files/GUID-0225808C-8C91-407B-990C-15AB966FFFA8.htm)
- [AddLightWeightPolyline（OCS 與標高）](https://help.autodesk.com/cloudhelp/2019/CHT/AutoCAD-ActiveX-Reference/files/GUID-2003E0A1-5FB5-48A7-8CDA-2804F7C61C1C.htm)
- [Add3DPoly（WCS）](https://help.autodesk.com/cloudhelp/2023/KOR/AutoCAD-ActiveX-Reference/files/GUID-21D7283A-552F-4DD8-BB4D-AEA1632186B9.htm)
- [AddArc（底層弧度）](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-ActiveX-Reference/files/GUID-864A7E1F-D221-4C83-A4DB-F60C8E56FED6.htm)
