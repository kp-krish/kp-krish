#!/usr/bin/env python3
"""
Rewrites the block between <!--START_SECTION:live--> and <!--END_SECTION:live-->
in README.md with numbers pulled live from the GitHub API.

Run by .github/workflows/live-stats.yml on a schedule, on every push,
and whenever a PR of yours gets opened or merged anywhere you can trigger it.
"""

import os
import sys
import datetime as dt
import urllib.request
import urllib.error
import json

USER = os.environ.get("GH_USER", "kp-krish")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
README = os.environ.get("README_PATH", "README.md")
START = "<!--START_SECTION:live-->"
END = "<!--END_SECTION:live-->"

API = "https://api.github.com"


def get(path):
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "live-stats-script")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"warn: {path} -> HTTP {e.code}", file=sys.stderr)
        return {}
    except Exception as e:  # noqa: BLE001
        print(f"warn: {path} -> {e}", file=sys.stderr)
        return {}


def count(query):
    from urllib.parse import quote
    data = get(f"/search/issues?q={quote(query)}&per_page=1")
    return int(data.get("total_count", 0))


def main():
    today = dt.date.today()
    month_ago = (today - dt.timedelta(days=30)).isoformat()

    prs_total = count(f"author:{USER} type:pr")
    prs_merged = count(f"author:{USER} type:pr is:merged")
    prs_open = count(f"author:{USER} type:pr is:open")
    prs_recent = count(f"author:{USER} type:pr created:>={month_ago}")
    issues_total = count(f"author:{USER} type:issue")
    reviews = count(f"reviewed-by:{USER} type:pr -author:{USER}")

    user = get(f"/users/{USER}")
    followers = user.get("followers", 0)
    public_repos = user.get("public_repos", 0)

    stars = 0
    page = 1
    while page <= 10:
        repos = get(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not isinstance(repos, list) or not repos:
            break
        stars += sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))
        if len(repos) < 100:
            break
        page += 1

    merge_rate = f"{(prs_merged / prs_total * 100):.0f}%" if prs_total else "n/a"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    block = f"""
## Pull request telemetry

<div align="center">

| | | |
| :--: | :--: | :--: |
| **{prs_total}** | **{prs_merged}** | **{prs_open}** |
| pull requests opened | merged | currently open |
| **{prs_recent}** | **{reviews}** | **{merge_rate}** |
| opened in last 30 days | PRs reviewed | merge rate |
| **{stars}** | **{public_repos}** | **{followers}** |
| stars earned | public repos | followers |

<sub>auto-refreshed by a GitHub Action. last run: {stamp}</sub>

</div>
"""

    with open(README, "r", encoding="utf-8") as f:
        content = f.read()

    if START not in content or END not in content:
        print("error: markers not found in README", file=sys.stderr)
        sys.exit(1)

    head, rest = content.split(START, 1)
    _, tail = rest.split(END, 1)
    new = f"{head}{START}\n{block}\n{END}{tail}"

    if new == content:
        print("no change")
        return

    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"updated: {prs_total} PRs, {prs_merged} merged, {stars} stars")


if __name__ == "__main__":
    main()
