from __future__ import annotations

from pathlib import Path

from plugin_market.common import MANIFEST_DIR, PluginMarketError
from plugin_market.manifest import load_manifest_map


def build_plugin_index(
    *,
    manifest_dir: Path = MANIFEST_DIR,
    checksums: dict[str, str] | None = None,
    strict_checksums: bool = False,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    manifests = load_manifest_map(manifest_dir)
    plugin_index: dict[str, dict[str, str]] = {}
    missing_checksums: list[str] = []

    for plugin_id in sorted(manifests):
        manifest = dict(manifests[plugin_id])
        if checksums is not None:
            checksum = checksums.get(plugin_id)
            if checksum:
                manifest["sha256"] = checksum
            else:
                missing_checksums.append(plugin_id)
                if strict_checksums:
                    raise PluginMarketError(
                        f"Missing checksum for plugin '{plugin_id}'. Update the release asset before generating PluginIndex.json."
                    )
        plugin_index[plugin_id] = manifest

    return plugin_index, missing_checksums

