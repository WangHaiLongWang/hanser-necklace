"""Build a sized manufacturing draft from result_02 embedded semantic layers."""

from __future__ import annotations

import base64
import csv
import html
import xml.etree.ElementTree as ET
from io import BytesIO
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
SOURCE_SVG = ROOT / "design" / "image" / "result_02.svg"
SOURCE_PSD = ROOT / "design" / "image" / "result_02.psd"
OUT_DIR = ROOT / "design" / "vector" / "manufacturing-v0.4"
VERSION = "v0.4"

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


def read_embedded_layers() -> tuple[Image.Image, list[np.ndarray], list[dict[str, str]], tuple[int, int]]:
    root = ET.parse(SOURCE_SVG).getroot()
    namespace = "{http://www.w3.org/2000/svg}"
    xlink = "{http://www.w3.org/1999/xlink}href"
    viewbox = [float(value) for value in root.attrib["viewBox"].split()]
    width, height = int(round(viewbox[2])), int(round(viewbox[3]))
    composite = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    layers: list[np.ndarray] = []
    metadata: list[dict[str, str]] = []
    for element in root.iter(namespace + "image"):
        payload = element.attrib[xlink].split(",", 1)[1]
        image = Image.open(BytesIO(base64.b64decode(payload))).convert("RGBA")
        x, y = int(float(element.attrib.get("x", "0"))), int(float(element.attrib.get("y", "0")))
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.alpha_composite(image, (x, y))
        layers.append(np.asarray(canvas))
        metadata.append({
            "id": element.attrib.get("id", f"image-{len(layers)}"),
            "x": str(x),
            "y": str(y),
            "width": str(image.width),
            "height": str(image.height),
        })
        composite.alpha_composite(image, (x, y))
    if len(layers) != 5:
        raise RuntimeError(f"Expected 5 embedded semantic layers, got {len(layers)}")
    return composite, layers, metadata, (width, height)


def build_silhouette(rgb: np.ndarray) -> np.ndarray:
    distance = np.linalg.norm(255.0 - rgb.astype(np.float32), axis=2)
    ink = np.where(distance > 12.0, 255, 0).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    silhouette = largest_component(fill_enclosed(ink))
    return cv2.morphologyEx(silhouette, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))


def layer_colour_mask(layer: np.ndarray, predicate: np.ndarray) -> np.ndarray:
    return np.where((layer[:, :, 3] > 12) & predicate, 255, 0).astype(np.uint8)


def semantic_masks(composite: np.ndarray, layers: list[np.ndarray], silhouette: np.ndarray, px_per_mm: float) -> dict[str, np.ndarray]:
    # SVG embedded-image order mirrors the PSD group: base metal/white artwork,
    # skin, heart, blue clothing, hair.
    _, skin_layer, heart_layer, clothing_layer, hair_layer = layers

    sr, sg, sb = [skin_layer[:, :, channel].astype(np.int16) for channel in range(3)]
    skin_predicate = (sr >= 190) & (sr > sg + 8) & (sg > sb + 6)
    skin = layer_colour_mask(skin_layer, skin_predicate)

    cr, cg, cb = [clothing_layer[:, :, channel].astype(np.int16) for channel in range(3)]
    blue_predicate = (cb >= 95) & (cb > cg + 24) & (cg > cr + 12)
    blue = layer_colour_mask(clothing_layer, blue_predicate)
    # The isolated heart layer is intentionally reassigned to the shared blue.
    heart = np.where(heart_layer[:, :, 3] > 12, 255, 0).astype(np.uint8)
    blue = cv2.bitwise_or(blue, heart)

    hr, hg, hb = [hair_layer[:, :, channel].astype(np.int16) for channel in range(3)]
    hair_predicate = (hr >= 60) & (hr <= 225) & (hr > hg + 22) & (hg > hb + 10)
    hair = layer_colour_mask(hair_layer, hair_predicate)

    rr, rg, rb = [composite[:, :, channel].astype(np.int16) for channel in range(3)]
    chroma = np.maximum.reduce([rr, rg, rb]) - np.minimum.reduce([rr, rg, rb])
    white_predicate = (rr >= 202) & (rg >= 202) & (rb >= 195) & (chroma <= 25)
    white = np.where(white_predicate & (silhouette > 0), 255, 0).astype(np.uint8)

    # Slightly consolidate the already simplified upper hand without changing
    # its outer silhouette. This removes narrow internal finger slits.
    upper_hand = polygon_mask(silhouette.shape, [(510, 95), (750, 90), (800, 255), (615, 270), (495, 205)])
    hand_skin = cv2.bitwise_and(skin, upper_hand)
    close_px = max(3, int(round(0.42 * px_per_mm)) | 1)
    hand_skin = cv2.morphologyEx(hand_skin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px, close_px)))
    skin[upper_hand > 0] = 0
    skin = cv2.bitwise_or(skin, hand_skin)

    active = silhouette > 0
    for mask in (skin, white, hair, blue):
        mask[~active] = 0

    # Resolve only antialias overlaps, preserving semantic-layer priority.
    hair[blue > 0] = 0
    skin[(blue > 0) | (hair > 0)] = 0
    white[(blue > 0) | (hair > 0) | (skin > 0)] = 0
    return {"SKIN": skin, "WHITE": white, "HAIR": hair, "BLUE": blue}


def clean_masks(raw: dict[str, np.ndarray], silhouette: np.ndarray, px_per_mm: float) -> dict[str, np.ndarray]:
    half_web_px = max(1, int(round((METAL_WEB_MM / 2.0) * px_per_mm)))
    inset = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half_web_px + 1, 2 * half_web_px + 1))
    cleanup_px = max(3, int(round(0.18 * px_per_mm)) | 1)
    cleanup = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cleanup_px, cleanup_px))
    minimum_area_px = MIN_REGION_AREA_MM2 * px_per_mm * px_per_mm
    result: dict[str, np.ndarray] = {}
    for name, raw_mask in raw.items():
        mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, cleanup)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cleanup)
        mask = cv2.erode(mask, inset)
        mask = remove_small_components(mask, minimum_area_px)
        result[name] = cv2.bitwise_and(mask, silhouette)
    return result


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    composite_image, layers, layer_metadata, (canvas_px_w, canvas_px_h) = read_embedded_layers()
    rgb = np.asarray(composite_image.convert("RGB"))
    silhouette = build_silhouette(rgb)
    ys, xs = np.where(silhouette > 0)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    px_per_mm = (y1 - y0) / NOMINAL_HEIGHT_MM
    width_mm = (x1 - x0) / px_per_mm
    canvas_w_mm = width_mm + 2 * MARGIN_MM
    canvas_h_mm = NOMINAL_HEIGHT_MM + 2 * MARGIN_MM

    masks = clean_masks(semantic_masks(rgb, layers, silhouette, px_per_mm), silhouette, px_per_mm)
    colour_union = np.zeros_like(silhouette)
    for mask in masks.values():
        colour_union = cv2.bitwise_or(colour_union, mask)
    raised_metal = cv2.bitwise_and(silhouette, cv2.bitwise_not(colour_union))

    base_paths = contour_paths(silhouette, x0, y0, px_per_mm)
    paths = {name: contour_paths(mask, x0, y0, px_per_mm) for name, mask in masks.items()}
    metal_paths = contour_paths(raised_metal, x0, y0, px_per_mm)

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w_mm:.3f}mm" height="{canvas_h_mm:.3f}mm" viewBox="0 0 {canvas_w_mm:.3f} {canvas_h_mm:.3f}">',
        f'  <title>HN Pendant manufacturing master {VERSION}</title>',
        '  <desc>Rebuilt from five embedded raster semantic layers in result_02.svg. Four paint fills plus raised metal. Nominal 40 mm.</desc>',
        f'  <g id="CUT_OUTER_METAL" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(base_paths))}"/></g>',
    ]
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        svg_lines.append(f'  <g id="FILL_{name}" fill="{PALETTE[name]}" fill-rule="evenodd"><path d="{html.escape(svg_path(paths[name]))}"/></g>')
    svg_lines.append(f'  <g id="RAISED_METAL_DETAILS" fill="{PALETTE["METAL"]}" fill-rule="evenodd"><path d="{html.escape(svg_path(metal_paths))}"/></g>')
    svg_lines.append("</svg>")
    svg_file = OUT_DIR / f"HN-PENDANT-RESULT02-{VERSION}.svg"
    svg_file.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")

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
    for aci, (name, colour) in enumerate(layer_colours.items(), start=1):
        layer = doc.layers.add(name, color=((aci - 1) % 7) + 1)
        layer.rgb = ezdxf.colors.RGB.from_hex(colour)
    msp = doc.modelspace()

    def add_polylines(items: list[list[tuple[float, float]]], layer: str) -> None:
        for points in items:
            msp.add_lwpolyline([(x, canvas_h_mm - y) for x, y in points], close=True, dxfattribs={"layer": layer})

    add_polylines(base_paths, "CUT_OUTER")
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        add_polylines(paths[name], f"FILL_{name}")
    add_polylines(metal_paths, "RAISED_METAL")
    dxf_file = OUT_DIR / f"HN-PENDANT-RESULT02-{VERSION}.dxf"
    doc.saveas(dxf_file)

    # Separate single-layer DXFs make it easy for a factory to inspect or quote
    # each process without hiding unrelated layers in CAD.
    split_dir = OUT_DIR / "layers"
    split_dir.mkdir(parents=True, exist_ok=True)
    split_sources = {
        "CUT_OUTER": base_paths,
        "FILL_SKIN": paths["SKIN"],
        "FILL_WHITE": paths["WHITE"],
        "FILL_HAIR": paths["HAIR"],
        "FILL_BLUE": paths["BLUE"],
        "RAISED_METAL": metal_paths,
    }
    for layer_name, items in split_sources.items():
        split_doc = ezdxf.new("R2010", setup=True)
        split_doc.units = ezdxf.units.MM
        split_doc.layers.add(layer_name, color=7)
        split_msp = split_doc.modelspace()
        for points in items:
            split_msp.add_lwpolyline(
                [(x, canvas_h_mm - y) for x, y in points],
                close=True,
                dxfattribs={"layer": layer_name},
            )
        split_doc.saveas(split_dir / f"HN-PENDANT-{VERSION}-{layer_name}.dxf")

    with (OUT_DIR / f"HN-PENDANT-RESULT02-LAYERS-{VERSION}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["layer", "purpose", "reference_color", "closed_contours"])
        writer.writerow(["CUT_OUTER", "316L outer silhouette/base", PALETTE["METAL"], len(base_paths)])
        writer.writerow(["FILL_SKIN", "skin enamel/fill", PALETTE["SKIN"], len(paths["SKIN"])])
        writer.writerow(["FILL_WHITE", "white enamel/fill", PALETTE["WHITE"], len(paths["WHITE"])])
        writer.writerow(["FILL_HAIR", "hair enamel/fill", PALETTE["HAIR"], len(paths["HAIR"])])
        writer.writerow(["FILL_BLUE", "blue enamel/fill, including heart", PALETTE["BLUE"], len(paths["BLUE"])])
        writer.writerow(["RAISED_METAL", "raised metal separators/features", PALETTE["METAL"], len(metal_paths)])

    scale = 14
    preview = Image.new("RGB", (round(canvas_w_mm * scale), round(canvas_h_mm * scale)), "white")
    draw = ImageDraw.Draw(preview)

    def draw_paths(items: list[list[tuple[float, float]]], fill: str) -> None:
        for points in items:
            if len(points) >= 3:
                draw.polygon([(round(x * scale), round(y * scale)) for x, y in points], fill=fill)

    draw_paths(base_paths, PALETTE["METAL"])
    for name in ("SKIN", "WHITE", "HAIR", "BLUE"):
        draw_paths(paths[name], PALETTE[name])
    preview_file = OUT_DIR / f"HN-PENDANT-RESULT02-PREVIEW-{VERSION}.png"
    preview.save(preview_file)

    comparison = Image.new("RGB", (1100, 760), "#F4F6F8")
    source_crop = composite_image.convert("RGB").crop((x0, y0, x1, y1))
    source_crop.thumbnail((470, 650), Image.Resampling.LANCZOS)
    vector_copy = preview.copy()
    vector_copy.thumbnail((470, 650), Image.Resampling.NEAREST)
    comparison.paste(source_crop, (40 + (470 - source_crop.width) // 2, 70))
    comparison.paste(vector_copy, (590 + (470 - vector_copy.width) // 2, 70))
    cdraw = ImageDraw.Draw(comparison)
    cdraw.text((40, 28), "SOURCE SVG COMPOSITE", fill="#263746")
    cdraw.text((590, 28), f"MANUFACTURING {VERSION.upper()}", fill="#263746")
    comparison.save(OUT_DIR / f"HN-PENDANT-RESULT02-COMPARISON-{VERSION}.png")

    layer_preview = Image.new("RGB", (1200, 310), "#F4F6F8")
    lp_draw = ImageDraw.Draw(layer_preview)
    for index, array in enumerate(layers):
        layer_image = Image.fromarray(array).convert("RGBA")
        alpha = layer_image.getchannel("A")
        white_background = Image.new("RGBA", layer_image.size, "white")
        white_background.alpha_composite(layer_image)
        crop = white_background.convert("RGB").crop((x0, y0, x1, y1))
        crop.thumbnail((210, 235), Image.Resampling.LANCZOS)
        x_pos = 20 + index * 235 + (210 - crop.width) // 2
        layer_preview.paste(crop, (x_pos, 50))
        lp_draw.text((20 + index * 235, 18), f"LAYER {index}: {layer_metadata[index]['id']}", fill="#263746")
    layer_preview.save(OUT_DIR / f"HN-PENDANT-RESULT02-SOURCE-LAYERS-{VERSION}.png")

    stats = []
    for name, mask in masks.items():
        stats.append((name, len(paths[name]), float((mask > 0).sum()) / (px_per_mm * px_per_mm)))
    metal_area = float((raised_metal > 0).sum()) / (px_per_mm * px_per_mm)

    report = [
        f"# HN-PENDANT result_02 加工矢量 {VERSION}",
        "",
        "生成日期：2026-10-13",
        "",
        "## 源文件审计",
        "",
        f"- `result_02.svg` SHA-256：`{sha256(SOURCE_SVG)}`。",
        f"- `result_02.psd` SHA-256：`{sha256(SOURCE_PSD)}`。",
        f"- SVG 画布：`{canvas_px_w} × {canvas_px_h}`，包含 5 个嵌入式 PNG 图层，包含 0 条 SVG path。",
        "- SVG 的 5 个嵌入图与 PSD 子图层逐一对应；按顺序合成后与 PSD 合成像素完全一致。",
        "- 因源 SVG 仍是位图容器，本版使用各层 Alpha 和颜色语义重建闭合路径；不是对现有 path 的直接转换。",
        "",
        "## 加工输出",
        "",
        f"- `HN-PENDANT-RESULT02-{VERSION}.svg`：毫米尺寸、分层闭合路径的加工母版。",
        f"- `HN-PENDANT-RESULT02-{VERSION}.dxf`：R2010、毫米单位、分层闭合 LWPOLYLINE。",
        f"- `HN-PENDANT-RESULT02-PREVIEW-{VERSION}.png`：由加工几何渲染的五色预览。",
        f"- `HN-PENDANT-RESULT02-COMPARISON-{VERSION}.png`：源合成图与加工结果对照。",
        f"- `HN-PENDANT-RESULT02-SOURCE-LAYERS-{VERSION}.png`：5 个源图层的可视化审计。",
        f"- `HN-PENDANT-RESULT02-LAYERS-{VERSION}.csv`：加工图层、参考色和闭合轮廓数量。",
        "- `layers/*.dxf`：每个加工层单独导出的毫米 DXF。",
        "",
        "## 几何规则",
        "",
        f"- 名义图案高度：`{NOMINAL_HEIGHT_MM:.2f} mm`，宽度：`{width_mm:.2f} mm`，不含吊环。",
        f"- 目标金属分隔宽度：约 `{METAL_WEB_MM:.2f} mm`。",
        f"- 目标最小保留特征：约 `{MIN_FEATURE_MM:.2f} mm`。",
        "- 肤色、蓝色、爱心和头发由各自源图层 Alpha 提取；白色从人物轮廓内的中性浅色恢复。",
        "- 爱心并入蓝色层；灰色描边、人物眼眉和毛怪五官归入凸起金属层。",
        "- 细碎发丝、鞋带、衣褶和窄指缝通过闭合、开运算、最小面积过滤和向内偏置进行简化。",
        "",
        "## 图层统计",
        "",
        "| 图层 | 闭合轮廓数 | 面积估算 mm² |",
        "|---|---:|---:|",
    ]
    report.extend(f"| FILL_{name} | {count} | {area:.2f} |" for name, count, area in stats)
    report.append(f"| RAISED_METAL | {len(metal_paths)} | {metal_area:.2f} |")
    report.extend([
        "",
        "## 下单前仍需完成",
        "",
        "- 工厂确认最小金属隔断、填色区、凹槽深度和允许圆角后，重新偏置最终路径。",
        "- 增加吊环、背面、厚度、重心、毛怪连接/转轴和公差图。",
        "- 1:1 打印并确认 40 mm 下手指、眼睛、鞋子和毛怪五官可读。",
        "- 当前文件可用于 DFM 与询价，不可未经工厂回签直接开模。",
        "",
    ])
    (OUT_DIR / "README.md").write_text("\n".join(report), encoding="utf-8")
    print(f"artwork={width_mm:.3f}x{NOMINAL_HEIGHT_MM:.3f}mm")
    print(svg_file)
    print(dxf_file)


if __name__ == "__main__":
    build()

