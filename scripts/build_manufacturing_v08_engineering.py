"""Generate v0.8 with frozen thickness, engraving and metal-line targets."""

from pathlib import Path

import ezdxf

import build_manufacturing_v04 as base


ROOT = Path(__file__).resolve().parents[1]
base.VERSION = "v0.8-80mm-engineering"
base.OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.8-80mm-engineering"
base.NOMINAL_HEIGHT_MM = 80.0
base.MARGIN_MM = 3.0
base.TARGET_WIDTH_MM = 56.72
base.METAL_WEB_MM = 0.30
base.OUTER_BORDER_MM = 0.60
base.PRESERVE_ALL_DETAILS = True
base.PATH_TOLERANCE_MM = 0.02
base.SEPARATE_HEART = True
base.PALETTE["HEART"] = "#EA6278"

TOTAL_THICKNESS_MM = 1.90
ENGRAVE_DEPTH_MM = 0.30
BASE_REMAINING_MM = TOTAL_THICKNESS_MM - ENGRAVE_DEPTH_MM


def build_section() -> None:
    out = base.OUT_DIR
    width = 24.0
    border = 0.60
    divider = 0.30
    pocket_a_end = 11.0
    divider_end = pocket_a_end + divider
    top = TOTAL_THICKNESS_MM
    recess = top - ENGRAVE_DEPTH_MM

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="55mm" viewBox="0 0 120 55">
  <style>text{{font-family:Arial,sans-serif;font-size:3px}} .metal{{fill:#A7A7A7;stroke:#333;stroke-width:.15}} .fill{{fill:#F5F3F0;stroke:#555;stroke-width:.12}} .dim{{stroke:#C33;stroke-width:.15;fill:none}}</style>
  <text x="5" y="5">HN-PENDANT v0.8 SECTION - mm</text>
  <g transform="translate(10,18) scale(4,-4)">
    <path class="metal" d="M0,0 H{width} V{top} H{width-border} V{recess} H{divider_end} V{top} H{pocket_a_end} V{recess} H{border} V{top} H0 Z"/>
    <path class="fill" d="M{border},{recess} H{pocket_a_end} V{top} H{border} Z"/>
    <path class="fill" d="M{divider_end},{recess} H{width-border} V{top} H{divider_end} Z"/>
  </g>
  <text x="10" y="34">Total thickness: {TOTAL_THICKNESS_MM:.2f}</text>
  <text x="10" y="39">Front engraving / fill recess: {ENGRAVE_DEPTH_MM:.2f}</text>
  <text x="10" y="44">Remaining base: {BASE_REMAINING_MM:.2f}</text>
  <text x="60" y="34">Internal raised metal: {divider:.2f}</text>
  <text x="60" y="39">Outer border nominal: {border:.2f}</text>
  <text x="60" y="44">Outer border allowed: 0.50-0.70</text>
</svg>
'''
    (out / "HN-PENDANT-SECTION-v0.8.svg").write_text(svg, encoding="utf-8")

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.layers.add("SECTION_METAL", color=7)
    doc.layers.add("SECTION_RECESS", color=3)
    msp = doc.modelspace()
    metal_profile = [
        (0, 0), (width, 0), (width, top), (width-border, top),
        (width-border, recess), (divider_end, recess), (divider_end, top),
        (pocket_a_end, top), (pocket_a_end, recess), (border, recess),
        (border, top), (0, top),
    ]
    msp.add_lwpolyline(metal_profile, close=True, dxfattribs={"layer": "SECTION_METAL"})
    msp.add_lwpolyline([(border, recess), (pocket_a_end, recess), (pocket_a_end, top), (border, top)], close=True, dxfattribs={"layer": "SECTION_RECESS"})
    msp.add_lwpolyline([(divider_end, recess), (width-border, recess), (width-border, top), (divider_end, top)], close=True, dxfattribs={"layer": "SECTION_RECESS"})
    doc.saveas(out / "HN-PENDANT-SECTION-v0.8.dxf")


def build() -> None:
    base.build()
    build_section()
    with (base.OUT_DIR / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## v0.8 冻结截面参数\n\n")
        stream.write("- 总厚度：1.90 mm。\n")
        stream.write("- 正面凹刻/填色槽深度：0.30 mm。\n")
        stream.write("- 凹刻后剩余基底厚度：1.60 mm。\n")
        stream.write("- 内部凸起金属分隔线：名义 0.30 mm。\n")
        stream.write("- 外轮廓金属边：名义 0.60 mm，允许范围 0.50-0.70 mm。\n")
        stream.write("- `HN-PENDANT-SECTION-v0.8.svg/dxf` 为示意截面，工程方需转成正式带公差图纸并回签。\n")


if __name__ == "__main__":
    build()

