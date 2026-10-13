"""Build a manufacturable vector draft from the flattened CONCEPT-v0.1 artwork.

This is a deterministic engineering simplification, not a general image tracer.
It produces a nominal 40 mm artwork master with a metal base, inset closed colour
regions, an SVG preview source, and a layered DXF for factory DFM review.
"""

from __future__ import annotations

import hashlib
import html
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import ezdxf
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design" / "image" / "result.png"
OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.1"

NOMINAL_HEIGHT_MM = 40.0
MARGIN_MM = 2.0
METAL_WEB_MM = 0.35
MIN_FEATURE_MM = 0.50
MIN_REGION_AREA_MM2 = 0.10
CURVE_TOLERANCE_MM = 0.08


@dataclass(frozen=True)
class Colour:
    name: str
    source_rgb: tuple[int, int, int]
    output_hex: str


# Source colours are classification anchors. Output colours are flat production
# references and intentionally remove gradients and soft illustration shading.
COLOURS = [
    Colour("METAL", (185, 190, 195), "#BFC5CB"),
    Colour("BLACK", (22, 10, 7), "#30231F"),
    Colour("WHITE", (251, 242, 228), "#F2F0E9"),
    Colour("GRAY", (174, 183, 190), "#AEB8C1"),
    Colour("BLUE", (20, 73, 188), "#2867C5"),
    Colour("DARK_BLUE", (14, 54, 149), "#16478E"),
    Colour("HAIR", (155, 82, 32), "#95502A"),
    Colour("HAIR_DARK", (94, 38, 10), "#68351F"),
    Colour("SKIN", (248, 193, 146), "#F2BF94"),
    Colour("SKIN_SHADOW", (222, 156, 96), "#DC926E"),
    Colour("GOLD", (237, 167, 85), "#E1A62F"),
    Colour("CREAM", (253, 239, 231), "#F1D7BB"),
    Colour("PINK", (248, 188, 161), "#E8868D"),
    Colour("RED", (235, 85, 99), "#DE505D"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fill_enclosed(mask: np.ndarray) -> np.ndarray:
    """Fill white-looking enclosed areas while preserving open negative spaces."""
    padded = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    inv = cv2.bitwise_not(padded)
    flood = inv.copy()
    flood_mask = np.zeros((flood.shape[0] + 2, flood.shape[1] + 2), np.uint8)
    cv2.floodFill(flood, flood_mask, (0, 0), 128)
    enclosed = np.where(flood == 255, 255, 0).astype(np.uint8)
    return cv2.bitwise_or(padded, enclosed)[1:-1, 1:-1]


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        raise RuntimeError("No artwork component detected")
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == index, 255, 0).astype(np.uint8)


def remove_small_components(mask: np.ndarray, min_area_px: float) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= min_area_px:
            out[labels == index] = 255
    return out


def polygon_mask(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.asarray(points, dtype=np.int32)], 255)
    return mask


def ellipse_mask(shape: tuple[int, int], center: tuple[int, int], axes: tuple[int, int], angle: float = 0) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.ellipse(mask, center, axes, angle, 0, 360, 255, -1)
    return mask


def apply_semantic_overrides(rgb: np.ndarray, labels: np.ndarray, silhouette: np.ndarray) -> np.ndarray:
    """Protect critical anatomy and manufacturing colours in this exact baseline.

    The source PSD is flattened and pale skin is nearly identical to white cloth.
    These spatial guards prevent face/hands/legs and small irises from vanishing
    during colour quantisation. Coordinates are tied to CONCEPT-v0.1.
    """
    out = labels.copy()
    height, width = silhouette.shape
    shape = (height, width)
    index = {colour.name: i for i, colour in enumerate(COLOURS)}
    r, g, b = [rgb[:, :, channel].astype(np.int16) for channel in range(3)]

    skin_zones = np.zeros(shape, dtype=np.uint8)
    zones = [
        # Face, upper hand, lower hand, left leg, right leg.
        [(390, 490), (575, 445), (705, 520), (735, 650), (665, 745), (535, 785), (410, 720), (365, 605)],
        [(555, 235), (690, 220), (740, 250), (795, 325), (760, 370), (675, 328), (585, 325)],
        [(665, 825), (735, 810), (805, 865), (795, 960), (730, 1015), (660, 950)],
        [(170, 990), (355, 995), (355, 1145), (205, 1185), (150, 1110)],
        [(405, 990), (575, 1010), (620, 1135), (465, 1170)],
    ]
    for points in zones:
        skin_zones = cv2.bitwise_or(skin_zones, polygon_mask(shape, points))

    eye_left = ellipse_mask(shape, (485, 605), (42, 55), -8)
    eye_right = ellipse_mask(shape, (620, 650), (43, 55), -8)
    eye_zones = cv2.bitwise_or(eye_left, eye_right)
    monster_zone = polygon_mask(shape, [(690, 675), (855, 670), (890, 805), (805, 865), (690, 815)])

    # Hair is one durable fill family. Dark ink remains metal; warm mid-tones
    # become hair so highlights do not fragment into tiny manufacturing cells.
    hair_like = (r >= 65) & (r <= 225) & (r > g + 28) & (g > b + 8)
    out[hair_like & (silhouette > 0)] = index["HAIR"]

    # Light warm pixels inside anatomical zones become a single skin fill.
    skin_like = (r >= 190) & (r > g + 4) & (g > b + 4)
    skin_mask = skin_like & (skin_zones > 0) & (eye_zones == 0) & (silhouette > 0)
    out[skin_mask] = index["SKIN"]

    # Preserve white eye sclera and gold irises as separate closed cells.
    sclera_like = (r >= 205) & (g >= 195) & (b >= 175)
    out[sclera_like & (eye_zones > 0) & (silhouette > 0)] = index["WHITE"]
    gold_like = (r >= 125) & (g >= 65) & (g <= 205) & (b <= 125) & (r > g + 15)
    out[gold_like & (eye_zones > 0) & (silhouette > 0)] = index["GOLD"]

    # The monster is cream, with its original pink/red facial accents retained.
    cream_like = (r >= 205) & (g >= 180) & (b >= 155)
    out[cream_like & (monster_zone > 0) & (silhouette > 0)] = index["CREAM"]
    pink_like = (r >= 210) & (g >= 80) & (g <= 205) & (b >= 75) & (b <= 190)
    out[pink_like & (monster_zone > 0) & (silhouette > 0)] = index["PINK"]

    # Consolidate remaining near-white illustration tones into manufacturable
    # white, and neutral mid-tones into one shoe/shadow gray.
    near_white = (r >= 205) & (g >= 195) & (b >= 175)
    out[near_white & (silhouette > 0) & ~skin_mask & ~((monster_zone > 0) & cream_like)] = index["WHITE"]
    neutral_gray = (np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b]) < 24) & (r >= 80) & (r < 205)
    out[neutral_gray & (silhouette > 0)] = index["GRAY"]
    return out


def contour_paths(mask: np.ndarray, x0: int, y0: int, px_per_mm: float) -> list[list[tuple[float, float]]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    paths: list[list[tuple[float, float]]] = []
    epsilon_px = CURVE_TOLERANCE_MM * px_per_mm
    for contour in contours:
        if abs(cv2.contourArea(contour)) < 3:
            continue
        approx = cv2.approxPolyDP(contour, epsilon_px, True)
        if len(approx) < 3:
            continue
        points = [
            ((float(p[0][0]) - x0) / px_per_mm + MARGIN_MM,
             (float(p[0][1]) - y0) / px_per_mm + MARGIN_MM)
            for p in approx
        ]
        paths.append(points)
    return paths


def svg_path(paths: list[list[tuple[float, float]]]) -> str:
    chunks: list[str] = []
    for points in paths:
        if not points:
            continue
        chunks.append(f"M {points[0][0]:.3f},{points[0][1]:.3f}")
        chunks.extend(f"L {x:.3f},{y:.3f}" for x, y in points[1:])
        chunks.append("Z")
    return " ".join(chunks)


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE).convert("RGB")
    rgb = np.asarray(image)

    # Detect ink/colour against the almost-white raster background, bridge tiny
    # antialiasing gaps, then fill only enclosed white regions of the character.
    distance = np.linalg.norm(255.0 - rgb.astype(np.float32), axis=2)
    ink = np.where(distance > 16.0, 255, 0).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    silhouette = largest_component(fill_enclosed(ink))
    silhouette = cv2.morphologyEx(silhouette, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

    ys, xs = np.where(silhouette > 0)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    art_h_px = y1 - y0
    art_w_px = x1 - x0
    px_per_mm = art_h_px / NOMINAL_HEIGHT_MM
    width_mm = art_w_px / px_per_mm
    canvas_w_mm = width_mm + 2 * MARGIN_MM
    canvas_h_mm = NOMINAL_HEIGHT_MM + 2 * MARGIN_MM

    source_palette = np.array([c.source_rgb for c in COLOURS], dtype=np.uint8).reshape((-1, 1, 3))
    source_lab = cv2.cvtColor(source_palette, cv2.COLOR_RGB2LAB).reshape((-1, 3)).astype(np.float32)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    distances = ((lab[:, :, None, :] - source_lab[None, None, :, :]) ** 2).sum(axis=3)
    labels = distances.argmin(axis=2)
    labels = apply_semantic_overrides(rgb, labels, silhouette)

    half_web_px = max(1, int(round((METAL_WEB_MM / 2.0) * px_per_mm)))
    min_feature_px = max(2, int(round(MIN_FEATURE_MM * px_per_mm)))
    min_area_px = MIN_REGION_AREA_MM2 * px_per_mm * px_per_mm
    inset_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half_web_px + 1, 2 * half_web_px + 1))
    cleanup_size = max(3, int(round(min_feature_px * 0.20)) | 1)
    cleanup_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cleanup_size, cleanup_size))

    base_paths = contour_paths(silhouette, x0, y0, px_per_mm)
    region_paths: dict[str, list[list[tuple[float, float]]]] = {}
    region_masks: dict[str, np.ndarray] = {}

    for index, colour in enumerate(COLOURS):
        if colour.name == "METAL":
            continue
        region = np.where((labels == index) & (silhouette > 0), 255, 0).astype(np.uint8)
        region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, cleanup_kernel)
        # Avoid opening critical facial/anatomical cells out of existence.
        if colour.name not in {"BLACK", "SKIN", "GOLD", "CREAM", "PINK", "RED"}:
            region = cv2.morphologyEx(region, cv2.MORPH_OPEN, cleanup_kernel)
        if colour.name in {"BLACK", "GOLD", "PINK", "RED"}:
            critical_px = max(1, int(round(0.10 * px_per_mm)))
            critical_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * critical_px + 1, 2 * critical_px + 1))
            region = cv2.erode(region, critical_kernel)
            region = remove_small_components(region, min_area_px * 0.35)
        else:
            region = cv2.erode(region, inset_kernel)
            region = remove_small_components(region, min_area_px)
        region_masks[colour.name] = region
        region_paths[colour.name] = contour_paths(region, x0, y0, px_per_mm)

    # SVG: base metal creates both the cut outline and separator network.
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w_mm:.3f}mm" height="{canvas_h_mm:.3f}mm" viewBox="0 0 {canvas_w_mm:.3f} {canvas_h_mm:.3f}">',
        '  <title>HN Pendant manufacturing vector draft v0.1</title>',
        '  <desc>Nominal 40 mm artwork height. Closed flat colour regions inset into a 316L metal base. DFM required.</desc>',
        f'  <g id="CUT_OUTER_METAL" fill="{COLOURS[0].output_hex}" fill-rule="evenodd">',
        f'    <path d="{html.escape(svg_path(base_paths))}"/>',
        '  </g>',
    ]
    for colour in COLOURS[1:]:
        path_data = svg_path(region_paths[colour.name])
        if not path_data:
            continue
        svg_lines.extend([
            f'  <g id="FILL_{colour.name}" fill="{colour.output_hex}" fill-rule="evenodd">',
            f'    <path d="{html.escape(path_data)}"/>',
            '  </g>',
        ])
    svg_lines.append('</svg>')
    svg_path_file = OUT_DIR / "HN-PENDANT-COLOR-v0.1.svg"
    svg_path_file.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")

    # DXF: millimetre coordinates; Y is flipped to conventional CAD orientation.
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.layers.add("CUT_OUTER", color=7)
    for aci, colour in enumerate(COLOURS[1:], start=1):
        layer = doc.layers.add(f"FILL_{colour.name}", color=((aci - 1) % 7) + 1)
        layer.rgb = ezdxf.colors.RGB.from_hex(colour.output_hex)
    msp = doc.modelspace()

    def add_polylines(paths: list[list[tuple[float, float]]], layer: str) -> None:
        for points in paths:
            cad_points = [(x, canvas_h_mm - y) for x, y in points]
            msp.add_lwpolyline(cad_points, close=True, dxfattribs={"layer": layer})

    add_polylines(base_paths, "CUT_OUTER")
    for colour in COLOURS[1:]:
        add_polylines(region_paths[colour.name], f"FILL_{colour.name}")
    dxf_path = OUT_DIR / "HN-PENDANT-OUTLINE-v0.1.dxf"
    doc.saveas(dxf_path)

    # Raster preview at 12 px/mm, directly from the same manufacturing masks.
    preview_scale = 12
    preview_w = int(round(canvas_w_mm * preview_scale))
    preview_h = int(round(canvas_h_mm * preview_scale))
    preview = Image.new("RGB", (preview_w, preview_h), "white")
    draw = ImageDraw.Draw(preview)

    def draw_paths(paths: list[list[tuple[float, float]]], fill: str) -> None:
        for points in paths:
            polygon = [(round(x * preview_scale), round(y * preview_scale)) for x, y in points]
            if len(polygon) >= 3:
                draw.polygon(polygon, fill=fill)

    draw_paths(base_paths, COLOURS[0].output_hex)
    for colour in COLOURS[1:]:
        draw_paths(region_paths[colour.name], colour.output_hex)
    preview_path = OUT_DIR / "HN-PENDANT-VECTOR-PREVIEW-v0.1.png"
    preview.save(preview_path)

    # Human review sheet: source concept beside the deterministic vector draft.
    review = Image.new("RGB", (1000, 720), "#F4F6F8")
    source_crop = image.crop((x0, y0, x1, y1))
    source_crop.thumbnail((430, 620), Image.Resampling.LANCZOS)
    preview_copy = preview.copy()
    preview_copy.thumbnail((430, 620), Image.Resampling.NEAREST)
    review.paste(source_crop, (35 + (430 - source_crop.width) // 2, 65))
    review.paste(preview_copy, (535 + (430 - preview_copy.width) // 2, 65))
    review_draw = ImageDraw.Draw(review)
    review_draw.text((35, 25), "SOURCE CONCEPT", fill="#263746")
    review_draw.text((535, 25), "VECTOR DRAFT - 40 mm NOMINAL", fill="#263746")
    review.save(OUT_DIR / "HN-PENDANT-COMPARISON-v0.1.png")

    region_summary = []
    for colour in COLOURS[1:]:
        count = len(region_paths[colour.name])
        area_mm2 = float((region_masks[colour.name] > 0).sum()) / (px_per_mm * px_per_mm)
        region_summary.append((colour.name, colour.output_hex, count, area_mm2))

    report_lines = [
        "# HN-PENDANT 制造矢量草案 v0.1",
        "",
        "生成日期：2026-10-13",
        "",
        "## 输入与限制",
        "",
        f"- 输入：`design/image/result.png`，SHA-256 `{sha256(SOURCE)}`。",
        f"- 源文件：`design/image/result.psd`，SHA-256 `{sha256(ROOT / 'design' / 'image' / 'result.psd')}`。",
        "- PSD 经检查仅含两个整画布像素层，没有可直接提取的人物/色块矢量图层，因此本草案由合成图重新分区生成。",
        "- 本文件是用于工厂 DFM 的制造矢量草案，不是 G2 已发布生产图。",
        "",
        "## 名义几何规则",
        "",
        f"- 人物图案名义高度：{NOMINAL_HEIGHT_MM:.1f} mm（不含未来吊环）。",
        f"- 图案名义宽度：{width_mm:.2f} mm。",
        f"- 金属分隔网目标宽度：约 {METAL_WEB_MM:.2f} mm。",
        f"- 最小保留特征目标：约 {MIN_FEATURE_MM:.2f} mm。",
        f"- 小于约 {MIN_REGION_AREA_MM2:.2f} mm² 的孤立色块已删除。",
        f"- 路径简化容差：约 {CURVE_TOLERANCE_MM:.2f} mm。",
        "",
        "## 输出",
        "",
        "- `HN-PENDANT-COLOR-v0.1.svg`：金属底板和封闭平涂色块。",
        "- `HN-PENDANT-OUTLINE-v0.1.dxf`：毫米单位、按切边和颜色分层的封闭多段线。",
        "- `HN-PENDANT-VECTOR-PREVIEW-v0.1.png`：由同一矢量分区渲染的审阅预览。",
        "- `HN-PENDANT-COMPARISON-v0.1.png`：效果图与制造简化结果并排对照。",
        "",
        "## 色块统计",
        "",
        "| 图层 | 参考色 | 封闭轮廓数 | 估算净面积 mm² |",
        "|---|---|---:|---:|",
    ]
    report_lines.extend(f"| FILL_{n} | `{h}` | {c} | {a:.2f} |" for n, h, c, a in region_summary)
    report_lines.extend([
        "",
        "## 已执行的制造简化",
        "",
        "- 软阴影、高光碎点和过小孤立色块被合并或删除。",
        "- 原效果图中的主要深色描边和瞳孔归并为 `FILL_BLACK`，银色金属只作为结构底板和颜色隔断。",
        "- 发丝按大块轮廓保留，细尖端通过路径简化与最小面积规则减少。",
        "- 鞋带和衣褶不再作为独立细线，主要通过金属分隔网和大色块表达。",
        "- 手指保留整体剪影；小于最小特征的指缝会合并，避免细长易断结构。",
        "- 所有填色区域均为闭合轮廓，底层金属区域形成外边及颜色隔断。",
        "",
        "## 人工复核和工厂 DFM 必做项",
        "",
        "- 在 1:1 打印件上确认脸、五官、双手、鞋子和毛怪仍可辨认。",
        "- 确认哪些银色分隔线要改为深色填充；效果图深色描边目前统一解释为金属隔断。",
        "- 由工厂确认其实际最小隔断、色块、凹槽深度和填色工艺后重新偏置路径。",
        "- 毛怪固定版和旋转版仍需单独结构图；本 DXF 只表达正面图案分区，不定义转轴。",
        "- 吊环、背面、厚度、重心和公差尚未定义，不得用本草案直接开模。",
        "- 35 mm 或 45 mm 缩放后必须重新执行最小特征检查，不能只整体缩放 DXF。",
        "",
    ])
    (OUT_DIR / "README.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"source_bbox_px={x0},{y0},{x1},{y1}")
    print(f"artwork_mm={width_mm:.3f}x{NOMINAL_HEIGHT_MM:.3f}")
    print(f"px_per_mm={px_per_mm:.3f}")
    print(f"svg={svg_path_file}")
    print(f"dxf={dxf_path}")


if __name__ == "__main__":
    build()

