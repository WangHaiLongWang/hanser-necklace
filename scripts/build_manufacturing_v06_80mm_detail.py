"""Generate an 80 x 56.72 mm maximum-detail manufacturing master."""

from pathlib import Path

from PIL import Image, ImageDraw

import build_manufacturing_v04 as base


ROOT = Path(__file__).resolve().parents[1]
base.VERSION = "v0.6-80mm-detail"
base.OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.6-80mm-detail"
base.NOMINAL_HEIGHT_MM = 80.0
base.MARGIN_MM = 3.0
base.TARGET_WIDTH_MM = 56.72
base.PRESERVE_ALL_DETAILS = True
base.PATH_TOLERANCE_MM = 0.02


def build() -> None:
    base.build()

    simplified = ROOT / "design" / "vector" / "manufacturing-v0.5-80mm" / "HN-PENDANT-RESULT02-PREVIEW-v0.5-80mm.png"
    detailed = base.OUT_DIR / "HN-PENDANT-RESULT02-PREVIEW-v0.6-80mm-detail.png"
    if simplified.exists() and detailed.exists():
        left = Image.open(simplified).convert("RGB")
        right = Image.open(detailed).convert("RGB")
        left.thumbnail((460, 650), Image.Resampling.NEAREST)
        right.thumbnail((460, 650), Image.Resampling.NEAREST)
        sheet = Image.new("RGB", (1080, 760), "#F4F6F8")
        sheet.paste(left, (40 + (460 - left.width) // 2, 70))
        sheet.paste(right, (580 + (460 - right.width) // 2, 70))
        draw = ImageDraw.Draw(sheet)
        draw.text((40, 28), "V0.5 - 80 mm / SIMPLIFIED", fill="#263746")
        draw.text((580, 28), "V0.6 - 80 mm / ALL DETAILS", fill="#263746")
        sheet.save(base.OUT_DIR / "HN-PENDANT-DETAIL-COMPARISON-v0.6-80mm.png")

    readme = base.OUT_DIR / "README.md"
    with readme.open("a", encoding="utf-8") as stream:
        stream.write("\n## 全细节模式\n\n")
        stream.write("- 关闭顶部手指合并、形态开闭、色块向内侵蚀和小色块删除。\n")
        stream.write("- 路径简化容差由约 0.08 mm 降至约 0.02 mm。\n")
        stream.write("- 所有源图层中可识别的金属隔断、鞋带、衣褶、发束、手指内线和五官均保留。\n")
        stream.write("- 这是一份最大细节母版；其中小于工厂实际能力的特征应由工厂在 DFM 中逐项标注，不能静默删除。\n")
        stream.write("- `HN-PENDANT-DETAIL-COMPARISON-v0.6-80mm.png` 对比同尺寸简化版与全细节版。\n")


if __name__ == "__main__":
    build()

