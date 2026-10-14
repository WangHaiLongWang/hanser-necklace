"""Assemble the v0.8 engineering package with section and colour specs."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCS = ROOT / "factory-pack" / "engineering-handoff-v0.7"
HANDOFF = ROOT / "factory-pack" / "engineering-handoff-v0.8"
DESIGN_SOURCE = ROOT / "design" / "vector" / "manufacturing-v0.8-80mm-engineering"
DESIGN_TARGET = HANDOFF / "design"
ZIP_PATH = ROOT / "factory-pack" / "HN-PENDANT-engineering-handoff-v0.8.zip"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def migrated_text(text: str) -> str:
    text = text.replace("VECTOR-DRAFT-v0.7-80mm-detail", "ENGINEERING-DRAFT-v0.8-80mm")
    text = text.replace("v0.7-80mm-detail", "v0.8-80mm-engineering")
    text = text.replace("v0.7", "v0.8")
    text = text.replace(
        "目标最小金属隔断：约 0.20 mm，需工程方书面确认",
        "内部金属线：名义 0.30 mm；外轮廓：名义 0.60 mm、允许 0.50-0.70 mm",
    )
    return text


def main() -> None:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    DESIGN_TARGET.mkdir(parents=True, exist_ok=True)

    doc_names = [
        "00-READ-ME-FIRST.md",
        "ENGINEERING-BRIEF.md",
        "DECISIONS-v0.7.md",
        "BOM-DRAFT-v0.7.md",
        "DFM-RESPONSE-v0.7.md",
        "SEND-CHECKLIST.md",
        "PEARL-CHAIN-AND-BAIL-SPEC.md",
    ]
    for name in doc_names:
        source = SOURCE_DOCS / name
        target_name = name.replace("v0.7", "v0.8")
        (HANDOFF / target_name).write_text(migrated_text(source.read_text(encoding="utf-8-sig")), encoding="utf-8")

    shutil.copy2(ROOT / "factory-pack" / "RFQ-DRAFT-CONCEPT-v0.1.md", HANDOFF / "RFQ-v0.8.md")
    shutil.copy2(ROOT / "docs" / "09-color-standard-v0.8.md", HANDOFF / "COLOR-SPEC-v0.8.md")
    shutil.copy2(SOURCE_DOCS / "PANTONE-COLOR-SPEC-v0.8.csv", HANDOFF / "PANTONE-COLOR-SPEC-v0.8.csv")

    core_patterns = [
        "HN-PENDANT-RESULT02-v0.8-80mm-engineering.svg",
        "HN-PENDANT-RESULT02-v0.8-80mm-engineering.dxf",
        "HN-PENDANT-RESULT02-PREVIEW-v0.8-80mm-engineering.png",
        "HN-PENDANT-RESULT02-COMPARISON-v0.8-80mm-engineering.png",
        "HN-PENDANT-RESULT02-LAYERS-v0.8-80mm-engineering.csv",
        "HN-PENDANT-SECTION-v0.8.svg",
        "HN-PENDANT-SECTION-v0.8.dxf",
        "README.md",
    ]
    for name in core_patterns:
        shutil.copy2(DESIGN_SOURCE / name, DESIGN_TARGET / name)
    target_layers = DESIGN_TARGET / "layers"
    target_layers.mkdir(parents=True, exist_ok=True)
    for source in sorted((DESIGN_SOURCE / "layers").glob("*.dxf")):
        shutil.copy2(source, target_layers / source.name)

    files = sorted(path for path in HANDOFF.rglob("*") if path.is_file() and path.name != "MANIFEST-SHA256.txt")
    manifest = HANDOFF / "MANIFEST-SHA256.txt"
    manifest.write_text(
        "\n".join(f"{digest(path)}  {path.relative_to(HANDOFF).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in HANDOFF.rglob("*") if item.is_file()):
            archive.write(path, Path("HN-PENDANT-engineering-handoff-v0.8") / path.relative_to(HANDOFF))
    print(f"handoff={HANDOFF}")
    print(f"zip={ZIP_PATH}")
    print(f"files={len(list(path for path in HANDOFF.rglob('*') if path.is_file()))}")


if __name__ == "__main__":
    main()

