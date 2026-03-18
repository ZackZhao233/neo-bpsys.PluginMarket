from __future__ import annotations

from plugin_market.common import GitHubApiClient


def find_conflicting_pull_requests(
    *,
    repo: str | None,
    token: str | None,
    current_pr_number: int,
    manifest_path: str,
    base_branch: str = "main",
) -> list[int]:
    client = GitHubApiClient(repo=repo, token=token)
    conflicts: list[int] = []

    for pull_request in client.list_open_pull_requests(base=base_branch):
        number = int(pull_request["number"])
        if number == current_pr_number:
            continue

        files = client.get_pull_request_files(number)
        changed_paths = {item.get("filename", "") for item in files}
        if manifest_path in changed_paths:
            conflicts.append(number)

    return sorted(conflicts)

