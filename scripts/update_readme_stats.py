#!/usr/bin/env python3
"""Refresh the numbers in the VulCodeCom profile READMEs (pl and en) from ghapi.

Rewrites four places, all from https://ghapi.dualfroz.com/v2/public:
- the intro sentence with lines of code and open source totals,
- the "In numbers" table and the diff block (between <!-- stats:summary --> markers),
- the languages table and the frameworks line (<!-- stats:languages -->),
- the open source list (<!-- stats:opensource -->).
Run it from the repository root: python3 scripts/update_readme_stats.py
"""
import json
import re
import urllib.request

API = "https://ghapi.dualfroz.com/v2/public"
FILES = {"pl": ["profile/README.md", "README.md"], "en": ["profile/README.en.md", "README.en.md"]}

TEXT = {
    "pl": {
        "loc": "linii kodu", "commits": "commitów", "projects": "projektów",
        "oss_stars": "gwiazdek projektów OSS", "oss_projects": "projektów open source",
        "languages": "języków", "days": "dni pracy",
        "added": "linii dodanych", "removed": "linii usuniętych", "net": "linii netto",
        "head": ("Język", "Linie kodu", "Commity", "Udział"),
        "oss_intro": "> Projekty, do których regularnie kontrybuujemy (tylko te z zaakceptowanymi zmianami). "
                     "Projekty posortowane według liczby gwiazdek. Łącznie {stars}+ ⭐ w {repos} repozytoriach.",
        "oss_head": "| Projekt | Gwiazdki | Język | Zmiany |",
    },
    "en": {
        "loc": "lines of code", "commits": "commits", "projects": "projects",
        "oss_stars": "OSS project stars", "oss_projects": "open source projects",
        "languages": "languages", "days": "working days",
        "added": "lines added", "removed": "lines removed", "net": "net lines",
        "head": ("Language", "Lines of code", "Commits", "Share"),
        "oss_intro": "Code that made it into projects we use every day. **{prs}** merged pull requests "
                     "in **{repos}** repositories with **{stars}+** stars combined.",
        "oss_head": "| Project | Stars | Language | Changes |",
    },
}


def get(path):
    request = urllib.request.Request(f"{API}{path}", headers={"User-Agent": "dualfroz-readme"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def num(value, lang):
    text = f"{int(value):,}"
    return text.replace(",", " ") if lang == "pl" else text


def floor_to(value, step):
    return value // step * step


def stars_short(value, lang):
    if value < 1000:
        return str(value)
    k = f"{value / 1000:.1f}".rstrip("0").rstrip(".")
    return f"{k.replace('.', ',')} tys." if lang == "pl" else f"{k}k"


def block(content, name, body):
    start, end = f"<!-- stats:{name} -->", f"<!-- /stats:{name} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(content):
        raise SystemExit(f"missing {start} markers")
    return pattern.sub(lambda _: f"{start}\n{body}\n{end}", content)


def summary(s, lang):
    t, oss = s["totals"], s["openSource"]["contributed"]
    T = TEXT[lang]
    net = t["linesAdded"] - t["linesRemoved"]
    return f"""<table>
  <tr>
    <td align="center" colspan="2" width="50%"><h3>{num(t["linesAdded"], lang)}</h3>{T["loc"]}</td>
    <td align="center" width="25%"><h3>{num(t["commits"], lang)}</h3>{T["commits"]}</td>
    <td align="center" width="25%"><h3>200+</h3>{T["projects"]}</td>
  </tr>
  <tr>
    <td align="center" width="25%"><h3>{num(floor_to(oss["stars"], 10_000), lang)}+</h3>{T["oss_stars"]}</td>
    <td align="center" width="25%"><h3>{num(oss["repos"], lang)}</h3>{T["oss_projects"]}</td>
    <td align="center" width="25%"><h3>{num(t["languages"], lang)}</h3>{T["languages"]}</td>
    <td align="center" width="25%"><h3>{num(t["activeDays"], lang)}</h3>{T["days"]}</td>
  </tr>
</table>

```diff
+ {num(t["linesAdded"], lang)} {T["added"]}
- {num(t["linesRemoved"], lang)} {T["removed"]}
! {num(net, lang)} {T["net"]}
```"""


def languages(langs, frameworks, icons, lang):
    T = TEXT[lang]
    rows = []
    for item in langs:
        pct = item["share"] * 100
        share = f"{pct:.1f}%"
        if lang == "pl":
            share = share.replace(".", ",")
        bar = "█" * max(1, round(pct / 4.5))
        icon = icons.get(item["name"], "")
        icon_td = f'<img src="{icon}" width="18" alt="{item["name"]}">' if icon else ""
        rows.append(
            f'    <tr><td>{icon_td}</td><td><b>{item["name"]}</b></td>'
            f'<td align="right">{num(item["linesAdded"], lang)}</td>'
            f'<td align="right">{num(item["commits"], lang)}</td>'
            f'<td align="right">{share} <sub>{bar}</sub></td></tr>'
        )
    head = "".join(f'<th align="{"left" if i == 0 else "right"}">{h}</th>' for i, h in enumerate(T["head"]))
    table = '<table align="center">\n  <tr><th></th>' + head + "</tr>\n" + "\n".join(rows) + "\n</table>"
    fw = " · ".join(f'{f["name"]} <sub>{f["repos"]}</sub>' for f in frameworks)
    heading = ("**Frameworki i narzędzia wykryte w projektach** <sub>(liczba repozytoriów)</sub>" if lang == "pl"
               else "**Frameworks & tools detected across projects** <sub>(repository count)</sub>")
    return f"{table}\n\n{heading}\n\n{fw}"


def opensource(oss, lang):
    T = TEXT[lang]
    merged = sorted((p for p in oss["projects"] if p["merged"] > 0), key=lambda p: -p["stars"])
    stars = floor_to(oss["contributed"]["stars"], 10_000)
    intro_line = T["oss_intro"].format(stars=num(stars, lang), repos=len(merged), prs=num(oss["pullRequests"]["merged"], lang))
    lines = [intro_line, "", T["oss_head"], "|---|---|---|---|"]
    for p in merged:
        lines.append(
            f'| [{p["name"]}]({p["url"]}) | ⭐ {stars_short(p["stars"], lang)} | {p.get("language") or "-"} | '
            f'<code>+{p["linesAdded"]}</code> <code>-{p["linesRemoved"]}</code> |'
        )
    return "\n".join(lines)


def intro(content, s, lang):
    t, oss = s["totals"], s["openSource"]["contributed"]
    millions = t["linesAdded"] // 1_000_000
    stars = floor_to(oss["stars"], 10_000)
    if lang == "pl":
        content = re.sub(r"ponad \*\*\d+ mln linijek kodu\*\*", f"ponad **{millions} mln linijek kodu**", content)
        content = re.sub(r"cegiełkę do \*\*\d+ repozytoriów open source\*\*", f"cegiełkę do **{oss['repos']} repozytoriów open source**", content)
        content = re.sub(r"mają \*\*[\d  ]+\+ gwiazdek\*\*", f"mają **{num(stars, lang)}+ gwiazdek**", content)
    else:
        content = re.sub(r"more than \*\*\d+ million lines of code\*\*", f"more than **{millions} million lines of code**", content)
        content = re.sub(r"contributed to \*\*\d+ open source repositories\*\*", f"contributed to **{oss['repos']} open source repositories**", content)
        content = re.sub(r"\*\*[\d,]+\+ combined stars\*\*", f"**{num(stars, lang)}+ combined stars**", content)
    return content


def main():
    frameworks = get("/frameworks")["frameworks"]
    oss = get("/opensource?limit=500")
    for lang, paths in FILES.items():
        s = get(f"/summary?lang={lang}")
        langs = get(f"/languages?limit=100&lang={lang}")["languages"]
        for path in paths:
            content = open(path, encoding="utf-8").read()
            icons = dict((m.group(2), m.group(1)) for m in re.finditer(
                r'<tr><td><img src="([^"]+)" width="18" alt="([^"]+)"></td>', content))
            content = intro(content, s, lang)
            content = block(content, "summary", summary(s, lang))
            content = block(content, "languages", languages(langs, frameworks, icons, lang))
            content = block(content, "opensource", opensource(oss, lang))
            open(path, "w", encoding="utf-8").write(content)
            print(f"{path}: updated")


if __name__ == "__main__":
    main()
