from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from plugin_market.common import (
    MANIFEST_DIR,
    PluginMarketError,
    error,
    git_diff_name_only,
    git_show_text,
    write_github_output,
)
from plugin_market.manifest import (
    ensure_manifest_path_allowed,
    load_manifest_map,
    parse_manifest_text,
    validate_manifest,
)
from plugin_market.pr_conflict_check import find_conflicting_pull_requests


@dataclass
class PrecheckResult:
    plugin_id: str
    manifest_path: str
    download_url: str
    conflict_prs: list[int]


class PrecheckFailure(PluginMarketError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def run_precheck(
    *,
    base_ref: str,
    head_ref: str,
    pr_number: int,
    repo: str | None,
    token: str | None,
) -> PrecheckResult:
    changed_files = git_diff_name_only(base_ref, head_ref)
    write_github_output("changed_files", "\n".join(changed_files))

    if not changed_files:
        raise PrecheckFailure("no-manifest-change", "No changed files were found in the pull request.")

    if "PluginIndex.json" in changed_files:
        raise PrecheckFailure(
            "plugin-index-modified",
            "PluginIndex.json is generated automatically. Do not modify it in a pull request.",
        )

    if any(path == "checksums.json" or path.endswith("/checksums.json") for path in changed_files):
        raise PrecheckFailure(
            "checksums-modified",
            "checksums.json is managed by release automation. Do not add or edit it in a pull request.",
        )

    if len(changed_files) != 1:
        raise PrecheckFailure(
            "invalid-changed-files",
            "Exactly one file may be changed in a plugin PR, and it must be PluginManifests/<PluginId>.yml.",
        )

    manifest_path = changed_files[0]
    ensure_manifest_path_allowed(manifest_path)

    try:
        manifest_text = git_show_text(head_ref, manifest_path)
    except PluginMarketError as exc:
        raise PrecheckFailure("manifest-missing", f"Unable to read {manifest_path} from pull request head: {exc}") from exc

    manifest = parse_manifest_text(manifest_text, manifest_path)
    errors = validate_manifest(manifest, source=manifest_path, manifest_path=manifest_path)
    if errors:
        raise PrecheckFailure("manifest-invalid", "\n".join(errors))

    target_path = (MANIFEST_DIR / Path(manifest_path).name).resolve()
    other_manifests = load_manifest_map(exclude_paths=[target_path] if target_path.exists() else [])
    plugin_id = manifest["id"]
    if plugin_id in other_manifests:
        raise PrecheckFailure(
            "duplicate-plugin-id",
            f"Plugin id '{plugin_id}' already exists in another manifest in this repository.",
        )

    conflicts = find_conflicting_pull_requests(
        repo=repo,
        token=token,
        current_pr_number=pr_number,
        manifest_path=manifest_path,
    )
    if conflicts:
        raise PrecheckFailure(
            "plugin-conflict",
            f"Another open pull request is already modifying {manifest_path}: {', '.join(f'#{pr}' for pr in conflicts)}",
        )

    return PrecheckResult(
        plugin_id=plugin_id,
        manifest_path=manifest_path,
        download_url=manifest["downloadURL"],
        conflict_prs=[],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plugin PR manifest changes.")
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--repo")
    parser.add_argument("--token")
    args = parser.parse_args()

    write_github_output("status", "failed")
    try:
        result = run_precheck(
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            pr_number=args.pr_number,
            repo=args.repo,
            token=args.token,
        )
    except PrecheckFailure as exc:
        write_github_output("failure_reason", exc.reason)
        write_github_output("error_message", str(exc))
        error(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001
        write_github_output("failure_reason", "unexpected-error")
        write_github_output("error_message", str(exc))
        error(str(exc))
        return 1

    write_github_output("status", "passed")
    write_github_output("failure_reason", "")
    write_github_output("plugin_id", result.plugin_id)
    write_github_output("manifest_path", result.manifest_path)
    write_github_output("download_url", result.download_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

