"""Assemble the v0.7 engineering DFM handoff and a reproducible ZIP."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "factory-pack" / "engineering-handoff-v0.7"
DESIGN_SOURCE = ROOT / "design" / "vector" / "manufacturing-v0.7-80mm-detail"
DESIGN_TARGET = HANDOFF / "design"
ZIP_PATH = ROOT / "factory-pack" / "HN-PENDANT-engineering-handoff-v0.7.zip"


CORE_FILES = [
    "HN-PENDANT-RESULT02-v0.7-80mm-detail.svg",
    "HN-PENDANT-RESULT02-v0.7-80mm-detail.dxf",
    "HN-PENDANT-RESULT02-PREVIEW-v0.7-80mm-detail.png",
    "HN-PENDANT-RESULT02-COMPARISON-v0.7-80mm-detail.png",
    "HN-PENDANT-RESULT02-LAYERS-v0.7-80mm-detail.csv",
    "README.md",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    DESIGN_TARGET.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        shutil.copy2(DESIGN_SOURCE / name, DESIGN_TARGET / name)
    target_layers = DESIGN_TARGET / "layers"
    target_layers.mkdir(parents=True, exist_ok=True)
    for source in sorted((DESIGN_SOURCE / "layers").glob("*.dxf")):
        shutil.copy2(source, target_layers / source.name)
    shutil.copy2(ROOT / "factory-pack" / "RFQ-DRAFT-CONCEPT-v0.1.md", HANDOFF / "RFQ-v0.7.md")

    files = sorted(path for path in HANDOFF.rglob("*") if path.is_file() and path.name != "MANIFEST-SHA256.txt")
    manifest = HANDOFF / "MANIFEST-SHA256.txt"
    manifest.write_text(
        "\n".join(f"{digest(path)}  {path.relative_to(HANDOFF).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in HANDOFF.rglob("*") if item.is_file()):
            archive.write(path, Path("HN-PENDANT-engineering-handoff-v0.7") / path.relative_to(HANDOFF))
    print(f"handoff={HANDOFF}")
    print(f"zip={ZIP_PATH}")
    print(f"files={len(list(HANDOFF.rglob('*.*')))}")


if __name__ == "__main__":
    main()

