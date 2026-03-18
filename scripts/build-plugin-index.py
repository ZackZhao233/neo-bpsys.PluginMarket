from __future__ import annotations

import argparse
import sys

from plugin_market.checksum_store import GitHubReleaseChecksumStore
from plugin_market.common import PLUGIN_INDEX_PATH, PluginMarketError, load_json_file, write_json_file
from plugin_market.index_builder import build_plugin_index

def load_checksums(args: argparse.Namespace) -> dict[str, str] | None:
    if args.checksums_file:
        data = load_json_file(args.checksums_file)
        if not isinstance(data, dict):
            raise PluginMarketError(f"Checksum file must contain a JSON object: {args.checksums_file}")
        return {str(key): str(value) for key, value in data.items()}

    if args.load_checksums_from_release:
        store = GitHubReleaseChecksumStore(
            repo=args.repo,
            token=args.token,
            release_tag=args.release_tag,
            asset_name=args.asset_name,
        )
        return store.load_checksums()

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PluginIndex.json from PluginManifests.")
    parser.add_argument("--checksums-file", type=str)
    parser.add_argument("--load-checksums-from-release", action="store_true")
    parser.add_argument("--strict-checksums", action="store_true")
    parser.add_argument("--repo")
    parser.add_argument("--token")
    parser.add_argument("--release-tag")
    parser.add_argument("--asset-name")
    args = parser.parse_args()

    try:
        checksums = load_checksums(args)
        if args.strict_checksums and checksums is None:
            raise PluginMarketError(
                "Strict checksum mode requires either --checksums-file or --load-checksums-from-release."
            )

        plugin_index, missing_checksums = build_plugin_index(
            checksums=checksums,
            strict_checksums=args.strict_checksums,
        )
        write_json_file(PLUGIN_INDEX_PATH, plugin_index)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if missing_checksums:
        print(
            f"Skipped sha256 for plugins missing release state: {', '.join(missing_checksums)}",
            file=sys.stderr,
        )

    print(f"Wrote {PLUGIN_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
