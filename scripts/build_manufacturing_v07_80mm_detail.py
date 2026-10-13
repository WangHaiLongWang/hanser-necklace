"""Generate v0.7 at 80 x 56.72 mm with all metal borders and pink heart."""

from pathlib import Path

from PIL import Image, ImageDraw

import build_manufacturing_v04 as base


ROOT = Path(__file__).resolve().parents[1]
base.VERSION = "v0.7-80mm-detail"
base.OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.7-80mm-detail"
base.NOMINAL_HEIGHT_MM = 80.0
base.MARGIN_MM = 3.0
base.TARGET_WIDTH_MM = 56.72
base.METAL_WEB_MM = 0.20
base.PRESERVE_ALL_DETAILS = True
base.PATH_TOLERANCE_MM = 0.02
base.SEPARATE_HEART = True
base.PALETTE["HEART"] = "#EA6278"


def build() -> None:
    base.build()

    old = ROOT / "design" / "vector" / "manufacturing-v0.6-80mm-detail" / "HN-PENDANT-RESULT02-PREVIEW-v0.6-80mm-detail.png"
    new = base.OUT_DIR / "HN-PENDANT-RESULT02-PREVIEW-v0.7-80mm-detail.png"
    if old.exists() and new.exists():
        left = Image.open(old).convert("RGB")
        right = Image.open(new).convert("RGB")
        left.thumbnail((460, 650), Image.Resampling.NEAREST)
        right.thumbnail((460, 650), Image.Resampling.NEAREST)
        sheet = Image.new("RGB", (1080, 760), "#F4F6F8")
        sheet.paste(left, (40 + (460 - left.width) // 2, 70))
        sheet.paste(right, (580 + (460 - right.width) // 2, 70))
        draw = ImageDraw.Draw(sheet)
        draw.text((40, 28), "V0.6 - PREVIOUS", fill="#263746")
        draw.text((580, 28), "V0.7 - #EA6278 HEART / ALL METAL BORDERS", fill="#263746")
        sheet.save(base.OUT_DIR / "HN-PENDANT-V07-COMPARISON.png")

    with (base.OUT_DIR / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## v0.7 专项要求\n\n")
        stream.write("- 图案尺寸：80.00 × 56.72 mm，不含吊环。\n")
        stream.write("- 毛怪爱心独立为 `FILL_HEART`，参考色 `#EA6278`。\n")
        stream.write("- 目标最小金属隔断约 0.20 mm；更宽的源金属边框保持原宽，不主动压窄。\n")
        stream.write("- 所有描边源图层中的金属边、人物五官、毛怪五官、鞋带、衣褶、发束和手指内线均保留。\n")
        stream.write("- 关闭形态开闭、色块侵蚀、小色块删除和手指合并；路径容差约 0.02 mm。\n")


if __name__ == "__main__":
    build()

