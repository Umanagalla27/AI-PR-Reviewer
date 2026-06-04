import httpx
from shared.github_client.auth import get_installation_token


async def get_pr_diff(repo_full_name: str, pr_number: int, installation_id: int) -> str:
    """Fetches the diff of a pull request."""
    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

    # Needs to handle rate limits and retries in a production app (can be added later)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


async def post_inline_comment(
    repo_full_name: str,
    pr_number: int,
    installation_id: int,
    commit_id: str,
    path: str,
    line: int,
    body: str,
) -> dict:
    """Posts an inline comment on a pull request."""
    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
    payload = {
        "body": body,
        "commit_id": commit_id,
        "path": path,
        "line": line,
        "side": "RIGHT",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def post_pr_summary(
    repo_full_name: str, pr_number: int, installation_id: int, commit_id: str, body: str
) -> dict:
    """Posts a PR review summary."""
    token = await get_installation_token(installation_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    payload = {"commit_id": commit_id, "body": body, "event": "COMMENT"}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
