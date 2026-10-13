"""Build VECTOR-DRAFT-v0.3 from flattened result_02 PSD/PNG artwork."""

from __future__ import annotations

import html
from pathlib import Path

import cv2
import ezdxf
import numpy as np
from PIL import Image, ImageDraw

from vectorize_concept import (
    contour_paths,
    fill_enclosed,
    largest_component,
    polygon_mask,
    remove_small_components,
    sha256,
    svg_path,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PNG = ROOT / "design" / "image" / "result_02.png"
SOURCE_PSD = ROOT / "design" / "image" / "result_02.psd"
OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.3"

NOMINAL_HEIGHT_MM = 40.0
MARGIN_MM = 2.0
METAL_WEB_MM = 0.35
MIN_FEATURE_MM = 0.50
MIN_REGION_AREA_MM2 = 0.08

PALETTE = {
    "METAL": "#A7A7A7",
    "SKIN": "#FAD3AB",
    "WHITE": "#F5F3F0",
    "HAIR": "#905530",
    "BLUE": "#196FC6",
}


def build_silhouette(rgb: np.ndarray) -> np.ndarray:
    distance = np.linalg.norm(255.0 - rgb.astype(np.float32), axis=2)
    ink = np.where(distance > 12.0, 255, 0).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    silhouette = largest_component(fill_enclosed(ink))
    return cv2.morphologyEx(silhouette, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))


def classify_masks(rgb: np.ndarray, silhouette: np.ndarray, px_per_mm: float) -> dict[str, np.ndarray]:
    r, g, b = [rgb[:, :, channel].astype(np.int16) for channel in range(3)]
    active = silhouette > 0

    blue_like = (b >= 105) & (b > g + 32) & (g > r + 12)
    hair_like = (r >= 70) & (r <= 225) & (r > g + 24) & (g > b + 12)
    skin_like = (r >= 205) & (g >= 135) & (b >= 105) & (r > g + 12) & (g > b + 8)
    white_like = (r >= 202) & (g >= 202) & (b >= 195) & ((np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])) <= 24)
    pink_heart = (r >= 195) & (r > g + 35) & (b >= 105) & (b > g - 25)

    masks = {
        "SKIN": np.where(skin_like & active, 255, 0).astype(np.uint8),
        "WHITE": np.where(white_like & active, 255, 0).astype(np.uint8),
        "HAIR": np.where(hair_like & active, 255, 0).astype(np.uint8),
        "BLUE": np.where((blue_like | pink_heart) & active, 255, 0).astype(np.uint8),
    }

    # The new artwork already has simplified fingers. Close only narrow internal
    # metal slits in the upper hand, preserving its outer gesture silhouette.
    upper_hand = polygon_mask(silhouette.shape, [(520, 105), (735, 90), (790, 245), (620, 250), (505, 200)])
    hand_skin = cv2.bitwise_and(masks["SKIN"], upper_hand)
    hand_close_px = max(3, int(round(0.45 * px_per_mm)) | 1)
    hand_skin = cv2.morphologyEx(
        hand_skin,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (hand_close_px, hand_close_px)),
    )
    masks["SKIN"][upper_hand > 0] = 0
    masks["SKIN"] = cv2.bitwise_or(masks["SKIN"], hand_skin)

    # Resolve overlaps: blue accents above hair/white, hair above skin, skin
    # above shared white. Unassigned gray/dark pixels remain raised metal.
    masks["HAIR"][masks["BLUE"] > 0] = 0
    masks["SKIN"][(masks["BLUE"] > 0) | (masks["HAIR"] > 0)] = 0
    masks["WHITE"][(masks["BLUE"] > 0) | (masks["HAIR"] > 0) | (masks["SKIN"] > 0)] = 0
    return masks


def clean_masks(raw: dict[str, np.ndarray], silhouette: np.ndarray, px_per_mm: float) -> dict[str, np.ndarray]:
    half_web_px = max(1, int(round((METAL_WEB_MM / 2.0) * px_per_mm)))
    inset = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half_web_px + 1, 2 * half_web_px + 1))
    clean_px = max(3, int(round(0.20 * px_per_mm)) | 1)
    clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (clean_px, clean_px))
    min_area_px = MIN_REGION_AREA_MM2 * px_per_mm * px_per_mm
    result: dict[str, np.ndarray] = {}
    for name, source in raw.items():
        mask = cv2.morphologyEx(source, cv2.MORPH_CLOSE, clean)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, clean)
        mask = cv2.erode(mask, inset)
        mask = remove_small_components(mask, min_area_px)
        result[name] = cv2.bitwise_and(mask, silhouette)
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

    masks = clean_masks(classify_masks(rgb, silhouette, px_per_mm), silhouette, px_per_mm)
    union = np.zeros_like(silhouette)
    for mask in masks.values():
        union = cv2.bitwise_or(union, mask)
    raised_metal = cv2.bitwise_and(silhouette, cv2.bitwise_not(union))

    base_paths = contour_paths(silhouette, x0, y0, px_per_mm)
    region_paths = {name: contour_paths(mask, x0, y0, px_per_mm) for name, mask in masks.items()}
    metal_paths = contour_paths(raised_metal, x0, y0, px_per_mm)

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w_mm:.3f}mm" height="{canvas_h_mm:.3f}mm" viewBox="0 0 {canvas_w_mm:.3f} {canvas_h_mm:.3f}">',
        '  <title>HN Pendant manufacturing vector draft v0.3</title>',
        '  <desc>Rebuilt from flattened result_02; four closed paint colours plus raised metal. Nominal height 40 mm.</desc>',
        f'  <g id="CUT_OUTER_METAL" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(base_paths))}"/></g>',
    ]
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        svg.append(f'  <g id="FILL_{name}" fill="{PALETTE[name]}" fill-rule="evenodd"><path d="{html.escape(svg_path(region_paths[name]))}"/></g>')
    svg.append(f'  <g id="RAISED_METAL_DETAILS" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(metal_paths))}"/></g>')
    svg.append('</svg>')
    svg_file = OUT_DIR / "HN-PENDANT-RESULT02-v0.3.svg"
    svg_file.write_text("\n".join(svg) + "\n", encoding="utf-8")

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    layer_colours = {
        "CUT_OUTER": PALETTE["METAL"],
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
    add(metal_paths, "RAISED_METAL")
    dxf_file = OUT_DIR / "HN-PENDANT-RESULT02-v0.3.dxf"
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
    # Metal is already visible through the base, but the explicit layer makes
    # the raster preview match the DXF layer semantics.
    draw_paths(metal_paths, PALETTE["METAL"])
    preview_file = OUT_DIR / "HN-PENDANT-RESULT02-PREVIEW-v0.3.png"
    preview.save(preview_file)

    comparison = Image.new("RGB", (1100, 760), "#F4F6F8")
    source_crop = image.crop((x0, y0, x1, y1))
    source_crop.thumbnail((470, 650), Image.Resampling.LANCZOS)
    preview_copy = preview.copy()
    preview_copy.thumbnail((470, 650), Image.Resampling.NEAREST)
    comparison.paste(source_crop, (40 + (470 - source_crop.width) // 2, 70))
    comparison.paste(preview_copy, (590 + (470 - preview_copy.width) // 2, 70))
    cdraw = ImageDraw.Draw(comparison)
    cdraw.text((40, 28), "SOURCE: RESULT_02", fill="#263746")
    cdraw.text((590, 28), "VECTOR DRAFT V0.3", fill="#263746")
    comparison.save(OUT_DIR / "HN-PENDANT-RESULT02-COMPARISON-v0.3.png")

    stats = []
    for name, mask in masks.items():
        stats.append((name, len(region_paths[name]), float((mask > 0).sum()) / (px_per_mm * px_per_mm)))
    metal_area = float((raised_metal > 0).sum()) / (px_per_mm * px_per_mm)
    report = [
        "# HN-PENDANT result_02 制造矢量草案 v0.3",
        "",
        "生成日期：2026-10-13",
        "",
        "## 输入审计",
        "",
        f"- `result_02.png` SHA-256：`{sha256(SOURCE_PNG)}`。",
        f"- `result_02.psd` SHA-256：`{sha256(SOURCE_PSD)}`。",
        "- PSD 为 0 图层的完全扁平合成文件，其合成像素与 PNG 完全一致；本版属于重新分区重建，不是原图层无损提取。",
        "",
        "## 输出",
        "",
        "- `HN-PENDANT-RESULT02-v0.3.svg`：后续人工细化母版。",
        "- `HN-PENDANT-RESULT02-v0.3.dxf`：毫米单位分层封闭轮廓。",
        "- `HN-PENDANT-RESULT02-PREVIEW-v0.3.png`：从同一几何分区渲染的五色预览。",
        "- `HN-PENDANT-RESULT02-COMPARISON-v0.3.png`：源图与简化结果对照。",
        "",
        "## 几何与最小特征",
        "",
        f"- 名义图案尺寸：高 `{NOMINAL_HEIGHT_MM:.2f} mm`，宽 `{width_mm:.2f} mm`，不含吊环。",
        f"- 目标金属分隔宽度：约 `{METAL_WEB_MM:.2f} mm`。",
        f"- 目标最小保留特征：约 `{MIN_FEATURE_MM:.2f} mm`。",
        "- 小于阈值的发丝、高光、鞋带缝、衣褶和指缝已合并或删除。",
        "- 原粉色毛怪爱心已归入蓝色层；所有灰色眼睛、五官和结构线归入凸起金属层。",
        "",
        "## 色层统计",
        "",
        "| 图层 | 闭合轮廓数 | 面积估算 mm² |",
        "|---|---:|---:|",
    ]
    report.extend(f"| FILL_{name} | {count} | {area:.2f} |" for name, count, area in stats)
    report.append(f"| RAISED_METAL | {len(metal_paths)} | {metal_area:.2f} |")
    report.extend([
        "",
        "## 后续修改流程",
        "",
        "1. 复制 SVG 并升版，不覆盖 v0.3。",
        "2. 在矢量软件中按 `FILL_*` / `RAISED_METAL_DETAILS` 图层调整节点。",
        "3. 保持所有色块闭合、无自交、无重叠，相邻颜色间保留连续金属网。",
        "4. 在 1:1 的 40 mm 视图检查手指、眼睛、鞋子和毛怪表情。",
        "5. 执行 `python scripts/svg_layers_to_dxf.py 输入.svg 输出.dxf` 重新生成 DXF。",
        "6. CAD 中确认单位为 mm、轮廓全部闭合后再交工厂 DFM。",
        "",
        "本文件仍缺吊环、背面、厚度、凹槽深度、毛怪连接和公差，不可直接开模。",
        "",
    ])
    (OUT_DIR / "README.md").write_text("\n".join(report), encoding="utf-8")
    print(f"source_bbox={x0},{y0},{x1},{y1}")
    print(f"artwork={width_mm:.3f}x{NOMINAL_HEIGHT_MM:.3f}mm")
    print(svg_file)
    print(dxf_file)


if __name__ == "__main__":
    build()

