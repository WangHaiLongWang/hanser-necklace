"""Generate an 80 x 56.72 mm high-detail manufacturing revision."""

from pathlib import Path

from PIL import Image, ImageDraw

import build_manufacturing_v04 as base


ROOT = Path(__file__).resolve().parents[1]
base.VERSION = "v0.5-80mm"
base.OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.5-80mm"
base.NOMINAL_HEIGHT_MM = 80.0
base.MARGIN_MM = 3.0
base.TARGET_WIDTH_MM = 56.72


def build() -> None:
    # Keep the real manufacturing thresholds unchanged. Recomputing from the
    # source layers at twice the physical size preserves more source detail.
    base.build()

    v04 = ROOT / "design" / "vector" / "manufacturing-v0.4" / "HN-PENDANT-RESULT02-PREVIEW-v0.4.png"
    v05 = base.OUT_DIR / "HN-PENDANT-RESULT02-PREVIEW-v0.5-80mm.png"
    if not (v04.exists() and v05.exists()):
        return
    left = Image.open(v04).convert("RGB")
    right = Image.open(v05).convert("RGB")
    left.thumbnail((460, 650), Image.Resampling.NEAREST)
    right.thumbnail((460, 650), Image.Resampling.NEAREST)
    sheet = Image.new("RGB", (1080, 760), "#F4F6F8")
    sheet.paste(left, (40 + (460 - left.width) // 2, 70))
    sheet.paste(right, (580 + (460 - right.width) // 2, 70))
    draw = ImageDraw.Draw(sheet)
    draw.text((40, 28), "V0.4 - 40 x 28.36 mm", fill="#263746")
    draw.text((580, 28), "V0.5 - 80 x 56.72 mm", fill="#263746")
    sheet.save(base.OUT_DIR / "HN-PENDANT-SIZE-COMPARISON-v0.5-80mm.png")

    readme = base.OUT_DIR / "README.md"
    with readme.open("a", encoding="utf-8") as stream:
        stream.write("\n## 80 mm 版本说明\n\n")
        stream.write("- 本版不是把 v0.4 DXF 整体放大，而是从源语义图层以 80 mm 高度重新计算。\n")
        stream.write("- 目标最小特征仍为约 0.50 mm，目标金属隔断仍为约 0.35 mm，因此可保留比 40 mm 版本更多的原始细节。\n")
        stream.write("- 图案名义尺寸为高 80.00 mm、宽约 56.72 mm，不含吊环。\n")
        stream.write("- `HN-PENDANT-SIZE-COMPARISON-v0.5-80mm.png` 用于比较 40 mm 与 80 mm 的细节保留程度。\n")


if __name__ == "__main__":
    build()

