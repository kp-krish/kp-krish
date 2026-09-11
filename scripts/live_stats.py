#!/usr/bin/env python3
"""
Generates assets/stats.svg from live GitHub API data and rewrites the
live block in README.md.

No external rendering service is involved, so the card cannot rate-limit,
404, or go down. The SVG is committed to the repo like any other asset.

Metrics that would read as weak (zero stars, tiny streaks) are skipped
automatically rather than displayed as zeros.
"""

import os
import sys
import json
import datetime as dt
import urllib.request
import urllib.error
from urllib.parse import quote
from html import escape

USER = os.environ.get("GH_USER", "kp-krish")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
README = os.environ.get("README_PATH", "README.md")
SVG_OUT = os.environ.get("SVG_PATH", "assets/stats.svg")
MOCK = os.environ.get("MOCK") == "1"

START = "<!--START_SECTION:live-->"
END = "<!--END_SECTION:live-->"
API = "https://api.github.com"

BG = "#0d1117"
CARD = "#161b22"
BORDER = "#21262d"
ACCENT = "#7c3aed"
TEXT = "#e6edf3"
MUTED = "#8b949e"

LANG_COLORS = {
    "Python": "#3572A5", "Java": "#b07219", "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6", "Jupyter Notebook": "#DA5B0B", "HTML": "#e34c26",
    "CSS": "#563d7c", "C++": "#f34b7d", "C": "#555555", "Go": "#00ADD8",
    "Shell": "#89e051", "Rust": "#dea584", "Dockerfile": "#384d54",
    "SCSS": "#c6538c", "Vue": "#41b883", "Kotlin": "#A97BFF", "PHP": "#4F5D95",
}
FALLBACK_COLORS = ["#7c3aed", "#2f81f7", "#3fb950", "#d29922", "#db61a2", "#a371f7"]


def get(path):
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats")
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
    return int(get(f"/search/issues?q={quote(query)}&per_page=1").get("total_count", 0))


def collect():
    if MOCK:
        return {
            "prs_total": 20, "prs_merged": 14, "prs_open": 6, "prs_recent": 7,
            "reviews": 3, "repos": 18, "stars": 4, "followers": 11,
            "langs": [("Python", 52.0), ("Java", 18.5), ("TypeScript", 12.0),
                      ("Jupyter Notebook", 9.5), ("HTML", 5.0), ("Shell", 3.0)],
        }

    prs_total = count(f"author:{USER} type:pr")
    data = {
        "prs_total": prs_total,
        "prs_merged": count(f"author:{USER} type:pr is:merged"),
        "prs_open": count(f"author:{USER} type:pr is:open"),
        "prs_recent": count(
            f"author:{USER} type:pr created:>="
            f"{(dt.date.today() - dt.timedelta(days=90)).isoformat()}"
        ),
        "reviews": count(f"reviewed-by:{USER} type:pr -author:{USER}"),
    }

    user = get(f"/users/{USER}")
    data["followers"] = user.get("followers", 0)

    repos, page = [], 1
    while page <= 10:
        batch = get(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    owned = [r for r in repos if not r.get("fork")]
    data["repos"] = len(owned)
    data["stars"] = sum(r.get("stargazers_count", 0) for r in owned)

    totals = {}
    for r in owned[:40]:
        langs = get(f"/repos/{USER}/{r['name']}/languages")
        if isinstance(langs, dict):
            for name, size in langs.items():
                totals[name] = totals.get(name, 0) + size
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    data["langs"] = [(n, round(v / grand * 100, 1)) for n, v in ranked]
    return data


def stat_tiles(d):
    """Only include tiles that are worth showing."""
    tiles = []
    if d["prs_total"]:
        tiles.append((str(d["prs_total"]), "pull requests"))
    if d["prs_merged"]:
        tiles.append((str(d["prs_merged"]), "merged"))
    if d["prs_total"]:
        tiles.append((f"{d['prs_merged'] / d['prs_total'] * 100:.0f}%", "merge rate"))
    if d["repos"]:
        tiles.append((str(d["repos"]), "repositories"))
    if d["prs_recent"]:
        tiles.append((str(d["prs_recent"]), "PRs this quarter"))
    if d["reviews"]:
        tiles.append((str(d["reviews"]), "code reviews"))
    if d["stars"] >= 5:
        tiles.append((str(d["stars"]), "stars earned"))
    if d["followers"] >= 10:
        tiles.append((str(d["followers"]), "followers"))
    return tiles[:6]


def build_svg(d):
    tiles = stat_tiles(d)
    langs = d["langs"]
    w, pad = 840, 28
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    tile_h, tile_gap = 74, 12
    grid_top = 78
    grid_h = rows * tile_h + max(0, rows - 1) * tile_gap
    lang_top = grid_top + grid_h + 30
    h = lang_top + (86 if langs else 0) + pad

    tile_w = (w - 2 * pad - (cols - 1) * tile_gap) / cols
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="GitHub activity summary">',
        "<style>"
        f".t{{font:700 30px 'Segoe UI',Ubuntu,sans-serif;fill:{TEXT}}}"
        f".l{{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:{MUTED};"
        "letter-spacing:.6px;text-transform:uppercase}"
        f".h{{font:600 15px 'Segoe UI',Ubuntu,sans-serif;fill:{TEXT}}}"
        f".s{{font:400 11px 'Segoe UI',Ubuntu,sans-serif;fill:{MUTED}}}"
        f".lg{{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:{TEXT}}}"
        "</style>",
        f'<rect width="{w}" height="{h}" rx="14" fill="{BG}" stroke="{BORDER}"/>',
        f'<rect x="{pad}" y="{pad}" width="4" height="20" rx="2" fill="{ACCENT}"/>',
        f'<text x="{pad + 16}" y="{pad + 16}" class="h">Engineering activity</text>',
        f'<text x="{w - pad}" y="{pad + 16}" class="s" text-anchor="end">'
        f'{escape(USER)} &#183; updated {dt.datetime.now(dt.timezone.utc):%d %b %Y}</text>',
    ]

    for i, (value, label) in enumerate(tiles):
        cx = pad + (i % cols) * (tile_w + tile_gap)
        cy = grid_top + (i // cols) * (tile_h + tile_gap)
        parts += [
            f'<rect x="{cx:.1f}" y="{cy}" width="{tile_w:.1f}" height="{tile_h}" '
            f'rx="10" fill="{CARD}" stroke="{BORDER}"/>',
            f'<text x="{cx + 18:.1f}" y="{cy + 38}" class="t">{escape(value)}</text>',
            f'<text x="{cx + 18:.1f}" y="{cy + 57}" class="l">{escape(label)}</text>',
        ]

    if langs:
        bar_w = w - 2 * pad
        parts.append(f'<text x="{pad}" y="{lang_top}" class="h">Language mix</text>')
        x = pad
        by = lang_top + 16
        for i, (name, pct) in enumerate(langs):
            seg = bar_w * pct / 100
            color = LANG_COLORS.get(name, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
            parts.append(
                f'<rect x="{x:.1f}" y="{by}" width="{max(seg, 2):.1f}" height="10" '
                f'fill="{color}"/>'
            )
            x += seg
        parts.append(
            f'<rect x="{pad}" y="{by}" width="{bar_w}" height="10" rx="5" '
            f'fill="none" stroke="{BG}" stroke-width="0"/>'
        )
        lx, ly = pad, by + 36
        for i, (name, pct) in enumerate(langs):
            color = LANG_COLORS.get(name, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
            parts += [
                f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>',
                f'<text x="{lx + 16}" y="{ly}" class="lg">'
                f'{escape(name)} {pct:.1f}%</text>',
            ]
            lx += 22 + len(f"{name} {pct:.1f}%") * 7
            if lx > w - 160 and i < len(langs) - 1:
                lx, ly = pad, ly + 22

    parts.append("</svg>")
    return "\n".join(parts)


def build_markdown(d):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    return (
        f'<div align="center">\n\n'
        f'<img src="assets/stats.svg" alt="GitHub activity summary" width="100%" />\n\n'
        f"<sub>generated by a scheduled GitHub Action, no third party services. "
        f"last run {stamp}</sub>\n\n"
        f"</div>"
    )


def main():
    d = collect()
    os.makedirs(os.path.dirname(SVG_OUT) or ".", exist_ok=True)
    with open(SVG_OUT, "w", encoding="utf-8") as f:
        f.write(build_svg(d))

    with open(README, "r", encoding="utf-8") as f:
        content = f.read()
    if START not in content or END not in content:
        print("error: markers missing from README", file=sys.stderr)
        sys.exit(1)
    head, rest = content.split(START, 1)
    _, tail = rest.split(END, 1)
    with open(README, "w", encoding="utf-8") as f:
        f.write(f"{head}{START}\n{build_markdown(d)}\n{END}{tail}")

    print(f"ok: {d['prs_total']} PRs, {d['prs_merged']} merged, {len(d['langs'])} langs")


if __name__ == "__main__":
    main()