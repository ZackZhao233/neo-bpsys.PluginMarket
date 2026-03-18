from __future__ import annotations

import json
import os
import urllib.parse
from typing import Any

from plugin_market.common import (
    DEFAULT_STATE_ASSET_NAME,
    DEFAULT_STATE_RELEASE_TAG,
    GitHubApiClient,
    PluginMarketError,
    log,
)


class GitHubReleaseChecksumStore:
    def __init__(
        self,
        *,
        repo: str | None = None,
        token: str | None = None,
        release_tag: str | None = None,
        asset_name: str | None = None,
    ) -> None:
        self.client = GitHubApiClient(repo=repo, token=token)
        self.release_tag = release_tag or os.environ.get("PLUGIN_MARKET_STATE_RELEASE_TAG") or DEFAULT_STATE_RELEASE_TAG
        self.asset_name = asset_name or os.environ.get("PLUGIN_MARKET_STATE_ASSET_NAME") or DEFAULT_STATE_ASSET_NAME

    def get_release(self) -> dict[str, Any]:
        try:
            release = self.client.request_json(
                "GET",
                f"/repos/{self.client.repo_slug}/releases/tags/{urllib.parse.quote(self.release_tag, safe='')}",
            )
        except PluginMarketError as exc:
            raise PluginMarketError(
                f"Release '{self.release_tag}' was not found. Create the release before running checksum automation.\n{exc}"
            ) from exc

        if not isinstance(release, dict):
            raise PluginMarketError(f"Unexpected release payload for tag '{self.release_tag}'")
        return release

    def _find_asset(self, release: dict[str, Any]) -> dict[str, Any] | None:
        for asset in release.get("assets", []):
            if asset.get("name") == self.asset_name:
                return asset
        return None

    def load_checksums(self) -> dict[str, str]:
        release = self.get_release()
        asset = self._find_asset(release)
        if asset is None:
            log(f"Release asset '{self.asset_name}' not found under tag '{self.release_tag}'. Initializing as empty JSON.")
            return {}

        content = self.client.request(
            "GET",
            f"/repos/{self.client.repo_slug}/releases/assets/{asset['id']}",
            accept="application/octet-stream",
            expected_statuses=(200,),
        )
        if not content:
            return {}

        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, dict):
            raise PluginMarketError(f"Release asset '{self.asset_name}' must be a JSON object")

        normalized: dict[str, str] = {}
        for key, value in data.items():
            normalized[str(key)] = str(value)
        return normalized

    def save_checksums(self, checksums: dict[str, str]) -> None:
        release = self.get_release()
        existing_asset = self._find_asset(release)
        if existing_asset is not None:
            self.client.request(
                "DELETE",
                f"/repos/{self.client.repo_slug}/releases/assets/{existing_asset['id']}",
                expected_statuses=(204,),
            )

        upload_url = str(release.get("upload_url", "")).split("{", 1)[0]
        if not upload_url:
            raise PluginMarketError(f"Release '{self.release_tag}' does not provide an upload_url")

        payload = json.dumps(checksums, indent=2, ensure_ascii=False).encode("utf-8")
        target = f"{upload_url}?name={urllib.parse.quote(self.asset_name, safe='')}"
        self.client.request(
            "POST",
            target,
            body=payload,
            accept="application/vnd.github+json",
            extra_headers={"Content-Type": "application/json"},
            expected_statuses=(201,),
        )

    def upsert_checksum(self, plugin_id: str, sha256: str) -> dict[str, str]:
        checksums = self.load_checksums()
        checksums[plugin_id] = sha256
        self.save_checksums(checksums)
        return checksums

