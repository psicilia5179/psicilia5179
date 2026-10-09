"""Build dark_mode.svg and light_mode.svg: ASCII portrait + neofetch-style card.

Run by .github/workflows/build.yml every day. Needs a token in ACCESS_TOKEN
(or GH_TOKEN) that can read the owner's private repos, so the counts include
private work. Only totals are published; repo names never leave this script.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
USER = "psicilia5179"
CODING_SINCE = 1998  # Uptime counts from here (Tono, 2026-10-08)
GITHUB_SINCE = 2023  # account opened 2023-09-16; first year of contributions

# --- card content --------------------------------------------------------
# Each row is either a header string, None (blank), or a list of (key, value)
# pairs. Keys may be dotted ("Languages.Real") and are coloured per part.
WIDTH = 56  # characters from the key to the end of the value

CARD = [
    ("header", "pedro@sicilia"),
    [("OS", "Windows 11, macOS/OS X, Linux, Android, iOS, iPadOS")],
    [("Uptime", "{uptime}")],
    [("Host", "Miami, FL")],
    [("Kernel", "Developer -> Sales -> back to building")],
    [("IDE", "Claude Code, Codex, VS Code")],
    None,
    [("Languages.Programming", "Python, TypeScript, JavaScript")],
    [("Languages.Computer", "HTML, CSS, SQL, Bash, YAML, Docker")],
    [("Languages.Real", "Spanish, English")],
    None,
    [("Method.Agents", "Plans, specs, tests still matter")],
    [("Builds.Current", "Agent tooling, self-hosted assistants")],
    [("Builds.Sales", "Live metrics dashboards for sales teams")],
    [("Open.To", "AI startups, new + returning devs")],
    None,
    ("header", "- Contact"),
    [("X", "@Pedro_artint")],
    [("GitHub", USER)],
    None,
    ("header", "- GitHub Stats"),
    [("Repos", "{repos}"), ("Commits", "{commits}")],
    [("Pull Requests", "{prs}"), ("Merged", "{merged}")],
    "contrib",
]

THEMES = {
    # shade: grey level of portrait glyphs for shade digit 0 (darkest) and 9.
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", value="#a5d6ff",
                 cc="#616e7f", shade=(70, 255)),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", value="#0a3069",
                  cc="#c2cfde", shade=(20, 190)),
}

# --- GitHub ----------------------------------------------------------------
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GH_TOKEN")


def request(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, (json.loads(r.read() or b"null"))


def graphql(query, **variables):
    _, data = request("https://api.github.com/graphql", {"query": query, "variables": variables})
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


REPOS_Q = """
query($after: String, $uid: ID!) {
  viewer {
    id
    repositories(first: 50, after: $after,
                 ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        owner { login }
        defaultBranchRef { target { ... on Commit { history(author: {id: $uid}) { totalCount } } } }
      }
    }
  }
}"""


def fetch_stats():
    uid = graphql("{ viewer { id } }")["viewer"]["id"]
    repos, after = [], None
    while True:
        v = graphql(REPOS_Q, after=after, uid=uid)["viewer"]
        repos += v["repositories"]["nodes"]
        page = v["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]

    owned = [r for r in repos if r["owner"]["login"] == USER]
    commits = sum(
        (r["defaultBranchRef"] or {}).get("target", {}).get("history", {}).get("totalCount", 0)
        for r in repos)

    _, prs = request(f"https://api.github.com/search/issues?q=author:{USER}+type:pr&per_page=1")
    _, merged = request(f"https://api.github.com/search/issues?q=author:{USER}+type:pr+is:merged&per_page=1")

    years = {}
    for year in range(GITHUB_SINCE, dt.date.today().year + 1):
        q = ('query($from: DateTime!, $to: DateTime!) { viewer { contributionsCollection(from: $from, to: $to)'
             ' { contributionCalendar { totalContributions } } } }')
        c = graphql(q, **{"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        years[str(year)] = c["viewer"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return {
        "repos": f"{len(owned)}",
        "commits": f"{commits:,}",
        "prs": f"{prs['total_count']:,}",
        "merged": f"{merged['total_count']:,}",
        "years": years,
    }


# --- rendering ---------------------------------------------------------------
def uptime(today):
    return f"{today.year - CODING_SINCE} years (coding since {CODING_SINCE})"


def grey(span, k):
    v = round(span[0] + (span[1] - span[0]) * k / 9)
    return f"#{v:02x}{v:02x}{v:02x}"


def shade_runs(line, shade):
    """Group consecutive glyphs of one shade into a single tspan."""
    out, i = [], 0
    while i < len(line):
        j = i
        while j < len(line) and shade[j] == shade[i]:
            j += 1
        text = esc(line[i:j])
        out.append(text if shade[i] == " " else f'<tspan class="s{shade[i]}">{text}</tspan>')
        i = j
    return "".join(out)


def esc(s):
    return html.escape(s, quote=False)


def key_spans(key):
    return ".".join(f'<tspan class="key">{esc(p)}</tspan>' for p in key.split("."))


def pair(key, value, width):
    dots = max(1, width - len(key) - len(value) - 3)
    return (f'{key_spans(key)}:<tspan class="cc"> {"." * dots} </tspan>'
            f'<tspan class="value">{esc(value)}</tspan>')


def render(theme, art, data):
    t = THEMES[theme]
    x_art, x_card, y0, lh = 15, 410, 30, 20
    art_y0, art_lh = 22, 12.5  # art uses 10px type: ~2.5x the card's detail
    lines = art["lines"]
    height = int(max(y0 + lh * (len(CARD) - 1), art_y0 + art_lh * (len(lines) - 1))) + 30
    out = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" '
        f'width="985px" height="{height}px" font-size="16px">',
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
        " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        f".key {{fill: {t['key']};}} .value {{fill: {t['value']};}} .cc {{fill: {t['cc']};}}",
        " ".join(f".s{k} {{fill: {grey(t['shade'], k)};}}" for k in range(10)),
        "text, tspan {white-space: pre;}",
        "</style>",
        f'<rect width="985px" height="{height}px" fill="{t["bg"]}" rx="15"/>',
        f'<text x="{x_art}" y="{art_y0}" font-size="10px">',
    ]
    for i, (line, shade) in enumerate(zip(lines, art["shades"])):
        out.append(f'<tspan x="{x_art}" y="{art_y0 + i * art_lh:g}">{shade_runs(line, shade)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{x_card}" y="{y0}" fill="{t["text"]}">')
    for i, row in enumerate(CARD):
        y = y0 + i * lh
        lead = f'<tspan x="{x_card}" y="{y}" class="cc">. </tspan>'
        if row is None:
            continue
        if isinstance(row, tuple):
            label = row[1]
            rule = "-" + "—" * (WIDTH - len(label) - 3) +"-—-"
            out.append(f'<tspan x="{x_card}" y="{y}">{esc(label)}</tspan> {rule}')
        elif row == "contrib":
            years = data["years"]
            total = f"{sum(years.values()):,}"
            recent = ", ".join(f"{y}: {n:,}" for y, n in list(years.items())[-2:])
            out.append(lead + pair("Contributions", f"{total} ({recent})", WIDTH))
        elif len(row) == 1:
            k, v = row[0]
            out.append(lead + pair(k, v.format(**data), WIDTH))
        else:
            (k1, v1), (k2, v2) = row
            left_w = 30
            out.append(lead + pair(k1, v1.format(**data), left_w)
                       + ' | ' + pair(k2, v2.format(**data), WIDTH - left_w - 3))
    out.append("</text>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    stats_file = ROOT / "cache" / "stats.json"
    if "--offline" in sys.argv:  # re-render from the last fetch
        data = json.loads(stats_file.read_text())
    else:
        data = fetch_stats()
        stats_file.write_text(json.dumps(data, indent=1) + "\n")
    data["uptime"] = uptime(dt.date.today())
    print(json.dumps({k: v for k, v in data.items()}, default=str))
    art = json.loads((ROOT / "art.json").read_text(encoding="utf-8"))
    for theme in ("dark", "light"):
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, art[theme], data), encoding="utf-8")


if __name__ == "__main__":
    main()
