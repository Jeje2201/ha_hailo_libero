"""Check the manual install archive and translated configuration contract."""

import importlib.util
import json
import tomllib
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "hailo_libero"


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_contains_client_and_notices(tmp_path: Path) -> None:
    module = load_script("build_release")
    archive = module.build_release(tmp_path / "release.zip")
    with ZipFile(archive) as output:
        names = output.namelist()
        assert "custom_components/hailo_libero/api/client.py" in names
        assert "custom_components/hailo_libero/manifest.json" in names
        assert "custom_components/hailo_libero/translations/en.json" in names
        assert "LICENSE" in names
        assert "THIRD_PARTY_NOTICES.md" in names
        assert not any("__pycache__" in name or ".venv" in name for name in names)
        for path in (ROOT / "src" / "aiohailo_libero").glob("*.py"):
            assert output.read(
                f"custom_components/hailo_libero/api/{path.name}"
            ) == path.read_bytes()


def test_translation_keys_match() -> None:
    english = json.loads((COMPONENT / "strings.json").read_text())
    french = json.loads((COMPONENT / "translations" / "fr.json").read_text())
    runtime_english = json.loads(
        (COMPONENT / "translations" / "en.json").read_text()
    )
    assert runtime_english == english

    def keys(value: dict, prefix: str = "") -> set[str]:
        result: set[str] = set()
        for key, item in value.items():
            path = f"{prefix}.{key}"
            result.add(path)
            if isinstance(item, dict):
                result.update(keys(item, path))
        return result

    assert keys(english) == keys(french)


def test_manifest_identifies_owner() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert manifest["codeowners"] == ["@Jeje2201"]
    assert manifest["domain"] == COMPONENT.name
    assert manifest["config_flow"] is True
    assert "quality_scale" not in manifest
    repository = "https://github.com/Jeje2201/ha_hailo_libero"
    assert manifest["documentation"] == repository
    urls = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["urls"]
    assert urls["Source"] == repository
    assert urls["Issues"] == f"{repository}/issues"
