"""Build a manual-install archive containing sources and license notices."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def build_release(destination: Path | None = None) -> Path:
    component = ROOT / "custom_components" / "hailo_libero"
    version = json.loads((component / "manifest.json").read_text())["version"]
    archive = destination or ROOT / "dist" / f"hailo-libero-{version}.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for path in sorted(component.rglob("*")):
            if path.relative_to(component).parts[0] == "api":
                continue
            if path.is_file() and path.suffix in (".py", ".json", ".yaml"):
                output.write(path, path.relative_to(ROOT).as_posix())
        for path in sorted((ROOT / "src" / "aiohailo_libero").glob("*.py")):
            output.write(path, f"custom_components/hailo_libero/api/{path.name}")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
            output.write(ROOT / name, name)
    return archive


if __name__ == "__main__":
    print(build_release())