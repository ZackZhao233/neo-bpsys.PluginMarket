from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "PluginManifests"
PLUGIN_INDEX_PATH = REPO_ROOT / "PluginIndex.json"

DEFAULT_STATE_RELEASE_TAG = os.environ.get("PLUGIN_MARKET_STATE_RELEASE_TAG", "market-state")
DEFAULT_STATE_ASSET_NAME = os.environ.get("PLUGIN_MARKET_STATE_ASSET_NAME", "checksums.json")


class PluginMarketError(RuntimeError):
    """Base exception for plugin market automation."""


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"::warning::{message}", flush=True)


def error(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr, flush=True)


def write_github_output(name: str, value: Any) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    rendered = "" if value is None else str(value)
    with Path(output_path).open("a", encoding="utf-8") as handle:
        if "\n" in rendered:
            handle.write(f"{name}<<__PLUGIN_MARKET_EOF__\n{rendered}\n__PLUGIN_MARKET_EOF__\n")
        else:
            handle.write(f"{name}={rendered}\n")


def append_step_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json_file(path: Path, *, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, data: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd or REPO_ROOT,
        check=False,
        capture_output=capture_output,
        text=text,
    )
    if check and completed.returncode != 0:
        raise PluginMarketError(
            f"Command failed ({completed.returncode}): {' '.join(args)}\n{completed.stderr.strip()}"
        )
    return completed


def git_diff_name_only(base_ref: str, head_ref: str) -> list[str]:
    completed = run_command(["git", "diff", "--name-only", base_ref, head_ref], cwd=REPO_ROOT)
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def git_show_text(ref: str, path: str) -> str:
    completed = run_command(["git", "show", f"{ref}:{path}"], cwd=REPO_ROOT)
    return completed.stdout


def download_file(
    url: str,
    destination: Path,
    *,
    retries: int = 3,
    timeout: int = 300,
    retry_delay_seconds: int = 5,
) -> Path:
    ensure_directory(destination.parent)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "neo-bpsys.PluginMarket automation",
                    "Accept": "*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                destination.write_bytes(response.read())
            if destination.stat().st_size == 0:
                raise PluginMarketError(f"Downloaded file is empty: {url}")
            return destination
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                log(f"Download attempt {attempt}/{retries} failed for {url}: {exc}")
                time.sleep(retry_delay_seconds)

    raise PluginMarketError(f"Failed to download {url}: {last_error}")


def parse_repo_slug(repo: str | None = None) -> tuple[str, str]:
    slug = repo or os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in slug:
        raise PluginMarketError(
            "GitHub repository slug is required. Set GITHUB_REPOSITORY or pass --repo owner/name."
        )
    owner, name = slug.split("/", 1)
    if not owner or not name:
        raise PluginMarketError(f"Invalid repository slug: {slug}")
    return owner, name


class GitHubApiClient:
    def __init__(
        self,
        *,
        repo: str | None = None,
        token: str | None = None,
        api_base_url: str = "https://api.github.com",
    ) -> None:
        self.owner, self.repo = parse_repo_slug(repo)
        self.api_base_url = api_base_url.rstrip("/")
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def _build_headers(
        self,
        *,
        accept: str = "application/vnd.github+json",
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "neo-bpsys.PluginMarket automation",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        endpoint_or_url: str,
        *,
        body: Any | None = None,
        accept: str = "application/vnd.github+json",
        extra_headers: dict[str, str] | None = None,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> bytes:
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            url = endpoint_or_url
        else:
            url = f"{self.api_base_url}{endpoint_or_url}"

        headers = self._build_headers(accept=accept, extra=extra_headers)
        payload: bytes | None

        if body is None:
            payload = None
        elif isinstance(body, (bytes, bytearray)):
            payload = bytes(body)
        else:
            payload = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(url, data=payload, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = response.getcode()
                content = response.read()
        except urllib.error.HTTPError as exc:
            content = exc.read()
            if exc.code in expected_statuses:
                return content
            detail = content.decode("utf-8", errors="replace")
            raise PluginMarketError(
                f"GitHub API request failed: {method} {url} -> {exc.code}\n{detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PluginMarketError(f"GitHub API request failed: {method} {url} -> {exc.reason}") from exc

        if status not in expected_statuses:
            detail = content.decode("utf-8", errors="replace")
            raise PluginMarketError(
                f"GitHub API request returned unexpected status: {method} {url} -> {status}\n{detail}"
            )

        return content

    def request_json(
        self,
        method: str,
        endpoint_or_url: str,
        *,
        body: Any | None = None,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> Any:
        content = self.request(
            method,
            endpoint_or_url,
            body=body,
            expected_statuses=expected_statuses,
        )
        if not content:
            return None
        return json.loads(content.decode("utf-8"))

    def paginate(self, endpoint: str) -> list[Any]:
        items: list[Any] = []
        page = 1
        separator = "&" if "?" in endpoint else "?"

        while True:
            data = self.request_json("GET", f"{endpoint}{separator}per_page=100&page={page}")
            if not data:
                break
            if not isinstance(data, list):
                raise PluginMarketError(f"Expected list response for pagination: {endpoint}")
            items.extend(data)
            if len(data) < 100:
                break
            page += 1

        return items

    def get_pull_request(self, number: int) -> dict[str, Any]:
        return self.request_json("GET", f"/repos/{self.repo_slug}/pulls/{number}")

    def get_pull_request_files(self, number: int) -> list[dict[str, Any]]:
        return self.paginate(f"/repos/{self.repo_slug}/pulls/{number}/files")

    def list_open_pull_requests(self, *, base: str | None = None) -> list[dict[str, Any]]:
        endpoint = f"/repos/{self.repo_slug}/pulls?state=open"
        if base:
            endpoint += f"&base={urllib.parse.quote(base)}"
        return self.paginate(endpoint)

    def get_file_content(self, path: str, *, ref: str) -> str:
        encoded_path = urllib.parse.quote(path, safe="/")
        data = self.request_json(
            "GET",
            f"/repos/{self.repo_slug}/contents/{encoded_path}?ref={urllib.parse.quote(ref, safe='')}",
        )
        if not isinstance(data, dict) or "content" not in data:
            raise PluginMarketError(f"Unable to fetch file content for {path} at ref {ref}")
        return base64.b64decode(data["content"]).decode("utf-8")

    def add_labels(self, issue_number: int, labels: list[str]) -> None:
        if not labels:
            return
        self.request_json(
            "POST",
            f"/repos/{self.repo_slug}/issues/{issue_number}/labels",
            body={"labels": labels},
            expected_statuses=(200,),
        )

    def remove_label(self, issue_number: int, label: str) -> None:
        encoded = urllib.parse.quote(label, safe="")
        try:
            self.request(
                "DELETE",
                f"/repos/{self.repo_slug}/issues/{issue_number}/labels/{encoded}",
                expected_statuses=(200, 404),
            )
        except PluginMarketError as exc:
            raise PluginMarketError(f"Failed to remove label '{label}' from PR #{issue_number}: {exc}") from exc

    def create_comment(self, issue_number: int, body: str) -> None:
        self.request_json(
            "POST",
            f"/repos/{self.repo_slug}/issues/{issue_number}/comments",
            body={"body": body},
            expected_statuses=(201,),
        )
