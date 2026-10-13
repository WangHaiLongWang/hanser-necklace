"""Build the five-colour manufacturing vector draft requested for v0.2.

Palette: skin, white, hair brown, blue, and raised/base metal. The source PSD
is flattened, so semantic guards are deliberately tied to CONCEPT-v0.1.
"""

from __future__ import annotations

import html
from pathlib import Path

import cv2
import ezdxf
import numpy as np
from PIL import Image, ImageDraw

from vectorize_concept import (
    contour_paths,
    ellipse_mask,
    fill_enclosed,
    largest_component,
    polygon_mask,
    remove_small_components,
    sha256,
    svg_path,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PNG = ROOT / "design" / "image" / "result.png"
SOURCE_PSD = ROOT / "design" / "image" / "result.psd"
OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.2"

NOMINAL_HEIGHT_MM = 40.0
MARGIN_MM = 2.0
METAL_WEB_MM = 0.35
MIN_FEATURE_MM = 0.50
MIN_REGION_AREA_MM2 = 0.10

PALETTE = {
    "METAL": "#BFC5CB",
    "SKIN": "#F2BF94",
    "WHITE": "#F2F0E9",
    "HAIR": "#95502A",
    "BLUE": "#2867C5",
}


def build_silhouette(rgb: np.ndarray) -> np.ndarray:
    distance = np.linalg.norm(255.0 - rgb.astype(np.float32), axis=2)
    ink = np.where(distance > 16.0, 255, 0).astype(np.uint8)
    ink = cv2.morphologyEx(
        ink,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    result = largest_component(fill_enclosed(ink))
    return cv2.morphologyEx(
        result,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )


def masks_for_baseline(rgb: np.ndarray, silhouette: np.ndarray, px_per_mm: float) -> tuple[dict[str, np.ndarray], np.ndarray]:
    height, width = silhouette.shape
    shape = (height, width)
    r, g, b = [rgb[:, :, channel].astype(np.int16) for channel in range(3)]

    # Semantic zones are tied to the baseline hash and protect pale skin from
    # being confused with white clothing in the flattened artwork.
    face = polygon_mask(shape, [(390, 490), (575, 445), (705, 520), (735, 650), (665, 745), (535, 785), (410, 720), (365, 605)])
    top_hand = polygon_mask(shape, [(545, 225), (690, 205), (750, 240), (805, 325), (770, 382), (670, 338), (575, 330)])
    lower_hand = polygon_mask(shape, [(650, 815), (742, 795), (815, 855), (805, 970), (720, 1025), (645, 945)])
    left_leg = polygon_mask(shape, [(160, 980), (360, 985), (365, 1148), (200, 1190), (140, 1100)])
    right_leg = polygon_mask(shape, [(400, 985), (585, 1005), (630, 1145), (455, 1185)])
    skin_zones = cv2.bitwise_or(face, top_hand)
    for zone in (lower_hand, left_leg, right_leg):
        skin_zones = cv2.bitwise_or(skin_zones, zone)

    monster_zone = polygon_mask(shape, [(685, 665), (855, 660), (900, 790), (820, 875), (680, 825)])

    # Start from four paint colours. Everything else remains exposed metal.
    skin_like = (r >= 185) & (r > g + 4) & (g > b + 4)
    skin = np.where(skin_like & (skin_zones > 0) & (silhouette > 0), 255, 0).astype(np.uint8)
    # One continuous face enamel cell sits below hair/eyes. This prevents pale
    # highlights in the flattened render from fragmenting the facial fill.
    face_base = ellipse_mask(shape, (548, 635), (139, 143), -5)
    face_base = cv2.bitwise_and(face_base, face)
    face_base = cv2.bitwise_and(face_base, silhouette)
    skin = cv2.bitwise_or(skin, face_base)

    blue_like = (b >= 90) & (b > r + 20) & (b > g + 8)
    blue = np.where(blue_like & (silhouette > 0), 255, 0).astype(np.uint8)

    hair_like = (r >= 60) & (r <= 230) & (r > g + 24) & (g > b + 6)
    hair = np.where(hair_like & (silhouette > 0), 255, 0).astype(np.uint8)

    pale_like = (r >= 175) & (g >= 165) & (b >= 145)
    white = np.where(pale_like & (silhouette > 0) & (skin_zones == 0), 255, 0).astype(np.uint8)

    # Monster body is explicitly white; its red heart is reassigned to the
    # shared blue paint so the final product still uses only four paint colours.
    monster_light = (r >= 185) & (g >= 145) & (b >= 125) & (monster_zone > 0)
    monster_body = np.where(monster_light, 255, 0).astype(np.uint8)
    monster_body = cv2.morphologyEx(monster_body, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    monster_body = fill_enclosed(monster_body)
    white = cv2.bitwise_or(white, monster_body)

    monster_heart = (r >= 190) & (r > g + 45) & (b > g - 10) & (monster_zone > 0)
    heart = np.where(monster_heart, 255, 0).astype(np.uint8)
    heart = cv2.morphologyEx(heart, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    blue = cv2.bitwise_or(blue, heart)

    # Simplify the top-hand skin mass: close tiny finger-joint gaps and remove
    # narrow protrusions while keeping the pointing silhouette.
    top_skin = cv2.bitwise_and(skin, top_hand)
    close_px = max(3, int(round(0.65 * px_per_mm)) | 1)
    open_px = max(3, int(round(0.16 * px_per_mm)) | 1)
    top_skin = cv2.morphologyEx(top_skin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px, close_px)))
    top_skin = cv2.morphologyEx(top_skin, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_px, open_px)))
    skin[top_hand > 0] = 0
    skin = cv2.bitwise_or(skin, top_skin)

    # Raised metal details: whole eyes + eyebrows for the character; separated
    # eyes and nose/mouth for the monster. These are explicit closed shapes.
    metal_detail = np.zeros(shape, dtype=np.uint8)
    for center, axes, angle in [((486, 607), (21, 31), -8), ((619, 651), (21, 31), -8)]:
        metal_detail = cv2.bitwise_or(metal_detail, ellipse_mask(shape, center, axes, angle))
    for points in [
        [(455, 550), (504, 552), (507, 559), (456, 558)],
        [(590, 589), (638, 594), (636, 602), (589, 597)],
    ]:
        metal_detail = cv2.bitwise_or(metal_detail, polygon_mask(shape, points))

    # Monster facial features are deliberately separate, not one merged cell.
    for center in [(746, 753), (799, 755)]:
        metal_detail = cv2.bitwise_or(metal_detail, ellipse_mask(shape, center, (7, 11), 0))
    metal_detail = cv2.bitwise_or(metal_detail, ellipse_mask(shape, (773, 774), (5, 5), 0))  # nose
    metal_detail = cv2.bitwise_or(metal_detail, ellipse_mask(shape, (773, 788), (13, 5), 0))  # mouth
    metal_detail = cv2.bitwise_and(metal_detail, silhouette)

    # Metal detail replaces paint, rather than sitting on top of an unbroken
    # enamel area. This expresses the actual raised separator geometry.
    for mask in (skin, white, hair, blue):
        mask[metal_detail > 0] = 0

    # Resolve paint overlap with deterministic visual priority: blue accents
    # and hair sit above the continuous face cell; skin sits above shared white.
    hair[blue > 0] = 0
    skin[(hair > 0) | (blue > 0)] = 0
    white[(skin > 0) | (blue > 0) | (hair > 0)] = 0
    return {"SKIN": skin, "WHITE": white, "HAIR": hair, "BLUE": blue}, metal_detail


def cleaned_regions(raw_masks: dict[str, np.ndarray], silhouette: np.ndarray, px_per_mm: float, metal_detail: np.ndarray) -> dict[str, np.ndarray]:
    half_web_px = max(1, int(round((METAL_WEB_MM / 2.0) * px_per_mm)))
    inset = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half_web_px + 1, 2 * half_web_px + 1))
    clean_px = max(3, int(round(MIN_FEATURE_MM * px_per_mm * 0.18)) | 1)
    clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (clean_px, clean_px))
    min_area_px = MIN_REGION_AREA_MM2 * px_per_mm * px_per_mm
    result: dict[str, np.ndarray] = {}
    for name, raw in raw_masks.items():
        mask = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, clean)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, clean)
        mask = cv2.erode(mask, inset)
        mask = remove_small_components(mask, min_area_px)
        mask = cv2.bitwise_and(mask, silhouette)
        mask[metal_detail > 0] = 0
        result[name] = mask
    return result


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE_PNG).convert("RGB")
    rgb = np.asarray(image)
    silhouette = build_silhouette(rgb)
    ys, xs = np.where(silhouette > 0)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    px_per_mm = (y1 - y0) / NOMINAL_HEIGHT_MM
    width_mm = (x1 - x0) / px_per_mm
    canvas_w_mm = width_mm + 2 * MARGIN_MM
    canvas_h_mm = NOMINAL_HEIGHT_MM + 2 * MARGIN_MM

    raw_masks, metal_detail = masks_for_baseline(rgb, silhouette, px_per_mm)
    masks = cleaned_regions(raw_masks, silhouette, px_per_mm, metal_detail)
    base_paths = contour_paths(silhouette, x0, y0, px_per_mm)
    detail_paths = contour_paths(metal_detail, x0, y0, px_per_mm)
    region_paths = {name: contour_paths(mask, x0, y0, px_per_mm) for name, mask in masks.items()}

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w_mm:.3f}mm" height="{canvas_h_mm:.3f}mm" viewBox="0 0 {canvas_w_mm:.3f} {canvas_h_mm:.3f}">',
        '  <title>HN Pendant five-colour manufacturing draft v0.2</title>',
        '  <desc>Four flat paint colours plus raised 316L metal. Nominal artwork height 40 mm. DFM required.</desc>',
        f'  <g id="CUT_OUTER_METAL" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(base_paths))}"/></g>',
    ]
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        svg.append(f'  <g id="FILL_{name}" fill="{PALETTE[name]}" fill-rule="evenodd"><path d="{html.escape(svg_path(region_paths[name]))}"/></g>')
    svg.append(f'  <g id="RAISED_METAL_DETAILS" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(detail_paths))}"/></g>')
    svg.append('</svg>')
    svg_file = OUT_DIR / "HN-PENDANT-5COLOR-v0.2.svg"
    svg_file.write_text("\n".join(svg) + "\n", encoding="utf-8")

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    layer_colours = {
        "CUT_OUTER": "#BFC5CB",
        "FILL_SKIN": PALETTE["SKIN"],
        "FILL_WHITE": PALETTE["WHITE"],
        "FILL_HAIR": PALETTE["HAIR"],
        "FILL_BLUE": PALETTE["BLUE"],
        "RAISED_METAL": PALETTE["METAL"],
    }
    for aci, (layer_name, colour) in enumerate(layer_colours.items(), start=1):
        layer = doc.layers.add(layer_name, color=((aci - 1) % 7) + 1)
        layer.rgb = ezdxf.colors.RGB.from_hex(colour)
    msp = doc.modelspace()

    def add(paths: list[list[tuple[float, float]]], layer: str) -> None:
        for points in paths:
            msp.add_lwpolyline([(x, canvas_h_mm - y) for x, y in points], close=True, dxfattribs={"layer": layer})

    add(base_paths, "CUT_OUTER")
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        add(region_paths[name], f"FILL_{name}")
    add(detail_paths, "RAISED_METAL")
    dxf_file = OUT_DIR / "HN-PENDANT-5COLOR-v0.2.dxf"
    doc.saveas(dxf_file)

    scale = 14
    preview = Image.new("RGB", (round(canvas_w_mm * scale), round(canvas_h_mm * scale)), "white")
    draw = ImageDraw.Draw(preview)

    def draw_paths(paths: list[list[tuple[float, float]]], fill: str) -> None:
        for points in paths:
            if len(points) >= 3:
                draw.polygon([(round(x * scale), round(y * scale)) for x, y in points], fill=fill)

    draw_paths(base_paths, PALETTE["METAL"])
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        draw_paths(region_paths[name], PALETTE[name])
    draw_paths(detail_paths, PALETTE["METAL"])
    preview_file = OUT_DIR / "HN-PENDANT-5COLOR-PREVIEW-v0.2.png"
    preview.save(preview_file)

    # Enlarged production-detail review for face, upper hand, and monster.
    detail = Image.new("RGB", (1120, 520), "#F4F6F8")
    detail_draw = ImageDraw.Draw(detail)
    detail_draw.text((30, 20), "FACE / RAISED METAL EYES", fill="#263746")
    detail_draw.text((405, 20), "TOP HAND SIMPLIFICATION", fill="#263746")
    detail_draw.text((780, 20), "MONSTER / METAL FEATURES / BLUE HEART", fill="#263746")
    source_boxes = [(390, 470, 705, 790), (535, 205, 810, 385), (675, 650, 900, 880)]
    for index, box in enumerate(source_boxes):
        px0 = round(((box[0] - x0) / px_per_mm + MARGIN_MM) * scale)
        py0 = round(((box[1] - y0) / px_per_mm + MARGIN_MM) * scale)
        px1 = round(((box[2] - x0) / px_per_mm + MARGIN_MM) * scale)
        py1 = round(((box[3] - y0) / px_per_mm + MARGIN_MM) * scale)
        crop = preview.crop((max(0, px0), max(0, py0), min(preview.width, px1), min(preview.height, py1)))
        factor = min(320 / crop.width, 420 / crop.height)
        crop = crop.resize((max(1, round(crop.width * factor)), max(1, round(crop.height * factor))), Image.Resampling.NEAREST)
        x_position = 30 + index * 375 + (320 - crop.width) // 2
        detail.paste(crop, (x_position, 70))
    detail.save(OUT_DIR / "HN-PENDANT-5COLOR-DETAILS-v0.2.png")

    comparison = Image.new("RGB", (1100, 760), "#F4F6F8")
    source_crop = image.crop((x0, y0, x1, y1))
    source_crop.thumbnail((470, 650), Image.Resampling.LANCZOS)
    vector_copy = preview.copy()
    vector_copy.thumbnail((470, 650), Image.Resampling.NEAREST)
    comparison.paste(source_crop, (40 + (470 - source_crop.width) // 2, 70))
    comparison.paste(vector_copy, (590 + (470 - vector_copy.width) // 2, 70))
    cdraw = ImageDraw.Draw(comparison)
    cdraw.text((40, 28), "SOURCE CONCEPT", fill="#263746")
    cdraw.text((590, 28), "V0.2: 4 PAINTS + RAISED METAL", fill="#263746")
    comparison.save(OUT_DIR / "HN-PENDANT-5COLOR-COMPARISON-v0.2.png")

    stats = []
    for name, mask in masks.items():
        area = float((mask > 0).sum()) / (px_per_mm * px_per_mm)
        stats.append((name, PALETTE[name], len(region_paths[name]), area))
    metal_area = float((silhouette > 0).sum()) / (px_per_mm * px_per_mm) - sum(item[3] for item in stats)

    readme = [
        "# HN-PENDANT 五色制造矢量草案 v0.2",
        "",
        "生成日期：2026-10-13",
        "",
        "## 颜色结构",
        "",
        "本版严格使用四种填色加一种凸起金属色：",
        "",
        "| 层 | 用途 | 参考色 |",
        "|---|---|---|",
        f"| FILL_SKIN | 顶部手、脸、下方手及腿部露肤 | `{PALETTE['SKIN']}` |",
        f"| FILL_WHITE | 衣服、鞋、袜套、毛怪主体 | `{PALETTE['WHITE']}` |",
        f"| FILL_HAIR | 头发 | `{PALETTE['HAIR']}` |",
        f"| FILL_BLUE | 裤子、蝴蝶结、蓝色装饰、毛怪爱心 | `{PALETTE['BLUE']}` |",
        f"| CUT_OUTER / RAISED_METAL | 底板、分隔网、人物眼睛/眉毛、毛怪五官 | `{PALETTE['METAL']}` |",
        "",
        "## 文件",
        "",
        "- `HN-PENDANT-5COLOR-v0.2.svg`：建议作为后续人工细化母版。",
        "- `HN-PENDANT-5COLOR-v0.2.dxf`：毫米单位的分层封闭多段线，用于 CAD/DFM。",
        "- `HN-PENDANT-5COLOR-PREVIEW-v0.2.png`：DXF/SVG 同源色块预览。",
        "- `HN-PENDANT-5COLOR-COMPARISON-v0.2.png`：效果图与制造草案对照。",
        "- `HN-PENDANT-5COLOR-DETAILS-v0.2.png`：脸部金属眼、顶部手和毛怪细节放大检查图。",
        "",
        "## 几何基线",
        "",
        f"- 图案名义高度 `{NOMINAL_HEIGHT_MM:.2f} mm`，宽度 `{width_mm:.2f} mm`，不含吊环。",
        f"- 目标金属分隔宽度约 `{METAL_WEB_MM:.2f} mm`。",
        f"- 目标最小保留特征约 `{MIN_FEATURE_MM:.2f} mm`。",
        f"- 输入 PNG SHA-256：`{sha256(SOURCE_PNG)}`。",
        f"- 输入 PSD SHA-256：`{sha256(SOURCE_PSD)}`。",
        "",
        "## 本版简化",
        "",
        "- 顶部手指通过形态闭合和开运算合并细小指缝，保留主要指向轮廓。",
        "- 人物两只完整眼睛与两条眉毛改为凸起金属块，不保留瞳孔、高光或虹膜分色。",
        "- 鞋带、衣褶、发丝高光和软阴影被合并到四个基础色块或金属隔断。",
        "- 毛怪两眼、鼻、嘴分别建立独立凸起金属闭合区域；小爱心统一改为蓝色。",
        "",
        "## 后续自己细化的推荐流程",
        "",
        "1. 复制 SVG 为新版本，例如 `HN-PENDANT-5COLOR-v0.3.svg`，不要覆盖 v0.2。",
        "2. 在 Illustrator、Inkscape 或 Affinity Designer 中按图层编辑；只调整对应 `FILL_*` 或 `RAISED_METAL_DETAILS` 的闭合路径。",
        "3. 使用节点工具减少锯齿和尖角；不要用自由画笔制造大量小节点。",
        "4. 保持每个填色区闭合、无自相交、无重叠，并让相邻色块之间留出连续金属分隔。",
        "5. 在 1:1 的 40 mm 视图检查眼睛、眉毛、顶部手、毛怪五官和蓝色爱心是否清楚。",
        "6. 使用 `python scripts/svg_layers_to_dxf.py <输入.svg> <输出.dxf>` 把修改后的分层 SVG 重新导出为毫米 DXF。",
        "7. 用 CAD 打开 DXF，确认单位为 mm、所有多段线闭合、图层名称正确，再交工厂 DFM。",
        "8. 工厂确认最小隔断/色块后，再做最终偏置；35/45 mm 版本不能直接整体缩放而不复查最小特征。",
        "",
        "## 色块统计",
        "",
        "| 色层 | 闭合轮廓数 | 估算面积 mm² |",
        "|---|---:|---:|",
    ]
    readme.extend(f"| FILL_{name} | {count} | {area:.2f} |" for name, _, count, area in stats)
    readme.append(f"| METAL（含底边/隔断估算） | {len(detail_paths)} 个细节轮廓 | {metal_area:.2f} |")
    readme.extend([
        "",
        "本版仍是 DFM 草案：吊环、背面、厚度、凹槽深度、毛怪转轴和公差尚未定义，禁止直接开模。",
        "",
    ])
    (OUT_DIR / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"artwork={width_mm:.3f}x{NOMINAL_HEIGHT_MM:.3f}mm")
    print(svg_file)
    print(dxf_file)


if __name__ == "__main__":
    build()

