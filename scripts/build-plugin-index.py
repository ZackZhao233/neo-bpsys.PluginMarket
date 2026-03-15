from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = REPO_ROOT / "PluginManifests"
OUTPUT_PATH = REPO_ROOT / "PluginIndex.json"


def parse_scalar(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""

    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)

    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")

    return value


def parse_manifest(path: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if raw_line[:1].isspace():
            raise ValueError(f"{path}: line {line_number} uses indentation; only flat key/value manifests are supported")

        key, separator, value = raw_line.partition(":")
        if not separator:
            raise ValueError(f"{path}: line {line_number} is not a valid key/value pair")

        key = key.strip()
        if not key:
            raise ValueError(f"{path}: line {line_number} has an empty key")
        if key in manifest:
            raise ValueError(f"{path}: duplicate key '{key}'")

        manifest[key] = parse_scalar(value)

    if "id" not in manifest or not manifest["id"]:
        raise ValueError(f"{path}: missing required 'id'")

    return manifest


def build_index() -> dict[str, dict[str, str]]:
    if not MANIFEST_DIR.exists():
        raise ValueError(f"Manifest directory not found: {MANIFEST_DIR}")

    manifests = sorted(MANIFEST_DIR.rglob("*.yml"))
    plugin_index: dict[str, dict[str, str]] = {}

    for manifest_path in manifests:
        manifest = parse_manifest(manifest_path)
        plugin_id = manifest["id"]
        if plugin_id in plugin_index:
            raise ValueError(
                f"Duplicate plugin id '{plugin_id}' found in "
                f"'{manifest_path}' and another manifest"
            )
        plugin_index[plugin_id] = manifest

    return {plugin_id: plugin_index[plugin_id] for plugin_id in sorted(plugin_index)}


def main() -> int:
    try:
        plugin_index = build_index()
        OUTPUT_PATH.write_text(
            json.dumps(plugin_index, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
