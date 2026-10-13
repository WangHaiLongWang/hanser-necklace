"""Convert this project's polygonal layered SVG into a millimetre DXF.

Supported SVG path commands: M, L, Z (absolute or relative). This matches the
generated manufacturing masters. If an editor saves curves, convert curves to
polylines before running this helper.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import ezdxf


TOKEN = re.compile(r"[MmLlZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def paths_from_d(data: str) -> list[list[tuple[float, float]]]:
    tokens = TOKEN.findall(data.replace(",", " "))
    paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    command = ""
    cursor = (0.0, 0.0)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in "MmLlZz":
            command = token
            index += 1
            if token in "Zz":
                if current:
                    paths.append(current)
                    current = []
                continue
        if command not in "MmLl":
            if index < len(tokens):
                raise ValueError(f"Unsupported or malformed SVG path near token {tokens[index]!r}")
            break
        if index + 1 >= len(tokens):
            raise ValueError("Odd coordinate count in SVG path")
        x, y = float(tokens[index]), float(tokens[index + 1])
        index += 2
        if command.islower():
            x += cursor[0]
            y += cursor[1]
        cursor = (x, y)
        current.append(cursor)
        if command in "Mm":
            command = "l" if command == "m" else "L"
    if current:
        paths.append(current)
    return paths


def convert(source: Path, target: Path) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    viewbox = [float(value) for value in root.attrib["viewBox"].replace(",", " ").split()]
    _, _, width, height = viewbox
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    for group in root.findall("svg:g", namespace):
        layer_name = group.attrib.get("id", "SVG_PATH")[:255]
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=7)
        for element in group.findall("svg:path", namespace):
            for points in paths_from_d(element.attrib.get("d", "")):
                if len(points) >= 3:
                    msp.add_lwpolyline([(x, height - y) for x, y in points], close=True, dxfattribs={"layer": layer_name})
    target.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(target)
    print(f"converted={source} -> {target}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/svg_layers_to_dxf.py INPUT.svg OUTPUT.dxf")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))

