#!/usr/bin/env python3
"""Refresh the numbers in the VulCodeCom profile READMEs (pl and en) from ghapi.

Rewrites four places, all from https://ghapi.dualfroz.com/v2/public:
- the intro sentence with lines of code and open source totals,
- the "In numbers" table and the diff block (between <!-- stats:summary --> markers),
- the languages table and the frameworks line (<!-- stats:languages -->),
- the open source list (<!-- stats:opensource -->).
Everything is fetched before any file is touched: when the API stays unreachable after
retries the files are left as they are and the script exits with 1. A section whose data
is missing or empty keeps its current content.
Run it from the repository root: python3 scripts/update_readme_stats.py
"""
import http.client
import json
import re
import sys
import time
import urllib.request

apiBase = "https://ghapi.dualfroz.com/v2/public"
headlineUrl = "https://vulcode.com/headline.json"
proxmoxExtra = {"repos": 1, "merged": 6}
readmeFiles = {"pl": ["profile/README.md", "README.md"], "en": ["profile/README.en.md", "README.en.md"]}
userAgent = "readme-stats"
attempts = 5
requestTimeout = 20

labels = {
    "pl": {
        "loc": "linii kodu", "commits": "commitów", "projects": "projektów",
        "ossStars": "gwiazdek projektów OSS", "ossProjects": "projektów open source",
        "languages": "języków", "days": "dni pracy",
        "added": "linii dodanych", "removed": "linii usuniętych", "net": "linii netto",
        "head": ("Język", "Linie kodu", "Commity", "Udział"),
        "ossIntro": "> Projekty, do których regularnie kontrybuujemy (tylko te z zaakceptowanymi zmianami). "
                    "Projekty posortowane według liczby gwiazdek. Łącznie {stars}+ ⭐ w {repos} repozytoriach.",
        "ossHead": "| Projekt | Gwiazdki | Język | Zmiany |",
    },
    "en": {
        "loc": "lines of code", "commits": "commits", "projects": "projects",
        "ossStars": "OSS project stars", "ossProjects": "open source projects",
        "languages": "languages", "days": "working days",
        "added": "lines added", "removed": "lines removed", "net": "net lines",
        "head": ("Language", "Lines of code", "Commits", "Share"),
        "ossIntro": "Code that made it into projects we use every day. **{prs}** merged pull requests "
                    "in **{repos}** repositories with **{stars}+** stars combined.",
        "ossHead": "| Project | Stars | Language | Changes |",
    },
}


class ApiError(Exception):
    pass


def get(path):
    url = path if path.startswith("http") else f"{apiBase}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": userAgent, "Accept": "application/json"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=requestTimeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError(f"expected a JSON object, got {type(payload).__name__}")
            return payload
        except (OSError, http.client.HTTPException, ValueError) as error:
            print(f"{url}: attempt {attempt}/{attempts} failed: {error}", file=sys.stderr)
            if attempt == attempts:
                raise ApiError(f"{url}: {error}") from error
            time.sleep(5 * attempt)


def num(value, lang):
    text = f"{int(value):,}"
    return text.replace(",", " ") if lang == "pl" else text


def floorTo(value, step):
    return int(value) // step * step


def starsShort(value, lang):
    if value < 1000:
        return str(value)
    thousands = f"{value / 1000:.1f}".rstrip("0").rstrip(".")
    return f"{thousands.replace('.', ',')} tys." if lang == "pl" else f"{thousands}k"


def block(content, name, body):
    start, end = f"<!-- stats:{name} -->", f"<!-- /stats:{name} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(content):
        raise ValueError(f"missing {start} markers")
    return pattern.sub(lambda _: f"{start}\n{body}\n{end}", content)


def summary(stats, projects, lang):
    totals, oss = stats["totals"], stats["openSource"]["contributed"]
    words = labels[lang]
    net = totals["linesAdded"] - totals["linesRemoved"]
    return f"""<table>
  <tr>
    <td align="center" colspan="2" width="50%"><h3>{num(totals["lines"], lang)}</h3>{words["loc"]}</td>
    <td align="center" width="25%"><h3>{num(totals["commits"], lang)}</h3>{words["commits"]}</td>
    <td align="center" width="25%"><h3>{num(projects, lang)}+</h3>{words["projects"]}</td>
  </tr>
  <tr>
    <td align="center" width="25%"><h3>{num(floorTo(oss["stars"], 10_000), lang)}+</h3>{words["ossStars"]}</td>
    <td align="center" width="25%"><h3>{num(oss["repos"] + proxmoxExtra["repos"], lang)}</h3>{words["ossProjects"]}</td>
    <td align="center" width="25%"><h3>{num(totals["languages"], lang)}</h3>{words["languages"]}</td>
    <td align="center" width="25%"><h3>{num(totals["activeDays"], lang)}</h3>{words["days"]}</td>
  </tr>
</table>

```diff
+ {num(totals["linesAdded"], lang)} {words["added"]}
- {num(totals["linesRemoved"], lang)} {words["removed"]}
! {num(net, lang)} {words["net"]}
```"""


def languages(langs, frameworks, icons, lang):
    if not langs or not frameworks:
        raise ValueError("empty languages or frameworks list")
    words = labels[lang]
    rows = []
    for language in langs:
        percent = language["share"] * 100
        share = f"{percent:.1f}%"
        if lang == "pl":
            share = share.replace(".", ",")
        bar = "█" * max(1, round(percent / 4.5))
        icon = icons.get(language["name"], "")
        iconCell = f'<img src="{icon}" width="18" alt="{language["name"]}">' if icon else ""
        rows.append(
            f'    <tr><td>{iconCell}</td><td><b>{language["name"]}</b></td>'
            f'<td align="right">{num(language["linesAdded"], lang)}</td>'
            f'<td align="right">{num(language["commits"], lang)}</td>'
            f'<td align="right">{share} <sub>{bar}</sub></td></tr>'
        )
    head = "".join(f'<th align="{"left" if i == 0 else "right"}">{h}</th>' for i, h in enumerate(words["head"]))
    table = '<table align="center">\n  <tr><th></th>' + head + "</tr>\n" + "\n".join(rows) + "\n</table>"
    frameworkLine = " · ".join(f'{framework["name"]} <sub>{framework["repos"]}</sub>' for framework in frameworks)
    heading = ("**Frameworki i narzędzia wykryte w projektach** <sub>(liczba repozytoriów)</sub>" if lang == "pl"
               else "**Frameworks & tools detected across projects** <sub>(repository count)</sub>")
    return f"{table}\n\n{heading}\n\n{frameworkLine}"


def opensource(oss, lang):
    words = labels[lang]
    merged = sorted((project for project in oss["projects"] if project.get("merged", 0) > 0),
                    key=lambda project: -project.get("stars", 0))
    if not merged:
        raise ValueError("no merged open source projects")
    stars = floorTo(oss["contributed"]["stars"], 10_000)
    repos = oss["contributed"]["repos"] + proxmoxExtra["repos"]
    prs = oss["pullRequests"]["merged"] + proxmoxExtra["merged"]
    introLine = words["ossIntro"].format(stars=num(stars, lang), repos=repos, prs=num(prs, lang))
    lines = [introLine, "", words["ossHead"], "|---|---|---|---|"]
    for project in merged:
        lines.append(
            f'| [{project["name"]}]({project["url"]}) | ⭐ {starsShort(project.get("stars", 0), lang)} | '
            f'{project.get("language") or "-"} | '
            f'<code>+{project.get("linesAdded", 0)}</code> <code>-{project.get("linesRemoved", 0)}</code> |'
        )
    return "\n".join(lines)


def intro(content, stats, projects, lang):
    totals, oss = stats["totals"], stats["openSource"]["contributed"]
    millions = int(totals["lines"]) // 1_000_000
    stars = floorTo(oss["stars"], 10_000)
    repos = oss["repos"] + proxmoxExtra["repos"]
    if lang == "pl":
        content = re.sub(r"ponad \*\*\d+ mln linijek kodu\*\*", f"ponad **{millions} mln linijek kodu**", content)
        content = re.sub(r"cegiełkę do \*\*\d+ repozytoriów open source\*\*", f"cegiełkę do **{repos} repozytoriów open source**", content)
        content = re.sub(r"mają \*\*[\d  ]+\+ gwiazdek\*\*", f"mają **{num(stars, lang)}+ gwiazdek**", content)
        content = re.sub(r"w \*\*\d+\+ projektach\*\*", f"w **{projects}+ projektach**", content)
    else:
        content = re.sub(r"more than \*\*\d+ million lines of code\*\*", f"more than **{millions} million lines of code**", content)
        content = re.sub(r"contributed to \*\*\d+ open source repositories\*\*", f"contributed to **{repos} open source repositories**", content)
        content = re.sub(r"\*\*[\d,]+\+ combined stars\*\*", f"**{num(stars, lang)}+ combined stars**", content)
        content = re.sub(r"across \*\*\d+\+ projects\*\*", f"across **{projects}+ projects**", content)
    return content


def section(content, name, render):
    try:
        return render(content)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        print(f"::warning::{name} left unchanged: {type(error).__name__}: {error}", file=sys.stderr)
        return content


def fetchAll():
    sources = {
        "frameworks": get("/frameworks").get("frameworks"),
        "opensource": get("/opensource?limit=500"),
        "projects": get(headlineUrl).get("projects"),
    }
    for lang in readmeFiles:
        sources[f"summary:{lang}"] = get(f"/summary?lang={lang}")
        sources[f"languages:{lang}"] = get(f"/languages?limit=100&lang={lang}").get("languages")
    return sources


def render(content, sources, lang):
    stats, projects = sources[f"summary:{lang}"], sources["projects"]
    icons = dict((m.group(2), m.group(1)) for m in re.finditer(
        r'<tr><td><img src="([^"]+)" width="18" alt="([^"]+)"></td>', content))
    if projects is None:
        print("::warning::headline.json has no projects, intro and summary left unchanged", file=sys.stderr)
    else:
        content = section(content, "intro", lambda text: intro(text, stats, projects, lang))
        content = section(content, "summary", lambda text: block(text, "summary", summary(stats, projects, lang)))
    content = section(content, "languages", lambda text: block(
        text, "languages", languages(sources[f"languages:{lang}"], sources["frameworks"], icons, lang)))
    content = section(content, "opensource", lambda text: block(
        text, "opensource", opensource(sources["opensource"], lang)))
    return content


def main():
    try:
        sources = fetchAll()
    except ApiError as error:
        print(f"::error::API unreachable, README files left untouched: {error}", file=sys.stderr)
        sys.exit(1)
    for lang, paths in readmeFiles.items():
        for path in paths:
            with open(path, encoding="utf-8") as file:
                current = file.read()
            updated = render(current, sources, lang)
            if updated == current:
                print(f"{path}: unchanged")
                continue
            with open(path, "w", encoding="utf-8") as file:
                file.write(updated)
            print(f"{path}: updated")


if __name__ == "__main__":
    main()
